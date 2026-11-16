# -*- coding: utf-8 -*-
"""
当前所在服务器定位
==================================================
为什么不读 C:\\Users\\1\\AppData\\Local\\fys ？
  · fys.broadcast.assistant.txt  未进服时只写占位文本，实测进服后也不刷新（本机验证）
  · logs\\fys.log                 19565 行全是 Base64 混淆块，零可读文本
  → 所以改用两条真实可用的通道：

通道 1（定位）：Steam 客户端日志 <Steam>\\logs\\console_log.txt
       每次通过 steam:// 连接服务器，Steam 都会记一行：
       [2026-09-21 15:58:21] ExecCommandLine: "... "steam://rungame/730/.../+connect 110.42.9.52:27901""
       取最后一条即"最近加入的服务器"。

通道 2（取图）：对该地址做 A2S 查询（Steam 服务器查询协议，UDP）
       A2S_INFO 直接返回 server name / map / 在线人数 / 最大人数
       → 这就是"实时检索服务器地图"的可靠做法，与 fys 客户端无关。

对外只暴露 detect()。
"""
import ctypes
import ctypes.wintypes as wt
import os
import re
import socket
import struct
import subprocess
import threading
import time
import urllib.parse

# ─────────────────── 进程 / Steam 目录 ───────────────────
def _pid_of(exe_name):
    """用 Toolhelp 快照找同名进程的 PID 列表。"""
    TH32CS_SNAPPROCESS = 0x00000002
    k = ctypes.windll.kernel32

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)), ("th32ModuleID", wt.DWORD),
            ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
            ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return []
    out = []
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = k.Process32First(snap, ctypes.byref(entry))
        target = exe_name.lower()
        while ok:
            if entry.szExeFile.decode("mbcs", "replace").lower() == target:
                out.append(int(entry.th32ProcessID))
            ok = k.Process32Next(snap, ctypes.byref(entry))
    finally:
        k.CloseHandle(snap)
    return out


def _proc_path(pid):
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        k.CloseHandle(h)
    return None


def cs2_pids():
    """cs2.exe 的全部 PID。"""
    return _pid_of("cs2.exe")


def cs2_running():
    """CS2 是否在运行；返回 (bool, exe路径或None)。"""
    for pid in _pid_of("cs2.exe"):
        p = _proc_path(pid)
        if p:
            return True, p
    return False, None


_REMOTE = re.compile(r"^\[?([0-9a-fA-F:.]+)\]?:(\d+)$")


def udp_peers(pids=None):
    """
    通道 3（强信号）：读 netstat，拿 cs2.exe 那些 **已建立对端** 的 UDP 连接。

    CS2 的游戏网络用 connect() 过的 UDP socket，Windows 会因此在 netstat 里
    显示「本地地址 -> 外部地址」；未 connect 的 UDP 才是 *:*。
    → 有对端 = 这一刻真的连着那台服务器（比 A2S「服务器还活着」强得多）。

    返回 {ip:port} 集合；拿不到（没权限 / 全是 *:* / 没装 netstat）返回空集。
    """
    pids = cs2_pids() if pids is None else pids
    if not pids:
        return set()
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "UDP"],
                             capture_output=True, text=True, encoding="mbcs",
                             errors="replace", timeout=4,
                             creationflags=0x08000000)          # CREATE_NO_WINDOW
    except Exception:                                           # noqa: BLE001
        return set()
    want = set(int(p) for p in pids)
    peers = set()
    for line in (out.stdout or "").splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0].upper() != "UDP":
            continue
        try:
            if int(parts[-1]) not in want:                      # 末列 = PID
                continue
        except ValueError:
            continue
        remote = parts[2]
        if remote in ("*:*", "0.0.0.0:0") or remote.startswith("*"):
            continue
        m = _REMOTE.match(remote)
        if m and m.group(1) not in ("0.0.0.0", "::"):
            peers.add("%s:%d" % (m.group(1), int(m.group(2))))
    return peers


_ROOT_CACHE = {"at": 0.0, "dir": None}


def steam_root(force=False, ttl=30.0):
    """找 Steam 安装目录。可用 FYS_STEAM_DIR 覆盖（便于测试）。

    带 30 秒缓存：页面每秒轮询，而这个函数要查注册表 + 枚举进程，
    没必要每次都做。
    """
    now = time.time()
    if not force and _ROOT_CACHE["dir"] is not None and now - _ROOT_CACHE["at"] < ttl:
        return _ROOT_CACHE["dir"]
    root = _steam_root_uncached()
    _ROOT_CACHE.update(at=now, dir=root)
    return root


def _steam_root_uncached():
    override = os.environ.get("FYS_STEAM_DIR")
    if override:
        return override
    cands = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            v, _ = winreg.QueryValueEx(k, "SteamPath")
            if v:
                cands.append(v.replace("/", os.sep))
    except OSError:
        pass
    for pid in _pid_of("steam.exe"):
        p = _proc_path(pid)
        if p:
            cands.append(os.path.dirname(p))
    cands += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam",
              r"D:\Steam", r"E:\Steam", r"F:\Steam"]
    for c in cands:
        if c and os.path.exists(os.path.join(c, "logs", "console_log.txt")):
            return c
    for c in cands:
        if c and os.path.isdir(c):
            return c
    return None


# ─────────────────── 通道 1：Steam 连接日志 ───────────────────
LINE_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
ADDR = re.compile(r"([A-Za-z0-9_.\-]+):(\d{2,5})")


def parse_connects(text):
    """从 steam console_log 文本里抽出所有 connect 目标，按时间正序。"""
    found = []
    for line in text.splitlines():
        if "connect" not in line.lower():
            continue
        ts = None
        m = LINE_TS.match(line)
        if m:
            ts = m.group(1)
        # URL 里 %20 被编码；先整体还原
        s = urllib.parse.unquote(line)
        for cm in re.finditer(r"connect[\s/]+", s, re.IGNORECASE):
            tail = s[cm.end():]
            am = ADDR.match(tail.lstrip())
            if am:
                host, port = am.group(1), int(am.group(2))
                if port <= 0:
                    continue
                found.append({"ts": ts, "host": host, "port": port,
                              "address": "%s:%d" % (host, port), "line": line.strip()})
    return found


_LAST_CACHE = {"key": None, "item": None}


def last_connect(steam_dir, tail_bytes=600_000):
    """
    读 console_log 尾部，返回最近一次 connect 记录与该日志路径。

    console_log.txt 动辄几百 MB，而页面每秒都在轮询；按 (mtime, size) 命中缓存，
    日志没变就不重复读那 600KB。
    """
    if not steam_dir:
        return None, None
    p = os.path.join(steam_dir, "logs", "console_log.txt")
    if not os.path.exists(p):
        return None, p
    try:
        st = os.stat(p)
        key = (p, st.st_mtime_ns, st.st_size)
    except OSError:
        return None, p
    if _LAST_CACHE["key"] == key:
        return _LAST_CACHE["item"], p
    try:
        with open(p, "rb") as fh:
            if st.st_size > tail_bytes:
                fh.seek(st.st_size - tail_bytes)
                fh.readline()          # 丢掉半行
            raw = fh.read()
    except OSError:
        return None, p
    txt = raw.decode("utf-8", "replace")
    items = parse_connects(txt)
    item = None
    if items:
        items.sort(key=lambda x: x["ts"] or "")
        item = items[-1]
    _LAST_CACHE.update(key=key, item=item)
    return item, p


# ⚠ 以下四个函数（connect_history / favorites_addresses / harvest_addresses /
#   is_ze）在「探测固定 9 台服务器」改造后已无任何调用者，属历史遗留。
#   连同 reward_server.py 的 PAGE / Handler / main()（旧版独立服务入口）一起，
#   可在下次大版本清理掉，能省下约 450 行与对应打包体积。保留是为了避免
#   与 spec 的打包引用发生意外，暂不删除。
def connect_history(steam_dir, tail_bytes=600_000, limit=12):
    """最近若干次 connect（去重后倒序），用于展示"最近去过"。"""
    last, _ = last_connect(steam_dir, tail_bytes)
    return last, None


def favorites_addresses(steam_dir):
    """
    读 Steam 服务器浏览器「收藏夹」：userdata/<账号>/7/remote/serverbrowser_hist.vdf
    里 "Filters"→"favorites" 段。文件里 name/address 存的就是 ip:port。
    返回 [{address, source:'favorite'}]。
    """
    if not steam_dir:
        return []
    udir = os.path.join(steam_dir, "userdata")
    if not os.path.isdir(udir):
        return []
    out, seen = [], set()

    def block(s, start):
        """从 '{' 起做花括号配对，返回块文本。"""
        depth, i = 0, start
        while i < len(s):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
            i += 1
        return s[start:]

    for uid in os.listdir(udir):
        p = os.path.join(udir, uid, "7", "remote", "serverbrowser_hist.vdf")
        if not os.path.exists(p):
            continue
        try:
            s = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        m = re.search(r'"favorites"\s*\{', s)
        if not m:
            continue
        for am in re.finditer(r'"address"\s*"([^"]+)"', block(s, m.end() - 1)):
            a = am.group(1).strip()
            hm = re.match(r"([A-Za-z0-9_.\-]+):(\d{2,5})$", a)
            if not hm or a in seen:
                continue
            seen.add(a)
            out.append({"address": a, "host": hm.group(1),
                        "port": int(hm.group(2)), "source": "favorite"})
    return out


def harvest_addresses(steam_dir, max_age_days=14, cap=60):
    """
    服务器清单 = Steam 连接历史（近 max_age_days 天） + 服务器浏览器收藏夹。
    返回 [{address, host, port, ts, ts_epoch, source}]，收藏夹在前。
    """
    if not steam_dir:
        return []
    favs = favorites_addresses(steam_dir)
    p = os.path.join(steam_dir, "logs", "console_log.txt")
    hist = []
    if os.path.exists(p):
        try:
            with open(p, "rb") as fh:
                raw = fh.read(8 << 20)          # 最多读 8MB
        except OSError:
            raw = b""
        items = parse_connects(raw.decode("utf-8", "replace"))
        cutoff = time.time() - max_age_days * 86400
        best = {}
        for it in items:
            ts = it.get("ts")
            if not ts:
                continue
            try:
                t = time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                continue
            if t < cutoff:
                continue
            a = it["address"]
            if a not in best or t > best[a]["ts_epoch"]:
                best[a] = {"address": a, "host": it["host"], "port": it["port"],
                           "ts": ts, "ts_epoch": t, "source": "history"}
        hist = sorted(best.values(), key=lambda r: -r["ts_epoch"])
    seen = {r["address"] for r in favs}
    rows = favs + [r for r in hist if r["address"] not in seen]
    return rows[:cap]


def scan_addresses(rows, timeout=1.2, workers=24):
    """并发 A2S 探测一批地址，返回在线的服务器（含地图）。"""
    import concurrent.futures as cf

    def one(r):
        info = a2s_info(r["host"], r["port"], timeout=timeout, attempts=2, gap=0.25)
        if "err" in info:
            return None
        out = dict(r)
        out.update({
            "name": clean_name(info.get("name")), "map": info.get("map"),
            "players": info.get("players"), "maxplayers": info.get("maxplayers"),
            "bots": info.get("bots"), "version": info.get("version"),
        })
        return out

    out = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(one, rows):
            if res:
                out.append(res)
    return out


FYS_MARKS = ("風雲", "风云", "風 雲", "fyscs", "FYS", "風  雲")

_QGROUP_RE = re.compile(r"\s*Q群\s*[:：]?\s*\d+\s*")


def clean_name(s):
    """去掉服务器名里的「Q群:xxxx」推广后缀（显示层统一清洗）。"""
    if not s:
        return s
    s = _QGROUP_RE.sub(" ", s).strip()
    return s or None


def is_fys(name):
    if not name:
        return False
    n = name.replace(" ", "")
    return any(m.replace(" ", "") in n for m in FYS_MARKS)


ZE_MARKS = ("僵尸逃跑", "僵尸逃", "[ze]", "［ze］")
ZE_EXCLUDE = ("多线",)          # 多线CN 服务器不在看板里


def is_ze(name, map_name=None):
    """只认僵尸逃跑（ZE）服：服务器名带「僵尸逃跑」/「[ZE]」，或当前地图是 ze_ 开头。"""
    n = (name or "").replace(" ", "").lower()
    if any(m in n for m in ZE_EXCLUDE):
        return False
    if any(m in n for m in ZE_MARKS):
        return True
    if (map_name or "").lower().startswith("ze_"):
        return True
    return False


_SRV_CACHE = {"at": 0.0, "rows": [], "addresses": 0}

# ────────── 風雲社僵尸逃跑 ZE 服清单（官网动态优先，下面是兜底表） ──────────
# 风雲社同时运营两套服：
#   · CS2  ：s1~s9.cs2ze.com:27015~27095，官网 modeId = 2001   ← 本看板只跟这套
#   · CS:GO：19.csgoze.com:27111（僵尸逃跑⑲）等，官网 modeId = 1001（旧版 1xxx 系）
# ⚠ 2026-11-15 复盘（又一次「跟不过去」）：兜底表原样写死 IP，运维换 IP 后就抓瞎——
#   实测 02# 实际在 110.42.9.107（表里写 203）、06# 实际在 110.42.9.155（表里写 107），
#   09# 已从官网清单一并下线（表里还挂着死地址 203:27095）。
#   → 兜底表改**按域名**存（sN.cs2ze.com，端口规则 27015+(N-1)*10），运行时 DNS 解析，
#     IP 变了自动跟随；下面 _FALLBACK_STATIC 只是 DNS 都解析不出来时的最后救命值。
#   → 官网清单可用时**只用官网清单**（不再拿兜底补齐，否则已下线的服会被救回来）。
FYS_SERVERS_FALLBACK = [
    ("s1.cs2ze.com", 27015, "01#"),
    ("s2.cs2ze.com", 27025, "02#"),
    ("s3.cs2ze.com", 27035, "03#"),
    ("s4.cs2ze.com", 27045, "04#"),
    ("s5.cs2ze.com", 27055, "05#"),
    ("s6.cs2ze.com", 27065, "06#"),
    ("s7.cs2ze.com", 27075, "07#"),
    ("s8.cs2ze.com", 27085, "08#"),
]
# DNS 全挂时的最后兜底（2026-11-15 实测值；只为「域名解析不出来」保命，
# 正常路径一律走域名解析，不要再把它当成服务器清单真值）
_FALLBACK_STATIC = {
    "s1.cs2ze.com": "110.42.9.155",
    "s2.cs2ze.com": "110.42.9.107",
    "s3.cs2ze.com": "110.42.9.139",
    "s4.cs2ze.com": "110.42.9.138",
    "s5.cs2ze.com": "110.42.9.138",
    "s6.cs2ze.com": "110.42.9.155",
    "s7.cs2ze.com": "110.42.9.139",
    "s8.cs2ze.com": "110.42.9.107",
}
FYS_SERVERS = FYS_SERVERS_FALLBACK      # 兼容旧引用（诊断脚本 / 云端脚本口径）


def _resolve_host(host):
    """域名 → IP（带 fys_web 的 TTL 缓存；解析失败退到 _FALLBACK_STATIC）。"""
    h = (host or "").strip().lower()
    if not h:
        return None
    if h.replace(".", "").isdigit():          # 已经是 IP
        return h
    try:
        import fys_web
        ip = fys_web.host_ip(h)
    except Exception:                          # noqa: BLE001
        ip = None
    return ip or _FALLBACK_STATIC.get(h)


FYS_SERVER_NAME = "❤️【風  雲】 僵尸逃跑 %s"      # 探测不到时的兜底显示名

CS2_MODE_MIN = 2000        # 官网 modeId：1xxx = CS:GO（旧版），2xxx = CS2

_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def _label_from_name(short, name=None):
    """「僵尸逃跑⑲」/「僵尸逃跑[ZE] 19#」→「19#」。认不出就原样返回简称。"""
    s = "%s %s" % (short or "", name or "")
    for i, ch in enumerate(_CIRCLED, 1):
        if ch in s:
            return "%02d#" % i
    m = re.search(r"(\d{1,2})\s*#", s)
    if m:
        try:
            return "%02d#" % int(m.group(1))
        except ValueError:
            pass
    return (short or name or "").strip() or "?"


_LISTS_CACHE = {"at": 0.0, "val": None}


def _is_cs2_item(it):
    """官网条目是不是 CS2（modeId 2xxx）。拿不到 modeId 时退而看域名里的 cs2。"""
    m = it.get("mode")
    if isinstance(m, int):
        return m >= CS2_MODE_MIN
    return "cs2" in (it.get("host") or "").lower()


def fys_lists(force=False, ttl=600.0):
    """官网 dashboard → {"ze": [(ip,port,label)], "ze_csgo": [...], "src": ...}。

    ze      = CS2 僵尸逃跑（本看板盯的这套）
    ze_csgo = CS:GO（旧版）僵尸逃跑，仅用于给玩家一句准确说明（别把 CS:GO 服当成 CS2）
    """
    now = time.time()
    # 还在用兜底表（官网快照还没热起来）时只缓存 60 秒，让它尽快换成官网清单
    eff = ttl if (_LISTS_CACHE["val"] or {}).get("src") == "web" else 60.0
    if not force and _LISTS_CACHE["val"] and now - _LISTS_CACHE["at"] < eff:
        return _LISTS_CACHE["val"]
    ze, ze_csgo, src = [], [], "fallback"
    try:
        import fys_web
        # 只读已抓到的缓存快照：绝不在这里触发同步 HTTPS（detect 每秒都会被调，
        # 首次请求不能被 6 秒超时卡住）。fys_web 自己的后台线程会持续刷新。
        fys_web._boot()
        snap = getattr(fys_web, "_SNAP", None) or {}
        if snap.get("at"):
            for it in (snap.get("ze") or []):
                ip = it.get("ip") or fys_web.host_ip(it.get("host"))
                port = it.get("port")
                if not (ip and isinstance(port, int) and port > 0):
                    continue
                row = (ip, port, _label_from_name(it.get("short"), it.get("name")))
                (ze if _is_cs2_item(it) else ze_csgo).append(row)
            if ze:
                src = "web"
    except Exception:                                          # noqa: BLE001
        ze, ze_csgo = [], []
    rows, seen = [], set()
    if ze:
        # 官网清单是权威：只认它，不再用兜底补齐（2026-11-15：09# 已下线，
        # 补齐会把它当成「还在」的服务器一直显示成探不到）。
        pool = ze
    else:
        # 官网拿不到 → 兜底表按域名解析（IP 变了自动跟随），端口用表里的固定值
        pool = [(_resolve_host(h), p, lab) for h, p, lab in FYS_SERVERS_FALLBACK]
    for h, p, lab in pool:
        if not h:
            continue
        a = "%s:%d" % (h, p)
        if a in seen:
            continue
        seen.add(a)
        rows.append((h, p, lab))
    rows.sort(key=lambda r: (r[2] or ""))
    ze_csgo = sorted({r for r in ze_csgo}, key=lambda r: (r[2] or ""))
    val = {"ze": rows, "ze_csgo": ze_csgo, "src": src}
    _LISTS_CACHE.update(at=now, val=val)
    return val


def ze_servers(force=False, ttl=600.0):
    """CS2 風雲社「僵尸逃跑」服务器清单 → [(host_ip, port, label)]（见 fys_lists）。"""
    return fys_lists(force=force, ttl=ttl)["ze"]


def csgo_ze_servers(force=False, ttl=600.0):
    """CS:GO（旧版）風雲社 ZE 服清单 → [(host_ip, port, label)]，可能为空。"""
    return fys_lists(force=force, ttl=ttl)["ze_csgo"]


def fixed_rows():
    """风向社 ZE 服清单 → 探测输入行（source=fixed 便于和动态抓取区分）。"""
    return [{"address": "%s:%d" % (h, p), "host": h, "port": p,
             "source": "fixed", "label": lab} for h, p, lab in ze_servers()]


def fys_servers(force=False, ttl=60.0):
    """
    風雲社「僵尸逃跑」服务器实时看板。

    清单来自官网 dashboard（fys_web）按 modeId 动态生成（只取 CS2 那套，见 ze_servers()），
    官网不可用时退回内置兜底表；每轮对这些地址做 A2S 实时探测，探不到的照样留在
    列表里（地图/人数显示为 —）。
    排序：按在线人数降序（探不到的排最后），人数相同时保持服号 01# → 09# 顺序。
    """
    now = time.time()
    if not force and _SRV_CACHE["rows"] and now - _SRV_CACHE["at"] < ttl:
        return _SRV_CACHE
    rows = fixed_rows()
    alive = {r["address"]: r for r in scan_addresses(rows)}
    out = []
    for r in rows:
        got = alive.get(r["address"])
        if got:
            got["label"] = r.get("label")
            out.append(got)
        else:
            miss = dict(r)
            miss.update({"name": FYS_SERVER_NAME % r.get("label"),
                         "map": None, "players": None, "maxplayers": None,
                         "query_ok": False})
            out.append(miss)
    out.sort(key=lambda r: -(r.get("players") or 0))   # 在线降序，探不到垫底；稳定排序保持服号次序
    _SRV_CACHE.update(at=now, rows=out, addresses=len(rows))
    return _SRV_CACHE


# ─────────────────── 通道 2：A2S 查询 ───────────────────
def _sock(timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    return s


def a2s_info(host, port, timeout=1.0, attempts=1, gap=0.18):
    """
    A2S_INFO：拿服务器名 / 地图 / 人数。失败返回 {'err': ...}。

    实测这几台服务器的 A2S 有很明显的丢包/限速（单发成功率仅 3~5 成），
    所以默认给了 attempts 参数做多轮重试——一次丢包不再等于「服务器不见了」。
    """
    err = {"err": "未查询"}
    for i in range(max(1, int(attempts))):
        info = _a2s_info_once(host, port, timeout)
        if "err" not in info:
            if i:
                info["retries"] = i
            return info
        err = info
        if i + 1 < attempts:
            time.sleep(gap)
    return err


def _a2s_info_once(host, port, timeout=1.5):
    """单次 A2S_INFO（含 challenge 应答）。失败返回 {'err': ...}。"""
    s = _sock(timeout)
    try:
        s.sendto(b"\xFF\xFF\xFF\xFFTSource Engine Query\x00", (host, port))
        d, _ = s.recvfrom(4096)
        if len(d) >= 5 and d[4:5] == b"A":          # 挑战
            s.sendto(b"\xFF\xFF\xFF\xFFTSource Engine Query\x00" + d[5:9], (host, port))
            d, _ = s.recvfrom(4096)
        if len(d) < 6 or d[:4] != b"\xFF\xFF\xFF\xFF" or d[4:5] != b"I":
            return {"err": "unexpected reply"}
        i = 6
        out = {}
        for k in ("name", "map", "folder", "game"):
            j = d.index(b"\x00", i)
            out[k] = d[i:j].decode("utf-8", "replace")
            i = j + 1
        out["appid"] = struct.unpack_from("<H", d, i)[0]
        i += 2
        out["players"], out["maxplayers"], out["bots"] = d[i], d[i + 1], d[i + 2]
        i += 3
        out["servertype"], out["env"] = chr(d[i]), chr(d[i + 1])
        i += 2
        out["visibility"], out["vac"] = d[i], d[i + 1]
        i += 2
        j = d.index(b"\x00", i)
        out["version"] = d[i:j].decode("utf-8", "replace")
        return out
    except socket.timeout:
        return {"err": "超时"}
    except Exception as e:                                    # noqa: BLE001
        return {"err": "%s: %s" % (type(e).__name__, e)}
    finally:
        s.close()


def a2s_players(host, port, timeout=1.5):
    """A2S_PLAYER：部分服务器会屏蔽，返回 None 表示拿不到。"""
    s = _sock(timeout)
    try:
        s.sendto(b"\xFF\xFF\xFF\xFF\x55\xFF\xFF\xFF\xFF", (host, port))
        d, _ = s.recvfrom(8192)
        if not (len(d) >= 5 and d[4:5] == b"A"):
            return None
        s.sendto(b"\xFF\xFF\xFF\xFF\x55" + d[5:9], (host, port))
        d, _ = s.recvfrom(16384)
        if len(d) < 6 or d[4:5] != b"D":
            return None
        n = d[5]
        i, out = 6, []
        for _ in range(min(n, 128)):
            if d[i] != 0:
                break
            i += 1
            j = d.index(b"\x00", i)
            nm = d[i:j].decode("utf-8", "replace")
            i = j + 1
            score = struct.unpack_from("<i", d, i)[0]
            dur = struct.unpack_from("<f", d, i + 4)[0]
            i += 8
            out.append({"name": nm, "score": score, "minutes": round(dur, 1)})
        return out
    except Exception:                                         # noqa: BLE001
        return None
    finally:
        s.close()


def local_persona(steam_dir):
    """本机 Steam 账号昵称，用于确认"我确实在这个服里"。"""
    if not steam_dir:
        return None
    p = os.path.join(steam_dir, "config", "loginusers.vdf")
    if not os.path.exists(p):
        return None
    try:
        s = open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    names = re.findall(r'"PersonaName"\s*"([^"]*)"', s)
    return names[0] if names else None


# ─────────── 三路「最近进过的服务器」证据（netstat 看不到连接时的救命稻草） ───────────
# 背景：新版 CS2 走 SteamNetworking/SDR 时本机 netstat 常常**看不到** cs2.exe 的真实
# UDP 对端，`_pick_address` 只能退回 Steam 日志里那条「最近一次 steam://connect」——
# 而玩家在游戏内换服（服务器浏览器 / 控制台 connect）时那条日志根本不更新，看板于是
# 永远停在上一台服。下面三路证据都带时间戳，取**最新**的那条即可跟上换服：
#   1) Steam 连接日志 console_log.txt   —— steam://connect 时才写（老通道）
#   2) Steam 服务器浏览器历史 VDF        —— CS2 游戏内服务器浏览器/历史就是它
#   3) CS2 引擎日志 game/csgo/console.log —— 引擎自己记的连接/断开（需 -condebug）
_ADDR_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})\b")
_CS2_SUBDIR = os.path.join("steamapps", "common", "Counter-Strike Global Offensive")


def steam_libraries(steam_dir):
    """Steam 库目录列表（含 Steam 根目录本身）。"""
    dirs = [steam_dir] if steam_dir else []
    p = os.path.join(steam_dir or "", "steamapps", "libraryfolders.vdf")
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            s = fh.read()
        for m in re.finditer(r'"path"\s*"([^"]+)"', s):
            d = m.group(1).replace("\\\\", "\\")
            if d and d not in dirs:
                dirs.append(d)
    except OSError:
        pass
    return dirs


_BH_CACHE = {"key": None, "val": []}


def browser_history(steam_dir):
    """Steam 服务器浏览器历史 → [(address, lastplayed_epoch)]，按时间倒序。

    文件：<Steam>/userdata/<账号>/7/remote/serverbrowser_hist.vdf
    （CS2 游戏内「服务器浏览器」的收藏与历史就是这两段）。读不到返回 []。
    """
    if not steam_dir:
        return []
    udir = os.path.join(steam_dir, "userdata")
    paths = []
    try:
        for uid in os.listdir(udir):
            p = os.path.join(udir, uid, "7", "remote", "serverbrowser_hist.vdf")
            if os.path.exists(p):
                paths.append(p)
    except OSError:
        return []
    key = tuple((p, os.path.getmtime(p)) for p in sorted(paths))
    if _BH_CACHE["key"] == key:
        return _BH_CACHE["val"]
    out = []
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                s = fh.read()
        except OSError:
            continue
        # 每个条目形如： "12" { "address" "ip:port" "LastPlayed" "1782507570" ... }
        # 块内没有嵌套花括号，所以非贪婪匹配到第一个 } 即可。
        for m in re.finditer(r'"\d+"\s*\{(.*?)\}', s, re.S):
            blk = m.group(1)
            am = re.search(r'"address"\s*"([^"]+)"', blk)
            if not am:
                continue
            lm = re.search(r'"LastPlayed"\s*"(\d+)"', blk)
            addr = am.group(1).strip()
            if not addr:
                continue
            out.append((addr, int(lm.group(1)) if lm else 0))
    out.sort(key=lambda r: -r[1])
    _BH_CACHE.update(key=key, val=out)
    return out


_CS2_CACHE = {"key": None, "val": None}


def cs2_console_last(steam_dir):
    """CS2 引擎日志（game/csgo/console.log）→ (address, epoch, still_connected) 或 None。

    引擎自己记的连接/断开，最准，但**需要启动参数 -condebug**；文件不存在就返回 None
    （不影响其它通道）。日志形如：
      [Client] Sending connect to 110.42.9.31:27111
      [NetSteamConn] Associating NetChan server @ 110.42.9.31:27111 (...) with ... #...
      [NetSteamConn] Removing Steam Net Connection for 110.42.9.31:27111, handle #...
    """
    if not steam_dir:
        return None
    p = None
    for lib in steam_libraries(steam_dir):
        cand = os.path.join(lib, _CS2_SUBDIR, "game", "csgo", "console.log")
        if os.path.exists(cand):
            p = cand
            break
    if not p:
        return None
    try:
        st = os.stat(p)
        key = (p, st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    if _CS2_CACHE["key"] == key:
        return _CS2_CACHE["val"]
    try:
        with open(p, "rb") as fh:
            if st.st_size > 500_000:
                fh.seek(st.st_size - 500_000)
                fh.readline()
            raw = fh.read()
    except OSError:
        return None
    txt = raw.decode("utf-8", "replace")
    now = time.time()
    cur = None            # (addr, epoch, connected)
    for line in txt.splitlines():
        if ("Sending connect to" in line) or ("Remote Connect (" in line):
            m = _ADDR_RE.search(line)
            if not m:
                continue
            addr = "%s:%d" % (m.group(1), int(m.group(2)))
            cur = [addr, _line_epoch(line, now), True]
        elif "Removing Steam Net Connection for" in line and cur:
            m = _ADDR_RE.search(line)
            if m and "%s:%d" % (m.group(1), int(m.group(2))) == cur[0]:
                cur[2] = False
    val = tuple(cur) if cur else None
    _CS2_CACHE.update(key=key, val=val)
    return val


def _line_epoch(line, now=None):
    """CS2 引擎日志行首的 MM/DD HH:MM:SS → epoch（按当前年份推）。"""
    m = re.match(r"^\s*(\d{2})/(\d{2})\s+(\d{2}):(\d{2}):(\d{2})", line)
    if not m:
        return 0
    now = now or time.time()
    try:
        t = time.mktime(time.struct_time(
            (time.localtime(now).tm_year, int(m.group(1)), int(m.group(2)),
             int(m.group(3)), int(m.group(4)), int(m.group(5)), 0, 0, -1)))
    except (ValueError, OverflowError):
        return 0
    if t > now + 86400:            # 跨年（日志是去年 12 月）：往前挪一年
        try:
            t = time.mktime(time.struct_time(
                (time.localtime(now).tm_year - 1, int(m.group(1)), int(m.group(2)),
                 int(m.group(3)), int(m.group(4)), int(m.group(5)), 0, 0, -1)))
        except (ValueError, OverflowError):
            return 0
    return int(t)


_RJ_CACHE = {"key": None, "at": 0.0, "val": []}


def recent_joins(steam_dir, ttl=5.0, ze_only=False):
    """汇总「最近进过的服务器」→ [{address, ts, source}]，按时间倒序。

    三路证据的发布时间戳都不可靠齐全，所以**全部收下按时间排序**，由调用方取最新。
    ze_only=True 时只保留風雲社 CS2 ZE 服清单里的地址（换服判据只关心这几台）。
    """
    now = time.time()
    if _RJ_CACHE["key"] == steam_dir and _RJ_CACHE["val"] and now - _RJ_CACHE["at"] < ttl:
        val = _RJ_CACHE["val"]
    else:
        rows = []
        last, _p = last_connect(steam_dir)
        if last and last.get("ts"):
            try:
                t = time.mktime(time.strptime(last["ts"], "%Y-%m-%d %H:%M:%S"))
                rows.append({"address": last["address"], "ts": int(t), "source": "steam-log"})
            except ValueError:
                pass
        for addr, ts in browser_history(steam_dir):
            if ts:
                rows.append({"address": addr, "ts": ts, "source": "browser-hist"})
        cc = cs2_console_last(steam_dir)
        if cc and cc[1]:
            rows.append({"address": cc[0], "ts": cc[1], "source": "cs2-log"})
        rows.sort(key=lambda r: -r["ts"])
        val = rows
        _RJ_CACHE.update(key=steam_dir, at=now, val=val)
    if not ze_only:
        return val
    zs = set("%s:%d" % (h, p) for h, p, _ in ze_servers())
    return [r for r in val if r["address"] in zs]


def _addr_pair(address):
    """'ip:port' → (host, port)；解析不了返回 (None, None)。"""
    m = _REMOTE.match(address or "")
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def best_join(steam_dir, last=None):
    """三路证据里**最新**的那条 → 与 last_connect() 同构的 dict（多带 ts_epoch/source）。

    优先序完全按时间戳：游戏内换服会更新服务器浏览器历史 / CS2 引擎日志，于是它们
    能盖过 Steam 日志里那条旧的 steam://connect；反过来用 steam://connect 进服时
    Steam 日志最新，就它说话。取不到任何证据返回 None。
    """
    if last is None:
        last, _p = last_connect(steam_dir)
    cands = []
    if last:
        ts = 0
        if last.get("ts"):
            try:
                ts = int(time.mktime(time.strptime(last["ts"], "%Y-%m-%d %H:%M:%S")))
            except ValueError:
                ts = 0
        cands.append((ts, last["host"], last["port"], last["address"], "steam-log"))
    for r in recent_joins(steam_dir):
        if r["source"] == "steam-log":
            continue                          # 上面已经收过，别重复
        h, p = _addr_pair(r["address"])
        if h:
            cands.append((r["ts"], h, p, r["address"], r["source"]))
    if not cands:
        return None
    cands.sort(key=lambda c: -c[0])
    ts, host, port, addr, src = cands[0]
    return {"host": host, "port": port, "address": addr, "ts": None,
            "ts_epoch": ts, "source": src, "line": None}


# ─────────────────── 对外：detect() ───────────────────
# 三级证据（越靠前越硬）：
#   1) netstat：cs2.exe 与某地址有已连接的 UDP 往来 → 这一刻确实连着它
#   2) Steam 连接日志：最近一次 steam://connect 的目标地址
#   3) A2S 实时查询：服务器还活着 + 当前地图（**只能证明服务器活着**）
GRACE_SEC = 45.0        # A2S 打不通时，沿用上次成功数据的最长时间
FAIL_TTL = 1.5          # 失败结果的缓存时长（比成功短，方便尽快重试）
A2S_TRIES = 3           # 当前服务器的 A2S 重试轮数（实测单发丢包率约 5 成）
PEER_TTL = 5.0          # netstat 对端的缓存时长（每轮都起子进程太浪费）
AWAY_SEC = 15.0         # netstat 连续这么久看不到到该服的连接 → 认定已离开。
                        # 必须大于 2~3 个 PEER_TTL（netstat 本身 5 秒才刷一次），
                        # 否则「正在加载地图 / 中途切场景」会被误判成退出。
_NEG = {"t0": 0.0, "addr": None}   # 连续「看不到连接」的起始时间与地址
# netstat 通道对本机 CS2「确实有效过」吗？只有先看到过 cs2.exe 的真实 UDP 对端，
# 「后来一个都看不到」才算「已离开」的证据。若从头到尾都看不到对端，说明这台机器的
# netstat 读不到 CS2 的连接（新版 CS2 走 SteamNetworking/SDR 时就是这样），
# 那就不能拿它判离开——否则进服满 AWAY_SEC 秒必被误判成「未在服务器内」。
_PEER_EVER = {"seen": False}

_CACHE = {"at": 0.0, "data": None, "addr": None, "a2s": None, "a2s_at": 0.0,
          "fail_at": 0.0, "good": None, "good_at": 0.0, "good_addr": None}
_LOCK = threading.Lock()


def _blank_out():
    return {
        "available": False,
        "game_running": False,
        "cs2_path": None,
        "steam_dir": None,
        "log_path": None,
        "address": None, "host": None, "port": None,
        "joined_at": None, "age_sec": None, "joined_text": None,
        "server_name": None, "map": None,
        "players": None, "maxplayers": None, "bots": None,
        "game": None, "version": None,
        "query_ok": False, "query_error": None,
        "my_name": None,
        "confirmed": False,
        "in_server": None,          # True/False/None：netstat 给出的「这一刻真连着」，None=无法判断
        "peer_seen": False,         # cs2.exe 是否有可见的游戏 UDP 对端
        "udp_peers": [],            # 供排查
        "stale": False,             # 数据来自宽限期内的上一次成功查询
        "stale_age": None,
        "addr_source": None,        # netstat-udp / steam-log / browser-hist / cs2-log
        "ev_ts": 0,                 # 选中地址那条证据的 epoch（用于「谁的证据更新」比较）
        "evidence": [],             # 三路「最近进过」证据（排查用，倒序）
        "ze_count": 0,              # 当前 CS2 ZE 服清单台数
        "ze_src": None,             # 清单来源：web / fallback
        "away_sec": 0.0,            # 已连续多久 netstat 看不到到该服的连接
        "source": None,
        "reason": "",
    }


_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_RESOLVE_CACHE = {}


def _is_ip(host):
    """是不是字面 IP（v4 / v6）。"""
    if not host:
        return False
    return bool(_IPV4_RE.match(host) or ":" in host)


def _resolve_ip(host, ttl=600.0):
    """域名 -> IPv4（带 10 分钟缓存）。解析不了返回 None。

    为什么需要：Steam 日志里的 connect 目标常写成域名
    （如 cs1.zombieden.cn:27018），而 netstat 的对端永远是数字 IP，
    拿字符串直接比对永远对不上 → 白白丢掉一条硬证据。
    """
    if not host or _is_ip(host):
        return host
    now = time.time()
    hit = _RESOLVE_CACHE.get(host)
    if hit and now - hit[1] < ttl:
        return hit[0]
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        ip = None
    _RESOLVE_CACHE[host] = (ip, now)
    return ip


def _pick_address(peers, last, map_hint=None, recent=None, hint_fresh=True):
    """
    决定「当前在哪台服务器」。

    证据链（越靠前越硬）：
      ① netstat 里真有到風雲社 ZE 服的 UDP 对端 —— 这一刻确实连着它；
      ② 三路「最近进过的服务器」证据里**最新**的那条（recent，按时间倒序）；
      ③ Steam 日志 / 浏览器历史里那条最近记录（last，可能是几天前的，容易过期）。

    map_hint：广播文件（官方客户端 fys.broadcast.assistant.txt）里的「当前地图」。
    换服瞬间 / UDP 表项残留时 netstat 可能**同时**看到新旧两台風雲社服，只按清单顺序
    取第一台就可能取到旧服；旧服一旦被选中，detect 会给出 in_server=True，上层就不走
    「反查」兜底，看板会一直停在上一台服（2026-09-29 玩家反馈）。

    ⚠ 仲裁顺序很关键：**先信「最新证据」再信 map_hint**。map_hint 来自官方广播文件，
      它换服后经常不刷新（还是上一张图）——拿陈旧图去仲裁，恰好会把**旧服**挑出来
      （旧服还在跑那张老图），等于把看板钉死在上一台服。所以只有当 hint 明确新鲜
      （hint_fresh）时才用它兜底。
    """
    if peers:
        cands = [(h, p, "%s:%d" % (h, p), lab) for h, p, lab in ze_servers()
                 if "%s:%d" % (h, p) in peers]         # ① 就是風雲社 CS2 ZE 那几台
        if len(cands) > 1:
            # ② 最新证据（服务内换服后浏览器历史 / CS2 引擎日志会刷新）指向哪台就哪台
            for _ts, addr in (recent or []):
                for h, p, a, _l in cands:
                    if a == addr or h == addr:
                        return h, p, a, "netstat-udp"
            # ③ hint 新鲜才拿它仲裁（陈旧 hint 会把旧服挑出来，见 docstring）
            if map_hint and hint_fresh:
                want = str(map_hint).lower()
                try:
                    rows = [{"address": a, "host": h, "port": p} for h, p, a, _l in cands]
                    for got in scan_addresses(rows, timeout=0.8, workers=len(rows)):
                        if (got.get("map") or "").lower() == want:
                            return got["host"], got["port"], got["address"], "netstat-udp"
                except Exception:                          # noqa: BLE001
                    pass
        if cands:
            h, p, a, _lab = cands[0]
            return h, p, a, "netstat-udp"
        if last:                                       # ② 与日志一致（域名先解析成 IP）
            lip = _resolve_ip(last["host"])
            a2 = "%s:%d" % (lip, last["port"]) if lip else last["address"]
            if a2 in peers:
                return lip, last["port"], a2, "netstat-udp"
        game = []
        for a in peers:                                # ③ 端口像游戏服（27015~27999）
            hm = _REMOTE.match(a)
            if hm and 27015 <= int(hm.group(2)) <= 27999 \
                    and not hm.group(1).startswith(("127.", "10.", "192.168.", "169.254.")):
                game.append(a)
        if len(game) == 1:
            hm = _REMOTE.match(game[0])
            return hm.group(1), int(hm.group(2)), game[0], "netstat-udp"
    if last:
        src = last.get("source") or "steam-log"
        return last["host"], last["port"], last["address"], src
    return None, None, None, None


# ─────────────────── 广播图反查当前服务器 ───────────────────
# 痛点：新版 CS2 走 SDR / SteamNetworking 时，本机 netstat 经常**看不到** cs2.exe
# 的真实 UDP 对端 → `_pick_address` 只能退回陈旧的 Steam 日志地址（那条只在
# steam://connect 时才更新）。玩家用游戏内控制台 / 服务器浏览器换服、或换到非
# 風雲社服后，detect() 会一直停在旧地址，A2S 照常回包 → 看板「切换当前服务器没更新」。
#
# 破局点：官方客户端写出的广播文件（fys.broadcast.assistant.txt）里带「地图名称」，
# 当它与陈旧地址的 A2S 图不一致时，说明大概率已换服，用这张图去反查当前服务器。
# ⚠ 不要改用同目录的 fys.broadcast.live.txt——那是第三方「风云社直播助手」输出的
#   直播文本，地图字段转抄自 assistant、与它同源，没有任何额外信息（2026-09-29 核实）。
# 这里并行 A2S 探九台風雲社服务器，找出正在跑这张图的那台，把「当前服务器」跟过去。
_RELOC_CACHE = {"map": None, "at": 0.0, "host": None, "port": None, "info": None}


def relocate_by_map(target_map, ttl=15.0, prefer=None):
    """用广播里的当前地图反查風雲社 CS2 ZE 服里正在跑它的那台（netstat 看不到连接时兜底）。

    返回 (host, port, info) 或 (None, None, None)。结果缓存 ttl 秒：
    只有「广播图 ≠ 旧地址图」的换服瞬间才会触发，稳态不会每秒打一轮服务器。

    ⚠ 「同一张图被好几台服同时跑」是常态（实测 01/06/07/08 四台同为
      ze_venice_escape_p）。老实现「取第一台命中就返回」→ 会把玩家判到**错误**的服，
      看板照样显示错内容。现在：命中唯一才直接采信；命中多台时只用 prefer
      （netstat 对端 / 最新进服证据里出现过的地址）那台；仍无法唯一定位就返回 None，
      宁可维持现状也不乱跳。
    """
    if not target_map:
        return None, None, None
    tm = target_map.lower()
    now = time.time()
    c = _RELOC_CACHE
    if c["map"] == target_map and now - c["at"] < ttl:
        return c["host"], c["port"], c["info"]      # 命中（含「这次没找到」的短缓存）
    rows = fixed_rows()
    alive = {r["address"]: r for r in scan_addresses(rows)}
    hits = [(r, alive[r["address"]]) for r in rows
            if alive.get(r["address"]) and (alive[r["address"]].get("map") or "").lower() == tm]
    pick = None
    if len(hits) == 1:
        pick = hits[0]
    elif len(hits) > 1:
        pref = set(prefer or ())
        for r, got in hits:
            if r["address"] in pref:                # 只采信有旁证（对端/最新证据）的那台
                pick = (r, got)
                break
    if pick is None:
        # 没跑这张图的 / 有好几台跑同一张图又无法唯一定位：缓存「未命中」避免每秒重试
        c.update(map=target_map, at=now, host=None, port=None, info=None)
        return None, None, None
    r, got = pick
    info = {"name": got.get("name"), "map": got.get("map"),
            "players": got.get("players"), "maxplayers": got.get("maxplayers"),
            "bots": got.get("bots")}
    c.update(map=target_map, at=now, host=r["host"], port=r["port"], info=info)
    return r["host"], r["port"], info


def detect(force=False, log_ttl=2.0, a2s_ttl=6.0, grace=GRACE_SEC, map_hint=None,
           hint_fresh=True):
    """
    返回当前服务器信息。带缓存，可被 1 秒一次的页面轮询安全调用。

    容错要点（之前覆盖窗老闪「未在服务器内」就是因为这三条都没做）：
      · A2S 单发丢包 ≠ 离开：多轮重试
      · 重试全挂也不立刻改判：沿用 grace 秒内最近一次成功的数据（stale）
      · netstat 看到真实 UDP 连接 → 直接认定「在服内」

    hint_fresh：map_hint 是否**新鲜**（广播文件刚更新过）。只有新鲜时才拿它做
    多台仲裁——陈旧 hint 恰好会把「还在跑老图」的那台旧服挑出来（详见 _pick_address）。
    """
    now = time.time()
    if not force and _CACHE["data"] and now - _CACHE["at"] < log_ttl:
        return _CACHE["data"]
    # 已经有线程在查（页面 1 秒一次轮询）：等最多 2 秒拿最新结果，
    # 等不到就退回上一次结果——**绝不**返回空对象，那会让上层误判「未在服务器内」。
    if not _LOCK.acquire(timeout=2.0):
        return _CACHE["data"] if _CACHE["data"] else _blank_out()
    try:
        return _detect_locked(max(force, False), time.time(), a2s_ttl, grace,
                              map_hint, hint_fresh)
    finally:
        _LOCK.release()



_PEERS_CACHE = {"at": 0.0, "pids": (), "peers": set()}


def _peers_cached(pids):
    """netstat 对端结果缓存 PEER_TTL 秒（稳态下不必每 2 秒起一个 netstat）。"""
    now = time.time()
    key = tuple(sorted(pids))
    if _PEERS_CACHE["pids"] == key and now - _PEERS_CACHE["at"] < PEER_TTL:
        return _PEERS_CACHE["peers"]
    peers = udp_peers(pids)
    _PEERS_CACHE.update(at=now, pids=key, peers=peers)
    return peers


def _detect_locked(force, now, a2s_ttl, grace, map_hint=None, hint_fresh=True):
    root = steam_root()
    last, log_path = last_connect(root)
    # 三路「最近进过的服务器」证据里**最新**的那条（Steam 日志 / 浏览器历史 / CS2 引擎日志）。
    # 关键：游戏内换服会刷新后两者，于是它能盖过 Steam 日志里那条旧的 steam://connect。
    best = best_join(root, last)
    ev = best or last
    rj = recent_joins(root)
    recent = [(r["ts"], r["address"]) for r in rj[:8]]
    # CS2 引擎日志（-condebug）里「最新事件就是断开这台服」= 引擎自己记的离开证据。
    # 仅在 netstat 什么都看不到（无法判断）时才采纳，见下方 in_server 判定。
    _cc = cs2_console_last(root)
    cs2_left = bool(_cc and _cc[2] is False and ev and ev.get("source") == "cs2-log"
                    and ev.get("address") == _cc[0])
    pids = cs2_pids()
    running = bool(pids)
    cs2_path = _proc_path(pids[0]) if pids else None
    peers = _peers_cached(pids) if running else set()

    out = _blank_out()
    out.update(game_running=running, cs2_path=cs2_path, steam_dir=root,
               log_path=log_path, my_name=local_persona(root),
               udp_peers=sorted(peers), evidence=rj[:6],
               ze_count=len(ze_servers()), ze_src=fys_lists().get("src"),
               source="steam-log:console_log.txt")

    host, port, addr, addr_src = _pick_address(peers, ev, map_hint,
                                               recent=recent, hint_fresh=hint_fresh)
    if not addr:
        out["available"] = False
        out["reason"] = "Steam 日志里还没有连接记录" if root else "没找到 Steam 目录"
        _CACHE.update(at=now, data=out, addr=None, a2s=None,
                      good=None, good_addr=None)
        return out

    out["available"] = True
    out["address"], out["host"], out["port"] = addr, host, port
    out["addr_source"] = addr_src
    out["source"] = {
        "netstat-udp": "netstat:udp",
        "steam-log": "steam-log:console_log.txt",
        "browser-hist": "browser-hist:serverbrowser_hist.vdf",
        "cs2-log": "cs2-log:console.log",
    }.get(addr_src, addr_src)
    jts = int((ev or {}).get("ts_epoch") or 0)
    out["ev_ts"] = jts
    if jts:
        out["joined_text"] = time.strftime("%m-%d %H:%M:%S", time.localtime(jts))
        out["age_sec"] = max(0, int(now - jts))
        out["joined_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(jts))
    else:
        ts = (last or {}).get("ts")
        if ts:
            out["joined_at"] = ts
            try:
                t = time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
                out["age_sec"] = max(0, int(now - t))
                out["joined_text"] = time.strftime("%m-%d %H:%M:%S", time.localtime(t))
            except ValueError:
                pass

    # ── netstat 硬信号：这一刻真的有到这台服的 UDP 连接？ ──
    # 能对上号 → True；对不上号（日志那条已过期 / 连的是别的服）→ False（由宽限兜抖）。
    if running:
        out["peer_seen"] = bool(peers)
        if peers:
            _PEER_EVER["seen"] = True
            key = addr
            if host and not _is_ip(host):
                rip = _resolve_ip(host)          # 日志里的域名先解析成 IP 再比
                if rip:
                    key = "%s:%d" % (rip, port)
            out["in_server"] = (key in peers)
    else:
        _PEER_EVER["seen"] = False

    # ── A2S 实时查询 ──
    same = (_CACHE["addr"] == addr)
    failed = False
    if same and _CACHE["a2s"] and not force:
        age = now - _CACHE["a2s_at"]
        if "err" not in _CACHE["a2s"]:
            info = _CACHE["a2s"] if age < a2s_ttl else None
        else:
            info = _CACHE["a2s"] if age < FAIL_TTL else None
        if info is not None:
            players = _CACHE.get("players")
        else:
            info = None
    else:
        info = None

    if info is None:
        # CS2 没在跑：重试也没意义（反正会判未在服务器内），单发省时间。
        # 在跑：超时给 0.9s 足够（实测正常回包只要 0.1s，超时全是丢包），多轮兜丢包。
        tries = A2S_TRIES if running else 1
        info = a2s_info(host, port, timeout=0.9, attempts=tries, gap=0.15)
        players = None
        if "err" not in info:
            players = a2s_players(host, port, timeout=1.0)
        _CACHE.update(addr=addr, a2s=info, a2s_at=now, players=players,
                      fail_at=(0.0 if "err" not in info else now))
        if "err" not in info:
            _CACHE.update(good=dict(info), good_at=now, good_addr=addr)

    if "err" in info:
        failed = True
        out["query_error"] = info["err"]
        out["reason"] = "服务器查询无响应（%s）" % info["err"]
        good, good_at, good_addr = _CACHE.get("good"), _CACHE.get("good_at") or 0.0, _CACHE.get("good_addr")
        if good and good_addr == addr and (now - good_at) <= grace:
            # 宽限：上次成功数据还很新，继续用，别闪「未在服务器内」
            info = dict(good)
            out["stale"] = True
            out["stale_age"] = int(now - good_at)
            players = _CACHE.get("players")
        else:
            info = None

    # ── 硬负信号：退出服务器后别再挂着上一台服 ──
    # netstat 是唯一能证明「这一刻还连着」的证据。它连续 AWAY_SEC 秒看不到到这台服
    # 的连接，就说明人已经离开（回主菜单 / 换服 / 掉线）——此时不能再用「上一次成功」
    # 的宽限数据撑着，否则会一直显示旧服的地图与奖励。
    if running:
        if out.get("in_server") is True:
            _NEG.update(t0=0.0, addr=None)
            out["away_sec"] = 0.0
        elif out.get("peer_seen") or _PEER_EVER["seen"]:
            # 这条通道在本机确实有效过（现在看得到对端，或曾经看得到）→ 空白才算「离开」
            if _NEG.get("addr") != addr:
                _NEG.update(t0=now, addr=addr)
            out["away_sec"] = round(now - _NEG["t0"], 1)
            if out["away_sec"] >= AWAY_SEC:
                out["in_server"] = False
                if info:
                    info = None
                    _CACHE.update(good=None, good_at=0.0, good_addr=None)
                out["reason"] = ("CS2 运行中，但已连续 %.0f 秒没有到 %s 的连接"
                                 "（很可能已离开）" % (out["away_sec"], addr))
        else:
            # 无法判断（netstat 看不到 cs2 的对端）→ 不据此判离开，交给 A2S / 广播
            _NEG.update(t0=0.0, addr=None)
            out["away_sec"] = 0.0
            if cs2_left:
                # 例外：CS2 引擎日志（-condebug）把「已断开这台服」记为**最新事件**，
                # 那就是引擎自证的「已离开」（回主菜单 / 退出服务器）——别继续挂着
                # 这台服的地图与奖励。玩家用游戏内换服时引擎日志同样会先记断开。
                out["in_server"] = False
                if info:
                    info = None
                    _CACHE.update(good=None, good_at=0.0, good_addr=None)
                out["reason"] = "CS2 引擎日志显示已断开 %s（很可能已离开）" % addr

    if info:
        out["query_ok"] = not failed
        out["server_name"] = clean_name(info.get("name"))
        out["map"] = info.get("map")
        out["players"] = info.get("players")
        out["maxplayers"] = info.get("maxplayers")
        out["bots"] = info.get("bots")
        out["game"] = info.get("game")
        out["version"] = info.get("version")
        if not failed:
            out["reason"] = ""
        if players and out["my_name"]:
            for row in players:
                if row["name"] == out["my_name"]:
                    out["confirmed"] = True
                    break
    if out.get("retries") is None and info and info.get("retries"):
        out["retries"] = info["retries"]

    _CACHE["at"] = now
    _CACHE["data"] = out
    return out


# ─────────────────── CLI ───────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    d = detect(force=True)
    print("=" * 56)
    print("  Steam 目录    %s" % d["steam_dir"])
    print("  连接日志      %s" % d["log_path"])
    print("  CS2 运行中    %s" % d["game_running"])
    print("  本机昵称      %s" % d["my_name"])
    if d.get("udp_peers"):
        print("  UDP 对端      %s" % ", ".join(d["udp_peers"][:6]))
    print("-" * 56)
    print("  当前服务器    %s（来源 %s）" % (d["address"], d.get("addr_source")))
    print("  发生于        %s（%s 秒前）" % (d["joined_text"], d["age_sec"]))
    if d.get("away_sec"):
        print("  未见连接      %.0f 秒（>%.0f 秒即判定已离开）" % (d["away_sec"], AWAY_SEC))
    if d.get("in_server") is not None:
        print("  真连着该服    %s" % ("是（netstat 看到 UDP 连接）" if d["in_server"]
                                      else "否（netstat 没看到）"))
    if d["query_ok"]:
        print("  服务器名      %s" % d["server_name"])
        print("  当前地图      %s" % d["map"])
        print("  在线          %s / %s（bot %s）" % (d["players"], d["maxplayers"], d["bots"]))
        print("  版本          %s" % d["version"])
        print("  已确认在服内  %s" % ("是" if d["confirmed"] else "未知（该服屏蔽玩家列表）"))
    else:
        print("  查询失败      %s" % d["query_error"])
        if d.get("stale"):
            print("  宽限沿用      %d 秒前的数据，地图 %s" % (d["stale_age"], d["map"]))
    if d.get("reason"):
        print("  说明          %s" % d["reason"])
    print("=" * 56)

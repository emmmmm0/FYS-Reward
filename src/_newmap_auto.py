# -*- coding: utf-8 -*-
"""新图自动补全 —— 地图库新上架的 ze 图 → 自动补「实体预览」+「地图封面」。

用户约定（2026-09-28）
----------------------
「以后如果上了新图就自己下载地图实体预览，记得补上地图封面。」
即：`data/maps.json` ∪ `data/rewards.json` 出现新的 ze 图名时，
自动走一遍补图管线，不再等人点名。本脚本就是那条链的**统一入口**。

缺口的两个口径
--------------
    预览缺口 miss_pv = 地图库 ze  −  预览壳 payload 的图（宽松匹配）
    封面缺口 miss_cv = 地图库 ze  −  cover/<名>.jpg

工坊 ID 从哪来（按优先级）
------------------------
    ① _newmap_src.json 缓存（本脚本刷新）
    ② EXG 公开表  https://list.darkrp.cn:9000/ServerList/CurrentCs2MapStatus
    ③ 社区 ZE 配置仓库（codeload 直连，解包后正则抽 图名→工坊ID）
       e54385991/UPKK_ZE_PUBLIC · Ozlin-Info/CS2-ZE-ZM-Public-Configs
       · gflze/CS2-ZE-Configs

用法
----
    python _newmap_auto.py --check              # 只侦察、出报告（默认）
    python _newmap_auto.py --refresh-src        # 只刷新工坊 ID 源表
    python _newmap_auto.py --apply              # 侦察 + 全链路补全
    python _newmap_auto.py --apply --covers-only  # 只补封面（最快）
    python _newmap_auto.py --apply --no-build   # 补数据但不重建预览壳

`--apply` 会依次跑：
    刷源表 → 写 _newmap_ws.json → _fetch_missing.py → _refetch_ents.py
    → _add_missing_maps.py --apply → _rebuild_preview.py → _build_covers.py
**不做打包、不发布**（打包/发布永远要人点头，见项目铁律）。

报告落在 `_newmap_report.json`，日志 `_newmap.log`。
"""
import base64
import gzip
import io
import json
import os
import re
import struct
import subprocess
import sys
import tarfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GH = os.path.join(HERE, "_ghcrawl")
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

B64 = os.path.join(GH, "preview_payload.b64")
DATA = os.path.join(HERE, "data")
COVER = os.path.join(HERE, "cover")
ZR = os.path.join(HERE, "_zerepos", "x")
SRC = os.path.join(HERE, "_newmap_src.json")
WS_NEW = os.path.join(HERE, "_newmap_ws.json")
UNRES = os.path.join(HERE, "_newmap_unresolvable.json")
LOG = os.path.join(HERE, "_newmap.log")
REPORT = os.path.join(HERE, "_newmap_report.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
EXG_URL = "https://list.darkrp.cn:9000/ServerList/CurrentCs2MapStatus"
# 服务器端哨兵（EXG 图池快照）。v2.14 起服务器停用 → 默认为空 = 跳过，
# 只用本机 find_gaps()；将来又有哨兵时设 FYS_NEWMAP_URL 恢复。
NEWMAP_URL = os.environ.get("FYS_NEWMAP_URL", "").strip()
REPOS = [
    ("upkk", "https://codeload.github.com/e54385991/UPKK_ZE_PUBLIC/tar.gz/refs/heads/master"),
    ("ozlin", "https://codeload.github.com/Ozlin-Info/CS2-ZE-ZM-Public-Configs/tar.gz/refs/heads/main"),
    ("gflze", "https://codeload.github.com/gflze/CS2-ZE-Configs/tar.gz/refs/heads/main"),
]
SRC_MAX_AGE = 7 * 86400          # 源表超过 7 天自动刷新

SUF = re.compile(r"(_p|_fix|_final|_remake|_rewind|_v\d+|_b\d+|_x)$")


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def opener():
    """本机 urllib 会读系统代理；这里显式直连（与其它抓取脚本一致）。"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener().open(req, timeout=timeout) as r:
        return r.read()


# ------------------------------------------------------------------ 集合
def map_library():
    """地图库全 ze 图名（maps.json ∪ rewards.json）。"""
    names = set()
    for fn in ("maps.json", "rewards.json"):
        p = os.path.join(DATA, fn)
        if not os.path.exists(p):
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        if isinstance(d, dict):
            names |= set(d.keys())
        elif isinstance(d, list):
            for it in d:
                if isinstance(it, str):
                    names.add(it)
                elif isinstance(it, dict) and it.get("Name"):
                    names.add(it["Name"])
    return {n for n in names if n.startswith("ze")}


def preview_index():
    """预览壳 payload 里已有：返回 (精确名集合, 归一集合, 中文名集合)。"""
    sys.path.insert(0, GH)
    import _add_missing_maps as A                       # noqa: E402
    d, _ = A.load_payload(B64)
    names, cns = set(), set()
    for v in d["maps"].values():
        if v.get("m"):
            names.add(v["m"])
        if v.get("cn"):
            cns.add(v["cn"])
    return names, cns


def cover_index():
    if not os.path.isdir(COVER):
        return set()
    return {f[:-4] for f in os.listdir(COVER) if f.endswith(".jpg")}


def norm(n):
    n = re.sub(r"[^a-z0-9_]+", "_", n.lower().strip())
    changed = True
    while changed:
        changed = False
        m = SUF.search(n)
        if m and len(n) - len(m.group(0)) >= 4:
            n = n[:m.start()]
            changed = True
    return n


# ------------------------------------------------------------------ 源表
def _exg_rows(arr, tag):
    out = {}
    for it in arr if isinstance(arr, list) else []:
        n, pid, cn = it.get("Name"), it.get("WorkshopId"), it.get("CnName")
        if not n or not pid or not str(n).startswith("ze"):
            continue
        out[str(n).lower()] = {"pid": str(pid), "cn": cn, "src": tag}
    return out


def parse_exg():
    try:
        raw = http(EXG_URL, timeout=25)
        arr = json.loads(raw.decode("utf-8", "replace"))
    except Exception as ex:                                     # noqa: BLE001
        log("EXG 表抓取失败：%r" % (ex,))
        return {}
    out = _exg_rows(arr, "exg")
    log("EXG 表：%d 条 ze" % len(out))
    return out


def parse_exg_local():
    """本地旧快照 _exg_maps.json —— 服务器下架的图在新表里会消失，但地图库里还留着，
    这里兜个底，至少让巡检把它们做一次（哪怕下载失败也能进失败档）。"""
    p = os.path.join(HERE, "_exg_maps.json")
    if not os.path.exists(p):
        return {}
    try:
        arr = json.load(io.open(p, encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return {}
    out = _exg_rows(arr, "exg-local")
    log("旧 EXG 快照：%d 条 ze" % len(out))
    return out


RE_PATTERNS = [
    re.compile(r'"MapName"\s*:\s*"([^"]+)"\s*,\s*"WorkshopId"\s*:\s*"?(\d+)'),
    re.compile(r'"([^"]+)"\s*\{\s*"workshop_id"\s*"(\d+)"'),
    re.compile(r'^//\s*([A-Za-z0-9_\-]+)\s*:\s*(\d+)'),
    re.compile(r'^([A-Za-z0-9_\-]+)\s*:\s*(\d+)'),
]


def parse_failed_src():
    """历次抓取失败清单里的 图名→工坊ID —— 至少让巡检分清
    「有 ID 但抓不到（工坊下架）」和「压根没 ID」，两者处置不同。"""
    p = os.path.join(HERE, "_fetch_failed.json")
    if not os.path.exists(p):
        return {}
    try:
        arr = json.load(io.open(p, encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return {}
    return {str(x["name"]).lower(): {"pid": str(x["pid"]), "cn": None, "src": "failed"}
            for x in arr
            if isinstance(x, dict) and x.get("name") and x.get("pid")}


def parse_repos():
    out = {}
    os.makedirs(ZR, exist_ok=True)
    for tag, url in REPOS:
        dst = os.path.join(ZR, tag)
        if not os.path.isdir(dst):
            try:
                blob = http(url, timeout=90)
                tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
                tf.extractall(dst)
                log("仓库 %s 解包完成" % tag)
            except Exception as ex:                             # noqa: BLE001
                log("仓库 %s 拉取失败：%r" % (tag, ex))
                continue
        hit = 0
        for dirpath, _dirs, files in os.walk(dst):
            for fn in files:
                if not fn.lower().endswith((".json", ".jsonc", ".txt", ".cfg")):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    txt = io.open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for rx in RE_PATTERNS:
                    for m in rx.finditer(txt):
                        n = m.group(1).strip().lower()
                        if not n.startswith("ze"):
                            continue
                        pid = m.group(2)
                        if not pid.isdigit():
                            continue
                        if n not in out:
                            out[n] = {"pid": pid, "cn": None, "src": "repo:%s" % tag}
                            hit += 1
        log("仓库 %s：新增 %d 条" % (tag, hit))
    return out


def load_src(force=False):
    if not force and os.path.exists(SRC):
        try:
            d = json.load(io.open(SRC, encoding="utf-8"))
            if time.time() - d.get("_ts", 0) < SRC_MAX_AGE:
                return d
        except Exception:                                       # noqa: BLE001
            pass
    return refresh_src()


def parse_curated():
    """已校订的 地图名→工坊ID 表（_missing_ws_all.json）。

    优先级最高：这是补图过程中人工/程序共同裁决过的映射，能识破
    「社区表把同图异名当独立工坊条目」的陷阱（如 ze_lotr_minas_tirith_p
    社区表给 3314560349，实为 ze_lotr_minas_tirith_cs2 = 3353505696）。
    """
    p = os.path.join(HERE, "_missing_ws_all.json")
    out = {}
    if not os.path.exists(p):
        return out
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return out
    for k, v in d.items():
        if k == "_ts" or v in (None, "", 0):
            continue
        out[str(k).lower()] = {"pid": str(v), "cn": None, "src": "curated"}
    log("已校订表：%d 条" % len(out))
    return out


def refresh_src():
    src = {}
    src.update(parse_curated())                                 # 已校订表（最高优先）
    for k, v in parse_exg().items():                            # 最新公开表
        src.setdefault(k, v)
    for k, v in parse_exg_local().items():                      # 本地旧快照兜底
        src.setdefault(k, v)
    for k, v in parse_repos().items():                          # 社区仓库兜底
        src.setdefault(k, v)
    for k, v in parse_failed_src().items():                     # 失败档兜底
        src.setdefault(k, v)
    src["_ts"] = time.time()
    io.open(SRC, "w", encoding="utf-8").write(
        json.dumps(src, ensure_ascii=False, indent=1))
    log("源表落盘 _newmap_src.json：%d 条" % (len(src) - 1))
    return src


# ------------------------------------------------------------------ 缺口
def preview_pids():
    """预览壳已有地图的工坊 ID 集合（payload key 尾段）。"""
    sys.path.insert(0, GH)
    import _add_missing_maps as A                       # noqa: E402
    d, _ = A.load_payload(B64)
    return {k.rsplit("/", 1)[-1] for k in d["maps"]}


def known_missing_covers():
    p = os.path.join(COVER, "_missing.json")
    if not os.path.exists(p):
        return set()
    try:
        return set(json.load(io.open(p, encoding="utf-8")))
    except Exception:                                           # noqa: BLE001
        return set()


def load_failed():
    """历史抓取失败清单 pid -> 原因（工坊下架/非公开，重跑也是白跑）。"""
    p = os.path.join(HERE, "_fetch_failed.json")
    if not os.path.exists(p):
        return {}
    try:
        arr = json.load(io.open(p, encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return {}
    return {str(x.get("pid")): x.get("why")
            for x in arr if isinstance(x, dict) and x.get("pid")}


def lookup(name, src):
    """在源表里找 工坊ID（精确 → 归一化 → 唯一前缀）。"""
    hit = src.get(name.lower())
    if hit:
        return hit
    nn = norm(name)
    near = [(k, v) for k, v in src.items()
            if k != "_ts" and abs(len(k) - len(nn)) <= 2
            and (k.startswith(nn) or nn.startswith(k))]
    return near[0][1] if len(near) == 1 else None


def find_gaps(src=None):
    """返回 (地图库, 预览缺口, 封面缺口, 同图异名, 封面新增缺口)。

    判定预览是否已有，逐层收紧：
      ① 地图库名的工坊 ID 已在 payload 的 key 里（最准，能识破同图异名）
      ② 图名精确 / 去后缀归一 命中
      ③ 编号相同的两条（如 ze_a_p 与 ze_a）
    """
    lib = map_library()
    pv_names, pv_cns = preview_index()
    pv_norm = {norm(n) for n in pv_names}
    pids = preview_pids()
    src = src or {}
    cv, known_miss = cover_index(), known_missing_covers()

    miss_pv, alias, miss_cv, new_cv = [], [], [], []
    for n in sorted(lib):
        if n not in cv:                                        # 封面缺口独立算
            miss_cv.append(n)
            if n not in known_miss:
                new_cv.append(n)

        nn = norm(n)
        if n in pv_names or nn in pv_norm:                     # 名字精确/归一命中
            continue
        cand = [p for p in pv_norm if abs(len(p) - len(nn)) <= 2
                and (p.startswith(nn) or nn.startswith(p))]
        if len(cand) == 1:
            continue
        hit = lookup(n, src) if src else None
        if hit and str(hit["pid"]) in pids:                    # 工坊 ID 已在壳里
            alias.append((n, str(hit["pid"])))                 # 真·同图异名
            continue
        miss_pv.append(n)
    return lib, miss_pv, alias, miss_cv, new_cv


def resolve(miss_pv, src, retry_failed=False):
    """缺口 → (可自动补, 无工坊ID, 已知抓不到而跳过)。"""
    failed = load_failed()
    todo, unknown, skipped = {}, [], []
    for n in miss_pv:
        hit = lookup(n, src)
        if not hit or not str(hit["pid"]).isdigit():
            unknown.append(n)
            continue
        pid = str(hit["pid"])
        if pid in failed and not retry_failed:
            skipped.append((n, pid, failed[pid]))
            continue
        todo[n] = int(pid)
    return todo, unknown, skipped


# --------------------------------------------------- 服务器哨兵
def fetch_server_newmap(timeout=12.0):
    """读服务器端每日哨兵的产出（/root/fys_newmap.py → /usr/share/caddy/newmap.json）。

    两边视角互补，合并才不漏：
      本机 find_gaps() 看「地图库 maps/rewards.json」—— 地图库更新了才发现；
      服务器看「EXG 公开图池的两次快照」—— 服务器那边一上架就能发现，
      不必等地主把 maps.json 也更新过来。取不到就返回 None（不影响本机流程）。
    """
    try:
        if not NEWMAP_URL:          # 服务器停用：跳过哨兵，只用本机巡检
            return None
        with opener().open(NEWMAP_URL, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as ex:                                     # noqa: BLE001
        log("服务器哨兵不可用（不影响本机巡检）：%r" % (ex,))
        return None


# --------------------------------------------------- 无工坊ID的持久记忆
def load_unres():
    if not os.path.exists(UNRES):
        return {}
    try:
        d = json.load(io.open(UNRES, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:                                           # noqa: BLE001
        return {}


def track_unres(unknown):
    """更新「查不到工坊ID」的清单，返回本次**新增**的那些（值得提示的）。"""
    old = load_unres()
    now = {n: old.get(n) or time.strftime("%F") for n in unknown}
    fresh = [n for n in unknown if n not in old]
    io.open(UNRES, "w", encoding="utf-8").write(
        json.dumps(now, ensure_ascii=False, indent=1))
    return fresh, sorted(set(old) - set(now))                   # 新增 / 已解决


# ------------------------------------------------------------------ 执行
def run(cmd, env=None):
    log("RUN  %s" % " ".join(cmd))
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.Popen(cmd, cwd=HERE, env=e,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    tail = []
    for line in io.TextIOWrapper(p.stdout, encoding="utf-8", errors="replace"):
        line = line.rstrip()
        tail.append(line)
        if len(tail) > 6:
            tail.pop(0)
        print("    " + line, flush=True)
    p.wait()
    return p.returncode, tail


def main():
    args = sys.argv[1:]
    check_only = "--check" in args or not ("--apply" in args or "--refresh-src" in args)
    covers_only = "--covers-only" in args
    no_build = "--no-build" in args
    retry_failed = "--retry-failed" in args

    if "--refresh-src" in args and "--apply" not in args:
        refresh_src()
        return 0

    log("=" * 62)
    log("新图巡检开始")
    src = {} if covers_only else load_src()

    lib, miss_pv, alias, miss_cv, new_cv = find_gaps(src)
    log("地图库 %d 张 ze ｜ 预览缺口 %d ｜ 同图异名(已有) %d ｜ 封面缺口 %d（新增 %d）"
        % (len(lib), len(miss_pv), len(alias), len(miss_cv), len(new_cv)))

    todo, unknown, skipped = ({}, miss_pv, []) if covers_only else \
        resolve(miss_pv, src, retry_failed)

    # 服务器哨兵看到的新图（EXG 池新增）也并进来 —— 见 fetch_server_newmap 注释
    srv = None if covers_only else fetch_server_newmap()
    srv_new = [x for x in ((srv or {}).get("new") or []) if isinstance(x, dict)]
    added = 0
    for x in srv_new:
        n, pid = x.get("name"), str(x.get("pid") or "")
        if x.get("preview") or not n or not pid.isdigit() or n in todo:
            continue
        todo[n] = int(pid)
        added += 1
    if srv:
        log("服务器哨兵：图池 %d 张，服务器侧新图 %d 张（并入本机待办 %d 张）"
            % (srv.get("pool", 0), len(srv_new), added))
        for x in srv_new[:8]:
            log("    · %-40s %-12s %s"
                % (x.get("name"), x.get("cn") or "", x.get("pid") or ""))

    if todo:
        log("可自动补预览 %d 张，其中：%s"
            % (len(todo), ", ".join("%s=%s" % kv for kv in list(todo.items())[:6])))
    if skipped:
        log("已知抓不到（工坊下架/非公开，跳过）%d 张：%s"
            % (len(skipped), ", ".join(s[0] for s in skipped)))
    fresh_unres, solved = track_unres(unknown)
    if solved:
        log("已解决（拿到工坊ID）%d 张：%s" % (len(solved), ", ".join(solved)))
    if unknown:
        if fresh_unres:
            log("⚠ 新出现、查不到工坊 ID 的图 %d 张：%s"
                % (len(fresh_unres), ", ".join(fresh_unres)))
        else:
            log("查不到工坊 ID 的图 %d 张（都是老面孔，已记入 _newmap_unresolvable.json）"
                % len(unknown))
    if miss_cv:
        log("封面缺 %d 张（本次新增 %d）：%s"
            % (len(miss_cv), len(new_cv), ", ".join(miss_cv[:12])))

    report = {"地图库": len(lib), "预览缺口": miss_pv, "可自动": todo,
              "同图异名": [list(a) for a in alias],
              "已知抓不到": [{"名": s[0], "pid": s[1], "why": s[2]} for s in skipped],
              "服务器哨兵": {"时间": (srv or {}).get("ts_str"),
                             "图池": (srv or {}).get("pool"),
                             "新图": srv_new,
                             "云端封面数": (srv or {}).get("cover_total")},
              "无工坊ID": unknown, "无工坊ID_新增": fresh_unres,
              "封面缺口": miss_cv, "封面新增缺口": new_cv,
              "封面仍缺": [], "时间": time.strftime("%F %T"), "动作": []}
    io.open(REPORT, "w", encoding="utf-8").write(
        json.dumps(report, ensure_ascii=False, indent=1))

    if check_only:
        log("仅侦察（要真正补全请加 --apply）")
        return 0

    # ---- 1. 预览：抓取 → 完整实体 → 追加 payload → 重建壳
    if todo and not covers_only:
        io.open(WS_NEW, "w", encoding="utf-8").write(
            json.dumps(todo, ensure_ascii=False, indent=1))
        rc, _ = run([PY, "_fetch_missing.py"], {"FYS_WS_JSON": WS_NEW})
        report["动作"].append({"下载提取": rc})
        if rc == 0:
            rc, _ = run([PY, "_refetch_ents.py"], {"FYS_WS_JSON": WS_NEW})
            report["动作"].append({"完整实体重取": rc})
            # 必须带 FYS_WS_JSON：否则 _add_missing_maps 会去读 _missing_ws_all.json
            # （历史清单），本次新图反而不在里面，表现为「提取成功但没进 payload」。
            rc, _ = run([PY, "_add_missing_maps.py", "--apply"],
                        {"FYS_WS_JSON": WS_NEW})
            report["动作"].append({"追加payload": rc})
            if rc == 0 and not no_build:
                rc, _ = run([PY, "_rebuild_preview.py"])
                report["动作"].append({"重建预览壳": rc})

    # ---- 2. 封面（增量：已存在且非空跳过）
    rc, tail = run([PY, "_build_covers.py"])
    report["动作"].append({"封面抓取": rc})
    for ln in tail:
        if ln.startswith("完成：") or "缺失清单" in ln:
            log("封面：" + ln)
    report["封面仍缺"] = _recheck_cover_gap()

    io.open(REPORT, "w", encoding="utf-8").write(
        json.dumps(report, ensure_ascii=False, indent=1))
    log("巡检结束；报告 _newmap_report.json")
    return 0


def _recheck_cover_gap():
    """封面抓完后重新统计缺口（去掉刚补上的）。"""
    return sorted(map_library() - cover_index())


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
風雲社 通关云点 · 实时查询台
==================================================
读你本机的广播文件 fys.broadcast.assistant.txt，认出当前所在服务器与地图，
实时给出这张图【当前关卡】的通关云点（rankPasses）。

用法：
    python reward_server.py             # 启动服务并自动打开页面（推荐）
    python reward_server.py --once      # 只在终端打印一次，不开页面
    python reward_server.py --watch     # 终端常驻监听，变化时打印
    python reward_server.py --port 8888 # 换端口

数据来源：GitHub fyscs/cs2 的 2001/sharp/configs/rewards/<地图>.jsonc（Reward v22）
"""
import json
import os
import re
import sys
import time
import webbrowser
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
sys.path.insert(0, BASE_DIR)
import gsi                      # noqa: E402  CS2 GSI（游戏状态集成）状态
import build_index      # noqa: E402
import current_server   # noqa: E402
import fys_web          # noqa: E402  风雲社官网免登录接口（服务器实时人数交叉校验）
import mapnames         # noqa: E402

# ─────────────────────────── 配置 ───────────────────────────
def _localappdata():
    """%LOCALAPPDATA%（拿不到就退回当前用户目录）——不要写死 C:\\Users\\1\\…，
    换台机器 / 换个 Windows 账号就会静默读不到广播文件。"""
    return os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")


BROADCAST_FILE = os.environ.get(
    "FYS_BROADCAST_FILE",
    os.path.join(_localappdata(), "fys", "fys.broadcast.assistant.txt"),
)
# 只读官方客户端写出的这份广播（fys.broadcast.assistant.txt）。
# ⚠ 另有一个 fys.broadcast.live.txt 出现在同一目录，**它不是官方数据源**，而是第三方
#   「风云社直播助手」渲染输出的直播文本（其「地图名称」本身转抄自 assistant）。
#   曾经误把它当「官方实时广播」并作为换服真值，2026-09-29 已移除，详见 resolve()。
DEFAULT_PORT = 8777
POLL_MS = 1000          # 页面轮询间隔

# 地图名前缀白名单（按仓库实际目录统计得出）
MAP_PREFIX = r"(?:ze|zm|mg|ttt|de|cs|bhop|surf|kz|awp|aim|jail|fun|dr|trade)"
MAP_RE = re.compile(r"\b(%s_[A-Za-z0-9_]{2,})\b" % MAP_PREFIX, re.IGNORECASE)

REWARD_LABELS = [
    ("rankPasses", "通关云点", "int"),
    ("rankDamage", "伤害结算云点比例", "int"),
    ("rankIntern", "低保云点比例 /分钟", "float"),
    ("econPasses", "通关龙晶", "int"),
    ("econDamage", "伤害结算龙晶比例", "int"),
    ("econIntern", "低保龙晶比例 /分钟", "float"),
]

NOT_IN_SERVER_HINTS = ("还没有在", "未在", "不在服务器", "offline")

# 广播文件「新鲜」窗口：只有这么久内更新过，它的地图才敢拿去给多台服务器做仲裁。
# 陈旧的广播图会把「还在跑老图」的旧服挑出来（换服后看板钉死在上一台服的元凶）。
HINT_MAX_AGE = 180.0
# 最新进服证据指向 CS:GO（旧版）風雲社 ZE 服的判定窗口：只有「刚去过」才算数，
# 免得几天前玩过 CS:GO 就一直压着 CS2 判定不放。
CSGO_FRESH_SEC = 3 * 3600.0


def _csgo_recent(srv):
    """最新进服证据是否指向风雲社 CS:GO（旧版）ZE 服；是则返回该地址，否则 None。

    风雲社同时运营 CS:GO 服（19.csgoze.com 等，官网 modeId 1xxx），本看板只跟 CS2。
    玩家在 CS:GO 服时 netstat 对端在 CS2 清单里一个都匹配不上，是最容易「停在上一台
    CS2 服、继续显示别人地图的奖励」的场景 —— 这里给出准确说明，而不是硬凑一台 CS2 服。
    调用方保证：只在 in_server is not True（netstat 说不清）时才用。
    """
    try:
        cg = set("%s:%d" % (h, p) for h, p, _ in current_server.csgo_ze_servers())
        if not cg:
            return None
        rows = current_server.recent_joins((srv or {}).get("steam_dir") or "")
        if not rows:
            return None
        top = rows[0]
        if top.get("address") not in cg:
            return None
        if (time.time() - (top.get("ts") or 0)) > CSGO_FRESH_SEC:
            return None
        cur = int((srv or {}).get("ev_ts") or 0)
        if cur and (top.get("ts") or 0) <= cur:
            return None               # 当前地址那条证据更新 → 以当前为准
        return top["address"]
    except Exception:                                          # noqa: BLE001
        return None


# ─────────────────────────── 广播文件解析 ───────────────────────────
def read_broadcast():
    """返回 (文本, 文件mtime, 错误)。文件不存在或读不到时文本为空。"""
    try:
        with open(BROADCAST_FILE, "rb") as fh:
            raw = fh.read()
        for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
            try:
                return raw.decode(enc), os.path.getmtime(BROADCAST_FILE), None
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", "replace"), os.path.getmtime(BROADCAST_FILE), None
    except FileNotFoundError:
        return "", 0.0, "广播文件不存在：%s" % BROADCAST_FILE
    except OSError as e:
        return "", 0.0, "读取失败：%s" % e


# （原 _live_path / read_live / _read_text 已移除，2026-09-29。
#   它们读的 fys.broadcast.live.txt 不是官方数据源，而是第三方「风云社直播助手」
#   渲染输出的直播文本；其「地图名称 / 译名 / 当前关卡」转抄自官方客户端写出的
#   fys.broadcast.assistant.txt，与换服判据同源、没有任何独立性。详见 resolve()。）
def pick_map(text, known_maps):
    """从广播文本里认出地图名。优先选择索引里真实存在的地图。"""
    cands = []
    seen = set()
    for m in MAP_RE.finditer(text):
        name = m.group(1).lower()
        if name not in seen:
            seen.add(name)
            cands.append(name)
    if not cands:
        return None, []
    for c in sorted(cands, key=len, reverse=True):
        if c in known_maps:
            return c, cands
    return sorted(cands, key=len, reverse=True)[0], cands


STAGE_PATTERNS = [
    r"关卡\s*[:：=]?\s*(\d+)",
    r"第\s*(\d+)\s*关",
    r"[Ss]tage\s*[:：=]?\s*(\d+)",
    r"阶段\s*[:：=]?\s*(\d+)",
    r"(\d+)\s*/\s*\d+\s*(?:关|stage)",
    r"\[\s*(\d+)\s*\]",
    r"L\s*(\d+)\b",
]


def pick_stage(text, valid_stages):
    """从广播文本里认当前关卡号。识别不到返回 None。"""
    for pat in STAGE_PATTERNS:
        m = re.search(pat, text)
        if m:
            try:
                v = int(m.group(1))
            except (TypeError, ValueError):
                continue
            if not valid_stages or str(v) in valid_stages:
                return v
    return None


# ─────────────────── 地图名容错匹配 ───────────────────
# 官方仓库的配置名与服务器实际跑的地图名偶有 1~2 个字符的出入，实测例子：
#   官方 rewards 键 : ze_minecraft_hortus_de_escapismo
#   服务器 A2S 实名 : ze_minecraft_hortus_de_escapism      ← 少一个 o
# 精确查不到时不兜底的话，玩家正在玩的那张图会整块显示成「未收录」。
# 规则故意做得很保守：只在「两名字互为前缀 + 长度差 ≤2 + 全表唯一候选」时命中，
# 一旦出现第二个候选就放弃，避免把 ze_xxx_v5 这类版本图错配到 ze_xxx_v6 上。
LENIENT_MAX_DELTA = 2


def _lenient_key(name, table):
    """保守近似查键：命中返回表里的键，否则 None。"""
    if not name or not table:
        return None
    n = str(name).strip().lower()
    if n in table:
        return n
    cands = []
    for k in table:
        if k == n or abs(len(k) - len(n)) > LENIENT_MAX_DELTA:
            continue
        if k.startswith(n) or n.startswith(k):
            cands.append(k)
            if len(cands) > 1:
                return None            # 有歧义就绝不猜
    return cands[0] if cands else None


def reward_of(map_name):
    """按地图名取奖励配置。返回 (cfg, 命中的键, 是否近似命中)。"""
    m = str(map_name or "").strip().lower()
    if not m:
        return None, m, False
    cfg = (STATE.get("rewards") or {}).get(m)
    if isinstance(cfg, dict) and cfg:
        return cfg, m, False
    k = _lenient_key(m, STATE.get("rewards") or {})
    if k:
        cfg = STATE["rewards"].get(k)
        if isinstance(cfg, dict) and cfg:
            return cfg, k, True
    return None, m, False


def mapcn_of(map_name, hit_key=None):
    """地图中文名。精确翻不出、奖励又是按近似名命中的，就借近似名的中文名。"""
    cn = mapnames.cn(map_name)
    if cn is None and hit_key and hit_key != str(map_name or "").strip().lower():
        cn = mapnames.cn(hit_key)
    return cn


def _bgen():
    """数据代数：load_state 换掉 rewards/maps 时 +1，让按 mtime 的缓存整体失效。"""
    return STATE.get("_gen", 0)


def data_gen():
    """数据代际：**只在索引真被整片换掉时**（load_state）才 +1，随 /api/status 下发。

    前端拿它作废自己的地图库缓存（LIB.all / LIB.cfg）。⚠ 不能用 _gen：
    后台每 30 分钟的静默上游比对也会 _gen+1，但那不改本地缓存，
    用它会让用户正在看的地图库每半小时被刷一次。
    """
    return STATE.get("_dgen", 0)


def bump_data_gen():
    """代际 +1（回归专用：模拟「同步完成后索引换代」）。"""
    STATE["_dgen"] = (STATE.get("_dgen") or 0) + 1
    return STATE["_dgen"]


_BCAST_CACHE = {"key": None, "val": (None, [], None)}


def parse_broadcast_cached(text, mtime):
    """广播全文解析缓存：pick_map 要对全部已知地图（约 700 个）做前缀模糊匹配，
    是 /api/status 每秒一轮里最贵的一步。文件没变（mtime+长度不变）就复用上次结果。"""
    key = (mtime, len(text), _bgen()) if text else None
    if key is not None and _BCAST_CACHE["key"] == key:
        return _BCAST_CACHE["val"]
    cands = []
    bmap = None
    sline = None
    rewards = STATE["rewards"]
    bmap, cands = pick_map(text, set(rewards.keys()))
    if bmap:
        for line in text.splitlines():
            s = line.strip()
            if s and not MAP_RE.search(s) and len(s) < 40:
                sline = s
                break
    _BCAST_CACHE["key"] = key
    _BCAST_CACHE["val"] = (bmap, cands, sline)
    return _BCAST_CACHE["val"]


_STAGE_CACHE = {"key": None, "val": None}


def pick_stage_cached(stage_text, mtime, valid_stages, map_name):
    """关卡识别同样吃广播全文，按（mtime+地图+关卡集）缓存。"""
    key = (mtime, len(stage_text or ""), map_name, tuple(sorted(valid_stages)))
    if _STAGE_CACHE["key"] == key:
        return _STAGE_CACHE["val"]
    st = pick_stage(stage_text, valid_stages)
    _STAGE_CACHE["key"] = key
    _STAGE_CACHE["val"] = st
    return st


def resolve():
    """
    核心：定位当前服务器 -> 出当前地图/关卡/通关云点。

    取数优先级：
      1) fys 广播文件（能给出「当前关卡」，但实测进服后不一定刷新）
      2) Steam 连接日志 + A2S 实时查询（稳定，能给出地图与在线人数，但没有关卡号）
    """
    text, mtime, err = read_broadcast()
    rewards, maps, meta = STATE["rewards"], STATE["maps"], STATE["meta"]

    result = {
        "ok": False,
        "state": "unknown",
        "state_text": "未知",
        "server_line": None,
        "map": None,
        "mapcn": None,
        "map_candidates": [],
        "stage": None,
        "current": None,
        "stages": [],
        "total_stages": 0,
        "knockback": None,
        "infect": None,
        "map_data": None,
        "raw": text,
        "raw_mtime": mtime,
        "raw_mtime_str": time.strftime("%H:%M:%S", time.localtime(mtime)) if mtime else None,
        "broadcast_file": BROADCAST_FILE,
        "error": err,
        "source": None,
        "source_text": None,
        "server": None,
        "detail": None,
        "stage_hint": None,
        "shown_stage": None,
        "stage_src": None,          # broadcast=官方客户端上报 / gsi=按CT比分推断
        "gsi": None,
        "live": None,           # 本局战绩（伤害/K-D-A + 按比例算的兑换额）
        "built_at": meta.get("built_at_str"),
        "checked_at": time.strftime("%H:%M:%S"),
    }

    # ───── 1) 广播文件（官方客户端 fys.broadcast.assistant.txt）：能拿到「关卡」 ─────
    broadcast_map, broadcast_stage = None, None
    if not err and text.strip() and not any(h in text for h in NOT_IN_SERVER_HINTS):
        broadcast_map, result["map_candidates"], sline = parse_broadcast_cached(text, mtime)
        if sline:
            result["server_line"] = sline

    # ── 广播侧给出的「当前地图 / 对应文本」 ──
    # 只取官方客户端写出的 assistant 广播；它进服后才写、换服时不一定刷新，所以
    # **仅作参考**，真正的换服判据走下面的自证信号（netstat 连接表 / Steam 日志 + A2S）。
    #
    # ⚠ 为什么不再读 fys.broadcast.live.txt（2026-09-29 核实后移除）：
    #   那个文件不是官方数据源，而是第三方「风云社直播助手」渲染输出的直播文本
    #   （默认路径就贴在官方目录旁边）。它自己的字符串表写明「进服后自动读取
    #   fys.broadcast.assistant.txt，秒级显示 地图名称 / 译名 / 当前关卡」——即它的
    #   地图字段是**转抄 assistant** 来的，两者同源、毫无独立性；它只是多带了
    #   「当前分数 / 预计云点 / 预计龙晶」这类每秒变的数字，mtime 看着新鲜，但地图
    #   字段并不会比 assistant 更早更新。把它当「官方实时广播」并优先于 assistant，
    #   既修不了换服（assistant 不刷新时它也不刷新），又凭空多绑一个第三方软件。
    truth_map, truth_text, truth_mtime = broadcast_map, text, mtime

    # ───── 1.5) CS2 GSI（游戏状态集成）：比广播/A2S 更直接的「当前对局」证据 ─────
    # 游戏自己推来的 map.name 是权威的（连 workshop/123/ze_xxx 这种都规范化好了），
    # 而且它只在「真的在服务器里」时才有值 —— 可以替代 netstat 判断「是否在服内」
    # （新版 CS2 走 SDR，netstat 经常看不到 UDP 对端）。
    # 关卡：广播文件有明确关卡号且地图对得上时仍以广播为准；否则按 CT 比分推断。
    g = gsi.fresh()
    gsi_map = (g or {}).get("map") or ""
    gsi_in = bool(gsi_map)
    if gsi_in:
        result["gsi"] = {
            "map": gsi_map, "phase": g.get("phase"), "round": g.get("round"),
            "ct": g.get("ct"), "t": g.get("t"),
            "kills": g.get("kills"), "deaths": g.get("deaths"),
            "dmg_round": g.get("dmg_round"),
            "age": round((g.get("at") or 0) and (time.time() - g["at"]) or 0, 1),
        }
        # 广播图与 GSI 图不一致时，广播的内容（含关卡）视为上一张图的残留
        if gsi_map and (not truth_map or truth_map.lower() != gsi_map):
            truth_map, truth_text = gsi_map, ""
            truth_mtime = 0
    else:
        result["gsi"] = None

    # ───── 2) 服务器实时定位 ─────
    # 把「官方上报的当前图」当 hint 传进去，但它**只在新鲜时**才被用于多台仲裁：
    # 广播文件换服后经常不刷新（还是上一张图），拿陈旧图去仲裁恰好会把「还在跑老图」
    # 的那台**旧服**挑出来，看板于是被钉死在上一台服（见 current_server._pick_address）。
    # GSI 的地图是实时真值，直接按「新鲜」参与仲裁。
    _hint_fresh = bool(gsi_in or (mtime and (time.time() - mtime) <= HINT_MAX_AGE))
    try:
        srv = current_server.detect(map_hint=truth_map, hint_fresh=_hint_fresh)
    except Exception as e:                                     # noqa: BLE001
        srv = {"available": False, "query_ok": False, "game_running": False,
               "reason": "定位异常：%r" % e}
    result["server"] = srv
    in_server = (srv or {}).get("in_server")     # netstat 看到真实 UDP 连接 = True

    # ───── 3) 硬负信号：CS2 没在跑 → 必然不在服务器里 ─────
    # 必须放在「决定地图」之前：A2S 只能证明「那台服还活着」，它活着不代表你在里面。
    # （漏了这一步就会出现「CS2 已退出，看板仍挂着几天前那台服当前地图的奖励」）
    if not gsi_in and not in_server and srv and srv.get("available") \
            and not srv.get("game_running"):
        result["state"] = "offline"
        result["state_text"] = "未在服务器内"
        result["detail"] = "CS2 已退出，最后加入 %s（%s）" % (
            srv.get("address"), srv.get("joined_text"))
        return result

    # ───── 3.4) 玩家其实在风雲社的 CS:GO（旧版）服 ─────
    # 风雲社同时开着 CS:GO 服（19.csgoze.com 等，官网 modeId 1xxx），本看板只跟踪 CS2。
    # 玩家跑 CS:GO 时 netstat 对端在 CS2 清单里一个都匹配不上，是最容易「停在上一台
    # CS2 服、继续显示那张图的奖励」的场景。这里给出准确说明，而不是硬凑一台 CS2 服。
    _cg = _csgo_recent(srv)
    if _cg and (in_server is not True or (srv or {}).get("address") == _cg):
        result["state"] = "offline"
        result["state_text"] = "未在 CS2 服务器内"
        result["detail"] = ("最新记录显示你在风雲社的 CS:GO（旧版）服 %s —— "
                            "本看板只跟踪 CS2 僵尸逃跑服的奖励。" % _cg)
        return result

    # ───── 3.5) 硬负信号②：netstat 明确说「没连着」 ─────
    # 退出服务器但 CS2 还开着时，A2S 照样能查到「那台服活着 + 它当前地图」，
    # 以前会一路走到第 4 步，把别人的当前地图当成「你所在的位置」继续显示。
    # in_server=False（连续十几秒没有 UDP 连接）已经足够硬，直接判离线。
    # GSI 正在推某张图 = 人在服务器里（netstat 看不到 SDR 连接是常态，别误判离线）
    if in_server is False and not gsi_in:
        result["state"] = "offline"
        result["state_text"] = "未在服务器内"
        result["detail"] = (srv.get("reason")
                            or "已离开 %s，最后加入 %s" % (srv.get("address"), srv.get("joined_text")))
        return result

    # ───── 4) 决定地图 ─────
    # 取数原则：地图以**自证信号**为准（netstat 连接表 → Steam 连接日志 + A2S 实时查询），
    # 关卡只有官方客户端的广播文件能给，且必须与实时地图对得上才可用。
    a2s_map = (srv or {}).get("map")
    map_name = None
    stage_text = truth_text
    stage_mtime = truth_mtime

    # ── 换服反查：netstat 看不到连接时 detect 会停在旧地址，玩家换服后看板不更新 ──
    # 当「旧地址的 A2S 图」与「广播文件里的当前图」不一致时，基本可断定已换服（旧地址的
    # A2S 还在回包，但那是上一台服）。用当前图去九台風雲社服务器反查正在跑它的那台，
    # 把「当前服务器」跟到玩家实际所在的那台。广播文件只作为**反查用的候选图**，
    # 不是权威真值（它换服时不一定刷新，见上方说明）。
    #
    # in_server is True（netstat 认定了某台）时**不能无条件跳过**：那可能是换服瞬间
    # 残留的旧连接（新连接走 SDR 看不到 / 旧 UDP 表项还在），跳过就会一直停在上一个服。
    # 此时要求「反查到的地址确实出现在 netstat 对端列表里」才采信——有真连接做背书，
    # 既不会锁死旧服，也不会把无关服务器误认成当前服。
    _need_reloc = False
    if truth_map:
        if in_server is not True:
            _need_reloc = (not a2s_map) or (a2s_map.lower() != truth_map.lower())
        elif a2s_map and a2s_map.lower() != truth_map.lower():
            _need_reloc = True                      # 需 netstat 对端二次确认，见下
    if _need_reloc:
        _old_map = (srv or {}).get("map")
        # 旁证集合：netstat 对端 + 当前地址 + 三路「最近进过」证据的地址。
        # 反查命中多台（同一张图被好几台服同时跑）时，只有旁证里出现过的那台才采信。
        _pref = set(srv.get("udp_peers") or [])
        _pref.add(srv.get("address") or "")
        for _r in current_server.recent_joins(srv.get("steam_dir") or ""):
            _pref.add(_r.get("address"))
        _rh, _rp, _rinfo = current_server.relocate_by_map(truth_map, prefer=_pref)
        _raddr = "%s:%d" % (_rh, _rp) if _rinfo else None
        if _rinfo and in_server is True and _raddr not in set(srv.get("udp_peers") or []):
            log_warn("[resolve] netstat 认定连着 %s（图 %s）与广播文件当前图 %s 不符，"
                     "但反查到的 %s 不在 UDP 对端里 —— 判定为残留旧连接，维持不换"
                     % (srv.get("address"), _old_map, truth_map, _raddr))
            _rinfo = None
        if _rinfo:
            a2s_map = (_rinfo.get("map") or truth_map)
            srv = dict(srv or {})
            srv.update(available=True, game_running=True,
                       address=_raddr, host=_rh, port=_rp,
                       server_name=current_server.clean_name(_rinfo.get("name")),
                       map=a2s_map, players=_rinfo.get("players"),
                       maxplayers=_rinfo.get("maxplayers"), bots=_rinfo.get("bots"),
                       query_ok=True, in_server=None,
                       addr_source="broadcast-relocate",
                       source="broadcast-relocate")
            result["server"] = srv
            log_warn("[resolve] 广播当前图(%s)与旧地址图(%s)不符，反查当前服务器 %s:%d（%s）"
                     % (truth_map, _old_map, _rh, _rp, _rinfo.get("name")))

    if gsi_in:
        # GSI 有地图 = 游戏自己说「现在就在这张图」，优先级最高：
        # A2S 那套只能证明「某台服还活着/你最近连过它」，退出/换服后经常还是旧图。
        # 反查（relocate_by_map）已在上面试过；找不到就把服务器行留空，只显示地图。
        map_name = gsi_map
        result["source"] = "gsi"
        result["source_text"] = "CS2 游戏状态集成（GSI）"
        if not (a2s_map and a2s_map.lower() == gsi_map):
            result["server_line"] = None
            if srv:
                srv = dict(srv)
                srv["map_mismatch"] = a2s_map
                # 不能把小窗顶栏的服务器名留着——那是「上次连过的那台」，
                # 图上写 鬼泣、服务器名写别的图，玩家一眼就看出错了。
                srv["server_name"] = None
                srv["map"] = None
                result["server"] = srv
    elif a2s_map and truth_map and (a2s_map.lower() == truth_map.lower()):
        # 实时与广播文件一致（常规情况）：地图/服务器名走实时，关卡借用同源文本
        map_name = a2s_map.lower()
        result["source"] = "both"
        result["source_text"] = "服务器实时查询 + fys 广播" + (
            "（宽限缓存）" if srv.get("stale") else "")
        result["server_line"] = (srv or {}).get("server_name")
    elif a2s_map:
        # 实时有图但广播文件没有/对不上 → 广播是上一台服的残留，关卡一并作废
        map_name = a2s_map.lower()
        result["source"] = "server"
        result["source_text"] = "服务器实时查询" + ("（宽限缓存）" if srv.get("stale") else "")
        result["server_line"] = (srv or {}).get("server_name")
        stage_text = ""                       # A2S 不提供关卡号
        for _m in (truth_map, broadcast_map):
            if _m and _m not in result["map_candidates"]:
                result["map_candidates"] = sorted(set(result["map_candidates"] + [_m]))
    elif truth_map:
        # 拿不到实时（A2S 全挂）但有图（广播文件 / GSI）：按它显示
        map_name = truth_map
        if gsi_in:
            result["source"] = "gsi"
            result["source_text"] = "CS2 游戏状态集成（GSI）"
            stage_text = ""            # GSI 没有关卡号，交给比分推断
            stage_mtime = 0
        else:
            result["source"] = "broadcast"
            result["source_text"] = "fys 广播文件"
            stage_text = truth_text
            stage_mtime = truth_mtime

    # ───── 5) 有地址但没拿到地图 ─────
    if not map_name:
        if in_server:
            # 确有连接但一时拿不到地图（A2S 丢包）：别说「未在服务器内」误导人
            result["state"] = "warming"
            result["state_text"] = "已连上服务器，地图获取中…"
            result["detail"] = "netstat 确认与 %s 有连接；%s" % (
                srv.get("address"), srv.get("reason") or "A2S 查询未成功")
        elif srv and srv.get("available") and srv.get("game_running"):
            # CS2 在跑、A2S 这几轮没回包：正在重试，不是「没进服」
            result["state"] = "warming"
            result["state_text"] = "服务器查询中…"
            result["detail"] = "正在重试 %s（%s）" % (
                srv.get("address"), srv.get("query_error") or "查询未响应")
        elif srv and srv.get("available") and not srv.get("query_ok"):
            result["state"] = "offline"
            result["state_text"] = "服务器查询无响应"
            result["detail"] = "最近一次加入 %s（%s）没回应 %s——可能已离开，也可能只是查询超时" % (
                srv.get("address"), srv.get("joined_text"), srv.get("query_error") or "")
        else:
            result["state"] = "offline"
            result["state_text"] = "未在風雲社服务器内"
        return result

    result["map"] = map_name
    result["map_data"] = maps.get(map_name)
    result["knockback"] = (STATE.get("knockback") or {}).get(map_name)
    result["infect"] = (STATE.get("infect") or {}).get(map_name)

    cfg, hit_key, approx = reward_of(map_name)
    result["mapcn"] = mapcn_of(map_name, hit_key)
    if approx:
        result["map_approx"] = hit_key    # 近似命中的官方键，供界面提示
    if not isinstance(cfg, dict) or not cfg:
        result["state"] = "noreward"
        result["state_text"] = "该地图没有奖励配置"
        result["detail"] = "（大厅图 / 非 ZE 图，或该图未在仓库 rewards 目录中）"
        return result

    result["ok"] = True

    def stage_key(k):
        try:
            return (0, int(k))
        except (TypeError, ValueError):
            return (1, str(k))

    rows = []
    for k in sorted(cfg.keys(), key=stage_key):
        row = cfg[k]
        if not isinstance(row, dict):
            continue
        rows.append({"stage": k, "data": row})
    if not rows:
        # rewards 里这张图存在但一个关卡对象都没有（数据写坏了）：
        # 别让后面 rows[0] 抛 IndexError 把整个 /api/status 变成「内部错误」
        result["state"] = "noreward"
        result["state_text"] = "该地图奖励配置为空"
        result["detail"] = "rewards 里这张图没有可用的关卡对象，可能是数据文件损坏"
        return result
    result["stages"] = rows
    result["total_stages"] = len(rows)

    stage = pick_stage_cached(stage_text, stage_mtime,
                              set(r["stage"] for r in rows), map_name)
    stage_src = "broadcast" if stage is not None else None
    # 广播没给关卡（或给的图对不上）时，用 GSI 的 CT 比分推断：
    # ZE 里人类每赢一回合推进一关，map_round_wins / team_ct.score 都是游戏给的。
    if stage is None and gsi_in:
        _gs, _gwhy = gsi.stage_guess(map_name, len(rows))
        if _gs is not None:
            stage = _gs
            stage_src = "gsi"
            result["stage_inferred"] = True
            result["stage_why"] = _gwhy
    result["stage"] = stage
    result["stage_src"] = stage_src
    if stage is not None:
        for r in rows:
            if r["stage"] == str(stage):
                result["current"] = r["data"]
                break
    if result["current"] is None and len(rows) == 1:
        result["current"] = rows[0]["data"]
        result["stage"] = rows[0]["stage"]
    if result["current"] is None:
        result["current"] = rows[0]["data"]
        if stage is None:
            result["stage"] = None

    # 关卡号缺失：给界面一份可读的原因与「当前展示的是第几关」，
    # 避免用户把兜底展示的第 1 关数据误当成识别错误。
    result["stage_hint"] = None
    result["shown_stage"] = None
    if result["stage"] is None:
        result["shown_stage"] = rows[0]["stage"]
        if result.get("source") == "server":
            # 地图来自实时查询、广播文件对不上（多半是上一台服的残留）
            result["stage_hint"] = (
                "当前地图由服务器实时查询得到，fys 广播文件里没有这张图；"
                "官方客户端稍后刷新出这张图就会自动显示关卡号。")
        else:
            stale = ""
            if result.get("raw_mtime_str"):
                stale = "（官方广播最后更新 %s）" % result["raw_mtime_str"]
            result["stage_hint"] = (
                "官方 fys 客户端没有上报当前关卡%s，多半是它还没识别到你已进服；"
                "重启风云社客户端后会自动恢复，本窗口无需刷新。" % stale)
    else:
        result["shown_stage"] = result["stage"]

    # ───── 7) 本局战绩（GSI）：覆盖窗显示「本局伤害 / K-D-A / 伤害兑换」 ─────
    # 伤害口径 = 每回合 round_totaldmg 峰值累加（gsi._match_tick）。
    # 兑换额按该图该关官方配置的「伤害 : 1 货币」比例向下取整，属于**推算**，
    # 界面上必须带「推算/参考」字样（实际以服务器结算为准）。
    try:
        _cm = gsi.current_match()
        if _cm:
            _dmg = int(_cm.get("dmg") or 0)
            _cur = result.get("current") or {}
            _rd = _cur.get("rankDamage")
            _ed = _cur.get("econDamage")
            _cm["rankPts"] = (_dmg // _rd) if isinstance(_rd, int) and _rd > 0 else None
            _cm["econPts"] = (_dmg // _ed) if isinstance(_ed, int) and _ed > 0 else None
            _cm["stage"] = result.get("stage")
            _cm["dmg"] = _dmg
            result["live"] = _cm
    except Exception:                                          # noqa: BLE001
        result["live"] = None

    result["state"] = "ok"
    result["state_text"] = "已连接"
    result["map_data"] = maps.get(map_name)
    try:
        gsi.match_set_stage(result.get("stage") or result.get("shown_stage"))
    except Exception:                                          # noqa: BLE001
        pass
    return result


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return ("%g" % v)
    return str(v)


def server_summary(res):
    """把服务器信息压成一行，给人看。"""
    srv = res.get("server") or {}
    if not srv.get("available"):
        return None
    bits = []
    if srv.get("server_name"):
        bits.append(srv["server_name"])
    elif srv.get("address"):
        bits.append(srv["address"])
    if srv.get("players") is not None and srv.get("maxplayers"):
        bits.append("%s/%s 人" % (srv["players"], srv["maxplayers"]))
    if srv.get("confirmed"):
        bits.append("已确认在服内")
    return "  ·  ".join(bits)


def print_once(res):
    line = "─" * 52
    if not res["ok"]:
        print(line)
        print("  状态：%s" % res["state_text"])
        if res.get("map"):
            print("  地图：%s" % res["map"])
        if res.get("detail"):
            print("  %s" % res["detail"])
        s = server_summary(res)
        if s:
            print("  服务器：%s" % s)
        if res.get("error"):
            print("  %s" % res["error"])
        print(line)
        return
    cur = res["current"] or {}
    stage = res["stage"] if res["stage"] is not None else "未识别"
    print(line)
    if res.get("server_line"):
        print("  服务器    %s" % res["server_line"])
    print("  地图      %s" % res["map"])
    print("  关卡      %s" % stage)
    print("  来源      %s" % (res.get("source_text") or "—"))
    print(line)
    print("  ▸ 通关云点          %s" % fmt(cur.get("rankPasses")))
    print("    通关龙晶          %s" % fmt(cur.get("econPasses")))
    print("    伤害结算云点比例  %s" % fmt(cur.get("rankDamage")))
    print("    低保云点比例      %s /分钟" % fmt(cur.get("rankIntern")))
    print(line)
    if len(res["stages"]) > 1:
        print("  该图全部关卡：")
        for r in res["stages"]:
            mark = "▶" if res["stage"] is not None and r["stage"] == str(res["stage"]) else " "
            print("   %s %-4s 通关云点 %-4s 龙晶 %-4s" % (
                mark, r["stage"], fmt(r["data"].get("rankPasses")), fmt(r["data"].get("econPasses"))))
        print(line)


# ─────────────────────────── 页面 ───────────────────────────
# ⚠ 历史遗留（旧版独立服务入口）：PAGE + 下方 Handler + 文件末尾 main()
#   组成一套自带的网页界面，早已被 fys_reward_app.py 的 ui_page.build_page()
#   取代 —— 主程序不用这条路径，只有直接 `python reward_server.py` 才会跑。
#   下次大版本可整体删除（约 400 行），现仅保留以免影响打包引用。
PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>風雲社 · 通关云点实时查询台</title>
<style>
:root{--bg:#f7f5f1;--card:#fff;--ink:#221f1c;--ink2:#4a443d;--muted:#7d746a;
--line:#e4ded6;--line2:#efeae3;--accent:#a8502b;--asoft:#f6e9e0;--aline:#e6cbb9;
--green:#4a7355;--gsoft:#e8f0e9;--amber:#9a7526;--asoft2:#f7efdc;--gray:#f1eee9;
--mono:"Cascadia Code","JetBrains Mono",Consolas,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;
-webkit-font-smoothing:antialiased;min-height:100vh}
.wrap{max-width:880px;margin:0 auto;padding:34px 24px 60px}
.hd{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:22px}
.hd h1{font-size:19px;font-weight:700;letter-spacing:-.2px}
.hd h1 small{display:block;font-size:12.5px;color:var(--muted);font-weight:400;letter-spacing:0;margin-top:2px}
.pill{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;border-radius:999px;padding:6px 14px;
border:1px solid var(--line);background:var(--card);color:var(--ink2);white-space:nowrap}
.pill i{width:7px;height:7px;border-radius:50%;background:var(--muted);flex:none}
.pill.on i{background:var(--green);box-shadow:0 0 0 3px var(--gsoft)}
.pill.off i{background:var(--accent);box-shadow:0 0 0 3px var(--asoft)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:24px;
box-shadow:0 1px 2px rgba(34,31,28,.04),0 14px 34px -22px rgba(34,31,28,.18)}
.map-row{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.map-row .mn{font-family:var(--mono);font-size:21px;font-weight:600;letter-spacing:-.3px;word-break:break-all}
.tag{font-size:11.5px;font-family:var(--mono);border-radius:6px;padding:3px 9px;background:var(--gray);color:var(--muted)}
.tag.hl{background:var(--asoft);color:var(--accent);border:1px solid var(--aline)}
.sub{color:var(--muted);font-size:13px;margin-top:6px}
.srv{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;margin-top:11px;
padding:9px 13px;background:var(--gray);border-radius:9px}
.srv .slab{font-size:11.5px;color:var(--muted);flex:none;letter-spacing:.04em}
.srv .sname{font-size:13.5px;font-weight:600;color:var(--ink2)}
.srv .smeta{font-size:12px;color:var(--muted);font-family:var(--mono)}
.hint{font-size:13px;color:var(--muted);background:var(--gray);border-radius:9px;padding:11px 14px;margin-top:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:11px;margin-top:24px}
.kv{border:1px solid var(--line2);border-radius:10px;padding:13px 15px;background:#fdfcfa}
.kv .k{font-size:12px;color:var(--muted)}
.kv .v{font-family:var(--mono);font-size:19px;font-weight:600;margin-top:3px}
.kv.hiA{border-color:var(--accent);background:var(--asoft)}
.kv.hiA .k,.kv.hiA .v{color:var(--accent)}
.kv.hiB{border-color:#3a8fb7;background:#eef6fa}
.kv.hiB .k,.kv.hiB .v{color:#2b7ea3}
h2{font-size:14px;color:var(--muted);font-weight:600;letter-spacing:.05em;margin:30px 0 10px;text-transform:uppercase}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;font-size:11.5px;letter-spacing:.05em;color:var(--muted);font-weight:600;
padding:9px 11px;border-bottom:1px solid var(--line);background:#faf8f5;white-space:nowrap}
td{padding:10px 11px;border-bottom:1px solid var(--line2);font-family:var(--mono)}
table.srv{table-layout:fixed}
table.srv th:nth-child(1){width:42%}
table.srv td{white-space:normal;word-break:break-all;font-size:12.5px}
tr:last-child td{border-bottom:none}
tr.cur{background:var(--asoft)}
tr.cur td{font-weight:700;color:var(--accent)}
td.s{font-family:inherit;color:var(--muted)}
.mapcn{font-family:"Microsoft YaHei",sans-serif;font-size:10.5px;opacity:.62;margin-top:1px}
tr.srvrow{cursor:pointer;transition:background .12s}
tr.srvrow:hover{background:rgba(128,128,128,.12)}
.stgov{position:fixed;inset:0;z-index:900;background:rgba(8,6,14,.55);display:flex;align-items:center;justify-content:center}
.stgbox{width:min(520px,86%);max-height:76%;overflow:hidden;display:flex;flex-direction:column;border-radius:14px;
background:#0a0a0c;color:#eceaf2;box-shadow:0 18px 60px rgba(0,0,0,.55);border:1px solid rgba(255,255,255,.14)}
.stghead{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:14px 16px 8px}
.stgtitle{font-weight:700;font-size:14px;word-break:break-all}
.stgsub{font-size:11px;opacity:.65;margin-top:3px}
.stgx{border:0;background:transparent;color:inherit;font-size:14px;cursor:pointer;opacity:.6;padding:2px 6px;border-radius:6px}
.stgx:hover{opacity:1;background:rgba(128,128,128,.15)}
.stgbody{overflow-y:auto;padding:2px 16px 14px}
table.stgtab{width:100%;border-collapse:collapse;font-size:12px}
table.stgtab th{text-align:left;font-weight:600;opacity:.6;font-size:11px;padding:6px 8px;border-bottom:1px solid rgba(255,255,255,.16)}
table.stgtab td{padding:7px 8px;border-bottom:1px dashed rgba(255,255,255,.10)}
td.stgno{white-space:nowrap;font-weight:600}
.stgtab tbody tr:nth-child(even) td{background:rgba(255,255,255,.045)}
.stgtab tr.cur{background:transparent}
.stgtab th{background:transparent;color:#b9b4c6}
.stgtab tr.cur td{background:rgba(255,255,255,.10)!important;font-weight:800;color:#ffc766}
pre{background:#faf8f5;border:1px solid var(--line);border-radius:10px;padding:14px;
font-family:var(--mono);font-size:12.5px;color:var(--ink2);white-space:pre-wrap;word-break:break-all;
max-height:190px;overflow:auto}
.foot{margin-top:28px;padding-top:18px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);
display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}
.warn{border-left:3px solid var(--accent);background:var(--asoft)}
</style></head><body><div class="wrap">

<div class="hd">
  <h1>風雲社 · 通关云点实时查询台<small>数据源 fyscs/cs2 · Reward v22</small></h1>
  <span class="pill" id="pill"><i></i><span id="stateText">连接中…</span></span>
</div>

<div class="card" id="main">
  <div class="map-row">
    <span class="mn" id="mapName">—</span>
    <span class="tag" id="stageTag" style="display:none"></span>
    <span class="tag" id="srcTag" style="display:none"></span>
  </div>
  <div class="sub" id="subText">正在读取广播文件…</div>
  <div class="srv" id="srvBox" style="display:none">
    <span class="slab">服务器</span>
    <span class="sname" id="srvName">—</span>
    <span class="smeta" id="srvMeta"></span>
  </div>

  <div class="hint" id="hint" style="display:none"></div>

  <div class="grid" id="grid"></div>
</div>

<h2>该图全部关卡</h2>
<div class="card" style="padding:6px 6px 6px">
  <table><thead><tr>
    <th>关卡</th><th>通关云点</th><th>通关龙晶</th>
    <th>伤害云点比例</th><th>伤害龙晶比例</th>
  </tr></thead><tbody id="tbody"><tr><td colspan="5" style="text-align:center;color:#7d746a;font-family:inherit">—</td></tr></tbody></table>
</div>

<h2>風雲社 · 僵尸逃跑服务器（实时地图）</h2>
<div class="card" style="padding:6px 6px 2px">
  <table class="srv"><thead><tr>
    <th>服务器</th><th>当前地图</th><th>通关云点</th><th>通关龙晶</th><th>在线</th>
  </tr></thead><tbody id="stb"><tr><td colspan="4" class="s">正在探测…</td></tr></tbody></table>
  <div class="foot" style="border:none;margin:0;padding:10px 11px 6px" id="srvInfo"></div>
</div>

<h2>广播文件原文（备用通道）</h2>
<div class="card" style="padding:14px">
  <pre id="raw">—</pre>
  <div class="foot" style="border:none;padding:10px 0 0;margin:0">
    <span id="fileInfo"></span><span>每 __POLL__ 秒自动刷新</span>
  </div>
</div>

<div class="foot">
  <span id="built"></span>
  <span id="checked"></span>
</div>

</div>
<script>
var POLL = __POLL__;
function n(v){ return (v===undefined||v===null||v==="")?"—":String(v); }

function render(d){
  var pill=document.getElementById('pill'), st=document.getElementById('stateText');
  st.textContent = d.state_text || '未知';
  pill.className = 'pill ' + (d.state==='ok' ? 'on' : 'off');

  document.getElementById('mapName').textContent = d.map
    ? (d.mapcn ? d.map+'（'+d.mapcn+'）' : d.map)
    : (d.state_text || '—');
  var stTag=document.getElementById('stageTag');
  if(d.stage!==null && d.stage!==undefined && d.ok){
    stTag.style.display=''; stTag.className='tag hl'; stTag.textContent='关卡 '+d.stage;
  } else { stTag.style.display='none'; }

  var srcTag=document.getElementById('srcTag');
  if(d.source_text){
    srcTag.style.display=''; srcTag.className='tag'+(d.source==='server'?' hl':'');
    srcTag.textContent='来源 '+d.source_text;
  } else { srcTag.style.display='none'; }

  var sub=document.getElementById('subText');
  if(d.ok){
    var md=d.map_data||{};
    var bits=[];
    if(md.cooldown!==undefined) bits.push('CD '+md.cooldown);
    if(md.price!==undefined) bits.push('预订价 '+md.price+' 龙晶');
    if(md.nomination!==undefined) bits.push('可提名 '+(md.nomination?'是':'否'));
    bits.push('关卡数 '+d.stages.length);
    if(d.stage===null||d.stage===undefined) bits.push('关卡待同步');
    sub.textContent=bits.join('  ·  ');
  } else if(d.state==='noreward'){
    sub.textContent = (d.detail||'') || '该地图没有奖励配置';
  } else { sub.textContent = d.error || d.detail || '等待进入服务器…'; }

  var sv=d.server||{}, box=document.getElementById('srvBox');
  if(sv.available && (sv.server_name || sv.address)){
    box.style.display='';
    document.getElementById('srvName').textContent = sv.server_name || sv.address;
    var sm=[];
    if(sv.address) sm.push(sv.address);
    if(sv.map) sm.push('地图 '+sv.map);
    if(sv.players!==null && sv.players!==undefined && sv.maxplayers) sm.push(sv.players+'/'+sv.maxplayers+' 人');
    if(sv.joined_text) sm.push('进入于 '+sv.joined_text);
    if(sv.confirmed) sm.push('已确认在服内');
    else if(sv.query_ok) sm.push('该服未开放玩家列表');
    if(!sv.query_ok) sm.push('未响应'+(sv.query_error?('：'+sv.query_error):''));
    if(sv.available && !sv.game_running) sm.push('CS2 已退出');
    document.getElementById('srvMeta').textContent = sm.join('  ·  ');
  } else { box.style.display='none'; }

  var cur=d.current||{};
  function wan(v){
    /* 伤害/分数按「万」：≥1000 就换算，1 位小数（与主程序 ui_page 同规则） */
    if(v===null||v===undefined||v==='') return '—';
    var x=+v;
    if(isNaN(x)) return String(v);
    if(x<1000) return String(x);
    var r=Math.round(x/10000*10)/10;
    return (r===Math.round(r)?Math.round(r):r)+'w';
  }

  var hint=document.getElementById('hint');
  if(!d.ok){
    hint.style.display=''; hint.className='hint warn';
    hint.textContent = (d.state==='offline'||d.state==='warming')
      ? ((d.detail ? d.detail+'。' : '当前未在風雲社服务器内。')
        +'定位方式是「Steam 连接日志 + 服务器 A2S 实时查询」，进服后会自动更新，无需刷新。')
      : (d.state==='noreward'
          ? '已定位到服务器与地图，但这张图不在仓库的 rewards 目录里（例如大厅图），所以没有通关云点。'
          : '暂时认不出地图。请把下面的「广播文件原文」发给我，我按真实格式调整识别规则。');
  } else if(d.stage===null || d.stage===undefined){
    hint.style.display=''; hint.className='hint warn';
    var sg=(d.shown_stage!==null&&d.shown_stage!==undefined)?d.shown_stage:d.stages[0].stage;
    hint.textContent='这张图共 '+d.stages.length+' 个关卡，当前关卡号还没拿到，先按第 '+sg+
      ' 关显示数值（下表可查全部）。'+(d.stage_hint?('原因：'+d.stage_hint):'');
  } else { hint.style.display='none'; }

  var g=document.getElementById('grid');
  g.innerHTML='';
  var items=[
    ['通关云点','rankPasses','hiA',' 点'],
    ['通关龙晶','econPasses','hiB',' 颗'],
    ['云点伤害','rankDamage','',''],
    ['龙晶伤害','econDamage','','']
  ];
  for(var i=0;i<items.length;i++){
    var k=items[i][0], key=items[i][1], cls=items[i][2], unit=items[i][3];
    var v=(key==='rankPasses'||key==='econPasses')?n(cur[key]):wan(cur[key]);
    var div=document.createElement('div'); div.className='kv'+(cls?' '+cls:'');
    div.innerHTML='<div class="k">'+k+'</div><div class="v">'+v+
      (unit?'<span style="font-size:12px;color:var(--muted);font-weight:500">'+unit+'</span>':'')+'</div>';
    g.appendChild(div);
  }

  var tb=document.getElementById('tbody'); tb.innerHTML='';
  if(!d.stages || !d.stages.length){
    tb.innerHTML='<tr><td colspan="5" style="text-align:center;color:#7d746a;font-family:inherit">无数据</td></tr>';
  } else {
    d.stages.forEach(function(r){
      var tr=document.createElement('tr');
      if(d.stage!==null && String(d.stage)===String(r.stage)) tr.className='cur';
      var x=r.data||{};
      tr.innerHTML='<td>'+(String(d.stage)===String(r.stage)?'▶ ':'')+r.stage+'</td>'+
        '<td>'+n(x.rankPasses)+'</td><td>'+n(x.econPasses)+'</td>'+
        '<td>'+n(x.rankDamage)+'</td><td>'+n(x.econDamage)+'</td>';
      tb.appendChild(tr);
    });
  }

  document.getElementById('raw').textContent = d.raw || '(空)';
  document.getElementById('fileInfo').textContent =
    '文件修改时间 ' + (d.raw_mtime_str || '—') + ' · ' + (d.broadcast_file || '');
  document.getElementById('built').textContent = '索引构建于 ' + (d.built_at || '—');
  document.getElementById('checked').textContent = '本次检查 ' + (d.checked_at || '—');
}

function tick(){
  fetch('/api/status', {cache:'no-store'})
    .then(function(r){ return r.json(); })
    .then(render)
    .catch(function(e){
      document.getElementById('stateText').textContent='服务未响应';
      document.getElementById('pill').className='pill off';
    });
}

function tickServers(){
  fetch('/api/servers', {cache:'no-store'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      var tb=document.getElementById('stb'); tb.innerHTML='';
      var rows=(d&&d.rows)||[];
      if(!rows.length){
        tb.innerHTML='<tr><td colspan="5" class="s">没有探测到風雲社僵尸逃跑服务器（清单来自 Steam 收藏夹 + 连接历史）。</td></tr>';
      } else {
        rows.forEach(function(x){
          var tr=document.createElement('tr');
          if(x.fys) tr.className='cur';
          var pv='—', ev='—';
          if(x.passes_min!==null && x.passes_min!==undefined){
            pv = (x.passes_min===x.passes_max) ? String(x.passes_min)
               : (x.passes_min+' ~ '+x.passes_max);
            pv += '  <span class="s">('+x.stages+' 关)</span>';
          } else if(x.map){
            pv = '<span class="s">未收录</span>';
          }
          if(x.econ_min!==null && x.econ_min!==undefined){
            ev = (x.econ_min===x.econ_max) ? String(x.econ_min)
               : (x.econ_min+' ~ '+x.econ_max);
          } else if(x.map){
            ev = '<span class="s">未收录</span>';
          }
          var mapCell=n(x.map);
          if(x.mapcn) mapCell+='<div class="mapcn">'+x.mapcn+'</div>';
          var tag = x.src==='favorite' ? ' <span class="s" style="color:#b8860b">[收藏]</span>'
                  : x.src==='history'  ? ' <span class="s">[历史]</span>' : '';
          tr.innerHTML='<td class="s" style="max-width:230px;word-break:break-all">'+(x.name||x.address)+tag+
            '</td><td>'+mapCell+'</td><td>'+pv+'</td><td>'+ev+'</td><td>'+
            (x.players===null||x.players===undefined?'—':(x.players+'/'+x.maxplayers))+'</td>';
          if(x.map){
            tr.className=(tr.className?tr.className+' ':'')+'srvrow';
            tr.title='点击查看每关通关云点 / 龙晶';
            tr.onclick=function(){ openStages(x.map); };
          }
          tb.appendChild(tr);
        });
      }
      document.getElementById('srvInfo').textContent =
        '探测于 '+(d.at||'—')+' · 在线 '+((d.count)||0)+' 台 / 共 '+((d.addresses)||0)+
        ' 个地址 · 清单来自 Steam 收藏夹 + 连接历史 · 每分钟自动刷新';
    })
    .catch(function(){});
}
tick();
tickServers();
setInterval(tick, POLL);
setInterval(tickServers, 15000);

/* ── 关卡明细弹窗 ── */
function openStages(map){
  var ov=document.getElementById('stgOv');
  ov.style.display='';
  document.getElementById('stgTitle').textContent = map;
  document.getElementById('stgSub').textContent = '加载中…';
  document.getElementById('stgBody').innerHTML = '';
  fetch('/api/rewards?map='+encodeURIComponent(map), {cache:'no-store'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      var cn=d.mapcn ? '（'+d.mapcn+'）' : '';
      document.getElementById('stgTitle').textContent = map + cn;
      if(!d.ok || !d.stages.length){
        document.getElementById('stgSub').textContent='这张图不在仓库奖励目录里（例如大厅图），没有关卡数据。';
        return;
      }
      var st=d.stages, rmin=null,rmax=null,emin=null,emax=null;
      st.forEach(function(s){
        [s.rankPasses].forEach(function(v){ if(v!==null&&v!==undefined){ rmin=(rmin===null)?v:Math.min(rmin,v); rmax=(rmax===null)?v:Math.max(rmax,v);} });
        [s.econPasses].forEach(function(v){ if(v!==null&&v!==undefined){ emin=(emin===null)?v:Math.min(emin,v); emax=(emax===null)?v:Math.max(emax,v);} });
      });
      document.getElementById('stgSub').textContent='共 '+st.length+' 关 · 通关云点 '+(rmin===null?'未收录':(rmin===rmax?rmin:rmin+'~'+rmax))+
        ' · 通关龙晶 '+(emin===null?'未收录':(emin===emax?emin:emin+'~'+emax));
      var h='<table class="stgtab"><thead><tr><th>关卡</th><th>通关云点</th><th>通关龙晶</th><th>云点伤害</th><th>龙晶伤害</th></tr></thead><tbody>';
      var fmt=function(v){ return (v===null||v===undefined)?'—':String(v).replace(/\B(?=(\d{3})+(?!\d))/g,','); };
      st.forEach(function(s){
        h+='<tr><td class="stgno">第 '+s.stage+' 关</td><td>'+n(s.rankPasses)+'</td><td>'+n(s.econPasses)+
           '</td><td>'+fmt(s.rankDamage)+'</td><td>'+fmt(s.econDamage)+'</td></tr>';
      });
      h+='</tbody></table>';
      document.getElementById('stgBody').innerHTML=h;
    })
    .catch(function(){ document.getElementById('stgSub').textContent='加载失败，请稍后再试。'; });
}
function closeStages(){ document.getElementById('stgOv').style.display='none'; }
</script>
<div class="stgov" id="stgOv" style="display:none" onclick="if(event.target===this)closeStages()">
  <div class="stgbox">
    <div class="stghead">
      <div><div class="stgtitle" id="stgTitle">—</div><div class="stgsub" id="stgSub">加载中…</div></div>
      <button class="stgx" id="stgX">✕</button>
    </div>
    <div class="stgbody" id="stgBody"></div>
  </div>
</div>
<script>document.getElementById('stgX').onclick=closeStages;</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _host_ok(self):
        """回环校验（与桌面版 fys_reward_app 同款，只读服务至少校验 Host）：
        挡住浏览器跨站请求与 DNS rebinding —— 恶意网页不能借本机服务读
        广播文件原文里的服务器地址等本机信息。"""
        def _loop(h):
            h = (h or "").strip().lower()
            h = h.rsplit(":", 1)[0] if h.count(":") == 1 else h.lstrip("[").split("]")[0]
            return h in ("127.0.0.1", "localhost", "::1")
        if not _loop(self.headers.get("Host")):
            return False
        origin = self.headers.get("Origin")
        if origin:
            try:
                oh = urllib.parse.urlsplit(origin).hostname or ""
            except ValueError:
                return False
            if oh.lower() not in ("127.0.0.1", "localhost", "::1"):
                return False
        return True

    def do_GET(self):
        if not self._host_ok():
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = PAGE.replace("__POLL__", str(POLL_MS)).encode("utf-8")
            ctype = "text/html; charset=utf-8"
        elif path == "/api/status":
            try:
                body = json.dumps(resolve(), ensure_ascii=False).encode("utf-8")
            except Exception as e:
                body = json.dumps({"state": "error", "state_text": "内部错误",
                                   "error": repr(e), "ok": False, "stages": [],
                                   "raw": ""}, ensure_ascii=False).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        elif path == "/api/servers":
            try:
                body = json.dumps(servers_payload(), ensure_ascii=False).encode("utf-8")
            except Exception as e:
                body = json.dumps({"rows": [], "error": repr(e)}, ensure_ascii=False).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        elif path == "/api/rewards":
            try:
                body = json.dumps(rewards_payload(urllib.parse.parse_qs(
                    urllib.parse.urlsplit(self.path).query).get("map", [""])[0]),
                    ensure_ascii=False).encode("utf-8")
            except Exception as e:
                body = json.dumps({"ok": False, "stages": [], "error": repr(e)},
                                  ensure_ascii=False).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


STATE = {"rewards": {}, "maps": {}, "meta": {}, "srv_cache": None, "knockback": {},
         "infect": {}, "diff": {}, "mapcfg": {}, "updlog": []}

# 数据就绪闸门。load_state() 跑在后台线程（fys_reward_app 的 _boot_load），
# 而它跑完前 STATE 全是空的 —— 这时若被 /api/mapparams、/api/updlog 命中，
# 界面会显示「没有参数 / 还没有记录」，而前端拿到就缓存了、之后不再自动重取
# （用户实测：打开软件立刻点开一张图，参数是空的）。所以这两个接口先等一下。
STATE_READY = threading.Event()


def wait_state(timeout=20.0):
    """等后台 load_state 就绪；已就绪零开销。返回是否就绪。"""
    if STATE_READY.is_set():
        return True
    return STATE_READY.wait(timeout)


def _data_path(name):
    """数据文件定位：优先 exe 旁边的 data/（打包后同步到的最新数据），
    没有就回退到打包进 exe / 源码目录里的那份。"""
    cands = [os.path.join(BASE_DIR, "data", name),
             os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", name)]
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[0]


def _load_json(name, default, norm=None):
    """读 data/<name> 并交给 norm 归一化；任何异常/形状不对都回 default。

    这四个表原来是同一段样板抄了四遍（打开 → json.load → isinstance 校验 →
    except 返回默认值）。出错时的兜底行为最容易只改了一处，收敛成一个函数后
    「读坏文件不崩、界面显空」这条契约只有一处需要维护（v2.14 结构⑦）。
    norm(d) 返回归一化结果，形状不符时抛异常即可（会被吞掉并回 default）。
    """
    p = _data_path(name)
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        return norm(d) if norm else d
    except Exception:                                          # noqa: BLE001
        return default


def _load_knockback():
    """击退系数表（地图名 -> 系数），数据与风云社官方直播助手同源。"""
    return _load_json("knockback.json", {},
                      lambda d: {str(k).strip().lower(): v for k, v in d.items()})


def _load_infect():
    """尸变参数表（地图名 -> {rand, ratio, time, tp}）。

    源自仓库 2001/csgo/cfg/map-configs/<地图>.cfg：
      rand=1 纯随机尸变（官方 ze_infect_sort_by_immunity=false）
      rand=0 按尸变指数降序选母体
    """
    return _load_json("infect.json", {},
                      lambda d: {str(k).strip().lower(): v
                                 for k, v in d.items() if isinstance(v, dict)})


def _load_mapcfg():
    """每图 cfg 全量参数表（紧凑编码 {k, cn, v}）；给地图库详情用。

    表只增不减地随上游同步刷新，读坏就返回 {}（界面显示「暂无参数」而不是崩）。
    """
    def norm(d):
        if not (isinstance(d, dict) and isinstance(d.get("k"), list)):
            raise ValueError("mapcfg 形状不对")
        return d
    return _load_json("mapcfg.json", {}, norm)


def _load_updlog():
    """上游变更台账（列表，最新在前）。"""
    def norm(d):
        if not isinstance(d, list):
            raise ValueError("upd_log 应为列表")
        return d
    return _load_json("upd_log.json", [], norm)


def map_params_payload(name):
    """单图完整参数（cfg 全量 + 选图参数），供地图库详情「地图参数」卡使用。"""
    f = str(name or "").strip().lower()
    if not f:
        return {"ok": False, "error": "缺少地图名"}
    store = STATE.get("mapcfg") or {}
    row = build_index.cfg_rows(store).get(f) or {}
    groups = build_index.cfg_groups(row, build_index.cfg_cn(store))
    ms = build_index.mapset_rows(STATE.get("maps") or {}).get(f) or {}
    order = {cn: i for i, (_fk, cn) in enumerate(build_index.MAPSET_FIELDS)}
    set_items = sorted(({"n": k, "v": v} for k, v in ms.items()),
                       key=lambda it: order.get(it["n"], 99))
    return {"ok": True, "f": f, "has": bool(row),
            "groups": [{"n": n, "items": [{"n": a, "k": b, "v": c} for a, b, c in its]}
                       for n, its in groups],
            "set": set_items}


def map_diff_payload(name):
    """单图「新旧参数对比」：当前数据 vs 上次同步前（*.prev.json 快照）。

    玩家更新完数据后想知道「这张图到底改了什么」，而不是对着新数字自己猜。
    prev = build(force) 覆盖前存的旧数据（见 build_index.snapshot_prev）。"""
    f = str(name or "").strip().lower()
    if not f:
        return {"ok": False, "error": "缺少地图名"}

    def _load(suffix):
        out = {}
        for n in build_index._PREV_FILES:
            try:
                with open(os.path.join(build_index.DATA_DIR, n + suffix),
                          encoding="utf-8") as fh:
                    out[n] = json.load(fh)
            except Exception:                                  # noqa: BLE001
                out[n] = None if n == "mapcfg" else {}
        return out

    cur = _load(".json")
    prev = _load(".prev.json")
    if not (prev.get("rewards") or prev.get("maps")):
        # 首次安装 / 旧版升级上来还没同步过：没有「更新前」可比
        return {"ok": True, "f": f, "has_prev": False,
                "changed": False, "groups": {}}
    d = build_index.diff_repo(
        prev.get("rewards") or {}, prev.get("maps") or {},
        prev.get("infect") or {},
        cur.get("rewards") or {}, cur.get("maps") or {},
        cur.get("infect") or {},
        prev.get("mapcfg"), cur.get("mapcfg"))
    groups = {}
    for g, rows in (d.get("groups") or {}).items():
        hit = [it for it in (rows or [])
               if str(it.get("map") or "").strip().lower() == f]
        if hit:
            groups[g] = hit
    total = sum(len(v) for v in groups.values())
    cn = ""
    try:
        import mapnames as _mn
        cn = str(_mn.cn(f) or "")
    except Exception:                                          # noqa: BLE001
        pass
    return {"ok": True, "f": f, "has_prev": True,
            "changed": total > 0, "total": total,
            "mapcn": cn, "groups": groups}


def updlog_payload():
    """上游变更台账 + 类型汇总，供首页「上游更新」面板使用。

    顺带给每张图补上中文译名（c）：台账是按检测时刻逐条落盘的，图名只有英文；
    界面拿译名表现查现填，旧记录也能显示出中文名，不用重录。"""
    log = [e for e in (STATE.get("updlog") or []) if isinstance(e, dict)]
    try:
        import mapnames as _mn
    except Exception:                                          # noqa: BLE001
        _mn = None
    for e in log:
        for m in (e.get("maps") or []):
            if not isinstance(m, dict) or m.get("c"):
                continue
            if _mn is not None:
                try:
                    m["c"] = str(_mn.cn(m.get("f") or "") or "")
                except Exception:                              # noqa: BLE001
                    m["c"] = ""
            else:
                m["c"] = ""
    kinds = {}
    for e in log:
        for k, n in (e.get("kinds") or {}).items():
            kinds[k] = kinds.get(k, 0) + int(n or 0)
    return {"ok": True, "total": len(log),
            "last": (log[0].get("at") if log else ""),
            "kinds": kinds, "entries": log[:60]}
_WATCHER_STARTED = [False]


def servers_payload():
    """服务器实时看板数据：每台服的当前地图 + 该图通关云点区间。

    同时附上风雲社官网口径的实时人数做交叉校验（官网免登录接口，
    地图/关卡字段官网需登录，这里只用它的人数与在线状态）。
    """
    rewards = STATE["rewards"]
    c = STATE.get("srv_cache") or {"rows": [], "addresses": 0}
    if not c.get("rows"):
        # watcher 第一轮还没回来（刚启动 / 重启后）：就地兜底取一次（云端优先，
        # 正常零点几秒；失败回退本机 A2S）。取到就写回缓存，后续请求零开销
        try:
            c = srv_snapshot()
            if c and c.get("rows"):
                STATE["srv_cache"] = c
        except Exception:                                      # noqa: BLE001
            pass
    try:
        ws = fys_web.snapshot()
    except Exception:                                      # noqa: BLE001
        ws = {"ok": False, "by_addr": {}, "by_port": {}}
    out = []
    matched = 0
    for r in c.get("rows", []):
        m = (r.get("map") or "").lower()
        cfg, hit_key, approx = reward_of(m)
        item = {
            "name": r.get("name"), "address": r.get("address"), "map": r.get("map"),
            "mapcn": mapcn_of(r.get("map"), hit_key),
            "map_approx": hit_key if approx else None,
            "players": r.get("players"), "maxplayers": r.get("maxplayers"),
            "fys": current_server.is_fys(r.get("name")),
            "src": r.get("source"),
            "stages": 0, "passes_min": None, "passes_max": None,
            "econ_min": None, "econ_max": None,
            "web": None,
        }
        if ws.get("ok"):
            w, how = fys_web.lookup(r.get("address"), ws)
            if w:
                matched += 1
                item["web"] = {
                    "players": w.get("players"), "maxplayers": w.get("maxplayers"),
                    "id": w.get("server_id"), "short": w.get("short"),
                    "how": how,
                    "same": w.get("players") == r.get("players"),
                }
        if isinstance(cfg, dict) and cfg:
            vals = [v.get("rankPasses") for v in cfg.values()
                    if isinstance(v, dict) and isinstance(v.get("rankPasses"), int)]
            if vals:
                item["stages"] = len(cfg)
                item["passes_min"] = min(vals)
                item["passes_max"] = max(vals)
            evals = [v.get("econPasses") for v in cfg.values()
                     if isinstance(v, dict) and isinstance(v.get("econPasses"), int)]
            if evals:
                item["econ_min"] = min(evals)
                item["econ_max"] = max(evals)
        out.append(item)
    try:
        web = fys_web.summary(ws)
    except Exception:                                      # noqa: BLE001
        web = {"ok": False}
    web["matched"] = matched
    return {
        "at": time.strftime("%H:%M:%S"),
        "cloud": bool(c.get("cloud")),
        "addresses": c.get("addresses", 0),
        "count": len(out),
        # 固定清单里「探得到」的台数（探不到的仍留在列表里，人数显示 —）
        "online": sum(1 for i in out if i.get("players") is not None),
        # 索引是否已载入本地缓存：False 时行里的「未收录」只是还没来得及读，
        # 前端口径要说「读取中」而不是断言没录（启动首秒的体验，见 load_cached_state）
        "index_ready": bool(rewards),
        "rows": out,
        "web": web,
    }


def rewards_payload(map_name):
    """某张地图每关的通关云点/龙晶明细（服务器行点击展开用）。

    上游有变更时（repo_diff 命中），对应关卡附 upd = {字段: 旧值}，
    界面在数值旁标「↑ 原 X」。
    """
    m = (map_name or "").strip().lower()
    cfg, hit_key, approx = reward_of(m)
    if not isinstance(cfg, dict) or not cfg:
        return {"ok": False, "map": m, "mapcn": mapcn_of(m), "stages": []}
    # 变更索引：(小写地图名, str(关卡)) -> {字段: 旧值}
    diff = STATE.get("diff") or {}
    dgroups = diff.get("groups") or {}
    upd_by_stage = {}
    for e in dgroups.get("edit") or []:
        if not isinstance(e, dict):
            continue
        em = str(e.get("map") or "").lower()
        for fl in e.get("fields") or []:
            upd_by_stage.setdefault((em, str(fl.get("stage"))), {})[fl.get("f")] = fl.get("old")
    map_new = {str(e.get("map") or "").lower() for e in dgroups.get("new") or []
               if isinstance(e, dict)}
    stages = []
    for k, v in cfg.items():
        if not isinstance(v, dict):
            continue
        try:
            n = int(k)
        except (TypeError, ValueError):
            continue
        row = {
            "stage": n,
            "rankPasses": v.get("rankPasses"),
            "econPasses": v.get("econPasses"),
            "rankDamage": v.get("rankDamage"),
            "econDamage": v.get("econDamage"),
            "rankIntern": v.get("rankIntern"),
        }
        u = upd_by_stage.get((m, str(n)))
        if u:
            row["upd"] = u
        stages.append(row)
    stages.sort(key=lambda x: x["stage"])
    return {"ok": True, "map": m, "mapcn": mapcn_of(m, hit_key),
            "approx": approx, "hit": hit_key if approx else None,
            "is_new": m in map_new, "stages": stages}


# ───────────── 服务器状态：云端优先，本地探测兜底 ─────────────
# 云端由服务器常驻进程每 30 秒探一轮（带重试），成功率远高于本机单发 A2S；
# 所以能用就用。拿不到、解析不了、或数据已经停更时，一律回退本机链路，
# 保证任何时候都有数据、且离线可用。
# v2.14 起服务器停用 → 默认为空，直接走本机 A2S 探测（不再每次等 3 秒超时）。
# 将来又有云端状态源时设 FYS_CLOUD_STATUS 即可恢复。
CLOUD_STATUS_URL = (os.environ.get("FYS_CLOUD_STATUS", "") or "").strip().rstrip("/")
CLOUD_MAX_AGE = 150.0          # 云端数据旧于这个秒数就认为服务异常
_CLOUD_FAIL = {"n": 0}


def _rows_from_cloud(d):
    """云端 status.json → 与本地 fys_servers() 同构的 rows。"""
    rows = []
    for s in (d.get("servers") or []):
        lab = s.get("label") or ""
        if not s.get("ok"):
            rows.append({"address": s.get("address"), "host": s.get("host"),
                         "port": s.get("port"), "source": "cloud", "label": lab,
                         "name": current_server.FYS_SERVER_NAME % lab,
                         "map": None, "players": None, "maxplayers": None,
                         "query_ok": False})
            continue
        rows.append({"address": s.get("address"), "host": s.get("host"),
                     "port": s.get("port"), "source": "cloud", "label": lab,
                     # 显示层统一清洗（同 current_server.clean_name）：云端 name 是
                     # A2S 原始服务器名，自带「Q群:xxxx」推广后缀，透传出去列表就花了
                     "name": current_server.clean_name(s.get("name")),
                     "map": s.get("map"),
                     "players": s.get("players"),
                     "maxplayers": s.get("maxplayers"),
                     "query_ok": True, "names": s.get("names")})
    return rows


def srv_rows_cloud():
    """读云端状态；不可用返回 None（调用方应回退本地探测）。"""
    if not CLOUD_STATUS_URL:              # 离线版：直接走本机探测，不发请求
        return None
    import urllib.request
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open(CLOUD_STATUS_URL, timeout=3.0) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:                                     # noqa: BLE001
        _CLOUD_FAIL["n"] += 1
        if _CLOUD_FAIL["n"] <= 3 or _CLOUD_FAIL["n"] % 20 == 0:
            log_warn("云端状态不可用（%r），改用本地探测" % e)
        return None
    try:
        ts = float(d.get("ts") or 0)
        if ts and (time.time() - ts) > CLOUD_MAX_AGE:
            return None                       # 云端停更了，宁可自己探
        rows = _rows_from_cloud(d)
        if not rows:
            return None
        _CLOUD_FAIL["n"] = 0
        return {"rows": rows, "addresses": len(rows), "cloud": True,
                "at": d.get("str")}
    except Exception as e:                                     # noqa: BLE001
        log_warn("云端状态解析失败（%r），改用本地探测" % e)
        return None


def _augment_rows(c):
    """云端 status.json 只覆盖它自己那份清单；官网新增的 ZE 服（云端脚本还没更新时）
    在这里本地补探一次，避免看板漏服（检测侧已用动态清单，两边必须对齐）。"""
    have = {r.get("address") for r in (c.get("rows") or [])}
    try:
        missing = [row for row in current_server.fixed_rows()
                   if row["address"] not in have]
    except Exception:                                          # noqa: BLE001
        return c
    if not missing:
        return c
    try:
        alive = {r["address"]: r for r in current_server.scan_addresses(missing)}
    except Exception:                                          # noqa: BLE001
        alive = {}
    rows = list(c.get("rows") or [])
    for row in missing:
        got = alive.get(row["address"])
        if got:
            got["label"] = row.get("label")
            rows.append(got)
        else:
            miss = dict(row)
            miss.update({"name": current_server.FYS_SERVER_NAME % row.get("label"),
                         "map": None, "players": None, "maxplayers": None,
                         "query_ok": False})
            rows.append(miss)
    rows.sort(key=lambda r: -(r.get("players") or 0))
    return {"rows": rows, "addresses": len(rows), "cloud": True, "at": c.get("at")}


def srv_snapshot(force=False):
    """服务器看板数据源：云端优先（与官网动态清单对齐），失败回退本机 A2S。"""
    c = srv_rows_cloud()
    if c:
        return _augment_rows(c)
    return current_server.fys_servers(force=force)


def start_server_watcher(interval=30):
    """后台线程：定时刷新服务器看板（A2S 并发探测，不阻塞页面）。"""
    if _WATCHER_STARTED[0]:
        return
    _WATCHER_STARTED[0] = True

    def loop():
        fail = 0
        while True:
            cloud_ok = False
            try:
                c = srv_rows_cloud()
                cloud_ok = bool(c)
                if cloud_ok:
                    STATE["srv_cache"] = _augment_rows(c)
                    fail = 0
            except Exception:                                  # noqa: BLE001
                pass
            if not cloud_ok:
                # 云端不可用：回退本地探测。force=False 尊重 fys_servers 自身 60s TTL，
                # 避免云端挂掉期间变成「云端 30s 一轮 + 本地 30s 一轮」的双份全量 A2S
                try:
                    STATE["srv_cache"] = current_server.fys_servers(force=False)
                except Exception:                              # noqa: BLE001
                    pass
                fail += 1
                if fail >= 3:
                    # 连续失败退避：第 3 次起额外多等 1~3 个间隔（最多 4 倍），别对着挂掉的云端空转
                    time.sleep(interval * min(fail - 2, 3))
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()


def _load_diff():
    """上游变更检测结果（build_index 每次同步落盘），补上中文名进 STATE。"""
    p = _data_path("repo_diff.json")
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:                                          # noqa: BLE001
        return {}
    if not isinstance(d, dict):
        return {}
    for grp in (d.get("groups") or {}).values():
        if isinstance(grp, list):
            for row in grp:
                if isinstance(row, dict) and row.get("map"):
                    try:
                        row["mapcn"] = mapnames.cn(row["map"])
                    except Exception:                          # noqa: BLE001
                        row["mapcn"] = None
    return d


def diff_summary():
    """/api/status 附带的横幅摘要（轻量，每秒轮询走这里）。"""
    d = STATE.get("diff") or {}
    return {"counts": d.get("counts") or {},
            "seen": bool(d.get("seen", True)),
            "detected_at": d.get("detected_at"),
            "first": bool(d.get("first"))}


def diff_payload():
    """变更明细全量（弹窗用）。"""
    return STATE.get("diff") or {}


def diff_mark_seen():
    """用户确认过提醒：seen 写回 repo_diff.json + 内存同步（幂等）。"""
    d = STATE.get("diff") or {}
    if not d or d.get("seen"):
        return
    d["seen"] = True
    STATE["diff"] = d
    p = _data_path("repo_diff.json")
    try:
        tmp = p + ".seen.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:                                          # noqa: BLE001
        pass


def refresh_diff():
    """后台定时检测后，把落盘的 repo_diff.json 重新读回 STATE["diff"]，并 bump
    _gen 让前端下次轮询 /api/status 就能带出新的「官方数据有更新」横幅。

    仅刷新内存态、不写盘（写盘由 build_index 负责）。幂等、可在任意线程调用。
    """
    STATE["diff"] = _load_diff()
    # 后台检测也可能新记一条台账（不覆盖缓存，但历史要跟着更新）
    STATE["updlog"] = _load_updlog()
    STATE["_gen"] = (STATE.get("_gen") or 0) + 1


def load_state(force=False, progress=None):
    """progress(text, pct)：可选的阶段进度回调（「立即同步」时喂给界面）。

    手不手动同步都要走这里，回调只在传入时生效，默认无副作用。
    """
    build_index.set_progress(progress)
    try:
        meta = build_index.build(force=force)
    finally:
        build_index.set_progress(None)
    return apply_state(meta, progress)


def load_cached_state(meta=None):
    """只用本地缓存点亮界面（不联网、不下载）。

    启动顺序（v2.14 追加）：先 load_cached_state() 秒开，再后台 load_state() 校准。
    以前启动就 build()：缓存超过 10 分钟会重新下载整包，这 5~15 秒里
    STATE["rewards"] 还是空的 → 服务器列表每台都显示「未收录」，
    玩家以为数据没录（2026-10-28 用户反馈）。
    本地缓存缺失/读坏时抛异常，让调用方退回完整 load_state。
    """
    if not os.path.exists(build_index.REWARDS_OUT):
        raise FileNotFoundError(build_index.REWARDS_OUT)
    if meta is None:
        meta = {}
        try:
            with open(build_index.META_OUT, encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            meta = {}
    return apply_state(meta, None)


def apply_state(meta, progress=None):
    """把 data\\ 下的索引/参数/台账读进 STATE，并放行等待中的接口。"""
    try:
        rewards, maps, _ = build_index.load_cache()
    except (ValueError, OSError) as e:
        # data/rewards.json 被写坏（同步中途关窗 / 磁盘满 / 手工编辑）时，
        # 不要让整个程序起不来：退回到打包内置的那份数据，并标记降级。
        log_warn("索引缓存读取失败（%r），改用内置数据" % e)
        rewards, maps = _load_fallback_index()
        meta = dict(meta or {})
        meta["degraded"] = "索引缓存损坏，已用内置数据；请在「设置 → 立即同步」重试"
    STATE["rewards"] = rewards
    STATE["maps"] = maps
    if progress:
        try:
            progress("正在载入地图参数与变更台账…", 95)
        except Exception:                                      # noqa: BLE001
            pass
    STATE["meta"] = meta
    STATE["knockback"] = _load_knockback()
    STATE["infect"] = _load_infect()
    STATE["mapcfg"] = _load_mapcfg()          # 地图库详情「地图参数」卡的数据源
    STATE["updlog"] = _load_updlog()          # 上游变更台账（「上游更新」面板）
    STATE["diff"] = _load_diff()     # 同步后重建的变更检测（build 落盘 → 这里读回）
    STATE["_gen"] = (STATE.get("_gen") or 0) + 1     # 广播解析缓存整体失效
    # 索引整片换代：前端据此丢掉地图库的 LIB.all / LIB.cfg 缓存并重取
    #（否则「立即更新」后地图库还是启动时那份旧配置，要重启才变）
    STATE["_dgen"] = (STATE.get("_dgen") or 0) + 1
    # 「新旧参数对比」的快照兜底：升级上来第一次启动还没有 *.prev.json 时，
    # 把当前数据存一份当「更新前」。否则用户要同步两次才能见到对比卡，
    # 会以为功能没做（2026-10-23 用户反馈）。已有快照时不动它 ——
    # 那是「上次同步前」的真实旧数据。
    try:
        if not os.path.exists(os.path.join(build_index.DATA_DIR,
                                           "rewards.prev.json")):
            build_index.snapshot_prev()
    except Exception:                                          # noqa: BLE001
        pass
    STATE_READY.set()                # 放行 /api/mapparams、/api/updlog 的等待
    start_server_watcher()
    return meta


def _load_fallback_index():
    """内置（打包进 exe / 源码目录）的 rewards.json + maps.json。

    注意两个候选都要试：BASE_DIR/data 可能就是刚写坏的那个文件，
    所以按「内置目录 → 运行目录」顺序取第一个能解析成功的。
    """
    dirs = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
            os.path.join(BASE_DIR, "data")]
    out = []
    for name in ("rewards.json", "maps.json"):
        got = {}
        for d in dirs:
            p = os.path.join(d, name)
            if not os.path.exists(p):
                continue
            try:
                with open(p, encoding="utf-8") as fh:
                    got = json.load(fh)
                break
            except (OSError, ValueError):
                continue
        out.append(got if isinstance(got, dict) else {})
    return out[0], out[1]


_WARNED = set()


def log_warn(msg):
    """记一条只出现一次的告警（写进启动日志，不弹窗、不打断）。"""
    if msg in _WARNED:
        return
    _WARNED.add(msg)
    try:
        p = os.path.join(BASE_DIR, "data", "startup.log")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("%s  [引擎] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def main():
    args = sys.argv[1:]
    print("=" * 54)
    print("  風雲社 · 通关云点实时查询台")
    print("=" * 54)
    meta = load_state(force="--force" in args or "-f" in args)
    print("索引：%s 张地图 / %s 个关卡" % (meta.get("maps"), meta.get("stages")))
    print("广播文件：%s" % BROADCAST_FILE)
    print("  （文件存在：%s）" % os.path.exists(BROADCAST_FILE))
    print()

    if "--once" in args:
        print_once(resolve())
        return

    if "--watch" in args:
        print("监听中，Ctrl+C 退出。\n")
        last = None
        while True:
            r = resolve()
            sig = (r["state"], r["map"], r["stage"],
                   (r["current"] or {}).get("rankPasses"), r["raw_mtime"])
            if sig != last:
                os.system("")       # 让 Windows 终端能正常显示 ANSI
                print("\033[2J\033[H", end="")
                print_once(r)
                last = sig
            time.sleep(0.8)
        return

    port = DEFAULT_PORT
    if "--port" in args:
        try:
            port = int(args[args.index("--port") + 1])
        except (IndexError, ValueError):
            pass
    url = "http://127.0.0.1:%d/" % port
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("页面地址：%s" % url)
    print("（Ctrl+C 停止服务）\n")
    if "--no-open" not in args:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        srv.server_close()


if __name__ == "__main__":
    main()

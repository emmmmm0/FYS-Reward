# -*- coding: utf-8 -*-
"""CS2 Game State Integration（GSI）接入层。

官方机制：在 CS2 的 cfg 目录放一份 gamestate_integration_*.cfg，游戏就会把
完整状态 JSON 用 **POST** 推给本机 HTTP 地址（变化即推 + heartbeat 兜底）。
这里负责三件事：

  1) 解析与缓存最新一条状态（地图 / 阶段 / 回合 / 比分 / 个人战况），给
     resolve() 当「当前对局」的权威证据（比广播文件 + A2S 更直接）；
  2) 用 **CT 比分** 推断当前关卡（ZE 里人类赢一回合推进一关；
     map_round_wins / team_ct.score 都是游戏自己给的，不用猜）；
  3) 记录每局战绩（时长 / 比分 / K-D-A / 累计伤害）落盘 data/matches.json。

⚠ 关卡推断只作为「广播文件没给关卡」时的兜底，界面上必须标注「按比分推断」；
   官方客户端广播里有明确关卡号时以它为准（见 reward_server.resolve）。

⚠ 破坏性约定：GSI payload 里 player.state.round_totaldmg 是「本回合累计伤害」，
   回合结束会清零 —— 所以按回合号取 max 再累加（不是简单相加），
   这样同回合内的推送把值往上涨也不会重复计数。
"""
import ctypes
import io
import json
import os
import random
import re
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("FYS_DATA_DIR") or os.path.join(BASE_DIR, "data")
CFG_NAME = "gamestate_integration_cloudshop.cfg"
CFG_FILE = os.path.join(DATA_DIR, "gsi.json")          # 本软件的 GSI 设置 + token
MATCH_FILE = os.path.join(DATA_DIR, "matches.json")    # 对局战绩
MATCH_MAX = 300                                        # 最多留 300 局
FRESH_SEC = 15.0                                       # 超过这么久没推送 = 不在对局
STALE_SEC = 120.0                                      # 超过这么久没推送 = 收拾残局（落盘）

_LOCK = threading.RLock()
_ST = {
    "at": 0.0,          # 最后一条推送时间（time.time）
    "n": 0,             # 累计收到多少条（只用于判断「连上了没有」）
    "map": "",          # 规范化后的地图名（小写，去掉 workshop/NNN/ 前缀）
    "map_raw": "",
    "phase": "",
    "round": None,
    "ct": None, "t": None,
    "round_wins": {},
    "name": "", "kills": None, "deaths": None, "assists": None, "mvps": None,
    "hp": None, "armor": None, "money": None,
    "dmg_round": None, "round_kills": None,
    "last_err": "",
    "rejects": 0,       # 带了 token 但对不上（伪造/旧 cfg）
    "noauth": 0,        # CS2 没回传 auth（放行，但记一笔便于排查）
}


def _now():
    return time.time()


# ─────────────────────────── 设置（data/gsi.json） ───────────────────────────
def load_cfg():
    try:
        with io.open(CFG_FILE, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        if not isinstance(d, dict):
            return {}
        return d
    except (OSError, ValueError):
        return {}


def save_cfg(d):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = "%s.%d.tmp" % (CFG_FILE, threading.get_ident())
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, CFG_FILE)
        return True
    except OSError:
        return False


def token(create=False):
    """本机 GSI 校验用 token（防止同机其他程序乱投递）；create=True 时生成并落盘。"""
    d = load_cfg()
    tk = (d.get("token") or "").strip()
    if tk or not create:
        return tk
    tk = "%016x" % random.getrandbits(64)
    d["token"] = tk
    save_cfg(d)
    return tk


def enabled():
    """是否启用。**默认开启**（2026-11-15 用户要求）：配置里没有明确的
    enabled 键（首次运行 / 老配置文件）就按开启算；用户点过关掉会落盘
    enabled=false，之后保持关闭，尊重用户选择。"""
    d = load_cfg()
    if "enabled" in d:
        return bool(d.get("enabled"))
    return True


def set_enabled(on):
    d = load_cfg()
    d["enabled"] = bool(on)
    if on and not d.get("token"):
        d["token"] = "%016x" % random.getrandbits(64)
    save_cfg(d)
    return bool(d["enabled"])


# ─────────────────────────── CS2 安装位置 / cfg 写入 ───────────────────────────
def _library_folders():
    """Steam 库目录列表（含主目录）。解析 libraryfolders.vdf，失败就用主目录。"""
    out = []
    try:
        import current_server
        root = current_server.steam_root() or ""
    except Exception:                                          # noqa: BLE001
        root = ""
    if not root:
        return out
    out.append(root)
    vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
    try:
        txt = io.open(vdf, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return out
    shown = {os.path.normcase(os.path.abspath(x)) for x in out}
    for m in re.finditer(r'"path"\s+"([^"]+)"', txt):
        p = m.group(1).replace("\\\\", "\\")
        k = os.path.normcase(os.path.abspath(p)) if p else ""
        if p and k not in shown:
            shown.add(k)
            out.append(p)
    return out


CS2_DIRS = ("Counter-Strike Global Offensive",)


def cs2_cfg_dirs():
    """所有可能被 CS2 读取的 cfg 目录（存在才返回），按「实测可用」排序。

    CS2 不同版本/不同教程给出的路径有三种：game\\csgo\\cfg（最常用）、
    game\\cs2\\cfg、game\\core\\cfg。三个都在时就写第一个（csgo），其余存在
    的目录也一并写一份——cfg 内容完全相同，多写不会造成重复推送问题以外的
    副作用，而少写就会「装完没反应」。
    """
    out = []
    for lib in _library_folders():
        for name in CS2_DIRS:
            game = os.path.join(lib, "steamapps", "common", name, "game")
            if not os.path.isdir(game):
                continue
            for sub in ("csgo", "cs2", "core"):
                d = os.path.join(game, sub, "cfg")
                if os.path.isdir(d) and os.path.normcase(d) not in {os.path.normcase(x) for x in out}:
                    out.append(d)
    return out


def cfg_content(port, tk):
    """GSI 配置文件内容（Valve VDF）。字段尽量少：只要地图/比分/个人战况，
    不订阅 allplayers / grenades（对 ZE 用途无益，还白白多几十倍的数据量）。"""
    return (
        '"云朵小铺 · FYS ZE 通关奖励看板"\n'
        '{\n'
        '    "uri"       "http://127.0.0.1:%d/gsi"\n'
        '    "timeout"   "2.0"\n'
        '    "buffer"    "0.1"\n'
        '    "throttle"  "0.1"\n'
        '    "heartbeat" "5.0"\n'
        '    "auth"\n'
        '    {\n'
        '        "token" "%s"\n'
        '    }\n'
        '    "data"\n'
        '    {\n'
        '        "provider"             "1"\n'
        '        "map"                  "1"\n'
        '        "map_round_wins"       "1"\n'
        '        "round"                "1"\n'
        '        "player_id"            "1"\n'
        '        "player_state"         "1"\n'
        '        "player_match_stats"   "1"\n'
        '    }\n'
        '}\n' % (int(port), tk)
    )


def cfg_install(port):
    """把 cfg 写进所有找到的 CS2 cfg 目录。返回 {ok, dirs:[...], error}。

    FYS_GSI_NO_WRITE=1 时只探测目录、不真写（打包冒烟/自动化回归用，
    避免测试去改用户真实游戏目录里的文件）。
    """
    tk = token(create=True)
    dirs = cs2_cfg_dirs()
    if not dirs:
        d = load_cfg()
        d["cfg_error"] = "没找到 CS2 安装目录（Steam 库里的 Counter-Strike Global Offensive）"
        save_cfg(d)
        return {"ok": False, "dirs": [], "error": d["cfg_error"]}
    body = cfg_content(port, tk)
    if os.environ.get("FYS_GSI_NO_WRITE") == "1":
        d0 = load_cfg()
        d0["port"] = int(port)
        d0["cfg_dirs"] = list(dirs)
        d0["cfg_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        d0["cfg_at_ts"] = time.time()
        d0["cfg_error"] = ""
        save_cfg(d0)
        return {"ok": True, "dirs": dirs, "error": "", "skipped": True}
    wrote = []
    err = ""
    for d in dirs:
        try:
            fp = os.path.join(d, CFG_NAME)
            # 端口固定后内容通常不变：一样就不重写，少碰一次游戏目录里的文件
            try:
                with io.open(fp, "r", encoding="utf-8") as fh:
                    if fh.read() == body:
                        wrote.append(d)
                        continue
            except OSError:
                pass
            with io.open(fp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
            wrote.append(d)
        except OSError as e:                                   # noqa: BLE001
            err = "%s: %s" % (d, e)
    cfgd = load_cfg()
    cfgd["port"] = int(port)
    cfgd["cfg_dirs"] = wrote
    cfgd["cfg_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    cfgd["cfg_at_ts"] = time.time()
    cfgd["cfg_error"] = err
    save_cfg(cfgd)
    return {"ok": bool(wrote), "dirs": wrote, "error": err}


def cfg_remove():
    """删掉装进游戏目录的 cfg（关掉 GSI 时要真的卸载，别留个每秒推数据的配置）。"""
    removed, errs = [], []
    dirs = list(load_cfg().get("cfg_dirs") or []) + cs2_cfg_dirs()
    uniq = {}
    for d in dirs:
        uniq.setdefault(os.path.normcase(os.path.abspath(d)), d)
    for d in uniq.values():
        p = os.path.join(d, CFG_NAME)
        if not os.path.exists(p):
            continue
        try:
            os.remove(p)
            removed.append(d)
        except OSError as e:                                   # noqa: BLE001
            errs.append("%s: %s" % (p, e))
    return {"ok": not errs, "removed": removed, "error": "; ".join(errs)}


# ─────────────────────────── 状态解析 ───────────────────────────
_MAP_RE = re.compile(r"^(?:workshop/[0-9]+/)?([a-z0-9_\-]{1,124})$", re.I)


def norm_map(raw):
    """'workshop/123/ze_xxx' → 'ze_xxx'（小写）；认不出返回 ""。"""
    s = (raw or "").strip()
    m = _MAP_RE.match(s)
    return (m.group(1) if m else "").lower()


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def handle(payload, expect_token=""):
    """处理一条 GSI 推送。返回 {"ok": bool, "msg": str}（调用方只回状态码）。"""
    if not isinstance(payload, dict):
        return {"ok": False, "msg": "payload 不是对象"}
    # token 校验：**带了 auth 就必须对**；CS2 部分版本不回传 auth 字段，
    # 那种情况放行（否则会「端口收到数据却全被拒」，表现成永远「等待游戏推送」）。
    if expect_token:
        got = ((payload.get("auth") or {}).get("token") or "").strip()
        if got and got != expect_token:
            with _LOCK:
                _ST["rejects"] += 1
                _ST["last_err"] = "auth token 不匹配（收到 %s…）" % got[:6]
            return {"ok": False, "msg": "auth token 不匹配"}
        if not got:
            with _LOCK:
                _ST["noauth"] += 1

    mp = payload.get("map") or {}
    if not isinstance(mp, dict):
        mp = {}
    raw_name = mp.get("name") or ""
    name = norm_map(raw_name)
    if not name:
        with _LOCK:
            _ST["at"] = _now()
            _ST["n"] += 1
            _ST["map"] = ""
            _ST["map_raw"] = str(raw_name)[:120]
            _ST["last_err"] = "payload 没有地图名（多半在菜单/大厅）"
        _match_finalize("没有地图名")
        return {"ok": True, "msg": "菜单态"}

    ct = _int((mp.get("team_ct") or {}).get("score"))
    tt = _int((mp.get("team_t") or {}).get("score"))
    wins = mp.get("round_wins") or payload.get("round_wins") or {}
    if not isinstance(wins, dict):
        wins = {}
    rd = payload.get("round") or {}
    phase = (mp.get("phase") or (rd.get("phase") if isinstance(rd, dict) else "") or "")
    rnd = _int(mp.get("round"))

    pl = payload.get("player") or {}
    if not isinstance(pl, dict):
        pl = {}
    pst = pl.get("state") or {}
    if not isinstance(pst, dict):
        pst = {}
    pms = pl.get("match_stats") or {}
    if not isinstance(pms, dict):
        pms = {}

    with _LOCK:
        prev_map = _ST["map"]
        _ST.update({
            "at": _now(), "n": _ST["n"] + 1,
            "map": name, "map_raw": str(raw_name)[:160],
            "phase": str(phase or ""), "round": rnd,
            "ct": ct, "t": tt, "round_wins": wins,
            "name": str(pl.get("name") or ""),
            "kills": _int(pms.get("kills")), "deaths": _int(pms.get("deaths")),
            "assists": _int(pms.get("assists")), "mvps": _int(pms.get("mvps")),
            "hp": _int(pst.get("health")), "armor": _int(pst.get("armor")),
            "money": _int(pst.get("money")),
            "dmg_round": _int(pst.get("round_totaldmg")),
            "round_kills": _int(pst.get("round_kills")),
            "last_err": "",
        })
        snap = dict(_ST)
    if prev_map and prev_map != name:
        _match_finalize("换图")
    _match_tick(snap)
    if phase == "gameover":
        _match_finalize("本局结束", keep=True)
    return {"ok": True, "msg": "ok"}


def snapshot(roll=True):
    """当前状态（含推断关卡所需信息）；roll=True 时顺手收拾超时未结束的对局。"""
    if roll:
        _match_roll_stale()
    with _LOCK:
        s = dict(_ST)
    s["age"] = (time.time() - s["at"]) if s["at"] else None
    s["fresh"] = bool(s["at"] and s["age"] is not None and s["age"] <= FRESH_SEC)
    s["enabled"] = enabled()
    s["cfg"] = {k: load_cfg().get(k) for k in ("cfg_dirs", "cfg_at", "cfg_error", "port")}
    return s


def received():
    """累计收到多少条推送（诊断用）。"""
    with _LOCK:
        return int(_ST["n"])


def fresh(max_age=FRESH_SEC):
    """新鲜（在局内）时返回状态快照，否则 None。"""
    with _LOCK:
        at = _ST["at"]
        if not at or (time.time() - at) > max_age or not _ST["map"]:
            return None
        return dict(_ST)


def stage_guess(map_name, total_stages=0):
    """按 CT 比分推断当前关卡（ZE：人类每赢一回合推一关）。

    返回 (stage, source_text) 或 (None, reason)。
    · 只配了一关的图 → 直接第 1 关（与参考实现一致）；
    · 有 map_round_wins 时按「CT 赢的回合数」算，否则按 team_ct.score；
    · 结果夹在 [1, total_stages]（关卡数来自官方奖励配置，是权威上限）。
    """
    g = fresh()
    if not g or (map_name and g["map"] != map_name.lower()):
        return None, "GSI 没有当前地图"
    if total_stages == 1:
        return 1, "单关地图"
    wins = g.get("round_wins") or {}
    ct_wins = None
    if isinstance(wins, dict) and wins:
        try:
            ct_wins = sum(1 for v in wins.values() if str(v).lower() in ("ct", "3"))
        except Exception:                                      # noqa: BLE001
            ct_wins = None
    if ct_wins is None:
        ct_wins = g.get("ct")
    if ct_wins is None:
        return None, "GSI 还没给出比分"
    stage = int(ct_wins) + 1
    if total_stages and stage > total_stages:
        stage = total_stages
    return stage, "按 CT 比分推断（%s 胜 %d 回合）" % ("CT", int(ct_wins))


# ─────────────────────────── 对局战绩 ───────────────────────────
def _matches_read():
    try:
        with io.open(MATCH_FILE, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        rows = d.get("rows") if isinstance(d, dict) else d
        return list(rows or [])
    except (OSError, ValueError):
        return []


def _matches_write(rows):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = "%s.%d.tmp" % (MATCH_FILE, threading.get_ident())
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"rows": rows}, fh, ensure_ascii=False)
        os.replace(tmp, MATCH_FILE)
        return True
    except OSError:
        return False


_CUR = None          # 正在进行的这一局
_FINAL_GUARD = set()  # 已按「本局结束」结算过的 (map, ct, t)，防 gameover 反复推送重复记


def _match_tick(s):
    """每条推送都调：起局 / 累计回合最高伤害 / 更新统计峰值。"""
    global _CUR
    m = s.get("map")
    if not m:
        return
    with _LOCK:
        cur = _CUR
        if cur is None or cur["map"] != m:
            cur = _CUR = {
                "map": m, "start": time.time(), "end": None,
                "stage": None, "rounds": 0,
                "dmg": 0, "dmg_by_round": {}, "max_round": 0,
                "kills": 0, "deaths": 0, "assists": 0, "mvps": 0,
                "ct": s.get("ct"), "t": s.get("t"),
                "phase": s.get("phase"),
            }
        cur["end"] = time.time()
        cur["phase"] = s.get("phase") or cur["phase"]
        if s.get("ct") is not None:
            cur["ct"] = s["ct"]
        if s.get("t") is not None:
            cur["t"] = s["t"]
        rnd = s.get("round")
        if rnd:
            cur["max_round"] = max(cur["max_round"], int(rnd))
        # 本回合伤害：同回合取 max（round_totaldmg 回合结束清零，不是累加值）
        d = s.get("dmg_round")
        if d is not None and rnd is not None:
            key = str(rnd)
            prev = cur["dmg_by_round"].get(key, 0)
            if d > prev:
                cur["dmg_by_round"][key] = d
        for k in ("kills", "deaths", "assists", "mvps"):
            v = s.get(k)
            if v is not None and v > cur[k]:
                cur[k] = v


def _match_sum_dmg(cur):
    return int(sum(cur.get("dmg_by_round", {}).values()))


def _match_finalize(reason="", keep=False):
    """把当前这局写成一条战绩。keep=True 时保留（gameover 后同图继续推送不重复记）。"""
    global _CUR
    with _LOCK:
        cur = _CUR
        if not cur:
            return None
        rounds = max(cur.get("max_round") or 0, len(cur.get("dmg_by_round") or {}))
        # 抖动过滤：换图瞬间会连着刷几条（回合 0 / 几十毫秒就换图），别记成「一局」；
        # 打满 2 回合以上的短局（速推图）照样要记。
        if rounds < 1 or ((cur["end"] - cur["start"]) < 20 and rounds < 2):
            _CUR = None
            return None
        rec = {
            "map": cur["map"],
            "start": int(cur["start"]), "end": int(cur["end"]),
            "dur": int(cur["end"] - cur["start"]),
            "rounds": int(rounds),
            "ct": cur.get("ct"), "t": cur.get("t"),
            "kills": int(cur.get("kills") or 0),
            "deaths": int(cur.get("deaths") or 0),
            "assists": int(cur.get("assists") or 0),
            "mvps": int(cur.get("mvps") or 0),
            "dmg": _match_sum_dmg(cur),
            "stage": cur.get("stage"),
            "why": reason,
        }
        _CUR = None
    rows = _matches_read()
    # 同一局重复结算保护（gameover 会连续推好几条）
    sig = (rec["map"], rec["start"] // 60)
    if sig in _FINAL_GUARD:
        return None
    _FINAL_GUARD.add(sig)
    rows.insert(0, rec)
    _matches_write(rows[:MATCH_MAX])
    return rec


def _match_roll_stale():
    """长时间没推送（关游戏/退了服务器）→ 把残局落盘，不然战绩永远停在「进行中」。"""
    with _LOCK:
        cur = _CUR
        if not cur:
            return
        last = cur.get("end") or 0
        if last and (time.time() - last) > STALE_SEC:
            pass
        else:
            return
    _match_finalize("长时间无推送")


def current_match():
    """当前正在进行的这一局（给覆盖窗显示「本局伤害 / K-D-A」）。
    没有对局时返回 None；伤害是「每回合峰值累加」的口径（见 _match_tick）。"""
    with _LOCK:
        cur = _CUR
        if not cur:
            return None
        rounds = max(cur.get("max_round") or 0, len(cur.get("dmg_by_round") or {}))
        return {
            "map": cur["map"],
            "start": int(cur["start"]),
            "rounds": int(rounds),
            "dmg": _match_sum_dmg(cur),
            "kills": int(cur.get("kills") or 0),
            "deaths": int(cur.get("deaths") or 0),
            "assists": int(cur.get("assists") or 0),
            "ct": cur.get("ct"), "t": cur.get("t"),
            "stage": cur.get("stage"),
        }


def match_set_stage(stage):
    """由 resolve() 回填当前这局的关卡号（广播或推断结果）。"""
    with _LOCK:
        if _CUR is not None and stage is not None:
            try:
                _CUR["stage"] = int(stage)
            except (TypeError, ValueError):
                pass


def matches(limit=60):
    """战绩列表（新→旧），带奖励参数联动列。

    联动口径（来自官方 rewards 配置，不做任何猜测换算）：
      · 通关云点 / 通关龙晶  —— 该图该关的标准奖励
      · 云点伤害比 / 龙晶伤害比 —— 「伤害 : 1 点货币」的分母
      · 按本局累计伤害推算的伤害兑换额 floor(伤害 / 分母)，标 est=True
    """
    rows = _matches_read()
    try:
        import reward_server as R
    except Exception:                                          # noqa: BLE001
        R = None
    out = []
    for r in rows[:limit]:
        item = dict(r)
        cfg = None
        stg = r.get("stage")
        if R is not None:
            try:
                cfg, _hit, _approx = R.reward_of(r.get("map") or "")
            except Exception:                                  # noqa: BLE001
                cfg = None
        if R is not None:
            try:
                item["mapcn"] = R.mapcn_of(r.get("map") or "")
            except Exception:                                  # noqa: BLE001
                pass
        if isinstance(cfg, dict) and cfg:
            stage_row = None
            if stg is not None:
                stage_row = cfg.get(str(stg)) or cfg.get(stg)
            if not isinstance(stage_row, dict) and len(cfg) == 1:
                stage_row = list(cfg.values())[0]
                item["stage"] = list(cfg.keys())[0]
            if isinstance(stage_row, dict):
                rp = stage_row.get("rankPasses")
                ep = stage_row.get("econPasses")
                rdmg = stage_row.get("rankDamage")
                edmg = stage_row.get("econDamage")
                item["reward"] = {"rankPasses": rp, "econPasses": ep,
                                  "rankDamage": rdmg, "econDamage": edmg}
                dmg = int(r.get("dmg") or 0)
                est = {}
                if isinstance(rdmg, int) and rdmg > 0:
                    est["rankDmgPts"] = dmg // rdmg
                if isinstance(edmg, int) and edmg > 0:
                    est["econDmgPts"] = dmg // edmg
                if est:
                    item["est"] = est
        out.append(item)
    return out


def summary():
    rows = _matches_read()
    tot_dmg = sum(int(r.get("dmg") or 0) for r in rows)
    by_map = {}
    for r in rows:
        m = r.get("map") or "?"
        by_map[m] = by_map.get(m, 0) + 1
    return {"count": len(rows), "total_dmg": tot_dmg,
            "maps": len(by_map),
            "last": rows[0]["end"] if rows else None}


def status_payload():
    """给前端的 GSI 状态卡：连接情况 + 当前对局 + 关卡推断 + cfg 安装位置。"""
    s = snapshot()
    total = 0
    try:
        import reward_server as R
        cfg, _hit, _a = R.reward_of(s.get("map") or "")
        total = len(cfg) if isinstance(cfg, dict) else 0
    except Exception:                                          # noqa: BLE001
        total = 0
    guess, why = (None, "")
    if s.get("map"):
        guess, why = stage_guess(s["map"], total)
    return {
        "ok": True,
        "enabled": s["enabled"],
        "connected": bool(s["fresh"]),
        "age": None if s["age"] is None else round(s["age"], 1),
        "received": s["n"],
        "map": s["map"] or None,
        "map_raw": s["map_raw"] or None,
        "phase": s["phase"] or None,
        "round": s["round"],
        "score": {"ct": s["ct"], "t": s["t"]},
        "kills": s["kills"], "deaths": s["deaths"],
        "assists": s["assists"], "mvps": s["mvps"],
        "dmg_round": s["dmg_round"],
        "stage_guess": guess,
        "stage_why": why,
        "total_stages": total,
        "cfg": s["cfg"],
        "rejected": s["rejects"],
        "noauth": s["noauth"],
        "cs2": cs2_status(),
        "cfg_file_at": (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(_mt))
                        if (_mt := _cfg_mtime()) else None),
        "need_restart": _need_restart(cs2_status(), _cfg_mtime()),
        "error": s["last_err"] or None,
    }


def _proc_start(pid):
    """进程启动时间（unix 秒）。拿不到返回 None。"""
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))     # QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            c = ctypes.c_ulonglong(); e = ctypes.c_ulonglong()
            kt = ctypes.c_ulonglong(); ut = ctypes.c_ulonglong()
            if not k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                     ctypes.byref(kt), ctypes.byref(ut)):
                return None
            return (c.value / 1e7) - 11644473600.0     # FILETIME → unix
        finally:
            k.CloseHandle(h)
    except Exception:                                          # noqa: BLE001
        return None


def cs2_status():
    """CS2 是否在跑 / 什么时候启动的（判断「配置写得比游戏启动晚」用）。"""
    try:
        import current_server as C
        pids = C.cs2_pids()
    except Exception:                                          # noqa: BLE001
        return {"running": None, "started": None, "pid": None}
    if not pids:
        return {"running": False, "started": None, "pid": None}
    return {"running": True, "started": _proc_start(pids[0]), "pid": pids[0]}


def _cfg_mtime():
    """已装进游戏目录那份 cfg 的修改时间（可能有多份，取最新的）。没有返回 None。"""
    mt = None
    for d in (load_cfg().get("cfg_dirs") or []) + cs2_cfg_dirs():
        try:
            t = os.path.getmtime(os.path.join(d, CFG_NAME))
        except OSError:
            continue
        mt = t if mt is None else max(mt, t)
    return mt


def _need_restart(cs2, cfg_at):
    """配置是不是写在「这次游戏启动之后」——是的话本次会话不会加载，必须重启 CS2。"""
    try:
        if not cs2.get("running") or not cs2.get("started") or not cfg_at:
            return False
        return float(cfg_at) > float(cs2["started"])
    except (TypeError, ValueError):
        return False

# -*- coding: utf-8 -*-
r"""把「地图库有、预览壳没有」的地图追加进实体预览 payload。

背景
----
预览壳（地图实体预览-3D视图.html）的地图数据来自 fyscs/MapTracking-CS2 归档
（StarDance 实体 dump，只有 345 张图目录 / 645 条记录 = 548 张 ze）。
地图库里另有 153 张图不在这份归档里 → 预览页根本列不出它们（用户报的「鬼泣」就是）。

这些图我们绕过归档自己补：steamcmd 匿名下载工坊包 → 解析 vpk 内的
   maps/<name>/entities/*.vents_c（二进制 KV3，实体 + m_connections）
   maps/<name>/world_physics.vmdl_c（真实碰撞地形）
产物落在 E:\FYS-cache\_ents_raw\<工坊ID>.json 与 _meshes_raw\<工坊ID>.bin.gz
（格式与 _build_meshes.py 一致）。本脚本负责把实体部分**追加**进 payload 的
maps 字典，条目字段与 _build_preview_data.py 写出的完全同构：

    m/i/a/f/d/g/n/k/h/b/fb/c/t/st/cn/lib/e/A/C/bg

其余字段由后续步骤补齐：
    zq       ← _inject3d.py（高度分位）
    bb/bbm   ← _inject3d.py（从 _ents_raw 匹配精确包围盒）
    wm/wf/wb ← _inject3d.py（从 _meshes/_manifest.json 取地形分包）

用法
----
    python _add_missing_maps.py --check              # 预检：报告将追加哪些图
    python _add_missing_maps.py --apply              # 实际写入 preview_payload.b64
    python _add_missing_maps.py --apply --refresh     # 重建已追加过的图（补属性/连接）

`--refresh` 用于后续拿到「完整实体」（含 kv 属性 + m_connections 连接）后重灌：
对 payload 里已存在的补图条目按图名定位并替换，同时沿用旧底图记录，避免
BINS 里重复堆同一张位图。全局池（classes/kp/op/ip/tp/pp）本身带去重，不会膨胀。

写入后按顺序跑：
    FYS_TRACKING_B64=<本 payload> python _ghcrawl/_build_meshes.py --repack
    python _ghcrawl/_inject3d.py
    python _patch_preview_names.py --apply
    python _sync_preview.py
（以上 5 步已封装为 `python _rebuild_preview.py`）
"""
import base64
import collections
import gzip
import io
import json
import math
import os
import re
import struct
import sys
import time

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
GH = os.path.join(ROOT, "fys-reward", "_ghcrawl")
B64 = os.path.join(GH, "preview_payload.b64")
FDIR = os.path.join(ROOT, "fys-reward")
DATA = os.path.join(FDIR, "data")
WS_JSON = os.environ.get("FYS_WS_JSON") or os.path.join(FDIR, "_missing_ws_all.json")
ENTS_DIR = os.environ.get("FYS_ENTS_DIR") or r"E:\FYS-cache\_ents_raw"

APPID = "2001"                      # payload 里所有 ze 图都在 2001 组
GEN = "自建提取（steamcmd 匿名下载 + vents_c/KV3 解析）"

# ---------------------------------------------------------------- 分组规则
# 必须与 _build_preview_data.py 的 GROUPS/RULES 保持一致，
# 否则新图的图层面板分类、侧栏统计、3D 配色都会和原 548 张对不上。
GROUPS = [
    ("tele", "传送门 / 落点", "#7c3aed", 1.35, True),
    ("break", "可破坏物", "#f59e0b", 1.30, True),
    ("hurt", "危险区 / 火焰", "#ef4444", 1.25, True),
    ("trig", "触发区", "#14b8a6", 1.15, True),
    ("mech", "机关 / 门", "#0ea5e9", 1.15, True),
    ("path", "路径点 / 逃跑线", "#84cc16", 1.00, True),
    ("spawn", "出生点", "#22c55e", 1.10, False),
    ("logic", "逻辑节点", "#ec4899", 0.95, False),
    ("item", "武器 / 道具", "#eab308", 0.95, False),
    ("prop", "动态模型", "#64748b", 0.95, False),
    ("env", "环境点（地形轮廓）", "#b9bec9", 0.80, True),
    ("misc", "其他", "#9ca3af", 0.90, False),
]

RULES = [
    ("tele", ["trigger_teleport", "trigger_teleport_relative", "point_teleport",
              "info_teleport_destination", "trigger_teleport_autocancel"]),
    ("break", ["func_breakable", "func_breakable_surf", "func_physbox", "prop_physics",
               "prop_physics_multiplayer", "prop_physics_override",
               "prop_physics_multiplayer_override", "func_brush_breakable"]),
    ("hurt", ["trigger_hurt", "env_fire", "env_explosion", "trigger_ignite",
              "trigger_waterydeath"]),
    ("trig", ["trigger_once", "trigger_multiple", "trigger_push", "func_buyzone",
              "trigger_brush", "trigger_wind", "trigger_look", "trigger_*",
              "func_ladder", "func_illusionary"]),
    ("mech", ["func_button", "func_door", "func_door_rotating", "prop_door_rotating",
              "func_movelinear", "func_rotating", "func_wall_toggle", "func_tracktrain",
              "phys_thruster", "func_water", "func_brush", "func_wall", "func_*"]),
    ("path", ["path_track", "path_corner", "func_trackautochange", "path_*"]),
    ("logic", ["logic_relay", "logic_case", "logic_timer", "logic_branch", "logic_auto",
               "logic_compare", "logic_measure_movement", "logic_collision_pair",
               "logic_multiple", "logic_script", "math_counter", "math_remap", "math_*",
               "point_template", "env_entity_maker", "point_servercommand",
               "game_player_equip", "logic_*", "point_*"]),
    ("spawn", ["info_player_terrorist", "info_player_counterterrorist",
               "info_player_start", "info_player_teamspawn", "info_player_*"]),
    ("item", ["weapon_*", "item_*", "game_*"]),
    ("prop", ["prop_*", "prop_dynamic", "prop_static", "prop_ragdoll"]),
    ("env", ["light_*", "info_particle_system", "env_particle_glow",
             "env_combined_light_probe_volume", "env_light_probe_volume",
             "env_cubemap_box", "point_soundevent", "ambient_generic", "env_soundscape",
             "env_soundscape_proxy", "snd_event_point", "env_sky",
             "post_processing_volume", "path_particle_rope_clientside", "cable_dynamic",
             "point_worldtext", "env_fade", "env_shake", "env_hudhint", "game_text",
             "info_target", "worldspawn", "cs_minimap_boundary", "func_clip_vphysics",
             "filter_*", "env_*", "info_*", "water_lod_control", "sky_camera",
             "shadow_control", "color_correction"]),
]
MID2GID = {}
for _gid, _pats in RULES:
    for _p in _pats:
        MID2GID.setdefault(_p, _gid)
NAMED_GIDS = {"tele", "break", "mech", "hurt", "trig", "path"}
CONN_GIDS = {"tele", "break", "mech", "hurt", "trig", "path", "logic"}
ENV_CAP = 90
GID_ORDER = [g[0] for g in GROUPS]

# 源键名 → 短名（与 _build_preview_data.ATTR_WANT 完全一致，顺序也一致）
ATTR_WANT = [
    ("damage", "damage"), ("damagecap", "dmgcap"), ("damagetype", "dmgtype"),
    ("damagemodel", "dmgmodel"), ("damagescale", "dmgscale"), ("Damage", "damage"),
    ("DamageDelay", "dmgdelay"), ("DamageType", "dmgtype"), ("DamageRadius", "dmgrad"),
    ("health", "hp"), ("target", "target"), ("filtername", "filter"),
    ("filterclass", "filtercls"), ("Negated", "negated"), ("speed", "speed"),
    ("wait", "wait"), ("dmg", "dmg"), ("spawnflags", "flags"),
    ("StartDisabled", "startoff"), ("ExplodeDamage", "expldmg"),
    ("ExplodeRadius", "explr"), ("iMagnitude", "magnitude"),
    ("iRadiusOverride", "magradius"), ("delay", "delay"), ("MinDelay", "mindelay"),
    ("MaxDelay", "maxdelay"), ("landmark", "landmark"),
    ("UseLandmarkAngles", "useLandmarkAngles"),
    ("CheckDestIfClearForPlayer", "checkDestClear"), ("triggeronstarttouch", "trigOnStart"),
    ("radius", "radius"), ("filterattribute", "filterAttr"),
]

NUM_RE = re.compile(r"-?\d+(\.\d+)?$")

# ---------------------------------------------------------------- 底图（密度轮廓）
RES = 128


def density_grid(pts, bounds, res=RES):
    x0, y0, _, x1, y1, _ = bounds
    gx0, gx1 = min(x0, x1), max(x0, x1)
    gy0, gy1 = min(y0, y1), max(y0, y1)
    w = (gx1 - gx0) or 1
    h = (gy1 - gy0) or 1
    grid = [0.0] * (res * res)
    n = 0
    for p in pts:
        ix = int((p[0] - gx0) / w * res)
        iy = int((p[1] - gy0) / h * res)
        if 0 <= ix < res and 0 <= iy < res:
            grid[iy * res + ix] += 1
            n += 1
    return grid if n >= 40 else None


def blur_sep(grid, res, r=2, rounds=2):
    cur = grid
    for _ in range(rounds):
        tmp = [0.0] * (res * res)
        win = 2 * r + 1
        for y in range(res):
            row = cur[y * res:(y + 1) * res]
            s = sum(row[:win])
            for x in range(res):
                tmp[y * res + x] = s
                if x - r >= 0:
                    s -= row[x - r]
                if x + r + 1 < res:
                    s += row[x + r + 1]
        out = [0.0] * (res * res)
        for x in range(res):
            s = sum(tmp[y * res + x] for y in range(win))
            for y in range(res):
                out[y * res + x] = s
                if y - r >= 0:
                    s -= tmp[(y - r) * res + x]
                if y + r + 1 < res:
                    s += tmp[(y + r + 1) * res + x]
        cur = out
    return cur


def quantize_bg(grid, res=RES):
    if not grid:
        return None
    nz = sorted(v for v in grid if v > 0)
    if len(nz) < 30:
        return None
    lo = nz[int(len(nz) * 0.12)]
    hi = nz[min(len(nz) - 1, int(len(nz) * 0.995))]
    rng = (hi - lo) or 1.0
    out = bytearray(res * res // 4)
    for i, v in enumerate(grid):
        if v <= 0:
            continue
        t = (v - lo) / rng
        lv = 1 if t <= 0.12 else (2 if t <= 0.48 else 3)
        out[i >> 2] |= lv << ((i & 3) * 2)
    return bytes(out)


def clean_num(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, str):
        v = v.strip()
        if NUM_RE.match(v):
            try:
                f = float(v)
                return int(f) if f == int(f) else f
            except Exception:                                  # noqa: BLE001
                pass
        return v[:64]
    if isinstance(v, float):
        return int(v) if v == int(v) else round(v, 3)
    return v


def match_gid(cn):
    g = MID2GID.get(cn)
    if g:
        return g
    for key, gid in MID2GID.items():
        if key.endswith("*") and cn.startswith(key[:-1]):
            return gid
    return "misc"


# ---------------------------------------------------------------- payload 读写
def load_payload(path):
    raw = io.open(path, encoding="ascii").read().strip()
    packed = gzip.decompress(base64.b64decode(raw))
    jlen = struct.unpack_from("<I", packed, 0)[0]
    data = json.loads(packed[4:4 + jlen])
    bins = bytearray(packed[4 + jlen:])
    return data, bins


def save_payload(path, data, bins):
    jb = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = struct.pack("<I", len(jb)) + jb + bytes(bins)
    b64 = base64.b64encode(gzip.compress(packed, 9)).decode("ascii")
    tmp = path + ".tmp"
    io.open(tmp, "w", encoding="ascii").write(b64)
    os.replace(tmp, path)
    return len(jb), len(bins), len(b64)


# ---------------------------------------------------------------- 单图条目构建
class Builder(object):
    """持有可变的全局池（classes / kp / op / ip / tp / pp）与 BINS。"""

    def __init__(self, data, bins, rewards, lib):
        self.data = data
        self.bins = bins
        self.rewards = rewards
        self.lib = lib
        self.CLS = data["classes"]
        self.CLS_IDX = {c: i for i, c in enumerate(self.CLS)}
        self.KP = data["kp"]
        self.KP_IDX = {k: i for i, k in enumerate(self.KP)}
        self.OP = data["op"]
        self.OP_IDX = {k: i for i, k in enumerate(self.OP)}
        self.IP = data["ip"]
        self.IP_IDX = {k: i for i, k in enumerate(self.IP)}
        self.TP = data["tp"]
        self.TP_IDX = {k: i for i, k in enumerate(self.TP)}
        self.PP = data["pp"]
        self.PP_IDX = {k: i for i, k in enumerate(self.PP)}

    @staticmethod
    def _pool(lst, idx, name):
        i = idx.get(name)
        if i is None:
            i = len(lst)
            idx[name] = i
            lst.append(name)
        return i

    def build(self, name, pid, ents, reuse_bg=None):
        """ents = [{cn,o,nm,uid,(c,h),(kv),(cx)}, ...]（_build_meshes 的输出）
        reuse_bg：刷新时沿用旧条目的底图记录，避免往 BINS 里重复追加同一张位图。"""
        buckets = collections.defaultdict(list)
        classcnt = collections.Counter()
        for e in ents:
            cn = (e.get("cn") or "").strip()
            o = e.get("o")
            if not cn or not o:
                continue
            classcnt[cn] += 1
            buckets[match_gid(cn)].append((o, cn, (e.get("nm") or "").strip(), e))

        # 环境点抽样（与 _build_preview_data 同规则）
        env_all = [v[0] for v in (buckets.get("env") or [])]
        envl = buckets.get("env") or []
        hidden = 0
        if len(envl) > ENV_CAP:
            step = int(math.ceil(len(envl) / float(ENV_CAP)))
            buckets["env"] = [v for j, v in enumerate(envl) if j % step == 0]
            hidden = len(envl) - len(buckets["env"])

        core = [v[0] for gid, lst in buckets.items() if gid != "env" for v in lst]
        if not core:
            core = [v[0] for lst in buckets.values() for v in lst]
        if not core:
            return None
        sx = sorted(v[0] for v in core)
        sy = sorted(v[1] for v in core)
        sz = sorted(v[2] for v in core)

        def q(arr, r):
            return int(round(arr[max(0, min(len(arr) - 1, int(len(arr) * r)))]))

        bounds = [q(sx, .005), q(sy, .005), q(sz, .005), q(sx, .995), q(sy, .995), q(sz, .995)]
        full = [int(round(sx[0])), int(round(sy[0])), int(round(sz[0])),
                int(round(sx[-1])), int(round(sy[-1])), int(round(sz[-1]))]

        out_ents = []
        gc = {}
        attr_recs = []
        conn_recs = []
        for gid in GID_ORDER:
            lst = buckets.get(gid)
            if not lst:
                continue
            gc[gid] = len(lst)
            minlen = 1 if gid in NAMED_GIDS else 99
            for (x, y, z), cn, tn, raw_e in lst:
                ci = self.CLS_IDX.get(cn)
                if ci is None:
                    ci = len(self.CLS)
                    self.CLS_IDX[cn] = ci
                    self.CLS.append(cn)
                nm = tn[:26] if (len(tn) >= minlen and len(tn) <= 26) else None
                rec = [int(round(x)), int(round(y)), int(round(z)), ci]
                if nm:
                    rec.append(nm)
                ai = gi = -1
                if gid in CONN_GIDS:
                    seen_short = set()
                    a = []
                    kv = raw_e.get("kv") or {}
                    for src, short in ATTR_WANT:
                        if short in seen_short or src not in kv:
                            continue
                        v = kv[src]
                        if v is None or v == "" or isinstance(v, (list, dict)):
                            continue
                        v = clean_num(v)
                        if v == "" or v is None:
                            continue
                        seen_short.add(short)
                        a.append((self._pool(self.KP, self.KP_IDX, short), v))
                    if a:
                        enc = ";".join(
                            "%d=%s" % (k, str(v).replace("=", "：").replace(";", "，")
                                       .replace("|", "/")) for k, v in a)
                        ai = len(attr_recs)
                        attr_recs.append(enc)
                    cs = []
                    for c in (raw_e.get("cx") or []):
                        if not isinstance(c, dict):
                            continue
                        p = str(c.get("p") or "")
                        cs.append((self._pool(self.OP, self.OP_IDX, str(c.get("o") or "")[:24]),
                                   str(c.get("t") or "")[:32],
                                   self._pool(self.IP, self.IP_IDX, str(c.get("i") or "")[:24]),
                                   p[:40], clean_num(c.get("d", 0))))
                    if cs:
                        enc = "\n".join(
                            "%d|%d|%d|%d|%s" % (o, self._pool(self.TP, self.TP_IDX, t), i,
                                                self._pool(self.PP, self.PP_IDX, p) if p else -1,
                                                d)
                            for o, t, i, p, d in cs)
                        gi = len(conn_recs)
                        conn_recs.append(enc)
                if ai >= 0:
                    rec.append(ai)
                if gi >= 0:
                    rec.append(gi)
                out_ents.append(rec)

        # 底图：环境点密度轮廓（2bit/像素）
        bg_rec = reuse_bg
        if bg_rec is None:
            try:
                g = density_grid(env_all, bounds)
                if g:
                    g = blur_sep(g, RES)
                    qq = quantize_bg(g, RES)
                    if qq:
                        bg_rec = [len(self.bins), len(qq)]
                        self.bins.extend(qq)
            except Exception:                                  # noqa: BLE001
                bg_rec = None

        return {
            "m": name, "i": name, "a": APPID, "f": str(pid),
            "d": "", "g": GEN,
            "n": len(ents), "k": len(out_ents), "h": hidden,
            "b": bounds, "fb": full,
            "c": gc,
            "t": [[c, n] for c, n in classcnt.most_common(14)],
            "st": len(self.rewards.get(name) or {}),
            "cn": "",
            "lib": 1 if name in self.lib else 0,
            "e": out_ents,
            "bg": bg_rec,
            "rb": None, "rbb": None,
            "A": attr_recs,
            "C": conn_recs,
        }


def main():
    apply = "--apply" in sys.argv
    refresh = "--refresh" in sys.argv      # 重建已追加过的图（用于补齐属性/连接）
    t0 = time.time()
    data, bins = load_payload(B64)
    maps = data["maps"]
    print("payload: maps=%d classes=%d BINS=%.2f MB"
          % (len(maps), len(data["classes"]), len(bins) / 1048576))
    if refresh:
        print("模式：--refresh（已存在的补图条目将被重建，底图记录沿用不重复占位）")

    existing = {v.get("m") for v in maps.values()}
    have_pid = {k.split("/")[-1] for k in maps}
    # 图名 → payload 键（刷新时用它定位要替换的条目）
    key_by_name = {}
    for k, v in maps.items():
        key_by_name.setdefault(v.get("m"), k)
    # 工坊 ID → 预览里已有的图名（用于解释「同图异名」跳过）
    payload_by_pid = {}
    for v in maps.values():
        payload_by_pid.setdefault((v.get("f") or ""), v.get("m"))
    added_by_pid = {}

    if not os.path.exists(WS_JSON):
        print("！缺少 %s" % WS_JSON)
        return 1
    ws = json.load(io.open(WS_JSON, encoding="utf-8"))

    todo, nodata = [], []
    for name, pid in sorted(ws.items()):
        p = os.path.join(ENTS_DIR, str(pid) + ".json")
        if name in existing:
            if not refresh:
                continue
            if not os.path.exists(p):
                continue          # 没有新产物可刷，保持原样
            todo.append((name, str(pid), p, True))
            continue
        if not os.path.exists(p):
            nodata.append((name, pid))
            continue
        todo.append((name, str(pid), p, False))

    n_ref = sum(1 for t in todo if t[3])
    print("待追加 %d 张（其中刷新存量 %d 张）| 无实体产物 %d 张 | 已在 payload %d 张"
          % (len(todo), n_ref, len(nodata),
             len(ws) - len(todo) - len(nodata)))
    if nodata:
        for n, p in nodata:
            print("    缺数据 %-42s %s" % (n, p))

    rewards_path = os.path.join(DATA, "rewards.json")
    lib_path = os.path.join(DATA, "maps.json")
    rewards = json.load(io.open(rewards_path, encoding="utf-8")) \
        if os.path.exists(rewards_path) else {}
    lib = json.load(io.open(lib_path, encoding="utf-8")) \
        if os.path.exists(lib_path) else {}

    bd = Builder(data, bins, rewards, lib)
    added, skipped = [], []
    n_new = 0
    for name, pid, path, is_ref in todo:
        try:
            ents = json.load(io.open(path, encoding="utf-8"))
        except Exception as ex:                                # noqa: BLE001
            skipped.append((name, "解析失败 %s" % ex))
            continue
        if not ents:
            skipped.append((name, "实体为空"))
            continue
        key = key_by_name.get(name) if is_ref else None
        if is_ref and not key:
            is_ref = False                                     # 找不到旧键，退化为新增
        # 同一工坊 ID 被两个图名共用（如 ze_lotr_minas_tirith / _p / _cs2）：
        # 预览里已有这张图，只是叫工坊原名的那个。中文名一致，搜中文名同样找得到，
        # 不再复制一份同数据异名条目（会让列表出现两张一模一样的图）。
        if not is_ref and pid in have_pid:
            other = payload_by_pid.get(pid) or added_by_pid.get(pid) or "?"
            skipped.append((name, "同图异名：工坊 ID %s 在预览里已叫 %s" % (pid, other)))
            continue
        reuse = maps.get(key, {}).get("bg") if is_ref else None
        rec = bd.build(name, pid, ents, reuse_bg=reuse)
        if not rec:
            skipped.append((name, "构建结果为空"))
            continue
        tgt = key if is_ref else "%s/%s/%s" % (APPID, name, pid)
        if tgt not in maps:
            n_new += 1
            have_pid.add(pid)
            added_by_pid[pid] = name
        maps[tgt] = rec
        added.append((name, pid, rec))
        if len(added) % 20 == 0:
            print("  … 已构建 %d/%d（%.0fs）" % (len(added), len(todo), time.time() - t0),
                  flush=True)

    print("\n== 结果 ==")
    print("处理 %d 张（新增 %d / 刷新 %d）| 跳过 %d 张"
          % (len(added), n_new, len(added) - n_new, len(skipped)))
    for name, why in skipped:
        print("    跳过 %-42s %s" % (name, why))
    for name, pid, rec in added[:12]:
        print("    %-40s %s  实体 %5d（保留 %5d） 属性 %d 连接 %d bg=%s"
              % (name, pid, rec["n"], rec["k"], len(rec["A"]), len(rec["C"]),
                 "有" if rec["bg"] else "无"))
    if len(added) > 12:
        print("    … 其余 %d 张略" % (len(added) - 12))

    # meta 同步
    meta = data.setdefault("meta", {})
    meta["maps"] = len(maps)
    meta["entities_all"] = sum(v.get("n") or 0 for v in maps.values())
    meta["entities_kept"] = sum(v.get("k") or 0 for v in maps.values())
    meta["entities_hidden"] = sum(v.get("h") or 0 for v in maps.values())
    meta["classes"] = len(data["classes"])
    meta["bg_density"] = sum(1 for v in maps.values() if v.get("bg"))
    meta["filled"] = meta.get("filled", 0) + n_new
    meta["filled_note"] = ("其中 %d 张为「地图库有、官方归档没有」的图，"
                           "由本地工坊包自行提取（实体/地形/属性/连接与其余图同源同构）"
                           % meta["filled"])

    jb, nb, b64 = save_payload(B64, data, bins) if apply else (0, len(bins), 0)
    print("\nJSON %.2f MB + BINS %.2f MB → base64 %s"
          % ((len(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
              / 1048576), nb / 1048576,
             ("%.2f MB" % (b64 / 1048576)) if apply else "（未写）"))
    print("最终地图数 %d（非 ze %d 张待 _patch_preview_names.py 过滤）"
          % (len(maps), sum(1 for v in maps.values()
                            if not (v.get("m") or "").lower().startswith("ze_"))))
    if apply:
        print("已写入 %s" % B64)
    else:
        print("\n== 预检完成，未写入（加 --apply 实际写入）==")
    print("用时 %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

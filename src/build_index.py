# -*- coding: utf-8 -*-
"""
風雲社 CS2 配置索引构建器
--------------------------------------------------
从 GitHub 一次性打包下载 fyscs/cs2，抽取 rewards(通关奖励) 与 maps(地图数据)，
以及 map-configs(每张图的官方 ConVar 配置，含尸变参数)，解析成扁平 JSON 缓存在
data/ 下，供实时查询使用。

不消耗 GitHub API 配额（下载的是仓库归档包，1 次请求）。

用法：
    python build_index.py            # 增量：缓存新鲜就跳过
    python build_index.py --force    # 强制重新拉取
"""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
import time
import urllib.request

REPO_TARBALL = "https://codeload.github.com/fyscs/cs2/tar.gz/refs/heads/master"
# 同内容的备用地址（github.com 会 302 到 codeload，两者出口不同，偶尔一条通一条断）
REPO_TARBALL2 = "https://github.com/fyscs/cs2/archive/refs/heads/master.tar.gz"
# 国内镜像（可选）：曾由自建服务器定时同步归档包后缓存。
# **v2.14 起服务器停用 → 默认为空，直接走官方源**（实测 codeload 约 900KB/s，
# 1.7MB 归档 2 秒下完，不需要中转）。将来若又有镜像，设 FYS_REPO_MIRROR 即可。
REPO_MIRROR = os.environ.get("FYS_REPO_MIRROR", "").strip()
ROOT_TAG = "cs2-master/"          # 归档包内的一级目录（⚠ 只对 master 归档成立）

# ⚠ 一级目录名会随下载方式变：refs/heads/master → `cs2-master`，按提交 sha 下载
# → `cs2-<sha>`。所以归档内一律先剥掉第一段再匹配（2026-10-01 用父提交归档
# 复盘历史时踩到：按 ROOT_TAG 匹配旧侧全空 → 整库被判成「新增 699 张图」）。
def relpath_of(name):
    """归档内路径 → 去掉根目录的相对路径（无根时原样返回）。"""
    return name.split("/", 1)[1] if "/" in name else name


def app_dir():
    """打包成 exe 后，缓存要放在 exe 旁边，而不是临时解包目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = app_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
REWARDS_OUT = os.path.join(DATA_DIR, "rewards.json")
MAPS_OUT = os.path.join(DATA_DIR, "maps.json")
# 本地补充层：官方仓库里没有、由本地维护的地图条目（样板图 / 新图入库）。
# 官方索引每次同步都整体覆盖 maps.json / rewards.json，本地加的条目必须
# 放这两个文件里才不会丢；build() 写盘前把它们并回去（官方数据优先）。
MAPS_LOCAL = os.path.join(DATA_DIR, "maps_local.json")
REWARDS_LOCAL = os.path.join(DATA_DIR, "rewards_local.json")
META_OUT = os.path.join(DATA_DIR, "meta.json")
INFECT_OUT = os.path.join(DATA_DIR, "infect.json")
# 每图 cfg 的**全量** ConVar（31 项）。infect.json 只留「尸变」4 项给界面用，
# 官方提交里「修改地图参数」改的却是任意一项（如 ze_cash_damage_zombie），
# 只盯 4 项会整类漏报 —— 这份表专门给上游变更检测当基准（2026-10-01 加）。
MAPCFG_OUT = os.path.join(DATA_DIR, "mapcfg.json")
DIFF_OUT = os.path.join(DATA_DIR, "repo_diff.json")
# 上游「变更台账」：每次检测到上游改动追加一条，可在软件里回看（v2.9 起）。
UPDLOG_OUT = os.path.join(DATA_DIR, "upd_log.json")
# 配置层**文件清单**（哪张图的哪一类文件动过）。字段级 diff 只盯奖励 / 选图 / 参数，
# 「修改地图翻译」「补充地图Boss」这类提交只有文件哈希才认得出（2026-10-01 加）。
MANIFEST_OUT = os.path.join(DATA_DIR, "repo_files.json")
UPDLOG_MAX = 240

# 以下前缀全部是**相对路径**（先过 relpath_of，见上）
REWARDS_PREFIX = "2001/sharp/configs/rewards/"
MAPS_PATH = "2001/sharp/configs/maps.json"
MAPPERS_PATH = "2001/sharp/configs/mappers.json"
# 每张地图的官方 ConVar 配置（由 ZombiEscape - Map Configs 生成器产出），
# 里面就是「尸变」相关参数的正源：ze_infect_sort_by_immunity 等
CFG_PREFIX = "2001/csgo/cfg/map-configs/"
# 配置层里字段级 diff 覆盖不到的两类（只做文件级比对）
TRANS_PREFIX = "2001/sharp/configs/translations/"
BOSS_PREFIX = "2001/sharp/configs/bosses/"
MISC_PATHS = (MAPS_PATH, MAPPERS_PATH)

# 缓存有效期（秒）。仓库是配置仓，10 分钟内认为新鲜即可
CACHE_TTL = 600

# 配置层「层」中文名（台账与界面共用）
LAYER_CN = {"cfg": "地图参数", "rew": "通关奖励", "trans": "地图翻译",
            "boss": "Boss 配置", "misc": "选图数据"}


def layer_of(name):
    """归档内路径 → (层键, 名字)；不是配置层文件返回 (None, None)。

    「配置层」= 官方每次提交真正会动的那几类文件；exe/资源等一律不关心。
    """
    if name.startswith(CFG_PREFIX) and name.endswith(".cfg"):
        base = os.path.basename(name)[:-4]
        return ("cfg", base) if not base.startswith("_") else (None, None)
    if name.startswith(REWARDS_PREFIX) and name.endswith(".jsonc"):
        base = os.path.basename(name)[:-6]
        return ("rew", base) if not base.startswith("_") else (None, None)
    for key, prefix in (("trans", TRANS_PREFIX), ("boss", BOSS_PREFIX)):
        if name.startswith(prefix) and name.endswith(".jsonc"):
            return key, os.path.basename(name)[:-6]
    for p in MISC_PATHS:
        if name == p:
            return "misc", os.path.basename(p)
    return None, None


# ────────────────────────────── JSONC 解析 ──────────────────────────────
def strip_jsonc(text: str) -> str:
    """去掉 // 与 /* */ 注释（跳过字符串内部），并清理尾随逗号。"""
    out = []
    i, n = 0, len(text)
    in_str = False
    quote = ""
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                in_str = False
            i += 1
            continue
        if c in ('"', "'"):
            in_str = True
            quote = c
            out.append('"' if c == "'" else c)
            i += 1
            continue
        if c == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                j = text.find("\n", i)
                i = n if j == -1 else j
                continue
            if nxt == "*":
                j = text.find("*/", i + 2)
                i = n if j == -1 else j + 2
                continue
        out.append(c)
        i += 1

    s = "".join(out)
    s = re.sub(r",(\s*[}\]])", r"\1", s)   # 尾随逗号
    return s


def parse_jsonc(text: str):
    return json.loads(strip_jsonc(text))


# ───────────────────────── 每图 ConVar（尸变参数） ─────────────────────────
# cfg 是「// 注释 + 变量名 "值"」的 Source 引擎配置，直接抓键值对即可。
# ⚠ 必须带 re.M：parse_infect 是整段文本 findall，没有 MULTILINE 时 ^ 只认串首。
CFG_KV = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s+"([^"]*)"', re.M)
# 每个 ConVar 上文都有「// 说  明: 中文名」，拿来当明细里的参数名
CFG_CN = re.compile(r'//\s*说\s*明\s*[:：]\s*(.+?)\s*$')
CFG_CN_BACK = 8                 # 中文名最多往上找几行


def infect_of(kv: dict):
    """从 ConVar 字典里抽「尸变」4 项（界面口径）；没抽到任何字段则返回 None。

    字段含义（与官方 cfg 注释一致）：
      rand  1=纯随机尸变（官方 ze_infect_sort_by_immunity=false）
            0=按尸变指数降序选母体（老玩家优先尸变）
      ratio 尸变比（人），默认 7
      time  尸变倒计时（秒），默认 15
      tp    尸变时传送回出生点（开关）
    """
    out = {}

    v = kv.get("ze_infect_sort_by_immunity")
    if v is not None:
        out["rand"] = 1 if str(v).strip().lower() == "false" else 0

    def num(key, cast=int):
        try:
            return cast(float(kv[key]))
        except (KeyError, TypeError, ValueError):
            return None

    ratio = num("ze_infect_mother_ratio")
    if ratio is not None:
        out["ratio"] = ratio
    t = num("ze_infect_mother_spawn_time")
    if t is not None:
        out["time"] = t
    tp = kv.get("ze_infect_teleport_to_spawn")
    if tp is not None:
        out["tp"] = str(tp).strip().lower() == "true"
    return out or None


def parse_infect(text: str):
    """从单张地图的 cfg 文本里抽「尸变」相关参数。"""
    return infect_of(dict(CFG_KV.findall(text)))


def parse_cfg(text: str):
    """解析单张地图的 cfg：返回 (尸变 4 项, 全量 ConVar, 参数中文名)。

    官方仓库里占大头的是「修改地图参数」类提交，动的是任意一项 ConVar；
    只留 4 项尸变参数的话，别的改动在本地数据里连痕迹都没有 —— 见
    fys_reward_app 的「上游变更检测」。这里把全量键值+中文名一起带出去。
    """
    kv, cn = {}, {}
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        m = CFG_KV.match(ln)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        kv[key] = val
        for j in range(i - 1, max(-1, i - 1 - CFG_CN_BACK), -1):
            c = CFG_CN.search(lines[j])
            if c:
                cn[key] = c.group(1).strip()
                break
    return infect_of(kv), kv, cn


# ────────────────────────────── 下载与抽取 ──────────────────────────────
def _fetch(url: str, part: str, timeout: int) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "fys-reward-indexer"})
    total = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            total += len(chunk)
    return total


# ── 进度回调（v2.14 体验 P1④）────────────────────────────────────────
# 同步一次要 10~30 秒（下载 → 解包 → 比对 → 写盘），以前界面上只有一句
# 「正在从 GitHub 拉取…」，用户不知道是不是卡死了。这里把每个阶段的
# (文案, 百分比) 抛给调用方（fys_reward_app 会写进 State.sync，前端轮询显示）。
_PROGRESS = {"fn": None}


def set_progress(fn):
    """注册进度回调 fn(text, pct)；传 None 取消。回调抛异常一律忽略。"""
    _PROGRESS["fn"] = fn


def _step(text, pct):
    print("[%d%%] %s" % (pct, text))
    fn = _PROGRESS["fn"]
    if fn:
        try:
            fn(text, pct)
        except Exception:                                      # noqa: BLE001
            pass


def download_tarball(dest: str) -> str:
    _step("正在从 GitHub 下载仓库归档包…", 5)
    t0 = time.time()
    part = dest + ".part"
    for p in (part, dest):                      # 清掉上次的残留
        try:
            os.remove(p)
        except OSError:
            pass
    # 官方源直连（镜像可选）；一个失败换下一个，全失败才报错。
    for url in (REPO_MIRROR, REPO_TARBALL, REPO_TARBALL2):
        if not url:
            continue
        try:
            total = _fetch(url, part, 60 if url == REPO_MIRROR else 180)
        except Exception as e:                  # noqa: BLE001
            print("      %s 不可用（%r），换下一个源" % (url[:52], e))
            continue
        if total < 1024:                        # 镜像可能返回空壳，视为失败
            print("      %s 内容异常（%d 字节），换下一个源" % (url[:52], total))
            continue
        os.replace(part, dest)                  # 只有完整下完才落盘
        _step("归档包已下载（%.1f MB），正在解包…" % (total / 1048576.0), 25)
        return dest
    raise RuntimeError("仓库归档包下载失败（镜像与官方源均不可用）")


def extract(tar_path: str):
    """返回 (rewards, maps, mappers, infects, mapcfg, manifest)

    manifest = {层键: {名字: 短哈希}}，给「文件级变更台账」用；老调用方
    （回归脚本的替身实现）只返回 5 项时，build() 侧按 5 项兼容。
    """
    print("[2/4] 解包并解析配置 ...")
    _step("正在解包并解析官方配置…", 40)
    rewards, maps, mappers, infects = {}, {}, {}, {}
    cfg_kv, cfg_cn = {}, {}          # 图名 -> ConVar 全量 / 参数中文名
    man = {k: {} for k in ("cfg", "rew", "trans", "boss", "misc")}
    max_mt = 0
    bad = []
    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf:
            if not m.isfile():
                continue
            name = relpath_of(m.name)                  # 先剥掉归档根目录名
            if m.mtime > max_mt:
                max_mt = m.mtime                       # 归档内 mtime 全被压平成提交时间
            lk, ln = layer_of(name)
            if lk:
                try:
                    man[lk][ln] = hashlib.sha1(tf.extractfile(m).read()).hexdigest()[:10]
                except Exception:                      # noqa: BLE001
                    pass
            if name.startswith(REWARDS_PREFIX) and name.endswith(".jsonc"):
                map_name = os.path.basename(name)[:-len(".jsonc")]
                fh = tf.extractfile(m)
                if fh is None:
                    continue
                try:
                    rewards[map_name] = parse_jsonc(fh.read().decode("utf-8", "replace"))
                except Exception as e:            # 单个文件坏掉不影响整体
                    bad.append((name, repr(e)))
            elif name.startswith(CFG_PREFIX) and name.endswith(".cfg"):
                # 跳过 _template.cfg / _extreme_*.cfg 这类前后缀标记文件
                map_name = os.path.basename(name)[:-len(".cfg")]
                if map_name.startswith("_"):
                    continue
                fh = tf.extractfile(m)
                if fh is None:
                    continue
                try:
                    inf, kv, cn = parse_cfg(fh.read().decode("utf-8", "replace"))
                    if inf:
                        infects[map_name] = inf
                    if kv:
                        cfg_kv[map_name] = kv
                    for k, v in cn.items():
                        cfg_cn.setdefault(k, v)
                except Exception as e:            # noqa: BLE001
                    bad.append((name, repr(e)))
            elif name == MAPS_PATH:
                fh = tf.extractfile(m)
                if fh:
                    try:
                        maps = parse_jsonc(fh.read().decode("utf-8", "replace"))
                    except Exception as e:
                        bad.append((name, repr(e)))
            elif name == MAPPERS_PATH:
                fh = tf.extractfile(m)
                if fh:
                    try:
                        mappers = parse_jsonc(fh.read().decode("utf-8", "replace"))
                    except Exception as e:
                        bad.append((name, repr(e)))

    mapcfg = cfg_store(cfg_kv, cfg_cn)
    man["at_ts"] = int(max_mt)
    man["at"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(max_mt)) if max_mt else ""
    rand = sum(1 for v in infects.values() if v.get("rand") == 1)
    print("      地图奖励 %d 份 / 地图数据 %d 条 / 作者表 %d 条 / 尸变配置 %d 条（其中随机尸变 %d）"
          % (len(rewards), len(maps), len(mappers), len(infects), rand))
    print("      地图参数 %d 张图 × %d 项（中文名 %d 个）"
          % (len(cfg_kv), len(mapcfg["k"]), len(cfg_cn)))
    print("      配置层清单：参数 %d / 奖励 %d / 翻译 %d / Boss %d"
          % (len(man["cfg"]), len(man["rew"]), len(man["trans"]), len(man["boss"])))
    if bad:
        print("      !! 解析失败 %d 个：" % len(bad))
        for n, e in bad[:5]:
            print("         -", n, e)
    return rewards, maps, mappers, infects, mapcfg, man


# ───────────────────── 全量 ConVar 表的紧凑编码 ─────────────────────
# 703 张图 × 31 项直接存 {"图": {"键": "值"}} 是 660KB；键在所有图里完全一致，
# 抽成「键表 + 值数组」后约 180KB，落在 exe 与 zip 里都省得多。
# 读取端一律先经 cfg_rows() 还原成普通字典，比对逻辑不感知这个编码。
def cfg_store(kv_map: dict, cn: dict):
    keys = sorted({k for kv in kv_map.values() for k in kv})
    vals = {}
    for mp, kv in kv_map.items():
        vals[mp] = [kv.get(k) for k in keys]
    return {"k": keys, "cn": dict(cn), "v": vals}


def cfg_rows(store):
    """紧凑表还原成 {图名: {ConVar: 值}}；None / 旧版缺表都返回 {}。"""
    out = {}
    if not isinstance(store, dict):
        return out
    keys = store.get("k")
    vals = store.get("v")
    if not isinstance(keys, list) or not isinstance(vals, dict):
        return out
    for mp, row in vals.items():
        if not isinstance(row, list):
            continue
        d = {}
        for i, k in enumerate(keys):
            if i < len(row) and row[i] is not None:
                d[k] = row[i]
        out[str(mp).strip().lower()] = d
    return out


def cfg_cn(store):
    cn = (store or {}).get("cn") if isinstance(store, dict) else None
    return cn if isinstance(cn, dict) else {}


# cfg 参数的界面分组：玩家看一张图时最关心的角度（与官方 cfg 注释的立场一致）
CFG_GROUPS = (
    ("僵尸与尸变", ("ze_infect_sort_by_immunity", "ze_infect_mother_ratio",
                    "ze_infect_mother_spawn_time", "ze_infect_teleport_to_spawn")),
    ("僵尸技能", ("ze_skill_blader_damage", "ze_skill_cirrus_range",
                  "ze_skill_dancer_speed", "ze_skill_deimos_amount",
                  "ze_skill_farter_regen", "ze_skill_faster_speed",
                  "ze_skill_hunter_power", "ze_skill_smoker_range",
                  "ze_skill_yaksha_damage")),
    ("武器与补给", ("ze_weapons_spawn_hegrenade", "ze_weapons_spawn_molotov",
                    "ze_weapons_spawn_decoy", "ze_weapons_round_hegrenade",
                    "ze_weapons_round_molotov", "ze_weapons_round_decoy",
                    "ze_weapons_round_flash", "ze_weapons_round_smoke",
                    "ze_weapons_round_adrenaline")),
    ("击退与生存", ("ze_knockback_scale", "sv_falldamage_scale",
                    "ze_spawn_start_health_override", "ms_flashlight_enabled")),
    ("时间与投票", ("mp_timelimit", "mp_roundtime", "mcr_map_extend_times",
                    "vip_map_extend_times")),
    ("经济", ("ze_cash_damage_zombie",)),
)


def cfg_disp(v):
    """cfg 原始值 → 玩家看得懂的写法（开关转中文、45.0 去掉多余小数）。"""
    if v is None or v == "":
        return "—"
    s = str(v).strip()
    low = s.lower()
    if low == "true":
        return "开启"
    if low == "false":
        return "关闭"
    try:
        return "%g" % float(s)
    except (TypeError, ValueError):
        return s


def _cfgnum(v):
    """cfg 值 → 数值（40.0 与 40 归一），非数值返回 None。"""
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else f


def _cfg_same(a, b):
    """cfg 参数是否相同：数值型按数值比（官方生成器 40 / 40.0 混用，直接比字符串会把
    「没变」报成「变了」）；非数值退回字符串比较。"""
    if a == b:
        return True
    fa, fb = _cfgnum(a), _cfgnum(b)
    return fa is not None and fb is not None and fa == fb


def cfg_groups(row, cn_map=None):
    """单图 {ConVar: 原始值} → [(分组名, [(中文名, 键, 显示值), ...]), ...]

    未出现在 CFG_GROUPS 里的键归到末尾「其它」（官方新增参数时不会丢）。
    """
    cn_map = cn_map or {}
    row = row or {}
    out, seen = [], set()
    for name, keys in CFG_GROUPS:
        items = []
        for k in keys:
            if k in row:
                items.append((cn_map.get(k) or k, k, cfg_disp(row[k])))
                seen.add(k)
        if items:
            out.append((name, items))
    rest = [(cn_map.get(k) or k, k, cfg_disp(row[k]))
            for k in sorted(row) if k not in seen]
    if rest:
        out.append(("其它参数", rest))
    return out


MAPSET_FIELDS = (("price", "选图价格"), ("cooldown", "选图冷却(分)"),
                 ("requiredPlayers", "所需人数"), ("requiredOnline", "在线门槛"),
                 ("nomination", "可提名"), ("admin", "管理员专属"),
                 ("certainTimes", "限定时段"))
SET_CN = {f: cn for f, cn in MAPSET_FIELDS}


def _disp(v):
    if isinstance(v, (list, tuple)):
        return "、".join(str(x) for x in v) if v else "—"
    if isinstance(v, bool):
        return "是" if v else "否"
    if v is None or v == "":
        return "—"
    return str(v)


def mapset_rows(maps):
    """maps.json 的「选图参数」→ {图名: {中文名: 显示值}}（官方叫「修改地图数据」）。"""
    out = {}
    for k, v in (maps or {}).items():
        if not isinstance(v, dict):
            continue
        row = {}
        for f, cn in MAPSET_FIELDS:
            if f in v:
                row[cn] = _disp(v.get(f))
        if row:
            out[str(k).strip().lower()] = row
    return out


_PREV_FILES = ("rewards", "maps", "mapcfg", "infect")


def snapshot_prev():
    """同步覆盖前，把当前数据存成 *.prev.json —— 地图详情「新旧参数对比」的数据源。

    语义：prev = 上次「立即同步」之前的配置。定时检测（auto）只比对不覆盖，
    不会动这份快照，所以对比的始终是「玩家上次实际应用更新前」的样子。"""
    import shutil
    for n in _PREV_FILES:
        src = os.path.join(DATA_DIR, n + ".json")
        if not os.path.exists(src):
            continue
        try:
            shutil.copyfile(src, os.path.join(DATA_DIR, n + ".prev.json"))
        except OSError as e:                                   # noqa: BLE001
            print("      !! 旧数据快照失败（不影响同步）: %r" % (e,))


def sanity(rewards: dict) -> dict:
    """产出统计信息，便于确认数据没解析歪。"""
    stages_total = 0
    passes_vals = []
    for mp, cfg in rewards.items():
        if not isinstance(cfg, dict):
            continue
        for st, st_cfg in cfg.items():
            stages_total += 1
            if isinstance(st_cfg, dict) and "rankPasses" in st_cfg:
                try:
                    passes_vals.append(int(st_cfg["rankPasses"]))
                except Exception:
                    pass
    passes_vals.sort()
    return {
        "maps": len(rewards),
        "stages": stages_total,
        "rankPasses_min": passes_vals[0] if passes_vals else None,
        "rankPasses_max": passes_vals[-1] if passes_vals else None,
        "rankPasses_median": passes_vals[len(passes_vals) // 2] if passes_vals else None,
    }


# ───────────────────────── 上游变更检测（v2.2） ─────────────────────────
# 每次成功拉取并解析新数据后，与磁盘上的旧数据做一次本地比对，结果落
# data/repo_diff.json —— 主页横幅 / 变更明细弹窗 / 关卡表「有更新」角标都读它。
# 比对在本地完成，零额外网络请求。
REWARD_FIELDS = ("rankPasses", "rankDamage", "econPasses", "econDamage", "rankIntern")
REWARD_FIELD_CN = {"rankPasses": "通关云点", "rankDamage": "伤害云点",
                   "econPasses": "通关龙晶", "econDamage": "伤害龙晶",
                   "rankIntern": "内部云点"}
INFECT_FIELD_CN = {"rand": "尸变模式", "ratio": "尸变比",
                   "time": "尸变倒计时", "tp": "传送回出生点"}


def _num(v):
    """数值统一：整数值转 int（100.0 → 100），避免 100 与 100.0 判不等。"""
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return v


def _skey(k):
    return (0, k) if isinstance(k, int) else (1, str(k))


def _norm_rewards(rewards):
    """统一成 {小写地图名: {str(关卡): {字段: 数值}}}，diff 只认内容不认键风格。"""
    out = {}
    for k, cfg in (rewards or {}).items():
        if not isinstance(cfg, dict):
            continue
        stages = {}
        for sk, sv in cfg.items():
            if not isinstance(sv, dict):
                continue
            stages[str(sk)] = {f: _num(sv.get(f)) for f in REWARD_FIELDS
                               if sv.get(f) is not None}
        out[str(k).strip().lower()] = stages
    return out


def _norm_infect(infect):
    return {str(k).strip().lower(): dict(v) for k, v in (infect or {}).items()
            if isinstance(v, dict)}


def _infect_disp(field, v):
    """尸变参数转人话（与样板图口径一致）；旧值缺失时给「—」。"""
    if v is None:
        return "—"
    if field == "rand":
        return "纯随机" if v == 1 else "按指数降序"
    if field == "ratio":
        try:
            return "1/%d" % int(v)
        except (TypeError, ValueError):
            return str(v)
    if field == "time":
        try:
            return "%g 秒" % float(v)
        except (TypeError, ValueError):
            return str(v)
    if field == "tp":
        return "开" if v else "关"
    return str(v)


# diff 算法版本：改了 diff_repo / _read_old_cache 的判定口径就 +1。
# 旧算法算出来的「未读提醒」可能是假阳性（v2.1 曾把已转正的本地条目反复报成
# 新增地图），所以 _write_diff 只在算法版本一致时才保留未读提醒 —— 版本一变，
# 旧的那份第一次比对就会被子正确结果覆盖，用户升级后不用再手动点一次「立即更新」。
DIFF_ALGO = 3


def _empty_diff(seen=True, first=False):
    return {"detected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "detected_ts": time.time(), "seen": seen, "first": first,
            "algo": DIFF_ALGO,
            "counts": {"new": 0, "edit": 0, "stage": 0, "zombie": 0,
                       "param": 0, "del": 0, "total": 0},
            "groups": {"new": [], "edit": [], "stage": [], "zombie": [],
                       "param": [], "del": []}}


def diff_repo(old_r, old_m, old_i, new_r, new_m, new_i, old_c=None, new_c=None):
    """新旧数据逐图逐字段比对 → 按类型分组的变更明细。

    old_c/new_c = 全量 ConVar 表（build_index.cfg_store 那套编码）。旧客户端
    没有这份表时为 None，这时**跳过**参数比对：没有基准就不能断言「变了」，
    宁可这一轮不报，也不能把整表当成新增误报几百条。
    """
    groups = {"new": [], "edit": [], "stage": [], "zombie": [],
              "param": [], "del": []}
    or_, nr_ = _norm_rewards(old_r), _norm_rewards(new_r)
    okeys = set(or_) | {str(k).strip().lower() for k in (old_m or {})}
    nkeys = set(nr_) | {str(k).strip().lower() for k in (new_m or {})}
    ninf, oinf = _norm_infect(new_i), _norm_infect(old_i)

    def snum(k):
        try:
            return int(k)
        except (TypeError, ValueError):
            return str(k)

    # 新增 / 下架：只按「官方数据里还有没有这张图」判定。
    # 新图把概要值一并带进 fields（关卡数 / 选图参数）——台账与横幅明细里
    # 「新上架」不再是一句空话（2026-10-23 用户反馈：看不懂改动内容是什么）。
    nset_all = mapset_rows(new_m)
    for k in sorted(nkeys - okeys):
        stages = len(nr_.get(k) or {})
        fields = [{"k": "关卡数", "f": "stages", "old": None, "new": stages}]
        row = nset_all.get(k) or {}
        for f, cn in MAPSET_FIELDS:
            v = row.get(cn)
            if v in (None, "", "-1", "—"):
                continue          # -1 = 无门槛/不限，没信息量（2026-10-23）
            fields.append({"k": cn, "f": "set:" + f, "old": None, "new": v})
        groups["new"].append({"map": k, "stages": stages, "fields": fields})
    for k in sorted(okeys - nkeys):
        groups["del"].append({"map": k})

    # 共有地图：奖励数值 / 关卡数 / 尸变参数
    edits = {}                       # 同一张图的字段变化合并成一条（明细里一行）
    for k in sorted(okeys & nkeys):
        ost, nst = or_.get(k) or {}, nr_.get(k) or {}
        if ost and nst and len(ost) != len(nst):
            added = sorted({snum(x) for x in set(nst) - set(ost)}, key=_skey)
            removed = sorted({snum(x) for x in set(ost) - set(nst)}, key=_skey)
            groups["stage"].append({"map": k, "old": len(ost), "new": len(nst),
                                    "added": added, "removed": removed})
        for sk in set(ost) & set(nst):
            for f in REWARD_FIELDS:
                a, b = ost[sk].get(f), nst[sk].get(f)
                if a is None and b is None:
                    continue
                if a != b:
                    ed = edits.setdefault(k, {"map": k, "fields": []})
                    ed["fields"].append({"stage": snum(sk), "k": REWARD_FIELD_CN[f],
                                         "f": f, "old": a, "new": b})
        oi, ni = oinf.get(k) or {}, ninf.get(k) or {}
        if oi or ni:
            zfields = []
            for f in ("rand", "ratio", "time", "tp"):
                a, b = oi.get(f), ni.get(f)
                if a != b:
                    zfields.append({"k": INFECT_FIELD_CN[f], "f": f,
                                    "old": _infect_disp(f, a),
                                    "new": _infect_disp(f, b)})
            if zfields:
                groups["zombie"].append({"map": k, "fields": zfields})
    groups["edit"] = [edits[k] for k in sorted(edits)]

    # 地图参数：cfg 全量 ConVar（官方「修改地图参数」）+ maps.json 选图参数
    # （官方「修改地图数据」）。旧客户端没有基准表时整段跳过，避免误报。
    if old_c is not None and new_c is not None:
        oc, nc = cfg_rows(old_c), cfg_rows(new_c)
        oset, nset = mapset_rows(old_m), mapset_rows(new_m)
        cn_of = dict(cfg_cn(old_c))
        cn_of.update(cfg_cn(new_c))
        # maps.json 原始行按小写图名索引（oset/nset 只有显示值，拿不到原始字段名）
        old_l = {str(x).strip().lower(): v for x, v in (old_m or {}).items()
                 if isinstance(v, dict)}
        new_l = {str(x).strip().lower(): v for x, v in (new_m or {}).items()
                 if isinstance(v, dict)}
        # 并集遍历：官方给某图新补 / 删掉整份 cfg 也是「地图参数」变更，
        # 以前只比交集，这两种情况会被静默漏掉（2026-11-09 排查）。
        for k in sorted(set(oc) | set(nc)):
            o, n = oc.get(k) or {}, nc.get(k) or {}
            pfields = []
            for f in sorted(set(o) | set(n)):
                a, b = o.get(f), n.get(f)
                if _cfg_same(a, b):
                    continue
                # 显示走 cfg_disp（40.0→40、true→开启），与地图参数页同口径
                pfields.append({"k": cn_of.get(f) or f, "f": f,
                                "old": cfg_disp(a), "new": cfg_disp(b)})
            # 选图参数只比「两边都有的图」：整图上下架由 new/del 组负责
            if k in oset and k in nset:
                orow, nrow = old_l.get(k) or {}, new_l.get(k) or {}
                for fk, cn in MAPSET_FIELDS:
                    a, b = _disp(orow.get(fk)), _disp(nrow.get(fk))
                    if a != b:
                        pfields.append({"k": cn, "f": "set:" + fk,
                                        "old": a, "new": b})
            if pfields:
                groups["param"].append({"map": k, "fields": pfields})

        # 选图参数补漏：上面只在「两边都有 cfg ConVar 基准」的图里顺带比 maps.json，
        # 没有 cfg 的图改了价格/冷却/提名会被静默漏掉（2026-10-23 修）。
        cfg_maps = set(oc) | set(nc)
        for k in sorted((set(oset) & set(nset)) - cfg_maps):
            orow, nrow = old_l.get(k) or {}, new_l.get(k) or {}
            pfields = []
            for fk, cn in MAPSET_FIELDS:
                a, b = _disp(orow.get(fk)), _disp(nrow.get(fk))
                if a != b:
                    pfields.append({"k": cn, "f": "set:" + fk, "old": a, "new": b})
            if pfields:
                groups["param"].append({"map": k, "fields": pfields})

    d = _empty_diff(seen=False)
    d["groups"] = groups
    total = 0
    for g, rows in groups.items():
        d["counts"][g] = len(rows)
        total += len(rows)
    d["counts"]["total"] = total
    return d


def _write_diff(diff, force=False):
    """diff 落盘（原子写）。

    特殊规则：结果为空时，若上一份 diff 还有「用户没看过」的变更，保留不动——
    TTL 过期后的后台静默重建也会走到这里，横幅不能被无声冲掉。
    force=True（用户点「立即同步」触发）时照常覆盖：同步完数据就是最新的，
    旧提醒该消失就消失。
    """
    if not force and not diff["counts"]["total"]:
        prev = None
        try:
            if os.path.exists(DIFF_OUT):
                with open(DIFF_OUT, "r", encoding="utf-8") as fh:
                    prev = json.load(fh)
        except Exception:                                      # noqa: BLE001
            prev = None
        if (isinstance(prev, dict) and (prev.get("counts") or {}).get("total")
                and not prev.get("seen")
                # 旧算法留下的未读提醒不保留：它可能是假阳性（见 DIFF_ALGO），
                # 保留下来横幅就再也下不去了。升级后第一次比对即自愈。
                and prev.get("algo") == DIFF_ALGO):
            return
    _write_json(DIFF_OUT, diff)


# ─────────────────── 配置层文件级比对 & 上游变更台账（v2.9）───────────────────
_CONFIG_LAYERS = ("cfg", "rew", "trans", "boss", "misc")


def manifest_load():
    """读上次的配置层文件清单；没有基准（首次安装 / 旧版升级）返回 None。"""
    try:
        with open(MANIFEST_OUT, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:                                          # noqa: BLE001
        return None
    return d if isinstance(d, dict) and isinstance(d.get("cfg"), dict) else None


def diff_files(old_man, new_man):
    """配置层**文件级**差异 → {层键: {"c": [改过], "a": [新增], "r": [删除]}}。

    字段级 diff 覆盖不到「地图翻译」「Boss 配置」——那两类除了内容变化没有别的
    信号，只有文件哈希认得出（官方提交里这类占比很大）。
    """
    out = {}
    if not isinstance(old_man, dict) or not isinstance(new_man, dict):
        return out
    for lk in _CONFIG_LAYERS:
        o, n = old_man.get(lk) or {}, new_man.get(lk) or {}
        if not isinstance(o, dict) or not isinstance(n, dict):
            continue
        c = sorted(k for k in n if k in o and o[k] != n[k])
        a = sorted(k for k in n if k not in o)
        r = sorted(k for k in o if k not in n)
        if c or a or r:
            out[lk] = {"c": c, "a": a, "r": r}
    return out


def updlog_load():
    """读变更台账（列表，最新在前）。坏文件按空台账处理。"""
    try:
        with open(UPDLOG_OUT, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:                                          # noqa: BLE001
        return []
    return d if isinstance(d, list) else []


# 字段级分组 → 台账 / 界面用的中文类型
_GROUP_KIND = {"param": "地图参数", "zombie": "地图参数", "edit": "通关奖励",
               "stage": "关卡数", "new": "新增地图", "del": "已下架"}
_KIND_ORDER = {"新增地图": 0, "已下架": 1, "通关奖励": 2, "关卡数": 3,
               "地图参数": 4, "地图翻译": 5, "Boss 配置": 6}


def _sig(entry):
    """台账去重签名：同一份上游状态（同提交时间 + 同受影响图/类型）只记一次。"""
    return (entry.get("ts"),
            tuple(sorted((m.get("f"), tuple(m.get("k") or []))
                         for m in (entry.get("maps") or []))),
            bool(entry.get("misc")))


def history_entry(fdiff, groups, man, detected, via):
    """把一次检测结果整理成一条台账记录；没有实质改动返回 None。"""
    kinds, maps = {}, {}
    # 新图不拆「参数/翻译/Boss」类别：一张新图的所有文件都是新的，
    # 文件级 diff 会把它同时算进四五个类别，全是噪音（2026-10-23）。
    new_names = {str((it or {}).get("map") or "").strip().lower()
                 for it in (groups or {}).get("new") or []}

    def touch(name, kind):
        if not name:
            return
        if str(name).strip().lower() in new_names and kind != "新增地图":
            return
        e = maps.setdefault(name, {"f": name, "k": [], "fld": []})
        if kind not in e["k"]:
            e["k"].append(kind)
            # ⚠ 按「图 × 类型」去重计数：文件级与字段级会命中同一张图同一类，
            # 直接累加会把 1 条改动算成 2 条（2026-10-01 种子复盘时发现）
            kinds[kind] = kinds.get(kind, 0) + 1

    for lk, d in (fdiff or {}).items():
        if lk == "misc":
            continue
        for name in list(d.get("c") or []) + list(d.get("a") or []):
            touch(name, LAYER_CN.get(lk, lk))
    for g, items in (groups or {}).items():
        kind = _GROUP_KIND.get(g)
        if not kind:
            continue
        for it in items or []:
            name = str((it or {}).get("map") or "").strip()
            if not name:
                continue
            touch(name, kind)
            for f in (it.get("fields") or []):
                if not isinstance(f, dict):
                    continue
                # st=关卡号（通关/伤害奖励才有）。此前把它丢了，台账里同一张图
                # 八条「通关云点 11→12」根本分不清是哪一关（2026-10-12 用户反馈）
                maps[name]["fld"].append({"g": kind, "k": f.get("k"), "f": f.get("f"),
                                          "st": f.get("stage"),
                                          "old": f.get("old"), "new": f.get("new")})
    misc = any((d.get("c") or d.get("a") or d.get("r"))
               for k, d in (fdiff or {}).items() if k == "misc")
    if not maps and not misc:
        return None
    man = man if isinstance(man, dict) else {}
    ml = sorted(maps.values(),
                key=lambda e: (min(_KIND_ORDER.get(k, 9) for k in e["k"]), e["f"]))
    return {"at": man.get("at") or "", "ts": int(man.get("at_ts") or 0),
            "detected": detected, "via": via, "kinds": kinds,
            "misc": bool(misc), "n": len(ml), "maps": ml[:150]}


def history_append(entry):
    """追加一条台账（近 3 条内签名相同视为重复；超上限丢最旧的）。"""
    if not entry:
        return None
    log = [e for e in updlog_load() if isinstance(e, dict)]
    s = _sig(entry)
    for prev in log[:3]:
        if _sig(prev) == s:
            return None
    log.insert(0, entry)
    _write_json(UPDLOG_OUT, log[:UPDLOG_MAX], indent=None)
    return entry


def load_local() -> dict:
    """读本地补充层（maps_local.json / rewards_local.json），坏文件按空表处理。"""
    out = {"maps": {}, "rewards": {}}
    for key, path in (("maps", MAPS_LOCAL), ("rewards", REWARDS_LOCAL)):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    d = json.load(fh)
                if isinstance(d, dict):
                    out[key] = d
        except Exception:                                          # noqa: BLE001
            pass
    return out


def _read_old_cache(upstream=None):
    """读磁盘上的旧缓存做 diff 基准；文件缺失/损坏按空表处理。

    本地补充条目不算「上游变更」，比对前先剔除，免得每次同步都误报删除。

    ⚠ 但**不能无脑剔除**（v2.14 修）：本地补充层里有些图随着官方收录已经
    「转正」，同一张图在 maps_local.json 和官方 maps.json 里都有。若无脑
    `pop`，这张图就从旧基准里消失，而上游有它 → 每次比对都判成「新增地图」，
    同步多少次都不归零：横幅永远挂着「官方数据有更新 · 立即更新」，用户点完
    下次开软件又冒出来（实测 5 张：ze_exit8 / ze_fe8_sacred_stones / …）。
    所以只剔除「上游也没有」的本地条目 —— 那种才真的是本地私货，不该报删除。
    upstream={"maps": set, "rewards": set} 为上游本次的键集合；None 表示调用方
    拿不到上游（老测试脚本），退回旧行为。

    cfg（全量参数表）缺失或损坏时给 None 而不是 {}：{} 会被当成「官方原本
    一项参数都没有」的基准，于是整表 700 多张图全报成变更。
    """
    out = {"rewards": {}, "maps": {}, "infect": {}, "cfg": None, "man": None}
    for key, path in (("rewards", REWARDS_OUT), ("maps", MAPS_OUT),
                      ("infect", INFECT_OUT), ("cfg", MAPCFG_OUT)):
        empty = {} if key != "cfg" else None
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    out[key] = json.load(fh)
            else:
                out[key] = empty
        except Exception:                                          # noqa: BLE001
            out[key] = empty
    # 配置层文件清单（旧版升级 / 首次安装时没有 → None，只是少报翻译/Boss 类改动）
    out["man"] = manifest_load()
    local = load_local()
    for key in ("maps", "rewards"):
        # 上游键集合统一小写比较：官方 maps.json 的键是小写，但本地层可能手写成
        # 混合大小写，按原样 `in` 判断会漏掉「其实上游也有」。两个方向都按小写
        # 归一，避免同名不同大小写造成的假「新增」。
        up = None
        if isinstance(upstream, dict) and upstream.get(key) is not None:
            up = {str(x).strip().lower() for x in upstream[key]}
        for k in list(local[key]):
            if up is not None and str(k).strip().lower() in up:
                continue          # 官方也收录了 → 保留在基准里，不当「新增」报
            out[key].pop(k, None)
            if up is not None:    # 本地层与缓存的时间大小写可能不一致，兜底再删一次
                out[key].pop(str(k).strip().lower(), None)
    return out


# ────────────────────────────── 主流程 ──────────────────────────────
def is_fresh() -> bool:
    for p in (REWARDS_OUT, MAPS_OUT, META_OUT, INFECT_OUT, MAPCFG_OUT,
              MANIFEST_OUT):
        if not os.path.exists(p):
            return False
    return (time.time() - os.path.getmtime(REWARDS_OUT)) < CACHE_TTL


def seed_cache():
    """首次运行时，把打包进 exe 的缓存释放到 exe 旁边，做到离线可用。"""
    bundle = getattr(sys, "_MEIPASS", None)
    if not bundle:
        return
    src_dir = os.path.join(bundle, "data")
    if not os.path.isdir(src_dir):
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    # ⚠ 本地补充层必须也释放：EXG 补充图 / 样板图放在 maps_local.json / rewards_local.json，
    # 官方索引同步时会整体覆盖 maps.json，若不先把本地层落到 data\\，用户「立即同步」后
    # 这批复盖层条目（含全部 EXG 图）会被清空（2026-09-28 修）
    for name in ("rewards.json", "maps.json", "meta.json", "infect.json",
                 "mapcfg.json", "repo_files.json", "upd_log.json",
                 "maps_local.json", "rewards_local.json"):
        src, dst = os.path.join(src_dir, name), os.path.join(DATA_DIR, name)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                # 用 copyfile 而非 copy2：让 mtime 变成当前时间，
                # 首次运行即视为新鲜数据，不必联网。
                shutil.copyfile(src, dst)
            except OSError:
                pass


def build(force: bool = False, auto: bool = False) -> dict:
    """force=用户点「立即同步」；auto=后台定时刷新（见 fys_reward_app.repo_check_loop）。

    两者都强制下载，差别只在**变更提醒**怎么处理：
    - 手动同步（force）：同步完数据就是最新的，旧提醒该消失就消失；
    - 定时刷新（auto）：必须**保住用户还没看过的横幅**，否则它第二轮跑出空 diff
      就把提醒悄悄冲掉了（用户根本没机会看见）。
    所以别把 auto 直接翻成 force —— 那正是这里的坑。
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    seed_cache()
    if not (force or auto) and is_fresh():
        with open(META_OUT, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        print("[缓存] 数据仍新鲜（构建于 %s），跳过下载。" % meta.get("built_at_str", "?"))
        return meta

    tmp_tar = os.path.join(DATA_DIR, "_repo.tar.gz")
    try:
        download_tarball(tmp_tar)
        # extract 现在返回 6 项（多一份配置层文件清单）。回归脚本的替身实现可能仍只给
        # 5 项，按长度兼容；缺清单时视为「没有文件级基准」，只是少报翻译/Boss。
        got = extract(tmp_tar)
        rewards, maps, mappers, infects, mapcfg = got[:5]
        man = got[5] if len(got) > 5 else None
        # 兜底：extract 的替身实现（回归脚本）可能不带参数表
        if not isinstance(mapcfg, dict):
            mapcfg = cfg_store({}, {})
        if not isinstance(man, dict):
            man = None
    except Exception as e:
        # 断网 / 下载失败时，退回到已有缓存，保证软件仍能用
        if os.path.exists(REWARDS_OUT):
            print("[!] 数据更新失败（%s），继续使用本地缓存。" % e)
            with open(META_OUT, "r", encoding="utf-8") as fh:
                return json.load(fh)
        raise
    finally:
        try:
            os.remove(tmp_tar)
        except OSError:
            pass

    print("[3/4] 写入缓存 ...")
    _step("正在比对上游变更并写入缓存…", 75)
    # ── 上游变更检测：必须在覆盖写缓存「之前」与磁盘旧数据比对 ──
    # _changed 同时决定「要不要重新拍 *.prev.json 快照」：只有这次同步真的带来
    # 变化时才动快照，否则空同步会把上一次的对比基准冲成 prev==当前（见下面注释）
    _changed = False
    try:
        if os.path.exists(REWARDS_OUT):          # 首次安装没有旧数据，无从比对
            # 上游键集合一并传进去：本地补充层里「已转正」的条目必须留在基准里，
            # 否则会被反复报成「新增地图」（见 _read_old_cache 的说明）。
            old = _read_old_cache({"maps": set(maps), "rewards": set(rewards)})
            d_new = diff_repo(old["rewards"], old["maps"], old["infect"],
                              rewards, maps, infects,
                              old.get("cfg"), mapcfg)
            # 空差异不需要用户「确认」：否则落盘成 total=0 + seen=False 的怪状态，
            # 任何以后只看 seen 的地方都会以为还有没读的提醒（v2.14 修）。
            if not d_new["counts"]["total"]:
                d_new["seen"] = True
            else:
                _changed = True          # 真变化 → 这次才值得更新对比基准
            _write_diff(d_new, force=bool(force))
            # 变更台账：文件级（翻译 / Boss）+ 字段级（参数 / 奖励）合成一条记录
            try:
                history_append(history_entry(
                    diff_files(old.get("man"), man), d_new.get("groups"), man,
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    "manual" if force else "auto"))
            except Exception as e:                             # noqa: BLE001
                print("      !! 变更台账写入失败（不影响同步）: %r" % e)
        elif auto:
            # 定时检测时本地还没有缓存：没有「上次同步基准」，比对会把整份上游
            # 误报成几百条新增。直接返回，不写 diff。
            return {"auto": True, "checked_at": time.time(),
                    "note": "no-local-baseline"}
        else:
            _write_diff(_empty_diff(first=True), force=bool(force))
    except Exception as e:                                     # noqa: BLE001
        print("      !! 变更检测失败（不影响数据更新本身）: %r" % e)

    if auto:
        # 定时检测模式：只比对、不覆盖本地缓存。
        # 若这里把本地缓存刷成上游最新，横幅只会显示「自上次检测以来的增量」，
        # 而非「自用户上次同步以来累计的未读变更」——用户迟迟不同步就会漏看。
        # 真正的缓存覆盖留给手动「立即同步」（force=True）。
        return {"auto": True, "checked_at": time.time()}

    # 覆盖前留一份旧数据（地图详情「新旧参数对比」用）。
    # ⚠ 只在「这次同步真有变化」时拍快照：上游没变的空同步（连点两次立即同步、
    #   或自动检测发现无更新后用户又手动点一次）若照旧覆盖，prev 会被写成与当前
    #   完全一样 → 详情页「🆕 本次数据更新」卡永远不出现，用户会以为功能没做
    #   （2026-10-27 反馈「找不到新旧对比」的真实原因）。
    #   没有快照时补一份当基准（升级上来的首次同步不至于没得比）。
    if _changed or not os.path.exists(os.path.join(DATA_DIR, "rewards.prev.json")):
        snapshot_prev()
    local = load_local()                     # 本地补充条目并回去（官方优先）
    maps_out = dict(local["maps"])
    maps_out.update(maps)
    rewards_out = dict(local["rewards"])
    rewards_out.update(rewards)
    for path, obj in ((REWARDS_OUT, rewards_out), (MAPS_OUT, maps_out),
                      (INFECT_OUT, infects), (MAPCFG_OUT, mapcfg)):
        _write_json(path, obj, indent=None)
    if isinstance(man, dict):
        _write_json(MANIFEST_OUT, man, indent=None)

    meta = sanity(rewards)
    meta.update({
        "built_at": time.time(),
        "built_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": REPO_TARBALL,
        "mappers": len(mappers),
        "infect": len(infects),
        "infect_rand": sum(1 for v in infects.values() if v.get("rand") == 1),
        "cfg_maps": len(mapcfg.get("v") or {}),
        "cfg_keys": len(mapcfg.get("k") or []),
        "rewards_v22": True,
    })
    _write_json(META_OUT, meta, indent=2)

    print("[4/4] 完成 -> %s" % DATA_DIR)
    _step("数据已写盘，正在刷新界面索引…", 90)
    return meta


def _write_json(path, obj, indent=None):
    """原子写 JSON：先写同目录 .tmp 再 os.replace。

    「立即同步」跑在 daemon 线程里，用户随时可能关窗；直接写正式文件被中断
    就会留下半截 JSON，下次启动 load_cache() 抛 JSONDecodeError，软件直接起不来。
    tmp 名必须带线程 id：同步和刷新可能被同时触发（都会落到 build(force=True)），
    两个线程用同一个只含 PID 的 tmp 名会交错写出坏 JSON 再被 os.replace 转正。
    """
    import threading
    tmp = "%s.%d.%d.tmp" % (path, os.getpid(), threading.get_ident())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False,
                  separators=None if indent else (",", ":"), indent=indent)
    os.replace(tmp, path)


def load_cache():
    with open(REWARDS_OUT, "r", encoding="utf-8") as fh:
        rewards = json.load(fh)
    maps = {}
    if os.path.exists(MAPS_OUT):
        with open(MAPS_OUT, "r", encoding="utf-8") as fh:
            maps = json.load(fh)
    meta = {}
    if os.path.exists(META_OUT):
        with open(META_OUT, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    return rewards, maps, meta


def load_infect() -> dict:
    """读取尸变参数表（地图名 -> {rand, ratio, time, tp}）。"""
    p = INFECT_OUT
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:                                          # noqa: BLE001
        return {}


if __name__ == "__main__":
    force = "--force" in sys.argv or "-f" in sys.argv
    m = build(force=force)
    print()
    print("地图数        : %s" % m.get("maps"))
    print("关卡总数      : %s" % m.get("stages"))
    print("通关云点 区间 : %s ~ %s（中位数 %s）" %
          (m.get("rankPasses_min"), m.get("rankPasses_max"), m.get("rankPasses_median")))
    print("尸变配置      : %s 张（随机尸变 %s 张）" % (m.get("infect"), m.get("infect_rand")))
    print("构建时间      : %s" % m.get("built_at_str"))

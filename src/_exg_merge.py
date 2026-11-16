# -*- coding: utf-8 -*-
"""EXG 图池「缺图」整合器 —— 把 EXG 表里有、FYS 地图库没有的那批图做进地图库，
并统一归入 `exg` 分类（`cat: "exg"`），同时产出一张样板条目。

口径（与 _check_pool.py 的 A 栏完全一致）：
  图池  = EXG 公开表 list.darkrp.cn:9000/ServerList/CurrentCs2MapStatus（只取 ze）
  地图库 = data/maps.json ∪ data/rewards.json （只取 ze）
  缺失  = 归一化名不在库里；且工坊ID / 中文名 / 归一化名都没在预览壳里出现过；
          且与库内名的相似度 < 0.90（≥0.90 且候选唯一的算同图异名，不算缺）

产出：
  _exg_missing.json       缺的那批（默认 99 张）：EXG 原生字段 + 工坊ID + 中文名
                          + 3D 预览 / 封面状态
  data/exg_local.json     `exg` 分类登记表（99 张的完整记录：exg 原生字段、
                          估算依据、参数与奖励、预览/封面状态）
  _sample_entry.json      样板条目（分类结构 + 条目结构的范本）

写库（`--write`）：
  data/maps_local.json    { 图名: 官方字段... + cat:"exg" }
  data/rewards_local.json { 图名: {"1": {关卡字段...}} }
  同时同步写入 data/maps.json / data/rewards.json（备份 .bak_<时间戳>），
  下次官方同步由 build_index 的本地补充层并回来。

⚠ 数值口径：这 99 张不在官方地图库里，**没有官方参数与奖励数据**。
   条目里的数值是「同 ZeTagStr + 同 Difficulty」的库内众数（样本 <5 退回全量），
   是估算值、不是官方数据，界面上以 `cat=exg` 徽标与说明标注，勿当作真实配置引用。

用法：
    python _exg_merge.py                  # 生成 _exg_missing.json + 分类登记表（不写库）
    python _exg_merge.py --check          # 只打印统计
    python _exg_merge.py --write          # 把 99 张 + 分类标记写进地图库
    python _exg_merge.py --verify         # 校验结构一致性（不通过则退出码 1）
    python _exg_merge.py --offline        # 不联网，用本地 EXG 快照
"""
import collections
import difflib
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)

import _check_pool as CP                                             # noqa: E402

EXG_MISS = os.path.join(HERE, "_exg_missing.json")
SAMPLE_F = os.path.join(HERE, "_sample_entry.json")
SIDECAR = os.path.join(DATA, "exg_local.json")
EXG_NAMES = os.path.join(DATA, "exg_mapnames.json")
SAMPLE_MAP = "ze_1_schizo"        # 样板图：思觉失调（缺图里排序靠前的一张）
CAT_KEY = "cat"                   # 分类字段名
CAT = "exg"                       # 分类取值
CAT_LABEL = "EXG 补充"
EXG_URL_DOC = "https://list.darkrp.cn:9000/ServerList/CurrentCs2MapStatus"
EXG_FIELDS = ("LastRun", "CooldownMinute", "Allow", "ZeTag", "ZeTagStr",
              "Difficulty", "DifficultyName", "Achievement10")


# ─────────────────────────────── 数据加载 ───────────────────────────────
def exg_table(offline=False):
    """EXG 公开表全量（保留原始字段）。"""
    arr = None
    if not offline:
        try:
            arr = json.loads(CP.http(CP.EXG_URL).decode("utf-8", "replace"))
        except Exception as ex:                                      # noqa: BLE001
            print("[warn] 在线 EXG 表拉取失败：%r" % (ex,))
    if not isinstance(arr, list):
        arr = json.load(io.open(os.path.join(HERE, "_exg_maps.json"),
                                encoding="utf-8"))
        print("[info] 回退本地快照 _exg_maps.json")
    return {str(it.get("Name")).lower(): it for it in arr if it.get("Name")}


def read_json(name):
    p = os.path.join(DATA, name)
    return json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else {}


# ─────────────────────────── 找出缺的那批 ───────────────────────────
def build(offline=False):
    exg = exg_table(offline)
    maps, rew = read_json("maps.json"), read_json("rewards.json")
    # ⚠ 必须先剔除本地补充层条目再算缺口：否则上一次写进去的 exg 图会把自己
    # 挤出缺口列表（数量越来越少），重跑就不幂等了。
    loc_m = set(_load(os.path.join(DATA, "maps_local.json")))
    loc_r = set(_load(os.path.join(DATA, "rewards_local.json")))
    # 转正（2026-11-09）：本地补充层的图一旦被官方正式收录（maps/rewards 出现
    # 同名**官方条目**——无 cat:"exg" 标记），本地估算条目就该退出 EXG 视图，
    # 不再登记、不再进缺口（首日转正 5 张：ze_exit8 / ze_fe8_sacred_stones /
    # ze_gugugaga_escape / ze_shadow_moses / ze_x_game_room）。不剔除的话：
    # ① 缺口清单永远含它们，登记表卡在旧张数；② EXG 视图挂着已转正图的
    # 估算参数误导玩家。判定用「键在 maps/rew 且条目无 exg 标记」——
    # 本地层自己并回来的条目带 cat:"exg"，不会误判。
    def _is_official(k):
        v = maps.get(k) or rew.get(k)
        return isinstance(v, dict) and v.get("cat") != "exg"

    retired = {k for k in (loc_m | loc_r) if _is_official(k)}
    loc_m -= retired
    loc_r -= retired
    loc_seen = {str(x).lower() for x in (loc_m | loc_r)} | retired
    for k in loc_m | loc_r:
        maps.pop(k, None)
        rew.pop(k, None)
    pids, pv_nrm, pv_cns, pv_cnmap = CP.payload()
    cv = CP.covers()

    libn = {}
    for k in list(maps) + list(rew):
        libn.setdefault(CP.norm(str(k)), str(k))

    def lib_of(nm):
        if nm in maps or nm in rew:
            return nm, "exact"
        nk = CP.norm(nm)
        if nk in libn:
            return libn[nk], "norm"
        return None, ""

    # 全量映射（取「同组众数」用）：EXG 图 → 库内配置
    pool_all = {}
    for k, it in exg.items():
        nm = str(it.get("Name"))
        if not nm.startswith("ze"):
            continue
        lk, _how = lib_of(nm)
        pool_all[nm.lower()] = {
            "name": nm, "exg": it,
            "cfg": maps.get(lk) if lk else None,
            "rewards": rew.get(lk) if lk else None,
        }

    # 缺的那批：口径同 _check_pool 的 A 栏
    miss, alias = [], []
    for k in sorted(pool_all):
        v = pool_all[k]
        nm, it = v["name"], v["exg"]
        nk = CP.norm(nm)
        if nk in libn:
            continue
        pid = str(it.get("WorkshopId") or "")
        cn = it.get("CnName") or ""
        hit, why = CP.classify(nm, pid, cn, pids, pv_nrm, pv_cns, pv_cnmap)
        # ⚠ 本地补充层里的图不能算「同图异名」：它们正是上面被主动从 maps/rew
        #   剔除的那批，而补图后又带着同一工坊 ID（乃至同名）出现在预览壳里，
        #   classify 会据此把它们踢出缺口 → 重跑 --write 就会把这批图从本地
        #   补充层删掉（实测 99 张会掉到 8 张，等于悄悄删库）。
        if hit and nm.lower() not in loc_seen:
            alias.append([nm, why, hit])
            continue
        near = difflib.get_close_matches(nk, list(libn), n=2, cutoff=0.90)
        if len(near) == 1:
            alias.append([nm, "≈名近", libn[near[0]]])
            continue
        miss.append({
            "name": nm,
            "cn": cn,
            "pid": pid,
            "exg": {f: it[f] for f in EXG_FIELDS if f in it},
            "preview": pid in pids,
            "cover": nm.lower() in cv,
        })

    meta = {"ts": int(time.time()), "ts_str": time.strftime("%F %T"),
            "offline": offline, "exg": len(pool_all), "lib": len(libn),
            "missing": len(miss), "alias": len(alias), "cat": CAT,
            "exg_fields": list(EXG_FIELDS),
            "have_preview": sum(1 for m in miss if m["preview"]),
            "have_cover": sum(1 for m in miss if m["cover"])}
    return miss, meta, pool_all, alias, maps, rew


# ─────────────────────────────── 结构定义 ───────────────────────────────
def field_union(maps):
    order, seen = [], set()
    for v in maps.values():
        if isinstance(v, dict):
            for k in v:
                if k not in seen:
                    seen.add(k)
                    order.append(k)
    return order


def stage_field_union(rew):
    order, seen = [], set()
    for v in rew.values():
        for st in (v.values() if isinstance(v, dict) else []):
            if isinstance(st, dict):
                for k in st:
                    if k not in seen:
                        seen.add(k)
                        order.append(k)
    return order


def group_rows(pool_all, target_exg):
    """取「同 ZeTagStr + 同 Difficulty」的、有库内配置的图；样本不足退回全量。"""
    def key_of(it):
        return (it.get("ZeTagStr"), it.get("Difficulty"))

    rows = [v for v in pool_all.values() if isinstance(v.get("cfg"), dict)]
    k = key_of(target_exg) if target_exg else None
    grp = [v for v in rows if key_of(v["exg"]) == k]
    return grp if len(grp) >= 5 else rows


# ─────────────────────────── 逐张估算参数与奖励 ───────────────────────────
def estimate(exg_item, pool_all, maps, rew):
    """按「同 ZeTag + 同难度」库内众数，估出 maps/rewards 两段结构。"""
    grp = group_rows(pool_all, exg_item)

    def kmodal(field):
        c = collections.Counter()
        for v in grp:
            cfg = v["cfg"]
            if isinstance(cfg, dict) and field in cfg:
                c[json.dumps(cfg[field])] += 1
        return json.loads(c.most_common(1)[0][0]) if c else None

    obj = {f: kmodal(f) for f in field_union(maps)}
    obj = {k: v for k, v in obj.items() if v is not None}

    def smodal(field):
        c = collections.Counter()
        for v in grp:
            rw = v["rewards"]
            if isinstance(rw, dict) and rw:
                k0 = sorted(rw, key=lambda x: int(x) if str(x).isdigit() else 0)[0]
                st = rw[k0]
                if isinstance(st, dict) and field in st:
                    c[json.dumps(st[field])] += 1
        return json.loads(c.most_common(1)[0][0]) if c else None

    stage = {f: smodal(f) for f in stage_field_union(rew)}
    stage = {k: v for k, v in stage.items() if v is not None}
    est = {"group": "%s / %s" % (exg_item.get("ZeTagStr") or "-",
                                 exg_item.get("DifficultyName") or "-"),
           "sample": len(grp)}
    return obj, {"1": stage}, est


def build_entries(miss, pool_all, maps, rew):
    """把 99 张缺图变成可入库的条目（含 exg 分类标记）。"""
    out = []
    for m in miss:
        exg_item = pool_all[m["name"].lower()]["exg"]
        obj, stage, est = estimate(exg_item, pool_all, maps, rew)
        out.append({
            "name": m["name"],
            "cn": m["cn"],
            "pid": m["pid"],
            "cat": CAT,
            "exg": m["exg"],
            "preview": m["preview"],
            "cover": m["cover"],
            "est": est,
            "obj": dict(obj, **{CAT_KEY: CAT}),
            "stage": stage,
        })
    return out


def make_sample(entries):
    rec = next((e for e in entries if e["name"] == SAMPLE_MAP), entries[0])
    return {
        "_note": ("样板条目：`cat` 是分类标记（全部 EXG 补充图都是 \"exg\"）；"
                  "其余字段与官方 data/maps.json / data/rewards.json 完全一致。"
                  "数值按「同 ZeTag + 同难度（%s）」分组取库内众数（%d 张图样本），"
                  "是估算值、非官方配置。以后新图入库照这个结构填。"
                  % (rec["est"]["group"], rec["est"]["sample"])),
        "map": rec["name"],
        "cn": rec["cn"],
        "pid": rec["pid"],
        "cat": CAT,
        "exg": rec["exg"],
        "est": rec["est"],
        "obj": rec["obj"],
        "stage": rec["stage"],
        "_fields": {"maps.json": list(rec["obj"]),
                    "rewards.json": list(rec["stage"]["1"])},
        "_cat": {"字段": CAT, "含义": CAT_LABEL, "张数": len(entries)},
    }


# ─────────────────────────────── 校验 ───────────────────────────────
def verify(entries, sample, maps, rew):
    want, want_s = field_union(maps), set(stage_field_union(rew))
    out = []

    out.append(("官方字段集非空", bool(want) and bool(want_s),
                "%d 字段 / %d 关卡字段" % (len(want), len(want_s))))
    # 每条：官方字段齐 + 只多一个 cat
    bad_f = [e["name"] for e in entries
             if set(e["obj"]) - {CAT_KEY} != set(want)]
    out.append(("每条 obj 字段集 = 官方字段集 + cat", not bad_f,
                "异常 %d 条 %s" % (len(bad_f), bad_f[:3])))
    bad_s = [e["name"] for e in entries
             if set(e["stage"]["1"]) != want_s]
    out.append(("每条 stage 字段集 = 官方关卡字段集", not bad_s,
                "异常 %d 条 %s" % (len(bad_s), bad_s[:3])))
    bad_c = [e["name"] for e in entries if e["cat"] != CAT]
    out.append(("每条分类标记均为 " + CAT, not bad_c, bad_c[:3]))
    bad_v = [e["name"] for e in entries if not e["obj"] or not e["stage"]["1"]]
    out.append(("每条数值都已估算出", not bad_v, bad_v[:3]))
    # 样板 == 其中一条
    match = next((e for e in entries if e["name"] == sample["map"]), None)
    out.append(("样板条目取自 99 张之内且内容一致",
                match is not None and match["obj"] == sample["obj"]
                and match["stage"] == sample["stage"], sample["map"]))
    # 官方记录里不应出现 exg 之外的多余字段（排除本地补充条目）
    local = set(json.load(io.open(os.path.join(DATA, "maps_local.json"),
                                  encoding="utf-8"))) \
        if os.path.exists(os.path.join(DATA, "maps_local.json")) else set()
    extra = set()
    for k, v in maps.items():
        if k in local or not isinstance(v, dict):
            continue
        extra |= set(v) - set(want)
    out.append(("官方 maps 记录无超出字段", not extra, str(extra)))
    return out


# ─────────────────────────────── 落盘 ───────────────────────────────
def _dump(path, obj, indent=None):
    tmp = path + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(
        json.dumps(obj, ensure_ascii=False, indent=indent,
                   **({} if indent else {"separators": (",", ":")})))
    os.replace(tmp, path)


def _load(path):
    if not os.path.exists(path):
        return {}
    try:
        return json.load(io.open(path, encoding="utf-8")) or {}
    except Exception:                                                # noqa: BLE001
        return {}


def write_sidecar(entries, meta, sample):
    """写 `exg` 分类登记表（本地侧，官方同步不碰）。"""
    doc = {
        "_meta": dict(meta, label=CAT_LABEL, source=EXG_URL_DOC,
                      sample=sample["map"], count=len(entries),
                      note=("EXG 公开图池里有、FYS 官方地图库里没有的 ze 图。"
                            "参数与奖励按「同 ZeTag+同难度」库内众数估算，"
                            "非官方数据；界面上以 exg 徽标标注。")),
        "cat": CAT,
        "entries": {e["name"]: e for e in entries},
    }
    _dump(SIDECAR, doc, indent=2)
    print("[ok] 分类登记表 → %s（%s %d 张）"
          % (SIDECAR, CAT, len(entries)))


def write_mapnames(entries):
    """把 EXG 表给的中文名落成译名表的兜底层（data/exg_mapnames.json）。

    优先级：用户自定义 > 云端热更 > 平台表 > 精选整名 > **本表** > 词根合成
    （见 mapnames.cn）。只补 EXG 表确实给了中文名的，缺的不硬凑。
    """
    got = {e["name"].lower(): e["cn"].strip()
           for e in entries if (e.get("cn") or "").strip()}
    _dump(EXG_NAMES, got, indent=1)
    print("[ok] EXG 中文名 → %s（%d/%d 张有译名）"
          % (EXG_NAMES, len(got), len(entries)))
    return got


def write_all(entries, meta, sample, do_write):
    miss = [{k: e[k] for k in ("name", "cn", "pid", "exg", "preview", "cover")}
            for e in entries]
    io.open(EXG_MISS, "w", encoding="utf-8").write(
        json.dumps({"meta": meta, "maps": miss}, ensure_ascii=False, indent=1))
    print("[ok] 缺图清单 → %s（%d 张）" % (EXG_MISS, len(entries)))
    io.open(SAMPLE_F, "w", encoding="utf-8").write(
        json.dumps(sample, ensure_ascii=False, indent=2))
    print("[ok] 样板条目 → %s（%s）" % (SAMPLE_F, sample["map"]))
    write_sidecar(entries, meta, sample)
    write_mapnames(entries)
    if not do_write:
        return

    stamp = time.strftime("%Y%m%d_%H%M%S")
    # ① 本地补充层：官方同步不碰，条目能长期留在库里
    mp = os.path.join(DATA, "maps_local.json")
    rp = os.path.join(DATA, "rewards_local.json")
    cur_m, cur_r = _load(mp), _load(rp)
    for e in entries:
        cur_m[e["name"]] = e["obj"]
        cur_r[e["name"]] = e["stage"]
    _dump(mp, cur_m, indent=2)
    _dump(rp, cur_r, indent=2)
    print("[ok] 本地补充层 maps_local %d 条 / rewards_local %d 条" %
          (len(cur_m), len(cur_r)))
    # ② 同时写进正式缓存，地图库页面立刻可见（下次官方同步由 ① 并回来）
    for fn, box in (("maps.json", cur_m), ("rewards.json", cur_r)):
        p = os.path.join(DATA, fn)
        if not os.path.exists(p):
            print("[skip] %s 不存在" % fn)
            continue
        shutil.copy2(p, "%s.bak_%s" % (p, stamp))
        obj = json.load(io.open(p, encoding="utf-8"))
        for e in entries:
            obj[e["name"]] = box[e["name"]]
        _dump(p, obj)
        print("[ok] 写入 %-15s %d 条（备份 %s.bak_%s）"
              % (fn, len(obj), fn, stamp))


def main():
    args = sys.argv[1:]
    miss, meta, pool_all, alias, maps, rew = build("--offline" in args)
    print("=" * 66)
    print("EXG %d 张 ze ｜ 地图库 %d 张 → 缺 %d 张（另 %d 张实为同图异名，已剔除）"
          % (meta["exg"], meta["lib"], meta["missing"], meta["alias"]))
    print("  其中已有 3D 预览 %d 张 ｜ 已有封面 %d 张"
          % (meta["have_preview"], meta["have_cover"]))
    print("=" * 66)
    for m in miss[:12]:
        print("   %-40s pid=%-11s 预览=%s 封面=%s %s"
              % (m["name"], m["pid"], "有" if m["preview"] else "无",
                 "有" if m["cover"] else "无", m["cn"]))
    if len(miss) > 12:
        print("   ... 其余 %d 张见 %s" % (len(miss) - 12, os.path.basename(EXG_MISS)))

    if "--check" in args:
        return 0

    entries = build_entries(miss, pool_all, maps, rew)
    sample = make_sample(entries)
    print("\n分类：%s（cat=%s）· %d 张" % (CAT_LABEL, CAT, len(entries)))
    print("样板条目：%s（%s）pid=%s  估算组=%s（%d 张样本）"
          % (sample["map"], sample["cn"] or "-", sample["pid"],
             sample["est"]["group"], sample["est"]["sample"]))
    print("  obj   =", json.dumps(sample["obj"], ensure_ascii=False))
    print("  stage =", json.dumps(sample["stage"], ensure_ascii=False))
    checks = verify(entries, sample, maps, rew)
    for nm, passed, detail in checks:
        print("  [%s] %s  %s" % ("PASS" if passed else "FAIL", nm, detail[:96]))

    write_all(entries, meta, sample, "--write" in args)
    if "--verify" in args and not all(p for _, p, _ in checks):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

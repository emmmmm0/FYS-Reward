# -*- coding: utf-8 -*-
"""地图库自检：本地索引 / 接口输出 vs GitHub 源仓库（fyscs/cs2）逐字段比对。

用法：
    python libcheck.py            # 完整自检（会下载 1.6MB 归档包，约 3~10 秒）
    python libcheck.py --offline  # 跳过 GitHub 比对，只查本地与接口

检查项：
    A. 接口层：真实 HTTP 路由 /api/maplib 的结构、记录数、缓存一致性
    B. 索引层：data/maps.json、data/rewards.json、data/infect.json 与 GitHub 归档包逐字段深比对
    C. 数据层：击退系数表、尸变参数表值域/覆盖、无奖励图、无击退图等边界情况
    D. 界面层：地图库用到的字段是否齐备、类型是否正常

报告输出：地图库自检报告.txt（终端同时打印）
"""
import json
import os
import sys
import tarfile
import threading
import time
import urllib.request
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

OFFLINE = "--offline" in sys.argv
TARBALL = "https://codeload.github.com/fyscs/cs2/tar.gz/refs/heads/master"
ROOT = "cs2-master/"
MAPS_PATH = ROOT + "2001/sharp/configs/maps.json"
REWARDS_PREFIX = ROOT + "2001/sharp/configs/rewards/"
CFG_PREFIX = ROOT + "2001/csgo/cfg/map-configs/"

OUT = []
FAIL = []


def say(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line, flush=True)


def check(name, ok, extra=""):
    say(("  [OK]  " if ok else "  [!!]  ") + name + (("  " + extra) if extra else ""))
    if not ok:
        FAIL.append(name + ("  " + extra if extra else ""))


# ────────────────────────── A. 接口层 ──────────────────────────
say("=" * 78)
say("A. 接口层：/api/maplib 真实路由")
say("=" * 78)

import build_index
import fys_reward_app
from http.server import ThreadingHTTPServer

rewards, maps, meta = build_index.load_cache()
kb_raw = json.load(open(os.path.join(HERE, "data", "knockback.json"), encoding="utf-8"))
kb = {str(k).strip().lower(): v for k, v in kb_raw.items()}
inf_disk = build_index.load_infect()
meta_disk = json.load(open(os.path.join(HERE, "data", "meta.json"), encoding="utf-8"))

# 用真实索引对象喂真实接口代码（State.engine 即 reward_server 模块，STATE 结构一致）
shim = SimpleNamespace(STATE={"maps": maps, "rewards": rewards, "knockback": kb,
                             "infect": inf_disk, "meta": meta_disk, "srv_cache": None})
fys_reward_app.State.engine = shim

recs = fys_reward_app.maplib_records()
check("记录数 == maps.json 条数", len(recs) == len(maps), "%d / %d" % (len(recs), len(maps)))
check("缓存命中（同索引再取结果相同）", fys_reward_app.maplib_records()[0] is recs[0])
shim.STATE["maps"] = dict(maps)                      # 换对象模拟同步后重建索引
check("索引变更后缓存自动失效", fys_reward_app.maplib_records() is not recs)
shim.STATE["maps"] = maps

srv = ThreadingHTTPServer(("127.0.0.1", 8792), fys_reward_app.make_handler())
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(0.3)
t0 = time.time()
with urllib.request.urlopen("http://127.0.0.1:8792/api/maplib", timeout=30) as r:
    payload = r.read()
dt = time.time() - t0
d = json.loads(payload)
check("HTTP 200 + ok=true", bool(d.get("ok")) and isinstance(d.get("maps"), list))
check("HTTP 记录数一致", len(d.get("maps") or []) == len(maps), str(len(d.get("maps") or [])))
check("HTTP 体积/耗时合理", len(payload) < 900 * 1024,
      "%.0f KB / %.2fs" % (len(payload) / 1024.0, dt))
check("meta 带索引构建时间", bool((d.get("meta") or {}).get("built_at")),
      str((d.get("meta") or {}).get("built_at")))
with urllib.request.urlopen("http://127.0.0.1:8792/api/prefs", timeout=10) as r:
    check("老接口 /api/prefs 未受影响", bool(json.loads(r.read()).get("ok")))
srv.shutdown()

# ────────────────────────── B. 与 GitHub 源比对 ──────────────────────────
say("")
say("=" * 78)
say("B. 索引层：data/*.json vs GitHub 源仓库")
say("=" * 78)

# 本地补充条目（样板图 / 新图入库，见 data/maps_local.json）不是上游数据，
# 比对时先剔除、单独报告，否则每次自检都会报「键集合不一致」。
_loc = build_index.load_local()
_lm = set(_loc["maps"]) & set(maps)
_lr = set(_loc["rewards"]) & set(rewards)
if _lm or _lr:
    _cats = {}
    for _k in _lm:
        _c = (maps.get(_k) or {}).get("cat") or "(未分类)"
        _cats[_c] = _cats.get(_c, 0) + 1
    say("  本地补充条目：maps %d 张 / rewards %d 张（跳过上游比对）"
        % (len(_lm), len(_lr)))
    say("     按分类：%s" % " · ".join(
        "%s %d 张" % (k, v) for k, v in sorted(_cats.items())))
    say("     %s" % ", ".join(sorted(_lm))[:200])
maps = {k: v for k, v in maps.items() if k not in _lm}
rewards = {k: v for k, v in rewards.items() if k not in _lr}

FIELDS = ["cooldown", "price", "nomination", "admin",
          "requiredOnline", "requiredPlayers", "certainTimes"]
SFIELDS = ["rankPasses", "rankDamage", "rankIntern",
           "econPasses", "econDamage", "econIntern"]
gh_maps, gh_rewards = {}, {}
gh_knock_names, stage_cnt_gh = [], 0
gh_infect = {}

if OFFLINE:
    say("  （--offline 跳过 GitHub 比对）")
else:
    tmp_tar = os.path.join(HERE, "data", "_check.tar.gz")
    say("  下载归档包 ...")
    try:
        t0 = time.time()
        req = urllib.request.Request(TARBALL, headers={"User-Agent": "fys-reward-indexer"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp_tar, "wb") as fh:
            total = 0
            while True:
                c = resp.read(1 << 20)
                if not c:
                    break
                fh.write(c)
                total += len(c)
        say("  完成 %.1f MB / %.1fs" % (total / 1048576.0, time.time() - t0))
        with tarfile.open(tmp_tar, "r:gz") as tf:
            for m in tf:
                if not m.isfile():
                    continue
                n = m.name
                if "knock" in os.path.basename(n).lower():
                    gh_knock_names.append(n)
                if n == MAPS_PATH:
                    gh_maps = build_index.parse_jsonc(
                        tf.extractfile(m).read().decode("utf-8", "replace"))
                elif n.startswith(REWARDS_PREFIX) and n.endswith(".jsonc"):
                    fh = tf.extractfile(m)
                    if fh is None:
                        continue
                    try:
                        gh_rewards[os.path.basename(n)[:-len(".jsonc")]] = \
                            build_index.parse_jsonc(fh.read().decode("utf-8", "replace"))
                    except Exception as e:                          # noqa: BLE001
                        say("  !! 解析失败", n, repr(e))
                elif n.startswith(CFG_PREFIX) and n.endswith(".cfg"):
                    bn = os.path.basename(n)[:-len(".cfg")]
                    if bn.startswith("_"):          # _template / _extreme_* 标记文件
                        continue
                    fh = tf.extractfile(m)
                    if fh is None:
                        continue
                    try:
                        d = build_index.parse_infect(fh.read().decode("utf-8", "replace"))
                        if d:
                            gh_infect[bn] = d
                    except Exception as e:                          # noqa: BLE001
                        say("  !! cfg 解析失败", n, repr(e))
        say("  GitHub: maps=%d rewards=%d 尸变 cfg=%d" %
            (len(gh_maps), len(gh_rewards), len(gh_infect)))
    except Exception as e:                                          # noqa: BLE001
        say("  !! 归档包下载失败：%r" % (e,))
        OFFLINE = True
    finally:
        try:
            os.remove(tmp_tar)
        except OSError:
            pass

    # -- 地图设置逐字段 --
    check("maps 键集合一致", set(gh_maps) == set(maps),
          "仅本地 %d / 仅远端 %d" % (len(set(maps) - set(gh_maps)),
                                    len(set(gh_maps) - set(maps))))
    diff = {}
    for f in sorted(set(gh_maps) & set(maps)):
        for k in FIELDS:
            if maps[f].get(k) != gh_maps[f].get(k):
                diff.setdefault(k, []).append((f, gh_maps[f].get(k), maps[f].get(k)))
    for k in FIELDS:
        bad = diff.get(k) or []
        check("地图设置 %s 一致" % k, not bad,
              "" if not bad else "不一致 %d 例，如 %s（源 %s → 本地 %s）" %
              (len(bad), bad[0][0], bad[0][1], bad[0][2]))
    extra_keys = {}
    for f in sorted(set(gh_maps) & set(maps)):
        if gh_maps[f] != maps[f]:
            for k in set(gh_maps[f]) | set(maps[f]):
                if gh_maps[f].get(k) != maps[f].get(k):
                    extra_keys[k] = extra_keys.get(k, 0) + 1
    check("maps.json 整条记录完全一致（含未显示字段）", not extra_keys,
          "" if not extra_keys else "差异字段 %s" % extra_keys)

    # -- 奖励配置逐字段 --
    check("rewards 键集合一致", set(gh_rewards) == set(rewards),
          "仅本地 %d / 仅远端 %d" % (len(set(rewards) - set(gh_rewards)),
                                    len(set(gh_rewards) - set(rewards))))
    sdiff, stage_cnt_local = {}, 0
    for f in sorted(set(gh_rewards) & set(rewards)):
        a, b = rewards[f], gh_rewards[f]
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        if set(a) != set(b):
            sdiff.setdefault("__stage_keys__", []).append((f, sorted(b), sorted(a)))
        stage_cnt_gh += len(b)
        stage_cnt_local += len(a)
        for st in set(a) & set(b):
            ra, rb = a[st], b[st]
            if not isinstance(ra, dict) or not isinstance(rb, dict):
                continue
            for k in SFIELDS:
                if ra.get(k) != rb.get(k):
                    sdiff.setdefault(k, []).append((f, st, rb.get(k), ra.get(k)))
    for k in SFIELDS:
        bad = sdiff.get(k) or []
        check("奖励字段 %s 一致" % k, not bad,
              "" if not bad else "不一致 %d 例，如 %s 第%s关（源 %s → 本地 %s）" %
              (len(bad), bad[0][0], bad[0][1], bad[0][2], bad[0][3]))
    check("关卡键集合一致", not (sdiff.get("__stage_keys__") or []),
          "" if not sdiff.get("__stage_keys__") else "例 %s" % (sdiff["__stage_keys__"][0],))
    check("关卡总数一致", stage_cnt_gh == stage_cnt_local,
          "GitHub %d / 本地 %d" % (stage_cnt_gh, stage_cnt_local))

    # -- 尸变参数逐字段（官方 map-configs/*.cfg） --
    infect_disk = inf_disk
    say("  尸变参数：本地 %d 条 / GitHub cfg %d 条" % (len(infect_disk), len(gh_infect)))
    check("infect 键集合与仓库 cfg 一致", set(gh_infect) == set(infect_disk),
          "仅本地 %d / 仅远端 %d" % (len(set(infect_disk) - set(gh_infect)),
                                    len(set(gh_infect) - set(infect_disk))))
    idiff = {}
    for f in sorted(set(gh_infect) & set(infect_disk)):
        for k in ("rand", "ratio", "time", "tp"):
            if gh_infect[f].get(k) != infect_disk[f].get(k):
                idiff.setdefault(k, []).append((f, gh_infect[f].get(k), infect_disk[f].get(k)))
    for k in ("rand", "ratio", "time", "tp"):
        bad = idiff.get(k) or []
        check("尸变字段 %s 一致" % k, not bad,
              "" if not bad else "不一致 %d 例，如 %s（源 %s → 本地 %s）" %
              (len(bad), bad[0][0], bad[0][1], bad[0][2]))
    gh_rand = sum(1 for v in gh_infect.values() if v.get("rand") == 1)
    check("随机尸变张数与 meta.infect_rand 一致", meta_disk.get("infect_rand") == gh_rand,
          "GitHub %s / meta %s" % (gh_rand, meta_disk.get("infect_rand")))
    check("meta.infect 条数一致", meta_disk.get("infect") == len(gh_infect),
          "GitHub %d / meta %s" % (len(gh_infect), meta_disk.get("infect")))

    # -- meta 统计 --
    vals = []
    for cfg in gh_rewards.values():
        if isinstance(cfg, dict):
            for st_cfg in cfg.values():
                if isinstance(st_cfg, dict) and st_cfg.get("rankPasses") is not None:
                    try:
                        vals.append(int(st_cfg["rankPasses"]))
                    except Exception:                                # noqa: BLE001
                        pass
    vals.sort()
    gh_stat = {"maps": len(gh_rewards), "stages": stage_cnt_gh,
               "rankPasses_min": vals[0] if vals else None,
               "rankPasses_max": vals[-1] if vals else None,
               "rankPasses_median": vals[len(vals) // 2] if vals else None}
    for k, v in gh_stat.items():
        check("meta.%s 与 GitHub 计算值一致" % k, meta_disk.get(k) == v,
              "GitHub %s / meta %s" % (v, meta_disk.get(k)))
    check("meta.source 指向该仓库", meta_disk.get("source") == TARBALL,
          str(meta_disk.get("source")))

check("meta.built_at 已记录", bool(meta_disk.get("built_at")),
      "索引构建于 %s" % meta_disk.get("built_at_str"))

# ────────────────────────── C. 数据层边界情况 ──────────────────────────
say("")
say("=" * 78)
say("C. 数据层：击退表与边界情况")
say("=" * 78)
extra_kb = sorted(set(kb) - set(maps))
no_rew = sorted(set(maps) - set(rewards))
no_kb = sorted(set(maps) - set(kb))
say("  仓库内击退同源文件：%s" % (gh_knock_names[:3] if gh_knock_names
                              else "无 → 该表来自官方直播助手，非本仓库"))
check("击退表条数合理", 600 <= len(kb) <= 720, "%d 条" % len(kb))
bad_vals = [(k, v) for k, v in kb.items()
            if not isinstance(v, (int, float)) or not (0.1 <= float(v) <= 3.0)]
check("击退系数值域 0.1~3.0", not bad_vals, "" if not bad_vals else str(bad_vals[:3]))
check("击退表键全为小写地图名", all(k == k.lower() for k in kb))
cover = len(set(kb) & set(maps))
say("  覆盖：%d / %d 张图有击退系数（%.1f%%）" % (cover, len(maps), cover * 100.0 / len(maps)))
say("  击退表多出、地图池未收录的键（%d 个，界面不展示，属官方数据残留）：" % len(extra_kb))
for k in extra_kb[:10]:
    say("      %-34s 击退=%-4s 有奖励配置=%s" % (k, kb[k], k in rewards))
check("多出的击退键不进入界面记录", not (set(extra_kb) & {r["f"] for r in recs}))
say("  有地图设置但无奖励配置的图（%d 个）：%s" % (len(no_rew), no_rew))
say("  无击退系数的图（%d 个）：%s" % (len(no_kb), no_kb))

# -- 尸变参数表（data/infect.json）--
inf = inf_disk
inf_rand = sorted(f for f, v in inf.items() if v.get("rand") == 1)
no_inf = sorted(set(maps) - set(inf))
check("尸变表条数合理", 650 <= len(inf) <= 750, "%d 条" % len(inf))
bad_rand = [(f, v.get("rand")) for f, v in inf.items() if v.get("rand") not in (0, 1, None)]
check("rand 取值只有 0/1", not bad_rand, "" if not bad_rand else str(bad_rand[:3]))
check("rand 字段无缺失", all("rand" in v for v in inf.values()))
bad_ratio = [(f, v["ratio"]) for f, v in inf.items()
             if v.get("ratio") is not None and not (1 <= v["ratio"] <= 64)]
check("尸变比值域 1~64", not bad_ratio, "" if not bad_ratio else str(bad_ratio[:3]))
bad_time = [(f, v["time"]) for f, v in inf.items()
            if v.get("time") is not None and not (10 <= v["time"] <= 90)]
check("尸变倒计时值域 10~90 秒", not bad_time, "" if not bad_time else str(bad_time[:3]))
check("随机尸变张数合理（10~60）", 10 <= len(inf_rand) <= 60, "%d 张" % len(inf_rand))
cover_i = len(set(inf) & set(maps))
say("  覆盖：%d / %d 张图有尸变配置（%.1f%%）" % (cover_i, len(maps), cover_i * 100.0 / len(maps)))
say("  随机尸变（rand=1）的图 %d 张：%s" % (len(inf_rand), ", ".join(inf_rand[:10])))
say("  无尸变配置的图（%d 个，详情页显示“未收录”）：%s" %
    (len(no_inf), ", ".join(no_inf[:12])))

# ────────────────────────── D. 界面字段完整性 ──────────────────────────
say("")
say("=" * 78)
say("D. 地图库界面字段完整性")
say("=" * 78)
need = {"f", "c", "k", "s", "i", "st"}
bad_shape = [r["f"] for r in recs if not need <= set(r)]
check("每条记录含 f/c/k/s/i/st", not bad_shape, "" if not bad_shape else str(bad_shape[:5]))
bad_i = [r["f"] for r in recs if r["i"] is not None and not isinstance(r["i"], dict)]
check("i 字段为对象或 None", not bad_i, "" if not bad_i else str(bad_i[:5]))
mismatch_i = [r["f"] for r in recs if r["i"] != inf.get(r["f"])]
check("记录的 i 与 infect.json 逐条一致", not mismatch_i,
      "" if not mismatch_i else str(mismatch_i[:5]))
rec_rand = sum(1 for r in recs if r["i"] and r["i"].get("rand"))
pool_rand = sorted(set(inf_rand) & set(maps))
check("界面可筛选的随机尸变张数 == 尸变表∩地图池", rec_rand == len(pool_rand),
      "界面 %d / 池内 %d / 表 %d" % (rec_rand, len(pool_rand), len(inf_rand)))
out_pool_rand = sorted(set(inf_rand) - set(maps))
if out_pool_rand:
    say("  随机尸变但未进地图池的图（%d 个，界面不展示，同击退表残留）：%s" %
        (len(out_pool_rand), ", ".join(out_pool_rand)))
bad_s = [r["f"] for r in recs if not isinstance(r["s"], dict) or
         not {"cd", "pr", "nm", "ad", "ro", "rp", "tm"} <= set(r["s"])]
check("s 字段齐全（cd/pr/nm/ad/ro/rp/tm）", not bad_s, "" if not bad_s else str(bad_s[:5]))
bad_st = [r["f"] for r in recs if any(len(row) != 7 for row in r["st"])]
check("每关奖励行长度=7", not bad_st, "" if not bad_st else str(bad_st[:5]))
nonum = []
for r in recs:
    if not isinstance(r["k"], (int, float, type(None))):
        nonum.append((r["f"], "k", r["k"]))
    for key in ("cd", "pr", "ro", "rp"):
        v = r["s"].get(key)
        if not isinstance(v, (int, float, type(None))):
            nonum.append((r["f"], key, v))
check("数值字段无字符串污染", not nonum, "" if not nonum else str(nonum[:5]))
nulld = {k: sum(1 for r in recs if r["s"].get(k) is None) for k in ("cd", "pr", "ro", "rp")}
check("cooldown / price 无缺失", nulld["cd"] == 0 and nulld["pr"] == 0, str(nulld))
no_cn = sum(1 for r in recs if not (r["c"] or "").strip())
say("  译名覆盖：%d / %d（%d 张无译名，只能用地图名搜索）" %
    (len(recs) - no_cn, len(recs), no_cn))
check("地图名唯一（无重复记录）", len(recs) == len({r["f"] for r in recs}))
low = [r["f"] for r in recs if r["f"] != r["f"].lower()]
check("地图名统一小写（与服务器广播对齐）", not low, "" if not low else str(low[:3]))
check("搜索字段可匹配（f / c 均为字符串）",
      all(isinstance(r["f"], str) and isinstance(r["c"], str) for r in recs))

say("")
say("  抽样对照（本地记录 ← GitHub 源）：")
for f in ("ze_samosbor", "ze_2012_p", "ze_8bit"):
    if f not in gh_maps and not OFFLINE:
        continue
    r = [x for x in recs if x["f"] == f][0]
    src = gh_maps.get(f) or {}
    rew = gh_rewards.get(f) if gh_rewards else rewards.get(f, {})
    say("    %-18s 冷却 %s/%s 价格 %s/%s 关数 %d/%d 击退 %s" %
        (f, r["s"]["cd"], src.get("cooldown", "—"), r["s"]["pr"], src.get("price", "—"),
         len(r["st"]), len(rew or {}), r["k"]))

say("")
say("=" * 78)
if FAIL:
    say("自检结果：%d 项异常" % len(FAIL))
    for x in FAIL:
        say("  - " + x)
else:
    say("自检结果：全部通过（本地索引与 GitHub 源仓库一致）")
say("=" * 78)

rep = os.path.join(HERE, "地图库自检报告.txt")
open(rep, "w", encoding="utf-8").write("\n".join(OUT) + "\n")
print("report:", rep)

# -*- coding: utf-8 -*-
"""图池 ⇄ 地图库 双向核对（v2：多重身份判定，先扣掉命名变体噪音）。

图池  = EXG 公开表 `list.darkrp.cn:9000/ServerList/CurrentCs2MapStatus`（只取 ze）
地图库 = `data/maps.json` ∪ `data/rewards.json`（只取 ze）

判定优先级（判定「这张图其实已经有了」用）：
  ① 工坊 ID 命中（最硬 —— 同一张图换个名字发布也认得出来）
  ② 中文名命中（EXG 的 CnName ↔ 预览壳 payload 的 cn）
  ③ 归一化名命中（去 _p/_cs2/_z/_v2 这类版本变体后缀）
  ④ 归一化名相似度 ≥ 0.90 且候选唯一 → 记为「疑似同图异名」，不算真缺

输出：
  A. 图池有、地图库没有
  B. 地图库有、图池没有

用法：python _check_pool.py [--offline] [--json]
"""
import difflib
import io
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GH = os.path.join(HERE, "_ghcrawl")
EXG_URL = "https://list.darkrp.cn:9000/ServerList/CurrentCs2MapStatus"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"

# 已知「版本/分组」变体后缀 —— 只剥这些词，别剥 lite/soft/easy 这类真·区分词
VAR = r"(p|cs2|l|z|m|fys|x|ex|re|ii|old|fix|fix\d|remake|recompile|night|demo|" \
      r"v\d+([_.]\d+)*|b\d+|a\d+|xyy|new)"
SUF = re.compile(r"_" + VAR + r"$")


def http(u, t=25):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    return op.open(req, timeout=t).read()


def norm(n):
    n = re.sub(r"[^a-z0-9_]+", "_", str(n).lower().strip()).strip("_")
    while True:
        m = SUF.search(n)
        if not m or len(n) - len(m.group(0)) < 6:
            return n
        n = n[:m.start()]


def pool(offline=False):
    if offline:
        d = json.load(io.open(os.path.join(HERE, "_newmap_src.json"), encoding="utf-8"))
        out = {}
        for k, v in d.items():
            if k == "_ts" or v.get("src") not in ("exg", "exg-local"):
                continue
            out[k] = {"name": k, "cn": v.get("cn") or "", "pid": str(v.get("pid") or "")}
        return out, "本地快照"
    arr = json.loads(http(EXG_URL).decode("utf-8", "replace"))
    out = {}
    for it in arr if isinstance(arr, list) else []:
        n = it.get("Name") or ""
        if n.startswith("ze"):
            out[n.lower()] = {"name": n, "cn": it.get("CnName") or "",
                              "pid": str(it.get("WorkshopId") or "")}
    return out, "EXG 在线表"


def library():
    out = {}
    for fn in ("maps.json", "rewards.json"):
        p = os.path.join(HERE, "data", fn)
        if not os.path.exists(p):
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        for k in (d if isinstance(d, list) else list(d.keys())):
            k = str(k)
            if k.startswith("ze"):
                out.setdefault(k, fn.split(".")[0])
    return out


def payload():
    """预览壳索引：pid→(名,中文) / 归一化名集合 / 中文名集合。"""
    sys.path.insert(0, GH)
    import _add_missing_maps as A                                    # noqa: E402
    d, _ = A.load_payload(os.path.join(GH, "preview_payload.b64"))
    pids, nrm, cns, nm_cn = {}, set(), {}, {}
    for k, v in d["maps"].items():
        pid = k.rsplit("/", 1)[-1]
        nm, cn = v.get("m") or "", v.get("cn") or ""
        pids[pid] = nm
        nrm.add(norm(nm))
        if cn:
            cns.setdefault(cn, nm)
            nm_cn[nm.lower()] = cn
    return pids, nrm, cns, nm_cn


def covers():
    d = os.path.join(HERE, "cover")
    return ({f[:-4].lower() for f in os.listdir(d) if f.endswith(".jpg")}
            if os.path.isdir(d) else set())


def classify(name, pid, cn, pids, pv_nrm, pv_cns, pv_cnmap):
    """返回 (已有哪些身份命中 or None, 说明)。"""
    if pid and pid in pids:
        return "pid", pids[pid]
    if cn and cn in pv_cns:
        return "cn", pv_cns[cn]
    if norm(name) in pv_nrm:
        return "name", ""
    return None, ""


def main():
    offline = "--offline" in sys.argv
    P, tag = pool(offline)
    lib = library()
    pids, pv_nrm, pv_cns, pv_cnmap = payload()
    cv = covers()

    libn = {}
    for k in lib:
        libn.setdefault(norm(k), k)
    pv_nrm_pool = {norm(k) for k in P}

    # A：图池有 —— 扣掉「地图库里其实有（只是名字不同）」
    A, A_alias = [], []
    for k in sorted(P):
        v = P[k]
        nk = norm(v["name"])
        if nk in libn:
            continue
        # 地图库里有同工坊ID或同中文名的条目吗？（用 src 表反查）
        hit, why = classify(v["name"], v["pid"], v["cn"], pids, pv_nrm, pv_cns, pv_cnmap)
        if hit:
            A_alias.append((v["name"], why, hit))
            continue
        near = difflib.get_close_matches(nk, list(libn), n=2, cutoff=0.90)
        if len(near) == 1:
            A_alias.append((v["name"], "≈名近", libn[near[0]]))
            continue
        A.append({"名": v["name"], "中文": v["cn"], "pid": v["pid"],
                  "预览": v["pid"] in pids, "封面": v["name"].lower() in cv})

    # B：地图库有 —— 扣掉图池里其实有（异名）
    B, B_alias = [], []
    for k in sorted(lib):
        if k.lower() in P:
            continue
        nk = norm(k)
        if nk in pv_nrm_pool:
            B_alias.append((k, "≈名近", ""))
            continue
        near = difflib.get_close_matches(nk, list(pv_nrm_pool), n=2, cutoff=0.90)
        if len(near) == 1:
            B_alias.append((k, "≈名近", near[0]))
            continue
        B.append({"名": k, "来源": lib[k],
                  "预览": nk in pv_nrm, "封面": k.lower() in cv})

    print("=" * 70)
    print("图池 %s：%d 张 ze ｜ 地图库：%d 张 ze ｜ 预览壳：%d 张 ze"
          % (tag, len(P), len(lib), len(pids)))
    print("=" * 70)
    print("\nA. 图池有、地图库没有：%d 张（另 %d 张实为异名，已剔除）"
          % (len(A), len(A_alias)))
    for x in A:
        print("   %-42s pid=%-12s 预览=%s 封面=%s  %s"
              % (x["名"], x["pid"] or "-", "有" if x["预览"] else "无",
                 "有" if x["封面"] else "无", x["中文"]))
    print("\nB. 地图库有、图池没有：%d 张（另 %d 张实为异名，已剔除）"
          % (len(B), len(B_alias)))
    for x in B:
        print("   %-42s 预览=%s 封面=%s  [%s]"
              % (x["名"], "有" if x["预览"] else "无", "有" if x["封面"] else "无", x["来源"]))

    if A_alias:
        print("\n【A 中判定为异名的】")
        for n, why, h in A_alias[:40]:
            print("   %-42s %s → %s" % (n, why, h))
    if B_alias:
        print("\n【B 中判定为异名的】")
        for n, why, h in B_alias[:40]:
            print("   %-42s %s → %s" % (n, why, h))

    if "--json" in sys.argv:
        out = {"ts": time.strftime("%F %T"), "图池": len(P), "地图库": len(lib),
               "图池有库没有": A, "库有图池没有": B,
               "异名_A": [[n, w, h] for n, w, h in A_alias],
               "异名_B": [[n, w, h] for n, w, h in B_alias]}
        p = os.path.join(HERE, "_check_pool.json")
        io.open(p, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
        print("\n报告 → %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

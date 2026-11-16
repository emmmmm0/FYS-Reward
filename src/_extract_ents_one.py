# -*- coding: utf-8 -*-
"""单张地图：从本地工坊 VPK 重提「完整实体」（带 kv 属性 + cx 触发连接）。

背景：首轮抓取部分图只存了 {cn,o,nm,c,h}（精简格式，无属性/连接）。
本脚本按 keep_kv=True 重跑单张，覆盖 E:\\FYS-cache\\_ents_raw\\<pid>.json。

用法：
    python _extract_ents_one.py 3559330245
    python _extract_ents_one.py ze_backrooms_insomnia
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_ghcrawl"))
os.environ["FYS_ENTS_FULL"] = "1"                       # 提取器带上 kv/cx
import _build_meshes as BM                              # noqa: E402


def name_map():
    m = {}
    for p in ("_ghcrawl/_wsmap.json", "_ghcrawl/_workshop_maps.json",
              "_missing_ws_all.json", "data/exg_mapnames.json",
              "_newmap_src.json"):
        fp = os.path.join(HERE, p)
        if not os.path.exists(fp):
            continue
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
        except Exception:                                 # noqa: BLE001
            continue
        if p.endswith("_wsmap.json"):
            d = d.get("mapping") or {}
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            if isinstance(v, dict):
                v = v.get("item") or v.get("pid")
            v = str(v)
            if v.isdigit():
                m.setdefault(v, k)
    return m


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    arg = sys.argv[1].strip()
    nm = name_map()
    rev = {}
    for pid, name in nm.items():
        rev.setdefault(name, pid)
    pid = arg if arg.isdigit() else rev.get(arg)
    if not pid:
        print("找不到工坊 ID：%s" % arg)
        return 1
    name = nm.get(pid, arg)

    local = BM.workshop_vpk_map()
    vpk = local.get(pid)
    if not vpk:
        print("本地没有 %s (%s) 的 VPK，路径：%s" % (name, pid, os.path.dirname(BM.ENTS_DIR)))
        return 2
    print("图名 %s  pid %s" % (name, pid))
    print("VPK  %s" % vpk)

    t = time.time()
    ents = BM.extract_ents_from_vpk({"vpk": vpk, "stem": vpk}, name, keep_kv=True)
    if not ents:
        print("提取为空")
        return 3
    nk = sum(1 for e in ents if e.get("kv"))
    nc = sum(1 for e in ents if e.get("cx"))
    nt = sum(1 for e in ents if str(e.get("cn", "")).startswith("trigger_"))
    ep = os.path.join(BM.ENTS_DIR, pid + ".json")
    tmp = ep + ".tmp"
    os.makedirs(os.path.dirname(ep), exist_ok=True)
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(ents, separators=(",", ":")))
    os.replace(tmp, ep)
    print("✔ 实体 %d ｜ 带属性 %d ｜ 带连接 %d ｜ 触发区 %d ｜ %.1fs"
          % (len(ents), nk, nc, nt, time.time() - t))
    print("已写入 %s" % ep)
    return 0


if __name__ == "__main__":
    sys.exit(main())

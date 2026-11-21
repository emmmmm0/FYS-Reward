# -*- coding: utf-8 -*-
"""从风云社官方仓库（fyscs/cs2 的 2001/csgo/cfg/map-configs/）同步两张参数表：

  data/knockback.json  地图 -> ze_knockback_scale（击退系数）
  data/infect.json     地图 -> {rand, ratio, time, tp}（尸变参数）

为什么要它：旧表是从「蜜柚直播助手」的 knockback_db.json 抄的快照（2026-09-21，
692 条），官方 cfg 一直在更新（2026-11-21 对比：43 张新增、16 张改值），鬼泣等
新图在旧表里查不到击退。本脚本直接从源头全量提取，官方值优先、本地多余键保留
（跟 *_local.json 的补充层思路一致）。

用法：
    python fys-reward/_sync_mapcfg.py            # 同步 + 打印差异报告
    python fys-reward/_sync_mapcfg.py --dry      # 只打印差异，不写文件
"""
import argparse
import io
import json
import os
import re
import tarfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TARBALL = "https://codeload.github.com/fyscs/cs2/tar.gz/refs/heads/master"

RX_KB = re.compile(r'ze_knockback_scale\s+"?([\d.]+)"?')
RX_INFECT = {
    "rand": re.compile(r'ze_infect_sort_by_immunity\s+"?(true|false)"?'),
    "ratio": re.compile(r'ze_infect_mother_ratio\s+"?(\d+)"?'),
    "time": re.compile(r'ze_infect_mother_spawn_time\s+"?(\d+)"?'),
    "tp": re.compile(r'ze_infect_teleport_to_spawn\s+"?(true|false)"?'),
}


def pull():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(TARBALL, timeout=180) as r:
        data = r.read()
    tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    kb, inf, no_kb = {}, {}, []
    for n in tf.getnames():
        if "/map-configs/" not in n or not n.endswith(".cfg"):
            continue
        f = tf.extractfile(n)
        if not f:
            continue
        txt = f.read().decode("utf-8", "replace")
        key = n.split("/")[-1][:-4].strip().lower()
        m = RX_KB.findall(txt)
        if m:
            kb[key] = float(m[0])
        else:
            no_kb.append(key)
        vals = {}
        for k, rx in RX_INFECT.items():
            mm = rx.findall(txt)
            if mm:
                v = mm[0]
                if k in ("rand", "tp"):
                    vals[k] = (v == "true") if k == "tp" else (v != "true")
                    # rand=1 纯随机 = sort_by_immunity 关闭(false)
                else:
                    vals[k] = int(v)
        if vals:
            inf[key] = vals
    return kb, inf, no_kb


def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        return {}


def norm(d):
    return {str(k).strip().lower(): v for k, v in d.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    kb_new, inf_new, no_kb = pull()
    print("官方 map-configs：%d 张有击退 / %d 张有尸变参数 / %d 张 cfg 无 ze_knockback_scale"
          % (len(kb_new), len(inf_new), len(no_kb)))

    kb_path = os.path.join(HERE, "data", "knockback.json")
    inf_path = os.path.join(HERE, "data", "infect.json")
    kb_old = norm(load(kb_path))
    inf_old = norm(load(inf_path))

    for tag, old, new in (("击退", kb_old, kb_new), ("尸变", inf_old, inf_new)):
        add = {k: v for k, v in new.items() if k not in old}
        chg = {k: (old[k], v) for k, v in new.items()
               if k in old and old[k] != v}
        extra = sorted(k for k in old if k not in new)
        print("[%s] 官方 %d 条：新增 %d、改值 %d、官方已删但本地保留 %d"
              % (tag, len(new), len(add), len(chg), len(extra)))
        if add:
            print("   新增样例:", list(sorted(add.items()))[:8])
        if chg:
            print("   改值样例:", list(sorted(chg.items()))[:8])

    merged_kb = {**kb_old, **kb_new}
    merged_inf = {**inf_old, **inf_new}
    maps = norm(load(os.path.join(HERE, "data", "maps.json")))
    # 过滤非地图条目：_template.cfg（官方模板）、_extreme_*.cfg（同图极难难度
    # 变体，不是独立图，地图池里没有这个键）。规则：留「地图池里有」或「旧表
    # 已有」的键，其余剔除（2026-11-21 发现 _template/_extreme_ 混进官方 735）。
    keep = lambda d: {k: v for k, v in d.items() if k in maps or k in kb_old or k in inf_old}
    merged_kb = keep(merged_kb)
    merged_inf = keep(merged_inf)
    for tag, mg in (("击退", merged_kb), ("尸变", merged_inf)):
        miss = sorted(m for m in maps if m not in mg)
        print("地图池 %d 张：%s 覆盖 %d，仍缺 %d（官方没配的图，界面显示 —）"
              % (len(maps), tag, len(mg), len(miss)))

    if args.dry:
        print("（--dry 未写文件）")
        return
    for p, d in ((kb_path, merged_kb), (inf_path, merged_inf)):
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
        print("已写", p, len(d), "条")


if __name__ == "__main__":
    main()

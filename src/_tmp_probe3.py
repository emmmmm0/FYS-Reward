# -*- coding: utf-8 -*-
import os, io, re, json, sys

ACF = r"E:\FYS-cache\steamdl\steamapps\workshop\appworkshop_730.acf"
s = io.open(ACF, encoding="utf-8", errors="replace").read()
print("=== acf 大小 %d 字节 ===" % len(s))
# 顶层区块
for m in re.finditer(r'^\t"([^"]+)"\s*$', s, re.M):
    print("  区块:", m.group(1))
# WorkshopItemsInstalled / Details 条目数
for key in ["WorkshopItemsInstalled", "WorkshopItemDetails"]:
    i = s.find('"%s"' % key)
    if i < 0:
        print("%s: 无" % key)
        continue
    seg = s[i:i + 400000]
    ids = re.findall(r'^\s*"(\d{6,})"\s*$', seg, re.M)
    print("%s: %d 条" % (key, len(ids)))
# 是否包含我们缺的 34 张
missing = json.load(io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "_ghcrawl", "_missing_ids.json"), encoding="utf-8"))
mids = [m["pid"] for m in missing]
hit = [p for p in mids if ('"%s"' % p) in s]
print("34 张缺图里，acf 中有记录的：%d 张" % len(hit))
print("  前 10 个:", hit[:10])

print()
print("=== 本机 Steam 工坊目录 ===")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ghcrawl"))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ghcrawl"))
import _build_meshes as BM
wdirs = BM.steam_workshop_dirs()
wdirs.append(os.path.join(BM.DL_ROOT, "steamapps", "workshop", "content", "730"))
for w in wdirs:
    exists = os.path.isdir(w)
    n = len(os.listdir(w)) if exists else 0
    print("  %-64s %s (%d 项)" % (w, "OK" if exists else "不存在", n))
    if exists:
        local = set(os.listdir(w))
        inter = [p for p in mids if p in local]
        if inter:
            print("      含缺图 %d 张: %s" % (len(inter), inter[:8]))

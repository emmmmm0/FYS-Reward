# -*- coding: utf-8 -*-
import os, time, json, io, re

DL = r"E:\FYS-cache\steamdl"
print("=== %s 树（深度<=3）===" % DL)
for dp, ds, fs in os.walk(DL):
    rel = os.path.relpath(dp, DL)
    depth = 0 if rel == "." else rel.count(os.sep) + 1
    if depth > 3:
        ds[:] = []
        continue
    tot = sum(os.path.getsize(os.path.join(dp, f)) for f in fs)
    print("  " * depth + "[%s] %d 文件 %.2f MB" % (rel, len(fs), tot / 1048576.0))
    if depth <= 3:
        for f in sorted(fs)[:6]:
            p = os.path.join(dp, f)
            print("  " * (depth + 1) + "%-44s %9.1f KB  %s" % (
                f[:44], os.path.getsize(p) / 1024.0,
                time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))))
        if len(fs) > 6:
            print("  " * (depth + 1) + "... 共 %d 个" % len(fs))

print()
print("=== 缺地形的工坊 ID 清单 ===")
ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
GH = os.path.join(ROOT, "fys-reward", "_ghcrawl")
man = json.load(io.open(os.path.join(GH, "_meshes", "_manifest.json"), encoding="utf-8"))
have = set(k.split("/")[-1] for k in man)
trk = json.load(io.open(os.path.join(GH, "maptracking_preview3d.json"), encoding="utf-8"))
missing = []
for key, v in trk["maps"].items():
    pid = key.split("/")[-1]
    if pid not in have:
        missing.append({"pid": pid, "key": key, "cn": v.get("cn", "")})
print("缺 %d 张" % len(missing))
io.open(os.path.join(GH, "_missing_ids.json"), "w", encoding="utf-8").write(
    json.dumps(missing, ensure_ascii=False, indent=1))
for m in missing:
    print("  %-12s %-34s %s" % (m["pid"], m["key"].split("/")[1], m["cn"]))

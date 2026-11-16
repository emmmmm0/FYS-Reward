# -*- coding: utf-8 -*-
import os, re, io, time, shutil

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
GH = os.path.join(ROOT, "fys-reward", "_ghcrawl")

print("=== 缓存目录 ===")
for d in [r"E:\FYS-cache", r"E:\FYS-cache\steamdl", r"E:\FYS-cache\steamcmd",
          r"E:\FYS-cache\steamcmd2", r"E:\FYS-cache\_raw", r"E:\FYS-cache\_ents_raw",
          r"E:\FYS-cache\_meshes_raw", r"E:\FYS-cache\_meshes"]:
    if os.path.isdir(d):
        items = os.listdir(d)
        tot = 0
        for it in items:
            p = os.path.join(d, it)
            try:
                if os.path.isfile(p):
                    tot += os.path.getsize(p)
            except Exception:
                pass
        print("%-30s %6d 项 %9.1f MB  改于 %s" % (
            d, len(items), tot / 1048576.0,
            time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(d)))))
    else:
        print("%-30s 不存在" % d)

print()
print("=== 磁盘 ===")
for drv in ["C:\\", "E:\\"]:
    try:
        t, u, f = shutil.disk_usage(drv)
        print("%s 总 %.1f GB / 剩 %.1f GB" % (drv, t / 2**30, f / 2**30))
    except Exception as e:
        print(drv, e)

print()
print("=== _build_meshes.py 入口 ===")
s = io.open(os.path.join(GH, "_build_meshes.py"), encoding="utf-8").read()
lines = s.splitlines()
for i, l in enumerate(lines, 1):
    if re.match(r"^(def |class |if __name__)", l) or "argv" in l or "--" in l:
        print("%4d %s" % (i, l.rstrip()[:170]))

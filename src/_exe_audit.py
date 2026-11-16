# -*- coding: utf-8 -*-
"""分析打包 exe 的归档构成：找出体积大头，判断哪些是不必要的依赖。"""
import os
import sys
import collections

EXE = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\云朵小铺-FYS通关奖励看板\FYS-Reward.exe"

try:
    from PyInstaller.archive.readers import CArchiveReader
except Exception as e:
    print("需要 PyInstaller 环境：", e)
    sys.exit(1)

a = CArchiveReader(EXE)
print("== 顶层类型分布 ==")
bytype = collections.Counter()
tot = 0
for name, (dpos, dlen, ulen, flag, typcd) in a.toc.items():
    bytype[typcd] += ulen
    tot += ulen
for t, n in bytype.most_common():
    print("  %s: %.2f MB" % (t, n / 1048576.0))
print("  合计（未压缩内容）: %.2f MB  |  exe 实际 %.2f MB"
      % (tot / 1048576.0, os.path.getsize(EXE) / 1048576.0))

print("\n== 单个最大的 40 项 ==")
rows = sorted(((ulen, name, typcd) for name, (dp, dl, ulen, fl, typcd) in a.toc.items()),
              reverse=True)
for ulen, name, typcd in rows[:40]:
    print("  %9.2f KB  [%s] %s" % (ulen / 1024.0, typcd, name))

print("\n== 按顶层目录/包归类（前 30）==")
groups = collections.Counter()
for name, (dp, dl, ulen, fl, typcd) in a.toc.items():
    if typcd == "z":
        continue
    parts = name.replace("\\", "/").split("/")
    key = parts[0] if len(parts) > 1 else ("<root>:" + name.split(".")[-1][:24])
    groups[key] += ulen
for k, v in groups.most_common(30):
    print("  %8.2f MB  %s" % (v / 1048576.0, k))

print("\n== 是否包含这些大库 ==")
names = " ".join(a.toc.keys()).lower()
for lib in ["numpy", "scipy", "pandas", "matplotlib", "tkinter", "test", "unittest",
            "pydoc", "lib2to3", "setuptools", "pip", "PIL", "pythonnet", "clr_loader",
            "webview", "requests", "urllib3", "certifi", "lxml", "cv2", "PyQt",
            "sqlite3", "distutils", "email", "xml", "asyncio", "multiprocessing"]:
    print("  %-16s %s" % (lib, "有" if lib in names else "-"))

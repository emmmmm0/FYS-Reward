# -*- coding: utf-8 -*-
"""精确列出归档里「可剔除的无用条目」：XML 文档 / 非 x64 的 WebView2Loader / numpy 链。"""
import os
import re
import sys

EXE = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\云朵小铺-FYS通关奖励看板\FYS-Reward.exe"

from PyInstaller.archive.readers import CArchiveReader

a = CArchiveReader(EXE)
toc = a.toc
print("归档条目数 %d" % len(toc))


def show(pat, label):
    hit = [(n, v[2]) for n, v in toc.items() if re.search(pat, n, re.I)]
    tot = sum(u for _, u in hit)
    print("\n== %s  命中 %d 条  合计 %.2f MB ==" % (label, len(hit), tot / 1048576.0))
    for n, u in sorted(hit, key=lambda x: -x[1])[:16]:
        print("  %9.1f KB  %s" % (u / 1024.0, n))


show(r"\.xml$", "XML 文档")
show(r"webview2loader", "WebView2Loader")
show(r"^numpy", "numpy（顶层）")
show(r"numpy\.libs|openblas|scipy", "OpenBLAS / scipy")
show(r"python\.runtime|pythonnet|clr_loader", "pythonnet / clr_loader")

print("\n== webview 包内所有 dll ==")
for n, v in sorted(toc.items()):
    if re.search(r"\.dll$", n, re.I) and "webview" in n.lower():
        print("  %9.1f KB  %s" % (v[2] / 1024.0, n))

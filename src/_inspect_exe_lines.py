# -*- coding: utf-8 -*-
"""从发行 exe 里取出 fys_reward_app 的 code object，打印关键函数的首个行号。

用途：玩家报错栈里只有行号（entry/main/run_overlay_child），拿它反查是哪个版本。
用法：python _inspect_exe_lines.py <exe路径>
"""
import marshal
import os
import sys
import tempfile

from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader


def find_pyz(exe):
    c = CArchiveReader(exe)
    toc = c.toc
    names = list(toc.keys()) if hasattr(toc, "keys") else [e[0] for e in toc]
    for n in names:
        if n.lower().endswith(".pyz") or "PYZ" in n.upper():
            return c, n
    raise SystemExit("归档里找不到 PYZ：%r" % names[:10])


def walk(code, path="", out=None):
    if out is None:
        out = {}
    name = getattr(code, "co_name", "?")
    full = (path + "." + name) if path else name
    out[full] = getattr(code, "co_firstlineno", -1)
    for k in getattr(code, "co_consts", ()):
        if hasattr(k, "co_code"):
            walk(k, full, out)
    return out


def main():
    exe = sys.argv[1]
    c, pyz_name = find_pyz(exe)
    # 主脚本以 typecode 's' 直接放在 CArchive（marshal 过的 code object），不在 PYZ 里
    raw = c.extract("fys_reward_app")
    if isinstance(raw, tuple):
        raw = raw[1]
    code = marshal.loads(raw)
    table = walk(code)
    print("== 文件：%s ==" % exe)
    for fn in ("entry", "main", "run_overlay_child"):
        for k, v in table.items():
            if k == fn or k.endswith("." + fn):
                print("  def %-22s 首个行号 = %d" % (fn, v))
    hit = [k for k in table if k in ("entry", "main", "run_overlay_child")]
    if not hit:
        print("  ! 未找到目标函数，已 dump 顶层函数：")
        for k in sorted(table)[:40]:
            print("    ", k, table[k])


if __name__ == "__main__":
    main()

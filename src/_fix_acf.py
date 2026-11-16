# -*- coding: utf-8 -*-
"""清掉 appworkshop_730.acf 里那 34 张缺图的残留记录，让 steamcmd 从头干净下载。

只动这一个文件；先备份，临时文件 + os.replace 原子替换，全程 bytes 操作（零编码风险）。
默认 dry-run，加 --apply 才写盘。
"""
import os, io, re, json, time, sys, shutil

ACF = r"E:\FYS-cache\steamdl\steamapps\workshop\appworkshop_730.acf"
GH = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\fys-reward\_ghcrawl"
APPLY = "--apply" in sys.argv

missing = json.load(io.open(os.path.join(GH, "_missing_ids.json"), encoding="utf-8"))
mids = set(m["pid"] for m in missing)
print("目标 %d 个工坊 ID" % len(mids))

b = open(ACF, "rb").read()
print("原 acf %d 字节" % len(b))

BLK = re.compile(rb'\n\t\t"(\d+)"\s*\n\t\t\{(?:[^{}]|\n)*?\n\t\t\}', re.S)

i_inst = b.find(b'"WorkshopItemsInstalled"')
i_det = b.find(b'"WorkshopItemDetails"')
print("区块位置 Installed=%d Details=%d" % (i_inst, i_det))

removed_inst, removed_det = [], []
def repl(m):
    pid = m.group(1).decode()
    if pid in mids:
        (removed_inst if m.start() < i_det else removed_det).append(pid)
        return b""
    return m.group(0)

new = BLK.sub(repl, b)
print("删除 Installed 条目 %d 个 | Details 条目 %d 个" % (len(removed_inst), len(removed_det)))
print("新 acf %d 字节（-%.1f KB）" % (len(new), (len(b) - len(new)) / 1024.0))

# ---- 结构自检：大括号平衡 + 关键区块仍在 ----
for name in [b'"WorkshopItemsInstalled"', b'"WorkshopItemDetails"', b'"AppWorkshop"']:
    print("  含 %-28s %s" % (name.decode(), name in new))
print("  大括号 %d 开 / %d 闭" % (new.count(b"{"), new.count(b"}")))
if new.count(b"{") != new.count(b"}"):
    print("!! 大括号不平衡，放弃"); sys.exit(2)
if i_det > 0:
    seg = new[new.find(b'"WorkshopItemsInstalled"'):new.find(b'"WorkshopItemDetails"')]
    n_inst_after = len(re.findall(rb'\n\t\t"\d+"\s*\n\t\t\{', seg))
    seg2 = new[new.find(b'"WorkshopItemDetails"'):]
    n_det_after = len(re.findall(rb'\n\t\t"\d+"\s*\n\t\t\{', seg2))
    print("  删后条目数 Installed=%d Details=%d" % (n_inst_after, n_det_after))

if not APPLY:
    print()
    print("[dry-run] 未写盘。加 --apply 执行。")
    sys.exit(0)

bak = ACF + ".bak-" + time.strftime("%m%d-%H%M%S")
shutil.copy2(ACF, bak)
print("备份 →", bak)

tmp = ACF + ".tmp"
with open(tmp, "wb") as fh:
    fh.write(new)
os.replace(tmp, ACF)
print("已写回。核对：现 %d 字节" % os.path.getsize(ACF))

# 复核
b2 = open(ACF, "rb").read()
left = [p for p in mids if p.encode() in b2]
print("仍残留的目标 ID：%d 个 %s" % (len(left), left[:6]))

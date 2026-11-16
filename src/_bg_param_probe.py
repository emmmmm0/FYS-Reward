# -*- coding: utf-8 -*-
"""背景素材压缩参数实验：在「实际显示尺寸」下找体积与画质的平衡点。

各图真实用途（见 ui_page.py bgCSS / applyHeroes / .heroBanner）：
  pat / pat_dark  平铺底纹 background-size: 400px（CSS px），且被 56% 白纱盖住
  run / winner / girl  ① hero 横幅（height:170px + object-fit:cover）
                       ② 整幅 cover 氛围底（被 82% 白纱盖住，只剩 18% 可见度）
  mascot          卡片角标 background-size: 290px auto + 80~86% 白纱
  sticker_*       侧栏贴纸 contain，260x400 内
"""
import base64
import io
import os
from PIL import Image

SRC = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\_themeart"

# key: (源文件, 现用宽, 现用q, 备选[(宽,q), ...])
CASES = [
    ("pat",       "pat.jpg",      900, 72, [(900, 72), (760, 68), (640, 66), (560, 64)]),
    ("pat_dark",  "pat_dark.jpg", 900, 72, [(900, 72), (760, 68), (640, 66), (560, 64)]),
    ("run",       "run.jpg",     1200, 74, [(1200, 74), (1200, 66), (1000, 68), (880, 66)]),
    ("winner",    "winner.jpg",  1200, 74, [(1200, 74), (1200, 66), (1000, 68), (880, 66)]),
    ("girl",      "girl.jpg",    1000, 74, [(1000, 74), (1000, 66), (860, 68), (760, 66)]),
    ("mascot",    "mascot.jpg",   720, 74, [(720, 74), (560, 70), (460, 68), (400, 66)]),
]

print("%-10s %-22s %10s %10s %8s" % ("key", "参数(宽,q)", "raw KB", "base64 KB", "相对现版"))
print("-" * 74)
tot_now = tot_best = 0
for key, fn, w0, q0, cands in CASES:
    p = os.path.join(SRC, fn)
    im0 = Image.open(p).convert("RGB")
    base = None
    rows = []
    for w, q in cands:
        im = im0
        if im.size[0] != w:
            im = im.resize((w, max(1, round(im.size[1] * w / im.size[0]))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        raw = buf.getvalue()
        b64 = int(len(raw) * 4 / 3)
        if base is None:
            base = b64
            tot_now += b64
        rows.append((w, q, raw, b64, im.size))
    for i, (w, q, raw, b64, size) in enumerate(rows):
        tag = "  ← 现版" if i == 0 else ""
        print("%-10s %-22s %8.1f %9.1f %7.0f%%%s"
              % (key if i == 0 else "", "%dx%d q%d" % (size[0], size[1], q),
                 len(raw) / 1024.0, b64 / 1024.0, b64 * 100.0 / base, tag))
    tot_best += rows[-1][3]
    print()

print("合计 base64：现版 %.0f KB → 最小档 %.0f KB" % (tot_now / 1024.0, tot_best / 1024.0))

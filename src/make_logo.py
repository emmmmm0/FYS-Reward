# -*- coding: utf-8 -*-
"""把 云朵小铺-可爱游戏Logo.png 的主标做成 app.ico + 界面内嵌 logo。

步骤：
1. 定位主标（黄色描边圆角方块）——按描边色检测边界
2. 裁剪 + 圆角透明蒙版（半径按视觉 0.22）
3. 输出 app.ico（16/24/32/48/64/128/256）
4. 输出 logo_embed.png（64px，供 ui_page.py base64 内嵌）
"""
import base64
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(ROOT), "云朵小铺-可爱游戏Logo.png")
OUT_ICO = os.path.join(ROOT, "app.ico")
OUT_PNG = os.path.join(ROOT, "logo_embed.png")

img = Image.open(SRC).convert("RGBA")
W, H = img.size
print("source:", W, "x", H)

# ── 1. 找主标：描边黄 #FFD98C 行/列直方图，取密集连续区间（排除色点等小元素）──
px = img.load()
target = (0xFF, 0xD9, 0x8C)


def near(c, t, tol=26):
    return abs(c[0] - t[0]) <= tol and abs(c[1] - t[1]) <= tol and abs(c[2] - t[2]) <= tol


row_cnt = [0] * H
col_cnt = [0] * W
for y in range(0, int(H * 0.72)):
    for x in range(0, int(W * 0.55)):
        if near(px[x, y], target):
            row_cnt[y] += 1
            col_cnt[x] += 1
# 主标描边是细线框：只有顶/底边框的「行」和左/右边框的「列」呈峰值
rows_hit = [y for y in range(int(H * 0.72)) if row_cnt[y] > 500]
cols_hit = [x for x in range(int(W * 0.55)) if col_cnt[x] > 400]
print("row peaks:", rows_hit[:3], "...", rows_hit[-3:] if rows_hit else [])
ry0 = rows_hit[0]
ry1 = rows_hit[-1]
rx0 = cols_hit[0]
rx1 = cols_hit[-1]
print("main bbox:", rx0, ry0, rx1, ry1)
if rx1 < 0 or ry1 < 0:
    sys.exit("未找到主标描边")

# ── 2. 裁剪（含描边外 2px 余量）+ 转正方形 ──
pad = 2
box = (max(0, rx0 - pad), max(0, ry0 - pad),
       min(W, rx1 + 1 + pad), min(H, ry1 + 1 + pad))
crop = img.crop(box)
cw, ch = crop.size
side = min(cw, ch)
# 居中取正方形
crop = crop.crop(((cw - side) // 2, (ch - side) // 2,
                  (cw + side) // 2, (ch + side) // 2))
crop = crop.resize((512, 512), Image.LANCZOS)

# 圆角透明蒙版（描边方块自身圆角 ≈ 边长 22%）
mask = Image.new("L", (512, 512), 0)
d = ImageDraw.Draw(mask)
d.rounded_rectangle((0, 0, 511, 511), radius=112, fill=255)
crop.putalpha(mask)
crop.save(os.path.join(ROOT, "data", "logo_main.png"))
print("main logo saved")

# ── 3. app.ico：多尺寸，小图用 LANCZOS 缩放 ──
sizes = [16, 24, 32, 48, 64, 128, 256]
crop.save(OUT_ICO, format="ICO", sizes=[(s, s) for s in sizes])
print("app.ico saved:", os.path.getsize(OUT_ICO), "bytes")

# ── 4. 界面内嵌 64px PNG → base64 ──
small = crop.resize((64, 64), Image.LANCZOS)
small.save(OUT_PNG, format="PNG", optimize=True)
b64 = base64.b64encode(open(OUT_PNG, "rb").read()).decode()
with open(os.path.join(ROOT, "data", "_logo_b64.txt"), "w") as fh:
    fh.write(b64)
print("embed png:", os.path.getsize(OUT_PNG), "bytes, b64 len:", len(b64))

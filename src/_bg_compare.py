# -*- coding: utf-8 -*-
"""生成「背景素材压缩前后」的真实显示条件对比图。

不是把两张原图并排贴，而是按 ui_page.py 的真实 CSS 渲染出**玩家实际看到的画面**：
  ① 底纹：400px 平铺 + 56% 白纱（模拟 .main 背景压在浅粉底上）
  ② 角标：290px + 83% 白纱（模拟 .card 右上角水印）
  ③ 横幅：1030px 宽 × 170px 高，object-fit:cover + object-position:center 64%
每行左=旧版素材，右=新版素材，同一显示条件。
"""
import base64
import io
import re
import os

import numpy as np
from PIL import Image, ImageDraw

BASE = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\fys-reward"
OUT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\底图压缩对比.png"


def load_bg(path):
    """从 bg_assets.py 里读出 BG_DATA（显式用 SourceFileLoader —— .bak 后缀没法自动推断 loader）。"""
    import importlib.util
    from importlib.machinery import SourceFileLoader
    name = "bgmod_" + re.sub(r"\W", "_", os.path.basename(path))
    loader = SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m.BG_DATA


def decode(uri):
    body = uri.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(body))).convert("RGB")


def veil(im, rgba):
    a = rgba[3]
    base = np.asarray(im).astype(np.float32)
    col = np.array(rgba[:3], dtype=np.float32)
    return Image.fromarray(np.clip(base * (1 - a) + col * a, 0, 255).astype(np.uint8))


def tile_on(im, size, page, veil_rgba, bg=(255, 250, 252)):
    """按 background-size:size 平铺到 page，再叠纱。"""
    plane = Image.new("RGB", page, bg)
    tw, th = size
    for y in range(0, page[1], th):
        for x in range(0, page[0], tw):
            plane.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
    return veil(plane, veil_rgba)


def hero(im, W, H, pos):
    sw = W
    sh = max(1, round(im.size[1] * sw / im.size[0]))
    if sh < H:
        im = im.resize((sw, H), Image.LANCZOS)
        sh = H
    else:
        im = im.resize((sw, sh), Image.LANCZOS)
    top = int((sh - H) * pos)
    return im.crop((0, top, sw, top + H))


old = load_bg(os.path.join(BASE, "bg_assets.py.bak"))
new = load_bg(os.path.join(BASE, "bg_assets.py"))

PAD, LH, GAP = 16, 200, 14
W = 1030
rows = []

# ① 底纹
a = tile_on(decode(old["pat"]), (400, 368), (W // 2 - PAD, 150), (255, 253, 254, 0.56))
b = tile_on(decode(new["pat"]), (400, 368), (W // 2 - PAD, 150), (255, 253, 254, 0.56))
rows.append(("① 底纹 400px 平铺 + 56% 白纱", a, b, old["pat"], new["pat"]))

# ② 角标（卡片底色 #fff 上）
card = Image.new("RGB", (W // 2 - PAD, 150), (255, 255, 255))
ma = decode(old["mascot"]); mb = decode(new["mascot"])


def stamp(im, canvas):
    h = round(290 * im.size[1] / im.size[0])
    s = im.resize((290, h), Image.LANCZOS)
    c = canvas.copy()
    c.paste(s, (canvas.size[0] - 290 + 40, -40))     # 对应 right -46px top -54px
    return veil(c, (255, 255, 255, 0.83))


rows.append(("② 卡片角标 290px + 83% 白纱", stamp(ma, card), stamp(mb, card),
             old["mascot"], new["mascot"]))

# ③ 横幅
ha = hero(decode(old["run"]), W - PAD * 2, 170, 0.64)
hb = hero(decode(new["run"]), W - PAD * 2, 170, 0.64)
rows.append(("③ 服务器页横幅 1030×170 center 64%", ha, hb, old["run"], new["run"]))

# ④ 横幅（winner，地图库）
wa = hero(decode(old["winner"]), W - PAD * 2, 132, 0.54)
wb = hero(decode(new["winner"]), W - PAD * 2, 132, 0.54)
rows.append(("④ 地图库横幅 1030×132 center 54%", wa, wb, old["winner"], new["winner"]))


def ssim(a, b):
    x = np.asarray(a.convert("L")).astype(np.float64)
    y = np.asarray(b.convert("L")).astype(np.float64)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    win, vals = 8, []
    for i in range(0, x.shape[0] - win + 1, win):
        for j in range(0, x.shape[1] - win + 1, win):
            bx = x[i:i + win, j:j + win].ravel(); by = y[i:i + win, j:j + win].ravel()
            mx, my = bx.mean(), by.mean()
            cxy = float(np.mean((bx - mx) * (by - my)))
            vals.append(((2 * mx * my + C1) * (2 * cxy + C2)) /
                        ((mx * mx + my * my + C1) * (bx.var() + by.var() + C2)))
    return float(np.mean(vals))


def psnr(a, b):
    x = np.asarray(a).astype(np.float32); y = np.asarray(b).astype(np.float32)
    mse = float(np.mean((x - y) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


total_h = PAD + len(rows) * (LH + GAP + 34) + 60
canvas = Image.new("RGB", (W, total_h), (245, 242, 248))
d = ImageDraw.Draw(canvas)
try:
    from PIL import ImageFont
    FONTP = r"C:\Windows\Fonts\msyh.ttc"
    font = ImageFont.truetype(FONTP, 13)
except Exception:
    font = None
y = PAD + 24
d.text((PAD, PAD - 12),
       '背景素材压缩前后对比 —— 每行左侧=旧素材，右侧=新素材（同一真实显示条件；绿框=新）',
       fill=(60, 60, 80), font=font)
for title, ia, ib, ua, ub in rows:
    kb_o = len(ua) // 1024
    kb_n = len(ub) // 1024
    s, p = ssim(ia, ib), psnr(ia, ib)
    d.text((PAD, y), "%s    旧 %dKB → 新 %dKB    SSIM %.4f   PSNR %.1fdB"
           % (title, kb_o, kb_n, s, p), fill=(70, 70, 90), font=font)
    y += 22
    canvas.paste(ia, (PAD, y))
    canvas.paste(ib, (PAD + W // 2, y))
    d.rectangle([PAD, y, PAD + W // 2 - PAD - 2, y + ia.size[1]], outline=(210, 205, 220))
    d.rectangle([PAD + W // 2, y, W - PAD, y + ib.size[1]], outline=(150, 190, 160))
    y += LH + GAP

canvas.save(OUT, "PNG")
print("->", OUT, canvas.size)

# 汇总
print("\n== 压缩前后体积 ==")
tot_o = tot_n = 0
for k in ("pat", "pat_dark", "run", "winner", "mascot", "girl",
          "sticker_zombie", "sticker_cloud", "sticker_cat"):
    o = len(old[k]) // 1024
    n = len(new[k]) // 1024
    tot_o += o; tot_n += n
    print("   %-16s %5d KB → %5d KB   (%+.0f%%)" % (k, o, n, (n - o) * 100.0 / o))
print("   %-16s %5d KB → %5d KB   (%+.0f%%)" % ("合计", tot_o, tot_n, (tot_n - tot_o) * 100.0 / tot_o))

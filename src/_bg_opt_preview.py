# -*- coding: utf-8 -*-
"""生成「卡片右上角吉祥物水印」的优化对比图（当前 / 调参 / 换透明底贴纸）。

按 ui_page.py 的 bgCSS() 真实参数复刻：
  当前：白纱 linear-gradient(rgba(255,255,255,.80), rgba(255,255,255,.86))
        + mascot  background-size: 290px auto, background-position: right -46px top -54px
只用于出对比图，不进软件。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, RAD = 900, 240, 16
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bgdump")
OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "底图优化对比.png"))
CARD_BG = (255, 253, 254)


def _font(size):
    for f in ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc",
              "C:/Windows/Fonts/simhei.ttf"):
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                pass
    return ImageFont.load_default()


def rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    return m


def veil(a_top, a_bot):
    """从 top 到 bottom 线性插值的白色纱层（CSS 里盖在图片上方的那层）。"""
    a = np.linspace(a_top, a_bot, H).reshape(H, 1)
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = 255, 253, 254
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def sticker(path, box_w, box_h, right, bottom, fade_left=0, project_off=None,
            veil_ab=None):
    """把一张图按「右/下」对齐贴到卡片上，可选左侧淡出、可选再压白纱。"""
    card = Image.new("RGBA", (W, H), CARD_BG + (255,))
    im = Image.open(path).convert("RGBA")
    im = im.resize((box_w, box_h), Image.LANCZOS)
    if fade_left:
        al = np.array(im.split()[3]).astype(np.float32)
        ramp = np.clip(np.arange(box_w) / float(fade_left), 0, 1)
        al = (al * ramp.reshape(1, -1)).astype(np.uint8)
        im.putalpha(Image.fromarray(al, "L"))
    x = W - box_w - right
    y = H - box_h - bottom
    if project_off:                       # 允许向右/上溢出（截断）
        dx, dy = project_off
        x += dx
        y += dy
    card.alpha_composite(im, (int(x), int(y)))
    if veil_ab:
        card.alpha_composite(veil(*veil_ab))
    card.putalpha(rounded_mask(W, H, RAD))
    return card


def build():
    rows = []

    # ① 现状：完全按现有 CSS 复刻（290px、右溢 46、上溢 54、白纱 .80→.86）
    rows.append(("① 现状（= 你截图里的样子）",
                 "白纱 80%~86% + 图 290px、右溢 46px、上溢 54px → 主角被裁掉、只剩一团灰影",
                 sticker(os.path.join(SRC, "mascot.jpg"), 290, 261, -46, 0,
                         project_off=(0, -54), veil_ab=(0.80, 0.86))))

    # ② 调参：缩小 + 移到右下 + 降白纱 + 左侧渐隐（仍用同一张图）
    rows.append(("② 调参：缩小 / 移到右下 / 降白纱 / 左侧渐隐",
                 "图 210px、右下角、白纱 64%~72%、左边缘 120px 渐隐 → 看得清、不脏、避开数值区",
                 sticker(os.path.join(SRC, "mascot.jpg"), 210, 193, 16, -26,
                         fade_left=120, veil_ab=(0.64, 0.72))))

    # ③ 换透明底贴纸（推荐）：sticker_cloud.webp 本身就是透明底，无需白纱压
    rows.append(("③ 换透明底贴纸（推荐）：云朵精灵 · 抱龙晶",
                 "透明底 webp 直接贴在右下角、不再铺白纱 → 边缘干净、颜色饱和、主体完整",
                 sticker(os.path.join(SRC, "sticker_cloud.webp"), 150, 158, 22, -12,
                         veil_ab=(0.10, 0.14))))

    pad, gap, label_h = 28, 26, 52
    cw, ch = W + pad * 2, (H + label_h + gap) * len(rows) + pad
    canvas = Image.new("RGB", (cw, ch), (243, 244, 248))
    d = ImageDraw.Draw(canvas)
    f_t, f_s = _font(21), _font(15)
    y = pad // 2
    for title, sub, img in rows:
        d.text((pad, y), title, font=f_t, fill=(38, 34, 46))
        d.text((pad, y + 30), sub, font=f_s, fill=(122, 116, 132))
        y += label_h
        canvas.paste(img, (pad, y), img)
        y += H + gap
    canvas.save(OUT)
    print("已生成", OUT, canvas.size)


if __name__ == "__main__":
    build()

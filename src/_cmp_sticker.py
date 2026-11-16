# -*- coding: utf-8 -*-
"""三款侧栏贴纸在亮底 / 夜幕暗底下的对比图（检验抠图边缘与暗色可读性）。"""
import base64
import io
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bg_assets import BG_DATA                                   # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "验证截图-界面巡检", "背景08-贴纸三款对比.png")
KEYS = [("sticker_cloud", "云朵精灵（默认）"), ("sticker_cat", "小白猫"), ("sticker_zombie", "小僵尸")]
LIGHT = (255, 246, 250)
DARK = (26, 25, 32)


def from_uri(u):
    return Image.open(io.BytesIO(base64.b64decode(u.split(",", 1)[1]))).convert("RGBA")


CELL_W, CELL_H = 240, 260
canvas = Image.new("RGB", (CELL_W * 3, CELL_H * 2 + 4), (250, 250, 252))
for row, bg in enumerate((LIGHT, DARK)):
    for col, (key, _nm) in enumerate(KEYS):
        tile = Image.new("RGB", (CELL_W, CELL_H), bg)
        im = from_uri(BG_DATA[key])
        im.thumbnail((CELL_W - 44, CELL_H - 44), Image.LANCZOS)
        tile.paste(im, ((CELL_W - im.size[0]) // 2, (CELL_H - im.size[1]) // 2), im)
        canvas.paste(tile, (col * CELL_W, row * (CELL_H + 4)))

canvas.save(OUT)
print("->", OUT, canvas.size)
print("上排=亮色主题底，下排=夜幕护眼底；列序：", " / ".join(n for _, n in KEYS))

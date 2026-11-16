# -*- coding: utf-8 -*-
"""生成程序图标 app.ico（不依赖任何第三方库，手写 ICO/BMP 格式）。

图形取意「云点」：暖土色圆角底 + 白色圆环币形，中置小方块。
输出多尺寸：16 / 24 / 32 / 48 / 64 / 128 / 256
"""
import os
import struct

BG = (0x2B, 0x50, 0xA8, 0xFF)      # BGRA —— 品牌色 #A8502B
FG = (0xFF, 0xFF, 0xFF, 0xFF)      # 白色
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")


def rounded(x, y, w, h, r):
    """点 (x,y) 是否落在圆角矩形内。"""
    if x < 0 or y < 0 or x >= w or y >= h:
        return False
    if r <= 0:
        return True
    cx = r if x < r else (w - 1 - r if x > w - 1 - r else x)
    cy = r if y < r else (h - 1 - r if y > h - 1 - r else y)
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= r * r


def make_pixels(size):
    """返回自上而下的 BGRA 行列表。"""
    r = max(2, int(size * 0.22))          # 圆角半径
    cx = cy = (size - 1) / 2.0
    ring_out = size * 0.34                 # 圆环外半径
    ring_in = size * 0.24                  # 圆环内半径
    core = size * 0.10                     # 中心方块半宽
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            if not rounded(x, y, size, size, r):
                row.append((0, 0, 0, 0))   # 透明
                continue
            dx, dy = x - cx, y - cy
            d = (dx * dx + dy * dy) ** 0.5
            if ring_in <= d <= ring_out:
                row.append(FG)             # 圆环
            elif abs(dx) <= core and abs(dy) <= core:
                row.append(FG)             # 中心方块
            else:
                row.append(BG)             # 底色
        rows.append(row)
    return rows


def bmp_image(size):
    """构造 ICO 内部的 BMP：BITMAPINFOHEADER + 自下而上的 BGRA + AND 掩码。"""
    rows = make_pixels(size)
    header = struct.pack(
        "<IiiHHIIiiII",
        40,            # biSize
        size,          # biWidth
        size * 2,      # biHeight（含掩码，故为 2 倍）
        1,             # biPlanes
        32,            # biBitCount
        0,             # biCompression = BI_RGB
        0, 0, 0, 0, 0,
    )
    body = bytearray()
    for y in range(size - 1, -1, -1):       # 自下而上
        for (b, g, r, a) in rows[y]:
            body += bytes((b, g, r, a))
    # AND 掩码：32bpp 下不生效，但格式要求存在，每行 4 字节对齐
    stride = ((size + 31) // 32) * 4
    body += bytes(stride * size)
    return header + bytes(body)


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [(s, bmp_image(s)) for s in sizes]

    out = bytearray()
    out += struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for s, data in images:
        w = 0 if s >= 256 else s
        h = 0 if s >= 256 else s
        out += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for _, data in images:
        out += data

    with open(OUT, "wb") as fh:
        fh.write(out)
    print("已生成 %s  (%d 字节, 含 %d 个尺寸)" % (OUT, len(out), len(images)))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""背景图压缩的「真实显示条件」画质验证。

不比较原图 vs 压缩图的像素，而是**按 ui_page.py 里的真实 CSS 管线模拟最终屏幕效果**，
再算 PSNR/SSIM —— 因为决定观感的是「显示尺寸 + 叠在上面的白纱」之后的画面。

模拟口径（摘自 ui_page.py）：
  pat/pat_dark  平铺 background-size:400px，叠 rgba(255,253,254,.56) 白纱
  run/winner/girl  hero 横幅 height:170px + object-fit:cover object-position:center 64%
                    （另作 cover 整幅底时叠 .82 白纱，条件更宽松）
  mascot        卡片角标 background-size:290px auto，叠 rgba(255,255,255,.80→.86) 白纱
  sticker_*     侧栏 height:126px
"""
import io
import os

import numpy as np
from PIL import Image

SRC = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\_themeart"

# 现版参数（= 当前 bg_assets.py 的口径），作为画质基线
NOW = {"pat": (900, 72), "pat_dark": (900, 72), "run": (1200, 74),
       "winner": (1200, 74), "girl": (1000, 74), "mascot": (720, 74)}
FILES = {"pat": "pat.jpg", "pat_dark": "pat_dark.jpg", "run": "run.jpg",
         "winner": "winner.jpg", "girl": "girl.jpg", "mascot": "mascot.jpg"}

# 候选参数
CAND = {
    "pat":      [(900, 72), (760, 68), (680, 67), (600, 66), (520, 64)],
    "pat_dark": [(900, 72), (760, 68), (680, 67), (600, 66), (520, 64)],
    "run":      [(1200, 74), (1200, 68), (1100, 68), (1000, 68), (900, 66)],
    "winner":   [(1200, 74), (1200, 68), (1100, 68), (1000, 68), (900, 66)],
    "girl":     [(1000, 74), (1000, 68), (900, 68), (820, 66), (720, 64)],
    "mascot":   [(720, 74), (560, 70), (460, 68), (420, 66), (360, 64)],
}


def encode(fn, w, q):
    im = Image.open(os.path.join(SRC, fn)).convert("RGB")
    if im.size[0] != w:
        im = im.resize((w, max(1, round(im.size[1] * w / im.size[0]))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
    raw = buf.getvalue()
    return Image.open(io.BytesIO(raw)).convert("RGB"), len(raw)   # (图, 字节数)


def resize(im, w, h):
    return im.resize((w, h), Image.LANCZOS)


def veil(im, rgba):
    """按 CSS 语义叠一层纯色纱：result = img*(1-a) + color*a"""
    a = rgba[3]
    base = np.asarray(im).astype(np.float32)
    col = np.array(rgba[:3], dtype=np.float32)
    out = base * (1 - a) + col * a
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def psnr(a, b):
    x = np.asarray(a).astype(np.float32)
    y = np.asarray(b).astype(np.float32)
    mse = float(np.mean((x - y) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def ssim(a, b):
    """灰度全局 SSIM（8x8 滑窗），够用来判断「看不看得出来」。"""
    x = np.asarray(a.convert("L")).astype(np.float64)
    y = np.asarray(b.convert("L")).astype(np.float64)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    win = 8
    hs = list(range(0, x.shape[0] - win + 1, win))
    ws = list(range(0, x.shape[1] - win + 1, win))
    vals = []
    for i in hs:
        for j in ws:
            bx = x[i:i + win, j:j + win].ravel()
            by = y[i:i + win, j:j + win].ravel()
            mx, my = bx.mean(), by.mean()
            vx, vy = bx.var(), by.var()
            cxy = float(np.mean((bx - mx) * (by - my)))
            vals.append(((2 * mx * my + C1) * (2 * cxy + C2)) /
                        ((mx * mx + my * my + C1) * (vx + vy + C2)))
    return float(np.mean(vals))


def render(key, im, ref=False):
    """按该图的真实显示条件渲染成最终屏幕画面。"""
    if key in ("pat", "pat_dark"):
        d = resize(im, 400, 368)                       # 400px 平铺
        return veil(d, (255, 253, 254, 0.56))          # 56% 白纱
    if key == "mascot":
        h = round(290 * im.size[1] / im.size[0])
        d = resize(im, 290, h)                         # 290px 角标
        return veil(d, (255, 255, 255, 0.83))          # 80~86% 白纱，取中值
    # hero：容器宽取 1400（.content max-width:1500 减 padding），高 170，center 64%
    W, H, POS = 1400, 170, 0.64
    sw = W
    sh = max(1, round(im.size[1] * sw / im.size[0]))
    scaled = resize(im, sw, sh)
    if sh < H:
        scaled = resize(im, sw, H)
        sh = H
    top = int((sh - H) * POS)
    crop = scaled.crop((0, top, sw, top + H))
    if key == "girl":
        # girl 还用作 setBanner（158x106 固定）+ cover 底
        small = resize(im, 158, 106)
        return crop, small
    return crop


print("%-10s %-14s %9s %9s %9s %8s" % ("key", "参数", "raw KB", "base64KB", "PSNR(dB)", "SSIM"))
print("-" * 70)
summary = []
for key, cands in CAND.items():
    fn = FILES[key]
    ref_img, _ = encode(fn, *NOW[key])
    ref = render(key, ref_img)
    ref_c = ref[0] if isinstance(ref, tuple) else ref
    base_b64 = None
    row_best = None
    for w, q in cands:
        im, nbytes = encode(fn, w, q)
        b64 = int(nbytes * 4 / 3)
        if base_b64 is None:
            base_b64 = b64
        out = render(key, im)
        out_c = out[0] if isinstance(out, tuple) else out
        p, s = psnr(ref_c, out_c), ssim(ref_c, out_c)
        note = ""
        if w == NOW[key][0] and q == NOW[key][1]:
            note = "  ← 现版(基线)"
        print("%-10s %-14s %9.1f %9.1f %9.1f %8.4f%s"
              % (key if w == cands[0][0] else "", "%dx? q%d" % (w, q),
                 nbytes / 1024.0, b64 / 1024.0, p, s, note))
        if isinstance(out, tuple):   # girl 的 setBanner 小图也评一下
            p2, s2 = psnr(ref[1], out[1]), ssim(ref[1], out[1])
            print("%-10s %-14s %9s %9s %9.1f %8.4f   (setBanner 158x106)"
                  % ("", "", "", "", p2, s2))
        row_best = (w, q, nbytes, b64, p, s)
    summary.append((key, base_b64, row_best))
    print()

print("== 各图「最激进档」汇总 ==")
tb = ta = 0
for key, base_b64, (w, q, raw, b64, p, s) in summary:
    tb += base_b64
    ta += b64
    print("  %-10s %dx? q%-3d  base64 %5.0f KB → %5.0f KB (-%2.0f%%)  PSNR %.1f dB  SSIM %.4f"
          % (key, w, q, base_b64 / 1024.0, b64 / 1024.0,
             (1 - b64 / base_b64) * 100, p, s))
print("  合计 %.0f KB → %.0f KB" % (tb / 1024.0, ta / 1024.0))

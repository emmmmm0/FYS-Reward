# -*- coding: utf-8 -*-
"""从 _themeart/ 生成 fys-reward/bg_assets.py —— 界面背景素材（base64 内联，随 exe 走）。

源图：项目根 _themeart/（ImageGen 生成后已裁掉右下角水印的成品）
输出：fys-reward/bg_assets.py -> BG_DATA = {key: data_uri}
体积：目标合计 < 800KB（比展示版再压一档，底纹/插画都不需要原分辨率）
      v2.7 实测：JPEG 部分 base64 约 728KB → 483KB（-34%），画质见 JOBS 上方注释
用法：_build_bg_assets.py
"""
import base64
import glob
import io
import os
from PIL import Image, ImageDraw, ImageFilter

SRC = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\_themeart"
DST = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\fys-reward\bg_assets.py"

# (源文件, key, 目标宽, JPEG 质量, 说明)
#
# ── 尺寸/质量口径（v2.7 重定，依据 _bg_quality_probe.py 的真实显示条件实测）──
# 判定不能拿「原图 vs 压缩图」直接比，要按 ui_page.py 的真实 CSS 管线模拟出最终屏幕
# 画面（显示尺寸 + 叠在上面的白纱）再比。实测结论分两类，差距很大：
#
#   ① 底纹/角标（pat、pat_dark、mascot）——**压缩几乎零代价**，可以压到 1/3：
#      · pat / pat_dark：background-size:400px 平铺 + rgba(255,253,254,.56) 白纱
#        → 图从 900px 降到 560px，实测 SSIM 0.988 / PSNR 44dB（视觉无损）
#      · mascot：卡片角标只按 290px 显示 + 80~86% 白纱（只剩 14~20% 可见度）
#        → 图从 720px 降到 420px，SSIM 0.995 / PSNR 51dB（比底纹还稳）
#
#   ② 三张插画（run、winner、girl）——是「门面」，不能压尺寸：
#      同一张图有两条用途：hero/lib 横幅（height 170/132px，宽度撑满容器）
#      与整幅 cover 氛围底。窗口默认 1280×820 → 主区约 1030px；最大化时受
#      .content{max-width:1500px} 限到 1500px。实测（容器取 1400px 的严苛口径）：
#        1100px q68 → SSIM 0.92    900px q66 → SSIM 0.87（已可察觉）
#      故只把 1200→1100（默认窗口下仍是下采样，无损）并把 q 74→68，
#      不做更激进的处理 —— 这 3 张合计仍占压缩后总量的 3/4，是体积的硬底。
JOBS = [
    ("pat.jpg",      "pat",       560, 66, "云朵小铺图案（平铺底纹）"),
    ("pat_dark.jpg", "pat_dark",  560, 66, "云朵小铺图案（夜幕护眼暗色版）"),
    ("run.jpg",      "run",      1100, 68, "冒险出发：Q版小队冲向终点（整幅氛围底/服务器页横幅）"),
    ("winner.jpg",   "winner",   1100, 68, "通关庆祝：举旗+满屏龙晶（整幅氛围底/地图库横幅）"),
    ("mascot.jpg",   "mascot",    420, 66, "云朵小铺吉祥物抱龙晶袋（卡片角标水印）"),
    ("girl.jpg",     "girl",      950, 68, "二次元少女坐云朵敲电脑（整幅氛围底/设置页头图）"),
]


def find_one(pattern):
    """按 glob 找唯一素材。注意：pattern 必须唯一命中——用 *主题词* 这种宽匹配容易同时
    命中两张（曾把「举旗图」当成「出发图」用错），命中多个时直接报错而不是默默取最后一张。"""
    hits = [h for h in sorted(glob.glob(os.path.join(SRC, pattern)))
            if h.lower().endswith(".png")]
    if not hits:
        raise SystemExit("未找到素材: " + pattern)
    if len(hits) > 1:
        raise SystemExit("素材匹配不唯一（%d 张）: %s\n  %s"
                         % (len(hits), pattern, "\n  ".join(os.path.basename(h) for h in hits)))
    return hits[0]


def cutout(path, crop_bottom=0, out_size=(260, 400), thresh=46):
    """白底 → 透明贴纸：只挖与边缘连通的外部白底（flood fill），保留角色自身白色。
    crop_bottom：先裁掉底部若干像素（ImageGen 图右下有很淡的水印）。"""
    im = Image.open(path).convert("RGBA")
    if crop_bottom:
        w, h = im.size
        im = im.crop((0, 0, w, max(1, h - crop_bottom)))
    w0, h0 = im.size
    probe = im.convert("RGB")
    magic = (255, 0, 255)                     # 品红极不易与画面撞色
    for cx, cy in ((0, 0), (w0 - 1, 0), (0, h0 - 1), (w0 - 1, h0 - 1)):
        ImageDraw.floodfill(probe, (cx, cy), magic, thresh=thresh)
    pr = probe.load()
    a = im.split()[3]
    ap = a.load()
    for y in range(h0):
        for x in range(w0):
            if pr[x, y] == magic:
                ap[x, y] = 0
    im.putalpha(a.filter(ImageFilter.GaussianBlur(0.8)))   # 羽化 1px，缩放时不出现硬锯齿
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    im.thumbnail(out_size, Image.LANCZOS)
    return im


def main():
    parts = []
    total = 0

    for fn, key, w, q, note in JOBS:
        src = os.path.join(SRC, fn)
        im = Image.open(src).convert("RGB")
        if im.size[0] != w:
            im = im.resize((w, max(1, round(im.size[1] * w / im.size[0]))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        raw = buf.getvalue()
        total += len(raw)
        parts.append((key, "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii"), note))
        print("  %-9s %-11s %dx%d  %dKB" % (key, fn, im.size[0], im.size[1], len(raw) // 1024))

    # ── 侧栏贴纸（可自选，均为透明底） ──────────────────────────────
    # 抠图统一走 cutout()：只挖「与边缘连通的外部白底」，不能按亮度一刀切——
    # 一刀切会把角色自己的白色描边/眼白也削成透明：亮色主题下底色也是白的看不出来，
    # 换到夜幕护眼（深色）立刻露馅，看起来像换了一张图。
    STICKERS = [
        ("zombie", "*小僵尸吉祥物贴纸*", "Q版小僵尸", 0),      # 已裁过水印，无需再裁底
        ("cloud",  "*云朵精灵吉祥物*",   "云朵小铺吉祥物", 82),
        ("cat",    "*小白猫吉祥物*",     "Q版小白猫", 82),
    ]
    for key, pattern, note, crop_bottom in STICKERS:
        img = cutout(find_one(pattern), crop_bottom)
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=82, method=6)
        raw = buf.getvalue()
        total += len(raw)
        parts.append(("sticker_" + key,
                      "data:image/webp;base64," + base64.b64encode(raw).decode("ascii"),
                      "%s（透明底贴纸）" % note))
        print("  %-13s %dx%d  %dKB" % ("sticker_" + key, img.size[0], img.size[1],
                                       len(raw) // 1024))

    lines = [
        "# -*- coding: utf-8 -*-",
        '"""界面背景素材（自动生成，勿手改）。',
        "",
        "源图：项目根 _themeart/（ImageGen 生成 + 裁水印压缩）",
        "生成：fys-reward/_build_bg_assets.py —— 改了素材重新跑一遍即可",
        "用法：ui_page.build_page() 把 BG_DATA 注入页面 __BGS__ 占位符，",
        "      前端 applyBG() 按所选背景方案取用（见 ui_page.py 的 BGS / bgCSS）。",
        '"""',
        "",
        "BG_DATA = {",
    ]
    for key, uri, note in parts:
        lines.append("    # %s" % note)
        lines.append("    %r: %r," % (key, uri))
    lines.append("}")
    lines.append("")

    with open(DST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    print("\n-> %s  （原图合计 %dKB，base64 后约 %dKB）"
          % (DST, total // 1024, int(total * 1.37) // 1024))


if __name__ == "__main__":
    main()

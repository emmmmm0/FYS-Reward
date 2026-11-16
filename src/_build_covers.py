# -*- coding: utf-8 -*-
"""
地图封面抓取（官方图床 resx.fyscs.cn/mapimgs/<地图名>.jpg）
==================================================
风云社官方站点自己就显示这些图（ServerDetail 组件里 qA(map) 拼出的地址），
国内直连可达，比 Steam 工坊页面稳（工坊社区域名在国内部署机器上被墙）。

产出：cover/<地图名>.jpg   统一 320x180（居中裁剪）质量 78，约 12~20KB
       cover/_missing.json  没有封面的地图名列表（前端回退到默认图）

用法：
  python _build_covers.py           增量（已存在且非空就跳过）
  python _build_covers.py --all     全量重抓
  python _build_covers.py --probe   只测命中率，不落盘
"""
import io
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cover")
BASE = "https://resx.fyscs.cn/mapimgs/"
DEFAULT = "defaultmap"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
W, H, Q = 320, 180, 78
WORKERS = 8


def maps():
    """地图库全 ze 图名（maps.json ∪ rewards.json）——必须取并集，
    否则 rewards 独有的新图不会去抓封面（新图自动补全链依赖这一点）。"""
    names = set()
    for fn in ("maps.json", "rewards.json"):
        p = os.path.join(HERE, "data", fn)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        if isinstance(d, dict):
            names |= set(d.keys())
    return sorted(n for n in names if n.startswith("ze"))


def opener():
    """本机 urllib 默认会读系统代理；这里显式走系统代理（沙箱环境直连不通外网）"""
    return urllib.request.build_opener()


def fetch(name, timeout=25):
    """返回 (bytes, err)；err 为 None 表示成功"""
    op = opener()
    req = urllib.request.Request(BASE + name + ".jpg", headers={"User-Agent": UA})
    try:
        return op.open(req, timeout=timeout).read(), None
    except Exception as e:
        return None, type(e).__name__


def shrink(raw):
    from PIL import Image
    im = Image.open(io.BytesIO(raw))
    im = im.convert("RGB")
    sw, sh = im.size
    if sw == 0 or sh == 0:
        raise ValueError("empty")
    # 居中裁剪到 16:9 再缩放（工坊封面多为 16:9，少数方图也不留黑边）
    tw, th = W, H
    ar_src, ar_dst = sw / sh, tw / th
    if ar_src > ar_dst:
        nw = int(sh * ar_dst)
        im = im.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
    else:
        nh = int(sw / ar_dst)
        im = im.crop((0, (sh - nh) // 2, sw, (sh - nh) // 2 + nh))
    im = im.resize((tw, th), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=Q, optimize=True, progressive=True)
    return buf.getvalue()


def one(name, force):
    dst = os.path.join(OUT, name + ".jpg")
    if not force and os.path.exists(dst) and os.path.getsize(dst) > 1024:
        return name, "skip", 0
    raw, err = fetch(name)
    if err:
        return name, "miss:" + err, 0
    if len(raw) < 2048:
        return name, "tiny", 0
    try:
        out = shrink(raw)
    except Exception as e:
        return name, "bad:" + type(e).__name__, 0
    tmp = dst + ".part"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, dst)
    return name, "ok", len(out)


def main():
    args = sys.argv[1:]
    force = "--all" in args
    probe = "--probe" in args
    names = maps()
    for a in args:
        if a.startswith("--limit="):
            names = names[:int(a.split("=")[1])]
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    ok = miss = skip = 0
    missing = []
    sizes = {}

    def run(n):
        if probe:
            raw, err = fetch(n, timeout=15)
            if err:
                return n, "miss", 0
            try:
                from PIL import Image
                im = Image.open(io.BytesIO(raw))
                sizes[n] = im.size
            except Exception:
                pass
            return n, "ok", len(raw)
        return one(n, force)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, (n, st, sz) in enumerate(ex.map(run, names), 1):
            if st == "ok":
                ok += 1
            elif st == "skip":
                skip += 1
            else:
                miss += 1
                missing.append(n)
            if i % 50 == 0 or i == len(names):
                print("  %d/%d  ok=%d skip=%d miss=%d  %.0fs"
                      % (i, len(names), ok, skip, miss, time.time() - t0), flush=True)
    print("完成：%d 张，成功 %d / 跳过 %d / 缺失 %d，用时 %.0fs"
          % (len(names), ok, skip, miss, time.time() - t0))
    if not probe:
        json.dump(missing, open(os.path.join(OUT, "_missing.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("缺失清单：cover/_missing.json（%d）" % len(missing))
        tot = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)
                  if f.endswith(".jpg"))
        print("封面总占用：%.1f MB" % (tot / 1048576))
    if probe and sizes:
        from collections import Counter
        c = Counter(sizes.values())
        print("原图尺寸分布 top5：", c.most_common(5))


if __name__ == "__main__":
    main()

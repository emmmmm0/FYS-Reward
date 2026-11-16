# -*- coding: utf-8 -*-
"""把重建好的实体预览页同步进软件目录。

源：根目录 `地图实体预览-3D视图.html` + `terr/<工坊ID>.js`
目标：`fys-reward/preview3d.html` + `fys-reward/terr/<工坊ID>.bin`
      （原始 gz 字节，比 base64 js 省 25% 体积；根目录 terr/*.js 保留作 file:// 兜底）
      根目录 `terr_bin/` 是 .bin 的生成缓存。

用法：python _sync_preview.py            # 实际同步
      python _sync_preview.py --check    # 只看差异，不写
"""
import os, sys, time, shutil, base64, re

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
SRC_HTML = os.path.join(ROOT, "地图实体预览-3D视图.html")
DST_HTML = os.path.join(ROOT, "fys-reward", "preview3d.html")
SRC_T = os.path.join(ROOT, "terr")
DST_T = os.path.join(ROOT, "fys-reward", "terr")
SRC_TB = os.path.join(ROOT, "terr_bin")
CHECK = "--check" in sys.argv

for p in (SRC_HTML, SRC_T):
    if not os.path.exists(p):
        raise SystemExit("缺少源文件：%s" % p)
os.makedirs(DST_T, exist_ok=True)

t0 = time.time()
hs, hd = os.path.getsize(SRC_HTML), (os.path.getsize(DST_HTML) if os.path.exists(DST_HTML) else -1)
need_html = hs != hd
print("HTML  源 %.2f MB / 目标 %s %s" % (
    hs / 1048576, ("%.2f MB" % (hd / 1048576)) if hd >= 0 else "不存在",
    "→ 需要同步" if need_html else "→ 已是最新"))
if need_html and not CHECK:
    tmp = DST_HTML + ".tmp"
    shutil.copy2(SRC_HTML, tmp)
    os.replace(tmp, DST_HTML)
    print("      已写入 %.2f MB（%.1fs）" % (os.path.getsize(DST_HTML) / 1048576, time.time() - t0))

src = sorted(f for f in os.listdir(SRC_T) if f.endswith(".js"))
new = same = 0
for f in src:
    s, d = os.path.join(SRC_T, f), os.path.join(DST_T, f)
    if os.path.exists(d) and os.path.getsize(d) == os.path.getsize(s):
        same += 1
        continue
    new += 1
    if not CHECK:
        tmp = d + ".tmp"
        shutil.copy2(s, tmp)
        os.replace(tmp, d)
# 目标里多出来的（源已无）只报告，不删
extra = [f for f in os.listdir(DST_T) if f.endswith(".js") and f not in set(src)]
print("terr  源 %d 个 / 需更新 %d 个 / 已最新 %d 个%s" % (
    len(src), new, same, ("（--check，未写入）" if CHECK else "")))
if extra:
    print("      目标多出 %d 个（源已无，未删除）：%s" % (len(extra), ", ".join(extra[:5])))

sa = sum(os.path.getsize(os.path.join(SRC_T, f)) for f in src)
da = sum(os.path.getsize(os.path.join(DST_T, f)) for f in os.listdir(DST_T) if f.endswith(".js"))
print("体积  源 %.1f MB / 目标 %.1f MB" % (sa / 1048576, da / 1048576))

# ── terr_bin：从根 terr/*.js 解出 base64 → 原始 gz 字节（发行包瘦身） ──
import re
B64RE = re.compile(r'"([A-Za-z0-9+/=]{100,})"')
os.makedirs(SRC_TB, exist_ok=True)
bins = sorted(f for f in os.listdir(SRC_T) if f.endswith(".js"))
nb = sameb = 0
for f in bins:
    sj = os.path.join(SRC_T, f)
    sb = os.path.join(SRC_TB, f[:-3] + ".bin")
    if os.path.exists(sb) and os.path.getmtime(sb) >= os.path.getmtime(sj):
        sameb += 1
        continue
    nb += 1
    if not CHECK:
        m = B64RE.search(open(sj, encoding="ascii").read())
        if not m:
            print("      ! 解析失败：%s" % f)
            continue
        tmp = sb + ".tmp"
        open(tmp, "wb").write(base64.b64decode(m.group(1)))
        os.replace(tmp, sb)
for f in bins:
    db = os.path.join(DST_T, f[:-3] + ".bin")
    sb = os.path.join(SRC_TB, f[:-3] + ".bin")
    if CHECK or not os.path.exists(sb):
        continue
    if not os.path.exists(db) or os.path.getsize(db) != os.path.getsize(sb) or os.path.getmtime(db) < os.path.getmtime(sb):
        tmp = db + ".tmp"
        shutil.copy2(sb, tmp)
        os.replace(tmp, db)
# 目标目录改用 .bin 后，旧 .js 全部清掉（预览页 http 下已不走 js）
stale_js = [f for f in os.listdir(DST_T) if f.endswith(".js")]
if stale_js and not CHECK:
    for f in stale_js:
        try:
            os.remove(os.path.join(DST_T, f))
        except OSError as e:
            print("      ! 删除旧 js 失败 %s：%r" % (f, e))
    print("      已清理旧版 .js 分包 %d 个（改用 .bin）" % len(stale_js))
ta = sum(os.path.getsize(os.path.join(SRC_TB, f)) for f in os.listdir(SRC_TB) if f.endswith(".bin"))
db_total = sum(os.path.getsize(os.path.join(DST_T, f)) for f in os.listdir(DST_T) if f.endswith(".bin"))
print("terr_bin 共 %d 个 / 新生成 %d 个%s / %.1f MB（js 为 %.1f MB，省 %.0f%%）"
      % (len(bins), nb, ("（--check，未写入）" if CHECK else ""),
         ta / 1048576, sa / 1048576, (1 - ta / sa) * 100 if sa else 0))
print("fys-reward/terr 现有 %.1f MB .bin" % (db_total / 1048576))
print("完成，用时 %.1fs" % (time.time() - t0))

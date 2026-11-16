# -*- coding: utf-8 -*-
"""分析首页 HTML 体积构成：内联 CSS / JS / base64 资源各占多少。只读。"""
import base64
import io
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

print("== 直接用 build_page() 生成首页，分析构成 ==")
import ui_page  # noqa: E402
html = ui_page.build_page("v2.7")
raw = html.encode("utf-8")
print("  首页总大小 %.1f KB" % (len(raw) / 1024.0))

def seg_all(tag):
    return re.findall(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), html, re.S)

style_len = sum(len(s) for s in seg_all("style"))
script_len = sum(len(s) for s in seg_all("script"))
print("  <style> 合计 %.1f KB  (%d 块)" % (style_len / 1024.0, len(seg_all("style"))))
print("  <script> 合计 %.1f KB (%d 块)" % (script_len / 1024.0, len(seg_all("script"))))

uris = re.findall(r"data:image/(\w+);base64,([A-Za-z0-9+/=]+)", html)
tot64 = sum(len(b) for _e, b in uris)
print("  内联 data:image 共 %d 个，base64 合计 %.1f KB（解码后约 %.1f KB）"
      % (len(uris), tot64 / 1024.0, tot64 * 3 / 4 / 1024.0))
per = {}
for e, b in uris:
    per.setdefault(e, [0, 0])
    per[e][0] += 1
    per[e][1] += len(b)
for e, (n, sz) in sorted(per.items(), key=lambda x: -x[1][1]):
    print("     %-6s %3d 个  %8.1f KB" % (e, n, sz / 1024.0))

print("\n== bg_assets.py 本身 ==")
p = os.path.join(HERE, "bg_assets.py")
print("  文件 %.1f KB" % (os.path.getsize(p) / 1024.0))

print("\n== 首页里最长的 JS 函数（前 12）==")
for blk in seg_all("script"):
    pass
scripts = seg_all("script")
for idx, s in enumerate(scripts, 1):
    fns = re.findall(r"function\s+(\w+)\s*\([^)]*\)\s*\{", s)
    print("  块 %d: %d 字符, %d 个 function: %s"
          % (idx, len(s), len(fns), ", ".join(fns[:14])))

print("\n== /overlay 页面（覆盖小窗）大小 ==")
import fys_reward_app  # noqa: E402
try:
    ov = fys_reward_app.build_overlay_page() if hasattr(fys_reward_app, "build_overlay_page") else None
    if ov is None:
        ov = [v for k, v in vars(fys_reward_app).items() if isinstance(v, str) and "FYS 屏幕覆盖" in str(v)]
        print("  未找到 build_overlay_page()，候选字符串 %d 个" % len(ov))
    else:
        print("  %.1f KB" % (len(ov.encode("utf-8")) / 1024.0))
except Exception as e:
    print("  跳过:", e)

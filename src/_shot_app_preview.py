# -*- coding: utf-8 -*-
"""软件内「🗺️ 实体预览」页验证：真实后端（起本机服务）+ headless Edge 截图 / DOM 断言

用法：python _shot_app_preview.py            # 截图 + 断言
      python _shot_app_preview.py --dom      # 只跑 DOM 断言
"""
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
W = os.path.dirname(HERE)
SHOT = os.path.join(W, "验证截图-软件实体预览")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8799

ONLY_DOM = "--dom" in sys.argv

import fys_reward_app as A          # noqa: E402
import reward_server as engine      # noqa: E402

A.State.engine = engine
meta = engine.load_state(force=False)
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
print("本机服务已启动 %s（地图 %s 张 / 关卡 %s 段）"
      % (A.State.url, meta.get("maps"), meta.get("stages")))
time.sleep(0.8)

os.makedirs(SHOT, exist_ok=True)
PROF = os.path.join(SHOT, "_prof")


def edge(url, extra=None, budget=15000, out=None):
    cmd = [EDGE, "--headless=new", "--disable-gpu-sandbox", "--enable-unsafe-swiftshader",
           "--use-angle=swiftshader", "--hide-scrollbars", "--no-first-run",
           "--user-data-dir=" + PROF, "--window-size=1330,720",
           "--virtual-time-budget=%d" % budget]
    cmd += (extra or [])
    cmd += [url]
    if out:
        cmd.insert(-1, "--screenshot=" + out)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          encoding="utf-8", errors="replace")


def dom(path, must=(), must_not=()):
    r = edge(A.State.url.rstrip("/") + path, ["--dump-dom"], 18000)
    html = r.stdout or ""
    ok = True
    for t in must:
        if t not in html:
            ok = False
    for t in must_not:
        if t in html:
            ok = False
    print("  DOM %-42s %s  %s" % (path, "OK " if ok else "FAIL", "len=%d" % len(html)))
    for t in must:
        if t not in html:
            print("     缺: %s" % t)
    for t in must_not:
        if t in html:
            print("     不该有: %s" % t)
    return ok


print("\n── DOM 断言 ──")
dom_ok = []
dom_ok.append(dom("/", must=['data-view="pre"', 'id="preFrame"', 'id="pvNow"', 'id="preShot"']))
# 预览页直连：embed 类 + 主题属性必须落到 <html> 上（CSS 里也有 data-theme 字样，故按整标签断言）
dom_ok.append(dom("/preview3d?embed=1&th=N",
                  must=['<html lang="zh-CN" data-theme="N" class="embed">', 'id="maps"']))
dom_ok.append(dom("/preview3d?embed=1&th=E",
                  must=['<html lang="zh-CN" data-theme="E" class="embed">']))
dom_ok.append(dom("/preview3d", must=['<html lang="zh-CN">', 'id="maps"'],
                  must_not=['<html lang="zh-CN" ']))

CASES = [
    ("01-软件内预览-奶油草莓", "/?view=pre&theme=E", 17000),
    ("02-软件内预览-夜幕护眼", "/?view=pre&theme=N", 17000),
    ("03-软件内预览-薄荷团子", "/?view=pre&theme=F", 17000),
    ("04-软件内预览-带图跳转-邪恶公馆", "/?view=pre&map=ze_evil_mansion&theme=E", 17000),
    ("05-服务器页-入口按钮", "/?view=srv&theme=E", 10000),
    ("06-地图库-入口按钮", "/?view=lib&theme=E", 13000),
]

if not ONLY_DOM:
    print("\n── 截图 ──")
    for name, qs, wait in CASES:
        out = os.path.join(SHOT, name + ".png")
        if os.path.exists(out):
            os.remove(out)
        r = edge(A.State.url.rstrip("/") + qs, budget=wait, out=out)
        if os.path.exists(out) and os.path.getsize(out) > 8000:
            print("  %-34s OK   %.0f KB" % (name, os.path.getsize(out) / 1024))
        else:
            print("  %-34s FAIL %s" % (name, (r.stderr or "")[-200:]))
    # 预览页直连（模拟浏览器打开那份）
    out = os.path.join(SHOT, "07-浏览器打开-独立预览.png")
    r = edge(A.State.url.rstrip("/") + "/preview3d?map=ze_evil_mansion", budget=16000, out=out)
    print("  %-34s %s" % ("07-浏览器打开-独立预览",
                          "OK" if os.path.exists(out) else "FAIL"))

print("\nDOM 断言 %s    截图目录：%s" % ("全过 ✓" if all(dom_ok) else "有失败 ✗", SHOT))

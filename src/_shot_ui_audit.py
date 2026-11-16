# -*- coding: utf-8 -*-
"""界面巡检截图：把这次修过的几处（服务器表列宽 / 深色主题在线条 / 屏幕覆盖页 / 覆盖小窗空态）
逐个拍下来，方便肉眼比对。

用法：python _shot_ui_audit.py           # 全部截图
      python _shot_ui_audit.py --dom     # 只跑 DOM 断言
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
W = os.path.dirname(HERE)
SHOT = os.path.join(W, "验证截图-界面巡检")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8801
ONLY_DOM = "--dom" in sys.argv

import fys_reward_app as A          # noqa: E402
import reward_server as engine      # noqa: E402

A.State.engine = engine
meta = engine.load_state(force=False)
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
BASE = A.State.url.rstrip("/")
print("本机服务 %s（地图 %s / 关卡 %s）" % (BASE, meta.get("maps"), meta.get("stages")))
time.sleep(0.8)

os.makedirs(SHOT, exist_ok=True)
PROF = os.path.join(SHOT, "_prof")


def edge(url, budget=14000, out=None, extra=None, size="1400,780"):
    cmd = [EDGE, "--headless=new", "--disable-gpu-sandbox", "--enable-unsafe-swiftshader",
           "--use-angle=swiftshader", "--hide-scrollbars", "--no-first-run",
           "--user-data-dir=" + PROF, "--window-size=" + size,
           "--virtual-time-budget=%d" % budget]
    cmd += (extra or [])
    cmd += [url]
    if out:
        cmd.insert(-1, "--screenshot=" + out)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          encoding="utf-8", errors="replace")


def dom(path, must=(), must_not=()):
    r = edge(BASE + path, 16000, extra=["--dump-dom"])
    html = r.stdout or ""
    ok = True
    for t in must:
        if t not in html:
            ok = False
    for t in must_not:
        if t in html:
            ok = False
    print("  DOM %-40s %s  len=%d" % (path, "OK " if ok else "FAIL", len(html)))
    for t in must:
        if t not in html:
            print("     缺: %s" % t)
    for t in must_not:
        if t in html:
            print("     不该有: %s" % t)
    return ok


print("\n── DOM 断言 ──")
oks = []
# 关键：这次修好的几处必须出现在页面里
oks.append(dom("/", must=['table class="srvtab"', 'function esc(', '__tickBusy',
                          'function applyTheme(id, save){', 'NST=(d.stages&&d.stages.length)'
                          ]))
oks.append(dom("/?", must_not=['table.srv{']))
# 主题非法码要收敛到默认主题（不能把整页配色弄没）
oks.append(dom("/?theme=Z", must=['data-theme="E"']))
oks.append(dom("/?theme=N", must=['data-theme="N"']))

if not ONLY_DOM:
    print("\n── 截图 ──")
    cases = [
        ("01-服务器表-浅色E", "/?view=srv&theme=E", 12000),
        ("02-服务器表-深色N", "/?view=srv&theme=N", 12000),
        ("03-屏幕覆盖页-浅色E", "/?view=ov&theme=E", 11000),
        ("04-屏幕覆盖页-深色N", "/?view=ov&theme=N", 11000),
        ("05-地图库-浅色E", "/?view=lib&theme=E", 13000),
        ("06-主题页-浅色E", "/?view=theme&theme=E", 10000),
    ]
    for name, qs, wait in cases:
        out = os.path.join(SHOT, name + ".png")
        if os.path.exists(out):
            os.remove(out)
        r = edge(BASE + qs, budget=wait, out=out)
        ok = os.path.exists(out) and os.path.getsize(out) > 8000
        print("  %-24s %s  %s" % (name, "OK " if ok else "FAIL",
                                  ("%.0f KB" % (os.path.getsize(out) / 1024)) if ok else (r.stderr or "")[-120:]))
    # 覆盖小窗：透明底，单独用 00000000 背景色，便于看「未进服」紧凑卡
    out = os.path.join(SHOT, "07-覆盖小窗-空态.png")
    edge(BASE + "/overlay", budget=9000, out=out, size="560,260",
         extra=["--default-background-color=00000000"])
    print("  %-24s %s" % ("07-覆盖小窗-空态",
                          "OK " if os.path.exists(out) else "FAIL"))

print("\nDOM %s    截图目录：%s" % ("全过 ✓" if all(oks) else "有失败 ✗", SHOT))
sys.exit(0 if all(oks) else 1)

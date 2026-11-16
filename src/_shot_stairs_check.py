# -*- coding: utf-8 -*-
"""确认软件内嵌的实体预览用的是新版地形（楼梯图 ze_backrooms_insomnia）。

用法：python _shot_stairs_check.py
产物：验证截图-界面巡检/08-软件内嵌预览-后室失眠症.png
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
W = os.path.dirname(HERE)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8805
MAP = "ze_backrooms_insomnia"
OUT = os.path.join(W, "验证截图-界面巡检", "08-软件内嵌预览-后室失眠症.png")

import fys_reward_app as A          # noqa: E402
import reward_server as engine      # noqa: E402

A.State.engine = engine
engine.load_state(force=False)
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
base = A.State.url.rstrip("/")
print("本机服务 %s" % base)
time.sleep(0.8)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
if os.path.exists(OUT):
    os.remove(OUT)
prof = os.path.join(os.path.dirname(OUT), "_prof_st")
r = subprocess.run(
    [EDGE, "--headless=new", "--disable-gpu-sandbox", "--enable-unsafe-swiftshader",
     "--use-angle=swiftshader", "--hide-scrollbars", "--no-first-run",
     "--user-data-dir=" + prof, "--window-size=1400,820",
     "--virtual-time-budget=26000", "--dump-dom",
     "--screenshot=" + OUT,
     base + "/preview3d?map=" + MAP],
    capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
html = r.stdout or ""
ok = os.path.exists(OUT) and os.path.getsize(OUT) > 20000
# 页面里的状态栏应显示面数与地图名
import re
m = re.search(r"(\d[\d.,]*k?)\s*面", html)
print("截图 %s %s  (%.0f KB)" % (OUT, "OK " if ok else "FAIL",
                                os.path.getsize(OUT) / 1024 if ok else 0))
print("DOM 里抓到的面数:", m.group(0) if m else "未抓到")
print("页面含 ERR:", "ERR" in html)

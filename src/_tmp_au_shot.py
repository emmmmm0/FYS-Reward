# -*- coding: utf-8 -*-
"""临时：截设置页作者名片 + 更新日志区域，确认虚线环偏移 / 角标遮挡现状。"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
W = os.path.dirname(HERE)
SHOT = os.path.join(W, "验证截图-界面巡检")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8813

import fys_reward_app as A          # noqa: E402
import reward_server as engine      # noqa: E402

A.State.engine = engine
meta = engine.load_state(force=False)
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
BASE = A.State.url.rstrip("/")
print("本机服务 %s" % BASE)
time.sleep(0.8)
os.makedirs(SHOT, exist_ok=True)
PROF = os.path.join(SHOT, "_prof_tmp")

url = BASE + "/?view=set"
r = subprocess.run([EDGE, "--headless=new", "--disable-gpu-sandbox",
                    "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
                    "--hide-scrollbars", "--no-first-run",
                    "--user-data-dir=" + PROF, "--window-size=1100,3400",
                    "--virtual-time-budget=15000",
                    "--screenshot=" + os.path.join(SHOT, "_tmp_au_full.png"), url],
                   capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
print("shot done", r.returncode)
A.stop_http_server()

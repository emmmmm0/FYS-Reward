# -*- coding: utf-8 -*-
"""用 headless Edge 给样板 HTML 截图，验证 5 主题下的渲染。

坑（项目既有经验）：中文路径给 --user-data-dir / --screenshot 会 0x5 失败，
所以先把 HTML 复制到 %TEMP% 的纯 ASCII 目录，再走本地 HTTP（file:// + ?query 会白屏）。
"""
import http.server
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

SRC = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\云朵小铺-游玩记录与趋势样板.html"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
# ⚠ 落点必须全 ASCII 且**在项目目录内**（与已验证的 _shot_sample.py 一致）：
#   中文路径给 --screenshot 会 0x5；%TEMP% 下偶发 0 字节。
BASE = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\fys-reward\_shot_tmp2"
WORK = os.path.join(BASE, "web")
OUT = BASE
PROFILE = os.path.join(BASE, "prof")

shutil.rmtree(BASE, ignore_errors=True)
for d in (WORK, OUT, PROFILE):
    os.makedirs(d, exist_ok=True)
shutil.copy2(SRC, os.path.join(WORK, "index.html"))

# 起本地 HTTP（找空闲端口）
s = socket.socket()
s.bind(("127.0.0.1", 0))
PORT = s.getsockname()[1]
s.close()


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


os.chdir(WORK)
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
time.sleep(0.4)
print("服务 http://127.0.0.1:%d/" % PORT)

SHOTS = [
    ("E", "log", "①奶油草莓 · 游玩记录"),
    ("N", "log", "②夜幕护眼 · 游玩记录"),
    ("E", "trend", "③奶油草莓 · 趋势统计"),
    ("G", "plan", "④樱花苏打 · 落地方案"),
]
paths = []
for th, vw, label in SHOTS:
    out = os.path.join(OUT, "shot_%s_%s.png" % (th, vw))
    url = "http://127.0.0.1:%d/?theme=%s&view=%s" % (PORT, th, vw)
    cmd = [EDGE, "--headless", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check",
           "--user-data-dir=" + PROFILE,
           "--window-size=1280,900",
           "--screenshot=" + out, url]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    ok = os.path.exists(out) and os.path.getsize(out) > 8000
    print("  %-22s -> %s  (%s bytes) rc=%d" %
          (label, os.path.basename(out), os.path.getsize(out) if os.path.exists(out) else 0, r.returncode))
    if not ok:
        print("     stderr:", r.stderr.decode("utf-8", "ignore")[-400:])
    paths.append(out)

httpd.shutdown()
print("\n截图目录:", OUT)
for p in paths:
    print("  ", p)

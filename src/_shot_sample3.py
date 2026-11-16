# -*- coding: utf-8 -*-
"""用 CDP 给样板 HTML 截图（验证 5 主题 × 3 视图的渲染）。

⚠ 本机实测：Edge 的 `--headless --screenshot=xx.png` 已经截不出东西（0 字节，rc=0，
   换路径/加 profile/换 --headless 老新式都无效）。所以改走项目里已验证的 CDP 方式
   （与 _e2e_layout.py 同一条路）：--headless=new + --remote-debugging-port，
   再调 Page.captureScreenshot 拿图。
"""
import base64
import functools
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import websocket

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
SRC = os.path.join(ROOT, "云朵小铺-游玩记录与趋势样板.html")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = os.path.join(ROOT, "fys-reward", "_shot_tmp2")
WORK = os.path.join(BASE, "web")
PROFILE = os.path.join(BASE, "prof")
DPORT = 9403

for d in (WORK, PROFILE):
    os.makedirs(d, exist_ok=True)
shutil.copy2(SRC, os.path.join(WORK, "index.html"))

s = socket.socket()
s.bind(("127.0.0.1", 0))
PORT = s.getsockname()[1]
s.close()
Handler = functools.partial(SimpleHTTPRequestHandler, directory=WORK)
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print("服务 http://127.0.0.1:%d/" % PORT)

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

edge = subprocess.Popen(
    [EDGE, "--headless=new", "--remote-debugging-port=%d" % DPORT,
     "--remote-allow-origins=*", "--user-data-dir=" + PROFILE,
     "--no-first-run", "--window-size=1280,900", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ws_url = None
    for _ in range(60):
        try:
            tabs = json.load(OPENER.open("http://127.0.0.1:%d/json" % DPORT, timeout=2))
            pg = [t for t in tabs if t.get("type") == "page"]
            if pg:
                ws_url = pg[0]["webSocketDebuggerUrl"]
                break
        except Exception:
            time.sleep(0.5)
    assert ws_url, "Edge CDP 起不来"
    ws = websocket.create_connection(ws_url, timeout=60)

    def cdp(mid, method, params=None):
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m

    cdp(1, "Page.enable")
    cdp(2, "Runtime.enable")
    # 视口尺寸用 CDP 精确指定：命令行 --window-size 会受系统 DPI 缩放影响（实测被缩成 500x527）
    cdp(3, "Emulation.setDeviceMetricsOverride",
        {"width": 1280, "height": 2200, "deviceScaleFactor": 1, "mobile": False})

    def shoot(name, theme, view):
        url = "http://127.0.0.1:%d/index.html?theme=%s&view=%s" % (PORT, theme, view)
        cdp(10, "Page.navigate", {"url": url})
        ok = False
        for _ in range(60):
            r = cdp(11, "Runtime.evaluate",
                     {"expression": "document.readyState==='complete' && "
                                    "!!document.getElementById('heat').children.length && "
                                    "!!document.getElementById('barChart').children.length"})
            if r.get("result", {}).get("result", {}).get("value") is True:
                ok = True
                break
            time.sleep(0.25)
        time.sleep(0.5)
        r = cdp(12, "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": True})
        data = r.get("result", {}).get("data")
        p = os.path.join(BASE, "shot_%s_%s.png" % (theme, view))
        if data:
            with open(p, "wb") as fh:
                fh.write(base64.b64decode(data))
        try:
            from PIL import Image
            dim = Image.open(p).size
        except Exception:
            dim = '?' 
        try:
            from PIL import Image
            dim = Image.open(p).size
        except Exception:
            dim = '?' 
        print("  %-26s ready=%-5s -> %s (%s bytes, %s)"
              % ("%s/%s" % (theme, view), ok, os.path.basename(p),
                 os.path.getsize(p) if os.path.exists(p) else 0, dim))
        return p

    SHOTS = [("E", "log"), ("N", "log"), ("E", "trend"), ("N", "plan"), ("H", "trend")]
    for th, vw in SHOTS:
        shoot("", th, vw)
finally:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(edge.pid)],
                   capture_output=True, timeout=10)
    httpd.shutdown()
print("\n截图目录:", BASE)

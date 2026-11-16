# -*- coding: utf-8 -*-
"""抓 6 个视图的现状截图，供「美化样板总览」对比用。用法: _shot_views_now.py <port>"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\验证截图-界面巡检"
CDP = 9351

# (view, 深链, 就绪判定JS, 额外等待秒)
VIEWS = [
    ("1-服务器",  "/?view=srv",   "typeof LIB!=='undefined' && document.querySelectorAll('#view-srv table tr, #view-srv .srow').length>0", 1.5),
    ("2-屏幕覆盖", "/?view=ov",    "typeof LIB!=='undefined' && !!document.querySelector('#view-ov')", 1.2),
    ("3-主题",    "/?view=theme", "typeof LIB!=='undefined' && !!document.querySelector('#view-theme')", 1.0),
    ("4-地图库",  "/?view=lib",   "typeof LIB!=='undefined' && document.querySelectorAll('#view-lib .librow, #view-lib li, #view-lib tr').length>5", 1.2),
    ("5-设置",    "/?view=set",   "typeof LIB!=='undefined' && !!document.querySelector('#clgCard')", 1.0),
    ("6-实体预览", "/?view=pre&map=ze_pizza_cookie",
     "typeof LIB!=='undefined' && (function(){try{return !!window.frames[0].document.querySelector('canvas')}catch(e){return false}})()", 4.0),
]


def main():
    port = int(sys.argv[1])
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    prof = os.path.join(OUT, "_prof_cdp9")
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
         "--remote-allow-origins=*", "--user-data-dir=" + prof,
         "--no-first-run", "--window-size=1500,950", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(40):
            try:
                tabs = json.load(op.open("http://127.0.0.1:%d/json" % CDP, timeout=2))
                pg = [t for t in tabs if t.get("type") == "page"]
                if pg:
                    ws_url = pg[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.5)
        ws = websocket.create_connection(ws_url, timeout=180)
        _id = [0]

        def send(m, p=None):
            _id[0] += 1
            ws.send(json.dumps({"id": _id[0], "method": m, "params": p or {}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == _id[0]:
                    return msg.get("result", {})

        def ev(e):
            return send("Runtime.evaluate", {"expression": e, "returnByValue": True}) \
                .get("result", {}).get("value")

        send("Page.enable")
        for name, url, ready, extra in VIEWS:
            send("Page.navigate", {"url": "http://127.0.0.1:%d%s" % (port, url)})
            deadline = time.time() + 90
            while time.time() < deadline:
                if ev(ready):
                    break
                time.sleep(1)
            time.sleep(extra)
            shot = send("Page.captureScreenshot", {"format": "png"})
            p = os.path.join(OUT, "现状-%s.png" % name)
            with open(p, "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            print("OK %-8s %4d KB" % (name, os.path.getsize(p) // 1024))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""重截样板E：注入后把「显示内容」组滚进视口。用法: _reshoot_e.py <port>"""
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
CDP = 9375


def main():
    port = int(sys.argv[1])
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "_mock_inject_shots2.py"), encoding="utf-8").read()
    css_e = src.split('CSS_E = """')[1].split('"""')[0]
    js_e = src.split('JS_E = """')[1].split('"""')[0]
    inject = js_e.replace("%CSS_E%", json.dumps(css_e))

    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    prof = os.path.join(OUT, "_prof_cdp9")
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
         "--remote-allow-origins=*", "--user-data-dir=" + prof,
         "--no-first-run", "--window-size=1330,720", "about:blank"],
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
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=ov" % port})
        for _ in range(60):
            if ev("typeof LIB!=='undefined'"):
                break
            time.sleep(1)
        time.sleep(2.5)
        print("注入:", ev(inject))
        time.sleep(0.6)
        ev("var hs=document.querySelectorAll('#view-ov h2'); if(hs[1]) hs[1].scrollIntoView({block:'start'});")
        time.sleep(0.8)
        shot = send("Page.captureScreenshot", {"format": "png"})
        p = os.path.join(OUT, "样板E-屏幕覆盖整页.png")
        with open(p, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("OK", os.path.getsize(p) // 1024, "KB")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

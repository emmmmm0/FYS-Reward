# -*- coding: utf-8 -*-
"""UI 验证：服务端有新版时，设置页更新日志上方亮出「一键更新」横幅。"""
import base64
import io
import json
import os
import re
import subprocess
import time
import urllib.request

import websocket

BASE = "http://127.0.0.1:8807"
SHOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\验证截图-界面巡检"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DOM = os.path.join(os.environ["TEMP"], "upd_ui_dom")
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
os.makedirs(SHOT, exist_ok=True)

_id = [0]


def send(method, params=None):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == _id[0]:
            return m.get("result", {})


def ev(expr):
    r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get("result", {}).get("value")


proc = subprocess.Popen([
    EDGE, "--headless=new", "--disable-gpu", "--remote-debugging-port=9344",
    "--remote-allow-origins=*", "--user-data-dir=" + DOM, "--window-size=1280,800",
    "--no-first-run", "--no-default-browser-check", BASE,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ok_all = True
try:
    ws = None
    for _ in range(40):
        time.sleep(0.5)
        try:
            tabs = json.loads(op.open("http://127.0.0.1:9344/json", timeout=3).read().decode())
            pg = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
            if pg:
                ws = websocket.create_connection(pg[0]["webSocketDebuggerUrl"],
                                                 timeout=60, http_proxy_host=None,
                                                 https_proxy_host=None)
                break
        except Exception:
            pass
    if not ws:
        raise SystemError("CDP 连不上")

    send("Page.enable")
    send("Runtime.enable")
    time.sleep(4)                       # 等 bootReal + checkUpdate
    ev("showView('set')")               # 设置页
    time.sleep(1.5)

    bar = ev("""(function(){
      var b=document.getElementById('updBar');
      return JSON.stringify({shown: b && b.style.display!=='none',
        text: b? b.innerText.replace(/\\n/g,' ').slice(0,60):''})})()""")
    d = json.loads(bar or "{}")
    print("[1] 横幅亮出:", d.get("shown"), "· 文案:", d.get("text"))
    ok_all &= bool(d.get("shown"))

    btn = ev("(function(){var b=document.getElementById('updGo');"
             "return b? '按钮在':'按钮缺失'})()")
    print("[2] 一键更新按钮:", btn)
    ok_all &= (btn == "按钮在")

    d = send("Page.captureScreenshot", {"format": "png"})
    io.open(os.path.join(SHOT, "upd-横幅-v9.9.png"), "wb").write(
        base64.b64decode(d["data"]))
    print("截图已存: upd-横幅-v9.9.png")
finally:
    try:
        proc.terminate()
    except Exception:
        pass
print("结论:", "通过 ✓" if ok_all else "!! 失败")

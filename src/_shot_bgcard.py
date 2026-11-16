# -*- coding: utf-8 -*-
"""补截「界面背景 + 侧栏贴纸」选择器整图（滚到卡片处，亮/暗各一张）。用法：_shot_bgcard.py <port>"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
OUT = os.path.join(ROOT, "验证截图-界面巡检")
CDP = 9395


def launch():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
         "--remote-allow-origins=*", "--user-data-dir=" + os.path.join(OUT, "_prof_bgcard"),
         "--no-first-run", "--window-size=1330,720", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        return send("Runtime.evaluate", {"expression": e, "returnByValue": True}).get("result", {}).get("value")

    return proc, send, ev


def snap(send, path):
    d = send("Page.captureScreenshot", {"format": "png"})
    with open(path, "wb") as f:
        f.write(base64.b64decode(d["data"]))
    print("OK", os.path.basename(path), os.path.getsize(path) // 1024, "KB")


def main():
    port = int(sys.argv[1])
    proc, send, ev = launch()
    send("Page.enable")
    try:
        for tag, theme in (("亮色", "E"), ("夜幕", "N")):
            send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=theme&stk=cloud" % port})
            for _ in range(40):
                if ev("document.readyState==='complete'") and ev("typeof LIB!=='undefined'"):
                    break
                time.sleep(0.6)
            for _ in range(40):
                if ev("document.querySelectorAll('#stkrow .stkopt').length>0"):
                    break
                time.sleep(0.8)
            time.sleep(2.0)
            # 先切主题再让背景卡滚进视野（内容区内部滚动，window.scrollTo 无效）
            ev("typeof applyTheme==='function'&&applyTheme(%s, false)" % json.dumps(theme))
            time.sleep(0.5)
            ev("var b=document.getElementById('bggrid');"
               "b&&b.scrollIntoView({block:'center'});")
            time.sleep(1.2)
            snap(send, os.path.join(OUT, "背景09-界面背景与贴纸选择器-%s.png" % tag))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

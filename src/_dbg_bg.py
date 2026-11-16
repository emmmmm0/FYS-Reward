# -*- coding: utf-8 -*-
"""背景状态诊断：看后端偏好、BGDATA 是否有素材、bgcss 实际内容。用法：_dbg_bg.py <port>"""
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
CDP = 9394


def launch():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    prof = os.path.join(OUT, "_prof_dbg")
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
         "--remote-allow-origins=*", "--user-data-dir=" + prof,
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
    ws = websocket.create_connection(ws_url, timeout=120)
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


def main():
    port = int(sys.argv[1])
    base = "http://127.0.0.1:%d" % port
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    print("A) 清空前 /api/prefs:", json.dumps(json.loads(op.open(base + "/api/prefs", timeout=5).read())
                                             ["prefs"], ensure_ascii=False)[:300])
    op.open(base + "/api/prefs?set=bg&val=null", timeout=5).read()
    print("B) 清空后 /api/prefs:",
          json.dumps(json.loads(op.open(base + "/api/prefs", timeout=5).read())["prefs"],
                     ensure_ascii=False)[:300])

    proc, send, ev = launch()
    send("Page.enable")
    try:
        send("Page.navigate", {"url": base + "/?view=theme"})
        for _ in range(60):
            if ev("typeof LIB!=='undefined'"):
                break
            time.sleep(1)
        time.sleep(3)
        for k, e in [
            ("html[data-bg]", "document.documentElement.getAttribute('data-bg')"),
            ("html[data-theme]", "document.documentElement.getAttribute('data-theme')"),
            ("PREFS.bg", "JSON.stringify(PREFS.bg)"),
            ("PREFS keys", "Object.keys(PREFS).join(',')"),
            ("BGDATA keys", "Object.keys(BGDATA).join(',')"),
            ("BGDATA.pat len", "(BGDATA.pat||'').length"),
            ("bgopt 数量", "document.querySelectorAll('#bggrid .bgopt').length"),
            ("bgopt.on", "(document.querySelector('#bggrid .bgopt.on')||{className:{}}).getAttribute"
                         "?document.querySelector('#bggrid .bgopt.on').getAttribute('data-b'):'NONE'"),
            ("bgcss id 存在", "!!document.getElementById('bgcss')"),
            ("bgcss len", "((document.getElementById('bgcss')||{textContent:''}).textContent||'').length"),
            ("bgcss 开头", "((document.getElementById('bgcss')||{textContent:''}).textContent||'').slice(0,120)"),
            ("sticker", "!!document.getElementById('cuteSticker')"),
            ("再手动 applyBG('cloud') 后 bgcss len",
             "(function(){applyBG('cloud',false);return document.getElementById('bgcss').textContent.length})()"),
        ]:
            print("  %-28s = %s" % (k, ev(e)))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

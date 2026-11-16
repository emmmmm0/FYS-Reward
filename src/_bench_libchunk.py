# -*- coding: utf-8 -*-
"""量地图库列表渲染耗时：分段 vs 一次性。输出各阶段行数与完成时间。"""
import json
import os
import subprocess
import sys
import time

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
PORT, CDP = 9428, 9429
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "http://127.0.0.1:%d" % PORT


def send(ws, method, params=None, mid=1):
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        d = json.loads(ws.recv())
        if d.get("id") == mid:
            return d


def ev(ws, expr, mid=1):
    r = send(ws, "Runtime.evaluate",
             {"expression": expr, "returnByValue": True, "awaitPromise": True}, mid)
    return ((r.get("result") or {}).get("result") or {}).get("value")


def main():
    proc = subprocess.Popen([PY, os.path.join(HERE, "fys_reward_app.py"),
                             "--port", str(PORT)], cwd=HERE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    edge = ws = None
    try:
        import urllib.request
        for _ in range(90):
            try:
                urllib.request.urlopen(BASE + "/api/status", timeout=2).read()
                break
            except Exception:                              # noqa: BLE001
                time.sleep(0.5)
        edge = subprocess.Popen(
            [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
             "--user-data-dir=" + os.path.join(HERE, "_prof_bench"), "--disable-gpu",
             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(
                    "http://127.0.0.1:%d/json" % CDP, timeout=2))
                page = [t for t in tabs if t.get("type") == "page"]
                if page:
                    ws_url = page[0]["webSocketDebuggerUrl"]
                    break
            except Exception:                              # noqa: BLE001
                time.sleep(0.5)
        ws = websocket.create_connection(ws_url, timeout=60)
        send(ws, "Runtime.enable", mid=900)
        send(ws, "Page.navigate", {"url": BASE + "/?noreadme=1"}, mid=902)
        for _ in range(60):
            if ev(ws, "typeof tick==='function'"):
                break
            time.sleep(0.25)
        ev(ws, "showView('lib')")
        for _ in range(120):
            n = ev(ws, "(typeof LIB!=='undefined'&&LIB.all)?LIB.all.length:0") or 0
            if n:
                break
            time.sleep(0.5)
        print("index:", n)

        # 连测三轮：浏览器内记 libRender 开始到「行数==结果数」的耗时
        for trial in range(3):
            r = ev(ws, """(function(){
              return new Promise(function(res){
                var t0=performance.now();
                libRender();
                var first=document.querySelectorAll('#libList .libRow').length;
                var total=LIB.all.filter(libFilt).filter(libHit).length;
                (function poll(){
                  if(document.querySelectorAll('#libList .libRow').length>=total){
                    res({first:first,total:total,ms:performance.now()-t0});return;}
                  setTimeout(poll,10);
                })();
              });
            })()""")
            print("trial%d: 首屏 %s 行 / 全部 %s 行 / 完成耗时 %.0f ms"
                  % (trial, r["first"], r["total"], r["ms"]))
        # 输入延迟模拟：改关键词到首屏出现
        r = ev(ws, """(function(){
          var q=document.getElementById('libQ'); q.value='ze';
          var t0=performance.now(); libRender();
          return {ms: performance.now()-t0, rows: document.querySelectorAll('#libList .libRow').length};
        })()""")
        print("typing->首屏: %.0f ms (%s 行)" % (r["ms"], r["rows"]))
    finally:
        try:
            if ws:
                ws.close()
        except Exception:                                  # noqa: BLE001
            pass
        for p in (edge, proc):
            if p:
                try:
                    p.terminate()
                except Exception:                          # noqa: BLE001
                    pass
        time.sleep(1)


if __name__ == "__main__":
    main()

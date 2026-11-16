# -*- coding: utf-8 -*-
"""地图库「🧩 EXG 补充」分类效果截图。

起真实后端（本机 HTTP，不启 webview）+ headless Edge（CDP 控制）：
  1. 全量地图库（分类 chip 栏可见）
  2. 点「🧩 EXG 补充」→ 只剩 99 张，每行带 🧩
  3. 选中一张 EXG 图 → 详情页分类徽标 + 估算说明

用法：python _shot_exglib.py
"""
import base64
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
W = os.path.dirname(HERE)
SHOT = os.path.join(HERE, "_shot")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROF = os.path.join(W, "验证截图-界面巡检", "_prof_exgshot")
PORT = 8801

import websocket                                                    # noqa: E402
import fys_reward_app as A                                          # noqa: E402
import reward_server as engine                                      # noqa: E402

A.State.engine = engine
meta = engine.load_state(force=False)
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
print("本机服务已启动 %s（地图 %s 张 / 关卡 %s 段）"
      % (A.State.url, meta.get("maps"), meta.get("stages")))
time.sleep(0.8)
os.makedirs(SHOT, exist_ok=True)

R = []


def ev(ws, expr):
    ws.send(json.dumps({"id": ev._i, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True}}))
    ev._i += 1
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == ev._i - 1:
            if "exceptionDetails" in r:
                return "__ERR__ " + json.dumps(r["exceptionDetails"])[:200]
            return r.get("result", {}).get("result", {}).get("value")


ev._i = 1


def shot(ws, name):
    ws.send(json.dumps({"id": ev._i, "method": "Page.captureScreenshot",
                        "params": {"format": "png", "captureBeyondViewport": False}}))
    ev._i += 1
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == ev._i - 1:
            d = r.get("result", {}).get("data")
            if not d:
                print("  %-30s FAIL %s" % (name, json.dumps(r)[:160]))
                return None
            p = os.path.join(SHOT, name + ".png")
            with io.open(p, "wb") as fh:
                fh.write(base64.b64decode(d))
            print("  %-30s OK   %.0f KB" % (name, os.path.getsize(p) / 1024.0))
            R.append(p)
            return p


edge = subprocess.Popen(
    [EDGE, "--headless=new", "--remote-debugging-port=9397",
     "--remote-allow-origins=*", "--user-data-dir=" + PROF, "--no-first-run",
     "--hide-scrollbars", "--window-size=1360,820", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ws_url = None
    import urllib.request
    _op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(60):
        try:
            tabs = json.load(_op.open("http://127.0.0.1:9397/json", timeout=2))
            page = [t for t in tabs if t.get("type") == "page"]
            if page:
                ws_url = page[0]["webSocketDebuggerUrl"]
                break
        except Exception:
            time.sleep(0.5)
    assert ws_url, "Edge CDP 起不来"
    ws = websocket.create_connection(ws_url, timeout=60)
    ws.send(json.dumps({"id": 900, "method": "Runtime.enable"}))
    ws.send(json.dumps({"id": 902, "method": "Page.navigate",
                        "params": {"url": A.State.url.rstrip("/") + "/?view=lib&theme=E"}}))
    for _ in range(100):
        if ev(ws, "typeof libRender==='function' && Array.isArray(LIB.all) && LIB.all.length>700"):
            break
        time.sleep(0.3)
    print("\n── 截图 ──")
    time.sleep(1.5)
    shot(ws, "exg-01-地图库分类栏")

    ev(ws, "document.querySelector('#libChips .libChip[data-t=exg]').click()")
    time.sleep(1.2)
    print("     筛选后行数 =", ev(ws, "document.querySelectorAll('#libList .libRow').length"),
          "| 计数 =", ev(ws, "document.getElementById('libCnt').textContent"))
    shot(ws, "exg-02-筛选出99张")

    ev(ws, "libSelect('ze_1_schizo'); libPulse('ze_1_schizo');")
    time.sleep(1.2)
    print("     详情徽标 =", ev(ws, "!!document.querySelector('#libDetail .libExg')"),
          "| 标题 =", ev(ws, "document.querySelector('#libDetail .libHead .cn').textContent"))
    shot(ws, "exg-03-详情页分类与估算说明")

    ev(ws, "document.querySelector('#libChips .libChip[data-t=all]').click();"
           "$('libQ').value='天使的心跳'; libRender();")
    time.sleep(1.2)
    shot(ws, "exg-04-中文名可搜")
finally:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(edge.pid)],
                   capture_output=True, timeout=10)
print("\n截图 %d 张 → %s" % (len(R), SHOT))

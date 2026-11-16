# -*- coding: utf-8 -*-
"""全维度审查 · 前端性能测量 + 全页面截图。端口 9436 / CDP 9437。"""
import base64
import json
import os
import subprocess
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 9436
CDP = 9437
BASE = "http://127.0.0.1:%d" % PORT
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W = os.path.dirname(HERE)
SHOT_DIR = os.path.join(W, "验证截图-界面巡检")
PROFILE = os.path.join(SHOT_DIR, "_prof_audit")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_seq = [1]


def send(ws, method, params=None):
    i = _seq[0]
    _seq[0] += 1
    ws.send(json.dumps({"id": i, "method": method,
                        "params": params if params is not None else {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == i:
            return r


def ev(ws, expr):
    r = send(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return ((r.get("result") or {}).get("result") or {}).get("value")


def shot(ws, name, width=1500, height=980):
    send(ws, "Emulation.setDeviceMetricsOverride",
         {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
    time.sleep(0.3)
    d = send(ws, "Page.captureScreenshot", {"format": "png"})
    data = (d.get("result") or {}).get("data")
    p = os.path.join(SHOT_DIR, "audit_" + name + ".png")
    with open(p, "wb") as fh:
        fh.write(base64.b64decode(data))
    print("shot:", name, os.path.getsize(p) // 1024, "KB")


def main():
    proc = subprocess.Popen(
        [PY, os.path.join(HERE, "fys_reward_app.py"), "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    edge = None
    ws = None
    try:
        for _ in range(60):
            try:
                OPENER.open(BASE + "/api/prefs", timeout=2).read()
                break
            except Exception:
                time.sleep(0.5)
        # 预热 maplib（消除冷构建对前端测量的干扰）
        t0 = time.perf_counter()
        OPENER.open(BASE + "/api/maplib", timeout=120).read()
        print("maplib cold(HTTP): %.0f ms" % ((time.perf_counter() - t0) * 1000))
        t0 = time.perf_counter()
        OPENER.open(BASE + "/api/maplib", timeout=60).read()
        print("maplib warm(HTTP): %.0f ms" % ((time.perf_counter() - t0) * 1000))

        edge = subprocess.Popen(
            [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
             "--remote-allow-origins=*", "--user-data-dir=" + PROFILE,
             "--no-first-run", "--hide-scrollbars",
             "--window-size=1500,1080", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        for _ in range(60):
            try:
                tabs = json.load(OPENER.open(
                    "http://127.0.0.1:%d/json" % CDP, timeout=2))
                pg = [t for t in tabs if t.get("type") == "page"]
                if pg:
                    ws_url = pg[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.5)
        ws = websocket.create_connection(ws_url, timeout=90)
        send(ws, "Runtime.enable")
        send(ws, "Page.enable")
        send(ws, "Emulation.setDeviceMetricsOverride",
             {"width": 1500, "height": 980, "deviceScaleFactor": 1, "mobile": False})

        # 首屏：从 about:blank 导航到 / ，测DOMContentLoaded+可交互时间
        t0 = time.perf_counter()
        send(ws, "Page.navigate", {"url": BASE + "/"})
        for _ in range(300):
            rd = ev(ws, "document.readyState")
            if rd == "complete":
                break
            time.sleep(0.1)
        print("page load(readyState=complete): %.0f ms" % ((time.perf_counter() - t0) * 1000))
        time.sleep(3)
        ev(ws, "applyTheme('E',false); showView('srv')")

        # 进地图库并等索引
        ev(ws, "showView('lib')")
        n = 0
        for _ in range(90):
            n = ev(ws, "(typeof LIB!=='undefined'&&LIB.all)?LIB.all.length:0") or 0
            if n:
                break
            time.sleep(1)
        print("lib index:", n)
        time.sleep(2)

        # 渲染性能：全量列表渲染 / 搜索过滤 / 滚动
        r = ev(ws, "(function(){"
                   "var t0=performance.now();libRender();var t1=performance.now();"
                   "var q=document.getElementById('libQ');q.value='ze';"
                   "q.dispatchEvent(new Event('input'));var t2=performance.now();"
                   "q.value='';libRender();var t3=performance.now();"
                   "return JSON.stringify({fullRender:Math.round(t1-t0),"
                   "searchFilter:Math.round(t2-t1),restore:Math.round(t3-t2),"
                   "rows:document.querySelectorAll('#libList .libRow').length,"
                   "imgs:document.querySelectorAll('#libList img.libBg').length})})()")
        print("render:", r)

        # 进详情页测 mapdiff/cfg 加载
        ev(ws, "(function(){var r=document.querySelector('#libList .libRow');"
               "if(r)r.click();})()")
        time.sleep(1.5)
        shot(ws, "detail_浅色")
        ev(ws, "showView('lib');history.replaceState(null,'','?view=lib')")
        time.sleep(0.6)
        shot(ws, "lib_浅色")
        ev(ws, "showView('srv')")
        time.sleep(1.2)
        shot(ws, "srv_浅色")
        ev(ws, "showView('set')")
        time.sleep(1.0)
        shot(ws, "set_浅色")
        ev(ws, "showView('theme')")
        time.sleep(1.0)
        shot(ws, "theme_浅色")
        # 夜幕主题抽查
        ev(ws, "applyTheme('N',false);showView('srv')")
        time.sleep(1.0)
        shot(ws, "srv_夜幕")
        ev(ws, "showView('lib')")
        time.sleep(0.8)
        shot(ws, "lib_夜幕")
        ev(ws, "applyTheme('E',false)")
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        for p in (edge, proc):
            if p:
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                                   capture_output=True)
                except Exception:
                    pass
        time.sleep(1.5)


if __name__ == "__main__":
    main()

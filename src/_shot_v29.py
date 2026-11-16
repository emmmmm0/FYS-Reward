# -*- coding: utf-8 -*-
"""v2.9 新界面实测截图：地图库「地图参数」卡 + 「上游更新动态」面板。

自起应用（源码态，独立端口）→ headless Edge（CDP）→ 操作 → 截图。
产物落在工作区根 `验证截图-界面巡检/v29_*.png`。
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = os.path.join(ROOT, "验证截图-界面巡检")
PROFILE = os.path.join(ROOT, "_shot_v29_prof")
PORT = 8801
CDP = 9401
BASE = "http://127.0.0.1:%d" % PORT
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TARGET = "ze_obj_abyss_v2"

_seq = [1]


def send(ws, method, params=None):
    i = _seq[0]
    _seq[0] += 1
    ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == i:
            return r


def ev(ws, expr):
    r = send(ws, "Runtime.evaluate",
             {"expression": expr, "returnByValue": True})
    res = r.get("result", {})
    if "exceptionDetails" in res:
        return "__ERR__" + json.dumps(res["exceptionDetails"])[:240]
    return res.get("result", {}).get("value")


def wait(ws, expr, secs=25, step=0.25):
    for _ in range(int(secs / step)):
        v = ev(ws, expr)
        if v:
            return v
        time.sleep(step)
    return None


def shot(ws, name):
    p = os.path.join(OUT, name)
    r = send(ws, "Page.captureScreenshot", {"format": "png"})
    with open(p, "wb") as fh:
        fh.write(base64.b64decode(r["result"]["data"]))
    print("  截图 %-34s %8d bytes" % (name, os.path.getsize(p)))
    return p


def main():
    os.makedirs(OUT, exist_ok=True)
    shutil.rmtree(PROFILE, ignore_errors=True)
    proc = subprocess.Popen([PY, os.path.join(HERE, "fys_reward_app.py"),
                             "--port", str(PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    edge = None
    try:
        for _ in range(80):
            try:
                OPENER.open(BASE + "/api/prefs", timeout=2).read()
                break
            except Exception:
                time.sleep(0.5)
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
        assert ws_url, "Edge CDP 起不来"
        ws = websocket.create_connection(ws_url, timeout=90)
        send(ws, "Runtime.enable")
        send(ws, "Page.enable")
        send(ws, "Emulation.setDeviceMetricsOverride",
             {"width": 1500, "height": 1080, "deviceScaleFactor": 1,
              "mobile": False})
        send(ws, "Page.navigate", {"url": BASE + "/?noreadme=1"})
        wait(ws, "typeof tick==='function' && !!document.getElementById('grid')")

        # ── ① 地图库：地图参数卡 ──
        ev(ws, "showView('lib')")
        wait(ws, "!!(window.LIB && LIB.all && LIB.all.length)")
        print("  地图库总数 =", ev(ws, "(LIB.all||[]).length"))
        ev(ws, "LIB.cur=LIB.all.filter(function(r){return r.f==='%s'})[0];"
               "libRender(); libDetail(); 'ok'" % TARGET)
        n = wait(ws, "document.querySelectorAll('#libCfg .cfgRow').length")
        print("  参数行数 =", n)
        # 页面每秒轮询 /api/status，中途会把视图重置回服务器页（showView 不记忆），
        # 所以截图前必须**再切一次**并确认 view-lib 真的挂上了 on
        ev(ws, "showView('lib')")
        wait(ws, "document.getElementById('view-lib').className.indexOf('on')>=0",
             secs=8)
        ev(ws, "var e=document.getElementById('libCfg');"
               "if(e) e.scrollIntoView({block:'start'}); 'ok'")
        time.sleep(0.8)
        print("  当前视图 =", ev(ws,
              "(document.querySelector('.view.on')||{}).id"))
        shot(ws, "v29_地图参数卡.png")

        # ── ② 上游更新动态弹窗 ──
        ev(ws, "openUpdLog()")
        m = wait(ws, "document.querySelectorAll('#updOvBody .ulItem').length")
        print("  台账条目 =", m, "|", ev(ws, "(document.getElementById('updOvSub')||{}).textContent"))
        time.sleep(0.5)
        shot(ws, "v29_上游更新动态.png")
        ev(ws, "closeUpdLog()")

        # ── ③ 设置页（含入口卡与版本号）──
        ev(ws, "showView('set')")
        time.sleep(1.0)
        ev(ws, "var e=document.getElementById('ulCard');"
               "if(e) e.scrollIntoView({block:'center'}); 'ok'")
        time.sleep(0.5)
        shot(ws, "v29_设置页入口.png")
        print("  v2.9 =", ev(ws, "typeof APP_VER!=='undefined'?APP_VER:''"))
    finally:
        if edge is not None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(edge.pid)],
                           capture_output=True)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True)
        time.sleep(0.8)
        shutil.rmtree(PROFILE, ignore_errors=True)


if __name__ == "__main__":
    main()

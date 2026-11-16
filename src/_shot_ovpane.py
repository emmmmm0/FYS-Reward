# -*- coding: utf-8 -*-
"""覆盖设置页「分区折叠」实拍截图：默认态 / 全部展开 / 只留进阶。

用法：python _shot_ovpane.py
截图落到 工作区/验证截图-覆盖设置页/。
"""
import json
import os
import subprocess
import sys
import time

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.dirname(HERE)
SHOT = os.path.join(W, "验证截图-覆盖设置页")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8855
CDP = 9412
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
import urllib.request  # noqa: E402

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

os.makedirs(SHOT, exist_ok=True)
PROF = os.path.join(HERE, "_prof_ovpane")


def edge_shot(name, url, inject=None, size="1200,1400", budget=9000):
    """用 CDP 打开页面、跑一段 JS、按整页截图。"""
    tabs = json.load(OPENER.open("http://127.0.0.1:%d/json" % CDP, timeout=5))
    ws = websocket.create_connection(
        [t for t in tabs if t.get("type") == "page"][0]["webSocketDebuggerUrl"], timeout=60)
    by_id = {}

    def call(_id, method, params, timeout=budget + 20000):
        ws.send(json.dumps({"id": _id, "method": method, "params": params or {}}))
        end = time.time() + timeout / 1000.0
        while time.time() < end:
            try:
                r = json.loads(ws.recv())
            except Exception:
                break
            if "id" in r:
                by_id[r["id"]] = r
                if r["id"] == _id:
                    return r
            elif r.get("method") == "Runtime.exceptionThrown":
                pass
        raise RuntimeError("CDP 超时：" + method)

    def ev(expr):
        r = call(90, "Runtime.evaluate",
                 {"expression": expr, "returnByValue": True}, timeout=20000)
        res = r.get("result", {})
        return res.get("result", {}).get("value")

    call(1, "Runtime.enable", {})
    call(2, "Page.enable", {})
    call(3, "Emulation.setDeviceMetricsOverride",
         {"width": 1200, "height": 1400, "deviceScaleFactor": 1, "mobile": False})
    call(4, "Page.navigate", {"url": url})
    time.sleep(3.2)
    call(5, "Emulation.setDeviceMetricsOverride",
         {"width": 1200, "height": 1400, "deviceScaleFactor": 1, "mobile": False})
    ev("document.body.style.margin='0';"
       "document.querySelectorAll('.main').forEach(function(m){m.style.maxHeight='none'});"
       "document.querySelectorAll('.view').forEach(function(v){v.style.overflow='visible'});"
       + (inject or ""))
    if "location.reload" in (inject or ""):
        time.sleep(3.5)      # 清掉折叠记忆后重载，才是真正的出厂默认态
    time.sleep(1.0)
    h = ev("Math.min(document.documentElement.scrollHeight,1400)")
    call(6, "Emulation.setDeviceMetricsOverride",
         {"width": 1200, "height": int(h or 1400), "deviceScaleFactor": 1, "mobile": False})
    time.sleep(0.6)
    d = call(7, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
    b64 = d.get("result", {}).get("data", "")
    out = os.path.join(SHOT, name + ".png")
    with open(out, "wb") as fh:
        fh.write(__import__("base64").b64decode(b64))
    ws.close()
    return out, os.path.getsize(out)


def main():
    import fys_reward_app as A
    import reward_server as engine

    A.State.engine = engine
    meta = engine.load_state(force=False)
    A.State.port = PORT
    A.State.url = "http://127.0.0.1:%d/" % PORT
    A.start_http_server(PORT)
    BASE = A.State.url.rstrip("/")
    print("本机服务 %s（地图 %s / 关卡 %s）" % (BASE, meta.get("maps"), meta.get("stages")))

    app = subprocess.Popen([PY, os.path.join(HERE, "fys_reward_app.py"),
                            "--port", str(PORT)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    br = None
    try:
        for _ in range(60):
            try:
                OPENER.open(BASE + "/api/prefs", timeout=3).read()
                break
            except Exception:
                time.sleep(0.5)
        br = subprocess.Popen(
            [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
             "--remote-allow-origins=*", "--user-data-dir=" + PROF,
             "--no-first-run", "--hide-scrollbars", "--window-size=1200,1400",
             "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.0)

        print("\n── 截图 ──")
        cases = [
            ("01-覆盖设置-默认态", BASE + "/?view=ov&theme=E",
             "localStorage.removeItem('fys_ov_panes');location.reload();"),
            ("02-覆盖设置-全部展开", BASE + "/?view=ov&theme=E",
             "localStorage.removeItem('fys_ov_panes');"
             "document.querySelectorAll('.ovpane').forEach(function(d){d.open=true});"),
            ("03-覆盖设置-只留常用", BASE + "/?view=ov&theme=N",
             "localStorage.setItem('fys_ov_panes',JSON.stringify({style:true,show:true,"
             "out:false,adv:false,obs:false}));"
             "document.querySelectorAll('.ovpane').forEach(function(d){"
             "d.open=['style','show'].indexOf(d.getAttribute('data-pane'))>=0});"),
        ]
        for name, url, js in cases:
            out, sz = edge_shot(name, url, js)
            print("  %-24s %6.1f KB  %s" % (name, sz / 1024.0, out))
    finally:
        for p in (br, app):
            if p:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                               capture_output=True, timeout=10)
    print("\n截图目录：%s" % SHOT)


main()

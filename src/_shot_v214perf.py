# -*- coding: utf-8 -*-
"""截图：v2.14 性能/体验改动的界面效果。

  v214d_设置页_同步进度条.png     （注入一个假的 40% 同步态，只看界面）
  v214d_详情_无变化一行.png       （地图库详情：本次数据更新缩成一行）
  v214d_地图库_分段渲染.png       （列表正常 + 计数）
"""
import base64
import json
import os
import subprocess
import sys
import time

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
PORT, CDP = 9424, 9425
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
SHOT_DIR = os.path.join(os.path.dirname(HERE), "验证截图-界面巡检")
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


def shot(ws, path, clip=None):
    p = {"format": "png"}
    if clip:
        p["clip"] = clip
    d = send(ws, "Page.captureScreenshot", p)
    data = (d.get("result") or {}).get("data")
    if not data:
        raise RuntimeError("captureScreenshot 失败: %r" % str(d)[:200])
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(data))
    print("  saved", os.path.basename(path))


def wait_up(port, timeout=90):
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/api/status" % port,
                                   timeout=2).read()
            return True
        except Exception:                                  # noqa: BLE001
            time.sleep(0.5)
    return False


def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
    proc = subprocess.Popen([PY, os.path.join(HERE, "fys_reward_app.py"),
                             "--port", str(PORT)],
                            cwd=HERE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    edge = None
    ws = None
    try:
        if not wait_up(PORT):
            raise RuntimeError("服务 %d 没起来（可能是端口被占/单实例锁）" % PORT)
        edge = subprocess.Popen(
            [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
             "--user-data-dir=" + os.path.join(HERE, "_prof_v214perf"),
             "--window-size=1500,980", "--disable-gpu", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import urllib.request
        from urllib.request import urlopen
        ws_url = None
        for _ in range(60):
            try:
                tabs = json.load(OPENER if False else urlopen(
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
        for _ in range(80):
            if ev(ws, "typeof tick==='function' && !!document.getElementById('grid')"):
                break
            time.sleep(0.25)

        # A. 设置页：注入一个假的同步进度（只改界面，不真的同步）。
        #    tick 每秒轮询会用真实状态覆盖注入值，所以直接接管 syncUI，
        #    截完立即还原（还原后下一轮 tick 恢复真实显示）。
        ev(ws, "applyTheme('E',false); showView('set');")
        time.sleep(1.2)
        ev(ws, "(function(){window.__realSyncUI=syncUI;"
               "syncUI=function(){__realSyncUI({sync:{running:true,"
               "msg:'正在解包并解析官方配置…',pct:40}});};syncUI();})()")
        time.sleep(0.4)
        shot(ws, os.path.join(SHOT_DIR, "v214d_设置页_同步进度条.png"))
        ev(ws, "syncUI=window.__realSyncUI; syncUI({sync:{running:false,ok:null}});")

        # B. 地图库 + 详情（无变化一行）
        ev(ws, "showView('lib');")
        print("  href:", ev(ws, "location.href"), "| view:", ev(ws, "CURVIEW"),
              "| LIB type:", ev(ws, "typeof LIB"),
              "| loading:", ev(ws, "(typeof LIB!=='undefined')?JSON.stringify(LIB.loading):'?'"),
              "| err:", ev(ws, "window.__errCount"))
        n = 0
        for _ in range(90):
            n = ev(ws, "(typeof LIB!=='undefined'&&LIB.all)?LIB.all.length:0") or 0
            if n:
                break
            time.sleep(1)
        time.sleep(2.5)                     # 等分段渲染把剩余行补齐
        print("  lib rows:", ev(ws, "document.querySelectorAll('#libList .libRow').length"),
              "/", n)
        ev(ws, "(function(){var rs=document.querySelectorAll('#libList .libRow');"
               "if(rs[3]) rs[3].click();})()")
        time.sleep(2.0)
        shot(ws, os.path.join(SHOT_DIR, "v214d_详情_无变化一行.png"))
        print("  diff card:", ev(ws, "(function(){var b=$('libDiff');"
                                "return b? (b.style.display+'|'+b.className+'|'+"
                                "b.textContent.slice(0,60)):'none'})()"))
    finally:
        try:
            if ws:
                ws.close()
        except Exception:                                   # noqa: BLE001
            pass
        for p in (edge, proc):
            if p:
                try:
                    p.terminate()
                except Exception:                           # noqa: BLE001
                    pass
        time.sleep(1.2)


if __name__ == "__main__":
    main()

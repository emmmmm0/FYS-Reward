# -*- coding: utf-8 -*-
"""「地图参数新旧对比」三张指引截图（2026-10-27 用户问：这功能在哪）。

A. 地图库详情页「🆕 本次数据更新」对比卡（造一份 prev 快照让 ze_atos 有差异）
B. 没变化的图的占位说明行（v2.14 新增：告诉用户比对位在哪）
C. 「上游更新动态」弹窗 · 按 🔧 地图参数 筛选 · 展开真实历史记录（旧值 → 新值）

用法：python _shot_upddiff_ui.py（端口 9412 / CDP 9413；结束还原 data/*.prev.json）
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
PORT = 9412
CDP = 9413
BASE = "http://127.0.0.1:%d" % PORT
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W = os.path.dirname(HERE)
SHOT_DIR = os.path.join(W, "验证截图-界面巡检")
PROFILE = os.path.join(SHOT_DIR, "_prof_upddiff_ui")
DATA = os.path.join(HERE, "data")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_seq = [1]
MAP = "ze_atos"          # 有差异样图
MAP_PLAIN = "ze_mota"    # 无差异样图


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
    res = r.get("result", {})
    if "exceptionDetails" in res:
        return "__ERR__" + json.dumps(res["exceptionDetails"])[:200]
    return res.get("result", {}).get("value")


def wait(ws, expr, secs=45, step=0.25):
    for _ in range(int(secs / step)):
        v = ev(ws, expr)
        if v:
            return v
        time.sleep(step)
    return None


def shot(ws, name):
    s = send(ws, "Page.captureScreenshot", {"format": "png"})
    p = os.path.join(SHOT_DIR, name)
    with open(p, "wb") as fh:
        fh.write(base64.b64decode(s["result"]["data"]))
    print("  [shot] %s" % p)


def _bak():
    b = {}
    for n in ("rewards", "maps", "mapcfg", "infect"):
        p = os.path.join(DATA, n + ".prev.json")
        if os.path.exists(p):
            b[n] = p + ".shot-bak"
            os.replace(p, b[n])
    return b


def _restore(b):
    for n, bak in b.items():
        p = os.path.join(DATA, n + ".prev.json")
        if os.path.exists(p):
            os.remove(p)
        if bak and os.path.exists(bak):
            os.replace(bak, p)


def _craft_prev():
    """复制当前数据为 prev，再把 ze_atos 改两处 → 详情页出现对比卡。"""
    cur = {}
    for n in ("rewards", "maps", "mapcfg", "infect"):
        p = os.path.join(DATA, n + ".json")
        cur[n] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else (
            None if n == "mapcfg" else {})
    prev = {n: (json.loads(json.dumps(v)) if v is not None else {})
            for n, v in cur.items()}
    st = prev["rewards"][MAP]["1"]
    st["rankPasses"] = int(st.get("rankPasses") or 10) + 1
    prev["maps"][MAP]["price"] = int(prev["maps"][MAP].get("price") or 0) + 50
    for n in ("rewards", "maps", "mapcfg", "infect"):
        with open(os.path.join(DATA, n + ".prev.json"), "w", encoding="utf-8") as fh:
            json.dump(prev[n], fh, ensure_ascii=False, indent=None)


def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
    proc = edge = None
    bak = {}
    try:
        bak = _bak()
        _craft_prev()
        proc = subprocess.Popen(
            [PY, os.path.join(HERE, "fys_reward_app.py"), "--port", str(PORT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(80):
            try:
                OPENER.open(BASE + "/api/prefs", timeout=2).read()
                break
            except Exception:                                  # noqa: BLE001
                time.sleep(0.5)
        elog = open(os.path.join(SHOT_DIR, "_upddiff_ui_edge.log"), "wb")
        edge = subprocess.Popen(
            [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
             "--remote-allow-origins=*", "--user-data-dir=" + PROFILE,
             "--no-first-run", "--hide-scrollbars", "--disable-gpu",
             "--window-size=1500,1080", "about:blank"],
            stdout=elog, stderr=subprocess.STDOUT)
        ws_url = None
        for _ in range(160):
            try:
                tabs = json.loads(OPENER.open(
                    "http://127.0.0.1:%d/json" % CDP, timeout=3).read())
                pg = [t for t in tabs if t.get("type") == "page"]
                if pg:
                    ws_url = pg[0]["webSocketDebuggerUrl"]
                    break
            except Exception:                                  # noqa: BLE001
                time.sleep(0.5)
        assert ws_url, "Edge CDP 起不来"
        ws = websocket.create_connection(ws_url, timeout=120)
        send(ws, "Runtime.enable")
        send(ws, "Page.enable")
        send(ws, "Emulation.setDeviceMetricsOverride",
             {"width": 1500, "height": 1080, "deviceScaleFactor": 1,
              "mobile": False})
        send(ws, "Page.navigate", {"url": BASE + "/?noreadme=1"})
        wait(ws, "typeof libLoad==='function'", secs=30)
        ev(ws, "applyTheme('L',false)")
        ev(ws, "showView('lib')")
        wait(ws, "LIB.all && LIB.all.length>100", secs=90)

        # A：有差异的图 → 「本次数据更新」对比卡
        ev(ws, "LIB.pend=%s; libGoto(%s)" % (json.dumps(MAP), json.dumps(MAP)))
        ok = wait(ws, "(function(){var b=document.querySelector('#libDiff');"
                  "return b && b.style.display!=='none' && "
                  "b.textContent.indexOf('本次数据更新')>=0;})()", secs=30)
        print("  A 对比卡出现:", bool(ok))
        ev(ws, "(function(){var b=document.getElementById('libDetail');"
           "if(b) b.scrollTop=0;})()")
        time.sleep(0.6)
        shot(ws, "v214_对比卡_地图详情.png")

        # B：没变化的图 → 占位说明行
        ev(ws, "LIB.pend=%s; libGoto(%s)" % (json.dumps(MAP_PLAIN),
                                             json.dumps(MAP_PLAIN)))
        ok = wait(ws, "(function(){var b=document.querySelector('#libDiff');"
                  "return b && b.style.display!=='none' && "
                  "b.textContent.indexOf('与上次同步前一致')>=0;})()", secs=30)
        print("  B 占位说明出现:", bool(ok))
        time.sleep(0.6)
        shot(ws, "v214_对比位_无变化说明.png")

        # C：上游更新动态 · 筛选「地图参数」· 展开真实历史（旧 → 新）
        ev(ws, "openUpdLog(); UL_GFILT='地图参数'; ulModal();")
        ok = wait(ws, "(function(){var b=document.querySelector('#updOvBody');"
                  "return b && b.textContent.indexOf('→')>=0 && "
                  "b.textContent.indexOf('地图参数')>=0;})()", secs=30)
        print("  C 台账参数明细出现:", bool(ok))
        time.sleep(0.6)
        shot(ws, "v214_更新动态_参数旧新.png")
        err = ev(ws, "window.__errCount||0")
        print("  页面 JS 报错:", err)
    finally:
        _restore(bak)
        for p in (edge, proc):
            if p is not None:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                               capture_output=True)
        time.sleep(0.8)
        shutil.rmtree(PROFILE, ignore_errors=True)


if __name__ == "__main__":
    main()

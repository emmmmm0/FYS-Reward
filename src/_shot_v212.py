# -*- coding: utf-8 -*-
"""v2.12 两处新界面截图 + 断言（不加回归编号，供界面巡检）。

  ① 地图库索引加载等待态：spinner + 已等待秒数（不再是干巴巴一行字）
  ② 地图详情头卡封面底图（红框那块），404 的图仍要正常渲染

用法：python _shot_v212.py [port]（缺省 9425）
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9425
BASE = "http://127.0.0.1:%d" % PORT
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W = os.path.dirname(HERE)
PROFILE = os.path.join(W, "验证截图-界面巡检", "_prof_v212")
SHOT_DIR = os.path.join(W, "验证截图-界面巡检")
CDP = 9426
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
R = []
_seq = [1]


def check(name, ok, extra=""):
    R.append((name, bool(ok), extra))


def send(ws, method, params=None):
    i = _seq[0]
    _seq[0] += 1
    ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == i:
            return r


def ev(ws, expr):
    r = send(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    res = r.get("result", {})
    if "exceptionDetails" in res:
        return "__ERR__" + json.dumps(res["exceptionDetails"])[:240]
    return res.get("result", {}).get("value")


def wait(ws, expr, secs=60, step=0.25):
    for _ in range(int(secs / step)):
        v = ev(ws, expr)
        if v:
            return v
        time.sleep(step)
    return None


def shot(ws, path):
    r = send(ws, "Page.captureScreenshot", {"format": "png"})
    if "data" not in r.get("result", {}):
        raise RuntimeError("截图失败：%s" % json.dumps(r)[:200])
    open(path, "wb").write(base64.b64decode(r["result"]["data"]))


def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
    proc = edge = None
    try:
        proc = subprocess.Popen(
            [PY, os.path.join(HERE, "fys_reward_app.py"), "--port", str(PORT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(80):
            try:
                OPENER.open(BASE + "/api/prefs", timeout=2).read()
                break
            except Exception:                                  # noqa: BLE001
                time.sleep(0.5)
        elog = open(os.path.join(SHOT_DIR, "_v212_edge.log"), "wb")
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

        # ── ① 等待态截图：给 maplib 响应加 3s 延迟（模拟首启慢加载），spinner 期间拍 ──
        ev(ws, "showView('lib')")
        wait(ws, "LIB.all && LIB.all.length>100", secs=90)
        ev(ws, "(function(){var real=window.get;"
               "window.__realGet=real;"
               "window.get=function(u){"
               "if(String(u).indexOf('/api/maplib')===0){"
               "return new Promise(function(res){"
               "setTimeout(function(){res(real(u));},3000);});}"
               "return real.apply(null,arguments);};return 1;})()")
        ev(ws, "LIB.all=null;LIB.cfg={};libLoad(true,true)")
        time.sleep(1.6)                     # 让 spinner + 「已等待 1 秒」先画出来
        wait_txt = ev(ws, "(document.querySelector('.libWaitTxt')||{}).textContent||''")
        sub_txt = ev(ws, "(document.querySelector('.libWaitSub')||{}).textContent||''")
        spin = ev(ws, "!!document.querySelector('.libSpin')")
        check("等待态有 spinner + 文案（%r / %r）" % (wait_txt, sub_txt),
              spin and "正在读取" in (wait_txt or "") and "已等待" in (sub_txt or ""))
        shot(ws, os.path.join(SHOT_DIR, "v212_索引加载等待.png"))
        ev(ws, "window.get=window.__realGet")   # 还原，免得影响后面的用例

        # ── ② 详情头卡封面（有封面的图 + 无封面的图各一张） ──
        for name, tag in (("ze_2021_xmas_world_p", "有封面"),
                          ("ze_mota", "无封面")):
            ev(ws, "LIB.pend=%s; libGoto(%s)" % (json.dumps(name), json.dumps(name)))
            wait(ws, "LIB.cur && String(LIB.cur.f)===%s" % json.dumps(name), secs=20)
            time.sleep(0.6)
            cv = ev(ws, "(function(){var c=document.querySelector('#libDetail .card.libCv');"
                    "if(!c) return 'NO-CARD';"
                    "var img=getComputedStyle(c,'::before').backgroundImage;"
                    "return (img&&img.indexOf('/cover/')>=0)?'CV':'BG:'+img;})()")
            check("详情头卡封面（%s %s）：%s" % (name, tag, cv),
                  cv == "CV" or (tag == "无封面" and cv == "CV"))
            shot(ws, os.path.join(SHOT_DIR, "v212_详情头封面_%s.png" % tag))

        err = ev(ws, "window.__errCount||0")
        check("无页面 JS 报错", not err, err)
    finally:
        for p in (edge, proc):
            if p is not None:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                               capture_output=True)
        time.sleep(0.8)
        import shutil
        shutil.rmtree(PROFILE, ignore_errors=True)

    print()
    ok = sum(1 for _, s, _ in R if s)
    for name, s, extra in R:
        print("  [%s] %s%s" % ("OK" if s else "!!", name,
                               ("  " + str(extra)) if extra else ""))
    print("== %d/%d 通过 ==" % (ok, len(R)))
    sys.exit(0 if ok == len(R) else 1)


if __name__ == "__main__":
    main()

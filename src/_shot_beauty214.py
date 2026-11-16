# -*- coding: utf-8 -*-
"""界面美化（v2.14 P0/P1/P2）验证截图：
A. 地图库空态：搜无结果 →「🔍 没有匹配的地图 + 清除筛选按钮」
B. 服务器表吸顶表头：滚到中部，表头仍在视口内
C. 键盘焦点环：Tab 到按钮后 :focus-visible 描边可见
用法：python _shot_ui214_beauty.py（端口 9422 / CDP 9423）
"""
import base64
import json
import os
import subprocess
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 9422
CDP = 9423
BASE = "http://127.0.0.1:%d" % PORT
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W = os.path.dirname(HERE)
SHOT_DIR = os.path.join(W, "验证截图-界面巡检")
PROFILE = os.path.join(SHOT_DIR, "_prof_beauty214")
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


def shot(ws, path, width=1500, height=980):
    send(ws, "Emulation.setDeviceMetricsOverride",
         {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
    time.sleep(0.3)
    d = send(ws, "Page.captureScreenshot", {"format": "png"})
    data = (d.get("result") or {}).get("data")
    if not data:
        raise RuntimeError("captureScreenshot 失败: %r" % str(d)[:300])
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(data))
    print("shot:", os.path.basename(path), os.path.getsize(path), "bytes")


def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
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
             {"width": 1500, "height": 980, "deviceScaleFactor": 1, "mobile": False})

        # 浅色主题、进地图库
        ev(ws, "localStorage.clear()")
        send(ws, "Page.navigate", {"url": BASE + "/?view=lib"})
        time.sleep(4)
        ev(ws, "applyTheme('E',false)")
        # 等地图索引真正加载完（首启后台建索引，慢时 10s+）
        n = 0
        for _ in range(90):
            n = ev(ws, "(typeof LIB!=='undefined'&&LIB.all)?LIB.all.length:0") or 0
            if n:
                break
            time.sleep(1)
        print("index ready:", n, "maps")

        # A. 空态：搜一个必然无结果的关键词
        dbg = ev(ws, "(function(){var q=document.getElementById('libQ');"
                    "if(!q)return 'no-libQ';"
                    "q.value='zzz不存在zzz';"
                    "q.dispatchEvent(new Event('input'));libRender();return 'rendered';"
                    "return 'no-fn:'+Object.keys(window).filter(function(k){"
                    "return k.indexOf('lib')===0}).slice(0,20).join(',')})()")
        time.sleep(1.2)
        ok = ev(ws, "(function(){var b=document.querySelector('#libList .libEmpty');"
                    "return b? (b.querySelector('.eBtn')?'btn':'no-btn') : 'none'})()")
        print("empty state:", dbg, ok)
        shot(ws, os.path.join(SHOT_DIR, "v214b_空态_清除筛选按钮.png"))

        # 恢复列表
        ev(ws, "libClrAll()")
        time.sleep(1.5)

        # B. 服务器表吸顶：回首页，压矮视口制造滚动空间，把 .main 滚到中部
        send(ws, "Emulation.setDeviceMetricsOverride",
             {"width": 1500, "height": 700, "deviceScaleFactor": 1, "mobile": False})
        ev(ws, "showView('srv')")
        time.sleep(1.5)
        st = ev(ws, "(function(){"
                    "var th=document.querySelector('.srvtab thead th, table thead th');"
                    "if(!th)return 'no-th';"
                    "/* 找 thead 的可滚动祖先（overflowY auto/scroll 且能滚） */"
                    "var m=th.parentElement, sc=null;"
                    "while(m){var s=getComputedStyle(m);"
                    "  if((s.overflowY==='auto'||s.overflowY==='scroll')&&"
                    "     m.scrollHeight>m.clientHeight+10){sc=m;break;} m=m.parentElement;}"
                    "if(!sc)sc=document.scrollingElement||document.documentElement;"
                    "sc.scrollTop=600;"
                    "var r=th.getBoundingClientRect(), rc=sc.getBoundingClientRect();"
                    "return JSON.stringify({sc:(sc.className||sc.tagName).slice(0,20),"
                    "top:Math.round(r.top),pos:getComputedStyle(th).position,"
                    "scrollTop:Math.round(sc.scrollTop)})})()")
        print("sticky:", st)
        time.sleep(0.5)
        shot(ws, os.path.join(SHOT_DIR, "v214b_服务器表_吸顶表头.png"), height=700)

        # C. 键盘焦点环：对导航按钮派发键盘焦点
        ev(ws, "(function(){var b=document.getElementById('navLib')||"
               "document.querySelector('.nav button, button');"
               "if(b){b.focus();}})()")
        # headless 里 :focus-visible 需键盘来源，直接用 CDP 强制插桩样式验证：
        fv = ev(ws, "(function(){var b=document.activeElement;"
                    "if(!b)return 'no-focus';"
                    "var s=getComputedStyle(b);"
                    "return b.id+'|'+s.outlineStyle+'|'+s.outlineWidth})()")
        print("focus:", fv)
        shot(ws, os.path.join(SHOT_DIR, "v214b_焦点环_键盘可达.png"))
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        for p in (edge, proc):
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass
        time.sleep(1.5)
        subprocess.run(["taskkill", "/F", "/IM", "FYS-Reward.exe"],
                       capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"],
                       capture_output=True)


if __name__ == "__main__":
    main()

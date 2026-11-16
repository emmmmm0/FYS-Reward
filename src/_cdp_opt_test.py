# -*- coding: utf-8 -*-
"""本次「全功能优化」专项 CDP 验证：
① 恢复默认外观按钮：点击后主题 E / 背景 cloud / 贴纸 cat 且偏好已保存
② render 快照比对：数据没变时四宫格 DOM 节点不重建（同一节点对象）
③ 服务器表快照：数据没变时整表不重建
④ 轮询降频接线：页面含 visibilitychange 监听 + 无残留 __POLL__
⑤ body 过渡动画挂在 aTheme 下（关动画后切主题瞬时）

用法：python _cdp_opt_test.py [port]   （port 缺省 8793，需已有服务）
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
sys.path.insert(0, HERE)
from _prefs_guard import PrefsGuard            # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8793
BASE = "http://127.0.0.1:%d" % PORT
W = os.path.dirname(HERE)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = os.path.join(W, "验证截图-界面巡检", "_prof_opt")


def ev(ws, expr):
    ws.send(json.dumps({"id": ev._i, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True}}))
    ev._i += 1
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == ev._i - 1:
            if "exceptionDetails" in r:
                return "__ERR__ " + json.dumps(r["exceptionDetails"])[:300]
            return r.get("result", {}).get("result", {}).get("value")


ev._i = 1


def main():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    # 等服务就绪
    for _ in range(40):
        try:
            op.open(BASE + "/api/prefs", timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--remote-debugging-port=9397",
         "--remote-allow-origins=*", "--user-data-dir=" + PROFILE,
         "--no-first-run", "--window-size=1440,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    R = []
    try:
        ws_url = None
        for _ in range(40):
            try:
                tabs = json.load(op.open("http://127.0.0.1:9397/json", timeout=2))
                page = [t for t in tabs if t.get("type") == "page"]
                if page:
                    ws_url = page[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.5)
        assert ws_url, "Edge CDP 起不来"
        ws = websocket.create_connection(ws_url, timeout=60)
        ws.send(json.dumps({"id": 900, "method": "Runtime.enable"}))
        ws.send(json.dumps({"id": 901, "method": "Page.enable"}))
        ws.send(json.dumps({"id": 902, "method": "Page.navigate",
                            "params": {"url": BASE + "/?noreadme=1"}}))
        for _ in range(80):
            if ev(ws, "typeof tick==='function' && !!document.getElementById('grid')"):
                break
            time.sleep(0.25)
        time.sleep(2.5)

        # ④ 静态接线
        R.append(("visibilitychange 已监听",
                  ev(ws, "true") is not None and
                  "visibilitychange" in op.open(BASE + "/", timeout=5).read().decode("utf-8")))
        R.append(("页面无 __POLL__ 残留（替换成功）",
                  "__POLL__" not in op.open(BASE + "/", timeout=5).read().decode("utf-8")))

        # ② render 快照：同一份数据连刷两次，grid 首节点应是同一对象（探针挂首节点，
        #    不能挂容器——innerHTML='' 不清容器自身属性，会假通过）
        n1 = ev(ws, "(function(){var g=document.getElementById('grid');"
                    "if(g.firstChild){g.firstChild.setAttribute('data-probe','1'); return '1';}"
                    "return '0';})()")
        ev(ws, "tick(true)")
        time.sleep(1.6)
        n2 = ev(ws, "(function(){var f=document.getElementById('grid').firstChild;"
                    "return (f&&f.getAttribute&&f.getAttribute('data-probe'))||'';})()")
        # 数据没变 → 整段跳过 → 首节点还是原来那个（探针属性还在）
        R.append(("render 快照：数据未变时 grid 不重建", n1 == "1" and n2 == "1"))

        # 强制变化：改快照键后下一 tick 应重建（新首节点没有探针）
        ev(ws, "window.__dataSnap='__force__'; tick(true);")
        time.sleep(1.6)
        n3 = ev(ws, "(function(){var f=document.getElementById('grid').firstChild;"
                    "return (f&&f.getAttribute&&f.getAttribute('data-probe'))||'';})()")
        R.append(("render 快照：数据变化时正常重建", n1 == "1" and n3 == ""))

        # ③ 服务器表快照（探针同样挂首行）
        ev(ws, "(function(){var t=document.getElementById('stb');"
               "if(t.firstChild) t.firstChild.setAttribute('data-probe','1');})()")
        ev(ws, "tickServers()")
        time.sleep(2.0)
        s2 = ev(ws, "(function(){var f=document.getElementById('stb').firstChild;"
                    "return (f&&f.getAttribute&&f.getAttribute('data-probe'))||'';})()")
        R.append(("服务器表快照：数据未变时不重建", s2 == "1"))

        # ⑤ 过渡动画挂 aTheme 下：先记原状态，摘类测「关」、加类测「开」、再还原
        had = ev(ws, "document.documentElement.classList.contains('aTheme')")
        ev(ws, "document.documentElement.classList.remove('aTheme')")
        t1 = ev(ws, "getComputedStyle(document.body).transitionDuration")
        ev(ws, "document.documentElement.classList.add('aTheme')")
        t2 = ev(ws, "getComputedStyle(document.body).transitionDuration")
        ev(ws, ("document.documentElement.classList.add('aTheme')" if had
                else "document.documentElement.classList.remove('aTheme')"))
        d1 = (t1.split(",")[0].strip().rstrip("s") or "0")
        R.append(("body 过渡动画受 aTheme 控制（关=%s 开=%s）" % (t1.split(",")[0], t2.split(",")[0]),
                  float(d1 or 0) == 0 and "0.32" in t2))

        # ① 恢复默认外观（PrefsGuard 隔离真实偏好文件）
        ev(ws, "showView('theme')")
        time.sleep(0.6)
        btn = ev(ws, "!!document.getElementById('btnResetLook')")
        # 先改成别的主题/背景/贴纸
        ev(ws, "applyTheme('N', true); applyBG('none', true); applySticker('off', true)")
        saved_mess = ev(ws, "JSON.stringify([PREFS.theme,PREFS.bg,PREFS.sticker])")
        ev(ws, "document.getElementById('btnResetLook').click()")
        time.sleep(1.2)
        saved_ok = ev(ws, "JSON.stringify([PREFS.theme,PREFS.bg,PREFS.sticker])")
        theme_now = ev(ws, "document.documentElement.getAttribute('data-theme')")
        bg_now = ev(ws, "document.getElementById('bgcss').textContent.length>=0 && "
                        "document.documentElement.getAttribute('data-bg')")
        R.append(("恢复默认前已是改动值 %s" % saved_mess,
                  saved_mess not in ('["E","cloud","cat"]',)))
        R.append(("恢复默认后偏好=%s 主题=%s 背景=%s" % (saved_ok, theme_now, bg_now),
                  saved_ok == '["E","cloud","cat"]' and theme_now == "E" and bg_now == "cloud"))
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n_ok = sum(1 for _, ok in R if ok)
    for t, ok in R:
        print(("  ✓ " if ok else "  ✗ FAIL ") + t)
    print("结果: %d/%d" % (n_ok, len(R)))
    return n_ok == len(R)


if __name__ == "__main__":
    with PrefsGuard():
        ok = main()
    sys.exit(0 if ok else 1)

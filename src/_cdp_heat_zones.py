# -*- coding: utf-8 -*-
"""热区专项：确认 8 块 .rz 缩放热区只贴窗口边缘，不吃界面交互。

跑法：python _cdp_heat_zones.py 8807
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8807
BASE = "http://127.0.0.1:%d/" % PORT
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DOM = os.path.join(tempfile.gettempdir(), "edge_hz_%d" % PORT)

import websocket  # noqa: E402

ok = bad = 0


def check(name, cond, extra=None):
    global ok, bad
    if cond:
        ok += 1
        print("  [PASS] %s" % name)
    else:
        bad += 1
        print("  [FAIL] %s  %s" % (name, extra if extra is not None else ""))


def main():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    op.open(BASE + "api/status", timeout=6).read()
    proc = subprocess.Popen([
        EDGE, "--headless=new", "--disable-gpu", "--remote-debugging-port=9611",
        "--remote-allow-origins=*",
        "--user-data-dir=" + DOM, "--window-size=1280,800",
        "--no-first-run", "--no-default-browser-check", BASE,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        for _ in range(40):
            time.sleep(0.5)
            try:
                tabs = json.loads(op.open("http://127.0.0.1:9611/json", timeout=3).read().decode())
                t = [x for x in tabs if x.get("type") == "page" and x.get("webSocketDebuggerUrl")]
                if t:
                    ws = websocket.create_connection(t[0]["webSocketDebuggerUrl"],
                                                     timeout=20, http_proxy_host=None)
                    break
            except Exception:
                pass
        if ws is None:
            print("[!] 连不上 CDP")
            return
        mid = [0]

        def send(m, p=None):
            mid[0] += 1
            ws.send(json.dumps({"id": mid[0], "method": m, "params": p or {}}))
            while True:
                d = json.loads(ws.recv())
                if d.get("id") == mid[0]:
                    return d.get("result", {})

        def ev(js):
            r = send("Runtime.evaluate", {"expression": js, "returnByValue": True,
                                          "awaitPromise": True})
            return r.get("result", {}).get("value")

        send("Page.enable")
        send("Runtime.enable")
        for _ in range(40):
            time.sleep(0.5)
            if ev("!!document.querySelector('#titlebar') && document.readyState==='complete'"):
                break
        time.sleep(1.5)

        print("\n[1] 热区结构与几何")
        n = ev("document.querySelectorAll('.rz').length")
        check("8 块热区都在（实际 %s）" % n, n == 8)
        geo = ev("""(function(){var o={};document.querySelectorAll('.rz').forEach(function(z){
          var r=z.getBoundingClientRect();o[z.getAttribute('data-edge')]=
          [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)]});
          return JSON.stringify(o)})()""")
        g = json.loads(geo or "{}")
        print("     几何:", g)
        # headless 视口 ≠ --window-size（实测 1256×708），必须读实际值，别硬编码
        W = int(ev("window.innerWidth"))
        H = int(ev("window.innerHeight"))
        print("     视口 %dx%d" % (W, H))
        check("右边热区贴右边缘且宽 4px", g.get("r", [0])[2] == 4
              and abs(g["r"][0] + 4 - W) <= 1, g.get("r"))
        check("下边热区贴下边缘且高 4px", g.get("b", [0, 0, 0, 0])[3] == 4
              and abs(g["b"][1] + 4 - H) <= 1, g.get("b"))
        check("左上角热区 14×14 贴角", g.get("tl", [])[:2] == [0, 0] and g["tl"][2:] == [14, 14],
              g.get("tl"))
        check("右下角热区 14×14 贴角", g.get("br", [])[2:] == [14, 14], g.get("br"))
        check("边热区避开角（上边 left≥14 且左边 top≥14）",
              g.get("t", [0])[0] >= 14 and g.get("l", [0, 0])[1] >= 14, (g.get("t"), g.get("l")))

        print("\n[2] 光标形状")
        cur = ev("""(function(){var o={};document.querySelectorAll('.rz').forEach(function(z){
          o[z.getAttribute('data-edge')]=getComputedStyle(z).cursor});return JSON.stringify(o)})()""")
        c = json.loads(cur or "{}")
        check("上/下边 ns-resize", c.get("t") == "ns-resize" and c.get("b") == "ns-resize", c)
        check("左/右边 ew-resize", c.get("l") == "ew-resize" and c.get("r") == "ew-resize", c)
        check("四角斜向光标", c.get("tl") == "nwse-resize" and c.get("tr") == "nesw-resize"
              and c.get("br") == "nwse-resize" and c.get("bl") == "nesw-resize", c)

        print("\n[3] 不吃界面交互（边缘之外的元素应正常命中）")
        cases = [
            ("侧栏菜单第一项", "document.querySelector('.nav')"),
            ("顶栏最小化按钮", "document.getElementById('wMin')"),
            ("顶栏关闭按钮", "document.getElementById('wClose')"),
            ("主区内卡片", "document.querySelector('.main .card, .main table, .main')"),
        ]
        for label, sel in cases:
            r = ev("""(function(){var e=%s;if(!e)return null;var b=e.getBoundingClientRect();
              var x=b.left+Math.min(30,b.width/2), y=b.top+Math.min(12,b.height/2);
              var hit=document.elementFromPoint(x,y);
              return JSON.stringify({hit:hit?(hit.className||hit.tagName):null,
                                     isRz:!!(hit&&hit.closest&&hit.closest('.rz'))})})()""" % sel)
            d = json.loads(r) if r else {}
            check("点在 %s 上不被热区抢走（命中 %s）" % (label, d.get("hit")),
                  d and not d.get("isRz"), d)

        print("\n[4] 边缘位置确实归热区（保证能拖）")
        r = ev("""(function(){var h=document.elementFromPoint(window.innerWidth-1,
          Math.round(window.innerHeight/2));return h?(h.className||h.tagName):null})()""")
        check("右边缘 4px 内命中热区（%s）" % r, r and "rz" in str(r), r)
        r = ev("""(function(){var h=document.elementFromPoint(Math.round(window.innerWidth/2),
          window.innerHeight-1);return h?(h.className||h.tagName):null})()""")
        check("下边缘 4px 内命中热区（%s）" % r, r and "rz" in str(r), r)

        print("\n[5] 最大化时热区自动隐藏")
        ev("document.documentElement.classList.add('aMax')")
        time.sleep(0.4)
        r = ev("(function(){return getComputedStyle(document.querySelector('.rz-e')).display})()")
        check("aMax 时热区 display=none（%s）" % r, r == "none", r)
        ev("document.documentElement.classList.remove('aMax')")
        time.sleep(0.3)
        r = ev("(function(){return getComputedStyle(document.querySelector('.rz-e')).display})()")
        check("取消 aMax 后恢复（%s）" % r, r != "none", r)

        print("\n[6] 按热区不报错")
        errs = []
        send("Runtime.evaluate", {"expression":
                                  "window.__e=[];window.addEventListener('error',function(e){window.__e.push(String(e.message))});"})
        # 用非法 edge 触发（后端立即返回，不会进系统缩放循环）
        r = ev("""(function(){var z=document.querySelector('.rz-e');
          var old=z.getAttribute('data-edge');z.setAttribute('data-edge','zz');
          z.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0}));
          z.setAttribute('data-edge',old);
          return 'sent'})()""")
        check("热区 mousedown 派发成功（%s）" % r, r == "sent", r)
        time.sleep(1.2)
        errs = json.loads(ev("JSON.stringify(window.__e||[])") or "[]")
        check("派发 mousedown 无 JS 报错", not errs, errs)
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
        print("\n==== 热区专项 %d 通过 / %d 失败 ====" % (ok, bad))
        return 1 if bad else 0


sys.exit(main() or 0)

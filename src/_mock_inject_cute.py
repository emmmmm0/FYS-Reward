# -*- coding: utf-8 -*-
"""可爱风格样板：在真实软件页面上注入「可爱风」样式层后整窗截图（1330x720，与软件窗口一致）。

可爱风元素：粉彩渐变底 + 虚线贴纸描边卡片 + 云朵圆角行 + 彩色圆徽章 + 漂浮 emoji 小贴纸。
用法：_mock_inject_cute.py <port>
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
OUT = os.path.join(ROOT, "验证截图-界面巡检")
CDP = 9381

# ── 可爱风全局样式 ──────────────────────────────────────────────
CSS_CUTE = """
body{
 background:
  radial-gradient(620px 300px at 6% -6%, #ffe1ee 0%, rgba(255,225,238,0) 62%),
  radial-gradient(720px 340px at 102% -4%, #e6e0ff 0%, rgba(230,224,255,0) 58%),
  radial-gradient(560px 300px at 50% 108%, #ffeef4 0%, rgba(255,238,244,0) 60%),
  linear-gradient(168deg, #fff8fb 0%, #fdf1f7 52%, #f4f1ff 100%) !important;}
.card{border-radius:24px !important;border:2px dashed #ffc9de !important;
 box-shadow:0 8px 22px rgba(240,120,170,.14) !important;background:rgba(255,255,255,.88) !important;}
button,.btn{border-radius:999px !important;}
.btn:hover{transform:translateY(-2px) rotate(-1deg);}
/* 服务器页：表格行云朵卡片化 */
.srvtab{border-collapse:separate !important;border-spacing:0 8px !important;}
.srvtab td{background:rgba(255,255,255,.92) !important;
 border-top:2px dashed #ffd3e3 !important;border-bottom:2px dashed #ffd3e3 !important;}
.srvtab td:first-child{border-left:2px dashed #ffd3e3 !important;border-radius:18px 0 0 18px !important;}
.srvtab td:last-child{border-right:2px dashed #ffd3e3 !important;border-radius:0 18px 18px 0 !important;}
.srvtab tbody tr:hover td{background:#fff0f7 !important;}
/* 主题页：色卡冰淇淋化 */
#themes .tcard{border-radius:26px !important;border:2px dashed #ffc9de !important;
 position:relative;overflow:hidden;transition:transform .18s;}
#themes .tcard::before{content:'';position:absolute;top:0;left:0;right:0;height:12px;
 background:linear-gradient(90deg,#ffd1e8,#d9ccff,#c2ecff,#c9f5d8);}
#themes .tcard:hover{transform:translateY(-4px) rotate(-1.5deg);}
/* 地图库：行圆角胶囊化 */
#libList .libRow{border-radius:999px !important;margin:4px 2px !important;
 border:2px dashed #ffd3e3 !important;background:rgba(255,255,255,.9) !important;}
#libList .libRow:hover{transform:translateY(-2px) rotate(-.6deg);}
#libDetail .libHead{border-radius:22px !important;}
"""

# ── 漂浮小贴纸 ─────────────────────────────────────────────────
JS_STICKERS = r"""
(function(){
 if(document.getElementById('cuteStickers')) return;
 var its=[['☁️','3%','7%'],['🌸','95%','12%'],['🍓','4%','84%'],['✨','94%','80%'],['🍬','50%','3%']];
 var html='';
 for(var i=0;i<its.length;i++){
  html+='<span style="position:fixed;left:'+its[i][1]+';top:'+its[i][2]
   +';font-size:26px;opacity:.85;pointer-events:none;animation:cuteFloat '+(3+i*0.6).toFixed(1)
   +'s ease-in-out infinite alternate">'+its[i][0]+'</span>';
 }
 var d=document.createElement('div'); d.id='cuteStickers';
 d.style.cssText='position:fixed;inset:0;pointer-events:none;z-index:9999';
 d.innerHTML=html; document.body.appendChild(d);
 var s=document.createElement('style');
 s.textContent='@keyframes cuteFloat{from{transform:translateY(0) rotate(-6deg)}to{transform:translateY(-10px) rotate(6deg)}}';
 document.head.appendChild(s);
})()
"""

# ── 地图库列表：马卡龙色圆徽章 ────────────────────────────────
JS_LIBBADGE = r"""
(function(){
 var hues=[338,286,205,160,42,14,318];
 var rows=document.querySelectorAll('#libList .libRow');
 for(var i=0;i<rows.length;i++){
  var r=rows[i];
  if(r.querySelector('.cbadge')) continue;
  var b=document.createElement('span'); b.className='cbadge';
  var h=hues[i%hues.length];
  b.style.cssText='display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;'
   +'border-radius:50%;margin-right:8px;font-weight:800;font-size:13px;flex:0 0 30px;'
   +'background:linear-gradient(135deg,hsl('+h+',90%,90%),hsl('+((h+45)%360)+',92%,82%));'
   +'color:hsl('+h+',60%,36%);box-shadow:0 3px 8px rgba(240,120,170,.25);border:2px solid #fff;';
  b.textContent=(r.textContent.trim().charAt(0)||'Z').toUpperCase();
  r.insertBefore(b,r.firstChild);
 }
})()
"""

# ── 地图库详情：贴纸横幅 ──────────────────────────────────────
JS_LIBHEAD = r"""
(function(){
 var h=document.querySelector('#libDetail .libHead');
 if(!h || h.querySelector('.csticker')) return;
 var s=document.createElement('span'); s.className='csticker';
 s.textContent='🐾';
 s.style.cssText='position:absolute;right:14px;top:-12px;font-size:34px;'
  +'transform:rotate(12deg);filter:drop-shadow(0 3px 6px rgba(240,120,170,.35));';
 h.style.position='relative';
 h.appendChild(s);
})()
"""


def launch():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    prof = os.path.join(OUT, "_prof_cdp9")
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
         "--remote-allow-origins=*", "--user-data-dir=" + prof,
         "--no-first-run", "--window-size=1330,720", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open("http://127.0.0.1:%d/json" % CDP, timeout=2))
            pg = [t for t in tabs if t.get("type") == "page"]
            if pg:
                ws_url = pg[0]["webSocketDebuggerUrl"]
                break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(ws_url, timeout=180)
    _id = [0]

    def send(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({"id": _id[0], "method": m, "params": p or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == _id[0]:
                return msg.get("result", {})

    def ev(e):
        return send("Runtime.evaluate", {"expression": e, "returnByValue": True}).get("result", {}).get("value")

    return proc, send, ev


def cute_inject(ev, extra_js=None):
    ev("var s=document.createElement('style');s.id='cuteCss';s.textContent=%s;document.head.appendChild(s)"
       % json.dumps(CSS_CUTE))
    ev(JS_STICKERS)
    if extra_js:
        ev(extra_js)


def snap(send, path):
    d = send("Page.captureScreenshot", {"format": "png"})
    with open(path, "wb") as f:
        f.write(base64.b64decode(d["data"]))
    print("OK", os.path.basename(path), os.path.getsize(path) // 1024, "KB")


def main():
    port = int(sys.argv[1])
    proc, send, ev = launch()
    send("Page.enable")
    try:
        # ── 可爱A：服务器页 ──
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=srv" % port})
        for _ in range(40):
            if ev("typeof LIB!=='undefined'"):
                break
            time.sleep(1)
        time.sleep(2.5)
        ev("typeof applyTheme==='function'&&applyTheme('E')")
        cute_inject(ev)
        time.sleep(0.6)
        snap(send, os.path.join(OUT, "可爱A-服务器整页.png"))

        # ── 可爱B：地图库 ──
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=lib" % port})
        for _ in range(40):
            if ev("typeof LIB!=='undefined'") and ev("document.querySelectorAll('#libList .libRow').length>10"):
                break
            time.sleep(1)
        time.sleep(2.5)
        ev("typeof applyTheme==='function'&&applyTheme('E')")
        cute_inject(ev, JS_LIBBADGE + " " + JS_LIBHEAD)
        time.sleep(0.8)
        snap(send, os.path.join(OUT, "可爱B-地图库整页.png"))

        # ── 可爱C：设置页 ──
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=set" % port})
        for _ in range(40):
            if ev("typeof LIB!=='undefined'") and ev("!!document.getElementById('clgCard')"):
                break
            time.sleep(1)
        time.sleep(2)
        ev("typeof applyTheme==='function'&&applyTheme('E')")
        cute_inject(ev)
        time.sleep(0.6)
        snap(send, os.path.join(OUT, "可爱C-设置整页.png"))

        # ── 可爱D：主题页 ──
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=theme" % port})
        for _ in range(40):
            if ev("typeof LIB!=='undefined'") and ev("document.querySelectorAll('#themes .tcard').length>=5"):
                break
            time.sleep(1)
        time.sleep(2)
        ev("typeof applyTheme==='function'&&applyTheme('E')")
        cute_inject(ev)
        time.sleep(0.6)
        snap(send, os.path.join(OUT, "可爱D-主题整页.png"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

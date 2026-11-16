# -*- coding: utf-8 -*-
"""可爱风格样板 · 第二批：屏幕覆盖 / 实体预览 + 夜幕深色适配验证。

可爱风（沿用第一批配方）：粉彩渐变底 + 虚线贴纸描边卡片 + 云朵圆角行 + 漂浮 emoji 贴纸。
深色版改走主题变量（--bg/--panel/--softline/--accent）+ color-mix 自适配，浅深通用。
用法：_mock_inject_cute2.py <port>
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
CDP = 9385

# ── 可爱风 · 浅色（第一批同款） ────────────────────────────────
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
"""

# ── 可爱风 · 主题自适应（浅深通用，深色靠 color-mix 提亮） ────
CSS_CUTE_ADAPT = """
body{
 background:
  radial-gradient(620px 300px at 6% -6%, color-mix(in srgb, var(--accent) 24%, transparent) 0%, transparent 62%),
  radial-gradient(720px 340px at 102% -4%, color-mix(in srgb, #a78bfa 26%, transparent) 0%, transparent 58%),
  radial-gradient(560px 300px at 50% 108%, color-mix(in srgb, #66d9c0 18%, transparent) 0%, transparent 60%),
  var(--bg) !important;}
.card{border-radius:24px !important;border:2px dashed var(--softline) !important;
 background:color-mix(in srgb, var(--panel) 92%, transparent) !important;
 box-shadow:0 8px 22px rgba(0,0,0,.10) !important;}
button,.btn{border-radius:999px !important;}
.srvtab{border-collapse:separate !important;border-spacing:0 8px !important;}
.srvtab td{background:color-mix(in srgb, var(--panel) 94%, transparent) !important;
 border-top:2px dashed var(--softline) !important;border-bottom:2px dashed var(--softline) !important;}
.srvtab td:first-child{border-left:2px dashed var(--softline) !important;border-radius:18px 0 0 18px !important;}
.srvtab td:last-child{border-right:2px dashed var(--softline) !important;border-radius:0 18px 18px 0 !important;}
.srvtab tbody tr:hover td{background:color-mix(in srgb, var(--accent) 12%, var(--panel)) !important;}
#libList .libRow{border-radius:999px !important;margin:4px 2px !important;
 border:2px dashed var(--softline) !important;
 background:color-mix(in srgb, var(--panel) 92%, transparent) !important;}
#libList .libRow:hover{transform:translateY(-2px) rotate(-.6deg);}
#libDetail .libHead{border-radius:22px !important;}
"""

# ── 覆盖页：iOS 式圆角开关 + 组头小图标 ───────────────────────
CSS_OV = """
#view-ov label{display:flex;align-items:center;gap:10px;padding:8px 12px;
 border-radius:16px;border:2px dashed transparent;cursor:pointer;transition:background .15s;}
#view-ov label:hover{background:color-mix(in srgb, var(--soft) 80%, transparent);
 border-color:var(--softline);}
#view-ov input[type=checkbox]{appearance:none;-webkit-appearance:none;position:relative;
 width:40px;height:22px;flex:0 0 40px;border-radius:999px;background:var(--line);
 transition:background .18s;cursor:pointer;margin:0;order:-1;}
#view-ov input[type=checkbox]::after{content:'';position:absolute;top:2px;left:2px;
 width:18px;height:18px;border-radius:50%;background:#fff;
 box-shadow:0 2px 5px rgba(0,0,0,.20);transition:left .18s;}
#view-ov input[type=checkbox]:checked{background:var(--good);}
#view-ov input[type=checkbox]:checked::after{left:20px;}
"""

JS_OV_ICONS = r"""
(function(){
 var ics=['🎀','✨','🍬','🌸','🧸','🍓'];
 var hs=document.querySelectorAll('#view-ov h2');
 for(var i=0;i<hs.length;i++){
  if(hs[i].getAttribute('data-ci')) continue;
  hs[i].setAttribute('data-ci','1');
  hs[i].insertBefore(document.createTextNode(ics[i%ics.length]+' '), hs[i].firstChild);
 }
})()
"""

# ── 预览页：父层工具条胶囊化（3D 画布不动） ───────────────────
CSS_PRE = """
.preBar2{border-radius:20px !important;border:2px dashed #ffc9de !important;
 background:rgba(255,255,255,.9) !important;padding:8px 12px !important;
 box-shadow:0 8px 22px rgba(240,120,170,.14) !important;}
#preCur2{border-radius:999px !important;background:var(--soft) !important;
 color:var(--accent) !important;padding:4px 12px !important;font-weight:800 !important;}
.preBar2 .btn{border-radius:999px !important;}
#preFrame{border-radius:20px !important;border:2px dashed #ffc9de !important;overflow:hidden;}
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

# ── 地图库：马卡龙圆徽章 ──────────────────────────────────────
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
   +'background:linear-gradient(135deg,hsl('+h+',90%,88%),hsl('+((h+45)%360)+',92%,78%));'
   +'color:hsl('+h+',60%,32%);box-shadow:0 3px 8px rgba(0,0,0,.22);border:2px solid #fff;';
  b.textContent=(r.textContent.trim().charAt(0)||'Z').toUpperCase();
  r.insertBefore(b,r.firstChild);
 }
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


def add_css(ev, css, sid="cuteCss"):
    ev("(function(){var s=document.createElement('style');s.id='%s';s.textContent=%s;document.head.appendChild(s)})()"
       % (sid, json.dumps(css)))


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
        # ── 可爱E：屏幕覆盖页（浅色） ──
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=ov" % port})
        for _ in range(40):
            if ev("typeof LIB!=='undefined'") and ev("!!document.querySelector('#view-ov input[type=checkbox]')"):
                break
            time.sleep(1)
        time.sleep(2.5)
        ev("typeof applyTheme==='function'&&applyTheme('E')")
        add_css(ev, CSS_CUTE)
        add_css(ev, CSS_OV, "cuteCssOv")
        ev(JS_STICKERS)
        ev(JS_OV_ICONS)
        time.sleep(0.8)
        snap(send, os.path.join(OUT, "可爱E-屏幕覆盖整页.png"))

        # ── 可爱F：实体预览页（浅色，父层壳） ──
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=pre&map=ze_pizza_cookie" % port})
        for _ in range(60):
            if ev("!!document.getElementById('preFrame')") and ev("window.frames.length>0"):
                break
            time.sleep(1)
        time.sleep(16)                      # 等 3D 地形加载完再截
        ev("typeof applyTheme==='function'&&applyTheme('E')")
        add_css(ev, CSS_CUTE)
        add_css(ev, CSS_PRE, "cuteCssPre")
        ev(JS_STICKERS)
        time.sleep(0.8)
        snap(send, os.path.join(OUT, "可爱F-实体预览整页.png"))

        # ── 可爱G：服务器页 · 夜幕可爱（自适应版） ──
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=srv" % port})
        for _ in range(40):
            if ev("typeof LIB!=='undefined'"):
                break
            time.sleep(1)
        time.sleep(2.5)
        ev("typeof applyTheme==='function'&&applyTheme('N')")
        time.sleep(0.6)
        add_css(ev, CSS_CUTE_ADAPT)
        ev(JS_STICKERS)
        time.sleep(0.8)
        snap(send, os.path.join(OUT, "可爱G-服务器夜幕可爱.png"))

        # ── 可爱H：地图库 · 夜幕可爱（自适应版） ──
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=lib" % port})
        for _ in range(40):
            if ev("typeof LIB!=='undefined'") and ev("document.querySelectorAll('#libList .libRow').length>10"):
                break
            time.sleep(1)
        time.sleep(2.5)
        ev("typeof applyTheme==='function'&&applyTheme('N')")
        time.sleep(0.6)
        add_css(ev, CSS_CUTE_ADAPT)
        ev(JS_STICKERS)
        ev(JS_LIBBADGE)
        time.sleep(0.8)
        snap(send, os.path.join(OUT, "可爱H-地图库夜幕可爱.png"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

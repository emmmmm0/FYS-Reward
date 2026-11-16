# -*- coding: utf-8 -*-
"""可爱风样板 · 新一组「棉花糖泡芙」（与前一套粉虚线贴纸风完全区分）。

配方差异：
  · 无虚线、无粉色贴纸 → 奶油白厚描边(3px #fff) + 外圈柔粉光环(0 0 0 3px)
  · 行/列表用**四色糖果底轮换**（薄荷/粉/奶黄/浅蓝），不是统一粉
  · 按钮换**渐变胶囊**（薄荷→粉）
  · 地图库徽章改**圆角方糖块**（10px 圆角薄荷/粉/黄/蓝/紫配色）
  · 装饰换 **CSS 手绘小云朵 + ✦ 星光闪烁**（不用大 emoji 贴纸）
  · 卡片 30px 超大圆角（泡芙感）；主题卡顶部加**木耳边**
用法：_mock_inject_cute3.py <port>
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
CDP = 9387

CSS_PUFF = """
/* ── 棉花糖泡芙 · 全局 ── */
body{
 background:
  radial-gradient(700px 320px at 4% -8%, #ddf7ed 0%, rgba(221,247,237,0) 60%),
  radial-gradient(760px 340px at 100% -6%, #ffe6f1 0%, rgba(255,230,241,0) 58%),
  radial-gradient(620px 300px at 50% 112%, #fff7e2 0%, rgba(255,247,226,0) 62%),
  linear-gradient(170deg,#fffefc 0%,#fffbfd 45%,#f8fffc 100%) !important;}
.card{border-radius:30px !important;
 border:3px solid #fff !important;background:#fff !important;
 box-shadow:0 12px 26px rgba(255,170,200,.16), 0 0 0 3px #ffe4ef !important;}
button,.btn{border-radius:999px !important;}
.btn{background:linear-gradient(135deg,#8fe3c6,#ffc3dc) !important;color:#fff !important;
 border:none !important;box-shadow:0 4px 10px rgba(255,170,200,.28) !important;}
#view-srv h2::before,#view-ov h2::before,#view-set h2::before{
 content:'';display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px;
 background:linear-gradient(135deg,#8fe3c6,#5ec9a8);vertical-align:middle;}
/* ── 服务器行：四色糖果轮换 ── */
.srvtab{border-collapse:separate !important;border-spacing:0 9px !important;}
.srvtab td{border:none !important;background:#fff !important;}
.srvtab tbody tr:nth-child(4n+1) td{background:#f3fdf8 !important;}
.srvtab tbody tr:nth-child(4n+2) td{background:#fff5f9 !important;}
.srvtab tbody tr:nth-child(4n+3) td{background:#fffdf2 !important;}
.srvtab tbody tr:nth-child(4n+4) td{background:#f4faff !important;}
.srvtab td:first-child{border-radius:20px 0 0 20px !important;}
.srvtab td:last-child{border-radius:0 20px 20px 0 !important;}
/* ── 地图库：软糖胶囊行 ── */
#libList .libRow{border-radius:22px !important;margin:5px 3px !important;border:none !important;}
#libList .libRow:nth-child(4n+1){background:#f3fdf8 !important;}
#libList .libRow:nth-child(4n+2){background:#fff5f9 !important;}
#libList .libRow:nth-child(4n+3){background:#fffdf2 !important;}
#libList .libRow:nth-child(4n+4){background:#f4faff !important;}
#libList .libRow:hover{transform:translateY(-2px);}
#libDetail .libHead{border-radius:26px !important;}
/* ── 主题卡：木耳边 + 泡芙圆角 ── */
#themes .tcard{border-radius:28px !important;position:relative;overflow:hidden;
 box-shadow:0 10px 22px rgba(255,170,200,.18) !important;border:3px solid #fff !important;}
#themes .tcard::before{content:'';position:absolute;top:0;left:0;right:0;height:12px;
 background:radial-gradient(circle at 6px 0, #ffd0e2 6px, rgba(255,208,226,0) 6.5px) repeat-x;
 background-size:12px 12px;}
#themes .tcard:hover{transform:translateY(-4px);}
/* ── 覆盖页：糖果胶囊开关 ── */
#view-ov label{padding:8px 12px;border-radius:16px;cursor:pointer;}
#view-ov label:hover{background:#fff5f9;}
#view-ov input[type=checkbox]{appearance:none;-webkit-appearance:none;position:relative;
 width:42px;height:24px;flex:0 0 42px;border-radius:999px;background:#ffe3ee;
 box-shadow:inset 0 2px 4px rgba(255,150,190,.30);transition:background .18s;cursor:pointer;margin:0;order:-1;}
#view-ov input[type=checkbox]::after{content:'';position:absolute;top:3px;left:3px;width:18px;height:18px;
 border-radius:50%;background:#fff;box-shadow:0 2px 5px rgba(0,0,0,.15);transition:left .18s;}
#view-ov input[type=checkbox]:checked{background:linear-gradient(135deg,#8fe3c6,#ffb8d6);}
#view-ov input[type=checkbox]:checked::after{left:21px;}
"""

# ── 装饰层：CSS 手绘云朵 + ✦ 星光 ──────────────────────────────
JS_DECO = r"""
(function(){
 if(document.getElementById('puffDeco')) return;
 var d=document.createElement('div'); d.id='puffDeco';
 d.style.cssText='position:fixed;inset:0;pointer-events:none;z-index:9999;overflow:hidden';
 var cloud='background:#fff;border-radius:999px;box-shadow:0 8px 18px rgba(255,180,205,.18);';
 d.innerHTML=
   '<div style="position:absolute;left:-40px;top:26px;width:120px;height:42px;'+cloud+'opacity:.7"></div>'
  +'<div style="position:absolute;left:40px;top:12px;width:70px;height:40px;'+cloud+'opacity:.7"></div>'
  +'<div style="position:absolute;right:-54px;top:78px;width:110px;height:40px;'+cloud+'opacity:.6"></div>'
  +'<div style="position:absolute;left:-56px;bottom:96px;width:120px;height:44px;'+cloud+'opacity:.6"></div>';
 document.body.appendChild(d);
 var s=document.createElement('style');
 s.textContent='.puffSp{position:fixed;font-size:20px;color:#ffb8d6;pointer-events:none;z-index:9999;'
  +'animation:puffTw 2.4s ease-in-out infinite alternate}'
  +'@keyframes puffTw{from{opacity:.35;transform:scale(.85) rotate(-8deg)}to{opacity:1;transform:scale(1.1) rotate(10deg)}}';
 document.head.appendChild(s);
 var pts=[['10%','15%','0s'],['87%','23%','.6s'],['14%','72%','1.2s'],['92%','66%','.3s']];
 for(var i=0;i<pts.length;i++){
   var e=document.createElement('span'); e.className='puffSp'; e.textContent='✦';
   e.style.left=pts[i][0]; e.style.top=pts[i][1]; e.style.animationDelay=pts[i][2];
   document.body.appendChild(e);
 }
})()
"""

# ── 地图库：圆角方糖块徽章（区别于上一版的圆形） ──────────────
JS_CHIPS = r"""
(function(){
 var cs=[['#e3f8ef','#2f9c78'],['#ffe8f2','#d9578f'],['#fff7e0','#c99320'],
         ['#e8f4ff','#3a86c9'],['#f1ebff','#7a5cd6']];
 var rows=document.querySelectorAll('#libList .libRow');
 for(var i=0;i<rows.length;i++){
  var r=rows[i]; if(r.querySelector('.cch')) continue;
  var c=cs[i%cs.length], b=document.createElement('span'); b.className='cch';
  b.style.cssText='display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;'
   +'border-radius:10px;margin-right:8px;font-weight:800;font-size:12px;flex:0 0 26px;'
   +'background:'+c[0]+';color:'+c[1]+';box-shadow:inset 0 -2px 4px rgba(0,0,0,.05);';
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


def add_css(ev, css):
    ev("(function(){var s=document.createElement('style');s.id='puffCss';s.textContent=%s;document.head.appendChild(s)})()"
       % json.dumps(css))


def snap(send, path):
    d = send("Page.captureScreenshot", {"format": "png"})
    with open(path, "wb") as f:
        f.write(base64.b64decode(d["data"]))
    print("OK", os.path.basename(path), os.path.getsize(path) // 1024, "KB")


def go(send, ev, port, view, wait_js, extra_js="", sleep_after=2.6):
    send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=%s" % (port, view)})
    for _ in range(60):
        if ev("typeof LIB!=='undefined'") and ev(wait_js):
            break
        time.sleep(1)
    time.sleep(sleep_after)
    ev("typeof applyTheme==='function'&&applyTheme('E')")
    add_css(ev, CSS_PUFF)
    ev(JS_DECO)
    if extra_js:
        ev(extra_js)
    time.sleep(0.8)


def main():
    port = int(sys.argv[1])
    proc, send, ev = launch()
    send("Page.enable")
    try:
        # A 服务器
        go(send, ev, port, "srv", "!!document.querySelector('.srvtab')")
        snap(send, os.path.join(OUT, "泡芙A-服务器整页.png"))
        # B 地图库
        go(send, ev, port, "lib", "document.querySelectorAll('#libList .libRow').length>10",
           JS_CHIPS)
        snap(send, os.path.join(OUT, "泡芙B-地图库整页.png"))
        # C 设置
        go(send, ev, port, "set", "!!document.querySelector('#view-set .card')")
        snap(send, os.path.join(OUT, "泡芙C-设置整页.png"))
        # D 屏幕覆盖
        go(send, ev, port, "ov", "!!document.querySelector('#view-ov input[type=checkbox]')")
        snap(send, os.path.join(OUT, "泡芙D-屏幕覆盖整页.png"))
        # E 主题
        go(send, ev, port, "theme", "document.querySelectorAll('#themes .tcard').length>=5")
        snap(send, os.path.join(OUT, "泡芙E-主题整页.png"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

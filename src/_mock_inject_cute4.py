# -*- coding: utf-8 -*-
"""可爱风样板 · 新一组「卡通图片风」：真实卡通图片当背景。

素材（ImageGen 生成后裁水印压缩，存 _cuteart/）：
  · pat.jpg   —— 卡通无缝图案（小兔/草莓/星星/云朵/波点）→ body 平铺背景（白色薄纱压淡）
  · scene.jpg —— 卡通小场景（云朵上的小兔与小猫）→ 卡片右上角水印 + 侧栏卡通贴纸
用法：_mock_inject_cute4.py <port>
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
ART = os.path.join(ROOT, "_cuteart")
CDP = 9389


def data_uri(path):
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")


CSS_TMPL = """
/* ── 卡通图片风 · 页面平铺卡通图案背景（白色薄纱压淡保证可读） ── */
body{
 background-image:
  radial-gradient(700px 320px at 4% -8%, rgba(221,247,237,.55) 0%, rgba(221,247,237,0) 60%),
  radial-gradient(760px 340px at 100% -6%, rgba(255,230,241,.55) 0%, rgba(255,230,241,0) 58%),
  linear-gradient(rgba(255,252,254,.60), rgba(255,250,253,.66)),
  url(__PAT__) !important;
 background-repeat: no-repeat, no-repeat, repeat, repeat !important;
 background-size: auto, auto, auto, 380px 380px !important;
 background-attachment: scroll, scroll, fixed, fixed !important;}
/* ── 卡通图片风 · 内容区（.main 才是真实底色，body 会被它盖住） ── */
.main{
 background-image:
  linear-gradient(rgba(255,252,254,.52), rgba(255,250,253,.60)),
  url(__PAT__) !important;
 background-repeat: repeat, repeat !important;
 background-size: auto, 380px 380px !important;
 background-attachment: local, local !important;}
.side{
 background-image: linear-gradient(rgba(255,246,250,.72), rgba(255,246,250,.80)), url(__PAT__) !important;
 background-repeat: repeat, repeat !important;
 background-size: auto, 340px 340px !important;}
/* ── 卡片：白底 + 右上角卡通小场景水印 ── */
.card{
 background-image: linear-gradient(rgba(255,255,255,.80), rgba(255,255,255,.86)), url(__SCENE__) !important;
 background-repeat: no-repeat, no-repeat !important;
 background-size: cover, 340px auto !important;
 background-position: center, right -30px top -50px !important;
 border-radius:26px !important;border:3px solid #fff !important;
 box-shadow:0 10px 24px rgba(255,170,200,.18), 0 0 0 3px #ffe6f0 !important;}
button,.btn{border-radius:999px !important;}
/* ── 侧栏底部卡通贴纸（白边拍立得感） ── */
#cuteSticker{position:fixed;left:14px;bottom:12px;width:132px;z-index:6;
 border:6px solid #fff;border-radius:20px;transform:rotate(-4deg);
 box-shadow:0 10px 22px rgba(255,150,190,.32);opacity:.98;}
/* ── 列表行：圆角 + 半透白，让图案底透出一点 ── */
#libList .libRow{border-radius:20px !important;margin:5px 3px !important;border:none !important;
 background:rgba(255,255,255,.86) !important;box-shadow:0 3px 9px rgba(255,180,205,.14) !important;}
#libList .libRow:hover{transform:translateY(-2px);background:rgba(255,255,255,.95) !important;}
#libDetail .libHead{border-radius:24px !important;}
#themes .tcard{border-radius:26px !important;border:3px solid #fff !important;
 box-shadow:0 10px 22px rgba(255,170,200,.18) !important;overflow:hidden;}
#themes .tcard:hover{transform:translateY(-4px);}
/* ── 覆盖页：奶油胶囊开关 ── */
#view-ov label{padding:8px 12px;border-radius:16px;cursor:pointer;}
#view-ov label:hover{background:rgba(255,246,250,.9);}
#view-ov input[type=checkbox]{appearance:none;-webkit-appearance:none;position:relative;
 width:42px;height:24px;flex:0 0 42px;border-radius:999px;background:#ffe3ee;
 box-shadow:inset 0 2px 4px rgba(255,150,190,.30);transition:background .18s;cursor:pointer;margin:0;order:-1;}
#view-ov input[type=checkbox]::after{content:'';position:absolute;top:3px;left:3px;width:18px;height:18px;
 border-radius:50%;background:#fff;box-shadow:0 2px 5px rgba(0,0,0,.15);transition:left .18s;}
#view-ov input[type=checkbox]:checked{background:linear-gradient(135deg,#8fe3c6,#ffb8d6);}
#view-ov input[type=checkbox]:checked::after{left:21px;}
/* ── 地图库首字徽章：卡通圆牌 ── */
#libList .cstk{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
 border-radius:50%;margin-right:8px;font-weight:800;font-size:13px;flex:0 0 30px;
 border:3px solid #fff;box-shadow:0 3px 8px rgba(255,150,190,.28);}
"""

JS_CHIP = r"""
(function(){
 var cs=[['#d8f6ea','#2f8f70'],['#ffe0ee','#c94a80'],['#fff3d6','#b8860b'],
         ['#e2f0ff','#3577b8'],['#efe6ff','#6d4fc9']];
 var rows=document.querySelectorAll('#libList .libRow');
 for(var i=0;i<rows.length;i++){
  var r=rows[i]; if(r.querySelector('.cstk')) continue;
  var c=cs[i%cs.length], b=document.createElement('span'); b.className='cstk';
  b.style.background=c[0]; b.style.color=c[1];
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


def snap(send, path):
    d = send("Page.captureScreenshot", {"format": "png"})
    with open(path, "wb") as f:
        f.write(base64.b64decode(d["data"]))
    print("OK", os.path.basename(path), os.path.getsize(path) // 1024, "KB")


def main():
    port = int(sys.argv[1])
    pat = data_uri(os.path.join(ART, "pat.jpg"))
    scene = data_uri(os.path.join(ART, "scene.jpg"))
    css = CSS_TMPL.replace("__PAT__", pat).replace("__SCENE__", scene)
    js_sticker = ("(function(){if(document.getElementById('cuteSticker'))return;"
                  "var i=document.createElement('img');i.id='cuteSticker';i.src='%s';"
                  "document.body.appendChild(i)})()" % scene)

    proc, send, ev = launch()
    send("Page.enable")

    def go(view, wait_js, extra_js=""):
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=%s" % (port, view)})
        for _ in range(60):
            if ev("typeof LIB!=='undefined'") and ev(wait_js):
                break
            time.sleep(1)
        time.sleep(2.6)
        ev("typeof applyTheme==='function'&&applyTheme('E')")
        ev("(function(){var s=document.createElement('style');s.textContent=%s;document.head.appendChild(s)})()"
           % json.dumps(css))
        ev(js_sticker)
        if extra_js:
            ev(extra_js)
        time.sleep(1.0)

    try:
        go("srv", "!!document.querySelector('.srvtab')")
        snap(send, os.path.join(OUT, "卡通A-服务器整页.png"))
        go("lib", "document.querySelectorAll('#libList .libRow').length>10", JS_CHIP)
        snap(send, os.path.join(OUT, "卡通B-地图库整页.png"))
        go("set", "!!document.querySelector('#view-set .card')")
        snap(send, os.path.join(OUT, "卡通C-设置整页.png"))
        go("ov", "!!document.querySelector('#view-ov input[type=checkbox]')")
        snap(send, os.path.join(OUT, "卡通D-屏幕覆盖整页.png"))
        go("theme", "document.querySelectorAll('#themes .tcard').length>=5")
        snap(send, os.path.join(OUT, "卡通E-主题整页.png"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

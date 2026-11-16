# -*- coding: utf-8 -*-
"""主题样板 · 贴合「云朵小铺 · ZE 通关奖励」的可爱 / 二次元素材。

素材（ImageGen 生成 -> 裁水印压缩，存 _themeart/）：
  · pat.jpg       云朵+龙晶+Q版小僵尸 无缝图案  -> 页面底纹
  · pat_dark.jpg  同款暗色底纹                 -> 夜幕护眼主题
  · run.jpg       Q版冒险小队冲向终点彩虹门    -> 服务器页英雄横幅
  · winner.jpg    二次元少女举旗 + 满屏蓝宝石  -> 地图库横幅
  · mascot.jpg    云朵吉祥物抱着龙晶袋         -> 卡片右上角淡水印
  · girl.jpg      二次元少女坐云朵敲电脑       -> 设置页插画头图
  · zombie.png    透明底 Q 版小僵尸贴纸        -> 侧栏贴纸 / 角标
用法：_mock_inject_theme.py <port>
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
ART = os.path.join(ROOT, "_themeart")
CDP = 9392


def uri(path):
    ext = os.path.splitext(path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    with open(path, "rb") as f:
        return "data:%s;base64,%s" % (mime, base64.b64encode(f.read()).decode("ascii"))


# ── 通用底座：页面底纹 + 卡片云朵水印 + 侧栏贴纸 ──────────────────────────
BASE = """
/* ── 1. 页面底纹：云朵 / 龙晶 / 小僵尸 无缝图案（白纱压淡保可读） ── */
html,body{background:#fff9fc !important;}
body,.main{
 background-image:
  radial-gradient(720px 320px at 2% -10%, rgba(214,240,255,.70) 0%, rgba(214,240,255,0) 62%),
  radial-gradient(780px 340px at 100% -8%, rgba(255,226,240,.70) 0%, rgba(255,226,240,0) 60%),
  linear-gradient(rgba(255,253,254,.56), rgba(255,250,253,.64)),
  url(__PAT__) !important;
 background-repeat:no-repeat,no-repeat,repeat,repeat !important;
 background-size:auto,auto,auto,400px 368px !important;
 background-attachment:scroll,scroll,local,fixed !important;}
.side{
 background-image:
  linear-gradient(180deg, rgba(255,249,252,.74) 0%, rgba(255,246,251,.80) 100%),
  url(__PAT__) !important;
 background-repeat:repeat,repeat !important;
 background-size:auto,360px 331px !important;}
/* ── 2. 卡片：白胖圆角 + 右上角云朵吉祥物淡水印 ── */
.card,.rmcard,.syncbox,.fxcard,.themePal{
 background-image:linear-gradient(rgba(255,255,255,.80), rgba(255,255,255,.86)), url(__MASCOT__) !important;
 background-repeat:no-repeat,no-repeat !important;
 background-size:cover,290px auto !important;
 background-position:center,right -46px top -54px !important;
 border-radius:28px !important;border:3px solid #fff !important;
 box-shadow:0 12px 26px rgba(146,186,236,.20), 0 0 0 3px #eaf4ff !important;}
h2{letter-spacing:.02em;}
/* ── 3. 侧栏 Q 版小僵尸贴纸 ── */
#cuteSticker{position:fixed;left:10px;bottom:8px;width:112px;z-index:6;pointer-events:none;
 transform:rotate(-5deg);filter:drop-shadow(0 10px 16px rgba(120,160,220,.40));}
/* ── 4. 圆润控件 ── */
button,.btn,.srvtab th{border-radius:999px !important;}
#libList .libRow{border-radius:20px !important;margin:5px 3px !important;border:none !important;
 background:rgba(255,255,255,.88) !important;box-shadow:0 3px 9px rgba(150,190,240,.16) !important;
 transition:transform .16s, background .16s;}
#libList .libRow:hover{transform:translateY(-2px);background:#fff !important;}
#libList .cstk{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
 border-radius:50%;margin-right:8px;font-weight:800;font-size:13px;flex:0 0 30px;
 border:3px solid #fff;box-shadow:0 3px 8px rgba(150,190,240,.30);}
#themes .tcard{border-radius:28px !important;border:3px solid #fff !important;overflow:hidden;
 box-shadow:0 10px 22px rgba(146,186,236,.20) !important;transition:transform .18s;}
#themes .tcard:hover{transform:translateY(-4px);}
"""

# ── 服务器页：英雄横幅（Q版冒险小队冲向终点彩虹门） ──────────────────────
CSS_SRV = """
.tHero{position:relative;margin:0 0 14px;border-radius:30px;overflow:hidden;
 border:4px solid #fff;box-shadow:0 16px 34px rgba(146,186,236,.28);}
.tHero img{display:block;width:100%;height:170px;object-fit:cover;object-position:center 64%;}
.tHero .tt{position:absolute;left:0;right:0;bottom:0;padding:30px 22px 14px;
 background:linear-gradient(transparent, rgba(255,255,255,.94));
 font-weight:900;font-size:20px;color:#54658c;letter-spacing:.03em;text-shadow:0 1px 0 #fff;}
.tHero .tt small{display:block;font-weight:700;font-size:12.5px;color:#8fa0bf;margin-top:5px;letter-spacing:0;}
.tHero .bd{position:absolute;right:14px;top:12px;background:rgba(255,255,255,.92);
 border-radius:999px;padding:5px 13px;font-size:12px;font-weight:800;color:#6d7fa8;
 box-shadow:0 4px 12px rgba(146,186,236,.30);}
"""
JS_SRV = r"""
(function(){
 var v=document.querySelector('#view-srv'); if(!v||v.querySelector('.tHero'))return;
 var d=document.createElement('div'); d.className='tHero';
 d.innerHTML='<img src="__RUN__"><div class="bd">ZOMBIE ESCAPE · 通关奖励</div>'+
  '<div class="tt">云朵小铺 · 通关奖励看板<small>云点 / 龙晶 达标门槛速查 · 实时服务器状态</small></div>';
 v.insertBefore(d,v.firstChild);
})()
"""

# ── 地图库：库横幅（二次元少女举旗 + 满屏蓝宝石） ────────────────────────
CSS_LIB = """
.libHero{position:relative;margin:0 0 12px;border-radius:26px;overflow:hidden;
 border:4px solid #fff;box-shadow:0 14px 30px rgba(146,186,236,.26);}
.libHero img{display:block;width:100%;height:132px;object-fit:cover;object-position:center 54%;}
.libHero .tt{position:absolute;left:0;right:0;bottom:0;padding:24px 20px 11px;
 background:linear-gradient(transparent, rgba(255,255,255,.94));
 font-weight:900;font-size:16.5px;color:#54658c;text-shadow:0 1px 0 #fff;}
.libHero .tt small{font-weight:700;font-size:12px;color:#8fa0bf;margin-left:8px;}
"""
JS_LIB = r"""
(function(){
 var c=document.querySelector('#view-lib .card'); if(!c||c.querySelector('.libHero'))return;
 var d=document.createElement('div'); d.className='libHero';
 d.innerHTML='<img src="__WINNER__"><div class="tt">地图库 · 奖励一览<small>点 ▸ 展开细类 · 点卡片看 3D 实体</small></div>';
 c.insertBefore(d,c.firstChild);
})()
"""

# ── 设置页：插画头图（二次元少女坐云朵敲电脑） ────────────────────────────
CSS_SET = """
.setHero{display:flex;gap:16px;align-items:center;background:#fff;border:4px solid #fff;
 border-radius:28px;padding:12px 18px;margin:0 0 14px;
 box-shadow:0 14px 30px rgba(146,186,236,.24);}
.setHero img{width:158px;height:106px;object-fit:cover;object-position:center 30%;border-radius:20px;flex:0 0 158px;}
.setHero .st{font-weight:900;font-size:17px;color:#54658c;}
.setHero .st small{display:block;font-weight:700;font-size:12.5px;color:#8fa0bf;margin-top:6px;line-height:1.6;}
"""
JS_SET = r"""
(function(){
 var v=document.querySelector('#view-set'); if(!v||v.querySelector('.setHero'))return;
 var d=document.createElement('div'); d.className='setHero';
 d.innerHTML='<img src="__GIRL__"><div class="st">设置 · 数据与外观'+
  '<small>官方数据自动同步 · 主题 / 动效 / 覆盖层都在这里调<br>数据源与云端索引保持同步，无需重装</small></div>';
 v.insertBefore(d,v.firstChild);
})()
"""

# ── 屏幕覆盖页：云朵胶囊开关 ──────────────────────────────────────────────
CSS_OV = """
#view-ov label{padding:8px 12px;border-radius:18px;cursor:pointer;}
#view-ov label:hover{background:rgba(255,248,252,.92);}
#view-ov input[type=checkbox]{appearance:none;-webkit-appearance:none;position:relative;
 width:44px;height:25px;flex:0 0 44px;border-radius:999px;background:#e6f0ff;
 box-shadow:inset 0 2px 5px rgba(120,160,220,.32);transition:background .18s;cursor:pointer;margin:0;order:-1;}
#view-ov input[type=checkbox]::after{content:'';position:absolute;top:3px;left:3px;width:19px;height:19px;
 border-radius:50%;background:#fff;box-shadow:0 2px 5px rgba(0,0,0,.16);transition:left .18s;}
#view-ov input[type=checkbox]:checked{background:linear-gradient(135deg,#8fd9f0,#ffb3d4);}
#view-ov input[type=checkbox]:checked::after{left:22px;}
#ovPrev.ovPrev{border-radius:24px !important;border:4px solid #fff !important;
 box-shadow:0 12px 26px rgba(146,186,236,.24) !important;overflow:hidden;}
"""

# ── 地图库行首卡通圆牌 ────────────────────────────────────────────────────
JS_CHIP = r"""
(function(){
 var cs=[['#d8f2ff','#2f7fb8'],['#ffe0ee','#c94a80'],['#e6f7e9','#3f8f5b'],
         ['#fff2d6','#b8860b'],['#eee6ff','#6d4fc9']];
 var rows=document.querySelectorAll('#libList .libRow');
 for(var i=0;i<rows.length;i++){
  var r=rows[i]; if(r.querySelector('.cstk'))continue;
  var c=cs[i%cs.length],b=document.createElement('span'); b.className='cstk';
  b.style.background=c[0]; b.style.color=c[1];
  b.textContent=(r.textContent.trim().charAt(0)||'Z').toUpperCase();
  r.insertBefore(b,r.firstChild);
 }
})()
"""


def launch():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    prof = os.path.join(OUT, "_prof_theme")
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
    ws = websocket.create_connection(ws_url, timeout=240)
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
    P = {
        "PAT": uri(os.path.join(ART, "pat.jpg")),
        "PDRK": uri(os.path.join(ART, "pat_dark.jpg")),
        "MASCOT": uri(os.path.join(ART, "mascot.jpg")),
        "RUN": uri(os.path.join(ART, "run.jpg")),
        "WINNER": uri(os.path.join(ART, "winner.jpg")),
        "GIRL": uri(os.path.join(ART, "girl.jpg")),
        "ZOMBIE": uri(os.path.join(ART, "zombie.png")),
    }

    def fill(s):
        for k, v in P.items():
            s = s.replace("__%s__" % k, v)
        return s

    base = fill(BASE)
    js_sticker = ("(function(){if(document.getElementById('cuteSticker'))return;"
                  "var i=document.createElement('img');i.id='cuteSticker';i.src='__ZOMBIE__';"
                  "document.body.appendChild(i)})()").replace("__ZOMBIE__", P["ZOMBIE"])

    proc, send, ev = launch()
    send("Page.enable")

    def go(view, wait_js, css="", extra_js="", theme="E", pat=None):
        send("Page.navigate", {"url": "http://127.0.0.1:%d/?view=%s" % (port, view)})
        for _ in range(60):
            if ev("typeof LIB!=='undefined'") and ev(wait_js):
                break
            time.sleep(1)
        time.sleep(2.8)
        ev("typeof applyTheme==='function'&&applyTheme(%s)" % json.dumps(theme))
        blob = pat or base
        ev("(function(){var o=document.getElementById('__mockcss');if(o)o.remove();"
           "var s=document.createElement('style');s.id='__mockcss';s.textContent=%s;"
           "document.head.appendChild(s)})()" % json.dumps(blob + fill(css)))
        ev(js_sticker)
        if extra_js:
            ev(fill(extra_js))
        time.sleep(1.1)

    try:
        go("srv", "!!document.querySelector('.srvtab')", CSS_SRV, JS_SRV)
        snap(send, os.path.join(OUT, "主题A-服务器整页.png"))

        go("lib", "document.querySelectorAll('#libList .libRow').length>10",
           CSS_LIB, JS_LIB + ";" + JS_CHIP)
        snap(send, os.path.join(OUT, "主题B-地图库整页.png"))

        go("set", "!!document.querySelector('#view-set .rmcard')", CSS_SET, JS_SET)
        snap(send, os.path.join(OUT, "主题C-设置整页.png"))

        go("ov", "!!document.querySelector('#view-ov input[type=checkbox]')", CSS_OV)
        snap(send, os.path.join(OUT, "主题D-屏幕覆盖整页.png"))

        go("theme", "document.querySelectorAll('#themes .tcard').length>=5")
        snap(send, os.path.join(OUT, "主题E-主题页整页.png"))

        go("pre", "!!document.querySelector('#view-pre iframe')")
        time.sleep(6)
        snap(send, os.path.join(OUT, "主题G-实体预览整页.png"))

        # 夜幕护眼：同款暗色底纹
        go("srv", "!!document.querySelector('.srvtab')", CSS_SRV, JS_SRV,
           theme="N", pat=base.replace(P["PAT"], P["PDRK"]))
        snap(send, os.path.join(OUT, "主题F-服务器-夜幕暗色版.png"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

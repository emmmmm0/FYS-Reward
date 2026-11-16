# -*- coding: utf-8 -*-
"""整页美化样板：在真实软件页面上注入样式后整窗截图（与软件窗口同尺寸）。
用法: _mock_inject_shots.py <port>   产物: 验证截图-界面巡检/样板{A,B,C,D}-*.png"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35\验证截图-界面巡检"
CDP = 9357
W, H = 1330, 720

# ── 样板A：服务器页 ──────────────────────────────────────────────
CSS_A = """
#view-srv .mockHero{display:flex;align-items:center;gap:14px;border-radius:16px;padding:13px 20px;margin-bottom:14px;
  background:linear-gradient(100deg,var(--soft,#ffeef4),#f3e6ff);box-shadow:0 4px 14px rgba(255,127,165,.16)}
#view-srv .mockHero .ava{width:46px;height:46px;border-radius:14px;background:#fff;display:flex;align-items:center;
  justify-content:center;font-size:25px;box-shadow:0 2px 8px rgba(255,127,165,.25);flex:none}
#view-srv .mockHero b{font-size:15px;display:block;line-height:1.3}
#view-srv .mockHero .sub2{font-size:11px;color:var(--muted)}
#view-srv .mockHero .nums{margin-left:auto;display:flex;gap:26px;text-align:center}
#view-srv .mockHero .nums b{font-size:20px;display:block;line-height:1.2}
#view-srv .mockHero .nums span{font-size:10px;color:var(--muted)}
#view-srv .srvtab{border-collapse:separate !important;border-spacing:0 7px !important}
#view-srv .srvtab thead th{padding:0 12px 2px !important;border-bottom:0 !important;background:none !important;
  color:var(--muted) !important;font-size:10.5px !important}
#view-srv .srvtab tbody tr{background:var(--panel) !important;
  box-shadow:0 1px 8px rgba(90,74,82,.06),0 0 0 1.5px var(--line) !important}
#view-srv .srvtab tbody tr:hover{box-shadow:0 3px 12px rgba(255,127,165,.16),0 0 0 1.5px var(--accent) !important}
#view-srv .srvtab tbody td{border:0 !important;background:transparent !important}
#view-srv .srvtab tbody tr.mockCur{box-shadow:0 3px 12px rgba(255,127,165,.2),0 0 0 2px var(--accent) !important}
#view-srv .sbadge{display:inline-flex;width:30px;height:30px;border-radius:10px;color:#fff;font-weight:800;
  font-size:12px;align-items:center;justify-content:center;margin-right:9px;vertical-align:middle;flex:none}
"""
JS_A = """
(function(){
  var view=document.querySelector('#view-srv'); if(!view) return 'NOVIEW';
  var colR=view.querySelector('.colR'); if(!colR||view.querySelector('.mockHero')) return 'done';
  var st=document.createElement('style'); st.textContent=%CSS_A%; document.head.appendChild(st);
  var h=document.createElement('div'); h.className='mockHero';
  h.innerHTML='<div class="ava">\\u2601\\uFE0F</div><div><b>\\u5F53\\u524D\\u72B6\\u6001\\uFF1A\\u672A\\u5728\\u670D\\u52A1\\u5668\\u5185</b>'+
   '<div class="sub2">\\u4E0A\\u6B21\\u52A0\\u5165 \\u3010\\u50F5\\u5C38\\u4E50\\u56ED\\u3011CS2 \\u8FDE\\u8DF3 Bhop \\u56F0\\u96BE #2 \\u00B7 09-23 12:04</div></div>'+
   '<div class="nums"><div><b style="color:#e0568a">1,284</b><span>\\u7D2F\\u8BA1\\u4E91\\u70B9</span></div>'+
   '<div><b style="color:#7a5cc4">96</b><span>\\u7D2F\\u8BA1\\u9F99\\u6676</span></div>'+
   '<div><b style="color:#3ea37a">213</b><span>\\u901A\\u5173\\u6B21\\u6570</span></div></div>';
  colR.insertBefore(h, colR.firstChild);
  var gs=['linear-gradient(135deg,#ff9db8,#ff6f9c)','linear-gradient(135deg,#8fd0ff,#5aa8f0)',
          'linear-gradient(135deg,#c4b8ff,#9b7ff0)','linear-gradient(135deg,#ffd08a,#ffab4a)',
          'linear-gradient(135deg,#9dffc9,#5fd0a0)'];
  var cur=view.querySelector('#srvName') ? view.querySelector('#srvName').textContent : '';
  var rows=view.querySelectorAll('.srvtab tbody tr');
  for(var i=0;i<rows.length;i++){
    var tr=rows[i], td=tr.cells[0]; if(!td) continue;
    var name=td.textContent.trim();
    if(name){
      var b=document.createElement('span'); b.className='sbadge';
      b.style.background=gs[i%gs.length];
      var ch=name.replace(/[^0-9A-Za-z\\u4e00-\\u9fa5]/g,'').charAt(0);
      b.textContent=ch||'?';
      td.insertBefore(b, td.firstChild);
    }
    if(cur && name && cur.indexOf(name.slice(0,5))>-1) tr.classList.add('mockCur');
  }
  return 'ok';
})()
"""

# ── 样板B：地图库 ────────────────────────────────────────────────
CSS_B = """
#libList .libRow{border-radius:12px;transition:box-shadow .15s,transform .15s}
#libList .libRow:hover{transform:translateX(2px);box-shadow:0 3px 10px rgba(255,127,165,.15)}
#libList .lbadge{display:inline-flex;width:30px;height:30px;border-radius:10px;color:#fff;font-weight:800;
  font-size:13px;align-items:center;justify-content:center;margin-right:10px;flex:none}
#libDetail>.card:first-child{background:linear-gradient(115deg,var(--soft,#ffeef4),#eae4ff) !important;
  border-radius:16px !important}
#libDetail .libHead .big .cn{font-size:21px !important;font-weight:800 !important}
#libDetail .libHead .big .fn{font-family:Consolas,monospace !important;opacity:.75}
#libDetail .libHead .libBdg{background:rgba(255,255,255,.75) !important;border-radius:12px !important}
#libDetail .libHead .libKb{background:rgba(255,255,255,.75) !important;border-radius:12px !important}
"""
JS_B = """
(function(){
  var view=document.querySelector('#view-lib'); if(!view) return 'NOVIEW';
  if(view.querySelector('.lbadge')) return 'done';
  var st=document.createElement('style'); st.textContent=%CSS_B%; document.head.appendChild(st);
  var gs=['linear-gradient(135deg,#ff9db8,#ff6f9c)','linear-gradient(135deg,#8fd0ff,#5aa8f0)',
          'linear-gradient(135deg,#c4b8ff,#9b7ff0)','linear-gradient(135deg,#ffd08a,#ffab4a)',
          'linear-gradient(135deg,#9dffc9,#5fd0a0)'];
  var rows=view.querySelectorAll('#libList .libRow');
  var n=0;
  for(var i=0;i<rows.length;i++){
    var row=rows[i];
    var key=row.getAttribute('data-f')||'';
    var hash=0; for(var j=0;j<key.length;j++){hash=(hash*31+key.charCodeAt(j))>>>0;}
    var lm=row.querySelector('.lm'); if(!lm) continue;
    var b=document.createElement('span'); b.className='lbadge';
    b.style.background=gs[hash%gs.length];
    var cn=row.querySelector('.lc');
    var txt=cn?cn.textContent.trim():'';
    b.textContent=txt.charAt(0)||'?';
    lm.insertBefore(b, lm.firstChild);
    n++;
  }
  return 'ok:'+n;
})()
"""

# ── 样板C：主题页（色卡缩略） ────────────────────────────────────
CSS_C = """
#themes .tcard{position:relative;overflow:visible}
#themes .tcard.on::after{content:'\\u2713';position:absolute;top:-8px;right:-8px;width:24px;height:24px;
  border-radius:50%;background:var(--accent);color:#fff;font-size:12px;font-weight:800;
  display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(255,127,165,.4)}
#themes .tcard{transition:transform .15s,box-shadow .15s}
#themes .tcard:hover{transform:translateY(-3px);box-shadow:0 5px 14px rgba(255,127,165,.2)}
#themes .mockband{border-radius:10px;overflow:hidden;border:1px solid var(--line);margin-bottom:8px}
#themes .mockband>div{height:15px;display:flex;gap:4px;align-items:center;padding:0 6px}
#themes .mockband i{width:16px;height:5px;border-radius:99px;background:rgba(255,255,255,.65);display:block}
#themes .mockband>div+div i+i{background:var(--line)}
"""
JS_C = """
(function(){
  var view=document.querySelector('#view-theme'); if(!view) return 'NOVIEW';
  if(view.querySelector('.mockband')) return 'done';
  var st=document.createElement('style'); st.textContent=%CSS_C%; document.head.appendChild(st);
  var bands={E:['#ffd6e7','#fff5f9'],F:['#c9ecd7','#f2fbf5'],G:['#cfe4ff','#f2f8ff'],
             H:['#ffd9c9','#fff6f0'],N:['#2b2436','#221c2e']};
  var cards=view.querySelectorAll('#themes .tcard');
  var n=0;
  for(var i=0;i<cards.length;i++){
    var c=cards[i];
    var id=c.getAttribute('data-t')||'';
    var bd=bands[id]; if(!bd) continue;
    var m=document.createElement('div'); m.className='mockband';
    m.innerHTML='<div style="background:'+bd[0]+'"><i></i><i></i></div>'+
                '<div style="background:'+bd[1]+'"><i style="background:'+bd[0]+'"></i><i></i></div>';
    c.insertBefore(m, c.firstChild);
    n++;
  }
  return 'ok:'+n;
})()
"""

# ── 样板D：设置页（快速操作卡 + 关于行图标） ─────────────────────
CSS_D = """
#view-set .qgrid{display:flex;gap:12px;margin-bottom:16px}
#view-set .qcard{flex:1;border-radius:16px;border:1.5px solid var(--line);background:var(--panel);
  padding:13px 16px;display:flex;align-items:center;gap:11px;box-shadow:0 2px 10px rgba(90,74,82,.05);
  transition:box-shadow .15s,transform .15s}
#view-set .qcard:hover{box-shadow:0 4px 14px rgba(255,127,165,.18);transform:translateY(-2px)}
#view-set .qcard .qi{width:38px;height:38px;border-radius:12px;display:flex;align-items:center;
  justify-content:center;font-size:18px;flex:none}
#view-set .qcard b{font-size:12.5px;display:block;line-height:1.35}
#view-set .qcard span{font-size:10.5px;color:var(--muted)}
#view-set .aboutRow .ai{width:24px;height:24px;border-radius:9px;background:var(--soft,#ffeef4);
  display:inline-flex;align-items:center;justify-content:center;font-size:12px;flex:none;margin-right:2px}
"""
JS_D = """
(function(){
  var view=document.querySelector('#view-set'); if(!view) return 'NOVIEW';
  if(view.querySelector('.qgrid')) return 'done';
  var st=document.createElement('style'); st.textContent=%CSS_D%; document.head.appendChild(st);
  var q=document.createElement('div'); q.className='qgrid';
  q.innerHTML=
   '<div class="qcard"><div class="qi" style="background:#e8fbf0">\\u21BB</div><div><b>\\u7ACB\\u5373\\u540C\\u6B65</b><span>GitHub \\u6570\\u636E \\u00B7 1 \\u5206\\u949F\\u524D</span></div></div>'+
   '<div class="qcard"><div class="qi" style="background:#fff0d8">\\uD83D\\uDCC4</div><div><b>\\u8FD0\\u884C\\u65E5\\u5FD7</b><span>startup.log \\u00B7 84 KB</span></div></div>'+
   '<div class="qcard"><div class="qi" style="background:#ffe3ec">\\uD83E\\uDDF9</div><div><b>\\u6E05\\u7406\\u7F13\\u5B58</b><span>data \\u7F13\\u5B58 \\u00B7 12 MB</span></div></div>';
  var anchor=view.querySelector('h2');
  if(anchor) anchor.parentElement.insertBefore(q, anchor);
  else view.insertBefore(q, view.firstChild);
  var ics={'\\u5F53\\u524D\\u7248\\u672C':'\\uD83E\\uDD14','\\u6570\\u636E\\u6765\\u6E90':'\\uD83D\\uDCE6',
           '\\u5173\\u5361\\u6765\\u6E90':'\\uD83D\\uDCEE'};
  var rows=view.querySelectorAll('.aboutRow');
  for(var i=0;i<rows.length;i++){
    var al=rows[i].querySelector('.al'); if(!al) continue;
    var t=(al.textContent||'').trim();
    var ic=ics[t]; if(!ic) continue;
    var s=document.createElement('span'); s.className='ai'; s.textContent=ic;
    al.insertBefore(s, al.firstChild);
  }
  return 'ok';
})()
"""

VIEWS = [
    ("样板A-服务器整页", "/?view=srv", CSS_A, JS_A, 3.0),
    ("样板B-地图库整页", "/?view=lib", CSS_B, JS_B, 3.5),
    ("样板C-主题整页", "/?view=theme", CSS_C, JS_C, 1.5),
    ("样板D-设置整页", "/?view=set", CSS_D, JS_D, 1.5),
]


def main():
    port = int(sys.argv[1])
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    prof = os.path.join(OUT, "_prof_cdp9")
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
         "--remote-allow-origins=*", "--user-data-dir=" + prof,
         "--no-first-run", "--window-size=%d,%d" % (W, H), "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
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
            return send("Runtime.evaluate", {"expression": e, "returnByValue": True}) \
                .get("result", {}).get("value")

        send("Page.enable")
        for name, url, css, js, extra in VIEWS:
            send("Page.navigate", {"url": "http://127.0.0.1:%d%s" % (port, url)})
            deadline = time.time() + 60
            while time.time() < deadline:
                if ev("typeof LIB!=='undefined'"):
                    break
                time.sleep(1)
            time.sleep(extra)
            inject = js.replace("%CSS_A%", json.dumps(css)) \
                       .replace("%CSS_B%", json.dumps(css)) \
                       .replace("%CSS_C%", json.dumps(css)) \
                       .replace("%CSS_D%", json.dumps(css))
            res = ev(inject)
            time.sleep(0.8)
            shot = send("Page.captureScreenshot", {"format": "png"})
            p = os.path.join(OUT, "%s.png" % name)
            with open(p, "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            print("%s  注入=%s  %d KB" % (name, res, os.path.getsize(p) // 1024))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

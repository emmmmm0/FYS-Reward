# -*- coding: utf-8 -*-
"""第二批整页美化样板（修正版）：
E 覆盖页 pill 开关（下滚露出开关区）/ F 预览页工具条 / G 服务器·夜幕 / H 地图库·夜幕。
用法: _mock_inject_shots2.py <port>"""
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
CDP = 9371
W, H = 1330, 720

# ── 样板E：屏幕覆盖（pill 开关 + 组头图标） ─────────────────────
CSS_E = """
#view-ov label{display:inline-flex;align-items:center;gap:7px;cursor:pointer}
#view-ov label input[type=checkbox]{appearance:none;-webkit-appearance:none;width:36px;height:20px;
  border-radius:99px;background:var(--line,#e4d5dd);position:relative;cursor:pointer;
  transition:background .18s;margin:0;flex:none;vertical-align:middle}
#view-ov label input[type=checkbox]::after{content:'';position:absolute;width:16px;height:16px;
  border-radius:50%;background:#fff;top:2px;left:2px;box-shadow:0 1px 3px rgba(0,0,0,.25);transition:left .18s}
#view-ov label input[type=checkbox]:checked{background:var(--good,#6fcf97)}
#view-ov label input[type=checkbox]:checked::after{left:18px}
#view-ov label{padding:4px 10px;border-radius:10px;transition:background .15s}
#view-ov label:hover{background:var(--soft,#ffeef4)}
#view-ov h2 .pi{display:inline-flex;width:26px;height:26px;border-radius:9px;background:var(--soft,#ffeef4);
  align-items:center;justify-content:center;font-size:13px;margin-right:8px;vertical-align:-6px}
"""
JS_E = """
(function(){
  var view=document.querySelector('#view-ov'); if(!view) return 'NOVIEW';
  if(view.dataset.mockE) return 'done';
  view.dataset.mockE='1';
  var st=document.createElement('style'); st.textContent=%CSS_E%; document.head.appendChild(st);
  var ics={'\\u663E\\u793A\\u5185\\u5BB9':'\\uD83D\\uDCCB','\\u6837\\u5F0F':'\\uD83C\\uDFA8'};
  var hs=view.querySelectorAll('h2');
  for(var i=0;i<hs.length;i++){
    var t=(hs[i].textContent||'').trim();
    for(var k in ics){
      if(t.indexOf(k)===0 && !hs[i].querySelector('.pi')){
        var s=document.createElement('span'); s.className='pi'; s.textContent=ics[k];
        hs[i].insertBefore(s, hs[i].firstChild);
      }
    }
  }
  return 'ok';
})()
"""

# ── 样板F：实体预览（壳层工具条胶囊化，iframe 不动） ─────────────
CSS_F = """
#view-pre .preBar2{background:var(--panel);border:1.5px solid var(--line);border-radius:14px;
  padding:8px 14px;box-shadow:0 2px 10px rgba(90,74,82,.06)}
#view-pre #preCur2{background:var(--soft,#ffeef4);border-radius:999px;padding:4px 14px;font-weight:800}
#view-pre .preBar2 .btn{border-radius:999px}
#view-pre .preBar2 .btn:hover{box-shadow:0 2px 8px rgba(255,127,165,.2)}
"""
JS_F = """
(function(){
  var view=document.querySelector('#view-pre'); if(!view) return 'NOVIEW';
  if(view.dataset.mockF) return 'done';
  view.dataset.mockF='1';
  var st=document.createElement('style'); st.textContent=%CSS_F%; document.head.appendChild(st);
  return 'ok';
})()
"""

# ── 服务器注入（A/G 共用，主题自适应版） ────────────────────────
CSS_S = """
#view-srv .mockHero{display:flex;align-items:center;gap:14px;border-radius:16px;padding:13px 20px;margin-bottom:14px;
  background:linear-gradient(100deg,var(--soft,#ffeef4),color-mix(in srgb,var(--accent) 10%,var(--panel)));
  box-shadow:0 4px 14px rgba(255,127,165,.16)}
#view-srv .mockHero .ava{width:46px;height:46px;border-radius:14px;background:var(--panel);display:flex;align-items:center;
  justify-content:center;font-size:25px;box-shadow:0 2px 8px rgba(0,0,0,.12);flex:none}
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
JS_S = """
(function(){
  var view=document.querySelector('#view-srv'); if(!view) return 'NOVIEW';
  var colR=view.querySelector('.colR'); if(!colR||view.querySelector('.mockHero')) return 'done';
  var st=document.createElement('style'); st.textContent=%CSS_S%; document.head.appendChild(st);
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

# ── 地图库注入（B/H 共用，主题自适应版） ────────────────────────
CSS_L = """
#libList .libRow{border-radius:12px;transition:box-shadow .15s,transform .15s}
#libList .libRow:hover{transform:translateX(2px);box-shadow:0 3px 10px rgba(255,127,165,.15)}
#libList .lbadge{display:inline-flex;width:30px;height:30px;border-radius:10px;color:#fff;font-weight:800;
  font-size:13px;align-items:center;justify-content:center;margin-right:10px;flex:none}
#libDetail>.card:first-child{background:linear-gradient(115deg,var(--soft,#ffeef4),
  color-mix(in srgb,var(--accent) 12%,var(--panel))) !important;border-radius:16px !important}
#libDetail .libHead .big .cn{font-size:21px !important;font-weight:800 !important}
#libDetail .libHead .big .fn{font-family:Consolas,monospace !important;opacity:.75}
#libDetail .libHead .libBdg{background:var(--panel) !important;border-radius:12px !important}
#libDetail .libHead .libKb{background:var(--panel) !important;border-radius:12px !important}
"""
JS_L = """
(function(){
  var view=document.querySelector('#view-lib'); if(!view) return 'NOVIEW';
  if(view.querySelector('.lbadge')) return 'done';
  var st=document.createElement('style'); st.textContent=%CSS_L%; document.head.appendChild(st);
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

VIEWS = [
    ("样板E-屏幕覆盖整页", "/?view=ov", CSS_E, JS_E, None, 2.5, 300),
    ("样板F-实体预览整页", "/?view=pre&map=ze_pizza_cookie", CSS_F, JS_F, None, 26.0, 0),
    ("样板G-服务器夜幕主题", "/?view=srv", CSS_S, JS_S, "N", 3.0, 0),
    ("样板H-地图库夜幕主题", "/?view=lib", CSS_L, JS_L, "N", 3.5, 0),
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
        for name, url, css, js, theme, extra, scroll in VIEWS:
            send("Page.navigate", {"url": "http://127.0.0.1:%d%s" % (port, url)})
            deadline = time.time() + 90
            while time.time() < deadline:
                if ev("typeof LIB!=='undefined'"):
                    break
                time.sleep(1)
            if theme:
                time.sleep(1.2)
                ev("applyTheme('%s')" % theme)
                time.sleep(1.0)
            time.sleep(extra)
            inject = js.replace("%CSS_E%", json.dumps(css)) \
                       .replace("%CSS_F%", json.dumps(css)) \
                       .replace("%CSS_S%", json.dumps(css)) \
                       .replace("%CSS_L%", json.dumps(css))
            res = ev(inject)
            if scroll:
                ev("window.scrollTo(0,%d)" % scroll)
                time.sleep(0.6)
            time.sleep(0.6)
            shot = send("Page.captureScreenshot", {"format": "png"})
            p = os.path.join(OUT, "%s.png" % name)
            with open(p, "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            print("%s  主题=%s  注入=%s  %d KB" % (name, theme or "默认", res,
                                                  os.path.getsize(p) // 1024))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

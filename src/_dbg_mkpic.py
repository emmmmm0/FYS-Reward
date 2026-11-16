# -*- coding: utf-8 -*-
"""调试：卡通图鉴样板的卡片尺寸与装饰挂载情况。"""
import base64, json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9421
F = os.path.join(D, '可爱样板-HTML', '可爱H-卡通图鉴.html')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*', '--user-data-dir=' + os.path.join(D, '_prof_dbgmk'),
    '--no-first-run', '--window-size=1330,720', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % PORT, timeout=2))
            pg = [t for t in tabs if t.get('type') == 'page']
            if pg:
                ws_url = pg[0]['webSocketDebuggerUrl']; break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(ws_url, timeout=120, http_proxy_host=None)
    _id = [0]

    def send(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': m, 'params': p or {}}))
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == _id[0]:
                return r.get('result', {})

    def ev(e):
        r = send('Runtime.evaluate', {'expression': e, 'returnByValue': True})
        if 'exceptionDetails' in r:
            return '__ERR__' + str(r['exceptionDetails'].get('text'))
        return r.get('result', {}).get('value')

    send('Page.enable')
    send('Emulation.setDeviceMetricsOverride',
         {'width': 1330, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})
    send('Page.navigate', {'url': 'file:///' + F.replace('\\', '/')})
    for _ in range(80):
        if ev("document.readyState==='complete' && !!document.getElementById('mkCute')"):
            break
        time.sleep(0.25)
    time.sleep(2.0)
    print('卡片清单 (宽×高 / 是否已挂 mkPic):')
    print(ev("""(function(){
      var cs=document.querySelectorAll('.card,.libList,.libDetail,.themePal');
      var o=[];
      for(var i=0;i<cs.length;i++){
        o.push([cs[i].className.slice(0,26), cs[i].offsetWidth, cs[i].offsetHeight,
                !!cs[i].querySelector(':scope > .mkPic')].join(' | '));
      }
      return o.join('\\n');
    })()"""))
    print('mkPic 总数:', ev("document.querySelectorAll('.mkPic').length"))
    print('手动执行挂载逻辑:')
    print(ev("""(function(){
      var cs=document.querySelectorAll('.card,.libList,.libDetail,.themePal');
      var n=0, tot=0;
      for(var i=0;i<cs.length;i++){
        tot++;
        if(cs[i].offsetWidth>=360 && cs[i].offsetHeight>=160) n++;
      }
      return '合格卡片 '+n+'/'+tot;
    })()"""))
finally:
    try:
        proc.terminate()
    except Exception:
        pass

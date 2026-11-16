# -*- coding: utf-8 -*-
"""修正版审计：用 DATA.maps 真实键选有地形的图，确认地形加载与昼夜对比度。"""
import json, os, subprocess, sys, time, urllib.request, base64
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9363
BASE = 'http://127.0.0.1:8791'
OUT = os.path.join(D, '验证截图-预览审计')
prof = os.path.join(OUT, '_prof2')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*', '--user-data-dir=' + prof, '--no-first-run',
    '--window-size=1600,1000', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % PORT, timeout=2))
            page = [t for t in tabs if t.get('type') == 'page']
            if page: ws_url = page[0]['webSocketDebuggerUrl']; break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(ws_url, timeout=120, http_proxy_host=None)
    _id = [0]
    def send(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': m, 'params': p or {}}))
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == _id[0]: return r.get('result', {})
    def ev(e, ap=False):
        r = send('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': ap})
        if 'exceptionDetails' in r: return '__ERR__ ' + str(r['exceptionDetails'].get('text'))
        return r.get('result', {}).get('value')

    send('Page.enable'); send('Runtime.enable')
    console = []

    def pump(sec):
        t0 = time.time()
        ws.settimeout(0.05)
        try:
            while time.time() - t0 < sec:
                try:
                    m = ws.recv()
                    j = json.loads(m)
                    if j.get('method') == 'Runtime.exceptionThrown':
                        d = j['params']['exceptionDetails']
                        console.append(str(d.get('exception', {}).get('description') or d.get('text'))[:160])
                except websocket.WebSocketTimeoutException:
                    pass
                except Exception:
                    pass
        finally:
            ws.settimeout(120)

    def shot(name):
        r = send('Page.captureScreenshot', {'format': 'png'})
        p = os.path.join(OUT, name)
        open(p, 'wb').write(base64.b64decode(r['data']))
        print('  截图 %s (%.0fKB)' % (name, os.path.getsize(p) / 1024))

    def terr_wait(wait=30):
        t0 = time.time()
        while time.time() - t0 < wait:
            pump(0.25)
            if ev("(function(){try{return GL3D.meshCount>0}catch(e){return false}})()"):
                return time.time() - t0
        return None

    print('=== 打开页面 ===')
    send('Page.navigate', {'url': BASE + '/preview3d'})
    for _ in range(240):
        pump(0.25)
        if ev("typeof DATA!=='undefined'&&!!DATA&&document.querySelectorAll('#lbody .li').length>0"):
            break
    pump(1)
    print('  默认图 wstat:', ev("document.getElementById('wstat').textContent"))

    # 选实体数最多的三张有地形的图
    keys = ev("""(function(){
      var a=Object.keys(DATA.maps).filter(function(k){
        return DATA.maps[k].wf && DATA.maps[k].wm && DATA.maps[k].es;});
      a.sort(function(x,y){return DATA.maps[y].es-DATA.maps[x].es;});
      return a.slice(0,6);})()""")
    print('  候选图:', keys)

    k0 = keys[0]
    ev("loadMap('%s')" % k0)
    dt = terr_wait()
    print('  %s 地形就绪 %s' % (k0, ('%.1fs' % dt) if dt else '超时未加载'))
    r = ev("""(function(){try{return {面:GL3D.meshCount, 实体:BOXES.length,
          wstat:document.getElementById('wstat').textContent}}catch(e){return 'ERR'}})()""")
    print('  状态:', r)
    pump(1.5)
    shot('b1-实体最多-浅色.png')

    ev("document.documentElement.setAttribute('data-theme','N')")
    pump(2)
    shot('b2-实体最多-夜幕.png')
    ev("document.documentElement.setAttribute('data-theme','E')")
    pump(1)

    # 视角拉近一点：切侧视 + fit
    if len(keys) > 2:
        ev("loadMap('%s')" % keys[2])
        dt2 = terr_wait()
        print('  %s 地形就绪 %s' % (keys[2], ('%.1fs' % dt2) if dt2 else '超时'))
        shot('b3-第三名-浅色.png')
        ev("document.documentElement.setAttribute('data-theme','N')")
        pump(2)
        shot('b4-第三名-夜幕.png')

    print('控制台异常: %d' % len(console))
    for c in console[:8]:
        print('   ', c)
finally:
    try: proc.kill()
    except Exception: pass
print('DONE')

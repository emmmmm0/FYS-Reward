# -*- coding: utf-8 -*-
"""3D 实体预览体检：实拍 + 性能 + 控制台错误。
输出截图到 验证截图-预览审计/，打印各项指标。"""
import json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9362
BASE = 'http://127.0.0.1:8791'
OUT = os.path.join(D, '验证截图-预览审计')
os.makedirs(OUT, exist_ok=True)
prof = os.path.join(OUT, '_prof')

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
    def on_msg(n, m):
        try:
            if m.get('method') == 'Runtime.exceptionThrown':
                console.append('EXC ' + json.dumps(m['params']['exceptionDetails'].get('exception', {}).get('description', ''))[:120])
        except Exception:
            pass

    def shot(name):
        r = send('Page.captureScreenshot', {'format': 'png'})
        p = os.path.join(OUT, name)
        open(p, 'wb').write(__import__('base64').b64decode(r['data']))
        print('  截图 %s (%.0fKB)' % (name, os.path.getsize(p) / 1024))

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
                        console.append(str(d.get('exception', {}).get('description') or d.get('text'))[:140])
                except websocket.WebSocketTimeoutException:
                    pass
                except Exception:
                    pass
        finally:
            ws.settimeout(120)

    def load_map(mid, theme, wait=25):
        ev("document.documentElement.setAttribute('data-theme','%s')" % theme)
        ev("loadMap('%s')" % mid)
        t0 = time.time()
        for _ in range(int(wait * 4)):
            pump(0.25)
            if ev("(function(){try{return GL3D.meshCount>0}catch(e){return false}})()"):
                break
        dt = time.time() - t0
        pump(1.5)
        return dt

    print('=== 打开预览页（默认图） ===')
    t_nav = time.time()
    send('Page.navigate', {'url': BASE + '/preview3d'})
    for _ in range(240):
        pump(0.25)
        if ev("typeof DATA!=='undefined'&&!!DATA&&document.querySelectorAll('#lbody .li').length>0"):
            break
    print('  页面+数据就绪 %.1fs' % (time.time() - t_nav))
    dt = load_map('3220221743', 'E')
    print('  大图 3D 就绪 %.1fs' % dt)
    pump(1)

    # FPS：钩 rAF 数 2 秒
    fps = ev("""(function(){return new Promise(function(res){
      var n=0, t0=performance.now();
      function f(){ n++; if(performance.now()-t0<2000) requestAnimationFrame(f); else res(+(n/2).toFixed(0)); }
      requestAnimationFrame(f); })})()""", ap=True)
    pump(2.5)
    print('  rAF 帧率(2s 平均): %s' % fps)

    # draw calls（单帧钩子）
    dc = ev("""(function(){try{
      var gl=document.getElementById('cv3').getContext('webgl2');
      var n=0, old=gl.drawElements.bind(gl), old2=gl.drawArrays.bind(gl);
      gl.drawElements=function(){n++;return old.apply(null,arguments)};
      gl.drawArrays=function(){n++;return old2.apply(null,arguments)};
      render3D(); gl.drawElements=old; gl.drawArrays=old2;
      return n; }catch(e){return 'ERR '+e.message}})()""")
    print('  单帧 draw calls: %s' % dc)

    r = ev("""(function(){try{
      return {地形面:GL3D.meshCount, 实体数:BOXES.length+(cur.pts||[]).length,
              主题:getComputedStyle(document.body).getPropertyValue('--accent').trim(),
              canvas:document.getElementById('cv3').width+'x'+document.getElementById('cv3').height,
              dpr:(window.devicePixelRatio||1)}}catch(e){return 'ERR '+e.message}})()""")
    print('  状态: %s' % r)
    shot('a1-大图-奶油草莓.png')

    print('=== 夜幕主题同图 ===')
    load_map('3220221743', 'N')
    shot('a2-大图-夜幕.png')

    print('=== 中位图 + 小图 ===')
    dt2 = load_map('3561455176', 'E')
    print('  中位图 3D 就绪 %.1fs' % dt2)
    shot('a3-中位图-奶油草莓.png')
    dt3 = load_map('3162998843', 'E')
    print('  小图 3D 就绪 %.1fs' % dt3)
    shot('a4-小图-奶油草莓.png')

    print('=== 2D 平面模式 ===')
    ev("setMode('2d')")
    pump(1.5)
    shot('a5-平面模式.png')

    print('=== 剖切 + 光晕 ===')
    ev("setMode('3d')")
    ev("(function(){document.getElementById('cutz').value=55;document.getElementById('cutz').dispatchEvent(new Event('input'))})()")
    pump(1.5)
    shot('a6-顶部剖切55.png')
    ev("(function(){document.getElementById('cutz').value=100;document.getElementById('cutz').dispatchEvent(new Event('input'))})()")
    ev("(function(){document.getElementById('glow').checked=true;document.getElementById('glow').dispatchEvent(new Event('change'))})()")
    pump(1.5)
    shot('a7-区域光晕.png')

    print('=== 控制台异常 (%d) ===' % len(console))
    for c in console[:10]:
        print('   ', c)
finally:
    try: proc.kill()
    except Exception: pass
print('DONE')

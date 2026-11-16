# -*- coding: utf-8 -*-
"""截图：预览页 3D 悬停提示 + 整体 3D 视图（修复后确认）"""
import base64, json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
OUT = os.path.join(D, '验证截图-界面巡检')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9361
BASE = 'http://127.0.0.1:%s' % (sys.argv[1] if len(sys.argv) > 1 else '8791')
prof = os.path.join(OUT, '_prof_shotpv')

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
    ws = websocket.create_connection(ws_url, timeout=90, http_proxy_host=None)
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
    def snap(path):
        d = send('Page.captureScreenshot', {'format': 'png'})
        open(path, 'wb').write(base64.b64decode(d['data']))
        print('  saved', os.path.basename(path), os.path.getsize(path) // 1024, 'KB')

    send('Page.enable')
    send('Emulation.setDeviceMetricsOverride',
         {'width': 1330, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})
    send('Page.navigate', {'url': BASE + '/preview3d?map=ze_pizza_cookie'})
    for _ in range(90):
        if ev("typeof DATA!=='undefined'&&!!DATA&&document.querySelectorAll('#lbody .li').length>0"):
            break
        time.sleep(0.25)
    for _ in range(80):
        if ev("(function(){try{return GL3D.meshCount>0}catch(e){return false}})()"):
            break
        time.sleep(0.25)
    time.sleep(2.5)

    print('整窗 3D 视图（修复后应一切正常）')
    snap(os.path.join(OUT, '预览优化01-3D视图正常.png'))

    print('3D 悬停提示：把鼠标移到实体上')
    pos = ev("""(function(){try{
      var vp=camVP().vp, W2=document.getElementById('cv3').clientWidth,
          H2=document.getElementById('cv3').clientHeight;
      var best=null, bd=1e18;
      for(var i=0;i<BOXES.length;i++){
        var b=BOXES[i], p=projPt(vp,b.x,b.y,b.z); if(!p) continue;
        if(p[0]<60||p[1]<60||p[0]>W2-60||p[1]>H2-80) continue;
        var d=Math.hypot(p[0]-W2/2,p[1]-H2/2);
        if(d<bd){ bd=d; best={sx:p[0],sy:p[1],cn:(b.o&&b.o.cn)||'?'}; }
      }
      return best;
    }catch(e){return 'ERR '+e.message}})()""")
    print('  目标实体:', pos)
    rs = ev("(function(){var r=document.getElementById('stage').getBoundingClientRect();"
            "return {l:r.left,t:r.top};})()")
    cx = rs['l'] + pos['sx']; cy = rs['t'] + pos['sy']
    # 真实鼠标移动（CDP 输入事件，更接近用户操作）
    send('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': int(cx), 'y': int(cy),
                                      'button': 'none', 'buttons': 0})
    time.sleep(0.8)
    # 再补一次页面内 pointermove，确保节流窗口被触发
    ev("""document.getElementById('cv3').dispatchEvent(new PointerEvent('pointermove',
         {bubbles:true, clientX:%d, clientY:%d, pointerId:1}))""" % (cx, cy))
    time.sleep(0.6)
    tip = ev("(function(){var t=document.getElementById('tip');"
             "return {disp:getComputedStyle(t).display, txt:t.textContent.slice(0,60)};})()")
    print('  气泡状态:', tip)
    snap(os.path.join(OUT, '预览优化02-3D悬停提示.png'))

    print('切一张大地图 + 展开图层细类')
    big = ev("Object.keys(DATA.maps).sort(function(a,b){return DATA.maps[b].n-DATA.maps[a].n})[0]")
    ev("loadMap('%s')" % big); time.sleep(5)
    ev("(function(){var x=document.querySelector('#lbody .xbtn'); if(x) x.click();})()")
    time.sleep(1.0)
    snap(os.path.join(OUT, '预览优化03-最大图与细类.png'))
    print('  最大图:', ev("cur.m.cn"), '实体', ev("cur.m.n"), '块体', ev("BOXES.length"))
finally:
    try: proc.terminate()
    except Exception: pass
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

# -*- coding: utf-8 -*-
"""地图实体预览 · 补充验证（重复请求 / 内存线性 / setMesh 耗时）"""
import json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9356
BASE = 'http://127.0.0.1:%s' % (sys.argv[1] if len(sys.argv) > 1 else '8791')
prof = os.path.join(D, '验证截图-界面巡检', '_prof_diag2')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*', '--enable-precise-memory-info',
    '--user-data-dir=' + prof, '--no-first-run', '--window-size=1600,1000',
    'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % PORT, timeout=2))
            page = [t for t in tabs if t.get('type') == 'page']
            if page:
                ws_url = page[0]['webSocketDebuggerUrl']; break
        except Exception:
            time.sleep(0.5)
    if not ws_url:
        raise SystemExit('CDP 没连上')
    ws = websocket.create_connection(ws_url, timeout=90, http_proxy_host=None)
    _id = [0]
    def send(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': m, 'params': p or {}}))
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == _id[0]:
                return r.get('result', {})
    def ev(e, ap=False):
        r = send('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': ap})
        if 'exceptionDetails' in r:
            return '__ERR__ ' + str(r['exceptionDetails'].get('text'))
        return r.get('result', {}).get('value')

    send('Page.enable')
    send('Page.navigate', {'url': BASE + '/preview3d?map=ze_pizza_cookie'})
    for _ in range(90):
        if ev("typeof DATA!=='undefined'&&!!DATA&&document.querySelectorAll('#lbody .li').length>0"):
            break
        time.sleep(0.25)
    for _ in range(60):
        if ev("GL3D.meshCount>0"):
            break
        time.sleep(0.25)
    print('=' * 70)
    print('[A] 地形 .bin 请求次数（切换一张新图，观察是否有重复下载）')
    keys = ev("Object.keys(DATA.maps).filter(function(k){return DATA.maps[k].wf && DATA.maps[k].wm})")
    print('  可用带地形地图数: %d' % len(keys))
    for k in keys[1:4]:
        ev("performance.clearResourceTimings()")
        ev("loadMap('%s')" % k)
        time.sleep(6)
        hits = ev("performance.getEntriesByType('resource').filter(function(r){"
                  "return /terr\\//.test(r.name)}).map(function(r){"
                  "return r.name.split('/').pop()+':'+Math.round(r.duration)+'ms/'+(r.transferSize||0)+'B'})")
        print('  %-46s → %s' % (k.split('/')[-1][:44], hits))

    print('\n[B] 内存随切图数量的变化（TERR 缓存无上限）')
    ev("loadMap('ze_pizza_cookie')"); time.sleep(1)
    print('  起始 heap: %s MB' % ev("Math.round(performance.memory.usedJSHeapSize/1048576)"))
    for i, k in enumerate(keys[1:21]):
        ev("loadMap('%s')" % k)
        time.sleep(1.2)
        if (i + 1) % 5 == 0:
            m = ev("""(function(){try{return {切图数:%d, terr条目:Object.keys(TERR).length,
                terrMB:+(Object.keys(TERR).reduce(function(a,k){return a+TERR[k].length},0)/1048576).toFixed(1),
                meshCache:meshCache.size,
                heapMB:Math.round(performance.memory.usedJSHeapSize/1048576)}}catch(e){return 'ERR '+e.message}})()""" % (i + 1))
            print('  ' + json.dumps(m, ensure_ascii=False))

    print('\n[C] setMesh 展开耗时（72000 面刷新场景时的单次成本）')
    st = ev("""(function(){try{
      var k = cur.__k, e = meshCache.get(k); if(!e) return 'no-cache';
      var t = performance.now();
      GL3D.setMesh(e.verts, e.idxs, e.o.map(function(x){return x*M2M}), e.s.map(function(x){return x*M2M}), e.nt);
      return {faces:e.nt, ms:+(performance.now()-t).toFixed(1)};
    }catch(err){return 'ERR '+err.message}})()""")
    print('  %s' % json.dumps(st, ensure_ascii=False))

    print('\n[D] 每帧新建的 GPU 缓冲（drawGrid 每次 render3D 重新构造）')
    dg = ev("""(function(){try{
      var cv=document.getElementById('cv3');
      var gl=cv.getContext('webgl2');
      var n=0, old=gl.bufferData.bind(gl);
      gl.bufferData=function(){ n++; return old.apply(null,arguments); };
      for(var i=0;i<30;i++) render3D();
      gl.bufferData=old; return {每帧bufferData次数:+(n/30).toFixed(2)};
    }catch(e){return 'ERR '+e.message}})()""")
    print('  %s' % json.dumps(dg, ensure_ascii=False))

    print('\n[E] 3D 画布导出 PNG 是否有内容')
    png = ev("""(function(){try{
      var u=document.getElementById('cv3').toDataURL('image/png');
      return {len:u.length, head:u.slice(0,22)};
    }catch(e){return 'ERR '+e.message}})()""")
    print('  %s' % json.dumps(png, ensure_ascii=False))

    print('\n[F] 3D 画布是否绑定了悬停/鼠标移动提示')
    hv = ev("""(function(){try{
      return {cv3有pointermove: !!window.__cv3move, 提示元素tip: !!document.getElementById('tip'),
              3D视角面板元素: !!document.getElementById('v3info')};
    }catch(e){return 'ERR '+e.message}})()""")
    print('  %s' % json.dumps(hv, ensure_ascii=False))
finally:
    try: proc.terminate()
    except Exception: pass
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

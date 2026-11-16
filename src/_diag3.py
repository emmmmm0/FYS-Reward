# -*- coding: utf-8 -*-
"""地图实体预览 · 补充验证 3（首载重复请求 / 3D 下的按钮一致性 / setMesh 成本）"""
import json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9357
BASE = 'http://127.0.0.1:%s' % (sys.argv[1] if len(sys.argv) > 1 else '8791')
prof = os.path.join(D, '验证截图-界面巡检', '_prof_diag3')

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

    send('Page.enable')
    print('=' * 70)
    print('[G] 首次进入预览页（全新会话）时地形 .bin 的请求次数')
    send('Page.navigate', {'url': BASE + '/preview3d'})
    for _ in range(90):
        if ev("typeof DATA!=='undefined'&&!!DATA&&document.querySelectorAll('#lbody .li').length>0"):
            break
        time.sleep(0.25)
    time.sleep(6)
    hits = ev("performance.getEntriesByType('resource').filter(function(r){"
              "return /terr\\//.test(r.name)}).map(function(r){"
              "return r.name.split('/').pop()+'  '+Math.round(r.duration)+'ms  '+(r.transferSize||0)+'B'})")
    print('  请求数=%d' % len(hits or []))
    for h in (hits or []): print('    ' + h)
    print('  （>1 条同名 = 并发重复下载，浪费带宽与一次额外解压）')

    print('\n[H] 3D 模式下「适应窗口」按钮的实际效果')
    r = ev("""(function(){try{
      var b=document.getElementById('fit');
      var vis = getComputedStyle(b).display;
      var before={dist:CAM.dist, tx:CAM.tx, ty:CAM.ty, tz:CAM.tz};
      b.click();
      var after={dist:CAM.dist, tx:CAM.tx, ty:CAM.ty, tz:CAM.tz};
      return {按钮可见:vis, 点击前:before, 点击后:after,
              是否改变: JSON.stringify(before)!==JSON.stringify(after)};
    }catch(e){return 'ERR '+e.message}})()""")
    print('  %s' % json.dumps(r, ensure_ascii=False))
    print('  （3D 下若为 false = 点了没反应；3D 的等效操作是 R 键复位）')

    print('\n[I] 3D 视图里的 HUD 元素可见性')
    r = ev("""(function(){try{var o={};
      ['north','sbline','zoomlab'].forEach(function(id){
        var e=document.getElementById(id);
        o[id]= e? (e.offsetParent!==null) : null;});
      o['v3info_text']=document.getElementById('v3info').textContent.slice(0,60);
      return o;
    }catch(e){return 'ERR '+e.message}})()""")
    print('  %s' % json.dumps(r, ensure_ascii=False))

    print('\n[J] 3D 画布监听器（是否有悬停 tooltip）')
    r = ev("""(function(){try{
      var cv=document.getElementById('cv3');
      return {有wheel:true, 提示元素tipDisplay:getComputedStyle(document.getElementById('tip')).display,
              tip绑定在2D画布上: true};
    }catch(e){return 'ERR '+e.message}})()""")
    print('  %s' % json.dumps(r, ensure_ascii=False))

    print('\n[K] setMesh 展开成本（当前图）')
    r = ev("""(function(){try{
      var k=S.key, e=meshCache.get(k);
      if(!e) return {cache:'miss', keys:[S.key].concat(Array.from(meshCache.keys()).slice(0,3))};
      var t=performance.now();
      GL3D.setMesh(e.verts, e.idxs, e.o.map(function(x){return x*M2M}), e.s.map(function(x){return x*M2M}), e.nt);
      return {面数:e.nt, ms:+(performance.now()-t).toFixed(1)};
    }catch(err){return 'ERR '+err.message}})()""")
    print('  %s' % json.dumps(r, ensure_ascii=False))

    print('\n[L] 大图对比：地图库中实体最多的图，场景规模与点选成本')
    r = ev("""(function(){try{
      var ks=Object.keys(DATA.maps).sort(function(a,b){return DATA.maps[b].n-DATA.maps[a].n}).slice(0,5);
      return ks.map(function(k){return DATA.maps[k].m+' / '+DATA.maps[k].n+' 实体';});
    }catch(e){return 'ERR '+e.message}})()""")
    print('  Top5 实体数: %s' % r)
    k0 = ev("Object.keys(DATA.maps).sort(function(a,b){return DATA.maps[b].n-DATA.maps[a].n})[0]")
    ev("loadMap('%s')" % k0); time.sleep(5)
    r = ev("""(function(){try{
      var t=performance.now();
      for(var i=0;i<20;i++) pick3({clientX:700,clientY:400});
      return {map:cur.m.cn, 实体:cur.m.n, 块体:BOXES.length, 点:cur.pts.length,
              点选单次ms:+((performance.now()-t)/20).toFixed(1)};
    }catch(e){return 'ERR '+e.message}})()""")
    print('  %s' % json.dumps(r, ensure_ascii=False))
finally:
    try: proc.terminate()
    except Exception: pass
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

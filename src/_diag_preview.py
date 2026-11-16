# -*- coding: utf-8 -*-
"""地图实体预览 · 性能与体验诊断（一次性脚本，跑完可删）
用法: python _diag_preview.py <端口>
"""
import json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9355
BASE = 'http://127.0.0.1:%s' % (sys.argv[1] if len(sys.argv) > 1 else '8791')
prof = os.path.join(D, '验证截图-界面巡检', '_prof_diag')

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

    def send(method, params=None):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': method, 'params': params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == _id[0]:
                return msg.get('result', {})

    def ev(expr, ap=False):
        r = send('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                      'awaitPromise': ap})
        if 'exceptionDetails' in r:
            return '__ERR__: ' + str(r['exceptionDetails'].get('text'))
        return r.get('result', {}).get('value')

    send('Page.enable')
    send('Runtime.enable')
    send('Log.enable')

    errs = []
    def pump(sec):
        """收集一段时间内的控制台错误"""
        end = time.time() + sec
        ws.settimeout(0.3)
        while time.time() < end:
            try:
                msg = json.loads(ws.recv())
            except Exception:
                continue
            m = msg.get('method')
            if m == 'Runtime.exceptionThrown':
                errs.append('EXC ' + str(msg['params']['exceptionDetails'].get('text'))[:120])
            elif m == 'Log.entryAdded':
                e = msg['params']['entry']
                if e.get('level') in ('error', 'warning'):
                    errs.append('%s %s' % (e['level'].upper(), str(e.get('text'))[:120]))
        ws.settimeout(90)

    print('=' * 72)
    print('地图实体预览 · 诊断报告')
    print('=' * 72)

    # ── [1] 首屏加载耗时 ──
    t0 = time.time()
    send('Page.navigate', {'url': BASE + '/preview3d?map=ze_pizza_cookie'})
    ready_at = None
    for _ in range(90):
        if ev("typeof DATA!=='undefined' && !!DATA && document.querySelectorAll('#lbody .li').length>0"):
            ready_at = time.time() - t0
            break
        time.sleep(0.25)
    # 等地形加载完
    terr_at = None
    for _ in range(120):
        if ev("(function(){try{return !!(window.GL3D&&GL3D.meshCount)}catch(e){return false}})()"):
            terr_at = time.time() - t0
            break
        time.sleep(0.25)
    print('\n[1] 首屏')
    print('  数据就绪(图层可交互) : %.2fs' % (ready_at or -1))
    print('  地形网格就绪         : %.2fs' % (terr_at or -1))
    nav = ev("(function(){var n=performance.getEntriesByType('navigation')[0];"
             "return n?[Math.round(n.domContentLoadedEventEnd),Math.round(n.loadEventEnd),"
             "Math.round(n.transferSize),Math.round(n.decodedBodySize)]:null})()")
    print('  DOMContentLoaded/load / 传输字节 / 解码字节 : %s' % nav)
    res = ev("performance.getEntriesByType('resource').filter(function(r){"
             "return /terr|preview3d/.test(r.name)}).map(function(r){"
             "return [r.name.split('/').pop(), Math.round(r.duration), r.transferSize||0, r.decodedBodySize||0]})")
    print('  资源明细 (文件名 / 耗时ms / 传输B / 解码B):')
    for r in (res or []):
        print('    %-28s %6d ms   %8d   %8d' % tuple(r))

    # ── [2] 场景规模 ──
    print('\n[2] 场景规模（默认图 ze_pizza_cookie）')
    sc = ev("""(function(){try{
      return {map:cur.m.cn, ents:cur.m.n, pts:cur.pts.length, boxes:BOXES.length,
              ptpick:PTPICK.length, meshFaces:(GL3D.meshCount||0),
              spanM:Math.round(cur.span*2.54/100), groups:Object.keys(cur.groups).length,
              cnTotal:Object.keys(cur.cncnt||{}).reduce(function(a,g){return a+Object.keys(cur.cncnt[g]).length},0),
              terrCached:Object.keys(TERR).length, meshCached:meshCache.size,
              heap:Math.round((performance.memory?performance.memory.usedJSHeapSize:0)/1048576)};
    }catch(e){return 'ERR '+e.message}})()""")
    print('  ' + json.dumps(sc, ensure_ascii=False))

    # ── [3] 渲染开销 ──
    print('\n[3] 渲染开销')
    if ev("!!document.getElementById('cv3').getContext('webgl2')"):
        r3 = ev("""(function(){try{
          var gl=document.getElementById('cv3').getContext('webgl2');
          var t=performance.now();
          for(var i=0;i<40;i++){ render3D(); gl.finish(); }
          return +( (performance.now()-t)/40 ).toFixed(2);
        }catch(e){return 'ERR '+e.message}})()""")
        print('  render3D 单帧（含 gl.finish 同步）: %s ms  → 理论 %.0f fps' %
              (r3, 1000.0 / r3 if isinstance(r3, (int, float)) and r3 else 0))
        b3 = ev("""(function(){try{
          var t=performance.now(); for(var i=0;i<8;i++) build3D();
          return +((performance.now()-t)/8).toFixed(2);
        }catch(e){return 'ERR '+e.message}})()""")
        print('  build3D 重建场景（切图层时调用）: %s ms' % b3)
        pk = ev("""(function(){try{
          var t=performance.now();
          for(var i=0;i<30;i++) pick3({clientX:700,clientY:400});
          return +((performance.now()-t)/30).toFixed(2);
        }catch(e){return 'ERR '+e.message}})()""")
        print('  pick3 点选一次（遍历全部块体）   : %s ms' % pk)
    rz = ev("""(function(){try{
      var t=performance.now(); for(var i=0;i<40;i++) resize();
      return +((performance.now()-t)/40).toFixed(2);
    }catch(e){return 'ERR '+e.message}})()""")
    print('  resize 一次                      : %s ms' % rz)

    # ── [4] 拖动渲染频率（是否存在 pointermove 直驱重绘）──
    print('\n[4] 拖动时的渲染次数（判断是否有 rAF 节流）')
    drag = ev("""(function(){try{
      var cv=document.getElementById('cv3');
      window.__rc=0; var _r=window.render3D;
      window.render3D=function(){ window.__rc++; return _r.apply(null,arguments); };
      /* 同时覆盖内部引用：render3D 在模块作用域被直接调用，包 window 无效——用计数法监听 gl 绘制 */
      return 'patched';
    }catch(e){return 'ERR '+e.message}})()""")
    print('  （见下方 [4b] 帧率采样）')

    # ── [5] 自由视角持续帧率 ──
    print('\n[5] 持续渲染帧率')
    fps = ev("""(function(){return new Promise(function(res){
      try{
        setFree(true);
        var gl=document.getElementById('cv3').getContext('webgl2');
        var n=0, t0=performance.now();
        function step(){
          render3D(); gl.finish(); n++;
          if(performance.now()-t0 < 2000) requestAnimationFrame(step);
          else { setFree(false); res(+(n/((performance.now()-t0)/1000)).toFixed(1)); }
        }
        requestAnimationFrame(step);
      }catch(e){ res('ERR '+e.message); }
    })})()""", ap=True)
    print('  自由视角持续渲染 : %s fps' % fps)

    # ── [6] 切换地图后的缓存累积（潜在内存增长）──
    print('\n[6] 连续切图 8 张后的缓存累积')
    keys = ev("Object.keys(DATA.maps).filter(function(k){return DATA.maps[k].wf}).slice(0,8)")
    print('  测试地图: %s' % keys)
    for k in keys:
        ev("loadMap('%s')" % k)
        time.sleep(0.25)
    time.sleep(4)
    mem = ev("""(function(){try{return {
      terrCached:Object.keys(TERR).length,
      terrBytes:Math.round(Object.keys(TERR).reduce(function(a,k){return a+TERR[k].length},0)/1048576),
      meshCached:meshCache.size,
      heapMB:Math.round((performance.memory?performance.memory.usedJSHeapSize:0)/1048576)
    }}catch(e){return 'ERR '+e.message}})()""")
    print('  ' + json.dumps(mem, ensure_ascii=False))
    print('  ※ TERR 缓存无上限：每张地形原始 gz 字节常驻内存')

    # ── [7] 交互走查 ──
    print('\n[7] 交互走查')
    ev("loadMap('ze_pizza_cookie')"); time.sleep(0.5)
    # 7a 实体搜索
    ev("$('esq').value='trigger_hurt'; esRender()"); time.sleep(0.4)
    hits = ev("($('esres').__hits||[]).length")
    print('  实体搜索 trigger_hurt 命中数 : %s' % hits)
    # 7b 图层细类展开
    ev("""(function(){var x=document.querySelector('#lbody .xbtn'); if(x) x.click();})()""")
    time.sleep(0.3)
    print('  图层细类子行数 : %s' % ev("document.querySelectorAll('#lbody .subs .si').length"))
    # 7c 搜索框过滤地图
    ev("(function(){var q=$('q'); q.value='ze_'; q.dispatchEvent(new Event('input'));})()")
    time.sleep(0.4)
    print('  地图搜索 ze_ 后列表行数 : %s / 总数 %s' %
          (ev("document.querySelectorAll('#maps .mi').length"), ev("MAPKEYS.length")))
    ev("(function(){var q=$('q'); q.value=''; q.dispatchEvent(new Event('input'));})()")
    # 7d 3D → 2D 切换
    ev("setMode('2d')"); time.sleep(0.4)
    d2 = ev("(function(){try{draw(); return 'ok'}catch(e){return 'ERR '+e.message}})()")
    ev("setMode('3d')"); time.sleep(0.4)
    print('  2D 平面视图渲染 : %s' % d2)
    # 7e 剖切
    ev("(function(){var c=$('cutz'); c.value='60'; c.dispatchEvent(new Event('input'));})()")
    time.sleep(0.3)
    print('  顶部剖切 60%% 生效 : %s' % ev("S.cutz"))

    pump(2)
    print('\n[8] 控制台错误/警告 (%d 条)' % len(errs))
    for e in errs[:14]:
        print('   ' + e)

finally:
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# -*- coding: utf-8 -*-
"""修复验证：重复下载 / TERR 上限 / 网格缓存 / 3D 悬停提示"""
import json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9360
BASE = 'http://127.0.0.1:%s' % (sys.argv[1] if len(sys.argv) > 1 else '8791')
prof = os.path.join(D, '验证截图-界面巡检', '_prof_diag5')

PASS, FAIL = [], []
def check(name, ok, extra=''):
    (PASS if ok else FAIL).append(name)
    print('  %s %s%s' % ('✓' if ok else '✗', name, ('  → ' + str(extra)) if extra else ''))

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

    send('Page.enable'); send('Runtime.enable'); send('Log.enable')
    errs = []
    send('Page.navigate', {'url': BASE + '/preview3d'})
    for _ in range(90):
        if ev("typeof DATA!=='undefined'&&!!DATA&&document.querySelectorAll('#lbody .li').length>0"):
            break
        time.sleep(0.25)
    for _ in range(80):
        if ev("(function(){try{return GL3D.meshCount>0}catch(e){return false}})()"):
            break
        time.sleep(0.25)
    time.sleep(2)

    print('\n[1] 首次进入：地形 .bin 请求次数（修复前 = 2）')
    hits = ev("performance.getEntriesByType('resource').filter(function(r){"
              "return /\\.bin$/.test(r.name)}).map(function(r){return r.name.split('/').pop()})")
    check('同名 .bin 只请求一次', len(hits or []) == 1, hits)

    print('\n[2] 地形缓存改用 Map + 上限')
    r = ev("""(function(){try{return {是Map: TERR instanceof Map, 上限: TERR_MAX,
           条目: TERR.size, 地形面数: GL3D.meshCount}}catch(e){return 'ERR '+e.message}})()""")
    check('TERR 是 Map 且有上限 12', isinstance(r, dict) and r.get('是Map') and r.get('上限') == 12, r)
    check('地形正常加载（面数 > 0）', isinstance(r, dict) and (r.get('地形面数') or 0) > 0, r)

    print('\n[3] 切 20 张图后 TERR 不超过上限')
    keys = ev("Object.keys(DATA.maps).filter(function(k){return DATA.maps[k].wf && DATA.maps[k].wm})")
    for k in keys[1:21]:
        ev("loadMap('%s')" % k); time.sleep(1.0)
    r = ev("""(function(){try{return {terr:TERR.size, mesh:meshCache.size,
      terrMB:+(Array.from(TERR.values()).reduce(function(a,v){return a+v.length},0)/1048576).toFixed(1)}}catch(e){return 'ERR '+e.message}})()""")
    check('TERR 条目 <= 12', isinstance(r, dict) and r.get('terr') <= 12, r)
    check('meshCache 条目 <= 5', isinstance(r, dict) and r.get('mesh') <= 5, r)

    print('\n[4] 地面网格几何缓存（修复前每帧 2 次 bufferData）')
    ev("loadMap('ze_pizza_cookie')"); time.sleep(3)
    r = ev("""(function(){try{
      render3D();                                   // 预热：首帧会重建并上传网格几何，不计入
      var gl=document.getElementById('cv3').getContext('webgl2');
      var n=0, old=gl.bufferData.bind(gl);
      gl.bufferData=function(){ n++; return old.apply(null,arguments); };
      for(var i=0;i<30;i++) render3D();
      gl.bufferData=old; return {每帧bufferData:+(n/30).toFixed(2)};
    }catch(e){return 'ERR '+e.message}})()""")
    check('静止时 render3D 不再重传网格缓冲', isinstance(r, dict) and r.get('每帧bufferData') == 0, r)

    print('\n[5] 3D 悬停提示')
    # 先取一个实体在屏幕上的位置（用投影找屏幕中心的实体）
    pos = ev("""(function(){try{
      var vp=camVP().vp, W2=document.getElementById('cv3').clientWidth,
          H2=document.getElementById('cv3').clientHeight;
      var best=null, bd=1e18;
      for(var i=0;i<BOXES.length;i++){
        var b=BOXES[i], p=projPt(vp,b.x,b.y,b.z); if(!p) continue;
        if(p[0]<40||p[1]<40||p[0]>W2-40||p[1]>H2-40) continue;
        var d=Math.hypot(p[0]-W2/2,p[1]-H2/2);
        if(d<bd){ bd=d; best={sx:p[0],sy:p[1],cn:b.o?b.o.cn:null}; }
      }
      return best;
    }catch(e){return 'ERR '+e.message}})()""")
    print('  目标实体屏幕位置: %s' % pos)
    if isinstance(pos, dict):
        rs = ev("(function(){var r=document.getElementById('stage').getBoundingClientRect();"
                "return {l:r.left,t:r.top};})()")
        cx = rs['l'] + pos['sx']; cy = rs['t'] + pos['sy']
        ev("""(function(){
          var cv=document.getElementById('cv3');
          cv.dispatchEvent(new PointerEvent('pointermove', {bubbles:true, clientX:%f, clientY:%f, pointerId:1}));
        })()""" % (cx, cy))
        time.sleep(0.6)
        tip = ev("(function(){var t=document.getElementById('tip');"
                 "return {disp:getComputedStyle(t).display, txt:t.textContent.slice(0,70)};})()")
        check('划过实体后气泡出现', isinstance(tip, dict) and tip.get('disp') == 'block', tip)
        check('气泡内容含类别', isinstance(tip, dict) and '类别' in (tip.get('txt') or ''), tip)
        # 移到空白处
        ev("""document.getElementById('cv3').dispatchEvent(new PointerEvent('pointermove',
             {bubbles:true, clientX:12, clientY:12, pointerId:1}))""")
        time.sleep(0.6)
        t2 = ev("getComputedStyle(document.getElementById('tip')).display")
        check('移到空白处气泡收起', t2 == 'none', t2)
        # 拖动中不应弹气泡
        ev("""(function(){var cv=document.getElementById('cv3');
          cv.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:%f,clientY:%f,pointerId:1,button:0}));
          cv.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:%f,clientY:%f,pointerId:1}));
        })()""" % (cx, cy, cx + 30, cy + 20))
        time.sleep(0.5)
        d3 = ev("""(function(){var cv=document.getElementById('cv3');
          cv.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,clientX:%f,clientY:%f,pointerId:1}));
          return getComputedStyle(document.getElementById('tip')).display;})()""" % (cx + 30, cy + 20))
        check('拖动中不弹气泡', d3 == 'none', d3)
    else:
        check('能定位到可拾取实体', False, pos)

    print('\n[6] 点选仍然正常（拆成 pick3At + pick3）')
    st = ev("""(function(){try{
      var vp=camVP().vp, r=document.getElementById('cv3').getBoundingClientRect();
      var b=BOXES[0]; for(var i=0;i<BOXES.length;i++){
        var p=projPt(vp,BOXES[i].x,BOXES[i].y,BOXES[i].z);
        if(p&&p[0]>20&&p[1]>20&&p[0]<800&&p[1]<600){ b=BOXES[i]; break; } }
      var p=projPt(vp,b.x,b.y,b.z);
      pick3({clientX:r.left+p[0], clientY:r.top+p[1]});
      return {选中:S.sel?S.sel.cn:null, 详情卡:getComputedStyle(document.getElementById('edetail')).display};
    }catch(e){return 'ERR '+e.message}})()""")
    check('点击块体仍能选中并弹详情卡',
          isinstance(st, dict) and st.get('选中') and st.get('详情卡') == 'block', st)

    print('\n[7] 2D 悬停气泡（重构后不应回归）')
    ev("setMode('2d')"); time.sleep(1.2)
    r = ev("""(function(){try{
      var cv=document.getElementById('cv');
      var r=cv.getBoundingClientRect();
      var o=cur.pts[0];
      hover({clientX:r.left+o.px*view.s+view.ox, clientY:r.top+o.py*view.s+view.oy});
      var t=document.getElementById('tip');
      return {disp:getComputedStyle(t).display, txt:t.textContent.slice(0,50)};
    }catch(e){return 'ERR '+e.message}})()""")
    check('2D 悬停气泡仍正常', isinstance(r, dict) and r.get('disp') == 'block', r)
    ev("setMode('3d')"); time.sleep(1)

    print('\n[8] 控制台错误')
    try:
        ws.settimeout(0.4); end = time.time() + 2
        while time.time() < end:
            try: msg = json.loads(ws.recv())
            except Exception: continue
            if msg.get('method') == 'Runtime.exceptionThrown':
                errs.append(str(msg['params']['exceptionDetails'].get('text'))[:110])
            elif msg.get('method') == 'Log.entryAdded':
                e = msg['params']['entry']
                if e.get('level') == 'error': errs.append(str(e.get('text'))[:110])
        ws.settimeout(90)
    except Exception: pass
    check('无未捕获异常 / error 日志', not errs, errs[:4])

    print('\n' + '=' * 60)
    print('通过 %d 项，失败 %d 项' % (len(PASS), len(FAIL)))
    for f in FAIL: print('  ✗ ' + f)
finally:
    try: proc.terminate()
    except Exception: pass
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

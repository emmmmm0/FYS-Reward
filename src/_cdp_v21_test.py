# -*- coding: utf-8 -*-
"""v2.1 三项美化验证：① 地形/雾主题化 ② 2D 底图灰度+对比拉伸 ③ 顶栏「⋯ 更多」收纳"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
SHOT = os.path.join(D, '验证截图-预览审计')
os.makedirs(SHOT, exist_ok=True)
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9372
BASE = 'http://127.0.0.1:%s' % (sys.argv[1] if len(sys.argv) > 1 else '8791')
prof = os.path.join(D, '验证截图-界面巡检', '_prof_diag6')

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
    def shot(name):
        b = send('Page.captureScreenshot', {'format': 'png'})['data']
        open(os.path.join(SHOT, name), 'wb').write(base64.b64decode(b))
        print('  📸 ' + name)

    send('Page.enable'); send('Runtime.enable')
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

    print('\n[A] 地形/雾主题化')
    r = ev("""(function(){try{return {themes:Object.keys(TERR_THEMES), cur:TERR3D.base,
      fog:CAM.fog.slice(), hook:typeof window.__p3dApplyTheme}}catch(e){return 'ERR '+e.message}})()""")
    check('主题表 5 组 + 默认 E 已应用', isinstance(r, dict) and r.get('themes') == ['E','F','G','H','N']
          and r.get('hook') == 'function', r)
    r = ev("(function(){applyTheme3D('N');return {fog:CAM.fog.slice(),base:TERR3D.base.slice(),"
           "attr:document.documentElement.getAttribute('data-theme')}})()")
    check('applyTheme3D(N)：雾色沉入深背景', isinstance(r, dict)
          and r.get('fog') == [0.10,0.10,0.13] and r.get('base') == [0.29,0.30,0.34], r)
    time.sleep(0.8); shot('v21-地形-夜幕N.png')
    ev("applyTheme3D('E')"); time.sleep(0.8)
    shot('v21-地形-奶油草莓E.png')
    # postMessage 路径（软件内真实切换通道）
    ev("window.postMessage({type:'p3d-th',th:'F'},'*')")
    time.sleep(0.6)
    r = ev("(function(){return {attr:document.documentElement.getAttribute('data-theme'),fog:CAM.fog.slice()}})()")
    check('postMessage p3d-th=F 全链路生效', isinstance(r, dict)
          and r.get('attr') == 'F' and r.get('fog') == [0.90,0.95,0.93], r)
    ev("window.postMessage({type:'p3d-th',th:'N'},'*')"); time.sleep(0.6)

    print('\n[B] 2D 底图灰度 + 对比拉伸')
    keys = ev("Object.keys(DATA.maps).filter(function(k){"
              "return DATA.maps[k].rb && DATA.maps[k].wm})") or []
    print('  雷达图可用地图: %d 张，用 %s' % (len(keys), keys[0] if keys else '-'))
    ev("S.bmap=true; S.bop=0.6; loadMap(%s)" % json.dumps(keys[0] if keys else 'ze_pizza_cookie'))
    time.sleep(2.5)
    ev("setMode('2d')"); time.sleep(1.2)
    r = ev("""(function(){try{
      var c = radarGrayCache.get(S.key);
      if(!c) return {有缓存:false, radarBmp:!!radarCache.get(S.key)};
      var g2=c.getContext('2d');
      var d=g2.getImageData(c.width>>1, c.height>>1, 64, 64).data;
      var gray=true;
      for(var i=0;i<d.length;i+=4){ if(d[i]!==d[i+1]||d[i+1]!==d[i+2]){gray=false;break;} }
      return {有缓存:true, 尺寸:[c.width,c.height], 中心采样全灰:gray};
    }catch(e){return 'ERR '+e.message}})()""")
    check('灰度底图已生成并缓存', isinstance(r, dict) and r.get('有缓存'), r)
    check('像素 r==g==b（真灰度）', isinstance(r, dict) and r.get('中心采样全灰'), r)
    shot('v21-2D底图灰度.png')
    # 二次绘制不重复处理（缓存命中）
    t0 = ev("(function(){var t=performance.now();for(var i=0;i<20;i++)draw();return +(performance.now()-t).toFixed(1)})()")
    check('20 次 draw() 复用缓存（耗时 ms）', isinstance(t0, (int, float)) and t0 < 400, t0)
    ev("setMode('3d')"); time.sleep(1)

    print('\n[C] 顶栏「⋯ 更多」收纳')
    r = ev("""(function(){try{
      var inBar = !document.querySelector('.bar > #fit');
      var inMenu = !!document.querySelector('#moremenu #fit') &&
                   !!document.querySelector('#moremenu #png') &&
                   !!document.querySelector('#moremenu #glow') &&
                   !!document.querySelector('#moremenu #full');
      var closed = getComputedStyle(document.getElementById('moremenu')).display === 'none';
      return {fit不在顶栏:inBar, 低频项在菜单:inMenu, 默认收起:closed};
    }catch(e){return 'ERR '+e.message}})()""")
    check('fit/png/glow/full 已收进菜单且默认收起', isinstance(r, dict) and all(r.values()), r)
    ev("document.getElementById('morebtn').click()"); time.sleep(0.4)
    r = ev("getComputedStyle(document.getElementById('moremenu')).display")
    check('点击 ⋯ 展开', r == 'flex', r)
    shot('v21-顶栏更多菜单.png')
    ev("document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
       "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))"); time.sleep(0.3)
    r = ev("getComputedStyle(document.getElementById('moremenu')).display")
    check('Esc 收起', r == 'none', r)
    # 菜单内功能可用：点「适应窗口」
    ev("document.getElementById('morebtn').click()"); time.sleep(0.3)
    ev("document.getElementById('fit').click()"); time.sleep(0.8)
    r = ev("(function(){try{return {fit回调执行:!!draw, 视图复位:view.s>0}}catch(e){return 'ERR '+e.message}})()")
    check('菜单内按钮功能正常（适应窗口）', isinstance(r, dict) and r.get('视图复位'), r)
    ev("document.body.click()"); time.sleep(0.2)

    print('\n[D] 控制台错误')
    errs = []
    try:
        ws.settimeout(0.4); end = time.time() + 2
        while time.time() < end:
            try: msg = json.loads(ws.recv())
            except Exception: continue
            if msg.get('method') == 'Runtime.exceptionThrown':
                errs.append(str(msg['params']['exceptionDetails'].get('text'))[:110])
            elif msg.get('method') == 'Log.entryAdded':
                e2 = msg['params']['entry']
                if e2.get('level') == 'error': errs.append(str(e2.get('text'))[:110])
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

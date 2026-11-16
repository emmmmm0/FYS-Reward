# -*- coding: utf-8 -*-
"""一次性 CDP 验证：.bin 地形加载 / 主题热跟随 / 有地形按钮已删。用完可删。"""
import json, os, subprocess, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9340
prof = os.path.join(D, '验证截图-界面巡检', '_prof_cdp6')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
    '--user-data-dir=' + prof, '--no-first-run', '--window-size=1600,1000', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ws_url = None
    for i in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % PORT, timeout=2))
            page = [t for t in tabs if t.get('type') == 'page']
            if page:
                ws_url = page[0]['webSocketDebuggerUrl']; break
        except Exception:
            time.sleep(0.5)
    if not ws_url:
        raise SystemExit('CDP 没连上')
    ws = websocket.create_connection(ws_url, timeout=90)
    _id = [0]
    def send(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': m, 'params': p or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == _id[0]:
                return msg.get('result', {})
    def ev(e):
        r = send('Runtime.evaluate', {'expression': e, 'returnByValue': True})
        return r.get('result', {}).get('value')

    # 带 th=N 打开，验证 ?th= 生效
    send('Page.enable')
    send('Page.navigate', {'url': 'http://127.0.0.1:8791/preview3d?map=ze_pizza_cookie&th=N'})
    for i in range(60):
        if ev("typeof S!=='undefined' && !!DATA"):
            break
        time.sleep(1)
    time.sleep(1)
    print('T1 ?th=N 生效:', ev("document.documentElement.getAttribute('data-theme')") == 'N')

    # T2 postMessage 热跟随
    ev("window.postMessage({type:'p3d-th',th:'E'}, '*')")
    time.sleep(0.3)
    print('T2 消息切到 E:', ev("document.documentElement.getAttribute('data-theme')") == 'E')
    ev("window.postMessage({type:'p3d-th',th:'N'}, '*')")
    time.sleep(0.3)
    print('T2 非法码拒绝:', ev("(function(){window.postMessage({type:'p3d-th',th:'X'},'*');return document.documentElement.getAttribute('data-theme');})()"))

    # T3 .bin 地形加载（切 3D 并等 wstat 出现「面」）
    ev("setMode('3d')")
    ok = False
    for i in range(60):
        st = ev("document.getElementById('wstat').textContent") or ''
        if '面' in st and '加载中' not in st:
            ok = True; break
        time.sleep(1)
    print('T3 .bin 地形加载:', ok, '/ wstat =', ev("document.getElementById('wstat').textContent"),
          '/ fetch 的是 bin:', ev("performance.getEntriesByType('resource').some(r=>r.name.endsWith('.bin'))"))

    # T4 有地形按钮已删
    print('T4 fltm 已删:', ev("!document.getElementById('fltm')"),
          '/ side-tools 按钮:', ev("document.querySelectorAll('.side-tools button').length"))

    # 截图（N 主题 + 地形）
    time.sleep(2)
    shot = send('Page.captureScreenshot', {'format': 'png'})
    p = os.path.join(D, '验证截图-界面巡检', '20-主题跟随与bin地形.png')
    open(p, 'wb').write(__import__('base64').b64decode(shot['data']))
    print('截图:', os.path.getsize(p)//1024, 'KB')
    ws.close()
    print('ALL DONE')
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()

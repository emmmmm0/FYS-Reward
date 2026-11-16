# -*- coding: utf-8 -*-
"""样板交互验证：侧栏点击能切页、无 JS 报错、预览页占位正常。"""
import base64, json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
OUTD = os.path.join(D, '可爱样板-HTML')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9411
F = os.path.join(OUTD, '可爱A-奶油布丁.html')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*', '--user-data-dir=' + os.path.join(D, '_prof_cutemockv'),
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
    send('Runtime.enable')
    send('Emulation.setDeviceMetricsOverride',
         {'width': 1330, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})
    send('Page.navigate', {'url': 'file:///' + F.replace('\\', '/')})
    for _ in range(80):
        if ev("document.readyState==='complete' && !!document.getElementById('mkCute')"):
            break
        time.sleep(0.25)
    time.sleep(1.4)

    print('文件:', os.path.basename(F), os.path.getsize(F) // 1024, 'KB')
    print('初始视图:', ev("(document.querySelector('.view.on')||{}).id"),
          '| 高亮项:', ev("(document.querySelector('.mv.on')||{}).textContent"))

    ok = 0
    tot = 0
    for v, label in [('ov', '屏幕覆盖'), ('theme', '主题'), ('lib', '地图库'),
                     ('set', '设置'), ('pre', '实体预览'), ('srv', '服务器')]:
        ev("(function(){var b=document.querySelector('.mv[data-view=\"%s\"]');"
           "if(b) b.click();})()" % v)
        time.sleep(0.5)
        cur = ev("(document.querySelector('.view.on')||{}).id")
        nav = ev("(document.querySelector('.mv.on')||{}).getAttribute('data-view')")
        cards = ev("document.querySelectorAll('#view-%s .card').length" % v)
        tot += 1
        good = (cur == 'view-' + v and nav == v)
        ok += 1 if good else 0
        print('  点击「%s」-> %s / 高亮=%s / 卡片=%s  %s'
              % (label, cur, nav, cards, 'OK' if good else 'FAIL'))

    print('预览占位可见:', ev("(function(){var n=document.getElementById('mkPreNote');"
                          "return n?getComputedStyle(n).display:'none'})()"))
    ev("(function(){var b=document.querySelector('.mv[data-view=\"srv\"]'); if(b) b.click();})()")
    time.sleep(0.4)
    print('侧栏数:', ev("document.querySelectorAll('.mv').length"),
          '| 视图数:', ev("document.querySelectorAll('.view').length"))
    print('JS 报错数:', ev("(window.__e||[]).length"))
    print('结果: %d/%d 通过' % (ok, tot))
finally:
    try:
        proc.terminate()
    except Exception:
        pass

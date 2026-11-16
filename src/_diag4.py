# -*- coding: utf-8 -*-
"""复核：3D 模式下「适应窗口」按钮是否真的生效"""
import json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9358
BASE = 'http://127.0.0.1:%s' % (sys.argv[1] if len(sys.argv) > 1 else '8791')
prof = os.path.join(D, '验证截图-界面巡检', '_prof_diag4')

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
    send('Page.navigate', {'url': BASE + '/preview3d'})
    for _ in range(90):
        if ev("typeof DATA!=='undefined'&&!!DATA&&document.querySelectorAll('#lbody .li').length>0"):
            break
        time.sleep(0.25)
    time.sleep(3)
    print('模式 =', ev("S.mode"), ' GLok =', ev("GLok"))
    # 模拟用户缩放 + 旋转，把相机改离复位态
    ev("CAM.dist *= 3.2; CAM.yaw += 0.9; CAM.pitch = 0.2; CAM.tx += 300; render3D()")
    before = ev("[CAM.dist, CAM.yaw, CAM.pitch, CAM.tx]")
    ev("document.getElementById('fit').click()")
    time.sleep(0.4)
    after = ev("[CAM.dist, CAM.yaw, CAM.pitch, CAM.tx]")
    print('点击前 [dist,yaw,pitch,tx] =', before)
    print('点击后                    =', after)
    print('按钮是否复位相机          =', before != after)
finally:
    try: proc.terminate()
    except Exception: pass
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

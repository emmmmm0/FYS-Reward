# -*- coding: utf-8 -*-
"""一次性 CDP 验证：预览页双击独显修复 + 移速滑杆。用完可删。"""
import json, os, subprocess, time, urllib.request, sys
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9333
prof = os.path.join(D, '验证截图-界面巡检', '_prof_cdp')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*',
    '--user-data-dir=' + prof, '--no-first-run', '--window-size=1600,1000',
    'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    ws = websocket.create_connection(ws_url, timeout=60, http_proxy_host=None)
    _id = [0]
    def send(method, params=None):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': method, 'params': params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == _id[0]:
                return msg.get('result', {})
    def ev(expr, await_promise=False):
        r = send('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                      'awaitPromise': await_promise})
        return r.get('result', {}).get('value')

    send('Page.enable')
    send('Page.navigate', {'url': 'http://127.0.0.1:8791/preview3d?map=ze_pizza_cookie'})
    # 等图层列表渲染出来（数据是内嵌的，几秒内就绪）
    for i in range(60):
        n = ev("document.querySelectorAll('#lbody .li').length")
        if n and n > 0 and ev("typeof S!=='undefined' && !!DATA"):
            break
        time.sleep(1)
    else:
        raise SystemExit('页面没就绪')
    print('图层行数:', n)

    # ── T1 单击延迟：detail=1 后立即不应生效 ──
    ev("""
      (() => { const li = document.querySelector('#lbody .li');
        window.__g = li.dataset.g;
        li.dispatchEvent(new MouseEvent('click', {bubbles:true, detail:1}));
      })()
    """)
    imm = ev("!S.off.has(__g) && !S.solo")   # 260ms 内还没落地
    time.sleep(0.45)
    after = ev("S.off.has(__g) === true")    # 延迟后切换为隐藏
    print('T1 单击: 立即未生效=%s, 260ms后已隐藏=%s' % (imm, after))

    # ── T2 双击独显：先隐藏态再双击，应 off 捞回 + solo ──
    ev("""
      (() => { const li = document.querySelector('#lbody .li');
        li.dispatchEvent(new MouseEvent('click', {bubbles:true, detail:2}));
      })()
    """)
    time.sleep(0.1)
    solo_ok = ev("S.solo === __g && !S.off.has(__g)")
    cls = ev("document.querySelector('#lbody .li').className")
    print('T2 双击独显: solo且未隐藏=%s, 行class=%r' % (solo_ok, cls))

    # ── T3 再双击取消独显 ──
    ev("document.querySelector('#lbody .li').dispatchEvent(new MouseEvent('click', {bubbles:true, detail:2}))")
    time.sleep(0.1)
    print('T3 再双击取消: solo=null =', ev("S.solo === null"))

    # ── T4 移速滑杆联动 + 记忆 ──
    ev("""
      (() => { const f = document.getElementById('fspd');
        f.value = 35; f.dispatchEvent(new Event('input')); })()
    """)
    fspd = ev("CAM.fspd")
    txt = ev("document.getElementById('fspdv').textContent")
    ls = ev("localStorage.getItem('p3dfspd')")
    print('T4 移速滑杆: CAM.fspd=%s, 显示=%s, localStorage=%s' % (fspd, txt, ls))

    # ── T5 自由视角下移速箱显示 / 行走下隐藏 ──
    disp = ev("getComputedStyle(document.getElementById('fspdbox')).display")
    print('T5 非自由视角时移速箱 display=%s（应 none）' % disp)
    ev("typeof setFree==='function' && setFree(true)")
    time.sleep(0.3)
    disp2 = ev("getComputedStyle(document.getElementById('fspdbox')).display")
    print('T5 自由视角时 display=%s（应 flex/grid 等非 none）' % disp2)
    ev("typeof setFree==='function' && setFree(false)")
    ws.close()
    print('ALL DONE')
finally:
    proc.terminate()
    try: proc.wait(timeout=10)
    except Exception: proc.kill()

# -*- coding: utf-8 -*-
"""一次性 CDP 验证：拖动委托（innerHTML 重建后仍有效）+ 属性卡宽度手柄 + 行距美化。用完可删。"""
import json, os, subprocess, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9337
prof = os.path.join(D, '验证截图-界面巡检', '_prof_cdp5')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*', '--user-data-dir=' + prof, '--no-first-run',
    '--window-size=1600,1000', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    ws = websocket.create_connection(ws_url, timeout=60)
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

    send('Page.enable')
    send('Page.navigate', {'url': 'http://127.0.0.1:8791/preview3d?map=ze_pizza_cookie'})
    for i in range(60):
        if ev("typeof S!=='undefined' && !!DATA && document.querySelectorAll('#lbody .li').length>0"):
            break
        time.sleep(1)
    print('页面就绪')

    # T1 行距美化
    print('T1 lbody rowGap:', ev("getComputedStyle(document.getElementById('lbody')).rowGap"),
          '/ li padding:', ev("getComputedStyle(document.querySelector('#lbody .li')).paddingTop"),
          '/ foot 行数:', ev("document.querySelector('#layers .foot').textContent.length < 40"))

    # T2 属性卡：渲染 → 手柄挂载 → 拖动（委托）
    ev("showDetail(cur.pts[0])")
    print('T2 grip 挂载:', ev("!!document.querySelector('#edetail .rsgrip')"),
          '/ h5 title:', repr(ev("document.querySelector('#edetail h5').title")))
    ev("""
      (() => {
        const h5 = document.querySelector('#edetail h5');
        const r = h5.getBoundingClientRect();
        const mk = (t,x,y) => new MouseEvent(t, {bubbles:true, clientX:x, clientY:y, button:0});
        h5.dispatchEvent(mk('mousedown', r.x+10, r.y+5));
        document.dispatchEvent(mk('mousemove', r.x-120, r.y+80));
        document.dispatchEvent(mk('mouseup', r.x-120, r.y+80));
      })()
    """)
    pos1 = ev("JSON.stringify({l:document.getElementById('edetail').style.left, t:document.getElementById('edetail').style.top})")
    print('T2 首次拖动: %s 记忆=%s' % (pos1, ev("localStorage.getItem('p3depos')") is not None))

    # T3 重建（再渲染另一实体）后拖动仍有效
    ev("showDetail(cur.pts[7])")
    ev("""
      (() => {
        const h5 = document.querySelector('#edetail h5');
        const r = h5.getBoundingClientRect();
        const mk = (t,x,y) => new MouseEvent(t, {bubbles:true, clientX:x, clientY:y, button:0});
        h5.dispatchEvent(mk('mousedown', r.x+10, r.y+5));
        document.dispatchEvent(mk('mousemove', r.x+70, r.y-50));
        document.dispatchEvent(mk('mouseup', r.x+70, r.y-50));
      })()
    """)
    pos2 = ev("JSON.stringify({l:document.getElementById('edetail').style.left, t:document.getElementById('edetail').style.top})")
    print('T3 重建后再拖: %s 位置变化=%s' % (pos2, pos1 != pos2))

    # T4 属性卡宽度手柄
    w0 = ev("document.getElementById('edetail').getBoundingClientRect().width")
    ev("""
      (() => {
        const g = document.querySelector('#edetail .rsgrip');
        const r = g.getBoundingClientRect();
        const mk = (t,x,y) => new MouseEvent(t, {bubbles:true, clientX:x, clientY:y, button:0});
        g.dispatchEvent(mk('mousedown', r.x+3, r.y+40));
        document.dispatchEvent(mk('mousemove', r.x+3+200, r.y+40));
        document.dispatchEvent(mk('mouseup', r.x+3+200, r.y+40));
      })()
    """)
    w1 = ev("document.getElementById('edetail').getBoundingClientRect().width")
    print('T4 宽度手柄: %.0f -> %.0f px, 记忆=%s' % (w0, w1, ev("localStorage.getItem('p3ddw')")))

    # T5 手柄可视 CSS
    print('T5 手柄 before 宽:', ev(
        "getComputedStyle(document.querySelector('#layers .rsgrip'), '::before').width"))

    # 截图
    shot = send('Page.captureScreenshot', {'format': 'png'})
    p = os.path.join(D, '验证截图-界面巡检', '19-面板美化与拖动.png')
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

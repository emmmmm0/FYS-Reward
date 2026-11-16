# -*- coding: utf-8 -*-
"""一次性 CDP 验证：图层浮层折叠组 / 拖动 / 宽度手柄。用完可删。"""
import json, os, subprocess, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9336
prof = os.path.join(D, '验证截图-界面巡检', '_prof_cdp4')

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
    def drag(sel_or_el, dx, dy, grip=False):
        """在元素中心按下-移动-抬起，模拟真实拖动"""
        ev("""
      (async (sel) => {
        const el = %s;
        const r = el.getBoundingClientRect();
        const cx = r.x + (%s ? 3 : r.width/2), cy = r.y + r.height/2;
        const mk = (t,x,y) => new MouseEvent(t, {bubbles:true, clientX:x, clientY:y, button:0});
        el.dispatchEvent(mk('mousedown', cx, cy));
        document.dispatchEvent(mk('mousemove', cx-40, cy-30));
        document.dispatchEvent(mk('mousemove', cx+%d, cy+%d));
        document.dispatchEvent(mk('mouseup', cx+%d, cy+%d));
      })(%s)
    """ % (sel_or_el, 'true' if grip else 'false', dx, dy, dx, dy, sel_or_el))

    send('Page.enable')
    send('Page.navigate', {'url': 'http://127.0.0.1:8791/preview3d?map=ze_pizza_cookie'})
    for i in range(60):
        if ev("typeof S!=='undefined' && !!DATA"):
            break
        time.sleep(1)
    else:
        raise SystemExit('页面没就绪')
    time.sleep(1)

    # T1 折叠组：默认收起，点击展开，再点收起
    print('T1 默认收起:', ev("document.getElementById('setgrp').classList.contains('closed')"))
    ev("document.getElementById('sethead').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    print('T1 点击展开:', ev("!document.getElementById('setgrp').classList.contains('closed')"),
          '记忆=', ev("localStorage.getItem('p3dsetopen')"))
    ev("document.getElementById('sethead').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    print('T1 再点收起:', ev("document.getElementById('setgrp').classList.contains('closed')"))

    # T2 图层浮层拖动
    before = ev("({l: layers.style.left, t: layers.style.top})" .replace('layers', "document.getElementById('layers')") if False else
                "JSON.stringify({l:document.getElementById('layers').style.left, t:document.getElementById('layers').style.top})")
    drag("document.querySelector('#layers h4')", 160, 120)
    after = ev("JSON.stringify({l:document.getElementById('layers').style.left, t:document.getElementById('layers').style.top})")
    moved = after != before
    saved = ev("localStorage.getItem('p3dlpos')") is not None
    print('T2 图层浮层拖动: 位置变了=%s, 记忆=%s (%s)' % (moved, saved, after))

    # T3 宽度手柄
    w0 = ev("document.getElementById('layers').getBoundingClientRect().width")
    ev("""
      (() => { const g = document.querySelector('#layers .rsgrip');
        const r = g.getBoundingClientRect();
        const mk = (t,x,y) => new MouseEvent(t, {bubbles:true, clientX:x, clientY:y, button:0});
        g.dispatchEvent(mk('mousedown', r.x+3, r.y+50));
        document.dispatchEvent(mk('mousemove', r.x-80, r.y+50));
        document.dispatchEvent(mk('mouseup', r.x-80, r.y+50));
      })()
    """)
    w1 = ev("document.getElementById('layers').getBoundingClientRect().width")
    print('T3 宽度手柄: %.0f -> %.0f px, 记忆=%s' % (w0, w1, ev("localStorage.getItem('p3dlw')")))

    # T4 属性卡拖动（先选个实体让它显示）
    has_card = ev("document.getElementById('edetail').style.display !== 'none'")
    if not has_card:
        ev("S.mode==='3d' && typeof selectEnt==='function' && BOXES.length && selectEnt(BOXES[0], false)")
        time.sleep(0.3)
        has_card = ev("document.getElementById('edetail').style.display !== 'none'")
    if has_card:
        b2 = ev("document.getElementById('edetail').style.bottom || '(auto)'")
        drag("document.querySelector('#edetail h5')", -120, -100)
        a2 = ev("JSON.stringify({l:document.getElementById('edetail').style.left, t:document.getElementById('edetail').style.top})")
        print('T4 属性卡拖动: bottom原=%s -> 位置=%s, 记忆=%s' % (b2, a2, ev("localStorage.getItem('p3depos')") is not None))
    else:
        print('T4 属性卡没显示，跳过')

    # T5 2D 模式下整组隐藏
    ev("setMode('2d')")
    print('T5 2D模式 setgrp display:', ev("document.getElementById('setgrp').style.display"), '（应 none）')
    ev("setMode('3d')")
    print('T5 回3D setgrp display:', repr(ev("document.getElementById('setgrp').style.display")), '（应空）')

    # 截图：折叠状态
    send('Page.evaluate', {'expression': "document.getElementById('layers').style.right='10px'; document.getElementById('layers').style.left='auto'; document.getElementById('layers').style.top='10px'; document.getElementById('layers').style.width=''; localStorage.removeItem('p3dlpos'); localStorage.removeItem('p3dlw'); localStorage.removeItem('p3depos'); location.reload()"})
    time.sleep(6)
    shot = send('Page.captureScreenshot', {'format': 'png'})
    p = os.path.join(D, '验证截图-界面巡检', '19-图层折叠美化.png')
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

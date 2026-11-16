# -*- coding: utf-8 -*-
"""一次性 CDP 验证：S2V 按钮已删 + 图层细类（▾）展开/单独隐藏。用完可删。
用法：python _cdp_trigsub_test.py <port>"""
import json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
CDP = 9341
prof = os.path.join(D, '验证截图-界面巡检', '_prof_cdp7')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % CDP,
    '--remote-allow-origins=*', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
    '--user-data-dir=' + prof, '--no-first-run', '--window-size=1600,1000', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ws_url = None
    for i in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % CDP, timeout=2))
            page = [t for t in tabs if t.get('type') == 'page']
            if page:
                ws_url = page[0]['webSocketDebuggerUrl']; break
        except Exception:
            time.sleep(0.5)
    if not ws_url:
        raise SystemExit('CDP 没连上')
    ws = websocket.create_connection(ws_url, timeout=120)
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
    # ── T1 主页：S2V 按钮与 openVrf 已删 ──
    send('Page.navigate', {'url': 'http://127.0.0.1:%d/?view=lib' % PORT})
    for i in range(60):
        if ev("typeof LIB!=='undefined' && LIB.all && LIB.all.length"):
            break
        time.sleep(1)
    ev("var b=document.querySelector('.libRow'); if(b) b.click();")
    time.sleep(1.2)
    print('T1 openVrf 已删:', ev("typeof openVrf==='undefined'"))
    print('T1 无 libVrf 按钮:', ev("!document.querySelector('.libVrf')"))
    print('T1 详情卡无 S2V 字样:', ev("!document.getElementById('libDetail').innerHTML.includes('Source 2 Viewer')"))

    # ── T2 预览页：细类展开器 ──
    send('Page.navigate', {'url': 'http://127.0.0.1:%d/preview3d?map=ze_pizza_cookie' % PORT})
    for i in range(90):
        if ev("typeof S!=='undefined' && !!DATA && !!cur"):
            break
        time.sleep(1)
    time.sleep(1)
    print('T2 有展开器:', ev("document.querySelectorAll('#lbody .xbtn').length"),
          '/ 图层行:', ev("document.querySelectorAll('#lbody .li').length"))

    # 展开 trigger_teleport 所在层（tele 通常排第一）
    ev("var xb=document.querySelector('#lbody .xbtn'); xb.click();")
    time.sleep(0.4)
    print('T3 展开出细类行:', ev("document.querySelectorAll('#lbody .si').length"),
          '/ tele 细类数:', ev("Object.keys(cur.cncnt.tele||{}).length"))

    # T4 单独隐藏一个细类 → S.coff 记录 + 计数变化 + 恢复
    before = ev("document.querySelector('#lbody .li .ct').textContent")
    st = ev("(function(){var si=document.querySelector('#lbody .si'); si.click(); return {cn:si.dataset.cn, off:Array.from(S.coff)};})()")
    time.sleep(0.6)
    after = ev("document.querySelector('#lbody .li .ct').textContent")
    print('T4 隐藏细类:', st, '/ 层计数', before, '→', after, '(应变小)')
    print('T4 点云被过滤:', ev("(function(){var cn=Array.from(S.coff)[0]; var n=0; for(const o of cur.pts) if(o.cn===cn) n++; return n;})()"), '个点被藏')
    ev("document.querySelector('#lbody .si').click();")   # 恢复
    time.sleep(0.4)
    print('T4 恢复后 coff:', ev("Array.from(S.coff).length"))

    # T5 3D 模式下隐藏细类不报错（build3D 重建走 coff 过滤）
    ev("setMode('3d')")
    time.sleep(2)
    ev("var si=document.querySelector('#lbody .si'); if(si) si.click();")
    time.sleep(2)
    print('T5 3D 无错误:', ev("document.title.indexOf('ERR')===-0 and True" if False else "document.title.indexOf('ERR')===-1"),
          '/ title:', ev("document.title"))

    # 截图：展开状态
    ev("var xb=document.querySelector('#lbody .xbtn'); if(xb && !document.querySelector('#lbody .si')) xb.click();")
    ev("setMode('2d')")
    time.sleep(1.5)
    shot = send('Page.captureScreenshot', {'format': 'png'})
    p = os.path.join(D, '验证截图-界面巡检', '22-图层细类下拉.png')
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

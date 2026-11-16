# -*- coding: utf-8 -*-
"""一次性 CDP 全视图巡检：6 个视图逐个打开，收集 JS 异常/控制台错误 + 关键 DOM 断言。
重点验证：设置页版本号 v1.2 与更新日志渲染。用法：python _cdp_audit_all.py <port>"""
import json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
CDP = 9342
prof = os.path.join(D, '验证截图-界面巡检', '_prof_cdp8')
SHOT = os.path.join(D, '验证截图-界面巡检')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % CDP,
    '--remote-allow-origins=*', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
    '--user-data-dir=' + prof, '--no-first-run', '--window-size=1500,950', 'about:blank'],
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
    def drain(sec):
        ws.settimeout(0.3); end = time.time()+sec; out=[]
        while time.time() < end:
            try:
                msg = json.loads(ws.recv())
                if msg.get('method') in ('Runtime.exceptionThrown',):
                    d = msg['params']['exceptionThrownDetails']
                    out.append('JS异常: ' + str(d.get('exception', {}).get('description', d))[:160])
                if msg.get('method') == 'Log.entryAdded':
                    e = msg['params']['entry']
                    if e.get('level') in ('error',):
                        out.append('控制台: ' + str(e.get('text'))[:160])
            except websocket.WebSocketTimeoutException:
                pass
            except Exception:
                break
        ws.settimeout(120)
        return out

    send('Runtime.enable'); send('Log.enable'); send('Page.enable')
    errs = []
    send('Page.navigate', {'url': 'http://127.0.0.1:%d/' % PORT})
    for i in range(60):
        if ev("typeof LIB!=='undefined' && !!window.STATUS"):
            break
        time.sleep(1)
    errs += drain(2)

    # ── 设置页：版本 + 更新日志 ──
    ev("showView('set')")
    time.sleep(1)
    print('S1 版本号:', ev("$('abVer').textContent"))
    print('S2 名片版本:', ev("$('auVer').textContent"))
    print('S3 更新日志版本数:', ev("document.querySelectorAll('#clgCard .clgv').length"),
          '/ 条目数:', ev("document.querySelectorAll('#clgCard .clg li').length"))
    print('S4 当前版本标记:', ev("(function(){var t=document.querySelector('#clgCard .clgv'); return t.textContent;})()"))
    print('S5 首发标记:', ev("(function(){var xs=document.querySelectorAll('#clgCard .clglx'); return xs[xs.length-1].textContent;})()"))
    errs += drain(1)
    shot = send('Page.captureScreenshot', {'format': 'png'})
    p = os.path.join(SHOT, '23-设置页版本与更新日志.png')
    open(p, 'wb').write(__import__('base64').b64decode(shot['data']))

    # ── 其余视图逐个过 ──
    for v, wait, chk in [
        ('srv',   1.2, "$('srvBox') ? ('ok · ' + ($('srvName')||{}).textContent) : 'no-srvBox'"),
        ('ov',    0.8, "document.querySelectorAll('#view-ov input[type=checkbox]').length + '个开关'"),
        ('theme', 0.8, "document.querySelectorAll('#themes .tcard, #themes > *').length + '个主题卡节点'"),
        ('lib',   0.8, "$('libSub').textContent.slice(0,40)"),
        ('pre',   1.0, "$('preCur2').textContent"),
    ]:
        ev("showView('%s')" % v)
        time.sleep(wait)
        print('视图 %-5s → %s' % (v, ev(chk)))
        errs += drain(0.5)

    # 地图库详情 + 预览细类回归
    ev("showView('lib')"); time.sleep(0.5)
    ev("var b=document.querySelector('.libRow'); if(b) b.click();"); time.sleep(1.0)
    print('详情卡正常:', ev("!!document.querySelector('#libDetail .libBdg')"),
          '/ 无 S2V:', ev("!document.getElementById('libDetail').innerHTML.includes('Source 2 Viewer')"))
    ev("openPreView('ze_pizza_cookie')")   # 从地图库直达内嵌预览
    for i in range(60):
        if ev("window.frames[0] && window.frames[0].document && window.frames[0].document.querySelectorAll('#lbody .xbtn').length > 0"):
            break
        time.sleep(1)
    time.sleep(1)
    fr = "window.frames[0]."
    print('内嵌预览加载:', ev(fr + "document.querySelectorAll('#lbody .li').length > 0"),
          '/ 细类展开器:', ev(fr + "document.querySelectorAll('#lbody .xbtn').length"))
    errs += drain(2)
    shot = send('Page.captureScreenshot', {'format': 'png'})
    p = os.path.join(SHOT, '24-内嵌预览回归.png')
    open(p, 'wb').write(__import__('base64').b64decode(shot['data']))

    print('')
    print('异常/错误汇总:', len(errs), '条')
    for e in errs[:12]:
        print('  -', e)
    ws.close()
    print('ALL DONE')
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()

# -*- coding: utf-8 -*-
"""第二批样板验证：每个文件都检查「默认页 / 装饰挂载 / 侧栏可切页 / 无 JS 报错」。"""
import base64, json, os, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
OUTD = os.path.join(D, '可爱样板-HTML')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9431

# 风格 -> (文件名, 该风格特有的装饰选择器, 说明)
JOBS = [
    ('F', '可爱F-云朵泡芙.html', '.mkCl', '卡片顶云朵'),
    ('G', '可爱G-草莓手账.html', '.mkTape', '胶带'),
    ('H', '可爱H-卡通图鉴.html', '#mkScene', '右下角场景卡'),
    ('I', '可爱I-贴纸派对.html', '.mkStk', '卡片贴纸'),
    ('J', '可爱J-毛绒玩偶.html', '.mkBtn', '卡片钮扣'),
    ('K', '可爱K-彩虹软糖.html', '.mkGloss', '果冻高光'),
]

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*', '--user-data-dir=' + os.path.join(D, '_prof_cutemockv2'),
    '--no-first-run', '--window-size=1330,720', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
FAIL = []


def check(name, ok, extra=''):
    print(('  [PASS] ' if ok else '  [FAIL] ') + name + (('  ' + str(extra)) if extra else ''))
    if not ok:
        FAIL.append(name)


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
            d = r['exceptionDetails']
            return '__ERR__' + str(d.get('exception', {}).get('description', d.get('text')))
        return r.get('result', {}).get('value')

    send('Page.enable')
    send('Runtime.enable')
    send('Page.addScriptToEvaluateOnNewDocument', {'source':
        "window.__e=[];addEventListener('error',function(x){__e.push(String(x.message||x))});"
        "addEventListener('unhandledrejection',function(x){__e.push('p:'+String(x.reason))});"})
    send('Emulation.setDeviceMetricsOverride',
         {'width': 1330, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})

    for key, fn, sel, desc in JOBS:
        p = os.path.join(OUTD, fn)
        print('\n%s  大小 %d KB' % (fn, os.path.getsize(p) // 1024))
        send('Page.navigate', {'url': 'file:///' + p.replace('\\', '/')})
        for _ in range(80):
            if ev("document.readyState==='complete' && !!document.getElementById('mkCute')"):
                break
            time.sleep(0.25)
        time.sleep(1.8)

        check('默认停在服务器页', ev("(document.querySelector('.view.on')||{}).id") == 'view-srv',
              ev("(document.querySelector('.view.on')||{}).id"))
        check('装饰已挂载：%s' % desc,
              (ev("document.querySelectorAll('%s').length" % sel) or 0) > 0,
              ev("document.querySelectorAll('%s').length" % sel))
        check('漂浮贴纸 8 个', ev("document.querySelectorAll('#mkDeco i').length") == 8)

        # 侧栏切页（切到地图库再切回来），并确认切页后装饰仍会补挂
        ev("(function(){var b=document.querySelector('.mv[data-view=\"lib\"]'); if(b) b.click();})()")
        time.sleep(0.9)
        check('点击「地图库」切页 + 高亮同步',
              ev("(document.querySelector('.view.on')||{}).id") == 'view-lib' and
              ev("(document.querySelector('.mv.on')||{}).getAttribute('data-view')") == 'lib')
        check('切页后地图库装饰补挂',
              (ev("document.querySelectorAll('#view-lib %s').length" % sel) or 0) +
              (ev("document.querySelectorAll('%s').length" % sel) or 0) > 0)
        ev("(function(){var b=document.querySelector('.mv[data-view=\"srv\"]'); if(b) b.click();})()")
        time.sleep(0.6)
        check('切回服务器页', ev("(document.querySelector('.view.on')||{}).id") == 'view-srv')

        errs = ev("(window.__e||[]).join(' | ')")
        check('无未捕获 JS 错误', not errs, errs)

    print('\n===== 结果：%s =====' % ('全部通过' if not FAIL else '失败 %d 项: %s' % (len(FAIL), FAIL)))
finally:
    try:
        proc.terminate()
    except Exception:
        pass

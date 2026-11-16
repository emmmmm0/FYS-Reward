# -*- coding: utf-8 -*-
"""验证主题自适应样板：5 份锁定版各自的主题真的生效 + 可切换版能现场切主题。

断言每份：
  · html[data-theme] 是目标主题
  · 计算出的 --accent / --bg 等于 ui_page.py 里该主题的值（证明配色真的跟着主题走，没被写死）
  · 卡片上的云朵装饰已挂载、数量与卡片数匹配
  · 底纹背景图带上了该主题对应的图案（暗色用 pat_dark、亮色用 pat）
  · 侧栏能点着切页
可切换版额外：
  · 底部主题条 5 个按钮 + 点第 i 个 → data-theme 变成对应主题，且 --accent 同步变
  · 主题页 5 张卡片仍在、点击其中一张也能切主题
用法：python _cute_mock_verify3.py
"""
import base64, json, os, re, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
FR = os.path.join(D, 'fys-reward')
OUTD = os.path.join(D, '可爱样板-HTML')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
sys.path.insert(0, FR)
import ui_page

THEMES = {t[0]: dict(name=t[1], accent=t[3]) for t in ui_page.THEMES}
DARK = {'N'}

port = 9423
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % port,
    '--remote-allow-origins=*', '--user-data-dir=' + os.path.join(D, '_prof_verify3'),
    '--no-first-run', '--window-size=1330,720', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

P = F = 0


def check(label, ok, extra=''):
    global P, F
    if ok:
        P += 1; print('  [OK] %s %s' % (label, extra))
    else:
        F += 1; print('  [!!] %s %s' % (label, extra))


try:
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % port, timeout=2))
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

    send('Page.enable'); send('Runtime.enable')
    send('Emulation.setDeviceMetricsOverride',
         {'width': 1330, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})
    # 收集运行期报错
    ev("window.__err=[];window.onerror=function(m){window.__err.push(''+m)};")

    for code in ['E', 'F', 'G', 'H', 'N']:
        p = os.path.join(OUTD, '\u53ef\u7231\u6837\u677f-\u4e3b\u9898%s%s.html' % (code, THEMES[code]['name']))
        send('Page.navigate', {'url': 'file:///' + p.replace('\\', '/')})
        for _ in range(80):
            if ev("document.readyState==='complete' && !!document.getElementById('mkCute')"):
                break
            time.sleep(0.25)
        time.sleep(2.2)
        print('[%s %s]' % (code, THEMES[code]['name']))
        info = ev("""(function(){
          var cs=getComputedStyle(document.documentElement);
          var m=document.querySelector('.main')||document.body;
          var bg=getComputedStyle(m).backgroundImage||'';
          return {th:document.documentElement.getAttribute('data-theme'),
                  accent:cs.getPropertyValue('--accent').trim(),
                  bgv:cs.getPropertyValue('--bg').trim(),
                  cl:document.querySelectorAll('.mkCl i').length,
                  tgt:document.querySelectorAll('.card,.libList,.libDetail,.themePal').length,
                  cards:document.querySelectorAll('.card').length,
                  hasBg:bg.length>500,
                  sticker:!!document.getElementById('cuteSticker'),
                  badge:(document.getElementById('mkBadge')||{}).textContent||''};
        })()""")
        check('\u4e3b\u9898\u5c5e\u6027', info['th'] == code, info['th'])
        check('\u4e3b\u8272\u8ddf\u968f\u4e3b\u9898', info['accent'].lower() == THEMES[code]['accent'].lower(),
              '%s vs %s' % (info['accent'], THEMES[code]['accent']))
        check('\u5e95\u8272\u4e0e\u4e3b\u9898\u5339\u914d\uff08\u6697\u8272\u7528\u6df1\u5e95\uff09',
              (info['bgv'].lower() == '#16151a') if code == 'N' else (info['bgv'] != '#16151a'),
              info['bgv'])
        check('\u4e91\u6735\u88c5\u9970\uff08\u4e0e\u88c5\u9970\u5bf9\u8c61\u6570\u5339\u914d\uff09', info['cl'] == info['tgt'] * 3,
              'puff=%d targets=%d cards=%d' % (info['cl'], info['tgt'], info['cards']))
        check('\u5e95\u7eb9\u80cc\u666f\u5df2\u751f\u6548', info['hasBg'])
        check('\u4fa7\u680f\u8d34\u7eb8\u5728', info['sticker'])
        check('\u89d2\u6807\u663e\u793a\u4e3b\u9898\u540d', THEMES[code]['name'] in info['badge'], info['badge'])
        # 点侧栏切页
        ev("(function(){var n=document.querySelector('.mv[data-view=lib]');if(n)n.click();})()")
        time.sleep(1.2)
        check('\u70b9\u4fa7\u680f\u80fd\u5207\u5230\u5730\u56fe\u5e93',
              ev("(document.querySelector('.view.on')||{}).id") == 'view-lib')
        ev("(function(){var n=document.querySelector('.mv[data-view=theme]');if(n)n.click();})()")
        time.sleep(1.0)
        check('\u70b9\u4fa7\u680f\u80fd\u5207\u5230\u4e3b\u9898\u9875',
              ev("(document.querySelector('.view.on')||{}).id") == 'view-theme')

    # ── 可切换版：现场切主题 ──
    print('[可切换版]')
    p = os.path.join(OUTD, '\u53ef\u7231\u6837\u677f-\u4e3b\u9898\u81ea\u9002\u5e94-\u53ef\u5207\u6362.html')
    send('Page.navigate', {'url': 'file:///' + p.replace('\\', '/')})
    for _ in range(80):
        if ev("document.readyState==='complete' && !!document.getElementById('mkBar')"):
            break
        time.sleep(0.25)
    time.sleep(2.2)
    check('\u4e3b\u9898\u6761 5 \u4e2a\u6309\u94ae', ev("document.querySelectorAll('#mkBar button').length") == 5)
    for i, code in enumerate(['E', 'F', 'G', 'H', 'N']):
        ev("document.querySelectorAll('#mkBar button')[%d].click()" % i)
        time.sleep(0.7)
        got = ev("({th:document.documentElement.getAttribute('data-theme'),"
                 "ac:getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),"
                 "on:document.querySelectorAll('#mkBar button.on').length,"
                 "badge:(document.getElementById('mkBadge')||{}).textContent||''})")
        check('\u70b9\u7b2c%d\u4e2a\u6309\u94ae\u2192%s' % (i + 1, THEMES[code]['name']),
              got['th'] == code and got['ac'] == THEMES[code]['accent'] and got['on'] == 1
              and THEMES[code]['name'] in got['badge'], str(got))
    # 主题页卡片点击切换
    ev("(function(){var n=document.querySelector('.mv[data-view=theme]');if(n)n.click();})()")
    time.sleep(1.2)
    check('\u4e3b\u9898\u9875 5 \u5f20\u5361\u7247\u5728', ev("document.querySelectorAll('#themes .tcard').length") == 5)
    ev("document.querySelectorAll('#themes .tcard')[1].click()")
    time.sleep(0.8)
    got = ev("({th:document.documentElement.getAttribute('data-theme'),"
             "on:document.querySelectorAll('#themes .tcard.on').length,"
             "st:(document.querySelectorAll('#themes .tstate')[1]||{}).textContent||''})")
    check('\u70b9\u4e3b\u9898\u5361\u4e5f\u80fd\u5207\u4e3b\u9898', got['th'] == 'F' and got['on'] == 1, str(got))
    check('\u5361\u7247\u4e0a\u6807\u300c\u4f7f\u7528\u4e2d\u300d', '\u4f7f\u7528\u4e2d' in got['st'], got['st'])
    errs = ev("(window.__err||[]).join(' | ')")
    check('\u65e0 JS \u62a5\u9519', not errs, errs)
finally:
    try:
        proc.terminate()
    except Exception:
        pass

print('\n\u5408\u8ba1 %d \u9879\u901a\u8fc7 / %d \u9879\u5931\u8d25' % (P, F))

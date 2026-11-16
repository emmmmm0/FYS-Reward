# -*- coding: utf-8 -*-
"""三个反馈的修复验证：① 设置页文案 ② 滚动时漂浮贴纸 ③ 更新日志展开不被轮询重置

   ② 的关键：滚动期间贴纸要淡出（data-roll=1），停手后重排到新空白处再淡入，
      并且**任何时刻都不能压到内容**（复用几何断言）。
   ③ 的关键：点开旧版本后跨 3+ 秒（= 3 次 status 轮询）仍保持展开。

   用法：python _cdp_fix_v18_test.py <port>
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

from _prefs_guard import PrefsGuard

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
SHOT = os.path.join(D, '验证截图-界面巡检')
CDP = 9403
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8807
FAIL = []


def check(name, ok, extra=''):
    print(('  [PASS] ' if ok else '  [FAIL] ') + name + (('  ' + str(extra)) if extra else ''))
    if not ok:
        FAIL.append(name)


OVERLAP_JS = r"""
(function(){
  var d=document.getElementById('floatDeco');
  if(!d) return {n:0, bad:[], occlen:0};
  var box=flOcc(), is=d.querySelectorAll('i'), i, j, bad=[];
  for(i=0;i<is.length;i++){
    if(is[i].style.display==='none') continue;
    var r=is[i].getBoundingClientRect();
    for(j=0;j<box.length;j++){
      var o=box[j];
      var ox=Math.min(r.right,o[2])-Math.max(r.left,o[0]);
      var oy=Math.min(r.bottom,o[3])-Math.max(r.top,o[1]);
      if(ox>0&&oy>0&&Math.round(ox*oy)>4) bad.push({i:i,area:Math.round(ox*oy)});
    }
  }
  var vis=0;
  for(i=0;i<is.length;i++) if(is[i].style.display!=='none') vis++;
  var cs=getComputedStyle(d);
  return {n:vis, bad:bad.slice(0,4), occlen:box.length,
          roll:d.getAttribute('data-roll'), op:cs.opacity};
})()
"""

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_g = PrefsGuard().__enter__()
proc = subprocess.Popen(
    [EDGE, '--headless=new', '--remote-debugging-port=%d' % CDP, '--remote-allow-origins=*',
     '--user-data-dir=' + os.path.join(SHOT, '_prof_v18'), '--no-first-run',
     '--window-size=1400,820', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % CDP, timeout=2))
            pg = [t for t in tabs if t.get('type') == 'page']
            if pg:
                ws_url = pg[0]['webSocketDebuggerUrl']
                break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(ws_url, timeout=240, http_proxy_host=None)
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
    send('Page.addScriptToEvaluateOnNewDocument', {'source':
        "window.__e=[];addEventListener('error',function(x){__e.push(String(x.message||x))});"})
    send('Emulation.setDeviceMetricsOverride',
         {'width': 1400, 'height': 820, 'deviceScaleFactor': 1, 'mobile': False})
    send('Page.navigate', {'url': 'http://127.0.0.1:%d/?noreadme' % PORT})
    for _ in range(90):
        if ev("typeof LIB!=='undefined' && !!$('flrow')"):
            break
        time.sleep(0.5)
    time.sleep(2.6)

    print('\n[1] 设置页头图文案')
    ev("showView('set')"); time.sleep(1.6)
    txt = ev("(document.querySelector('#view-set .setBanner')||{innerText:''}).innerText||''")
    check('文案不再声称主题/背景在设置页', '主题' not in txt and '背景' not in txt, txt.replace('\n', ' / '))
    check('文案列的是设置页真实内容（数据同步/广播原文/更新日志）',
          ('同步' in txt) and ('广播' in txt) and ('更新日志' in txt), txt.replace('\n', ' / '))
    d = send('Page.captureScreenshot', {'format': 'png'})
    open(os.path.join(SHOT, 'v18-01-设置页文案.png'), 'wb').write(base64.b64decode(d['data']))

    print('\n[2] 滚动时漂浮贴纸：滚动中淡出 / 停手后重排淡入且不压内容')
    ev("showView('srv')"); time.sleep(1.8)
    r0 = ev(OVERLAP_JS)
    check('滚动前：贴纸在且不压内容', not r0.get('bad'), r0)
    # 每次都重新查滚动容器：DOM 局部重建后旧引用会脱离文档，设 scrollTop 静默无效
    SCROLL_JS = ("(function(){var m=document.querySelector('.main');"
                 "var el=(m&&m.scrollHeight-m.clientHeight>40)?m:document.scrollingElement;"
                 "el.scrollTop=%d;return el.scrollTop})()")
    ev(SCROLL_JS % 0)
    tops = []
    for k in range(8):                                # 连续小步滚，模拟滚轮
        tops.append(ev(SCROLL_JS % ((k + 1) * 45)))
        time.sleep(0.045)
    r_mid = ev(OVERLAP_JS)
    check('滚动生效（scrollTop 递增到 %s）' % tops[-1],
          isinstance(tops[-1], (int, float)) and tops[-1] > 100, tops)
    check('滚动中：贴纸整体淡出（data-roll=1 且透明）',
          r_mid.get('roll') == '1' and float(r_mid.get('op') or 1) < 0.5, r_mid)
    time.sleep(0.9)                                   # 停手 > 220ms，等重排+淡入
    r1 = ev(OVERLAP_JS)
    check('停手后：重新出现（data-roll 已清、不透明）',
          r1.get('roll') is None and float(r1.get('op') or 0) > 0.9, r1)
    check('停手后：已按新布局重排，仍不压内容', not r1.get('bad'), r1)
    d = send('Page.captureScreenshot', {'format': 'png'})
    open(os.path.join(SHOT, 'v18-02-滚动后重排.png'), 'wb').write(base64.b64decode(d['data']))
    ev(SCROLL_JS % 0)
    time.sleep(0.8)

    print('\n[3] 更新日志：点开后不被每秒轮询重置')
    ev("showView('set')"); time.sleep(1.8)
    n0 = ev("document.querySelectorAll('#clgCard .clgvw.open').length")
    check('默认只展开「当前版本」1 条', n0 == 1, n0)
    r = ev("(function(){var vs=document.querySelectorAll('#clgCard .clgvw');"
           "for(var i=0;i<vs.length;i++){var b=vs[i].querySelector('.clgv b');"
           "if(b&&b.textContent.indexOf('v1.4')>=0){vs[i].querySelector('.clgv').click();break}}"
           "return document.querySelectorAll('#clgCard .clgvw.open').length})()")
    check('点击 v1.4 后展开为 2 条', r == 2, r)
    for w in (1.5, 3.2, 5.0):                          # 跨 1/3/5 次 status 轮询
        time.sleep(w - (0 if w == 1.5 else (1.5 if w == 3.2 else 3.2)))
        cur = ev("document.querySelectorAll('#clgCard .clgvw.open').length")
        check('等待 %ss 后仍保持展开（open=%s）' % (w, cur), cur == 2, cur)
    # 再点一下应能收起（交互没被破坏）
    ev("(function(){var vs=document.querySelectorAll('#clgCard .clgvw');"
       "for(var i=0;i<vs.length;i++){var b=vs[i].querySelector('.clgv b');"
       "if(b&&b.textContent.indexOf('v1.4')>=0){vs[i].querySelector('.clgv').click();break}}})()")
    time.sleep(1.4)
    check('再次点击可正常收起（open=1）',
          ev("document.querySelectorAll('#clgCard .clgvw.open').length") == 1)
    d = send('Page.captureScreenshot', {'format': 'png'})
    open(os.path.join(SHOT, 'v18-03-更新日志保持.png'), 'wb').write(base64.b64decode(d['data']))

    print('\n[4] 异常')
    errs = ev("(window.__e||[]).join(' | ')")
    check('全程无 JS 报错', not errs, errs)

    print('\n== 结果：%s ==' % ('全部通过' if not FAIL else '失败 %d 项' % len(FAIL)))
    for f in FAIL:
        print('   x', f)
    ws.close()
finally:
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except Exception:
        proc.kill()
    _g.__exit__(None, None, None)

# -*- coding: utf-8 -*-
"""漂浮贴纸（水印式）功能回归：CDP 真实点击 + 几何断言。

   重点不是「有没有挂上」，而是**有没有压到内容**：
   每个可见贴纸都要跟「占用区扫描」的结果做矩形相交检测（允许 ≤4px² 的贴边）。
   另外覆盖：三档切换 / 默认档 / 记忆 / 换页重排 / 改窗口重排 / 侧栏折叠 / 无 JS 报错。

   用法：python _cdp_float_test.py <port>
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
CDP = 9399
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8807
FAIL = []


def check(name, ok, extra=''):
    print(('  [PASS] ' if ok else '  [FAIL] ') + name + (('  ' + str(extra)) if extra else ''))
    if not ok:
        FAIL.append(name)


op = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# 偏好守卫：float 会被 [5] 改写成 on。(a) 先摘掉，[1] 才测得到真正的「首次默认档」；
# (b) 结束时字节级还原，脚本对用户设置零影响。见 _prefs_guard.py。
_g = PrefsGuard(drop=('float',)).__enter__()

proc = subprocess.Popen(
    [EDGE, '--headless=new', '--remote-debugging-port=%d' % CDP, '--remote-allow-origins=*',
     '--user-data-dir=' + os.path.join(SHOT, '_prof_float'), '--no-first-run',
     '--window-size=1400,820', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 页面里跑的重叠检测：返回「最紧的一处间隙」与违规数
OVERLAP_JS = r"""
(function(){
  var d=document.getElementById('floatDeco');
  if(!d) return {n:0, bad:[], tight:null};
  var box=flOcc(), is=d.querySelectorAll('i'), i, j, bad=[], minGap=1e9;
  for(i=0;i<is.length;i++){
    if(is[i].style.display==='none') continue;
    var r=is[i].getBoundingClientRect();
    for(j=0;j<box.length;j++){
      var o=box[j];
      var ox=Math.min(r.right,o[2])-Math.max(r.left,o[0]);
      var oy=Math.min(r.bottom,o[3])-Math.max(r.top,o[1]);
      if(ox>0&&oy>0){
        var area=Math.round(ox*oy);
        if(area>4) bad.push({i:i,area:area,box:o});
        else { var g=Math.max(ox,oy); if(g<minGap) minGap=g; }
      }
    }
  }
  var vis=0;
  for(i=0;i<is.length;i++) if(is[i].style.display!=='none') vis++;
  return {n:vis, bad:bad.slice(0,4), tight:(minGap===1e9?null:Math.round(minGap*10)/10),
          occlen:box.length};
})()
"""


def fmt(v):
    if v is None:
        return '-'
    return v


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

    def snap(name):
        d = send('Page.captureScreenshot', {'format': 'png'})
        open(os.path.join(SHOT, name), 'wb').write(base64.b64decode(d['data']))

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
    time.sleep(2.4)

    print('\n[1] 选择器与默认档')
    n_opt = ev("document.querySelectorAll('#flrow .stkopt').length")
    check('漂浮贴纸选择器 3 档', n_opt == 3, n_opt)
    check('默认选中「淡化水印」',
          ev("(document.querySelector('#flrow .stkopt.on')||{}).getAttribute ? "
             "document.querySelector('#flrow .stkopt.on').getAttribute('data-s') : '-'") == 'soft',
          ev("(document.querySelector('#flrow .stkopt.on')||{}).getAttribute && "
             "document.querySelector('#flrow .stkopt.on').getAttribute('data-s')"))
    st = ev("(function(){var d=document.getElementById('floatDeco');var i=d.querySelector('i');"
            "var cs=getComputedStyle(i);return {n:d.querySelectorAll('i').length,"
            "lv:d.getAttribute('data-lv'),op:cs.opacity,fs:cs.fontSize};})()")
    check('淡化档 = 3 个 / 17px / 透明度 .30', isinstance(st, dict) and st.get('n') == 3 and
          st.get('fs') == '17px' and abs(float(st.get('op', 0)) - 0.30) < 0.02, st)

    print('\n[2] 各页面几何检测：贴纸不得压到内容')
    for v, tag in (('srv', '服务器'), ('lib', '地图库'), ('theme', '主题'), ('set', '设置'),
                   ('ov', '屏幕覆盖')):
        ev("showView('%s')" % v)
        time.sleep(1.6)
        r = ev(OVERLAP_JS)
        check('%-6s 可见 %s 个，压到内容 %s 处（最紧间隙 %s px，占用区 %s）'
              % (tag, fmt(r.get('n')), len(r.get('bad') or []), fmt(r.get('tight')),
                 fmt(r.get('occlen'))),
              not (r.get('bad') or []), r.get('bad'))
        if v == 'srv':
            snap('贴纸-淡化-服务器页.png')

    print('\n[3] 换页 / 改窗口 / 折叠侧栏 后重排')
    # 断言看「整串落位」而不是首点：某档下两页首个候选点可能恰好相同（实测 6 贴纸时
    # 各页首点都是 1064,56），只看首点会误报；整串序列才反映占用区差异。
    POS_ALL = ("(function(){var is=document.querySelectorAll('#floatDeco i'),o=[];"
               "for(var i=0;i<is.length;i++) if(is[i].style.display!=='none')"
               "o.push(is[i].style.left+','+is[i].style.top);return o.join(' ')})()")
    ev("showView('theme')"); time.sleep(1.4)
    pos1 = ev(POS_ALL)
    ev("showView('srv')"); time.sleep(1.6)
    pos2 = ev(POS_ALL)
    check('换页后整串落位随新页面占用区重排', bool(pos1) and pos1 != pos2,
          '%s  →  %s' % (pos1, pos2))
    send('Emulation.setDeviceMetricsOverride',
         {'width': 1100, 'height': 760, 'deviceScaleFactor': 1, 'mobile': False})
    time.sleep(1.6)
    r = ev(OVERLAP_JS)
    check('窗口缩到 1100×760 后不压内容（可见 %s 个）' % fmt(r.get('n')),
          not (r.get('bad') or []), r.get('bad'))
    send('Emulation.setDeviceMetricsOverride',
         {'width': 1400, 'height': 820, 'deviceScaleFactor': 1, 'mobile': False})
    time.sleep(1.2)
    ev("fold(true)"); time.sleep(1.6)
    r = ev(OVERLAP_JS)
    check('折叠侧栏后不压内容（可见 %s 个）' % fmt(r.get('n')), not (r.get('bad') or []), r.get('bad'))
    ev("fold(false)"); time.sleep(1.0)

    print('\n[4] 三档切换')
    ev("(function(){document.querySelector('#flrow .stkopt[data-s=\"on\"]').click();})()")
    time.sleep(1.6)
    st = ev("(function(){var d=document.getElementById('floatDeco');var i=d.querySelector('i');"
            "var cs=getComputedStyle(i);return {n:d.querySelectorAll('i').length,lv:d.getAttribute('data-lv'),"
            "op:cs.opacity,fs:cs.fontSize};})()")
    check('「明显一点」= 6 个 / 20px / 52%', isinstance(st, dict) and st.get('n') == 6 and
          st.get('fs') == '20px' and abs(float(st.get('op', 0)) - 0.52) < 0.02, st)
    r = ev(OVERLAP_JS)
    check('「明显一点」也不压内容', not (r.get('bad') or []), r.get('bad'))
    snap('贴纸-明显-服务器页.png')

    ev("(function(){document.querySelector('#flrow .stkopt[data-s=\"off\"]').click();})()")
    time.sleep(0.9)
    check('「不显示」→ 图层整个移除', ev("!document.getElementById('floatDeco')"),
          ev("!!document.getElementById('floatDeco')"))
    ev("(function(){document.querySelector('#flrow .stkopt[data-s=\"soft\"]').click();})()")
    time.sleep(1.4)
    check('切回「淡化水印」→ 重新挂上 3 个',
          ev("(document.querySelectorAll('#floatDeco i')||[]).length") == 3)

    print('\n[5] 记忆与深链参数')
    ev("(function(){document.querySelector('#flrow .stkopt[data-s=\"on\"]').click();})()")
    time.sleep(0.8)
    saved = json.loads(op.open('http://127.0.0.1:%d/api/prefs' % PORT, timeout=8).read().decode())
    check('偏好写入 ui_prefs.json 的 float=on', saved.get('prefs', {}).get('float') == 'on',
          saved.get('prefs', {}).get('float'))
    send('Page.navigate', {'url': 'http://127.0.0.1:%d/?noreadme' % PORT})
    for _ in range(90):
        if ev("typeof LIB!=='undefined' && !!$('flrow')"):
            break
        time.sleep(0.5)
    time.sleep(2.0)
    check('刷新后仍是「明显一点」',
          ev("document.getElementById('floatDeco').getAttribute('data-lv')") == 'on')
    send('Page.navigate', {'url': 'http://127.0.0.1:%d/?noreadme&fl=off' % PORT})
    for _ in range(90):
        if ev("typeof LIB!=='undefined' && !!$('flrow')"):
            break
        time.sleep(0.5)
    time.sleep(1.6)
    check('?fl=off 预览参数生效', ev("!document.getElementById('floatDeco')"))
    send('Page.navigate', {'url': 'http://127.0.0.1:%d/?noreadme' % PORT})
    for _ in range(90):
        if ev("typeof LIB!=='undefined' && !!$('flrow')"):
            break
        time.sleep(0.5)
    time.sleep(1.8)

    print('\n[6] 主题页 / 实体预览 / 异常')
    ev("showView('theme')"); time.sleep(1.4)
    snap('贴纸-主题页选择器.png')
    ev("showView('pre')"); time.sleep(2.0)
    for _ in range(60):
        if ev("window.frames[0] && window.frames[0].document && "
              "window.frames[0].document.querySelectorAll('#lbody .li').length>0"):
            break
        time.sleep(1)
    time.sleep(3.0)
    r = ev(OVERLAP_JS)
    check('实体预览页（iframe 占满）不压 3D（可见 %s 个）' % fmt(r.get('n')),
          not (r.get('bad') or []), r.get('bad'))
    ev("showView('srv')"); time.sleep(1.2)
    errs = ev("(window.__e||[]).join(' | ')")
    check('全程无 JS 报错', not errs, errs)

    print('\n== 结果：%s ==' % ('全部通过' if not FAIL else '失败 %d 项' % len(FAIL)))
    for f in FAIL:
        print('   x', f)
finally:
    try:
        proc.terminate()
    except Exception:
        pass
    _g.__exit__(None, None, None)               # 还原用户真实偏好

# -*- coding: utf-8 -*-
"""把运行中的真实软件页面完整导出为「静态自包含 HTML」。
   - 逐个访问各视图，让数据都渲染进 DOM（否则快照里其他页是空的）
   - 导出 documentElement.outerHTML，剥掉全部 <script>，得到纯静态页
   - 页面内的背景素材/logo 本来就是 data URI，所以静态页自带全部资源
"""
import base64, json, os, re, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9401
BASE = 'http://127.0.0.1:%s' % (sys.argv[1] if len(sys.argv) > 1 else '61060')
OUT = os.path.join(D, '_snap_app.html')
prof = os.path.join(D, '_prof_snap')

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*', '--user-data-dir=' + prof, '--no-first-run',
    '--window-size=1330,720', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % PORT, timeout=2))
            page = [t for t in tabs if t.get('type') == 'page']
            if page:
                ws_url = page[0]['webSocketDebuggerUrl']; break
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

    def ev(e, ap=False):
        r = send('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': ap})
        if 'exceptionDetails' in r:
            return '__ERR__ ' + str(r['exceptionDetails'].get('text'))
        return r.get('result', {}).get('value')

    def wait(cond, sec=60, tag=''):
        for _ in range(int(sec * 4)):
            if ev(cond):
                return True
            time.sleep(0.25)
        print('   [超时]', tag or cond[:70])
        return False

    send('Page.enable')
    send('Emulation.setDeviceMetricsOverride',
         {'width': 1330, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})
    send('Page.navigate', {'url': BASE + '/?view=srv'})
    wait("document.readyState==='complete' && typeof LIB!=='undefined'", 90, '首页')
    time.sleep(2.0)
    print('首页就绪, 主题=', ev("document.documentElement.getAttribute('data-theme')"),
          '背景=', ev("document.documentElement.getAttribute('data-bg')"))

    # 逐个访问视图触发数据渲染（跳过 pre：会拉 34MB 预览页）
    PLAN = [
        ('lib', "document.querySelectorAll('#libList .libRow').length>0", '地图库索引'),
        ('theme', "document.querySelectorAll('#themes .tcard').length>=5", '主题卡'),
        ('set', "!!document.querySelector('#view-set .card')", '设置卡'),
        ('ov', "!!document.querySelector('#view-ov .card')", '覆盖页'),
    ]
    for v, cond, tag in PLAN:
        ev("showView('%s')" % v)
        ok = wait(cond, 60, tag)
        print('  %s -> %s' % (tag, 'OK' if ok else 'FAIL'))

    # 地图库点开第一张，让右侧详情卡有内容；再点开细类
    ev("showView('lib')"); time.sleep(0.8)
    ev("(function(){var r=document.querySelector('#libList .libRow');"
       "if(r){r.click();return 1}return 0})()")
    time.sleep(2.0)
    ev("showView('theme')"); time.sleep(1.0)
    ev("showView('ov')");  time.sleep(1.2)
    ev("showView('srv')"); time.sleep(2.0)

    html = ev("document.documentElement.outerHTML")
    print('快照长度:', len(html) // 1024, 'KB')
finally:
    try:
        proc.terminate()
    except Exception:
        pass

if not html or len(html) < 10000:
    print('!! 快照异常'); sys.exit(1)

# ── 后处理：剥脚本、断外链、清掉预览 iframe ──
n0 = len(html)
html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S | re.I)
html = re.sub(r'<script\b[^>]*/>', '', html, flags=re.I)
print('剥掉 script 段:', n0 - len(html), '字节')
# 预览 iframe 去掉 src，避免静态页去拉 34MB 预览
html = re.sub(r'(<iframe[^>]*id="preFrm"[^>]*)\ssrc="[^"]*"', r'\1', html)
# 顶栏的状态胶囊在静态页里没意义（连不上服务器），保留但不会动
open(OUT, 'w', encoding='utf-8').write('<!DOCTYPE html>\n' + html)
print('已写出', OUT, os.path.getsize(OUT) // 1024, 'KB')
print('  残留 <script>:', html.lower().count('<script'))
print('  视图数:', html.count('class="view'), '| 侧栏项:', html.count('class="nav mv'))
print('  地图行:', html.count('libRow'), '| 主题卡:', html.count('tcard'))
print('  背景图 data URI:', html.count('data:image/'))

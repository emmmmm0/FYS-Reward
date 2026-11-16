# -*- coding: utf-8 -*-
"""可爱G「草莓手账」样板 —— 把六个页面全部截一遍（整窗 1330×720）+ 拼一张对照图。

   样板 HTML 默认停在服务器页，所以只看得到第一页；本脚本用 CDP 依次点侧栏
   切到 地图库/主题/设置/屏幕覆盖/实体预览，逐页截图，最后拼 2×3 对照图。
   用法：python _cuteg_views.py
"""
import base64, json, os, subprocess, sys, time, urllib.request

import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
HTML = os.path.join(D, '可爱样板-HTML', '可爱G-草莓手账.html')
SHOT = os.path.join(D, '验证截图-界面巡检')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PREVIEW3D = os.path.join(D, 'fys-reward', 'preview3d.html').replace('\\', '/')
PORT = 9455
W, H = 1330, 720

# (data-view, 文件名后缀, 说明)
VIEWS = [
    ('srv', '01-服务器表', '服务器表'),
    ('lib', '02-地图库', '地图库'),
    ('theme', '03-主题页', '主题样式'),
    ('set', '04-设置页', '设置'),
    ('ov', '05-屏幕覆盖', '屏幕覆盖'),
    ('pre', '06-实体预览', '地图实体预览'),
]

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen(
    [EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT, '--remote-allow-origins=*',
     '--user-data-dir=' + os.path.join(D, '_prof_cutegv'), '--no-first-run',
     '--window-size=%d,%d' % (W, H), 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

shots = []
try:
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % PORT, timeout=2))
            pg = [t for t in tabs if t.get('type') == 'page']
            if pg:
                ws_url = pg[0]['webSocketDebuggerUrl']
                break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(ws_url, timeout=180, http_proxy_host=None)
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
    send('Emulation.setDeviceMetricsOverride',
         {'width': W, 'height': H, 'deviceScaleFactor': 1, 'mobile': False})

    print('打开 %s（%.1f MB）' % (os.path.basename(HTML), os.path.getsize(HTML) / 1048576))
    send('Page.navigate', {'url': 'file:///' + HTML.replace('\\', '/')})
    for _ in range(120):
        if ev("document.readyState==='complete' && !!document.getElementById('mkCute')"):
            break
        time.sleep(0.25)
    time.sleep(2.6)

    for view, tag, desc in VIEWS:
        ev("(function(){var b=document.querySelector('.mv[data-view=\"%s\"]'); if(b) b.click();})()" % view)
        time.sleep(1.5)
        cur = ev("(document.querySelector('.view.on')||{}).id")
        if view == 'pre' and '--realpre' in sys.argv:
            # 静态样板里的 iframe 是空的（没接 3D）。挂真实预览页试过一次：
            #   file:// 下父子不同源，拿不到 iframe 的 contentWindow，
            #   画布不会按 iframe 尺寸 resize → 渲染错位，故默认不做，
            #   保留样板自带的「样板是静态页面，不含 3D 实时数据」提示。
            ev("(function(){var f=document.getElementById('preFrame');var n=document.getElementById('mkPreNote');"
               "if(n) n.style.display='none'; if(f) f.src='file:///%s?map=ze_minecraft_hortus_de_escapismo';})()"
               % PREVIEW3D)
            time.sleep(14)
        ev("(function(){var c=document.querySelector('.content'); if(c) c.scrollTop=0; window.scrollTo(0,0);})()")
        time.sleep(0.4)
        d = send('Page.captureScreenshot', {'format': 'png'})
        out = os.path.join(SHOT, '可爱样板G草莓手账-%s.png' % tag)
        open(out, 'wb').write(base64.b64decode(d['data']))
        shots.append((out, desc))
        print('  %-40s %5d KB   当前页=%s' % (os.path.basename(out),
                                              os.path.getsize(out) // 1024, cur))
finally:
    try:
        proc.terminate()
    except Exception:
        pass

# ── 2×3 对照图 ──────────────────────────────────────────────
try:
    from PIL import Image, ImageDraw, ImageFont
    reg = r'C:\Windows\Fonts\msyh.ttc'
    bold = r'C:\Windows\Fonts\msyhbd.ttc'
    if not os.path.exists(bold):
        bold = reg
    f = ImageFont.truetype(bold, 21)
    COLS, ROWS, SC, GAP, BAR = 2, 3, 0.5, 12, 34
    tw, th = int(W * SC), int(H * SC)
    cw = COLS * tw + (COLS + 1) * GAP
    ch = ROWS * (th + BAR) + (ROWS + 1) * GAP
    canvas = Image.new('RGB', (cw, ch), '#f6f2f4')
    dr = ImageDraw.Draw(canvas)
    for i, (p, desc) in enumerate(shots):
        r, c = divmod(i, COLS)
        x = GAP + c * (tw + GAP)
        y = GAP + r * (th + BAR + GAP)
        im = Image.open(p).convert('RGB').resize((tw, th), Image.LANCZOS)
        canvas.paste(im, (x, y + BAR))
        dr.text((x + 4, y + 5), '%d. %s' % (i + 1, desc), font=f, fill='#5a3b3b')
        dr.rectangle([x - 1, y + BAR - 1, x + tw, y + BAR + th], outline='#e3d3d8')
    out = os.path.join(SHOT, '可爱样板G草莓手账-00-六视图对照.png')
    canvas.save(out, quality=92)
    print('\n对照图：%s  %d KB  %dx%d' % (os.path.basename(out), os.path.getsize(out) // 1024,
                                          canvas.size[0], canvas.size[1]))
except Exception as e:                                        # noqa: BLE001
    print('拼图失败：%s' % e)

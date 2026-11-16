# -*- coding: utf-8 -*-
"""地形面数对比截图：72k vs 144k，同机位同主题。
用法：python _cdp_terr_compare.py <8791>
依赖 fys-reward/terr/ 里 <pid>.bin 为 144k 版、<pid>.bin.bak72k 为原版；
脚本每张图按 [先144k → 还原72k → 再截] 的顺序出两帧。"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
TERR = os.path.join(D, 'fys-reward', 'terr')
SHOT = os.path.join(D, '验证截图-预览审计')
os.makedirs(SHOT, exist_ok=True)
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9381
BASE = 'http://127.0.0.1:%s' % (sys.argv[1] if len(sys.argv) > 1 else '8791')

MAPS = [
    ('3304076935', 'ze_steyliff_grove', 'steyliff'),
    ('3636650451', 'ze_silent_hill_rengurn', 'silenthill'),
    ('3261289969', 'de_jura', 'jura'),
]

proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*', '--user-data-dir=' + os.path.join(D, '验证截图-界面巡检', '_prof_diag7'),
    '--no-first-run', '--window-size=1440,900', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % PORT, timeout=2))
            page = [t for t in tabs if t.get('type') == 'page']
            if page: ws_url = page[0]['webSocketDebuggerUrl']; break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(ws_url, timeout=90, http_proxy_host=None)
    _id = [0]
    def send(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': m, 'params': p or {}}))
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == _id[0]: return r.get('result', {})
    def ev(e):
        r = send('Runtime.evaluate', {'expression': e, 'returnByValue': True})
        if 'exceptionDetails' in r: return '__ERR__ ' + str(r['exceptionDetails'].get('text'))
        return r.get('result', {}).get('value')
    def shot(name):
        b = send('Page.captureScreenshot', {'format': 'png'})['data']
        open(os.path.join(SHOT, name), 'wb').write(base64.b64decode(b))
        print('  📸 ' + name)

    send('Page.enable'); send('Runtime.enable')
    send('Network.enable')
    send('Network.setCacheDisabled', {'cacheDisabled': True})   # 防止 HTTP 缓存回吐旧 bin

    def load(name):
        # ?map= 是按内部名子串匹配的深链（如 ?map=steyliff），别传完整键
        send('Page.navigate', {'url': '%s/preview3d?map=%s' % (BASE, name)})
        for _ in range(120):
            if ev("typeof DATA!=='undefined'&&!!DATA&&document.querySelectorAll('#lbody .li').length>0"):
                break
            time.sleep(0.25)
        for _ in range(160):
            if ev("(function(){try{return GL3D.meshCount>0}catch(e){return false}})()"):
                break
            time.sleep(0.25)
        time.sleep(2.5)

    for pid, name, short in MAPS:
        got = ev("(function(){for(var k in DATA.maps){if(DATA.maps[k].m==='%s')return k}})()" % name)
        if not got:
            print('!! 找不到 %s 的内部键' % name); continue
        for variant, fname in (('144k', pid + '.bin.hi144k'), ('72k', pid + '.bin.bak72k')):
            src = os.path.join(TERR, fname)
            dst = os.path.join(TERR, pid + '.bin')
            if not os.path.exists(src):
                print('!! 缺 %s' % src); continue
            shutil.copy2(src, dst)
            load(name)
            faces = ev("(function(){try{return GL3D.meshCount}catch(e){return 0}})()")
            wf = ev("(function(){try{return cur.m.wf}catch(e){return null}})()")
            stat = ev("(function(){var w=document.getElementById('wstat');return w?w.textContent:''})()")
            print('  [%s %s] wf=%s meshCount=%s wstat=%s' % (short, variant, wf, faces, stat))
            assert str(wf) == pid, 'wf 与目标 pid 不一致，深链没生效'
            # 全景（默认机位）
            shot('terr对比-%s-%s.png' % (short, variant))
            # 近景：相机拉近 0.12x 并压低视角，楼梯/栏杆细节才看得清
            ev("(function(){try{CAM.dist=Math.max(0.5,CAM.dist*0.12);CAM.pitch=0.95;"
               "CAM.yaw=-Math.PI/2+0.55;render3D();return CAM.dist|0}catch(e){return 'ERR '+e.message}})()")
            time.sleep(0.8)
            shot('terr对比-%s-%s-近景.png' % (short, variant))
finally:
    try: proc.terminate()
    except Exception: pass
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass
    # 还原 72k 原版，避免本地缓存目录留 144k
    for pid, _, _ in MAPS:
        bak = os.path.join(TERR, pid + '.bin.bak72k')
        if os.path.exists(bak):
            shutil.copy2(bak, os.path.join(TERR, pid + '.bin'))
    print('terr 缓存已还原为 72k 原版')

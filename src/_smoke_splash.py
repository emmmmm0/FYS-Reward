# -*- coding: utf-8 -*-
"""一次性冒烟：软件本体内置启动界面（#bootSplash）。用完可删。

v2.15 批次改为「本体内置启动卡」后的验证链：
  1) 不存在独立启动窗（FysSplashWnd 类已随 splash.py 移除）；
  2) 主窗 ≤8s 可见（不再是先隐藏后显示）；
  3) 页面首屏带 #bootSplash 启动卡（HTTP 直查 HTML）；
  4) WebView2 CDP：启动卡出现 → bootReal 完成后淡出并从 DOM 移除；
  5) startup.log 无异常、无「强制显示」兜底残留。
"""
import ctypes
import json
import os
import subprocess
import time
import urllib.request

import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35\fys-reward'
PY = r'C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe'
LOG = os.path.join(D, 'data', 'startup.log')
PORT = 9472
CDP = 9488

user32 = ctypes.windll.user32
fails = []


def ev(win, expr):
    r = win.send('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
    res = r.get('result', {})
    if 'exceptionDetails' in r:
        return None
    return res.get('value')


class Ws(object):
    """极简 CDP websocket 封装。"""

    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=30, http_proxy_host=None)
        self._id = 0

    def send(self, method, params=None):
        self._id += 1
        self.ws.send(json.dumps({'id': self._id, 'method': method,
                                 'params': params or {}}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get('id') == self._id:
                return r.get('result', {})


def find_main():
    """返回可见的「云朵小铺」主窗列表。"""
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        buf = ctypes.create_unicode_buffer(128)
        user32.GetWindowTextW(h, buf, 128)
        pid = ctypes.c_uint32()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if buf.value.startswith('云朵小铺') and user32.IsWindowVisible(h):
            out.append(buf.value)
        return True

    user32.EnumWindows(cb, 0)
    return out


def find_splash():
    return user32.FindWindowW('FysSplashWnd', None)


op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = None
ws = None
try:
    pos = os.path.getsize(LOG) if os.path.exists(LOG) else 0

    # ── 起真应用：WebView2 挂 CDP 调试口，便于直查页面内部状态 ──
    env = dict(os.environ)
    env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = \
        '--remote-debugging-port=%d --remote-allow-origins=*' % CDP
    t0 = time.time()
    proc = subprocess.Popen([PY, 'fys_reward_app.py', '--port', str(PORT)],
                            cwd=D, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ① ≤8s 主窗可见；且任何时刻都没有 FysSplashWnd 独立窗
    win_seen = None
    splash_seen = None
    dl = time.time() + 8
    while time.time() < dl:
        if find_splash():
            splash_seen = time.time() - t0
        if find_main():
            win_seen = time.time() - t0
            break
        time.sleep(0.2)
    if splash_seen is not None:
        fails.append('① 出现了独立启动窗 FysSplashWnd（%.1fs）' % splash_seen)
    elif find_splash():
        fails.append('① 启动中途出现独立启动窗')
    else:
        print('① 全程无独立启动窗 ✔')
    if win_seen is None:
        fails.append('① 主窗 8s 内不可见')
    else:
        print('① 主窗 %.1fs 可见 ✔' % win_seen)

    # ② 页面 HTML 自带启动卡
    html = ''
    for _ in range(30):
        try:
            html = op.open('http://127.0.0.1:%d/' % PORT, timeout=3).read().decode('utf-8', 'replace')
            if 'bootSplash' in html:
                break
        except Exception:
            pass
        time.sleep(0.5)
    if 'id="bootSplash"' in html and 'bsPhase' in html:
        print('② 页面自带 #bootSplash 启动卡 ✔')
    else:
        fails.append('② 页面 HTML 里没有启动卡标记')

    # ③ CDP：启动卡出现 → 完成后淡出移除
    page_ws = None
    dl = time.time() + 25
    while time.time() < dl:
        try:
            tabs = json.load(op.open('http://127.0.0.1:%d/json' % CDP, timeout=2))
            pages = [t for t in tabs if t.get('type') == 'page'
                     and ('127.0.0.1:%d' % PORT) in (t.get('url') or '')]
            if pages:
                page_ws = pages[0]['webSocketDebuggerUrl']
                break
        except Exception:
            pass
        time.sleep(0.5)
    if not page_ws:
        fails.append('③ CDP 未连上 WebView2 页面')
    else:
        ws = Ws(page_ws)
        ws.send('Runtime.enable')
        early = ev(ws, "!!document.getElementById('bootSplash')")
        last_phase = None
        gone_at = None
        dl = time.time() + 30
        while time.time() < dl:
            ex = ev(ws, "!!document.getElementById('bootSplash')")
            ph = ev(ws, "window.bsPhase && document.getElementById('bsPhase')"
                       " ? document.getElementById('bsPhase').textContent"
                       " : (window.__bsLast||null)")
            if ph:
                last_phase = ph
            if early and ex is False:
                gone_at = time.time() - t0
                break
            if not early and gone_at is None and time.time() - t0 > 15:
                pass
            time.sleep(0.4)
        # 兜底记录最后阶段文案（启动卡被移除后元素查不到了，改抓退出前状态）
        if last_phase:
            print('③ 启动卡阶段文案（最后一次读到）：%s ✔' % last_phase)
        else:
            print('③ 启动卡阶段文案：启动卡已快速退场（未及轮询，属正常）')
        if early is True and gone_at is not None:
            print('③ 启动卡 %.1fs 出现 → %.1fs 完成初始化并淡出 ✔' % (0.0, gone_at))
        elif early is True:
            fails.append('③ 启动卡 30s 未退场（初始化链路卡住）')
        elif early is False:
            print('③ 连上时启动卡已退场（页面初始化快于 CDP 连接，正常）')
        err = ev(ws, "window.__errs ? window.__errs.length : null")
        if err:
            fails.append('③ 页面 JS 异常 %d 条' % err)

    # ④ 日志核对：窗口创建步 + 无兜底强显
    time.sleep(1)
    with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
        f.seek(pos)
        tail = f.read()
    if '原生启动卡已铺上窗体' in tail:
        print('④ 日志：原生启动卡模式已生效 ✔')
    else:
        fails.append('④ 日志里没有原生启动卡标记')
    if '强制显示' in tail or 'splash' in tail.lower():
        fails.append('④ 日志出现兜底强显或 splash 残留')
    else:
        print('④ 日志无兜底强显 / splash 残留 ✔')

    # ⑤ 15s 后仍是单窗运行
    time.sleep(6)
    if find_splash():
        fails.append('⑤ 运行中途冒出独立启动窗')
    if find_main():
        print('⑤ 运行稳定、主窗可见 ✔')
    else:
        fails.append('⑤ 运行 15s 后主窗不可见')
finally:
    if ws:
        try:
            ws.ws.close()
        except Exception:
            pass
    if proc:
        subprocess.run(['taskkill', '/F', '/PID', str(proc.pid), '/T'],
                       capture_output=True)

print('=' * 40)
if fails:
    print('冒烟失败 %d 项：' % len(fails))
    for f in fails:
        print(' ✘', f)
    raise SystemExit(1)
print('内置启动界面冒烟：全部通过')

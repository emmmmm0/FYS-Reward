# -*- coding: utf-8 -*-
"""预览壳下载进度回归（2026-11-16）：主窗口遮罩必须能看到真实下载进度。

背景（用户截图复现）：gh-proxy 间歇性挂起时 urlopen 卡满 180s 才换源，期间
/api/preview/progress 一直是 idle → 遮罩永远停在「假进度条」，看起来像没有进度条。

修复后口径：
  A) 后端 preview_fetch：每个源开连前 phase=connect + src=主机名；45s 换源、
     120s 总预算；下载中 64KB 分块流式 + got/total 实时更新。
  B) 前端遮罩：connect 显示「正在连接镜像源 …」；download 显示确定进度条 +
     百分比/MB；扫动条起点 -37% 保证任何时刻都至少露 1%（原 -64% 每圈 1/6
     时间整条隐形）。

用法：python _e2e_pvprog.py   （A 段进程内桩服务器，B 段 headless Edge CDP）
"""
import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)

PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
APP = os.path.join(HERE, "fys_reward_app.py")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PASS = FAIL = 0
PORT = 8863
CDP = 0                        # 运行时取随机空闲口，避免上次 Edge 残留抢占
BASE = "http://127.0.0.1:%d" % PORT
PROFILE = os.path.join(os.environ.get("TEMP", "."), "_pvprog_prof")
SHOT = os.path.join(HERE, "..", "验证截图-进度条遮罩")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE):
    EDGE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [OK]   %s %s" % (name, extra))
    else:
        FAIL += 1
        print("  [FAIL] %s %s" % (name, extra))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ─────────────────────────── A 段：后端进度状态机 ───────────────────────────

class _HangH(http.server.BaseHTTPRequestHandler):
    """挂起源：收下请求后不回响应头，一直耗到客户端超时。"""
    def do_GET(self):
        time.sleep(30)

    def log_message(self, *a):
        pass


class _SlowH(http.server.BaseHTTPRequestHandler):
    """慢速源：按 Content-Length 分块吐 3MB，模拟真实下载。"""
    def do_GET(self):
        total = 3 * 1024 * 1024
        self.send_response(200)
        self.send_header("Content-Length", str(total))
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        chunk = b"<html><body>" + b"p" * (64 * 1024 - 12)
        n = 0
        while n < total:
            self.wfile.write(chunk[: min(64 * 1024, total - n)])
            n += len(chunk[: min(64 * 1024, total - n)])
            time.sleep(0.01)

    def log_message(self, *a):
        pass


class _TrickleH(http.server.BaseHTTPRequestHandler):
    """涓流源：响应头秒回，数据每次只给 1KB（复刻镜像挂起时的涓流行为）。"""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(3 * 1024 * 1024))
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        end = time.time() + 20
        try:
            self.wfile.write(b"<html><body>")
            self.wfile.flush()
            while time.time() < end:          # 每秒 2KB，20 秒也下不完 3MB
                self.wfile.write(b"t" * 1024)
                self.wfile.flush()
                time.sleep(0.5)
        except OSError:
            return

    def log_message(self, *a):
        pass


def part_a():
    print("── A 段：preview_fetch 进度状态机（进程内 + 本地桩源）──")
    import fys_reward_app as A

    hang_port = free_port()
    slow_port = free_port()
    trk_port = free_port()
    hsrv = socketserver.ThreadingTCPServer(("127.0.0.1", hang_port), _HangH)
    ssrv = socketserver.ThreadingTCPServer(("127.0.0.1", slow_port), _SlowH)
    tsrv = socketserver.ThreadingTCPServer(("127.0.0.1", trk_port), _TrickleH)
    for s in (hsrv, ssrv, tsrv):
        threading.Thread(target=s.serve_forever, daemon=True).start()

    # 隔离：不碰真实壳 / 真实云端
    tmp_name = "preview3d_e2etmp.html"
    real_pf, real_stale, real_ver, real_file = (
        A.preview_path, A._pv_stale, A._pv_cloud_ver, A.PREVIEW_FILE)
    A.preview_path = lambda: None
    A._pv_stale = lambda sz: False
    A._pv_cloud_ver = lambda fresh=False: None
    A.PREVIEW_FILE = tmp_name
    A.PV_URLS = ["http://127.0.0.1:%d" % hang_port,      # 挂起源排第一
                 "http://127.0.0.1:%d" % slow_port]
    A.PV_OPEN_TIMEOUT = 3.0       # 测试口径：挂起源 3s 就换
    A.PV_SRC_BUDGET = 100.0
    try:
        seen = []                 # (t, phase, src, got, total)
        result = {}

        def run():
            result["r"] = A.preview_fetch()

        th = threading.Thread(target=run, daemon=True)
        th.start()
        t0 = time.time()
        last_got = -1
        mono = True
        while th.is_alive() and time.time() - t0 < 30:
            p = dict(A._PV_PROG)
            seen.append((round(time.time() - t0, 2), p.get("phase"),
                         p.get("src"), p.get("got"), p.get("total")))
            if p.get("phase") == "download":
                if p.get("got", 0) < last_got:
                    mono = False
                last_got = p.get("got", 0)
            time.sleep(0.05)
        th.join(timeout=5)

        phases = [s[1] for s in seen]
        check("先看到 connect 阶段", "connect" in phases, phases[:4])
        first = next((s for s in seen if s[1] == "connect"), None)
        check("connect 带挂起源主机名", first and str(first[2]).endswith(str(hang_port)),
              first and first[2])
        check("随后切到第二源（3s 换源生效）",
              any(s[1] == "connect" and str(s[2]).endswith(str(slow_port))
                  for s in seen)
              or any(s[1] == "download" and str(s[2]).endswith(str(slow_port))
                     for s in seen),
              "connect 窗口毫秒级抓不到也算过（download 的 src 已证明）")
        check("出现 download 阶段", "download" in phases, "")
        dl = [s for s in seen if s[1] == "download"]
        check("download 带 Content-Length 总量", dl and dl[-1][4] == 3 * 1024 * 1024,
              dl and dl[-1][4])
        check("got 单调递增", mono, "")
        check("download 阶段源主机名=成功源",
              dl and str(dl[-1][2]).endswith(str(slow_port)), dl and dl[-1][2])
        fp, err = result.get("r", (None, "?"))
        check("preview_fetch 成功返回", fp and err is None, err)
        if fp:
            check("落盘大小=Content-Length", os.path.getsize(fp) == 3 * 1024 * 1024,
                  os.path.getsize(fp))
            check("结束后 phase=done", A._PV_PROG.get("phase") == "done",
                  A._PV_PROG.get("phase"))
            try:
                os.remove(fp)
                if os.path.exists(fp + ".ver"):
                    os.remove(fp + ".ver")
            except OSError:
                pass

        # ── 场景 2：涓流源（响应头秒回、数据不走）→ 下载预算弃源换下家 ──
        A.PV_URLS = ["http://127.0.0.1:%d" % trk_port,
                     "http://127.0.0.1:%d" % slow_port]
        A.PV_DL_BUDGET = 2.0
        A._PV_PROG.update(phase="idle", got=0, total=0)
        result2 = {}
        th2 = threading.Thread(
            target=lambda: result2.__setitem__("r", A.preview_fetch()),
            daemon=True)
        th2.start()
        t0 = time.time()
        seen2 = []
        while th2.is_alive() and time.time() - t0 < 30:
            p = dict(A._PV_PROG)
            seen2.append((round(time.time() - t0, 2), p.get("phase"),
                          p.get("src"), p.get("got")))
            time.sleep(0.05)
        th2.join(timeout=5)
        dl2 = [s for s in seen2 if s[1] == "download"]
        trk = [s for s in dl2 if str(s[2]).endswith(str(trk_port))]
        check("涓流源：先在其上开始 download（有 got 增长）",
              bool(trk) and dl2[0][2] == trk[0][2] and max(s[3] for s in trk) > 0,
              trk[-1] if trk else dl2[:1])
        check("涓流源未被下完就弃掉（got 远小于 total）",
              trk and max(s[3] for s in trk) < 1024 * 1024,
              trk and max(s[3] for s in trk))
        check("涓流超预算弃掉、换到慢速源",
              any(s[1] == "download" and str(s[2]).endswith(str(slow_port))
                  for s in dl2), "")
        fp2, err2 = result2.get("r", (None, "?"))
        check("涓流场景最终成功", fp2 and err2 is None, err2)
        if fp2:
            check("涓流场景落盘完整", os.path.getsize(fp2) == 3 * 1024 * 1024,
                  os.path.getsize(fp2))
            try:
                os.remove(fp2)
                if os.path.exists(fp2 + ".ver"):
                    os.remove(fp2 + ".ver")
            except OSError:
                pass
    finally:
        A.preview_path, A._pv_stale, A._pv_cloud_ver, A.PREVIEW_FILE = (
            real_pf, real_stale, real_ver, real_file)
        hsrv.shutdown()
        hsrv.server_close()
        ssrv.shutdown()
        ssrv.server_close()
        tsrv.shutdown()
        tsrv.server_close()


# ─────────────────────────── B 段：遮罩渲染（CDP） ───────────────────────────

def send(ws, method, params=None, _id=[0]):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method,
                        "params": params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == _id[0]:
            return r


def ev(ws, expr):
    r = send(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    res = r.get("result", {})
    if "exceptionDetails" in res:
        return "__ERR__" + json.dumps(res["exceptionDetails"])[:240]
    return res.get("result", {}).get("value")


def wait(ws, expr, secs=40, step=0.25):
    for _ in range(int(secs / step)):
        v = ev(ws, expr)
        if v and not (isinstance(v, str) and v.startswith("__ERR__")):
            return v
        time.sleep(step)
    return None


def part_b():
    print("── B 段：主窗口下载遮罩渲染（headless Edge CDP，桩 fetch）──")
    import shutil
    proc = None
    edge = None
    shutil.rmtree(PROFILE, ignore_errors=True)   # 上次残留的 profile 会让 Edge 单实例转发
    cdp = free_port()                            # 随机 CDP 口，防上次 Edge 抢占 9431
    try:
        proc = subprocess.Popen(
            [PY, APP, "--port", str(PORT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        up = False
        for _ in range(80):
            try:
                if OPENER.open(BASE + "/api/ping", timeout=2).status == 200:
                    up = True
                    break
            except Exception:                                  # noqa: BLE001
                time.sleep(0.5)
        check("服务起来", up)
        if not up:
            return

        edge = subprocess.Popen(
            [EDGE, "--headless=new", "--remote-debugging-port=%d" % cdp,
             "--remote-allow-origins=*", "--user-data-dir=" + PROFILE,
             "--no-first-run", "--hide-scrollbars", "--disable-gpu",
             "--window-size=1500,1080", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        for _ in range(160):
            try:
                tabs = json.loads(OPENER.open(
                    "http://127.0.0.1:%d/json" % cdp, timeout=3).read())
                pg = [t for t in tabs if t.get("type") == "page"
                      and t.get("url", "").startswith("about:blank")]
                if pg:
                    ws_url = pg[0]["webSocketDebuggerUrl"]
                    break
            except Exception:                                  # noqa: BLE001
                time.sleep(0.5)
        assert ws_url, "Edge CDP 起不来"
        import websocket
        ws = websocket.create_connection(ws_url, timeout=120)
        send(ws, "Runtime.enable")
        send(ws, "Page.enable")
        send(ws, "Page.navigate", {"url": BASE + "/?noreadme=1"})
        wait(ws, "typeof pvReady==='function'", secs=30)

        # 桩掉 get()：完全掌控 pvReady 的三个请求，驱动遮罩走完整状态机
        ev(ws, """
window.__fake = {phase:'none'};
window.get = function(url){
  if(url.indexOf('/api/preview/progress')>=0){
    return Promise.resolve(JSON.parse(JSON.stringify(window.__fake)));
  }
  if(url.indexOf('/api/preview?')>=0 || /\\/api\\/preview$/.test(url)){
    return Promise.resolve({ready:false, need:16.3});
  }
  if(url.indexOf('/api/preview/fetch')>=0){
    return new Promise(function(res){ window.__fetchDone=res; });
  }
  return Promise.reject(new Error('stub'));
};
""")
        ev(ws, "pvReady(function(){})")
        ok = wait(ws, "document.getElementById('pvDl') && "
                      "document.getElementById('pvDl').style.display==='flex'", secs=10)
        check("遮罩出现", ok is True, "")

        # ① connect 阶段：扫动条 + 源主机名
        ev(ws, "window.__fake={phase:'connect',src:'gh-proxy.com'};")
        ok = wait(ws, "document.getElementById('pvDl').textContent.indexOf"
                      "('正在连接镜像源 gh-proxy.com')>=0", secs=6)
        check("connect 显示「正在连接镜像源 <主机名>」", ok is True,
              ev(ws, "document.getElementById('pvDl').textContent.slice(0,80)"))

        # ② download 阶段：确定进度条 + 百分比
        ev(ws, "window.__fake={phase:'download',got:8388608,total:16777216};")
        ok = wait(ws, "document.getElementById('pvDl').textContent.indexOf('50%')>=0",
                  secs=6)
        check("download 显示 50% 确定进度", ok is True,
              ev(ws, "document.getElementById('pvDl').textContent.slice(0,100)"))
        w = ev(ws, "(function(){var b=document.querySelector('#pvDl div div');"
                   "return b?b.style.width:'';})()")
        check("填充条宽度=50%", w == "50%", w)

        # ③ keyframes 起点：扫动条任何时刻至少露 1%
        kf = ev(ws, "document.getElementById('pvbarCss')?"
                    "document.getElementById('pvbarCss').textContent:''") or ""
        check("pvbar keyframes 起点 -37%（不再整条隐形）",
              kf.startswith("@keyframes pvbar{0%{margin-left:-37%}"), kf[:60])

        # ④ fetch 完成 → 遮罩关闭
        ev(ws, "window.__fetchDone({ok:true});")
        ok = wait(ws, "document.getElementById('pvDl').style.display==='none'", secs=6)
        check("成功后遮罩关闭", ok is True, "")

        # ⑤ 截图留档
        try:
            os.makedirs(SHOT, exist_ok=True)
            ev(ws, "window.__fake={phase:'download',got:12582912,total:16777216};"
                   "pvMask('<div style=\"font-weight:500\">首次使用需要下载预览数据</div>"
                   +"<div style=\"font-size:var(--fs-sm);color:var(--muted,#999);"
                   +"line-height:1.7\">16.3 MB · 视网速约 20~40 秒<br>"
                   +"下载后保存在本地，以后打开就是秒开</div>');")
            time.sleep(0.5)
            send(ws, "Page.captureScreenshot",
                 {"format": "png", "path": os.path.join(SHOT, "遮罩-真实进度.png"),
                  "clip": {"x": 300, "y": 200, "width": 900, "height": 500,
                           "scale": 1}})
        except Exception as e:                                 # noqa: BLE001
            print("   (截图失败：%r)" % (e,))
        ws.close()
    finally:
        for p in (proc, edge):
            if p:
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                                   capture_output=True)
                except Exception:                              # noqa: BLE001
                    pass
        shutil.rmtree(PROFILE, ignore_errors=True)


def main():
    part_a()
    part_b()
    print("── 结果：%d 过 / %d 败 ──" % (PASS, FAIL))
    return 0 if not FAIL else 2


if __name__ == "__main__":
    sys.exit(main())

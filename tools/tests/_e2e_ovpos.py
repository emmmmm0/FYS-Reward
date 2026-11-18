# -*- coding: utf-8 -*-
"""屏幕覆盖小窗「位置持久化」回归（端口 8864，不进 _run_regress 默认批次）。

玩家反馈：把小窗拖到别处，重启软件又回到默认位置。按真实路径分三段：
  A 纯拖动：frameless 拖动 → 直接关软件 → 重启开窗（位置应恢复）
  B 拖动后调设置：frameless 拖动 → /api/ctl?do=ovsave 改字号 → 关软件 → 重启
    （主进程内存里的旧 x/y 不许把子进程刚落盘的坐标覆盖掉）
  C tkinter 模式：SetWindowPos + WM_EXITSIZEMOVE（等价系统拖动结束）→ 重启

判定用「日志里的建窗坐标 + overlay.json」双证，不靠窗口句柄先后顺序。
用法：python _e2e_ovpos.py
"""
import ctypes
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from ctypes import wintypes

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PORT = 8864
BASE = "http://127.0.0.1:%d" % PORT
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
OVP = os.path.join(HERE, "data", "overlay.json")
LOG = os.path.join(HERE, "data", "startup.log")
BAK = OVP + ".e2e-bak"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
u = ctypes.windll.user32
RESULTS = []

TARGET = (700, 300)
WM_EXITSIZEMOVE = 0x0232
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def check(name, ok, extra=""):
    RESULTS.append(bool(ok))
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, extra))


def api(path, timeout=8):
    with OPENER.open(BASE + path, timeout=timeout) as r:
        return json.load(r)


def read_cfg():
    try:
        with open(OVP, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                                          # noqa: BLE001
        return {}


def write_cfg(d):
    with open(OVP, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def log_size():
    try:
        return os.path.getsize(LOG)
    except OSError:
        return 0


def log_since(mark):
    try:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            f.seek(mark)
            return f.read()
    except OSError:
        return ""


def last_build_pos(txt):
    """日志里最后一条建窗坐标：frameless / tkinter 两种子进程各一种写法。"""
    pat = re.compile(r"(?:准备创建覆盖窗口 url=\S+ |建窗 )x=(-?\d+) y=(-?\d+)")
    hits = pat.findall(txt)
    return (int(hits[-1][0]), int(hits[-1][1])) if hits else None


def reset(mode):
    d = read_cfg()
    d.update({"mode": mode, "layout": "card", "ov_ct": False,
              "x": None, "y": None, "ov_pos": "rt", "size": 30, "bg": 0.55,
              "livetxt": False})
    write_cfg(d)


def find_ov(mode):
    """按窗口枚举找（pywebview 窗按标题，原生分层窗按类名——它没有标题）。"""
    hits = []

    def cb(h, _lp):
        if mode == "tkinter":
            cls = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(h, cls, 64)
            if cls.value == "FysOverlayNative":
                hits.append(h)
        else:
            n = u.GetWindowTextLengthW(h)
            if n:
                b = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(h, b, n + 1)
                if b.value == "FYS 屏幕覆盖":
                    hits.append(h)
        return True

    u.EnumWindows(WNDENUMPROC(cb), 0)
    return hits[0] if hits else 0


def wait_ov(mode, timeout=45):
    for _ in range(int(timeout * 4)):
        h = find_ov(mode)
        if h and u.IsWindowVisible(h):
            return h
        time.sleep(0.25)
    return 0


def wait_gone(mode, timeout=20):
    for _ in range(int(timeout * 4)):
        if not find_ov(mode):
            return True
        time.sleep(0.25)
    return False


def rect(h):
    r = wintypes.RECT()
    if not u.GetWindowRect(h, ctypes.byref(r)):
        return None
    return (r.left, r.top)


def start_app():
    env = dict(os.environ)
    env["FYS_GSI_NO_WRITE"] = "1"          # 不碰真实 CS2 目录
    env["FYS_QUIET_MSG"] = "1"
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
              "http_proxy", "https_proxy", "all_proxy"):
        env.pop(k, None)
    out = open(os.path.join(os.environ.get("TEMP", HERE), "e2e_ovpos_app.log"), "ab")
    p = subprocess.Popen([PY, "fys_reward_app.py", "--port", str(PORT)],
                         cwd=HERE, stdout=out, stderr=out, env=env)
    for _ in range(80):
        try:
            api("/api/prefs", timeout=3)
            return p
        except Exception:                                      # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError("app 起不来")


def stop_app(p, mode):
    try:
        api("/api/ctl?do=close", timeout=5)     # 正常退出路径（会收小窗）
    except Exception:                                          # noqa: BLE001
        pass
    deadline = time.time() + 12
    while time.time() < deadline and p.poll() is None:
        time.sleep(0.2)
    if p.poll() is None:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                       capture_output=True, timeout=15)
    wait_gone(mode, 15)                          # 关键：别让下一段读到残留窗口
    time.sleep(0.5)


def open_and_move(mode, x, y):
    mark = log_size()
    api("/api/ctl?do=ovopen")
    h = wait_ov(mode)
    if not h:
        return 0
    time.sleep(2.5)                 # 等页面撑尺寸稳定 + 首轮落盘
    u.SetWindowPos(h, 0, x, y, 0, 0, 0x0001 | 0x0004)   # NOSIZE|NOZORDER
    if mode == "tkinter":
        u.PostMessageW(h, WM_EXITSIZEMOVE, 0, 0)        # 等价「系统拖动结束」
    time.sleep(2.5)                 # 等 1s 稳定阈值 + 落盘
    return h, mark


def run_case(name, mode, tweak=None):
    reset(mode)
    p = start_app()
    try:
        got = open_and_move(mode, *TARGET)
        if not got:
            check("%s：覆盖窗能打开" % name, False, find_ov(mode))
            return
        h, mark = got
        check("%s：开窗并挪到 %s" % (name, TARGET), rect(h) == TARGET,
              "rect=%s" % (rect(h),))
        if tweak:
            tweak()
            time.sleep(1.5)
        cfg = read_cfg()
        check("%s：overlay.json 记录新坐标" % name,
              (cfg.get("x"), cfg.get("y")) == TARGET,
              "x=%r y=%r" % (cfg.get("x"), cfg.get("y")))
    finally:
        stop_app(p, mode)

    mark2 = log_size()
    p2 = start_app()
    try:
        api("/api/ctl?do=ovopen")
        h2 = wait_ov(mode)
        time.sleep(2.0)
        built = last_build_pos(log_since(mark2))
        check("%s：重启后按保存坐标建窗" % name, built == TARGET, "日志建窗=%s" % (built,))
        check("%s：重启后窗口实际位置" % name, bool(h2) and rect(h2) == TARGET,
              "rect=%s" % (rect(h2) if h2 else None,))
        cfg2 = read_cfg()
        check("%s：重启后配置未被重置" % name,
              (cfg2.get("x"), cfg2.get("y")) == TARGET,
              "x=%r y=%r" % (cfg2.get("x"), cfg2.get("y")))
    finally:
        stop_app(p2, mode)


def main():
    subprocess.run(["taskkill", "/F", "/IM", "FYS-Reward.exe"], capture_output=True)
    if os.path.exists(OVP):
        shutil.copy2(OVP, BAK)
    try:
        run_case("A 纯拖动", "frameless")
        run_case("B 拖动后调字号", "frameless",
                 lambda: api("/api/ctl?do=ovsave&cfg="
                             + urllib.parse.quote('{"size":32}')))
        run_case("C tkinter 拖动", "tkinter")
    finally:
        subprocess.run(["taskkill", "/F", "/IM", "FYS-Reward.exe"],
                       capture_output=True)
        if os.path.exists(BAK):
            shutil.copy2(BAK, OVP)
            os.remove(BAK)
    ok = sum(RESULTS)
    print("== %d/%d 通过 ==" % (ok, len(RESULTS)))
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

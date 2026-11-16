# -*- coding: utf-8 -*-
"""第三批性能探针：覆盖小窗内存回落 / 反复开关与切换布局的累积泄漏检测。

只读测量，不改项目文件。
"""
import ctypes
import ctypes.wintypes as wt
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXE = os.path.join(ROOT, "云朵小铺-FYS通关奖励看板", "FYS-Reward.exe")

SNAP_PS = (
    "Get-Process | Where-Object { $_.ProcessName -match 'FYS|msedgewebview2' } | "
    "ForEach-Object { $_.ProcessName + '|' + $_.Id + '|' + "
    "[math]::Round($_.WorkingSet64/1MB,1) }"
)


def ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True)
    return r.stdout.decode("utf-8", "replace").strip()


def kill():
    out = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True) \
        .stdout.decode("gbk", "replace")
    for l in out.splitlines():
        if l.startswith('"FYS-Reward.exe"'):
            subprocess.run(["taskkill", "/F", "/T", "/PID", l.split(",")[1].strip('"')],
                           capture_output=True)


def snapshot():
    """返回 (进程数, 合计MB, FYS-only MB)"""
    out = ps(SNAP_PS)
    rows = [l.split("|") for l in out.splitlines() if "|" in l]
    tot = sum(float(r[2]) for r in rows)
    fys = sum(float(r[2]) for r in rows if r[0].startswith("FYS"))
    return len(rows), tot, fys


# ---- 用 Win32 直接读 FYS-Reward 的 CPU 时间（PowerShell 的 Sum 在某些写法下返回空）----
class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wt.DWORD), ("dwHighDateTime", wt.DWORD)]


def fys_pids():
    out = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True) \
        .stdout.decode("gbk", "replace")
    return [int(l.split(",")[1].strip('"')) for l in out.splitlines()
            if l.startswith('"FYS-Reward.exe"')]


def cpu_seconds():
    k32 = ctypes.windll.kernel32
    total = 0.0
    for pid in fys_pids():
        h = k32.OpenProcess(0x1000 | 0x0400, False, pid)   # QUERY_LIMITED|QUERY_INFO
        if not h:
            continue
        c, e, k, u = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                              ctypes.byref(k), ctypes.byref(u)):
            def to_s(ft):
                return (ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 1e7
            total += to_s(k) + to_s(u)
        k32.CloseHandle(h)
    return total


def main():
    kill()
    time.sleep(1)
    tmp = tempfile.mkdtemp(prefix="fys_p3_")
    dst = os.path.join(tmp, "FYS-Reward.exe")
    shutil.copy2(EXE, dst)
    t0 = time.time()
    subprocess.Popen([dst], cwd=tmp, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    port, logp = None, os.path.join(tmp, "data", "startup.log")
    while time.time() - t0 < 90:
        if os.path.exists(logp):
            try:
                m = re.search(r"本地服务已启动 http://127\.0\.0\.1:(\d+)/",
                              open(logp, encoding="utf-8", errors="ignore").read())
                if m:
                    port = int(m.group(1))
                    break
            except OSError:
                pass
        time.sleep(0.1)
    if not port:
        print("没抓到端口")
        kill()
        return 1
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = "http://127.0.0.1:%d" % port
    for _ in range(60):
        try:
            op.open(base + "/api/prefs", timeout=5).read()
            break
        except Exception:
            time.sleep(0.5)

    def ctl(q):
        try:
            return op.open(base + "/api/ctl?do=" + q, timeout=25).read().decode("utf-8")[:70]
        except Exception as e:
            return "ERR %s" % e

    def show(tag):
        n, tot, fys = snapshot()
        print("  %-26s 进程 %2d  合计 %6.0f MB   (FYS %.0f MB)" % (tag, n, tot, fys))
        return tot

    print("\n== 基线 ==")
    time.sleep(8)
    base_mem = show("启动稳定后")

    print("\n== A. 开覆盖后内存回落观察（同一实例，等 30 秒）==")
    print("  ovopen ->", ctl("ovopen"))
    for w in (5, 15, 30):
        time.sleep(w if w == 5 else w - (5 if w == 15 else 15))
        show("开覆盖 +%ds" % w)

    print("\n== B. 反复 关/开 覆盖小窗 5 轮 ==")
    for i in range(1, 6):
        ctl("ovclose")
        time.sleep(3)
        ctl("ovopen")
        time.sleep(5)
        show("第 %d 轮 开关后" % i)
    ctl("ovclose")
    time.sleep(5)
    show("全部关闭后")

    print("\n== C. 反复切换覆盖布局 6 次（走 ov_restart 重建路径）==")
    ctl("ovopen")
    time.sleep(5)
    show("开覆盖")
    import json as _json
    import urllib.parse as _up
    for i, lay in enumerate(["card", "compact", "iconic", "card", "compact", "iconic"], 1):
        cfg = _up.quote(_json.dumps({"layout": lay}))
        ctl("ovsave&cfg=" + cfg)
        time.sleep(4)
        show("切到 %-8s(%d)" % (lay, i))
    ctl("ovclose")
    time.sleep(5)
    show("关闭后")

    print("\n== D. 空闲 CPU（12 秒）==")
    c1 = cpu_seconds()
    time.sleep(12)
    c2 = cpu_seconds()
    print("  CPU 累计 %.3f -> %.3f s   => 空闲占用 %.2f%%" % (c1, c2, (c2 - c1) / 12.0 * 100))

    kill()
    time.sleep(1)
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

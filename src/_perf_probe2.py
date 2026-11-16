# -*- coding: utf-8 -*-
"""第二批性能探针：空闲 CPU + 覆盖小窗内存增量 + 各视图加载耗时。只读测量。"""
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
CPU_PS = ("(Get-Process -Name FYS-Reward | Measure-Object -Property TotalProcessorTime -Sum)"
          ".Sum.TotalSeconds")


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


def snapshot(tag):
    out = ps(SNAP_PS)
    rows = [l.split("|") for l in out.splitlines() if "|" in l]
    tot = sum(float(r[2]) for r in rows)
    print("  %-14s 进程 %2d 个   合计 %5.0f MB" % (tag, len(rows), tot))
    return tot


def main():
    kill()
    time.sleep(1)
    tmp = tempfile.mkdtemp(prefix="fys_p2_")
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
    print("端口 %d  就绪耗时 %.2f s" % (port, time.time() - t0))
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = "http://127.0.0.1:%d" % port
    for _ in range(60):
        try:
            op.open(base + "/api/prefs", timeout=5).read()
            break
        except Exception:
            time.sleep(0.5)

    print("\n== 内存 ==")
    m0 = snapshot("仅主窗")
    c1 = ps(CPU_PS)
    time.sleep(10)
    c2 = ps(CPU_PS)
    print("  CPU 累计 %.3f -> %.3f s" % (float(c1 or 0), float(c2 or 0)))
    try:
        print("  => 空闲 CPU 占用 %.2f%%（含每秒轮询 /api/status）"
              % ((float(c2) - float(c1)) / 10.0 * 100.0))
    except Exception as e:
        print("  CPU 解析失败:", e)

    print("\n== 打开覆盖小窗 ==")
    try:
        r = op.open(base + "/api/ctl?do=ovopen", timeout=25).read().decode("utf-8")
        print("  ovopen ->", r[:130])
    except Exception as e:
        print("  ovopen 失败:", e)
    time.sleep(7)
    m1 = snapshot("开覆盖后")
    print("  => 覆盖小窗额外占用 %.0f MB" % (m1 - m0))

    print("\n== 各接口/页面耗时 ==")
    paths = ["/api/status", "/api/servers", "/api/maplib", "/api/rewards",
             "/api/mapnames", "/api/about", "/api/upddiff", "/", "/overlay"]
    for p in paths:
        s = time.time()
        try:
            r = op.open(base + p, timeout=30)
            n = len(r.read())
            print("  %-16s %7.0f ms  %8d B" % (p, (time.time() - s) * 1000, n))
        except Exception as e:
            print("  %-16s 失败 %s" % (p, e))

    kill()
    time.sleep(1)
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

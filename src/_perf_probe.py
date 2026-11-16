# -*- coding: utf-8 -*-
"""性能探针：实测打包 exe 的冷启动耗时 / 首屏可用时间 / 稳态内存 / 稳态 CPU。

用法：
    python _perf_probe.py                    # 用发行目录里的 exe
    python _perf_probe.py <exe路径>
只读测量，不改任何项目文件（只在 %TEMP% 建临时目录跑）。
"""
import json
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
DEFAULT_EXE = os.path.join(ROOT, "云朵小铺-FYS通关奖励看板", "FYS-Reward.exe")

PS_MEM = (
    "Get-Process -Name FYS-Reward -ErrorAction SilentlyContinue | "
    "Select-Object -First 1 -ExpandProperty WorkingSet64"
)
PS_CPU = (
    "Get-Process -Name FYS-Reward -ErrorAction SilentlyContinue | "
    "Select-Object -First 1 -ExpandProperty TotalProcessorTime"
)
PS_LIST = (
    "Get-Process -Name FYS-Reward -ErrorAction SilentlyContinue | "
    "ForEach-Object { \"$($_.Id),$($_.WorkingSet64)\" }"
)


def ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True)
    return r.stdout.decode("utf-8", "replace").strip()


def kill_all():
    r = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True)
    out = r.stdout.decode("gbk", "replace")
    pids = [l.split(",")[1].strip('"') for l in out.splitlines()
            if l.startswith('"FYS-Reward.exe"')]
    for p in pids:
        subprocess.run(["taskkill", "/F", "/T", "/PID", p], capture_output=True)
    return pids


def main():
    exe = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXE
    if not os.path.exists(exe):
        print("找不到 exe:", exe)
        return 1
    print("被测 exe: %s  (%.1f MB)" % (exe, os.path.getsize(exe) / 1048576.0))

    kill_all()
    tmp = tempfile.mkdtemp(prefix="fys_perf_")
    dst = os.path.join(tmp, "FYS-Reward.exe")
    shutil.copy2(exe, dst)
    print("临时运行目录: %s" % os.path.basename(tmp))

    t0 = time.time()
    proc = subprocess.Popen([dst], cwd=tmp,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 1) 找端口：轮询 startup.log
    port = None
    logp = os.path.join(tmp, "data", "startup.log")
    while time.time() - t0 < 90:
        if os.path.exists(logp):
            try:
                with open(logp, "r", encoding="utf-8", errors="ignore") as f:
                    m = re.search(r"本地服务已启动 http://127\.0\.0\.1:(\d+)/", f.read())
                if m:
                    port = int(m.group(1))
                    break
            except OSError:
                pass
        if proc.poll() is not None:
            print("[!] 进程已退出，returncode=%s" % proc.returncode)
            return 1
        time.sleep(0.05)
    if not port:
        print("[!] 90 秒内没抓到服务端口")
        return 1
    t_port = time.time() - t0

    # 2) 首屏可用：/api/status 首次 200
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = "http://127.0.0.1:%d/api/status" % port
    t_ok = None
    first_body = None
    while time.time() - t0 < 120:
        try:
            r = op.open(url, timeout=5)
            if r.status == 200:
                first_body = r.read()
                t_ok = time.time() - t0
                break
        except Exception:
            pass
        time.sleep(0.05)
    print("\n== 启动 ==")
    print("  服务端口就绪 : %.2f s  (首次尝试即 %s)" % (t_port, port))
    print("  首屏可请求   : %s" % ("%.2f s" % t_ok if t_ok else "超时"))
    if first_body:
        try:
            d = json.loads(first_body.decode("utf-8"))
            print("  首屏返回 keys: %s" % ",".join(sorted(d.keys())[:12]))
        except Exception:
            pass

    # 3) 稳态：静置 12 秒后测内存 + CPU
    time.sleep(12)
    mem1 = ps(PS_MEM)
    cpu1 = ps(PS_CPU)
    time.sleep(10)
    mem2 = ps(PS_MEM)
    cpu2 = ps(PS_CPU)

    def to_sec(s):
        # PowerShell TimeSpan 形如 00:00:12.3456789
        try:
            h, m, sec = s.split(":")
            return int(h) * 3600 + int(m) * 60 + float(sec)
        except Exception:
            return None

    print("\n== 稳态（静置后，无操作）==")
    print("  工作集内存   : %s MB" % ("%.1f" % (int(mem2) / 1048576.0) if mem2.isdigit() else mem2))
    c1, c2 = to_sec(cpu1), to_sec(cpu2)
    if c1 is not None and c2 is not None:
        print("  空闲 CPU 占用: %.2f%%  (10 秒内累计 %.2f s CPU 时间)" %
              ((c2 - c1) / 10.0 * 100.0, c2 - c1))

    # 4) 子进程清单（pywebview 会拉起 Edge WebView2 的多个进程）
    print("\n== 相关进程 ==")
    out = ps("Get-Process | Where-Object { $_.ProcessName -match 'FYS|msedgewebview|WebView' } | "
             "Select-Object ProcessName,Id,@{n='MB';e={[math]::Round($_.WorkingSet64/1MB,1)}} | "
             "Sort-Object -Property MB -Descending | Format-Table -AutoSize | Out-String -Width 120")
    print(out)

    # 5) 轮询频率采样：10 秒内 /api/status 被请求的响应时间分布
    print("== 单次 /api/status 响应耗时（采样 8 次）==")
    ts = []
    for _ in range(8):
        s = time.time()
        try:
            op.open(url, timeout=5).read()
        except Exception:
            pass
        ts.append((time.time() - s) * 1000)
    print("  %s ms   (min %.0f / max %.0f)" %
          (" ".join("%.0f" % x for x in ts), min(ts), max(ts)))

    print("\n清理：结束进程并删除临时目录")
    kill_all()
    time.sleep(1)
    try:
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

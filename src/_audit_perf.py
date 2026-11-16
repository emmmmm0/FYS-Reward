# -*- coding: utf-8 -*-
"""全维度审查 · 性能测量：起真实实例，测各 API 首包/均耗时与负载大小。端口 9434。"""
import json
import os
import subprocess
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 9434
BASE = "http://127.0.0.1:%d" % PORT
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def timed(path, n=3):
    ts, size = [], 0
    for _ in range(n):
        t0 = time.perf_counter()
        r = OPENER.open(BASE + path, timeout=60)
        b = r.read()
        ts.append((time.perf_counter() - t0) * 1000)
        size = len(b)
    return min(ts), sum(ts) / len(ts), size


def main():
    proc = subprocess.Popen(
        [PY, os.path.join(HERE, "fys_reward_app.py"), "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(90):
            try:
                OPENER.open(BASE + "/api/prefs", timeout=2).read()
                break
            except Exception:
                time.sleep(0.5)
        time.sleep(3)  # 等后台索引加载
        rows = []
        for p in ["/", "/api/prefs", "/api/status", "/api/about",
                  "/api/maplib", "/api/updlog", "/api/upddiff",
                  "/api/ovcfg", "/api/exg"]:
            try:
                mn, av, sz = timed(p)
                rows.append((p, mn, av, sz))
            except Exception as e:
                rows.append((p, -1, -1, str(e)[:60]))
        print("%-14s %9s %9s %10s" % ("endpoint", "min(ms)", "avg(ms)", "bytes"))
        for p, mn, av, sz in rows:
            print("%-14s %9.1f %9.1f %10s" % (p, mn, av, "{:,}".format(sz) if isinstance(sz,int) else sz))
        # maplib 负载细节
        d = json.loads(OPENER.open(BASE + "/api/maplib", timeout=60).read())
        print("\nmaplib keys:", list(d.keys())[:8])
        print("maps:", len(d.get("maps") or d.get("all") or []),
              "| cfg keys:", len(d.get("cfg") or {}))
    finally:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
        except Exception:
            pass
        time.sleep(1.5)


if __name__ == "__main__":
    main()

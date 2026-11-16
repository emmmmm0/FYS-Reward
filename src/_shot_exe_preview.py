# -*- coding: utf-8 -*-
"""终验：直接跑打包出的 FYS-Reward.exe，截软件内「实体预览」页。"""
import io
import os
import re
import shutil
import subprocess
import sys
import time

W = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
EXE = os.path.join(W, "fys-reward", "dist4", "FYS-Reward.exe")
BOX = os.path.join(W, "_build_tmp", "exe_shot")
SHOT = os.path.join(W, "验证截图-软件实体预览")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TASKKILL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")

shutil.rmtree(BOX, ignore_errors=True)
os.makedirs(BOX)
exe = os.path.join(BOX, "FYS-Reward.exe")
shutil.copy2(EXE, exe)

DETACHED = 0x00000008 | 0x00000200
proc = subprocess.Popen([exe], cwd=BOX, creationflags=DETACHED,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
port = None
logp = os.path.join(BOX, "data", "startup.log")
t0 = time.time()
try:
    while time.time() - t0 < 70:
        time.sleep(1)
        if os.path.exists(logp):
            m = re.findall(r"127\.0\.0\.1:(\d+)", io.open(logp, encoding="utf-8",
                                                         errors="replace").read())
            if m:
                port = m[-1]
                break
    if not port:
        print("! 等不到服务端口")
        sys.exit(1)
    time.sleep(2)
    print("exe 已启动，端口", port)

    CASES = [
        ("08-exe本体-预览页-夜幕护眼", "/?view=pre&theme=N&map=ze_evil_mansion", 17000),
        ("09-exe本体-服务器页", "/?view=srv&theme=E", 11000),
    ]
    prof = os.path.join(SHOT, "_prof_exe")
    for name, qs, wait in CASES:
        out = os.path.join(SHOT, name + ".png")
        if os.path.exists(out):
            os.remove(out)
        r = subprocess.run([EDGE, "--headless=new", "--disable-gpu-sandbox",
                            "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
                            "--hide-scrollbars", "--no-first-run",
                            "--user-data-dir=" + prof, "--window-size=1330,720",
                            "--virtual-time-budget=%d" % wait,
                            "--screenshot=" + out,
                            "http://127.0.0.1:%s%s" % (port, qs)],
                           capture_output=True, text=True, timeout=300)
        ok = os.path.exists(out) and os.path.getsize(out) > 8000
        print("  %-30s %s" % (name, ("OK  %.0f KB" % (os.path.getsize(out) / 1024))
                              if ok else "FAIL"))
finally:
    subprocess.run([TASKKILL, "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    time.sleep(1.5)
    print("exe 已关闭")

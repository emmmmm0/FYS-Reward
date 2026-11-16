# -*- coding: utf-8 -*-
"""诊断 v2：apply 后立刻抓 cmd.exe 的完整命令行。"""
import io
import json
import os
import re
import subprocess
import time
import urllib.request

WS = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
TEST = os.path.join(WS, "_updtest")
EXE = os.path.join(TEST, "FYS-Reward.exe")

subprocess.run(["taskkill", "/F", "/T", "/IM", "FYS-Reward.exe"], capture_output=True)
time.sleep(1)
subprocess.Popen([EXE], cwd=TEST, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, creationflags=0x08000000)
port = None
for _ in range(30):
    time.sleep(2)
    try:
        log = io.open(os.path.join(TEST, "data", "startup.log"),
                      encoding="utf-8", errors="replace").read()
        mm = re.findall(r"本地服务已启动 http://127\.0\.0\.1:(\d+)/", log)
        if mm:
            port = mm[-1]
            break
    except OSError:
        pass
print("端口", port)

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
r = json.loads(op.open("http://127.0.0.1:%s/api/update/apply" % port, timeout=300).read())
print("apply:", r)

ps = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'cmd|tasklist|ping|find'} "
     "| Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List"],
    capture_output=True).stdout.decode("gbk", "replace")
print(ps)
print("bat 在:", os.path.exists(os.path.join(TEST, "_update.bat")))
subprocess.run(["taskkill", "/F", "/T", "/IM", "FYS-Reward.exe"], capture_output=True)

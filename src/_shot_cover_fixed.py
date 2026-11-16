# -*- coding: utf-8 -*-
"""拍一张「老用户更新后」场景的地图库实拍：空目录里的新 exe + 真实浏览器渲染。

和 _e2e_cover_bundled.py 同一沙箱（除 exe 外什么都没有的目录），区别是它只
断言接口，这里让浏览器真的把地图库画出来截成图，肉眼确认封面底纹回来了。

用法：python _shot_cover_fixed.py
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.dirname(HERE)
EXE = os.path.join(W, "云朵小铺-FYS通关奖励看板", "FYS-Reward.exe")
PORT = 8846
BASE = "http://127.0.0.1:%d" % PORT
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
SANDBOX = os.path.join(HERE, "_cover_shot_tmp")
OUT_DIR = os.path.join(W, "验证截图-封面修复")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
# 截图路径不能含中文（Edge 会 0x5 失败）：先写 ASCII 临时路径再拷回
TMP_PNG = os.path.join(os.environ.get("TEMP", "."), "fys_cover_fixed.png")

os.makedirs(OUT_DIR, exist_ok=True)
shutil.rmtree(SANDBOX, ignore_errors=True)
os.makedirs(SANDBOX, exist_ok=True)
dst = os.path.join(SANDBOX, os.path.basename(EXE))
shutil.copy2(EXE, dst)
print("沙箱（无 cover 目录）：", SANDBOX)
assert not os.path.isdir(os.path.join(SANDBOX, "cover")), "沙箱里不该有 cover"

proc = subprocess.Popen([dst, "--port", str(PORT)], cwd=SANDBOX,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(120):
        try:
            OPENER.open(BASE + "/api/status", timeout=3).read()
            break
        except Exception:                                        # noqa: BLE001
            time.sleep(0.5)
    print("exe 就绪，截图…")
    if os.path.exists(TMP_PNG):
        os.remove(TMP_PNG)
    # --virtual-time-budget 让页面跑够时间：地图库要等索引拉完才铺封面
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                    "--hide-scrollbars", "--window-size=1180,1000",
                    "--virtual-time-budget=12000",
                    "--screenshot=" + TMP_PNG, BASE + "/?view=lib&noreadme"],
                   capture_output=True, timeout=90)
    if os.path.exists(TMP_PNG) and os.path.getsize(TMP_PNG) > 1000:
        out = os.path.join(OUT_DIR, "01-更新后地图库封面.png")
        shutil.copy2(TMP_PNG, out)
        print("截图 →", out, "(%d bytes)" % os.path.getsize(out))
    else:
        print("截图失败：没产出文件")
finally:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   capture_output=True, timeout=15)

# -*- coding: utf-8 -*-
"""复现「恢复默认外观」三个偏好并发写入丢失（端口 9462 / CDP 9463）。"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

import _qa_usecase as Q

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT, CDP = 9462, 9463
BASE = "http://127.0.0.1:%d" % PORT
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PROF = os.path.join(os.environ["TEMP"], "_qa_reset_9463")
PREFS = os.path.join(HERE, "data", "ui_prefs.json")


def prefs():
    return json.load(open(PREFS, encoding="utf-8"))


def main():
    shutil.copy2(PREFS, PREFS + ".qa_bak")
    p = subprocess.Popen([PY, os.path.join(HERE, "fys_reward_app.py"), "--port", str(PORT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    e = None
    b = None
    try:
        for _ in range(80):
            try:
                OP.open(BASE + "/api/prefs", timeout=2).read()
                break
            except Exception:                                  # noqa: BLE001
                time.sleep(0.5)
        e = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
                              "--remote-allow-origins=*", "--user-data-dir=" + PROF,
                              "--no-first-run", "about:blank"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        url = None
        for _ in range(80):
            try:
                tabs = json.load(OP.open("http://127.0.0.1:%d/json" % CDP, timeout=2))
                pg = [t for t in tabs if t.get("type") == "page"]
                if pg:
                    url = pg[0]["webSocketDebuggerUrl"]
                    break
            except Exception:                                  # noqa: BLE001
                time.sleep(0.5)
        b = Q.Browser(url)
        for m in ("Runtime.enable", "Network.enable", "Page.enable", "Log.enable"):
            b.send(m)
        b.send("Page.navigate", {"url": BASE + "/"})
        b.wait("document.readyState==='complete'", 30)
        b.wait("document.querySelectorAll('#themes .tcard').length>0", 30)
        b.pump(1.0)
        print("起始 prefs:", {k: prefs().get(k) for k in ("theme", "bg", "sticker")})
        # 先改成非默认：夜幕 + 冒险出发 + 非猫贴纸（逐个点，避免测试本身并发）
        b.js("applyTheme('N',true)")
        b.pump(0.6)
        b.js("applyBG('run',true)")
        b.pump(0.6)
        b.js("applySticker('dog',true)")
        b.pump(0.8)
        print("改成非默认:", {k: prefs().get(k) for k in ("theme", "bg", "sticker")})
        for i in range(3):
            b.js("document.getElementById('btnResetLook').click()")
            b.pump(1.5)
            got = {k: prefs().get(k) for k in ("theme", "bg", "sticker")}
            bad = [k for k, want in (("theme", "e"), ("bg", "cloud"), ("sticker", "cat"))
                   if str(got.get(k)).lower() != want]
            print("第 %d 次点「恢复默认外观」→ %s  %s"
                  % (i + 1, got, ("❌ 未落盘: " + ",".join(bad)) if bad else "✅ 全部落盘"))
            # 重置回非默认，继续下一轮
            b.js("applyTheme('N',true)")
            b.pump(0.5)
            b.js("applyBG('run',true)")
            b.pump(0.5)
            b.js("applySticker('dog',true)")
            b.pump(0.7)
    finally:
        try:
            if b:
                b.ws.close()
        except Exception:                                      # noqa: BLE001
            pass
        for x in (e, p):
            if x:
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(x.pid)],
                                   capture_output=True)
                except Exception:                              # noqa: BLE001
                    pass
        time.sleep(1.0)
        shutil.move(PREFS + ".qa_bak", PREFS)
        print("prefs 已还原:", prefs().get("theme"), prefs().get("bg"))


main()

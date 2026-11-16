# -*- coding: utf-8 -*-
"""UI 验证：设置页新增的「地形缓存」行是否正确渲染（headless Edge dump-dom + 截图）。"""
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
W = os.path.dirname(HERE)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8813

import fys_reward_app as A                                          # noqa: E402
import reward_server as engine                                      # noqa: E402

A.State.engine = engine
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
port = int(A.State.url.rsplit(":", 1)[1].split("/")[0])
BASE = "http://127.0.0.1:%d" % port
print("服务 %s" % BASE)

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(40):
    try:
        op.open(BASE + "/api/status", timeout=5).read()
        break
    except Exception:                                               # noqa: BLE001
        time.sleep(1)

st = op.open(BASE + "/api/terr/info", timeout=10).read().decode("utf-8")
print("接口 /api/terr/info -> %s" % st)

prof = os.path.join(W, "验证截图-软件实体bbox", "_prof_terr")
os.makedirs(prof, exist_ok=True)
shot = os.path.join(W, "验证截图-界面巡检", "set-地形缓存行.png")
os.makedirs(os.path.dirname(shot), exist_ok=True)

r = subprocess.run([EDGE, "--headless=new", "--disable-gpu-sandbox", "--no-first-run",
                    "--user-data-dir=" + prof, "--window-size=1440,1100",
                    "--virtual-time-budget=15000",
                    "--screenshot=" + shot,
                    "--dump-dom", BASE + "/?view=set"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
dom = r.stdout or ""
print("DOM %.0f KB / 截图 %s" % (len(dom) / 1024.0,
                                ("%.0f KB" % (os.path.getsize(shot) / 1024.0))
                                if os.path.exists(shot) else "失败"))
m = re.search(r'id="abTerr"[^>]*>([^<]*)<', dom)
print("abTerr 文本       : %s" % (repr(m.group(1)) if m else "!! 未找到"))
print("含「地形缓存」标题 : %s" % ("地形缓存" in dom))
print("含清理按钮        : %s" % ('id="abTerrClear"' in dom))
print("页面有 JS 报错痕迹 : %s" % ("Uncaught" in dom))

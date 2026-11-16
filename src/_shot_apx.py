# -*- coding: utf-8 -*-
"""实拍服务器列表，验证「未收录」→ 近似命中的显示效果。"""
import os, sys, time, subprocess, json, urllib.request

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
os.chdir(os.path.join(ROOT, "fys-reward"))
sys.path.insert(0, ".")

import fys_reward_app as A
import reward_server as engine

A.State.engine = engine
engine.load_state(force=False)
PORT = 8809
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
time.sleep(1.0)

base = A.State.url.rstrip("/")
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
d = json.loads(op.open(base + "/api/servers", timeout=60).read().decode("utf-8"))

print("探测 %s | %d 台" % (d.get("at"), d.get("count")))
hit = None
for r in d.get("rows", []):
    mark = ""
    if r.get("map_approx"):
        mark = "  ★近似→%s" % r["map_approx"]
        hit = r
    print("  %-32s 关卡=%-4s 云点=%-8s 中文=%-16s%s" % (
        (r.get("map") or "—")[:30], r.get("stages") or "—",
        r.get("passes_min") if r.get("passes_min") is not None else "—",
        r.get("mapcn") or "—", mark))

OUT = os.path.join(ROOT, "验证截图-界面巡检")
img = os.path.join(OUT, "09-服务器表-未收录修复.png")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
prof = os.path.join(OUT, "_prof_apx")
cmd = [EDGE, "--headless=new", "--disable-gpu-sandbox", "--enable-unsafe-swiftshader",
       "--use-angle=swiftshader", "--no-first-run", "--user-data-dir=" + prof,
       "--window-size=1500,900", "--virtual-time-budget=16000",
       "--screenshot=" + img, base + "/?view=srv&theme=E"]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                   encoding="utf-8", errors="replace")
ok = os.path.exists(img) and os.path.getsize(img) > 20000
print()
print("截图 %s  (%s)" % ("OK" if ok else "失败",
                        "%.0f KB" % (os.path.getsize(img) / 1024) if os.path.exists(img) else "-"))
if hit:
    print("本次有近似命中 → 截图里 05# 那行应带 ≈ 标记")
else:
    print("本次 9 台都没有近似命中（地图已切换），截图仅作常规回归")

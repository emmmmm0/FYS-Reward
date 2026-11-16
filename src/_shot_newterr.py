# -*- coding: utf-8 -*-
"""抽查新补回来的地形：terr 分包能否取到 + 预览页能否渲染。

用法：python _shot_newterr.py
"""
import os, re, sys, json, time, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
W = os.path.dirname(HERE)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8810

import fys_reward_app as A          # noqa: E402
import reward_server as engine      # noqa: E402

A.State.engine = engine
engine.load_state(force=False)
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
time.sleep(0.9)
base = A.State.url.rstrip("/")
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))

lib = json.loads(op.open(base + "/api/maplib", timeout=60).read().decode("utf-8"))
by = dict((r.get("f", "").lower(), r) for r in lib.get("maps", []))
print("地图库 %d 张（仅作名字校验，工坊 ID 从 manifest 取）" % len(by))

# 工坊 ID 映射：_meshes/_manifest.json 的 key = 分类/地图名/工坊ID
man = json.load(open(os.path.join(HERE, "_ghcrawl", "_meshes", "_manifest.json"), encoding="utf-8"))
mid = {}
for key in man:
    parts = key.split("/")
    if len(parts) == 3:
        mid[parts[1].lower()] = parts[2]
print("manifest %d 张" % len(mid))

targets = ["ze_dark_sanctuary", "ze_imperium", "de_jura", "ze_resident_evil_3",
           "ze_ultrakill", "ze_rooftop_runaway3_xyy", "ze_timesink", "ze_obf_npst_v1"]
ok = bad = 0
print()
for t in targets:
    kid = mid.get(t)
    if not kid:
        print("  %-30s manifest 里没有" % t)
        continue
    b = op.open(base + "/terr/%s.js" % kid, timeout=60).read()
    # 真实格式：window.__TERR=window.__TERR||{};__TERR["<id>"]="<base64>"
    good = len(b) > 2000 and (('__TERR["%s"]' % kid).encode() in b[:140])
    ok += 1 if good else 0
    bad += 0 if good else 1
    print("  %-30s id=%-11s %9.1f KB  %s" % (t, kid, len(b) / 1024, "OK" if good else "!! 内容可疑"))

print()
print("HTTP 抽查：%d 张正常 / %d 张异常" % (ok, bad))

# ── 实拍见证：288 万面的巨图（新补）应能渲染出地形
OUT = os.path.join(W, "验证截图-界面巡检")
IMG = os.path.join(OUT, "12-补爬后新地形-暗黑圣域.png")
if os.path.exists(IMG):
    os.remove(IMG)
r = subprocess.run(
    [EDGE, "--headless=new", "--disable-gpu-sandbox", "--enable-unsafe-swiftshader",
     "--use-angle=swiftshader", "--hide-scrollbars", "--no-first-run",
     "--user-data-dir=" + os.path.join(OUT, "_prof_nt"), "--window-size=1400,820",
     "--virtual-time-budget=30000", "--dump-dom", "--screenshot=" + IMG,
     base + "/preview3d?map=ze_dark_sanctuary"],
    capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
html = r.stdout or ""
m = re.search(r"(\d[\d.,]*k?)\s*面", html)
print()
print("截图 %s (%.0f KB)" % ("OK" if os.path.exists(IMG) else "失败",
                            os.path.getsize(IMG) / 1024 if os.path.exists(IMG) else 0))
print("DOM 面数:", m.group(0) if m else "未抓到")
# 模板里本来就带这段提示文案，出现次数 >1 才说明真的走了「缺失」分支
print("「地形文件缺失」出现次数:", html.count("地形文件缺失"))

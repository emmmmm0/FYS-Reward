# -*- coding: utf-8 -*-
"""实拍验证：「当前地图」卡片右侧按钮在「未在服务器内」时改为「📚 去地图库」，
   点击（等价深链 ?view=lib&map=ze_xxx）会跳到地图库并定位到那张图。"""
import os, sys, time, subprocess, re

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
os.chdir(os.path.join(ROOT, "fys-reward"))
sys.path.insert(0, ".")

import fys_reward_app as A
import reward_server as engine

A.State.engine = engine
engine.load_state(force=False)
PORT = 8807
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
time.sleep(0.9)
base = A.State.url.rstrip("/")

OUT = os.path.join(ROOT, "验证截图-界面巡检")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
prof = os.path.join(OUT, "_prof_pvlib")


def edge(url, budget=16000, shot=None, dump=False):
    cmd = [EDGE, "--headless=new", "--disable-gpu-sandbox", "--enable-unsafe-swiftshader",
           "--use-angle=swiftshader", "--no-first-run", "--user-data-dir=" + prof,
           "--window-size=1500,900", "--virtual-time-budget=%d" % budget]
    if shot:
        cmd.append("--screenshot=" + shot)
    if dump:
        cmd.append("--dump-dom")
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                       encoding="utf-8", errors="replace")
    return r.stdout or ""


print("=== 1) 主界面（当前不在服务器内）→ 按钮应为「📚 去地图库」 ===")
html = edge(base + "/?view=srv&theme=E", dump=True)
m = re.search(r'<button class="btn" id="pvNow"[^>]*>([^<]*)</button>', html)
m2 = re.search(r'<button class="btn" id="pvNow"[^>]*data-k="([^"]*)"', html)
title = re.search(r'id="pvNow"[^>]*title="([^"]*)"', html)
print("  按钮文案 :", (m.group(1) if m else "（未找到）"))
print("  data-k   :", (m2.group(1) if m2 else "（无）"))
print("  title    :", (title.group(1) if title else "（无）"))
print("  含「未在服务器内」:", "未在服务器内" in html)
ok1 = bool(m) and "去地图库" in (m.group(1) or "")
print("  ->", "OK" if ok1 else "失败")

print()
print("=== 2) 深链 ?view=lib&map=ze_backrooms_insomnia → 定位到该图 ===")
html2 = edge(base + "/?view=lib&map=ze_backrooms_insomnia&theme=E", budget=20000, dump=True)
hit = re.search(r'class="libRow on[^"]*"[^>]*data-f="([^"]+)"', html2)
flash = 'class="libRow on flash"' in html2 or 'on flash' in html2
cnt = re.search(r'id="libCnt"[^>]*>([^<]*)<', html2)
det = "关卡数" in html2 and "ze_backrooms_insomnia" in html2
print("  高亮选中行 :", (hit.group(1) if hit else "（无）"))
print("  行内闪烁类 :", flash)
print("  计数       :", (cnt.group(1) if cnt else "（无）"))
print("  右侧详情已渲染:", det)
ok2 = bool(hit) and hit.group(1) == "ze_backrooms_insomnia" and det
print("  ->", "OK" if ok2 else "失败")

print()
print("=== 3) 深链指向不存在的图 → 不崩、退回全部列表 ===")
html3 = edge(base + "/?view=lib&map=ze_no_such_map_xyz&theme=E", budget=20000, dump=True)
cnt3 = re.search(r'id="libCnt"[^>]*>([^<]*)<', html3)
print("  计数       :", (cnt3.group(1) if cnt3 else "（无）"))
print("  列表有行   :", 'class="libRow' in html3)
ok3 = bool(cnt3) and 'libRow' in html3 and '暂无' not in (cnt3.group(1) or '')
print("  ->", "OK" if ok3 else "失败")

print()
print("=== 4) 截图 ===")
s1 = os.path.join(OUT, "10-当前地图卡-去地图库按钮.png")
s2 = os.path.join(OUT, "11-地图库-定位到当前图.png")
edge(base + "/?view=srv&theme=E", budget=14000, shot=s1)
edge(base + "/?view=lib&map=ze_backrooms_insomnia&theme=E", budget=20000, shot=s2)
for p in (s1, s2):
    print("  %s  %s" % ("OK " if os.path.exists(p) else "失败",
                       "%.0f KB  %s" % (os.path.getsize(p) / 1024, os.path.basename(p))
                       if os.path.exists(p) else os.path.basename(p)))

print()
print("结果：", "全部通过 ✓" if (ok1 and ok2 and ok3) else "有失败项 ✗")

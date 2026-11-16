# -*- coding: utf-8 -*-
"""实拍验证：卡片右侧按钮**固定为「📚 去地图库」**（不再随是否在服内切换文案）。
   在服内 / 不在服内两种状态下都应是「去地图库」，且 title 指向正确的目标图。"""
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
prof = os.path.join(OUT, "_prof_pvlib2")


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


def probe(html):
    txt = re.search(r'<button class="btn" id="pvNow"[^>]*>([^<]*)</button>', html)
    dk = re.search(r'id="pvNow"[^>]*data-k="([^"]*)"', html)
    tt = re.search(r'id="pvNow"[^>]*title="([^"]*)"', html)
    return ((txt.group(1).strip() if txt else "（未找到）"),
            (dk.group(1) if dk else "（无）"),
            (tt.group(1) if tt else "（无）"))


# ── 阶段 A：伪造「已在服务器内 + 认出地图」，按钮文案必须仍是「去地图库」 ──
_real = engine.resolve
FAKE = dict(_real())
FAKE.update({"ok": True, "state": "ok", "state_text": "已在服务器内",
             "map": "ze_backrooms_insomnia", "mapcn": "后室2:失眠症"})
engine.resolve = lambda: dict(FAKE)

print("=== 1) 在服务器内（map=ze_backrooms_insomnia）→ 按钮应仍是「📚 去地图库」 ===")
html = edge(base + "/?view=srv&theme=E", dump=True)
t, dk, tt = probe(html)
print("  按钮文案 :", t)
print("  data-k   :", dk)
print("  title    :", tt)
ok1 = ("去地图库" in t) and (dk == "ze_backrooms_insomnia") and ("ze_backrooms_insomnia" in tt)
print("  ->", "OK" if ok1 else "失败")
s1 = os.path.join(OUT, "13-在服内-按钮仍是去地图库.png")
edge(base + "/?view=srv&theme=E", budget=14000, shot=s1)

# ── 阶段 B：恢复真实状态（本机 CS2 未运行 = 不在服务器内），文案同样应是「去地图库」 ──
engine.resolve = _real

print()
print("=== 2) 不在服务器内 → 按钮同样应是「📚 去地图库」 ===")
html2 = edge(base + "/?view=srv&theme=E", dump=True)
t2, dk2, tt2 = probe(html2)
print("  按钮文案 :", t2)
print("  data-k   :", dk2)
print("  title    :", tt2)
ok2 = ("去地图库" in t2) and ("实体预览" not in t2)
print("  ->", "OK" if ok2 else "失败")
s2 = os.path.join(OUT, "14-不在服内-按钮仍是去地图库.png")
edge(base + "/?view=srv&theme=E", budget=14000, shot=s2)

print()
print("=== 3) 回归：深链 ?view=lib&map=ze_backrooms_insomnia 仍能定位 ===")
html3 = edge(base + "/?view=lib&map=ze_backrooms_insomnia&theme=E", budget=20000, dump=True)
hit = re.search(r'class="libRow on[^"]*"[^>]*data-f="([^"]+)"', html3)
print("  高亮选中行 :", (hit.group(1) if hit else "（无）"))
ok3 = bool(hit) and hit.group(1) == "ze_backrooms_insomnia"
print("  ->", "OK" if ok3 else "失败")

print()
print("=== 4) 截图 ===")
for p in (s1, s2):
    print("  %s  %s" % ("OK " if os.path.exists(p) else "失败",
                       "%.0f KB  %s" % (os.path.getsize(p) / 1024, os.path.basename(p))
                       if os.path.exists(p) else os.path.basename(p)))

print()
print("结果：", "全部通过 ✓" if (ok1 and ok2 and ok3) else "有失败项 ✗")

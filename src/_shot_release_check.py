# -*- coding: utf-8 -*-
"""发布前最后一轮改动验证：
   ① /api/servers 顶层有 web 字段（主界面「官网同步」胶囊的数据源）
   ② 地图库近似名定位：用「服务器实名」ze_minecraft_hortus_de_escapism（少一个 o）
      去查，应命中官方登记名 ze_minecraft_hortus_de_escapismo 并给出提示
   ③ 指向不存在的图 → 列表照常显示但「不自动选中第一张」（右侧不再显示别的图）
   ④ 图例新增「≈ 地图名按官方登记名近似匹配」
   ⑤ 卡片按钮恒为「📚 去地图库」"""
import os, sys, time, subprocess, re, json, urllib.request

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
os.chdir(os.path.join(ROOT, "fys-reward"))
sys.path.insert(0, ".")

import fys_reward_app as A
import reward_server as engine

A.State.engine = engine
engine.load_state(force=False)
PORT = 8808
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
time.sleep(0.9)
base = A.State.url.rstrip("/")

OUT = os.path.join(ROOT, "验证截图-界面巡检")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
prof = os.path.join(OUT, "_prof_rel")


def edge(url, budget=20000, shot=None, dump=False):
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


op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
oks = []

print("=== 1) /api/servers 顶层 web 字段（「官网同步」胶囊数据源） ===")
sv = json.loads(op.open(base + "/api/servers", timeout=90).read().decode("utf-8"))
has_web = "web" in sv
w = sv.get("web") or {}
print("  web 键存在 :", has_web)
print("  web 内容   :", json.dumps(w, ensure_ascii=False)[:150])
ok1 = has_web
oks.append(("servers.web", ok1))

print()
print("=== 2) 地图库近似名定位（服务器实名少一个 o → 官方登记名带 o） ===")
REAL = "ze_minecraft_hortus_de_escapism"
REG = "ze_minecraft_hortus_de_escapismo"
html = edge(base + "/?view=lib&map=" + REAL + "&theme=E", dump=True)
hit = re.search(r'class="libRow on[^"]*"[^>]*data-f="([^"]+)"', html)
got = hit.group(1) if hit else None
toast = re.search(r'id="preToast"[^>]*>(.*?)</div>', html, re.S)
ttext = re.sub(r"<[^>]+>", "", toast.group(1)) if toast else ""
print("  高亮行 data-f :", got)
print("  期望           :", REG)
print("  提示文字       :", (ttext[:90] or "（无）"))
ok2 = (got == REG) and ("近似" in ttext)
oks.append(("libGoto 近似名", ok2))
print("  ->", "OK" if ok2 else "失败")

print()
print("=== 3) 指向不存在的图 → 列表照常、不自动选中第一张 ===")
html2 = edge(base + "/?view=lib&map=ze_no_such_map_zzz&theme=E", dump=True)
sel = re.search(r'class="libRow on[^"]*"[^>]*data-f="([^"]+)"', html2)
cnt = re.search(r'id="libCnt"[^>]*>([^<]*)<', html2)
right = re.search(r'id="libDetail"[^>]*>(.*?)</div></div>', html2, re.S)
rtext = re.sub(r"<[^>]+>", " ", right.group(1))[:80] if right else ""
print("  选中行     :", (sel.group(1) if sel else "（无）"))
print("  列表计数   :", (cnt.group(1) if cnt else "（无）"))
print("  右侧面板   :", rtext.strip()[:60])
ok3 = (sel is None) and ("左侧选一张地图" in html2)
oks.append(("未找到图不误选", ok3))
print("  ->", "OK" if ok3 else "失败")

print()
print("=== 4) 图例：≈ 说明 / ⚠ 文案已压短 ===")
html3 = edge(base + "/?view=srv&theme=E", dump=True)
has_apx = "≈</span> 地图名按官方登记名近似匹配" in html3
no_long = "⚠ 官网 N ≠ 本机" not in html3          # 旧图例完整串（注释里那个带数字 12，不会误匹配）
print("  图例含 ≈ 条目 :", has_apx)
print("  旧长文案已消失 :", no_long)
ok4 = has_apx and no_long
oks.append(("图例", ok4))
print("  ->", "OK" if ok4 else "失败")

print()
print("=== 5) 卡片按钮恒为「📚 去地图库」 ===")
btn = re.search(r'<button class="btn" id="pvNow"[^>]*>([^<]*)</button>', html3)
print("  按钮文案 :", (btn.group(1).strip() if btn else "（未找到）"))
ok5 = bool(btn) and "去地图库" in btn.group(1)
oks.append(("pvNow", ok5))
print("  ->", "OK" if ok5 else "失败")

print()
print("=== 6) 截图 ===")
s1 = os.path.join(OUT, "15-发布前-服务器表.png")
s2 = os.path.join(OUT, "16-发布前-地图库近似名定位.png")
edge(base + "/?view=srv&theme=E", budget=16000, shot=s1)
edge(base + "/?view=lib&map=" + REAL + "&theme=E", budget=22000, shot=s2)
for p in (s1, s2):
    print("  %s  %s" % ("OK " if os.path.exists(p) else "失败",
                       "%.0f KB  %s" % (os.path.getsize(p) / 1024, os.path.basename(p))
                       if os.path.exists(p) else os.path.basename(p)))

print()
bad = [n for n, v in oks if not v]
print("结果：", "全部通过 ✓" if not bad else ("失败项 → " + ", ".join(bad)))

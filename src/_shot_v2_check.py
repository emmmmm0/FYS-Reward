# -*- coding: utf-8 -*-
"""v2.0 界面验证：设置页「预览数据」行 + 侧栏贴纸默认小白猫 + 服务器页云端数据。"""
import json
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
PORT = 8817

import fys_reward_app as A                                          # noqa: E402
import reward_server as engine                                      # noqa: E402

OK = [0]
FAIL = [0]


def chk(name, cond, extra=""):
    if cond:
        OK[0] += 1
        print("  PASS  %-24s %s" % (name, extra))
    else:
        FAIL[0] += 1
        print("  FAIL  %-24s %s" % (name, extra))


A.State.engine = engine
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
BASE = "http://127.0.0.1:%d" % PORT
print("服务 %s" % BASE)

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(40):
    try:
        op.open(BASE + "/api/status", timeout=5).read()
        break
    except Exception:                                               # noqa: BLE001
        time.sleep(1)

# 服务器看板由后台线程填充，测试里要自己把它拉起来
engine.start_server_watcher()
for _ in range(30):
    try:
        d0 = json.loads(op.open(BASE + "/api/servers", timeout=25).read().decode("utf-8"))
        if len(d0.get("rows") or []) > 0:
            break
    except Exception:                                               # noqa: BLE001
        pass
    time.sleep(1)

OUT = os.path.join(W, "验证截图-界面巡检")
os.makedirs(OUT, exist_ok=True)
prof = os.path.join(W, "验证截图-软件实体bbox", "_prof_v2")
os.makedirs(prof, exist_ok=True)


def shot(url, name):
    p = os.path.join(OUT, name)
    r = subprocess.run([EDGE, "--headless=new", "--disable-gpu-sandbox", "--no-first-run",
                        "--user-data-dir=" + prof, "--window-size=1440,1100",
                        "--virtual-time-budget=16000",
                        "--screenshot=" + p, "--dump-dom", url],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or ""), p


print("\n[1] 服务器页：云端状态")
try:
    d = json.loads(op.open(BASE + "/api/servers", timeout=25).read().decode("utf-8"))
    chk("rows = 9", len(d.get("rows") or []) == 9, str(len(d.get("rows") or [])))
    chk("cloud 标记", d.get("cloud") is True, str(d.get("cloud")))
    online = sum(1 for r in d.get("rows") or [] if r.get("players") is not None)
    chk("有在线人数", online >= 8, "online=%d/9" % online)
except Exception as e:                                             # noqa: BLE001
    chk("/api/servers", False, repr(e))

print("\n[2] 设置页：预览数据行")
dom, p = shot(BASE + "/?view=set", "set-预览数据行-v2.png")
chk("截图生成", os.path.exists(p) and os.path.getsize(p) > 20000,
    ("%.0f KB" % (os.path.getsize(p) / 1024.0)) if os.path.exists(p) else "无")
chk("含「预览数据」标题", "预览数据" in dom)
m = re.search(r'id="abPv"[^>]*>([^<]*)<', dom)
txt = m.group(1) if m else ""
chk("abPv 有值", bool(txt) and txt != "—", repr(txt))
print("     abPv = %s" % repr(txt))

print("\n[3] 侧栏贴纸默认小白猫")
dom2, p2 = shot(BASE + "/?view=theme", "theme-贴纸默认小白猫-v2.png")
chk("主题页截图", os.path.exists(p2) and os.path.getsize(p2) > 20000,
    ("%.0f KB" % (os.path.getsize(p2) / 1024.0)) if os.path.exists(p2) else "无")
def _on(dom, sid):
    """贴纸选项是否被选中（标签是 button，class 里带独立 on）"""
    for mm in re.finditer(r'<(\w+)[^>]*data-s="%s"[^>]*>' % sid, dom):
        if re.search(r'class="[^"]*\bstkopt on\b[^"]*"', mm.group(0)):
            return True
    return False


cat_on = _on(dom2, "cat")
cloud_on = _on(dom2, "cloud")
chk("cat 为选中态", cat_on)
chk("cloud 非选中", not cloud_on)
if not cat_on:      # 打印真实 DOM 片段，便于定位是渲染问题还是断言写法问题
    print("     [诊断] stkopt 标签样本：")
    for tag in re.findall(r'<div class="stkopt[^>]*>', dom2)[:5]:
        print("       %s" % tag)
    i = dom2.find('id="stkrow"')
    if i > 0:
        print("     [诊断] stkrow 片段：%s" % dom2[i:i + 400].replace("\n", " "))

print("\n%d 通过 / %d 失败" % (OK[0], FAIL[0]))
sys.exit(1 if FAIL[0] else 0)

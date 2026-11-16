# -*- coding: utf-8 -*-
"""全链路体检：后端接口 + 前端六个视图的真实交互 + 控制台异常 + 失败请求 + 性能抽样。

   和 _cdp_audit_all.py 的区别：那个只「打开看看」，这个会把主题卡 / 背景卡 / 贴纸 /
   动效开关 / 地图库搜索与详情 / 内嵌 3D 预览 全部点一遍，并统计
   Runtime.exceptionThrown、Log.entryAdded(error)、Network 4xx/5xx 与 loadingFailed。

   用法：python _cdp_health.py
"""
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

import websocket

from _prefs_guard import PrefsGuard

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
W = os.path.dirname(HERE)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
SHOT = os.path.join(W, "验证截图-界面巡检")
PORT = 8805
CDP = 9355
PROF = os.path.join(SHOT, "_prof_health")

FAIL = []
NOTE = []


def check(name, ok, extra=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + str(extra)) if extra else ""))
    if not ok:
        FAIL.append(name)


def note(msg):
    NOTE.append(msg)
    print("  [NOTE] " + msg)


# ── 起后端（进程内，不弹窗） ───────────────────────────────
import fys_reward_app as A          # noqa: E402
import reward_server as engine      # noqa: E402

A.State.engine = engine
meta = engine.load_state(force=False)
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
BASE = A.State.url.rstrip("/")
print("本机服务 %s（地图 %s / 关卡 %s）" % (BASE, meta.get("maps"), meta.get("stages")))
time.sleep(0.6)

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen(
    [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP, "--remote-allow-origins=*",
     "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--hide-scrollbars",
     "--user-data-dir=" + PROF, "--no-first-run", "--window-size=1400,820", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

EV = []
# 体检会把主题/背景/贴纸/动效全点一遍（且收尾硬编码回 E/cloud），
# 跑完字节级还原用户偏好，避免「做个体检把设置洗了」。见 _prefs_guard.py。
_g = PrefsGuard().__enter__()
try:
    ws_url = None
    for _ in range(40):
        try:
            tabs = json.load(op.open("http://127.0.0.1:%d/json" % CDP, timeout=2))
            pg = [t for t in tabs if t.get("type") == "page"]
            if pg:
                ws_url = pg[0]["webSocketDebuggerUrl"]
                break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(ws_url, timeout=240, http_proxy_host=None)
    _id = [0]

    def send(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({"id": _id[0], "method": m, "params": p or {}}))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == _id[0]:
                return r.get("result", {})
            EV.append(r)

    def drain(sec=0.6):
        ws.settimeout(0.25)
        end = time.time() + sec
        while time.time() < end:
            try:
                EV.append(json.loads(ws.recv()))
            except Exception:
                pass
        ws.settimeout(240)

    def ev(e):
        r = send("Runtime.evaluate", {"expression": e, "returnByValue": True})
        if "exceptionDetails" in r:
            return "__ERR__" + str(r["exceptionDetails"].get("exception", {}).get("description",
                                                                                  ""))[:120]
        return r.get("result", {}).get("value")

    def snap(name):
        d = send("Page.captureScreenshot", {"format": "png"})
        p = os.path.join(SHOT, name)
        open(p, "wb").write(base64.b64decode(d["data"]))
        return p

    def collect():
        """把累计事件里的异常/错误/坏请求挑出来"""
        js, con, net = [], [], []
        for m in EV:
            k = m.get("method")
            if k == "Runtime.exceptionThrown":
                d = m["params"].get("exceptionDetails", {})
                js.append(str(d.get("exception", {}).get("description", d.get("text")))[:200])
            elif k == "Log.entryAdded":
                e = m["params"]["entry"]
                if e.get("level") == "error":
                    con.append("%s %s" % (e.get("source"), str(e.get("text"))[:180]))
            elif k == "Network.responseReceived":
                r = m["params"]["response"]
                if r.get("status", 0) >= 400:
                    net.append("%s %s %s" % (r.get("status"), r.get("url", "")[:110],
                                             m["params"].get("type", "")))
            elif k == "Network.loadingFailed":
                p = m["params"]
                if not p.get("canceled"):
                    net.append("FAILED %s %s" % (p.get("errorText"), str(p.get("requestId"))))
        return js, con, net

    send("Page.enable")
    send("Runtime.enable")
    send("Log.enable")
    send("Network.enable")
    send("Emulation.setDeviceMetricsOverride",
         {"width": 1400, "height": 820, "deviceScaleFactor": 1, "mobile": False})
    send("Page.addScriptToEvaluateOnNewDocument", {"source":
        "window.__jserr=[];addEventListener('error',function(e){__jserr.push(String(e.message||e))});"
        "addEventListener('unhandledrejection',function(e){__jserr.push('p:'+String(e.reason))});"})

    print("\n── 1. 启动 ──")
    t0 = time.time()
    send("Page.navigate", {"url": BASE + "/?noreadme"})
    ok_boot = False
    t_first = None
    for _ in range(120):
        dt = time.time() - t0
        if ev("document.querySelectorAll('#stb tr').length>0 && !!$('stateText')"):
            t_first = dt
            ok_boot = True
            break
        time.sleep(0.4)
    check("首屏（服务器表 + 状态字）渲染完成 %.1fs" % (t_first or 99), ok_boot)
    # 等第一发 /api/status 回来（真正的“活了”判据）
    for _ in range(40):
        if ev("['在线','未在服务器内','服务未响应'].indexOf(($('stateText')||{}).textContent) >= 0"):
            break
        time.sleep(0.4)
    drain(1.0)
    check("状态字已就绪（非「服务未响应」）",
          ev("$('stateText').textContent") != "服务未响应",
          "$('stateText')=%s / 顶栏 pill=%s" % (ev("$('stateText').textContent"),
                                               ev("($('pill')||{}).className")))
    note("首屏服务器表 %s 行 / 地图名=%s / 状态=%s / 视图=%s"
         % (ev("document.querySelectorAll('#stb tr').length"),
            ev("(($('mapName')||{}).textContent)||'-'"),
            ev("$('stateText').textContent"),
            ev("(document.querySelector('.view.on')||{}).id")))

    print("\n── 2. 六视图切换 ──")
    for v in ("srv", "ov", "theme", "lib", "set", "pre"):
        ev("showView('%s')" % v)
        time.sleep(1.0)
        on = ev("(document.querySelector('.view.on')||{}).id")
        nav = ev("(document.querySelector('.mv.on')||{}).getAttribute('data-view')")
        page = ev("$('tPage').textContent")
        check("切到 %-5s → %s（侧栏高亮 %s / 顶栏 %s）" % (v, on, nav, page), on == "view-" + v and nav == v,
              on)
    drain(1.0)

    print("\n── 3. 主题卡全点 ──")
    n_th = ev("document.querySelectorAll('#themes .tcard').length") or 0
    check("主题卡数量 %d" % n_th, n_th >= 5)
    for code in ("E", "F", "G", "H", "N"):
        ev("(function(){var b=document.querySelector('#themes .tcard[data-t=\"%s\"]');if(b)b.click();})()" % code)
        time.sleep(0.55)
        got = ev("document.documentElement.getAttribute('data-theme')")
        oncard = ev("document.querySelectorAll('#themes .tcard.on').length")
        bgcss = ev("($('bgcss')||{}).textContent||''")
        check("主题 %s 生效（卡片选中 %d 个 / 底纹 %s）" % (code, oncard, "有" if bgcss else "无"),
              got == code and oncard == 1)
    ev("(function(){var b=document.querySelector('#themes .tcard[data-t=\"E\"]');if(b)b.click();})()")
    time.sleep(0.5)

    print("\n── 4. 背景卡 + 贴纸 + 动效 ──")
    n_bg = ev("document.querySelectorAll('#bggrid .bgopt').length") or 0
    check("背景方案 %d 套" % n_bg, n_bg >= 5)
    for bid in ("none", "cloud", "run", "win", "girl"):
        ev("(function(){var b=document.querySelector('#bggrid .bgopt[data-b=\"%s\"]');if(b)b.click();})()" % bid)
        time.sleep(0.6)
        cur = ev("document.documentElement.getAttribute('data-bg')")
        heroes = ev("document.querySelectorAll('.heroBanner,.libBanner,.setBanner').length")
        css = ev("($('bgcss')||{}).textContent||''")
        ok = cur == bid and (heroes == 0 if bid == "none" else heroes >= 1 and bool(css))
        check("背景 %-5s 生效（插画 %d 处 / 底纹 %s）" % (bid, heroes, "有" if css else "无"), ok, cur)
    ev("(function(){var b=document.querySelector('#bggrid .bgopt[data-b=\"cloud\"]');if(b)b.click();})()")
    time.sleep(0.6)

    n_st = ev("document.querySelectorAll('#stkrow .stkopt').length") or 0
    check("贴纸方案 %d 种" % n_st, n_st >= 4)
    for sid in ("cloud", "cat", "zombie", "off"):
        ev("(function(){var b=document.querySelector('#stkrow .stkopt[data-s=\"%s\"]');if(b)b.click();})()" % sid)
        time.sleep(0.5)
        has = ev("!!document.getElementById('cuteSticker')")
        check("贴纸 %-6s → %s" % (sid, "已挂" if has else "已摘"), has == (sid != "off"))
    ev("(function(){var b=document.querySelector('#stkrow .stkopt[data-s=\"cloud\"]');if(b)b.click();})()")
    time.sleep(0.4)

    ev("$('bAllOff').click()"); time.sleep(0.7)
    off = ev("document.querySelectorAll('#fxgrid .sw.on').length")
    ev("$('bAllOn').click()"); time.sleep(0.7)
    onn = ev("document.querySelectorAll('#fxgrid .sw.on').length")
    check("动效开关 全关=%s / 全开=%s" % (off, onn), off == 0 and onn >= 10)
    ev("$('bReplay').click()"); time.sleep(0.4)

    print("\n── 5. 地图库搜索 / 详情 / 近似名 ──")
    ev("showView('lib')"); time.sleep(1.2)
    cnt = ev("document.querySelectorAll('#libRows .libRow, #libList .libRow').length")
    print("  列表行数:", cnt)
    ev("(function(){var q=$('libQ');q.value='hortus';q.dispatchEvent(new Event('input',{bubbles:true}));})()")
    time.sleep(0.9)
    hits = ev("document.querySelectorAll('.libRow').length")
    check("搜索 hortus 命中 %s 行" % hits, bool(hits))
    check("近似名标记 .apx 出现（官方键与服务器实名差 1 字符）",
          bool(ev("document.querySelectorAll('.apx').length")),
          ev("document.querySelectorAll('.apx').length"))
    ev("(function(){var b=document.querySelector('.libRow');if(b)b.click();})()")
    time.sleep(1.0)
    check("详情卡渲染", bool(ev("!!document.querySelector('#libDetail .libBdg, #libDetail .lvRow')")))
    snap("体检-地图库详情.png")

    print("\n── 6. 内嵌 3D 预览（含 terr .bin 加载） ──")
    EV.clear()
    ev("openPreView('ze_minecraft_hortus_de_escapismo')")
    ok3 = False
    for _ in range(70):
        if ev("window.frames[0] && window.frames[0].document && "
              "window.frames[0].document.querySelectorAll('#lbody .li').length > 0"):
            ok3 = True
            break
        time.sleep(1)
    time.sleep(2.5)
    fr = "window.frames[0].document"
    check("内嵌预览图层渲染", ok3, ev(fr + ".querySelectorAll('#lbody .li').length"))
    check("3D 画布存在", bool(ev("!!%s.getElementById('cv3')" % fr)))
    wstat = ev("(function(){var e=%s.getElementById('wstat');return e?e.textContent:'-'})()" % fr)
    note("预览状态行 wstat=%s" % wstat)
    terr_ok = ev("(function(){var e=%s.getElementById('wstat');return e?e.textContent:''})()" % fr)
    check("地形已加载（wstat 非「地形文件缺失」）", terr_ok and "缺失" not in str(terr_ok), terr_ok)
    js, con, net = collect()
    terr_bad = [n for n in net if "terr" in n]
    check("terr/*.bin 无 4xx/5xx", not terr_bad, terr_bad[:3])
    snap("体检-内嵌3D预览.png")
    n33 = ev("window.frames[0].document.querySelectorAll('#lbody .xbtn').length")
    note("图层细类展开器 %s 个" % n33)
    ev("showView('srv')"); time.sleep(1.2)
    check("离开预览页释放 iframe",
          ev("(function(){var f=$('preFrame');return !f || f.getAttribute('src')==='' || "
             "f.getAttribute('src')==='about:blank';})()"),
          ev("($('preFrame')||{}).getAttribute ? $('preFrame').getAttribute('src') : '-'"))

    print("\n── 7. 弹窗 / 排序 / 窄窗 / 深链 ──")
    ev("showView('lib')"); time.sleep(0.8)
    n_before = ev("document.querySelectorAll('#libList .libRow').length")
    for s in ("st", "pr", "cn"):
        ev("(function(){var q=$('libSort');q.value='%s';q.dispatchEvent(new Event('change'));})()" % s)
        time.sleep(0.6)
        first = ev("(function(){var r=document.querySelector('#libList .libRow .lc');return r?r.textContent:''})()")
        check("地图库排序 %s 切换后仍 %s 行（首行 %s）"
              % (s, ev("document.querySelectorAll('#libList .libRow').length"), (first or '')[:18]),
              ev("document.querySelectorAll('#libList .libRow').length") == n_before)
    ev("openStages('ze_pizza_cookie')"); time.sleep(1.2)
    check("关卡明细弹窗打开（标题 %s / %s 行）"
          % (ev("$('stgTitle').textContent"), ev("document.querySelectorAll('#stgBody tr').length")),
          ev("$('stgOv').style.display") == "" and
          "pizza" in str(ev("$('stgTitle').textContent")))
    ev("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))"); time.sleep(0.4)
    check("Esc 关闭关卡弹窗", ev("$('stgOv').style.display") == "none")
    ev("openReadme()"); time.sleep(0.6)
    check("使用说明弹窗打开（%s 字）" % ev("$('rmOv').innerText.length"),
          ev("$('rmOv').style.display") == "")
    ev("closeReadme()"); time.sleep(0.3)

    for wpx, tag in ((1000, "1000"), (760, "760")):
        send("Emulation.setDeviceMetricsOverride",
             {"width": wpx, "height": 800, "deviceScaleFactor": 1, "mobile": False})
        time.sleep(0.7)
        over = ev("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("窄窗 %s px 无横向溢出（溢出 %s px）" % (wpx, over), (over or 0) <= 2, over)
        drain(0.3)
    send("Emulation.setDeviceMetricsOverride",
         {"width": 1400, "height": 820, "deviceScaleFactor": 1, "mobile": False})
    time.sleep(0.5)

    EV.clear()
    send("Page.navigate", {"url": BASE + "/?view=pre&map=ze_pizza_cookie&noreadme"})
    ok_dl = False
    for _ in range(90):
        if ev("(document.querySelector('.view.on')||{}).id") == "view-pre" and \
           ev("window.frames[0] && window.frames[0].document && "
              "window.frames[0].document.querySelectorAll('#lbody .li').length>0"):
            ok_dl = True
            break
        time.sleep(1)
    check("深链 ?view=pre&map= 直达内嵌预览（PRE.embed=%s）" % ev("PRE.embed"), ok_dl)
    js, con, net = collect()
    check("深链与弹窗过程无异常", not (js or con or net), "%s/%s/%s" % (len(js), len(con), len(net)))

    print("\n── 8. 边界 / 竞态 ──")
    # (a) 进预览后立刻离开：iframe 必须被释放且不会“晚到的 onload”把页面抢回来
    ev("showView('pre')")
    time.sleep(0.15)
    ev("showView('srv')")
    time.sleep(2.2)
    check("预览加载中切走 → iframe 已释放且未复活",
          ev("(function(){var f=$('preFrame');return f && (f.getAttribute('src')===''||"
             "f.getAttribute('src')==='about:blank');})()"),
          ev("($('preFrame')||{}).getAttribute && $('preFrame').getAttribute('src')"))
    check("iframe 只有 1 个（没有重复创建）",
          ev("document.querySelectorAll('#preFrame').length") == 1)

    # (b) 预览页开着时换主题：走 postMessage 热切，不该重载 iframe
    ev("openPreView('ze_pizza_cookie')")
    for _ in range(60):
        if ev("window.frames[0] && window.frames[0].document && "
              "window.frames[0].document.querySelectorAll('#lbody .li').length>0"):
            break
        time.sleep(1)
    time.sleep(1.5)
    nav = ev("(function(){var f=window.frames[0];var n=f.performance.getEntriesByType('navigation')[0]||{};"
             "return {dur:Math.round(n.duration||0),transfer:Math.round(n.transferSize||0),"
             "decode:Math.round(n.decodedBodySize||0)};})()")
    note("内嵌预览页第 1 次加载：%s" % nav)
    terr1 = ev("(function(){var f=window.frames[0];var rs=f.performance.getEntriesByType('resource')"
               ".filter(function(r){return r.name.indexOf('/terr/')>=0});"
               "var t=0;rs.forEach(function(r){t+=r.transferSize||0});"
               "return {n:rs.length,kb:Math.round(t/1024)};})()")
    note("第 1 次加载地形分包：%s" % terr1)
    ev("(function(){var b=document.querySelector('#themes .tcard[data-t=\"N\"]');if(b)b.click();})()")
    time.sleep(1.4)
    check("预览开着时换主题：iframe 主题跟随（data-theme=%s）"
          % ev("window.frames[0].document.documentElement.getAttribute('data-theme')"),
          ev("window.frames[0].document.documentElement.getAttribute('data-theme')") == "N")
    ev("(function(){var b=document.querySelector('#themes .tcard[data-t=\"E\"]');if(b)b.click();})()")
    time.sleep(0.8)

    # (c) 连续快速切 6 次视图
    for v in ("srv", "ov", "theme", "lib", "set", "srv"):
        ev("showView('%s')" % v)
        time.sleep(0.18)
    time.sleep(1.2)
    check("快速连切 6 次后仍停在 srv",
          ev("(document.querySelector('.view.on')||{}).id") == "view-srv")
    # (d) 离开预览页后再次进入：能正常加载（不是一次性的）
    ev("openPreView('ze_pizza_cookie')")
    ok_again = False
    for _ in range(60):
        if ev("window.frames[0] && window.frames[0].document && "
              "window.frames[0].document.querySelectorAll('#lbody .li').length>0"):
            ok_again = True
            break
        time.sleep(1)
    check("离开后再次进入预览可正常加载", ok_again)
    time.sleep(1.2)
    nav2 = ev("(function(){var f=window.frames[0];var n=f.performance.getEntriesByType('navigation')[0]||{};"
              "return {dur:Math.round(n.duration||0),transfer:Math.round(n.transferSize||0),"
              "decode:Math.round(n.decodedBodySize||0)};})()")
    note("内嵌预览页第 2 次加载：%s" % nav2)
    t2 = (nav2 or {}).get("transfer", 0)
    check("二次进入预览复用缓存（网络传输 %s 字节，解码 %s 字节）"
          % (t2, (nav2 or {}).get("decode")), bool(t2 is not None and t2 < 4096), t2)
    check("预览页首屏也有 ETag 缓存（传输 %s 字节）" % (nav or {}).get("transfer", 0),
          (nav or {}).get("transfer", 10 ** 9) < 4096)
    # 304 协商缓存每笔会回 ~300B 校验头（ETag/Last-Modified），不再要求 0 字节
    check("地形分包走缓存（传输 %s，仅 304 校验头）" % terr1, isinstance(terr1, dict) and terr1.get("kb", 99) <= 1)

    print("\n── 9. 异常与失败请求汇总 ──")
    js, con, net = collect()
    if js:
        print("  JS 未捕获异常 %d 条：" % len(js))
        for x in js[:8]:
            print("    -", x)
    if con:
        print("  控制台 error %d 条：" % len(con))
        for x in con[:8]:
            print("    -", x)
    if net:
        print("  网络异常 %d 条：" % len(net))
        for x in net[:8]:
            print("    -", x)
    check("无 JS 未捕获异常", not js, len(js))
    check("无控制台 error", not con, len(con))
    check("无 4xx/5xx/失败请求", not net, len(net))
    inpage = ev("(window.__jserr||[]).join(' | ')")
    check("页面自捕获错误列表为空", not inpage, inpage)

    print("\n== 体检结果：%s ==" % ("全部通过" if not FAIL else "失败 %d 项" % len(FAIL)))
    for f in FAIL:
        print("   x", f)
    for n in NOTE:
        print("   ·", n)
finally:
    try:
        proc.terminate()
    except Exception:
        pass
    _g.__exit__(None, None, None)

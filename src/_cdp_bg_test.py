# -*- coding: utf-8 -*-
"""界面背景（主题页可切换）功能回归：CDP 直驱 headless Edge 做真实点击与状态断言。

覆盖：默认开启云朵小铺 / 五套方案切换 / 底纹与插画挂载摘除 / 暗色主题换暗色图案 /
      偏好持久化 / 切视图后插画补挂。
用法：_cdp_bg_test.py <port>
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

from _prefs_guard import PrefsGuard

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
OUT = os.path.join(ROOT, "验证截图-界面巡检")
CDP = 9393

FAIL = []


def check(name, ok, extra=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + str(extra)) if extra else ""))
    if not ok:
        FAIL.append(name)


def launch():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    prof = os.path.join(OUT, "_prof_bg")
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP,
         "--remote-allow-origins=*", "--user-data-dir=" + prof,
         "--no-first-run", "--window-size=1330,720", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    ws = websocket.create_connection(ws_url, timeout=240)
    _id = [0]

    def send(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({"id": _id[0], "method": m, "params": p or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == _id[0]:
                return msg.get("result", {})

    def ev(e):
        return send("Runtime.evaluate", {"expression": e, "returnByValue": True}).get("result", {}).get("value")

    return proc, send, ev


def snap(send, path):
    d = send("Page.captureScreenshot", {"format": "png"})
    with open(path, "wb") as f:
        f.write(base64.b64decode(d["data"]))
    print("     shot:", os.path.basename(path), os.path.getsize(path) // 1024, "KB")


def main():
    port = int(sys.argv[1])
    base = "http://127.0.0.1:%d" % port
    proc, send, ev = launch()
    send("Page.enable")
    # 每次导航都注入错误收集器，最后断言页面没抛未捕获异常
    send("Page.addScriptToEvaluateOnNewDocument", {
        "source": "window.__jserr=[];window.addEventListener('error',function(e){"
                  "window.__jserr.push(String(e.message||e))});"
                  "window.addEventListener('unhandledrejection',function(e){"
                  "window.__jserr.push('promise: '+String(e.reason))});"})

    def go(view, wait_js, extra_qs=""):
        send("Page.navigate", {"url": "%s/?view=%s%s" % (base, view, extra_qs)})
        # 先等文档就绪（约 950KB 的页面里内联了近 800KB base64 素材，解析要几秒），
        # 再等业务条件；只等业务条件会出现「还在旧文档/半成品 DOM」上误判的竞态
        for _ in range(40):
            if ev("document.readyState==='complete'") and ev("typeof LIB!=='undefined'"):
                break
            time.sleep(0.6)
        for _ in range(60):
            if ev(wait_js):
                break
            time.sleep(1)
        time.sleep(1.6)

    # 偏好守卫：把 bg/sticker/theme 三个键先摘掉——[1] 验的就是「首次运行默认开启云朵小铺」，
    # 不摘会读到上一轮测试或用户留下的选择（手工设成硬编码默认则会把用户真实偏好弄丢）。
    # 结束时字节级还原。见 _prefs_guard.py。
    _g = PrefsGuard(drop=("bg", "sticker", "theme")).__enter__()
    try:
        print("[1] 主题页：背景卡结构 + 默认开启")
        go("theme", "!!document.documentElement.getAttribute('data-bg')")
        if ev("(window.__jserr||[]).length"):
            print("     jserr:", ev("(window.__jserr||[]).join(' | ')"))
            print("     diag: bgcss=",
                  ev("((document.getElementById('bgcss')||{textContent:''}).textContent||'').length"),
                  "bgopt=", ev("document.querySelectorAll('#bggrid .bgopt').length"))
        check("背景卡渲染 5 个选项",
              ev("document.querySelectorAll('#bggrid .bgopt').length") == 5,
              ev("document.querySelectorAll('#bggrid .bgopt').length"))
        check("默认选中 cloud（背景默认打开）",
              ev("(document.querySelector('#bggrid .bgopt.on')||{}).getAttribute"
                 "&&document.querySelector('#bggrid .bgopt.on').getAttribute('data-b')") == "cloud")
        check("html[data-bg]=cloud",
              ev("document.documentElement.getAttribute('data-bg')") == "cloud")
        check("底纹 CSS 已写入", ev("(document.getElementById('bgcss')||{}).textContent.length>1000"))
        check("底纹用图案 pat（非暗色）",
              ev("var t=document.getElementById('bgcss').textContent;"
                 "t.indexOf(BGDATA.pat)>0"))
        check("侧栏贴纸在（默认云朵精灵）", ev("!!document.getElementById('cuteSticker')"))
        snap(send, os.path.join(OUT, "背景01-主题页-默认云朵小铺.png"))

        print("[2] 逐套切换（底纹 + 贴纸 + 选中态）")
        cases = [("run", "run", True), ("win", "winner", True),
                 ("girl", "girl", True), ("none", None, False)]
        for bid, key, has_bg in cases:
            ev("document.querySelector('#bggrid .bgopt[data-b=\"%s\"]').click()" % bid)
            time.sleep(0.7)
            check("切到 %s：html[data-bg] 同步" % bid,
                  ev("document.documentElement.getAttribute('data-bg')") == bid)
            check("切到 %s：选中态唯一" % bid,
                  ev("document.querySelectorAll('#bggrid .bgopt.on').length") == 1
                  and ev("document.querySelector('#bggrid .bgopt.on').getAttribute('data-b')") == bid)
            if has_bg:
                check("切到 %s：底纹引用对应素材" % bid,
                      ev("document.getElementById('bgcss').textContent.indexOf(BGDATA['%s'])>0" % key))
                check("切到 %s：贴纸在（贴纸独立于背景）" % bid,
                      ev("!!document.getElementById('cuteSticker')"))
            else:
                check("切到 none：底纹清空", ev("document.getElementById('bgcss').textContent") == "")
                check("切到 none：贴纸仍在（贴纸独立于背景）",
                      ev("!!document.getElementById('cuteSticker')"))
                check("切到 none：插画横幅全部移除",
                      ev("document.querySelectorAll('.heroBanner,.libBanner,.setBanner').length") == 0)

        print("[2b] 侧栏贴纸自选（独立于背景方案）")
        check("贴纸选项 4 个",
              ev("document.querySelectorAll('#stkrow .stkopt').length") == 4,
              ev("document.querySelectorAll('#stkrow .stkopt').length"))
        check("默认云朵精灵",
              ev("(document.querySelector('#stkrow .stkopt.on')||{}).getAttribute"
                 "&&document.querySelector('#stkrow .stkopt.on').getAttribute('data-s')") == "cloud")
        check("默认贴纸图 = sticker_cloud",
              ev("(document.getElementById('cuteSticker')||{}).src===BGDATA.sticker_cloud"))
        check("贴纸与背景解耦：此时背景是 none，贴纸仍在",
              ev("document.documentElement.getAttribute('data-bg')") == "none"
              and ev("!!document.getElementById('cuteSticker')"))
        for sid, key in [("cat", "sticker_cat"), ("zombie", "sticker_zombie")]:
            ev("document.querySelector('#stkrow .stkopt[data-s=\"%s\"]').click()" % sid)
            time.sleep(0.5)
            check("选 %s：换图正确" % sid,
                  ev("(document.getElementById('cuteSticker')||{}).src===BGDATA['%s']" % key))
            check("选 %s：选中态唯一" % sid,
                  ev("document.querySelectorAll('#stkrow .stkopt.on').length") == 1)
        ev("document.querySelector('#stkrow .stkopt[data-s=\"off\"]').click()")
        time.sleep(0.5)
        check("选「不显示」：贴纸移除", ev("!document.getElementById('cuteSticker')"))
        snap(send, os.path.join(OUT, "背景06-主题页-贴纸自选.png"))
        ev("applySticker('cloud', true)"); time.sleep(0.5)

        print("[3] 插画横幅：三页挂载")
        # 上一段最后停在 none，且 go() 会重新导航（页面会重读后端偏好）→ 先落盘回 cloud
        ev("applyBG('cloud', true)"); time.sleep(0.6)
        go("srv", "!!document.querySelector('.srvtab')")
        check("服务器页 heroBanner 在", ev("!!document.querySelector('.heroBanner')"))
        check("服务器页横幅图 = run",
              ev("(document.querySelector('.heroBanner img')||{}).src===BGDATA.run"))
        snap(send, os.path.join(OUT, "背景02-服务器页-横幅.png"))
        go("lib", "document.querySelectorAll('#libList .libRow').length>10")
        check("地图库 libBanner 在", ev("!!document.querySelector('.libBanner')"))
        check("地图库横幅图 = winner",
              ev("(document.querySelector('.libBanner img')||{}).src===BGDATA.winner"))
        snap(send, os.path.join(OUT, "背景03-地图库-横幅.png"))
        go("set", "!!document.querySelector('#view-set .rmcard')")
        check("设置页 setBanner 在", ev("!!document.querySelector('.setBanner')"))
        check("设置页头图 = girl",
              ev("(document.querySelector('.setBanner img')||{}).src===BGDATA.girl"))
        snap(send, os.path.join(OUT, "背景04-设置页-头图.png"))

        print("[4] 切视图后插画补挂（不重复）")
        ev("showView('srv')"); time.sleep(0.6)
        ev("showView('lib')"); time.sleep(0.8)
        ev("showView('srv')"); time.sleep(0.6)
        check("来回切视图后 heroBanner 仍只有一个",
              ev("document.querySelectorAll('.heroBanner').length") == 1,
              ev("document.querySelectorAll('.heroBanner').length"))
        check("来回切视图后 libBanner 仍只有一个",
              ev("document.querySelectorAll('.libBanner').length") == 1,
              ev("document.querySelectorAll('.libBanner').length"))

        print("[5] 夜幕护眼：图案底自动换暗色版")
        ev("applyBG('cloud', false)")
        ev("typeof applyTheme==='function'&&applyTheme('N', false)")
        time.sleep(0.7)
        check("暗色下底纹引用 pat_dark",
              ev("document.getElementById('bgcss').textContent.indexOf(BGDATA.pat_dark)>0"))
        check("暗色下不再引用亮色 pat",
              ev("document.getElementById('bgcss').textContent.indexOf(BGDATA.pat)>0") is False)
        snap(send, os.path.join(OUT, "背景05-主题页-夜幕暗色.png"))
        ev("applyTheme('E', false)"); time.sleep(0.4)
        check("切回亮色后恢复 pat",
              ev("document.getElementById('bgcss').textContent.indexOf(BGDATA.pat)>0"))

        print("[6] 偏好持久化")
        ev("applyBG('win', true)"); time.sleep(0.5)
        ev("applySticker('cat', true)"); time.sleep(0.5)
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        _p = json.loads(op.open(base + "/api/prefs", timeout=5).read())["prefs"]
        check("后端 ui_prefs.json 记到 bg=win", _p.get("bg") == "win", _p.get("bg"))
        check("后端 ui_prefs.json 记到 sticker=cat", _p.get("sticker") == "cat", _p.get("sticker"))
        send("Page.navigate", {"url": "%s/?view=theme" % base})
        for _ in range(60):
            if ev("typeof LIB!=='undefined'") and ev("document.querySelectorAll('#bggrid .bgopt').length>0"):
                break
            time.sleep(1)
        time.sleep(2.4)
        check("刷新后仍是 win（记忆生效）",
              ev("document.documentElement.getAttribute('data-bg')") == "win")
        check("刷新后贴纸仍是小白猫",
              ev("(document.getElementById('cuteSticker')||{}).src===BGDATA.sticker_cat"))
        snap(send, os.path.join(OUT, "背景07-主题页-记忆恢复.png"))

        print("[7] 无 JS 报错")
        errs = ev("(window.__jserr||[]).join(' | ')")
        check("页面无未捕获错误", not errs, errs)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        _g.__exit__(None, None, None)          # 还原用户真实偏好（不再硬编码回 cloud）

    print()
    if FAIL:
        print("!! 失败 %d 项：%s" % (len(FAIL), "; ".join(FAIL)))
        sys.exit(1)
    print("全部通过 ✔")


if __name__ == "__main__":
    main()

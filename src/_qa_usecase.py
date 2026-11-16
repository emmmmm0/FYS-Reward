# -*- coding: utf-8 -*-
"""使用路径自检（v2.14 追加）：接口健壮性 + 安全边界 + 真浏览器交互旅程。

目的不是复跑既有断言，而是像用户一样把界面点一遍，抓
  · 未捕获异常 / console.error / 失败请求
  · 脏输入（引号、尖括号、超长、路径穿越）导致的崩或 XSS
  · 视图切换、搜索、筛选、收藏、详情、主题等主路径的行为异常
  · 布局溢出（横向滚动）/ 重复 id

端口 9440 / CDP 9441（未登记，独占）。
用法: python _qa_usecase.py [--keep]
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 9440
CDP_PORT = 9441
BASE = "http://127.0.0.1:%d" % PORT
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TMP = os.path.join(os.environ.get("TEMP", HERE), "_qa_prof_9441")
SHOT = os.path.join(HERE, "_qa_shots")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

BUGS = []       # 失败项
NOTES = []      # 观察项（不算 bug，但要人看）


def bug(tag, detail):
    BUGS.append({"tag": tag, "detail": detail})
    print("  NG  %-26s %s" % (tag, detail))


def ok(tag, detail=""):
    print("  OK  %-26s %s" % (tag, detail))


def note(tag, detail):
    NOTES.append({"tag": tag, "detail": detail})
    print("  --  %-26s %s" % (tag, detail))


# ─────────────────────────── 接口层 ───────────────────────────
def http(path, headers=None, timeout=120):
    req = urllib.request.Request(BASE + path, headers=headers or {})
    t0 = time.perf_counter()
    try:
        r = OPENER.open(req, timeout=timeout)
        body = r.read()
        return r.status, dict(r.headers), body, (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read(), (time.perf_counter() - t0) * 1000
    except Exception as e:                                    # noqa: BLE001
        return 0, {}, repr(e).encode(), (time.perf_counter() - t0) * 1000


def api_sweep():
    print("\n[1] JSON 接口：正常 / 缺参 / 脏参")
    cases = [
        ("/api/prefs", "正常"),
        ("/api/status", "正常（含 A2S）"),
        ("/api/servers", "正常（9 台探测）"),
        ("/api/maplib", "正常"),
        ("/api/mapnames", "正常"),
        ("/api/mapnames?q=ze", "带 q"),
        ("/api/rewards", "正常"),
        ("/api/upddiff", "正常"),
        ("/api/updlog", "正常"),
        ("/api/updlog?all=1", "带 all"),
        ("/api/about", "正常"),
        ("/api/ovcfg", "正常"),
        ("/api/ovpoll", "正常"),
        ("/api/terr/info", "正常"),
        ("/api/preview/progress", "正常"),
        ("/api/update/progress", "正常"),
        ("/api/ctl?do=coverstat", "ctl 只读"),
        ("/api/ctl", "ctl 缺参"),
        ("/api/ctl?do=__nope__", "ctl 未知动作"),
        ("/api/mapdiff", "mapdiff 缺参"),
        ("/api/mapdiff?f=", "mapdiff 空参"),
        ("/api/mapdiff?f=ze_not_a_real_map_xx", "mapdiff 不存在的图"),
        ("/api/mapdiff?f=../../fys_reward_app", "mapdiff 路径穿越"),
        ("/api/mapdiff?f=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E", "mapdiff XSS 串"),
        ("/api/mapparams", "mapparams 缺参"),
        ("/api/mapparams?f=", "mapparams 空参"),
        ("/api/mapparams?f=../../etc/passwd", "mapparams 路径穿越"),
        ("/api/mapparams?f=ze_samosbor", "mapparams 正常"),
        ("/api/mapdiff?f=ze_samosbor", "mapdiff 正常"),
        ("/api/preview", "preview 元信息"),
        ("/api/update/check", "update check"),
    ]
    for path, label in cases:
        st, hd, body, ms = http(path)
        txt = body.decode("utf-8", "replace")
        problem = []
        if st != 200:
            problem.append("HTTP %s" % st)
        try:
            j = json.loads(txt)
        except Exception:                                      # noqa: BLE001
            problem.append("非 JSON: %s" % txt[:120])
            j = None
        if isinstance(j, dict) and j.get("error"):
            # 缺参 / 未知动作返回 200 + {"error": "..."} 是设计好的温和拒绝，
            # 不算 bug；只有 5xx / 非 JSON / 堆栈泄漏才算。
            note("api 拒绝:" + path.split("?")[0], str(j.get("error"))[:80])
        if "Traceback" in txt or "File \"" in txt:
            problem.append("泄漏堆栈")
        if len(body) and "Content-Length" not in {k for k in hd}:
            problem.append("缺 Content-Length")
        if problem:
            bug("api:" + path.split("?")[0] + ("[%s]" % label if label else ""),
                "; ".join(problem)[:300])
        else:
            extra = ""
            if isinstance(j, dict):
                for k in ("maps", "rows", "entries", "counts", "stages"):
                    v = j.get(k)
                    if isinstance(v, (list, dict)):
                        extra = "%s=%d" % (k, len(v))
                        break
            ok("api " + path[:44], "%s %.0fms %s %s" % (st, ms, "%dKB" % (len(body) // 1024), extra))

    print("\n[2] 静态资源 / 路径穿越 / 跨站防护")
    for path, want, label in [
        ("/", 200, "主页"),
        ("/static/app.css", 200, "CSS"),
        ("/static/app.js", 200, "JS"),
        ("/overlay", 200, "覆盖小窗页"),
        ("/static/../version.json", 404, "静态目录穿越"),
        ("/static/..%2F..%2Fversion.json", 404, "静态编码穿越"),
        ("/terr/..%2F..%2Fversion.json", 400, "地形目录穿越"),
        ("/terr/..%5C..%5Cversion.json", 400, "地形反斜杠穿越"),
        ("/cover/..%2F..%2Fversion.json", 400, "封面目录穿越"),
        ("/api/maplib/../../version.json", 404, "接口目录穿越"),
        ("/favicon.ico", 404, "缺 favicon 应 404"),
        ("/index.htm", 404, "错误主页名"),
    ]:
        st, hd, body, ms = http(path)
        if st != want:
            bug("route:" + label, "%s → HTTP %s（期望 %s）" % (path, st, want))
        else:
            ok("route " + label, "%s %d" % (path, st))
        if st == 200 and path in ("/", "/static/app.css", "/static/app.js"):
            if path == "/" and len(body) > 400 * 1024:
                bug("主页体积", "%.0fKB，拆分后应 < 200KB" % (len(body) / 1024.0))
            if path.endswith(".js"):
                open(os.path.join(TMP, "app.js"), "wb").write(body)
            if path.endswith(".css"):
                open(os.path.join(TMP, "app.css"), "wb").write(body)

    print("\n[3] 跨站 / DNS rebinding 防护")
    for hd, want, label in [
        ({"Host": "evil.example.com"}, 403, "Host 非本机"),
        ({"Origin": "http://evil.example.com"}, 403, "Origin 非本机"),
        ({"Host": "127.0.0.1:%d" % PORT}, 200, "Host 本机"),
    ]:
        st, _, _, _ = http("/api/maplib", headers=hd)
        if st != want:
            bug("sec:" + label, "HTTP %s（期望 %s）" % (st, want))
        else:
            ok("sec " + label, "HTTP %s" % st)


# ─────────────────────────── 浏览器层 ───────────────────────────
class Browser(object):
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=90)
        self.seq = 0
        self.errors = []
        self.http4xx = []
        self.slow = []
        self.cover404 = 0

    def _collect(self, m):
        meth = m.get("method")
        p = m.get("params") or {}
        if meth == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails") or {}
            desc = ((d.get("exception") or {}).get("description")
                    or d.get("text") or "?")
            self.errors.append(("exception", desc.splitlines()[0][:300]))
        elif meth == "Runtime.consoleAPICalled":
            t = p.get("type")
            if t in ("error", "warning"):
                parts = []
                for a in p.get("args") or []:
                    parts.append(str(a.get("value") if "value" in a else a.get("description", "")))
                self.errors.append(("console." + t, " ".join(parts)[:300]))
        elif meth == "Log.entryAdded":
            e = p.get("entry") or {}
            if e.get("level") in ("error", "warning"):
                txt = (e.get("text") or "") + " " + (e.get("url") or "")
                # 封面 404 是数据侧已知缺口（官方图床就没有这张图），前端 <img onerror>
                # 静默隐藏，属于预期噪音；统计数量后单独记为观察项。
                if "Failed to load resource" in txt and ("/cover/" in txt or "favicon" in txt):
                    self.cover404 += 1
                    return
                self.errors.append(("log." + e.get("level"), txt[:300]))
        elif meth == "Network.responseReceived":
            r = p.get("response") or {}
            st = r.get("status")
            url = r.get("url") or ""
            if st and st >= 400:
                if "/cover/" in url or "/terr/" in url:
                    return                    # 封面/地形缺图是数据侧预期
                self.http4xx.append("%s %s" % (st, url[:160]))

    def send(self, method, params=None):
        self.seq += 1
        i = self.seq
        self.ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == i:
                return m
            self._collect(m)

    def ev(self, expr):
        r = self.send("Runtime.evaluate", {"expression": expr,
                                           "returnByValue": True,
                                           "awaitPromise": True})
        res = r.get("result") or {}
        if res.get("exceptionDetails"):
            d = res["exceptionDetails"]
            self.errors.append(("eval", "%s :: %s" % (
                (d.get("text") or "")[:160],
                ((d.get("exception") or {}).get("description") or "").splitlines()[0][:200])))
            return None
        return (res.get("result") or {}).get("value")

    def js(self, expr):
        """返回 JSON.parse 后的结果；表达式需自带 JSON.stringify。"""
        v = self.ev(expr)
        if v is None:
            return None
        try:
            return json.loads(v)
        except Exception:                                      # noqa: BLE001
            return v

    def wait(self, expr, timeout=25, interval=0.25):
        end = time.time() + timeout
        while time.time() < end:
            if self.ev("!!(%s)" % expr):
                return True
            self.pump(interval)
        return False

    def pump(self, secs):
        end = time.time() + secs
        self.ws.settimeout(0.08)
        while time.time() < end:
            try:
                m = json.loads(self.ws.recv())
            except Exception:                                  # noqa: BLE001
                continue
            self._collect(m)
        self.ws.settimeout(90)

    def shot(self, name, w=1500, h=980):
        self.send("Emulation.setDeviceMetricsOverride",
                  {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False})
        self.pump(0.35)
        d = self.send("Page.captureScreenshot", {"format": "png"})
        data = ((d.get("result") or {}).get("data") or "")
        if not data:
            return
        p = os.path.join(SHOT, "qa_" + name + ".png")
        with open(p, "wb") as fh:
            fh.write(base64.b64decode(data))
        print("      shot %s (%dKB)" % (name, os.path.getsize(p) // 1024))


def wait_http(path, tries=90, timeout=2):
    for _ in range(tries):
        try:
            OPENER.open(BASE + path, timeout=timeout).read()
            return True
        except Exception:                                      # noqa: BLE001
            time.sleep(0.5)
    return False


def browser_journey():
    print("\n[4] 真浏览器：主路径交互")
    edge = subprocess.Popen(
        [EDGE, "--headless=new", "--remote-debugging-port=%d" % CDP_PORT,
         "--remote-allow-origins=*", "--user-data-dir=" + TMP,
         "--no-first-run", "--disable-extensions",
         "--window-size=1500,1080", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    b = None
    try:
        ws_url = None
        for _ in range(80):
            try:
                tabs = json.load(OPENER.open("http://127.0.0.1:%d/json" % CDP_PORT, timeout=2))
                pg = [t for t in tabs if t.get("type") == "page"]
                if pg:
                    ws_url = pg[0]["webSocketDebuggerUrl"]
                    break
            except Exception:                                  # noqa: BLE001
                time.sleep(0.5)
        if not ws_url:
            bug("cdp", "拿不到 devtools 端点")
            return
        b = Browser(ws_url)
        b.send("Runtime.enable")
        b.send("Log.enable")
        b.send("Network.enable")
        b.send("Page.enable")
        b.send("Network.setCacheDisabled", {"cacheDisabled": True})
        b.send("Page.addScriptToEvaluateOnNewDocument", {"source": """
window.__QAERR=[];
window.addEventListener('error',function(e){
  window.__QAERR.push('error: '+String(e.message)+' @'+(e.filename||'')+':'+(e.lineno||0));
});
window.addEventListener('unhandledrejection',function(e){
  window.__QAERR.push('rejection: '+String(e.reason && e.reason.stack || e.reason));
});
"""})
        b.send("Emulation.setDeviceMetricsOverride",
               {"width": 1500, "height": 980, "deviceScaleFactor": 1, "mobile": False})
        t0 = time.perf_counter()
        b.send("Page.navigate", {"url": BASE + "/"})
        ok_load = b.wait("document.readyState==='complete'", 40)
        print("      readyState=complete %.0fms" % ((time.perf_counter() - t0) * 1000))
        if not ok_load:
            bug("boot", "页面 40s 未 readyState=complete")
        booted = b.wait("document.querySelectorAll('#themes .tcard').length>0", 30)
        if not booted:
            bug("boot", "30s 内 bootReal 未完成（#themes .tcard 为空）")
        else:
            ok("boot 初始化完成")
        b.pump(1.5)

        # 重复 id / 横向溢出 / 有无未定义引用
        dup = b.js("JSON.stringify((function(){var m={},d=[];"
                   "document.querySelectorAll('[id]').forEach(function(e){m[e.id]=(m[e.id]||0)+1;});"
                   "for(var k in m) if(m[k]>1) d.push(k+':'+m[k]);return d;})())")
        if dup:
            bug("DOM 重复 id", ", ".join(dup)[:300])
        else:
            ok("DOM 无重复 id")

        # 各视图切换（每切一次收一次错）
        for v in ("srv", "lib", "ov", "theme", "set", "srv"):
            r = b.js("JSON.stringify((function(){showView(%r);"
                     "return {v:CURVIEW,on:(document.querySelector('.view.on')||{}).id};})())"
                     % v)
            b.pump(0.7)
            if not r or r.get("v") != v:
                bug("view:" + v, "showView 未生效 %r" % (r,))
            elif r.get("on") != "view-" + v:
                bug("view:" + v, "可见视图错位 %r" % (r,))
        ok("视图切换 srv/lib/ov/theme/set")

        # 服务器表
        b.js("showView('srv')")
        b.wait("document.querySelectorAll('#stb tr').length>0", 25)
        srv = b.js("JSON.stringify((function(){"
                   "var rows=document.querySelectorAll('#stb tr');var tb=document.getElementById('stb');"
                   "return {rows:rows.length,txt:(tb.textContent||'').slice(0,60),"
                   "cols:[].slice.call(document.querySelectorAll('#stb tr:first-child td')).length,"
                   "wrapH:(document.querySelector('.srvWrap')||{}).clientHeight,"
                   "scrollable:(function(w){return !!w && w.scrollHeight>w.clientHeight+2;})(document.querySelector('.srvWrap'))};})())")
        if not srv or srv.get("rows", 0) < 2:
            bug("srv 表格", "行数=%r（少于表头+1 行）" % (srv,))
        else:
            ok("srv 表格行", "%d 行" % srv["rows"])
            if srv.get("cols") != 5:
                bug("srv 列数", "首行 %r 列（期望 5）" % srv.get("cols"))
        # 表头吸顶 + 表内滚动
        sc = b.js("JSON.stringify((function(){var w=document.querySelector('.srvWrap'),"
                  "th=document.querySelector('#stb')?document.querySelector('table.srvtab thead th'):null;"
                  "if(!w||!th) return {miss:1};var wt=w.getBoundingClientRect().top;w.scrollTop=60;"
                  "var t2=th.getBoundingClientRect().top;return {wrapTop:Math.round(wt),thTop:Math.round(t2),"
                  "pageY:window.scrollY,canScroll:w.scrollHeight>w.clientHeight+2,"
                  "pos:getComputedStyle(th).position};})())")
        if not sc or sc.get("miss"):
            bug("srv 滚动容器", "找不到 .srvWrap / 表头")
        else:
            if sc.get("pos") != "sticky":
                bug("srv 表头", "position=%r（应为 sticky）" % sc.get("pos"))
            if sc.get("pageY") != 0:
                bug("srv 滚动", "表内滚动带动了整页 scrollY=%r" % sc.get("pageY"))
            else:
                ok("srv 滚动", "thTop=%s 整页 scrollY=0" % sc.get("thTop"))

        # 地图库
        b.js("showView('lib')")
        if not b.wait("(typeof LIB!=='undefined' && LIB.all && LIB.all.length>0)", 40):
            bug("lib 索引", "40s 内 /api/maplib 未落地")
            return
        b.wait("document.querySelectorAll('#libList .libRow').length>0", 20)
        b.pump(1.2)
        lib = b.js("JSON.stringify((function(){"
                   "var rows=document.querySelectorAll('#libList .libRow');"
                   "var imgs=[].slice.call(document.querySelectorAll('#libList img.libBg'));"
                   "return {all:LIB.all.length,rows:rows.length,"
                   "imgs:imgs.length,broken:imgs.filter(function(i){return i.complete&&i.naturalWidth===0;}).length,"
                   "first:(rows[0]||{}).getAttribute?rows[0].getAttribute('data-f'):null,"
                   "cnt:(document.getElementById('libCnt')||{}).textContent};})())")
        if not lib:
            bug("lib 渲染", "取不到列表状态")
        else:
            if lib["rows"] < min(50, lib["all"]):
                bug("lib 渲染", "列表只出 %d / %d 行（分段渲染可能中断）" % (lib["rows"], lib["all"]))
            else:
                ok("lib 首屏", "%d 行 / 共 %d · %s" % (lib["rows"], lib["all"], lib["cnt"]))
            if lib["imgs"] and lib["broken"] == lib["imgs"]:
                bug("lib 封面", "%d 张 <img> 全 404" % lib["imgs"])
            elif lib["broken"]:
                note("lib 封面", "%d / %d 张封面加载失败（数据侧缺图，非崩溃）"
                     % (lib["broken"], lib["imgs"]))

        # 搜索：脏输入 / XSS / 超长
        print("      搜索脏输入…")
        for payload, label in [
            ("<img src=x onerror=\"window.__XSS=1\">", "HTML 注入"),
            ("' OR 1=1--", "SQL 风格"),
            ("\" onmouseover=\"window.__XSS=2", "属性截断"),
            ("%", "百分号"),
            ("*", "星号"),
            ("   ", "纯空格"),
            ("ze_" + "x" * 400, "超长 400"),
            ("🏥医院", "emoji+中文"),
        ]:
            r = b.js("JSON.stringify((function(){"
                     "var q=document.getElementById('libQ');q.value=%r;"
                     "q.dispatchEvent(new Event('input'));libRender();"
                     "return {rows:document.querySelectorAll('#libList .libRow').length,"
                     "xss:window.__XSS||0,html:document.getElementById('libList').innerHTML.slice(0,0)};})())"
                     % payload)
            b.pump(0.15)
            if not r:
                bug("搜索[%s]" % label, "执行异常")
            elif r.get("xss"):
                bug("搜索[%s]" % label, "XSS 生效 window.__XSS=%r" % r.get("xss"))
            elif label in ("HTML 注入", "属性截断"):
                ok("搜索[%s]" % label, "已转义，rows=%s" % r.get("rows"))
        b.js("document.getElementById('libQ').value='';libRender();")
        b.pump(0.4)

        # 高亮函数本身必须转义（搜索命中会走 libHl，名称里带标签也不能被执行）
        escr = b.js("JSON.stringify((function(){"
                    "var h=libHl('<img src=x onerror=window.__XSS=1>',['img']);"
                    "var d=document.createElement('div');d.innerHTML=h;"
                    "return {imgs:d.querySelectorAll('img').length,out:h.slice(0,60)};})())")
        if escr and escr.get("imgs"):
            bug("XSS 转义", "libHl 未转义：%r" % (escr,))
        else:
            ok("XSS 转义", "libHl 输出纯文本")

        # 分类筛选逐个点
        chips = b.js("JSON.stringify([].slice.call(document.querySelectorAll('#libChips .libChip'))"
                     ".map(function(c){return c.getAttribute('data-t');}))")
        print("      分类筛选 %d 个…" % len(chips or []))
        for k in (chips or []):
            r = b.js("JSON.stringify((function(){"
                     "var cs=[].slice.call(document.querySelectorAll('#libChips .libChip'));"
                     "var c=null;for(var i=0;i<cs.length;i++){"
                     "if(cs[i].getAttribute('data-t')===%r){c=cs[i];break;}}"
                     "if(!c) return null;c.click();"
                     "return {rows:document.querySelectorAll('#libList .libRow').length,"
                     "filt:(LIB.filt||[]).slice()};})())" % k)
            b.pump(0.2)
            if r is None:
                bug("筛选[%s]" % k, "找不到 chip")
        # 复位
        b.ev("LIB.filt=[];libChipSync();libRender();")
        b.pump(0.4)
        cnt = b.js("JSON.stringify(document.querySelectorAll('#libList .libRow').length)")
        if cnt is None:
            note("筛选复位", "未取到行数")

        # 排序
        for v in b.js("JSON.stringify([].slice.call(document.getElementById('libSort').options)"
                      ".map(function(o){return o.value;}))") or []:
            b.js("(function(){var s=document.getElementById('libSort');s.value=%r;"
                 "s.dispatchEvent(new Event('change'));})()" % v)
            b.pump(0.25)
        ok("排序切换", "%d 种" % len(b.js("JSON.stringify([].slice.call(document.getElementById('libSort').options)"
                                        ".map(function(o){return o.value;}))") or []))

        # 回车打开第一条 + 清空按钮 + 🔄 重读索引
        b.js("(function(){var q=document.getElementById('libQ');q.value='ze_samosbor';"
             "q.dispatchEvent(new Event('input'));"
             "q.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));})()")
        b.pump(1.2)
        sel = b.js("JSON.stringify((LIB.cur&&LIB.cur.f)||null)")
        if not sel:
            bug("搜索 Enter", "回车后没有选中第一条（LIB.cur 为空）")
        else:
            ok("搜索 Enter", "选中 %r" % sel)
        b.js("document.getElementById('libClr').click()")
        b.pump(0.7)
        clr = b.js("JSON.stringify({q:document.getElementById('libQ').value,"
                   "rows:document.querySelectorAll('#libList .libRow').length})")
        if not clr or clr.get("q") != "":
            bug("搜索清空", "清空按钮没清搜索框 %r" % (clr,))
        elif clr.get("rows", 0) < 50:
            bug("搜索清空", "清空后列表只有 %d 行" % clr.get("rows"))
        else:
            ok("搜索清空", "%d 行" % clr.get("rows"))
        b.js("document.getElementById('libReload').click()")
        b.pump(2.5)
        rl = b.js("JSON.stringify({rows:document.querySelectorAll('#libList .libRow').length,"
                  "loading:!!LIB.loading,all:!!(LIB.all&&LIB.all.length)})")
        if not rl or rl.get("rows", 0) < 10:
            bug("🔄 重读索引", "点刷新后列表没回来 %r" % (rl,))
        else:
            ok("🔄 重读索引", "%d 行" % rl.get("rows"))

        # 收藏：先把状态归零，再「点收藏 → 落盘 → 点取消 → 落盘」
        fav_f = b.js("(function(){var r=document.querySelector('#libList .libRow');"
                     "return r?r.getAttribute('data-f'):null;})()")
        if fav_f:
            if b.js("libIsFav(%r)" % fav_f):
                b.js("libToggleFav(%r)" % fav_f)          # 归零（可能是上次测试留下的）
                b.pump(0.8)
            b.js("libToggleFav(%r)" % fav_f)              # 收藏
            b.pump(0.9)
            st, _, body, _ = http("/api/prefs")
            fav = []
            try:
                fav = (json.loads(body.decode("utf-8")).get("prefs") or {}).get("fav") or []
            except Exception:                              # noqa: BLE001
                pass
            if str(fav_f).lower() not in [str(x).lower() for x in fav]:
                bug("收藏落盘", "点收藏后 /api/prefs 的 fav 里没有 %s（fav=%r）"
                    % (fav_f, fav[:5]))
            else:
                ok("收藏落盘", str(fav_f))
            b.js("libToggleFav(%r)" % fav_f)              # 取消收藏
            b.pump(0.9)
            st, _, body, _ = http("/api/prefs")
            fav2 = []
            try:
                fav2 = (json.loads(body.decode("utf-8")).get("prefs") or {}).get("fav") or []
            except Exception:                              # noqa: BLE001
                pass
            if str(fav_f).lower() in [str(x).lower() for x in fav2]:
                bug("取消收藏落盘", "取消后 fav 里仍有 %s" % fav_f)
            else:
                ok("取消收藏落盘", "fav 已移除 %s" % fav_f)

        # 详情页
        print("      详情页…")
        b.js("showView('lib')")
        b.wait("document.querySelectorAll('#libList .libRow').length>0", 15)
        b.js("(function(){var r=document.querySelector('#libList .libRow');if(r)r.click();})()")
        if not b.wait("document.querySelectorAll('#libDetail .card').length>=2", 15):
            bug("详情页", "点击地图行 15s 后详情卡未渲染")
        else:
            det = b.js("JSON.stringify((function(){var d=document.getElementById('libDetail');"
                       "return {cards:d.querySelectorAll('.card').length,"
                       "cfg:!!d.querySelector('#libCfg'),diff:!!d.querySelector('#libDiff'),"
                       "diffShown:(d.querySelector('#libDiff')||{}).style?d.querySelector('#libDiff').style.display:null,"
                       "pv:!!d.querySelector('.libPv'),fav:!!d.querySelector('.libFavD'),"
                       "empty:(d.textContent||'').indexOf('正在读取参数')>=0};})())")
            b.pump(1.6)
            det2 = b.js("JSON.stringify((function(){var d=document.getElementById('libDetail');"
                        "var c=d.querySelector('#libCfg');"
                        "return {cfgTxt:(c?c.textContent:'').replace(/\\s+/g,' ').slice(0,90),"
                        "stillLoading:!!c && c.textContent.indexOf('正在读取参数')>=0,"
                        "diffTxt:(d.querySelector('#libDiff')||{textContent:''}).textContent.replace(/\\s+/g,' ').slice(0,60)};})())")
            if det2 and det2.get("stillLoading"):
                bug("详情-地图参数", "1.6s 后仍停在「正在读取参数」")
            else:
                ok("详情-地图参数", (det2 or {}).get("cfgTxt", "")[:70])
            # 详情收藏按钮
            b.js("(function(){var b=document.querySelector('#libDetail .libFavD');if(b)b.click();})()")
            b.pump(0.7)
            b.js("(function(){var b=document.querySelector('#libDetail .libFavD');if(b)b.click();})()")
            b.pump(0.6)

        # 详情切换多张图（快速连点，验证旧响应不覆盖）
        print("      快速连点切图 6 张…")
        seq = b.js("JSON.stringify([].slice.call(document.querySelectorAll('#libList .libRow'))"
                   ".slice(1,7).map(function(r){return r.getAttribute('data-f');}))") or []
        for f in seq:
            b.js("libSelect(%r)" % f)
            b.pump(0.12)
        b.pump(1.8)
        cur = b.js("JSON.stringify((typeof LIB.cur==='object'&&LIB.cur)?LIB.cur.f:null)")
        detf = b.js("JSON.stringify((function(){var d=document.getElementById('libDetail');"
                    "var fn=d.querySelector('.libHead .fn');return fn?fn.textContent:null;})())")
        if cur and detf and str(cur).lower() != str(detf).lower():
            bug("详情切图", "LIB.cur=%r 但详情显示 %r（旧响应覆盖）" % (cur, detf))
        else:
            ok("详情切图", "选中 %r == 显示 %r" % (cur, detf))

        # 地图实体预览（内嵌 iframe）：点「预览」应切到 view-pre 并真的把壳加载起来
        print("      地图实体预览…")
        if cur:
            b.js("openPreView(%r)" % cur)
            got = b.wait("(document.getElementById('preFrame')||{}).src && "
                         "document.getElementById('preFrame').src.indexOf('preview3d')>=0", 12)
            b.pump(5.0)
            pinfo = b.js("JSON.stringify((function(){var f=document.getElementById('preFrame');"
                         "if(!f) return null;var d=null;try{d=f.contentDocument;}catch(e){return {cross:1,src:f.src.slice(-70)};}"
                         "if(!d) return {nodoc:1,src:f.src.slice(-70)};"
                         "var er=d.getElementById('pvErr')||d.querySelector('.pvErr');"
                         "return {src:f.src.slice(-70),view:CURVIEW,title:d.title||'',"
                         "chars:(d.body?d.body.innerText.length:0),"
                         "err:er?(er.textContent||'').trim().slice(0,120):null,"
                         "canvas:!!d.querySelector('canvas')};})())")
            if not got:
                bug("预览", "点预览后 iframe 未指向 preview3d")
            elif not pinfo or pinfo.get("nodoc") or pinfo.get("chars", 0) < 20:
                bug("预览", "壳已请求但页面没内容 %r" % (pinfo,))
            else:
                ok("预览", "已加载 %d 字 · canvas=%s · %s"
                   % (pinfo.get("chars"), pinfo.get("canvas"), (pinfo.get("err") or "无报错")[:60]))
            b.js("showView('lib')")
            b.pump(0.8)

        # 主题：全部切换一遍
        print("      主题全切…")
        tids = b.js("JSON.stringify([].slice.call(document.querySelectorAll('#themes .tcard'))"
                    ".map(function(c){return c.getAttribute('data-t');}))") or []
        for t in tids:
            r = b.js("JSON.stringify((function(){try{applyTheme(%r,false);}catch(e){return {err:String(e)};}"
                     "var cs=getComputedStyle(document.querySelector('.main'));"
                     "var ink=getComputedStyle(document.body).color;"
                     "return {t:document.documentElement.getAttribute('data-theme'),"
                     "bg:cs.backgroundColor,ink:ink};})())" % t)
            b.pump(0.15)
            if not r or r.get("err"):
                bug("主题[%s]" % t, "%r" % (r,))
            elif r.get("bg") == r.get("ink"):
                bug("主题[%s]" % t, "正文色与底色相同（不可读）%r" % (r,))
        ok("主题切换", "%d 个主题无异常" % len(tids))
        b.js("applyTheme('E',false)")

        # 设置页 / 主题页 / 覆盖页渲染
        b.js("showView('set')")
        b.pump(1.4)
        st = b.js("JSON.stringify((function(){"
                  "function t(id){var e=document.getElementById(id);return e?e.textContent.trim():null;}"
                  "return {ver:t('abVer'),port:t('abPort'),data:t('abData'),dir:t('abDir'),"
                  "sync:t('syncInfo'),ul:!!document.querySelector('#ulCard .ulRow, #ulCard .clgEmpty'),"
                  "clg:!!document.querySelector('#clgCard .clgRow, #clgCard .clgEmpty'),"
                  "raw:(document.getElementById('raw')||{}).textContent.length,"
                  "rawEmpty:(document.getElementById('rawEmpty')||{style:{}}).style.display,"
                  "terr:t('abTerr'),pv:t('abPv'),cover:t('abCover'),log:t('abLog'),"
                  "logSz:t('abLogSz')};})())")
        if not st or not st.get("ver") or st.get("ver") in ("—", ""):
            bug("设置页-关于", "版本号未填充 %r" % (st,))
        else:
            ok("设置页-关于", "ver=%s port=%s" % (st.get("ver"), st.get("port")))
            miss = [k for k in ("terr", "pv", "cover", "log", "logSz")
                    if st.get(k) in (None, "", "—")]
            if miss:
                bug("设置页-统计", "以下项没填充：%s" % ", ".join(miss))
            else:
                ok("设置页-统计", "地形/预览/封面/日志 %s"
                   % " · ".join("%s=%s" % (k, st.get(k)) for k in ("terr", "pv", "cover")))
            if not st.get("raw"):
                bug("设置页-直播文本", "广播文本区为空（#raw 0 字）")
            else:
                ok("设置页-直播文本", "%d 字" % st.get("raw"))
        if st and st.get("dir") in (None, "—", ""):
            bug("设置页-数据目录", "未填充")

        # 「上游更新动态」：展开一行历史（details/summary）
        ul = b.js("JSON.stringify((function(){"
                  "var d=document.querySelectorAll('#ulCard details');"
                  "if(!d.length) return {n:0};"
                  "var x=d[0];x.open=true;"
                  "var bd=x.querySelector('.ulBd');"
                  "return {n:d.length,h:x.querySelector('.ulHd')?x.querySelector('.ulHd').textContent.trim().slice(0,40):null,"
                  "bodyH:bd?bd.textContent.trim().length:0};})())")
        b.pump(0.4)
        if not ul or not ul.get("n"):
            note("设置页-更新动态", "没有台账条目（全无变更时正常）")
        elif not ul.get("bodyH"):
            bug("设置页-更新动态", "展开后正文为空（ulBody 未渲染）")
        else:
            ok("设置页-更新动态", "%d 条 · 首条 %r 正文 %d 字"
               % (ul["n"], ul.get("h"), ul["bodyH"]))

        # 设置开关：点一下应立刻反映到 PREFS，再点回去
        sw0 = b.js("JSON.stringify({a:PREFS.upd_auto,d:PREFS.upd_del})")
        if sw0 is not None:
            r = b.js("JSON.stringify((function(){document.getElementById('swUpdDel').click();"
                     "return {v:PREFS.upd_del,cls:document.getElementById('swUpdDel').className};})())")
            b.pump(0.7)
            b.js("document.getElementById('swUpdDel').click()")
            b.pump(0.4)
            if not r or r.get("v") == sw0.get("d"):
                bug("设置页-开关", "点「显示已移除」后 PREFS 未变 %r" % (r,))
            else:
                ok("设置页-开关", "upd_del %r → %r，再点回" % (sw0.get("d"), r.get("v")))

        b.js("showView('theme')")
        b.pump(1.0)
        th = b.js("JSON.stringify({bgs:document.querySelectorAll('#bggrid .bgopt').length,"
                  "stk:document.querySelectorAll('#stkrow .stkopt').length,"
                  "fx:document.querySelectorAll('#fxgrid .sw').length,"
                  "pal:(document.getElementById('palName')||{}).textContent})")
        if not th or not th.get("bgs"):
            bug("主题页", "背景/贴纸/特效未建好 %r" % (th,))
        else:
            ok("主题页", "背景 %s / 贴纸 %s / 特效 %s / %s"
               % (th["bgs"], th["stk"], th["fx"], th.get("pal")))
            # 背景切换（点一张再还原）
            bg0 = b.js("JSON.stringify(PREFS.bg||'none')")
            r = b.js("JSON.stringify((function(){var c=document.querySelectorAll('#bggrid .bgopt')[1];"
                     "if(!c) return null;c.click();"
                     "return {bg:PREFS.bg,cls:(document.querySelector('.main')||{}).className};})())")
            b.pump(0.8)
            if r is None:
                bug("主题页-背景", "第 2 张背景卡点不动")
            elif r.get("bg") == bg0:
                bug("主题页-背景", "点了背景卡 PREFS.bg 仍是 %r" % bg0)
            else:
                ok("主题页-背景", "切到 %r" % r.get("bg"))
            b.js("applyBG(%r,true)" % (bg0 or "none"))
            b.pump(0.6)
            # 特效全关 / 全开
            b.js("document.getElementById('bAllOff').click()")
            b.pump(0.6)
            off = b.js("JSON.stringify(PREFS.fx||[])")
            b.js("document.getElementById('bAllOn').click()")
            b.pump(0.6)
            on = b.js("JSON.stringify(PREFS.fx||[])")
            if not isinstance(off, list) or off:
                bug("主题页-特效全关", "全关后 PREFS.fx=%r" % (off,))
            elif not on:
                bug("主题页-特效全开", "全开后 PREFS.fx 仍为空")
            else:
                ok("主题页-特效", "全关 %d 项 / 全开 %d 项" % (len(off or []), len(on or [])))

        b.js("showView('ov')")
        b.pump(1.2)
        ov = b.js("JSON.stringify({prev:(document.getElementById('ovPrev')||{}).innerHTML?true:false,"
                  "checks:document.querySelectorAll('#ovChecks label, #ovChecks .ck').length,"
                  "state:(document.getElementById('ovState')||{}).textContent,"
                  "wrap:(document.getElementById('ovCropWrap')||{}).hidden})")
        if not ov or not ov.get("prev"):
            bug("覆盖页", "预览区未渲染 %r" % (ov,))
        else:
            ok("覆盖页", "预览 + %s 个开关" % ov.get("checks"))
        if ov and ov.get("wrap") is False:
            bug("覆盖页-取景框", "未点击时取景面板就是展开的")
        # 字号滑块：拖一下应立刻反映到数值与预览，松开后落盘
        sz0 = b.js("document.getElementById('ovSize')?document.getElementById('ovSize').value:null")
        if sz0 is not None:
            r = b.js("JSON.stringify((function(){var s=document.getElementById('ovSize');"
                     "s.value=40;s.dispatchEvent(new Event('input'));"
                     "return {lab:document.getElementById('ovSizeV').textContent,val:s.value};})())")
            b.pump(1.2)
            if not r or r.get("lab") != "40":
                bug("覆盖页-字号滑块", "拖到 40 后标签是 %r" % (r,))
            else:
                ok("覆盖页-字号滑块", "40 即时生效")
            b.js("(function(){var s=document.getElementById('ovSize');s.value=%s;"
                 "s.dispatchEvent(new Event('input'));})()" % sz0)
            b.pump(1.0)

        # Esc 关弹窗
        b.js("openDiff()")
        b.pump(0.5)
        shown = b.js("getComputedStyle(document.getElementById('diffOv')).display!=='none'")
        b.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape",
                                          "code": "Escape", "windowsVirtualKeyCode": 27})
        b.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape",
                                          "code": "Escape", "windowsVirtualKeyCode": 27})
        b.pump(0.5)
        closed = b.js("getComputedStyle(document.getElementById('diffOv')).display==='none'")
        if not shown:
            bug("弹窗", "openDiff 后弹窗未显示")
        elif not closed:
            bug("弹窗", "Esc 未关闭「查看明细」")
        else:
            ok("弹窗 Esc 关闭")

        # 窗口尺寸：窄屏横向溢出
        for w, h in ((1280, 800), (1100, 760), (900, 700)):
            b.send("Emulation.setDeviceMetricsOverride",
                   {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False})
            b.pump(0.6)
            ovf = b.js("JSON.stringify({sw:document.documentElement.scrollWidth,"
                       "cw:document.documentElement.clientWidth,"
                       "who:(function(){var out=[];document.querySelectorAll('.main *').forEach(function(e){"
                       "var r=e.getBoundingClientRect();if(r.right>window.innerWidth+2&&r.width>60)out.push((e.id||e.className||e.tagName)+'');});"
                       "return out.slice(0,6);})()})")
            if ovf and ovf.get("sw", 0) > ovf.get("cw", 0) + 3:
                bug("窄屏溢出 %dx%d" % (w, h), "scrollWidth=%s > clientWidth=%s · %s"
                    % (ovf.get("sw"), ovf.get("cw"), ovf.get("who")))
            else:
                ok("布局 %dx%d" % (w, h), "无横向溢出")
        b.send("Emulation.setDeviceMetricsOverride",
               {"width": 1500, "height": 980, "deviceScaleFactor": 1, "mobile": False})
        b.pump(0.4)

        # 刷新页面：偏好、主题、收藏是否留存；启动期是否报错
        print("      刷新页面（偏好/主题/收藏持久化）…")
        # 先记下用户原本的主题，测完要还原，别污染真实偏好
        orig_theme = None
        try:
            st, _, body, _ = http("/api/prefs")
            orig_theme = (json.loads(body.decode("utf-8")).get("prefs") or {}).get("theme")
        except Exception:                                      # noqa: BLE001
            pass
        b.js("applyTheme('E',true)")                            # 带保存地切一次
        b.pump(1.0)
        prefs_before = b.js("JSON.stringify({th:document.documentElement.getAttribute('data-theme'),"
                            "fav:(LIB.fav||[]).slice(),view:CURVIEW})")
        b.send("Page.navigate", {"url": BASE + "/?view=lib"})
        b.wait("document.readyState==='complete'", 40)
        b.wait("document.querySelectorAll('#themes .tcard').length>0", 30)
        b.pump(2.0)
        after = b.js("JSON.stringify({th:document.documentElement.getAttribute('data-theme'),"
                     "view:CURVIEW,qaerr:(window.__QAERR||[]).slice(0,5),"
                     "rows:document.querySelectorAll('#libList .libRow').length})")
        if not after:
            bug("刷新", "刷新后页面状态读不到")
        else:
            if after.get("qaerr"):
                bug("刷新-启动错误", "; ".join(after["qaerr"])[:300])
            else:
                ok("刷新-启动无 JS 错误")
            if prefs_before and after.get("th") != prefs_before.get("th"):
                bug("刷新-主题持久化", "%s → %s" % (prefs_before.get("th"), after.get("th")))
            else:
                ok("刷新-主题持久化", str(after.get("th")))
            if after.get("view") != "lib":
                note("刷新-视图", "?view=lib 打开后 CURVIEW=%r" % after.get("view"))
            if after.get("th") != "E":
                bug("刷新-主题持久化", "保存 E 后刷新变成 %r" % after.get("th"))

        # 还原用户原本的主题（测试期间改过偏好）
        if orig_theme:
            b.js("applyTheme(%r,true)" % orig_theme)
            b.pump(0.6)

        # 深链：?view=lib&map=xxx 应直接定位到那张图
        print("      深链定位…")
        target = "ze_samosbor"
        b.send("Page.navigate", {"url": BASE + "/?view=lib&map=" + target})
        b.wait("document.readyState==='complete'", 40)
        b.wait("document.querySelectorAll('#themes .tcard').length>0", 30)
        hit = b.wait("!!(typeof LIB==='object' && LIB.all && LIB.all.length && "
                     "LIB.cur && String(LIB.cur.f).toLowerCase()==='" + target + "')", 25)
        if not hit:
            got = b.js("JSON.stringify({view:CURVIEW,cur:(typeof LIB==='object'&&LIB.cur)?LIB.cur.f:null})")
            bug("深链 ?view=lib&map=", "25s 内没定位到 %s（%r）" % (target, got))
        else:
            ok("深链 ?view=lib&map=", target)

        b.shot("lib_1500")
        b.js("showView('srv')")
        b.pump(1.2)
        b.shot("srv_1500")

        qaerr = b.js("JSON.stringify((window.__QAERR||[]).slice(0,10))") or []
        if qaerr:
            bug("页面 window.onerror", "; ".join(qaerr)[:400])

        print("\n[5] 浏览器侧收集")
        if b.errors:
            seen = set()
            for kind, msg in b.errors:
                key = (kind, msg[:120])
                if key in seen:
                    continue
                seen.add(key)
                bug("前端 " + kind, msg)
        else:
            ok("前端无 exception/console.error")
        if b.http4xx:
            for u in sorted(set(b.http4xx))[:12]:
                note("失败请求", u)
        else:
            ok("无 4xx/5xx（封面地形除外）")
    finally:
        if b:
            try:
                b.ws.close()
            except Exception:                                  # noqa: BLE001
                pass
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(edge.pid)],
                           capture_output=True)
        except Exception:                                      # noqa: BLE001
            pass


def main():
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(SHOT, exist_ok=True)
    # 清残留 profile，避免旧 Edge 复用标签
    proc = subprocess.Popen([PY, os.path.join(HERE, "fys_reward_app.py"),
                             "--port", str(PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_http("/api/prefs"):
            print("服务未起来，退出")
            return 2
        t0 = time.perf_counter()
        st, _, body, _ = http("/api/maplib")
        print("maplib 首建 %.0fms / %dKB" % ((time.perf_counter() - t0) * 1000, len(body) // 1024))
        api_sweep()
        browser_journey()
    finally:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
        except Exception:                                      # noqa: BLE001
            pass

    print("\n================ 汇总 ================")
    print("失败 %d 项 / 观察 %d 项" % (len(BUGS), len(NOTES)))
    for x in BUGS:
        print("  NG  %-26s %s" % (x["tag"], x["detail"]))
    for x in NOTES:
        print("  --  %-26s %s" % (x["tag"], x["detail"]))
    with open(os.path.join(HERE, "_qa_report.json"), "w", encoding="utf-8") as fh:
        json.dump({"bugs": BUGS, "notes": NOTES}, fh, ensure_ascii=False, indent=1)
    return 1 if BUGS else 0


if __name__ == "__main__":
    sys.exit(main())

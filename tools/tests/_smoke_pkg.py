# -*- coding: utf-8 -*-
"""打包后手动冒烟：把发行目录里的 exe 拷到一个干净目录跑起来，逐条探关键接口。

替代 build_dist 的内置冒烟（那一步在本机会被沙箱「批量删除保护」拦下）：
  · 干净目录 = 没有 data\\overlay.json → 正好覆盖「全新安装」这条路径
    （2026-09-28 修的 ensure_ovcfg 崩溃就出在这里）
  · exe 旁优先：cover / terr / preview3d 的兜底逻辑也一并过一遍

用法：python _smoke_pkg.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/tests/ → 项目根
PKG_DIR = os.path.abspath(os.path.join(HERE, "..", "云朵小铺-FYS通关奖励看板"))
PKG_EXE = os.path.join(PKG_DIR, "FYS-Reward.exe")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
R = []


def check(name, ok, extra=""):
    R.append((name, bool(ok), extra))
    print(("PASS " if ok else "FAIL ") + name + (("  | " + str(extra)) if extra else ""))


def get(path, timeout=10):
    try:
        with OPENER.open(BASE + path, timeout=timeout) as fh:
            return fh.status, fh.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:                                            # noqa: BLE001
        return 0, b""


def js(path, timeout=10):
    code, raw = get(path, timeout)
    try:
        return code, json.loads(raw.decode("utf-8"))
    except Exception:                                            # noqa: BLE001
        return code, None


BASE = ""
if __name__ == "__main__":
    if not os.path.exists(PKG_EXE):
        raise SystemExit("找不到发行目录里的 exe：%s" % PKG_EXE)
    print("被测 exe：%s（%.1f MB）" % (PKG_EXE, os.path.getsize(PKG_EXE) / 1048576.0))
    tmp = os.path.join(tempfile.gettempdir(), "fys_smoke_pkg")
    sm = shutil.rmtree(tmp, ignore_errors=True)
    del sm
    os.makedirs(tmp, exist_ok=True)
    # onedir（2026-11-09 起）：exe + _internal 必须同目录才起得来 → 整包目录复制，
    # 排除 data\（全新安装语义）与 terr\（约 300MB，只补 1 个分包）。
    shutil.copytree(PKG_DIR, tmp,
                    ignore=shutil.ignore_patterns("data", "terr", "__pycache__"),
                    dirs_exist_ok=True)
    dst = os.path.join(tmp, "FYS-Reward.exe")
    # v2.14：预览壳与地形都随包（服务器停用），"只有 exe" 已不是合法安装形态。
    # copytree 已带 preview3d.html / cover\；这里补 1 个地形分包。
    terr_src = os.path.join(PKG_DIR, "terr")
    one_bin = ""
    if os.path.isdir(terr_src):
        for f in sorted(os.listdir(terr_src)):
            if f.endswith(".bin"):
                one_bin = f
                break
    if one_bin:
        os.makedirs(os.path.join(tmp, "terr"), exist_ok=True)
        shutil.copy2(os.path.join(terr_src, one_bin), os.path.join(tmp, "terr", one_bin))
    # 2026-11-15 起安装包**不带地形**（按需从托管下载），所以这里不再要求有 terr\
    check("干净目录：exe + _internal + 预览壳（地形按需下载）",
          os.path.exists(dst) and os.path.isdir(os.path.join(tmp, "_internal"))
          and os.path.exists(os.path.join(tmp, "preview3d.html")),
          sorted(os.listdir(tmp))[:8])

    # GSI 默认开启：冒烟时别去改用户真实 CS2 目录里的配置（只探测不写盘）
    env = dict(os.environ)
    env["FYS_GSI_NO_WRITE"] = "1"
    # --port 0：让系统随机挑端口（固定 8777 可能已被开发态实例占着 → 单实例预检会直接退出）
    proc = subprocess.Popen([dst, "--port", "0"], cwd=tmp, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logf = os.path.join(tmp, "data", "startup.log")
    port = None
    try:
        for _ in range(90):                     # 首次解包 + 起服务，给足 45 秒
            if os.path.exists(logf):
                try:
                    raw = open(logf, encoding="utf-8", errors="replace").read()
                except OSError:
                    raw = ""
                m = re.search(r"本地服务已启动 http://127\.0\.0\.1:(\d+)/", raw)
                if m:
                    port = int(m.group(1))
                    break
            time.sleep(0.5)
        check("exe 启动并起了本地服务", bool(port), "port=%s" % port)
        if not port:
            raise SystemExit(1)
        BASE = "http://127.0.0.1:%d" % port

        for _ in range(20):
            c, _b = get("/api/prefs", timeout=6)
            if c == 200:
                break
            time.sleep(0.5)

        c, j = js("/api/prefs")
        check("GET /api/prefs 200", c == 200, "HTTP %s" % c)
        # v2.14 修：偏好「读-改-写」必须串行（「↺ 恢复默认外观」一次点击连发
        # theme/bg/sticker 三个 set；不串行时后写的会把先写的键整个覆盖掉）
        import threading
        _keys = ["smoke_pref_%d" % i for i in range(6)]
        _ts = [threading.Thread(target=get, args=("/api/prefs?set=%s&val=1" % k, 8))
               for k in _keys]
        for _t in _ts:
            _t.start()
        for _t in _ts:
            _t.join()
        _c, _b = get("/api/prefs")
        try:
            _pf = (json.loads(_b.decode("utf-8")) or {}).get("prefs") or {}
        except ValueError:
            _pf = {}
        _miss = [k for k in _keys if k not in _pf]
        check("并发写偏好不丢键（恢复默认外观）", not _miss,
              ("丢失 %s" % _miss) if _miss else "6/6")
        c, j = js("/api/ovcfg")
        cfg = (j or {}).get("cfg") or {}
        check("GET /api/ovcfg 200 且回退默认值（全新安装不再崩）",
              c == 200 and cfg.get("layout") == "card" and cfg.get("mode") == "frameless",
              "HTTP %s %s" % (c, {k: cfg.get(k) for k in ("layout", "mode", "size")}))
        c, j = js("/api/ctl?do=ovpoll")
        check("GET /api/ctl?do=ovpoll 200", c == 200 and isinstance((j or {}).get("ct"), bool),
              "HTTP %s %s" % (c, j))
        c, j = js("/api/ctl?do=ovopen", timeout=20)
        check("启动屏幕覆盖 ok", (j or {}).get("ok") is True, j)
        on = False
        for _ in range(30):
            c, j = js("/api/ctl?do=ovstate")
            if (j or {}).get("on"):
                on = True
                break
            time.sleep(0.5)
        check("覆盖小窗进程存活", on, on)
        time.sleep(1.5)
        c, j = js("/api/ctl?do=ovstate")
        check("几秒后小窗仍在（没有自己消失）", (j or {}).get("on") is True, j)
        js("/api/ctl?do=ovclose")
        time.sleep(1.0)

        c, j = js("/api/status")
        check("GET /api/status 200", c == 200, "HTTP %s" % c)
        check("状态里带 upddiff 字段", j is not None and "upddiff" in (j or {}),
              (j or {}).get("upddiff"))
        c, j = js("/api/mapnames")
        check("GET /api/mapnames 200 且有内容", c == 200 and (j or {}).get("n", 0) > 100
              and isinstance((j or {}).get("names"), dict),
              "HTTP %s n=%s" % (c, (j or {}).get("n")))
        c, j = js("/api/about")
        check("GET /api/about 200", c == 200, "HTTP %s" % c)

        # 内置封面：exe 旁没有 cover\ 时应回退到包内资源
        cov = None
        for name in ("ze_1_schizo", "ze_2012_p", "ze_cabinet_v1_3"):
            c, raw = get("/cover/%s.jpg" % name)
            if c == 200 and len(raw) > 2000:
                cov = (name, c, len(raw))
                break
        check("封面可读（exe 旁没 cover\\ 时回退内置）", bool(cov), cov)

        c, raw = get("/api/preview")
        check("GET /api/preview 200（预览壳状态可查）", c == 200, "HTTP %s" % c)

        # 预览壳：v2.14 起随包（不再从云端下载），本地 shell 必须与包内那份一致
        local_shell = ""
        for cand in (os.path.join(HERE, "preview3d.html"),
                     os.path.join(HERE, "..", "地图实体预览-3D视图.html")):
            if os.path.exists(cand):
                local_shell = os.path.abspath(cand)
                break
        want = os.path.getsize(local_shell) if local_shell else 0
        t0 = time.time()
        c, raw = get("/preview3d", timeout=120)
        dt = time.time() - t0
        got = os.path.join(tmp, "preview3d.html")
        gs = os.path.getsize(got) if os.path.exists(got) else 0
        check("GET /preview3d 200 且整页可用", c == 200 and len(raw) > 1024 * 1024,
              "HTTP %s %.1f MB 用时 %.1fs" % (c, len(raw) / 1048576.0, dt))
        check("预览壳 = 包内那份（离线不联网）",
              bool(want) and gs == want, "%d vs %d" % (gs, want))

        # 地形：随包分包直接命中；缺失时立刻 404（不再等云端超时）
        if one_bin:
            c, raw = get("/terr/" + one_bin, timeout=10)
            check("地形分包可读（随包命中）", c == 200 and raw[:2] == b"\x1f\x8b",
                  "HTTP %s %d B" % (c, len(raw)))
        t0 = time.time()
        c, raw = get("/terr/9999999999.bin", timeout=40)
        dt = time.time() - t0
        # 地形 2026-11-15 起托管在 GitHub：不存在的 ID 要逐个源探，多源串行
        # （每个源超时有界）最坏可能较慢；这里只要求「有界」且给出明确状态，
        # 且同一 ID 10 分钟内不再重试（TERR_FAIL_TTL，第二次应秒回）。
        # 404 = 各源都确认未收录；502 = 有源没摸到（断网/镜像挂，可重试）——
        # 镜像状态随网络波动，断言只锁「有界 + 有明确状态」这个不变量。
        check("缺失地形有界返回（404 未收录 / 502 网络失败）",
              c in (404, 502) and dt < 35.0, "HTTP %s %.2fs" % (c, dt))
        t1 = time.time()
        get("/terr/9999999999.bin", timeout=10)
        check("缺失地形重试秒回（10 分钟负缓存）", time.time() - t1 < 2.0,
              "%.2fs" % (time.time() - t1))

        c, j = js("/api/update/check")
        _j = j or {}
        # v2.16 起更新通道改走 GitHub 仓库（不再是「离线版」）：能拿到清单即算正常，
        # 网络实在不通时允许 online 失败但不许抛 error 结构异常。
        check("更新检查可用（GitHub 通道，非离线版）",
              c == 200 and (_j.get("offline") is not True) and _j.get("error") is None
              and bool(_j.get("ver")), _j)

        raw = ""
        try:
            raw = open(logf, encoding="utf-8", errors="replace").read()
        except OSError:
            pass
        check("日志里没有 UnboundLocalError", "UnboundLocalError" not in raw,
              [ln for ln in raw.splitlines() if "UnboundLocalError" in ln][:2])
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, timeout=15)
        time.sleep(0.5)
    bad = [x for x in R if not x[1]]
    print("== %d/%d 通过 ==" % (len(R) - len(bad), len(R)))
    if bad:
        for x in bad:
            print("  失败:", x[0], x[2])
        sys.exit(1)
    print("（冒烟临时目录：%s，可手动删）" % tmp)

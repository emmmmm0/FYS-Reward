# -*- coding: utf-8 -*-
"""风雲社官网（fyscs.cn）免登录数据源。

只使用一个接口：
    GET https://fyscs.cn/silverwing/system/dashboard

未登录时可拿到全部服务器清单（名称 / 实时人数 / host / port / serverId）；
但 `map`、`translation` 两个字段后端会写成字符串「登录后查看」，
服务器详情与关卡（stage/total）走 SSE 且需要登录 —— 本模块不涉及，
关卡仍由官方 fys-client 的广播文件提供。

用途：给「服务器实时看板」做人数交叉校验（官网口径 vs 本机 A2S 口径）。
"""

import json
import os
import socket
import ssl
import threading
import time
import urllib.request

DASHBOARD_URL = os.environ.get(
    "FYS_WEB_DASHBOARD", "https://fyscs.cn/silverwing/system/dashboard")
TTL = float(os.environ.get("FYS_WEB_TTL", "20"))          # 缓存有效期（秒）
TIMEOUT = float(os.environ.get("FYS_WEB_TIMEOUT", "6"))   # 单次请求超时
# 域名解析缓存：sN.cs2ze.com 的 IP 会被运维换（2026-11-15 实测 02#/06# 都换过），
# 以前缓存 1 小时 → 换 IP 后看板最长一小时都打不开那台服。降到 5 分钟。
IP_TTL = 300.0
LOGIN_PLACEHOLDER = "登录后查看"

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "identity",
    "X-Client": "swallowtail",        # 官网自己的前端标识，缺了会被拒
    "Referer": "https://fyscs.cn/",
    "Origin": "https://fyscs.cn",
}

_CTX = ssl.create_default_context()
try:                                   # 个别机器证书链不全，退化为不校验
    _CTX.check_hostname = True
    _CTX.verify_mode = ssl.CERT_REQUIRED
except Exception:                      # noqa: BLE001
    pass
_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),   # 绕开系统代理，避免本地代理干扰
    urllib.request.HTTPSHandler(context=_CTX))

_lock = threading.Lock()
_SNAP = {"ok": False, "at": 0.0, "try": 0.0, "err": "尚未获取", "by_addr": {},
         "by_port": {}, "view": {}, "count": 0, "ze": []}
_IP_CACHE = {}
_BOOTED = [False]


# ─────────────────── 抓取 ───────────────────
def _decompress(raw, enc):
    enc = (enc or "").lower()
    try:
        if enc == "gzip":
            import gzip
            return gzip.decompress(raw)
        if enc == "deflate":
            import zlib
            return zlib.decompress(raw, -15)
        if enc == "br":
            import brotli
            return brotli.decompress(raw)
    except Exception:                                      # noqa: BLE001
        return raw
    return raw


def _http_json(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers=_HEADERS)
    with _OPENER.open(req, timeout=timeout) as r:
        raw = _decompress(r.read(), r.headers.get("Content-Encoding"))
    return json.loads(raw.decode("utf-8", "replace"))


# ─────────────────── 地址归一 ───────────────────
def _norm_host(h):
    return (h or "").strip().lower()


def host_ip(host, timeout=2.0):
    """域名 -> IP，带缓存；失败返回 None。"""
    h = _norm_host(host)
    if not h:
        return None
    if h.replace(".", "").isdigit():                       # 已经是 IP
        return h
    now = time.time()
    hit = _IP_CACHE.get(h)
    if hit and now - hit[0] < IP_TTL:
        return hit[1]
    ip = None
    try:
        socket.setdefaulttimeout(timeout)
        ip = socket.gethostbyname(h)
    except Exception:                                      # noqa: BLE001
        ip = None
    _IP_CACHE[h] = (now, ip)
    return ip


def _is_ze(name, short):
    s = "%s %s" % (name or "", short or "")
    return ("僵尸逃跑" in s) or ("僵尸" in s and "逃跑" in s)


def _index(servers):
    """构造 addr 索引：ip:port 优先，其次 port。"""
    by_addr, by_port, ze = {}, {}, []
    for s in servers:
        if not isinstance(s, dict):
            continue
        host = _norm_host(s.get("host"))
        port = s.get("port")
        if not host or not isinstance(port, int):
            continue
        item = {
            "server_id": s.get("serverId"),
            "short": s.get("shortName"),
            "name": s.get("name"),
            "host": host,
            "port": port,
            "players": s.get("currentPlayers"),
            "maxplayers": s.get("maxPlayers"),
            "game": s.get("game"),
            "mode": s.get("modeId"),
            "ze": _is_ze(s.get("name"), s.get("shortName")),
        }
        ip = host_ip(host)
        if ip:
            by_addr["%s:%d" % (ip, port)] = item
            item["ip"] = ip
        # 端口兜底：同端口多个时只保留第一个，避免误判
        by_port.setdefault(port, item)
        if item["ze"]:
            ze.append(item)
    return by_addr, by_port, ze


def _refresh():
    try:
        data = _http_json(DASHBOARD_URL)
    except Exception as e:                                 # noqa: BLE001
        with _lock:
            _SNAP["err"] = "%s: %s" % (type(e).__name__, e)
            _SNAP["ok"] = False
        return False
    servers = data.get("servers") if isinstance(data, dict) else None
    if not isinstance(servers, list):
        with _lock:
            _SNAP["err"] = "返回结构异常"
            _SNAP["ok"] = False
        return False
    by_addr, by_port, ze = _index(servers)
    view = data.get("view") if isinstance(data.get("view"), dict) else {}
    with _lock:
        _SNAP.update(ok=True, at=time.time(), err=None, by_addr=by_addr,
                     by_port=by_port, view=view, count=len(servers), ze=ze)
    return True


def _worker():
    while True:
        _refresh()
        time.sleep(max(5.0, TTL))


def _boot():
    if _BOOTED[0]:
        return
    _BOOTED[0] = True
    t = threading.Thread(target=_worker, name="fys-web", daemon=True)
    t.start()


# ─────────────────── 对外 ───────────────────
def snapshot(force=False, sync=False):
    """取缓存快照；首次调用启动后台线程。sync=True 时阻塞抓一次。"""
    if force or sync:
        _refresh()
    else:
        _boot()
        # 只在「从未成功过」且「距上次尝试超过 10 秒」时由调用方同步补一次。
        # 关键：把「尝试时刻」与「成功时刻」分开记 —— 原来只看 at（仅成功时写），
        # 官网不可达时 at 永远是 0.0，于是每个 /api/servers 请求都会同步跑一次
        # 6 秒超时的 HTTPS 请求，页面每 15 秒就卡 6 秒，还占住一个 HTTP 线程。
        need_sync = False
        with _lock:
            if _SNAP["at"] == 0.0 and (time.time() - _SNAP.get("try", 0.0)) > 10.0:
                _SNAP["try"] = time.time()
                need_sync = True
        if need_sync:
            _refresh()                                     # 首次同步抓一次，失败也不阻塞后续
    with _lock:
        s = dict(_SNAP)
        s["by_addr"] = dict(_SNAP["by_addr"])
        s["by_port"] = dict(_SNAP["by_port"])
        s["ze"] = list(_SNAP["ze"])
    s["age"] = (time.time() - s["at"]) if s["at"] else None
    s["at_str"] = time.strftime("%H:%M:%S", time.localtime(s["at"])) if s["at"] else None
    return s


def lookup(address, snap=None):
    """按 'ip:port' 找官网条目；找不到再按端口兜底。返回 (item, how) 或 (None, None)。"""
    snap = snap or snapshot()
    addr = (address or "").strip().lower()
    if not addr:
        return None, None
    it = snap.get("by_addr", {}).get(addr)
    if it:
        return it, "addr"
    if ":" in addr:
        try:
            port = int(addr.rsplit(":", 1)[1])
        except (TypeError, ValueError):
            return None, None
        it = snap.get("by_port", {}).get(port)
        if it:
            return it, "port"
    return None, None


def summary(snap=None):
    """官网汇总：在线服务器数 / 玩家数 / 总容量。"""
    snap = snap or snapshot()
    v = snap.get("view") or {}
    return {
        "ok": bool(snap.get("ok")),
        "at": snap.get("at_str"),
        "err": snap.get("err"),
        "servers": snap.get("count") or 0,
        "ze": len(snap.get("ze") or []),
        "players": v.get("onlinePlayers"),
        "slots": v.get("maxPlayers"),
        "clients": v.get("onlineClients"),
    }


if __name__ == "__main__":                                 # 自测
    s = snapshot(force=True, sync=True)
    print("ok=%s at=%s err=%s 服务器=%d ZE=%d" %
          (s["ok"], s["at_str"], s["err"], s["count"], len(s["ze"])))
    print("view:", s["view"])
    for it in (s["ze"] or [])[:12]:
        print("   %-22s %s:%s  %s/%s" % (it["short"], it["host"], it["port"],
                                         it["players"], it["maxplayers"]))

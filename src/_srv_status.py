#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""風雲社服务器常驻 A2S 探测服务（云端状态中枢）。

每 30 秒对 9 台服务器做一轮 A2S_INFO（各 3 次重试）+ A2S_PLAYER，
结果原子写入 /usr/share/caddy/status.json，供云朵小铺客户端读取。
同时每 10 分钟记一条历史到 /usr/share/caddy/hist.json（保留 24 小时）。

设计要点：
  · 服务端常驻重试，单轮成功率远高于客户端单发，客户端只读结果即可；
  · 原子写（.tmp + os.replace），客户端永远读不到半截 JSON；
  · 任何异常都不退出主循环，保证 7x24 在线。
"""
import json
import os
import socket
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor

SRV = [
    ("110.42.9.155", 27015, "01#"),
    ("110.42.9.203", 27025, "02#"),
    ("110.42.9.139", 27035, "03#"),
    ("110.42.9.138", 27045, "04#"),
    ("110.42.9.138", 27055, "05#"),
    ("110.42.9.107", 27065, "06#"),
    ("110.42.9.139", 27075, "07#"),
    ("110.42.9.107", 27085, "08#"),
    ("110.42.9.203", 27095, "09#"),
]

OUT = "/usr/share/caddy/status.json"
HIST = "/usr/share/caddy/hist.json"
GAP = 30
HIST_GAP = 600
HIST_MAX = 144

# 風雲社 9 台实测：A2S_PLAYER 一律返回 count=0（服务端屏蔽玩家名单），
# 所以默认不再发这次查询——省掉每轮 9 次无谓的 UDP 往返，也少挨限速。
# 哪天服务器开放了名单，把这里改成 True 即可，status.json 会多出 names 字段。
WANT_PLAYERS = False

Q = b"\xFF\xFF\xFF\xFFTSource Engine Query\x00"


def _info(host, port, to=1.5, att=3):
    """A2S_INFO（含 challenge 应答），失败重试 att 次。"""
    for _ in range(att):
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(to)
            s.sendto(Q, (host, port))
            d, _ = s.recvfrom(4096)
            if len(d) >= 5 and d[4:5] == b"A":
                s.sendto(Q + d[5:9], (host, port))
                d, _ = s.recvfrom(4096)
            s.close()
            s = None
            if len(d) < 6 or d[:4] != b"\xFF\xFF\xFF\xFF" or d[4:5] != b"I":
                continue
            i, o = 6, {}
            for k in ("name", "map", "folder", "game"):
                j = d.index(b"\x00", i)
                o[k] = d[i:j].decode("utf-8", "replace")
                i = j + 1
            o["appid"] = struct.unpack_from("<H", d, i)[0]
            i += 2
            o["players"], o["maxplayers"], o["bots"] = d[i], d[i + 1], d[i + 2]
            return o
        except Exception:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
            time.sleep(0.25)
    return None


def _players(host, port, to=1.5):
    """A2S_PLAYER，拿不到返回 None（部分服务器会屏蔽）。"""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(to)
        s.sendto(b"\xFF\xFF\xFF\xFF\x55\xFF\xFF\xFF\xFF", (host, port))
        d, _ = s.recvfrom(8192)
        if not (len(d) >= 5 and d[4:5] == b"A"):
            return None
        s.sendto(b"\xFF\xFF\xFF\xFF\x55" + d[5:9], (host, port))
        d, _ = s.recvfrom(16384)
        if len(d) < 6 or d[4:5] != b"D":
            return None
        n, i, out = d[5], 6, []
        for _ in range(min(n, 128)):
            if d[i] != 0:
                break
            i += 1
            j = d.index(b"\x00", i)
            out.append(d[i:j].decode("utf-8", "replace"))
            i = j + 9
        return out
    except Exception:
        return None
    finally:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass


def probe(row):
    host, port, lab = row
    a = _info(host, port)
    r = {"address": "%s:%d" % (host, port), "host": host, "port": port,
         "label": lab, "ok": a is not None}
    if a:
        r["name"] = a["name"]
        r["map"] = a["map"]
        r["players"] = a["players"]
        r["maxplayers"] = a["maxplayers"]
        if WANT_PLAYERS:
            pl = _players(host, port)
            if pl:
                r["names"] = pl[:64]
    return r


def _dump(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def main():
    try:
        with open(HIST, encoding="utf-8") as f:
            hist = json.load(f)
    except Exception:
        hist = []
    last = 0.0
    while True:
        try:
            with ThreadPoolExecutor(max_workers=9) as ex:
                rows = list(ex.map(probe, SRV))
            rows.sort(key=lambda r: -(r.get("players") or 0))
            now = time.time()
            data = {"ts": int(now),
                    "str": time.strftime("%H:%M:%S", time.localtime(now)),
                    "gap": GAP,
                    "live": sum(1 for r in rows if r["ok"]),
                    "total": sum(r.get("players") or 0 for r in rows),
                    "servers": rows}
            _dump(OUT, data)
            if now - last >= HIST_GAP:
                last = now
                hist.append({"t": int(now), "p": data["total"],
                             "m": {r["label"]: r.get("map")
                                   for r in rows if r["ok"]}})
                hist = hist[-HIST_MAX:]
                _dump(HIST, hist)
            sys.stderr.write("[%s] live=%d total=%d\n"
                             % (data["str"], data["live"], data["total"]))
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write("loop err: %r\n" % (e,))
            sys.stderr.flush()
        time.sleep(GAP)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""进服诊断（取证）：「进入服务器后显示未在服务器内」到底卡在哪一级信号。

判定链（reward_server.resolve()）：
    in_server=True   -> 在服内，正常显示
    in_server=False  -> 直接判「未在服务器内」
    in_server=None   -> 无法判断，交给 A2S / 广播

in_server 只来自 current_server.detect() 的 netstat UDP 对端比对。本脚本
在**你已经在服务器里**的时候运行，逐秒记录：

    cs2 pid / netstat 原始 UDP 行 / udp_peers / 选中的地址与来源 /
    in_server / peer_seen / away_sec / A2S 结果

用法：
    python _diag_srv.py [采样秒数，默认 24]
    python _diag_srv.py --once        # 只跑一轮，立刻出结果

结果同时写入同目录 _srv_diag.txt（UTF-8，可用记事本直接看）。
"""
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import current_server as C                                        # noqa: E402

OUT = os.path.join(HERE, "_srv_diag.txt")
FIELDS = ("game_running", "cs2_path", "available", "address", "addr_source",
          "in_server", "peer_seen", "udp_peers", "away_sec", "query_ok",
          "query_error", "server_name", "map", "players", "stale", "reason",
          "my_name")


def raw_udp(only_connected=True, pids=None):
    """netstat 的 UDP 原始行；only_connected=True 只留带对端的行。"""
    try:
        r = subprocess.run(["netstat", "-ano", "-p", "UDP"], capture_output=True,
                           text=True, encoding="mbcs", errors="replace",
                           timeout=6, creationflags=0x08000000)
    except Exception as e:                                        # noqa: BLE001
        return ["<netstat 失败 %r>" % e]
    want = set(int(p) for p in (pids or []))
    rows = []
    for line in (r.stdout or "").splitlines():
        s = " ".join(line.split())
        if not s.upper().startswith("UDP"):
            continue
        if want:
            try:
                if int(s.split()[-1]) not in want:
                    continue
            except (ValueError, IndexError):
                continue
        elif only_connected and ("*:*" in s or s.upper().startswith("UDP 0.0.0.0:0")):
            continue
        rows.append(s)
    return rows


def main():
    args = [a for a in sys.argv[1:]]
    once = "--once" in args
    secs = 1 if once else 24
    for a in args:
        if a.isdigit():
            secs = int(a)

    buf = io.StringIO()

    def w(s=""):
        print(s)
        buf.write(s + "\n")

    w("=" * 72)
    w("  服务器状态诊断   %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    w("=" * 72)
    w("  说明：请在【已经在服务器里】的时候运行本脚本。")
    w("")
    w("── 静态环境 ──────────────────────────────────────────────")
    root = C.steam_root(force=True)
    w("  Steam 目录      %s" % root)
    pids = C.cs2_pids()
    w("  cs2.exe PID     %s" % (pids or "（未运行）"))
    w("  cs2.exe 路径    %s" % (C._proc_path(pids[0]) if pids else "—"))
    w("  Steam 昵称      %s" % C.local_persona(root))
    last, lp = C.last_connect(root)
    w("  连接日志        %s" % lp)
    if last:
        w("  最近一次 connect %s  (%s)" % (last.get("address"), last.get("ts")))
    w("  固定 9 台服      %s" % ", ".join(
        "%s:%d" % (h, p) for h, p, _ in C.FYS_SERVERS))

    w("")
    w("── netstat 里「有对端」的 UDP（整机，不按 PID 过滤）──────")
    rows = raw_udp()
    if not rows:
        w("  （无：Windows 这一步看不到任何已连接的 UDP 套接字）")
    for r in rows:
        w("    %s" % r)

    w("")
    w("── cs2.exe 的全部 UDP 行（含未连接 *:*）─────────────────")
    if not pids:
        w("  （cs2.exe 未运行）")
    else:
        c2 = raw_udp(only_connected=False, pids=pids)
        if not c2:
            w("  （cs2.exe 一个 UDP 套接字都没有）")
        for r in c2:
            w("    %s" % r)

    w("")
    w("── 逐秒采样（每 2 秒一次）────────────────────────────────")
    hdr = "  %-5s %-6s %-6s %-22s %-11s %-8s %-5s %-6s %-8s %-6s %s" % (
        "t", "cs2", "peers", "addr", "addr_src", "in_srv", "peer", "away", "a2s", "map", "reason")
    w(hdr)
    w("  " + "-" * (len(hdr) - 2))

    t0 = time.time()
    seen = []
    n = 0
    while True:
        el = time.time() - t0
        if el > secs:
            break
        n += 1
        d = C.detect(force=True)
        a2s = "err:%s" % d.get("query_error") if not d.get("query_ok") else "ok"
        w("  %-5.0f %-6s %-6d %-22s %-11s %-8s %-5s %-6.1f %-8s %-6s %s" % (
            el,
            "yes" if d.get("game_running") else "no",
            len(d.get("udp_peers") or []),
            str(d.get("address")),
            str(d.get("addr_source")),
            str(d.get("in_server")),
            "T" if d.get("peer_seen") else "F",
            float(d.get("away_sec") or 0.0),
            a2s,
            str(d.get("map")),
            str(d.get("reason"))[:40]))
        seen.append(d)
        if once:
            break
        time.sleep(2)

    pids2 = C.cs2_pids()
    if pids2:
        w("")
        w("── 采样结束时 cs2.exe 的 UDP 行 ──────────────────────────")
        for r in raw_udp(only_connected=False, pids=pids2):
            w("    %s" % r)

    w("")
    w("── 结论 ─────────────────────────────────────────────────")
    lastd = seen[-1] if seen else {}
    peers = lastd.get("udp_peers") or []
    w("  cs2 在跑        %s" % lastd.get("game_running"))
    w("  netstat 对端数  %d %s" % (len(peers), peers[:8]))
    w("  选中地址        %s（来源 %s）" % (lastd.get("address"), lastd.get("addr_source")))
    w("  in_server       %s" % lastd.get("in_server"))
    w("  A2S 查询        %s  map=%s players=%s" % (
        "成功" if lastd.get("query_ok") else "失败(%s)" % lastd.get("query_error"),
        lastd.get("map"), lastd.get("players")))
    w("")
    if not lastd.get("game_running"):
        w("  → CS2 没在运行，本次诊断无效。请在【进入服务器后】重跑。")
    elif not peers:
        w("  → 【关键】netstat 完全看不到 cs2.exe 的 UDP 对端。")
        w("    若此时你确实在服务器里，说明现在的 CS2 用未 connect 的 UDP 套接字，")
        w("    netstat 通道失效 -> 连续 %d 秒后会被误判 in_server=False -> 「未在服务器内」。"
          % int(C.AWAY_SEC))
    elif lastd.get("addr_source") == "steam-log":
        w("  → netstat 有对端但没匹配上「当前服」地址（地址来自 Steam 日志）。")
        w("    常见原因：连的是域名/端口不在 27015~27999/对端走 SDR 中继。")
    else:
        w("  → netstat 正常匹配到当前服，判定链工作正常。")
        w("    若界面仍显示「未在服务器内」，问题在 reward_server.resolve() 的后续分支。")
    w("=" * 72)
    w("  完整报告已写入 %s" % OUT)

    with open(OUT, "w", encoding="utf-8-sig", newline="\r\n") as fh:
        fh.write(buf.getvalue())


main()

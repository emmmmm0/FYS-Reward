# -*- coding: utf-8 -*-
"""给「地图库有、预览壳没有」的每一张图找工坊 ID，产出下载清单。

数据来源（按优先级）：
  1) EXG 公开表 list.darkrp.cn（Name -> WorkshopId）：覆盖 99 张 EXG 补充图
  2) _ghcrawl/_wsmap.json 的 mapping（基础名 -> pid）
  3) _missing_ws_all.json / _missing_ws.json / _missing_ws2.json / _missing_ids.json
  4) _ghcrawl/_workshop_maps.json（vpk 索引，含 item）

输出 _gap_ws.json：{name: pid}，只包含**还没在预览壳里**的图；
未解析的单独打印（这些无法补，需要人工找 ID）。

用法：python _build_gap_ws.py [--offline]
"""
import base64
import gzip
import io
import json
import os
import re
import struct
import sys
import urllib.request
import zlib

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
FDIR = os.path.join(ROOT, "fys-reward")
OFFLINE = "--offline" in sys.argv
EXG_URL = "https://list.darkrp.cn:9000/ServerList/CurrentCs2MapStatus"


def read_json(p, default=None):
    if not os.path.exists(p):
        return default
    return json.load(io.open(p, encoding="utf-8"))


def pv_names():
    """预览壳收录的地图名（小写）。"""
    raw = io.open(os.path.join(FDIR, "preview3d.html"), "rb").read()
    i = raw.find(b'<script id="payload"')
    j = raw.find(b">", i)
    k = raw.find(b"</script>", j)
    blob = base64.b64decode(re.sub(rb"\s+", b"", raw[j + 1:k]))
    if blob[:2] == b"\x1f\x8b":
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        out = bytearray()
        need = None
        buf = blob
        while buf:
            piece = d.decompress(buf, 4 << 20)
            out += piece
            buf = d.unconsumed_tail
            if need is None and len(out) >= 4:
                need = 4 + struct.unpack("<I", bytes(out[:4]))[0]
            if need is not None and len(out) >= need:
                break
            if not piece and not buf:
                break
        blob = bytes(out[:need]) if need else b""
    jlen = struct.unpack("<I", blob[:4])[0]
    data = json.loads(blob[4:4 + jlen].decode("utf-8"))
    return set(str(v.get("m") or "").lower() for v in data["maps"].values() if v.get("m"))


names = pv_names()
maps = read_json(os.path.join(FDIR, "data", "maps.json"), {})
lib = sorted(maps)
gap = [n for n in lib if n.lower() not in names]
print("地图库 %d 张 · 壳内 %d 张 · 缺口 %d 张" % (len(lib), len(names), len(gap)))

# ---------------------------------------------------------------- pid 来源
pid_of = {}


def add(nm, pid):
    nm = str(nm or "").strip()
    pid = str(pid or "").strip()
    if nm and pid.isdigit():
        pid_of.setdefault(nm.lower(), set()).add(pid)


wsmap = read_json(os.path.join(FDIR, "_ghcrawl", "_wsmap.json"), {}) or {}
for nm, pid in (wsmap.get("mapping") or {}).items():
    add(nm, pid)
for f in ("_missing_ws_all.json", "_missing_ws.json", "_missing_ws2.json"):
    for nm, pid in (read_json(os.path.join(FDIR, f), {}) or {}).items():
        add(nm, pid)
for x in (read_json(os.path.join(FDIR, "_ghcrawl", "_missing_ids.json"), []) or []):
    parts = str(x.get("key") or "").split("/")
    add(parts[-2] if len(parts) > 1 else "", x.get("pid"))
for nm, v in (read_json(os.path.join(FDIR, "_ghcrawl", "_workshop_maps.json"), {}) or {}).items():
    add(nm, (v or {}).get("item"))

# EXG 表：Name -> WorkshopId（覆盖 ze_1_schizo 这类补充图）
exg = None
if not OFFLINE:
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        exg = json.loads(op.open(EXG_URL, timeout=25).read().decode("utf-8", "replace"))
        print("EXG 在线表：%d 条" % len(exg))
    except Exception as ex:                                      # noqa: BLE001
        print("[warn] EXG 在线表拉取失败：%r" % (ex,))
if not isinstance(exg, list):
    exg = read_json(os.path.join(FDIR, "_exg_maps.json"), []) or []
    print("EXG 本地快照：%d 条" % len(exg))
for it in exg:
    if isinstance(it, dict):
        add(it.get("Name"), it.get("WorkshopId"))

# ---------------------------------------------------------------- 匹配
def norm(n):
    return re.sub(r"_(p|cs2|cs2_l|z|t|b\d+|v\d+|\d+)$", "", n or "").lower()


norm_index = {}
for nm, pids in pid_of.items():
    norm_index.setdefault(norm(nm), set()).update(pids)

out, miss = {}, []
for n in gap:
    pids = pid_of.get(n.lower()) or norm_index.get(norm(n)) or set()
    if len(pids) == 1:
        out[n] = sorted(pids)[0]
    elif len(pids) > 1:
        # 多个候选：优先名字完全一致的
        exact = pid_of.get(n.lower())
        out[n] = sorted(exact)[0] if exact else sorted(pids)[0]
        print("  ! %s 有多个候选 %s，取 %s" % (n, sorted(pids), out[n]))
    else:
        miss.append(n)

print("\n解析到工坊 ID：%d / %d" % (len(out), len(gap)))
cat = lambda n: (maps.get(n) or {}).get("cat")
exg_gap = [n for n in gap if cat(n) == "exg"]
print("  其中 EXG 补充图 %d 张，解析到 %d 张"
      % (len(exg_gap), len([n for n in exg_gap if n in out])))
if miss:
    print("\n未解析到 ID 的 %d 张（无法自动补）：" % len(miss))
    for n in miss:
        print("   %-42s cat=%s" % (n, cat(n)))

with io.open(os.path.join(FDIR, "_gap_ws.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
print("\n已写 _gap_ws.json（%d 条）" % len(out))

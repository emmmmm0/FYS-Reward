# -*- coding: utf-8 -*-
"""审计「地图实体预览」覆盖：地图库全量 vs 预览页 DATA.maps。

用法：
    python _audit_pv_ents.py            # 概要 + 缺图清单
    python _audit_pv_ents.py --dump     # 额外打印 DATA 顶层结构
"""
import base64
import gzip
import io
import json
import os
import re
import struct
import sys

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
FDIR = os.path.join(ROOT, "fys-reward")
HTML = os.path.join(FDIR, "preview3d.html")
DUMP = "--dump" in sys.argv


def load_data():
    raw = io.open(HTML, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r'<script id="payload"[^>]*>(.*?)</script>', raw, re.S)
    if not m:
        raise SystemExit("找不到 <script id=\"payload\">")
    b64 = re.sub(r"\s+", "", m.group(1))
    blob = base64.b64decode(b64)
    if blob[:2] == b"\x1f\x8b":
        blob = gzip.decompress(blob)
    # 布局：[uint32 LE jlen][JSON jlen 字节][BIN 网格二进制]
    jlen = struct.unpack("<I", blob[:4])[0]
    js = blob[4:4 + jlen]
    binlen = len(blob) - 4 - jlen
    return json.loads(js.decode("utf-8")), len(raw), len(m.group(1)), binlen


D, html_len, b64_len, bin_len = load_data()
print("HTML %.2f MB · payload base64 %.2f MB · BIN %.2f MB"
      % (html_len / 1048576, b64_len / 1048576, bin_len / 1048576))
print("DATA 顶层类型=%s" % type(D).__name__)
if isinstance(D, dict):
    top = list(D.keys())
    print("顶层键=%s" % top)
    if DUMP:
        for k in top:
            v = D[k]
            print("  %-10s %s len=%s" % (k, type(v).__name__,
                  (len(v) if hasattr(v, "__len__") else "-")))

maps = D.get("maps") if isinstance(D, dict) else None
if not maps:
    raise SystemExit("DATA.maps 不存在")

print("\n=== DATA.maps 条目 %d ===" % len(maps))
k0 = next(iter(maps))
print("示例键 %r 字段 %s" % (k0, sorted(maps[k0].keys())))
if DUMP:
    s = dict(maps[k0])
    for f in list(s):
        v = s[f]
        if isinstance(v, (list, dict, str)) and hasattr(v, "__len__") and len(v) > 60:
            s[f] = "<%s len=%d>" % (type(v).__name__, len(v))
    print("示例值 %s" % json.dumps(s, ensure_ascii=False)[:1200])

# 名字字段
namefields = [f for f in ("m", "n", "nm", "name", "i", "f", "cn") if any(f in v for v in maps.values())]
print("疑似名字字段=%s" % namefields)


def nm_of(v):
    for f in ("m", "i", "nm", "name"):
        x = v.get(f)
        if isinstance(x, str) and x:
            return x
    return ""


# ---------------------------------------------------------------- 覆盖统计
def cnt(v):
    try:
        return int(v or 0)
    except Exception:
        return 0


def ent_count(v):
    """实体数 = 分类计数 c 的合计（c 是 {gid: n}）；老版本字段名是 es。"""
    c = v.get("c")
    if isinstance(c, dict) and c:
        try:
            return sum(int(x) for x in c.values())
        except Exception:
            return 0
    return cnt(v.get("es"))


def terr_ok_of(v):
    """有地形 = 有网格切片 wm 且长度 > 0。"""
    wm = v.get("wm")
    if isinstance(wm, list) and len(wm) >= 2:
        return cnt(wm[1]) > 0
    return cnt(v.get("wf")) > 0


ent_ok = [k for k, v in maps.items() if ent_count(v) > 0]
ent_no = [k for k, v in maps.items() if ent_count(v) <= 0]
terr_ok = [k for k, v in maps.items() if terr_ok_of(v)]
terr_no = [k for k, v in maps.items() if k not in terr_ok]
print("有实体 %d / 无实体 %d" % (len(ent_ok), len(ent_no)))
print("有地形 %d / 无地形 %d" % (len(terr_ok), len(terr_no)))
if ent_no:
    print("  无实体图：%s" % ", ".join(sorted(nm_of(maps[k]) or k for k in ent_no)[:20]))
if terr_no:
    print("  无地形图：%s" % ", ".join(sorted(nm_of(maps[k]) or k for k in terr_no)[:20]))

# ---------------------------------------------------------------- 对照地图库
mp = json.load(io.open(os.path.join(FDIR, "data", "maps.json"), encoding="utf-8"))
rw = json.load(io.open(os.path.join(FDIR, "data", "rewards.json"), encoding="utf-8"))
lib = sorted((set(mp) | set(rw)) - {""})
print("\n=== 地图库（maps+rewards） %d 张 ===" % len(lib))

pv_names = {}
for k, v in maps.items():
    n = nm_of(v)
    if n:
        pv_names[n.lower()] = k
print("预览页可反查名字 %d 条" % len(pv_names))

miss = [n for n in lib if n.lower() not in pv_names]
print("地图库中【预览页完全没有】= %d" % len(miss))
if miss:
    print("  " + ", ".join(miss[:60]))

# 有名字但没实体
miss_ent = []
for n in lib:
    k = pv_names.get(n.lower())
    if k and ent_count(maps[k]) <= 0:
        miss_ent.append((n, k))
print("地图库中【有图但 0 实体】= %d" % len(miss_ent))
for n, k in miss_ent[:60]:
    print("   %-42s pid=%s" % (n, k))

# 写清单
out = {
    "maps_total": len(maps),
    "lib_total": len(lib),
    "no_entity": sorted(miss_ent, key=lambda x: x[0]),
    "absent": miss,
}
with io.open(os.path.join(FDIR, "_pv_ent_audit.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print("\n清单已写 _pv_ent_audit.json")

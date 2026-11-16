# -*- coding: utf-8 -*-
"""地图库「实体预览」缺口报告。

比对三份数据：
  A) 地图库全量          data/maps.json ∪ data/rewards.json
  B) 预览 payload 已收录  preview3d.html 内嵌 payload 的 maps[*].m / .f
  C) 本地已抓产物         E:\\FYS-cache\\_ents_raw\\<pid>.json + _meshes_raw\\<pid>.bin.gz

输出 _pv_gap.json，并把「可立即补」的 name->pid 写进 _missing_ws_ready.json。

用法：python _pv_gap_report.py
"""
import base64
import gzip
import io
import json
import os
import re
import struct

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
FDIR = os.path.join(ROOT, "fys-reward")
CACHE = r"E:\FYS-cache"
ENTS = os.path.join(CACHE, "_ents_raw")
MESH = os.path.join(CACHE, "_meshes_raw")


def read_json(p, default=None):
    if not os.path.exists(p):
        return default
    return json.load(io.open(p, encoding="utf-8"))


def stems(d):
    if not os.path.isdir(d):
        return set()
    return set(f.split(".")[0] for f in os.listdir(d))


# ---------------------------------------------------------------- A 地图库
maps = read_json(os.path.join(FDIR, "data", "maps.json"), {})
rew = read_json(os.path.join(FDIR, "data", "rewards.json"), {})
loc = read_json(os.path.join(FDIR, "data", "maps_local.json"), {})
lib = sorted((set(maps) | set(rew)) - {""})

# ---------------------------------------------------------------- B payload
raw = io.open(os.path.join(FDIR, "preview3d.html"), encoding="utf-8", errors="replace").read()
m = re.search(r'<script id="payload"[^>]*>(.*?)</script>', raw, re.S)
blob = gzip.decompress(base64.b64decode(re.sub(r"\s+", "", m.group(1))))
jlen = struct.unpack("<I", blob[:4])[0]
D = json.loads(blob[4:4 + jlen].decode("utf-8"))
PV = D["maps"]
pv_names = set(v.get("m") for v in PV.values())
pv_pids = set(str(v.get("f")) for v in PV.values())

# ---------------------------------------------------------------- C 产物
ents = stems(ENTS)
mesh = stems(MESH)
ready = ents & mesh

# ---------------------------------------------------------------- pid -> name 映射
pid2names = {}


def add(pid, name):
    pid = str(pid)
    if pid and name:
        pid2names.setdefault(pid, set()).add(name)


wsmap = read_json(os.path.join(FDIR, "_ghcrawl", "_wsmap.json"), {})
for nm, pid in (wsmap.get("mapping") or {}).items():
    add(pid, nm)
for f in ("_missing_ws_all.json", "_missing_ws.json", "_missing_ws2.json"):
    for nm, pid in (read_json(os.path.join(FDIR, f), {}) or {}).items():
        add(pid, nm)
for x in (read_json(os.path.join(FDIR, "_ghcrawl", "_missing_ids.json"), []) or []):
    add(x.get("pid"), x.get("key", "").split("/")[-2] if x.get("key") else None)
for nm, v in (read_json(os.path.join(FDIR, "_ghcrawl", "_workshop_maps.json"), {}) or {}).items():
    add((v or {}).get("item"), nm)


def norm(n):
    return re.sub(r"_(p|cs2|cs2_l|z|t|b\d+|v\d+|\d+)$", "", n or "")


libnorm = {}
for n in lib:
    libnorm.setdefault(norm(n).lower(), []).append(n)


def match_lib(name):
    """把工坊里的基础名匹配到地图库里的正式名。"""
    if not name:
        return None
    if name in maps or name in rew:
        return name
    cand = libnorm.get(norm(name).lower())
    if cand:
        return cand[0]
    for n in lib:
        if n.lower().startswith(name.lower() + "_"):
            return n
    return None


# ---------------------------------------------------------------- 缺口
name2pid = {}


def pid_for(name):
    """地图库名 -> pid：先精确，再按 norm 反查。"""
    if name in name2pid:
        return name2pid[name]
    want = norm(name).lower()
    hit = None
    for pid, nms in pid2names.items():
        for c in nms:
            if norm(c).lower() == want:
                hit = pid
                break
        if hit:
            break
    name2pid[name] = hit
    return hit


# payload 里的名字也算一种映射（已经收录的不用管）
pv_nameset = set(pv_names)
pv_bynorm = {norm(n).lower(): n for n in pv_names}

absent = [n for n in lib if n not in pv_nameset and pv_bynorm.get(norm(n).lower()) not in pv_nameset]
print("地图库 %d 张 · 预览页 %d 张 · 缺口 %d 张" % (len(lib), len(PV), len(absent)))

todo, nodata, nomap = [], [], []
for n in absent:
    pid = pid_for(n)
    if not pid:
        nomap.append(n)
        continue
    if pid in ready:
        todo.append((n, pid))
    else:
        have = []
        if pid in ents:
            have.append("实体")
        if pid in mesh:
            have.append("网格")
        nodata.append((n, pid, have))

print("  可立即补（本地已有实体+网格）= %d" % len(todo))
print("  有产物但不全=%d / 完全无产物=%d / 找不到 pid=%d"
      % (len([x for x in nodata if x[2]]), len([x for x in nodata if not x[2]]), len(nomap)))

print("\n可立即补清单：")
for n, pid in todo:
    print("   %-42s %s" % (n, pid))

print("\n有部分产物（可补一半）：")
for n, pid, have in nodata:
    if have:
        print("   %-42s %s 只有%s" % (n, pid, "/".join(have)))

with io.open(os.path.join(FDIR, "_pv_gap.json"), "w", encoding="utf-8") as fh:
    json.dump({
        "lib": len(lib), "preview": len(PV), "absent": len(absent),
        "todo": todo, "partial": [[n, p, h] for n, p, h in nodata if h],
        "nodata": [[n, p] for n, p, h in nodata if not h], "nomap": nomap,
    }, fh, ensure_ascii=False, indent=1)

wsdir = read_json(os.path.join(FDIR, "_missing_ws_all.json"), {}) or {}
for n, pid in todo:
    wsdir[n] = pid
with io.open(os.path.join(FDIR, "_missing_ws_ready.json"), "w", encoding="utf-8") as fh:
    json.dump(wsdir, fh, ensure_ascii=False, indent=1, sort_keys=True)
print("\n已写 _pv_gap.json 与 _missing_ws_ready.json（%d 条）" % len(wsdir))

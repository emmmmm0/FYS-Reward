# -*- coding: utf-8 -*-
"""从 Steam 工坊页补抓封面（官方图床 resx.fyscs.cn 没有的那批）。

来源链：cover/_missing.json（_build_covers.py 落盘的缺失清单）
        ∩ _newmap_src.json（图名 → 工坊 ID，_newmap_auto.py 维护）
每个工坊条目取页面 previewImage（og:image 同源），居中裁 16:9 → 320x180 q78，
与 _build_covers.py 的产出规格完全一致。

用法：
  python _fetch_covers_steam.py            # 全量跑缺失清单
  python _fetch_covers_steam.py --probe    # 只测能抓到几张，不落盘
产出：cover/<地图名>.jpg；cover/_missing.json 更新为剩余缺失。
"""
import io
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _build_covers as BC            # 复用 shrink()/规格/目录

SRC = os.path.join(HERE, "_newmap_src.json")
UNRES = os.path.join(HERE, "_newmap_unresolvable.json")
PAGE = "https://steamcommunity.com/sharedfiles/filedetails/?id="
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
WORKERS = 6
RE_PREVIEW = re.compile(
    r'class="workshopItemPreviewImageMain"[^>]*?\ssrc="([^"]+)"')
RE_OG = re.compile(r'property="og:image"\s+content="([^"]+)"')
RE_GONE = re.compile(r'(error occurred|该物品已被移除|This item has been removed|'
                     r'非公开|Friends Only|-agecheck")', re.I)
# steamcommunity 对突发抓取直接 403（实测：6 连发后整段拉黑，冷却 ~90s 恢复）。
# 带上年龄 cookie + 单线程 + 2~3s 抖动间隔，连续 403 就整体退避。
COOKIE = "birthtime=568022401; lastagecheckage=1-January-1988; Steam_Language=schinese"


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(op, url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cookie": COOKIE})
    return op.open(req, timeout=timeout).read()


def pick_pid(name, src, unres):
    """图名 → 工坊 ID；查不到的记进 unres（下次直接跳过）。"""
    pid = src.get(name)
    if isinstance(pid, dict):
        pid = pid.get("pid") or pid.get("id")
    return str(pid) if pid else None


def one(name, pid, probe):
    """返回 (name, status, size)。status: ok / nopage / noimg / bad:<err>
    403 视为被风控：退避 45s 再试一次，仍 403 就返回 bad:403。"""
    op = opener()
    for attempt in (0, 1):
        try:
            html = get(op, PAGE + pid).decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            if e.code == 403 and attempt == 0:
                time.sleep(45)
                continue
            return name, "bad:403", 0
        except Exception as e:                                 # noqa: BLE001
            return name, "bad:" + type(e).__name__, 0
    if RE_GONE.search(html) and "previewImage" not in html:
        return name, "nopage", 0
    m = RE_PREVIEW.search(html) or RE_OG.search(html)
    if not m:
        return name, "noimg", 0
    img = m.group(1).replace("&amp;", "&").split("?imw=")[0]   # 去掉缩放参数取原图
    try:
        raw = get(op, img)
    except Exception as e:                                     # noqa: BLE001
        return name, "bad:" + type(e).__name__, 0
    if len(raw) < 2048:
        return name, "tiny", 0
    if probe:
        return name, "ok", len(raw)
    try:
        out = BC.shrink(raw)
    except Exception as e:                                     # noqa: BLE001
        return name, "bad:" + type(e).__name__, 0
    tmp = os.path.join(BC.OUT, name + ".jpg.part")
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, os.path.join(BC.OUT, name + ".jpg"))
    return name, "ok", len(out)


def main():
    probe = "--probe" in sys.argv
    missing = json.load(open(os.path.join(BC.OUT, "_missing.json"),
                             encoding="utf-8"))
    src = json.load(open(SRC, encoding="utf-8"))
    unres = set()
    if os.path.exists(UNRES):
        unres = set(json.load(open(UNRES, encoding="utf-8")) or [])
    todo = []
    for n in missing:
        if n in unres:
            continue
        pid = pick_pid(n, src, unres)
        if pid:
            todo.append((n, pid))
    print("缺失 %d 张，可从工坊补抓 %d 张（无工坊 ID 跳过 %d）"
          % (len(missing), len(todo), len(missing) - len(todo)))
    if not todo:
        return
    ok = fail = 0
    remain = list(missing)
    t0 = time.time()
    import random
    for i, (n, p) in enumerate(todo, 1):
        n2, st, sz = one(n, p, probe)
        if st == "ok":
            ok += 1
            if not probe and n2 in remain:
                remain.remove(n2)
        else:
            fail += 1
        if i % 20 == 0 or i == len(todo):
            print("  %d/%d  ok=%d fail=%d  %.0fs"
                  % (i, len(todo), ok, fail, time.time() - t0), flush=True)
            if not probe:      # 边跑边存：会话中断也能断点续跑
                json.dump(remain, open(os.path.join(BC.OUT, "_missing.json"), "w",
                                       encoding="utf-8"),
                          ensure_ascii=False, indent=1)
        if i < len(todo):
            time.sleep(1.8 + random.random() * 1.2)   # 2~3s 抖动，避开风控
    print("完成：成功 %d / 失败 %d，用时 %.0fs" % (ok, fail, time.time() - t0))
    if not probe:
        json.dump(remain, open(os.path.join(BC.OUT, "_missing.json"), "w",
                               encoding="utf-8"), ensure_ascii=False, indent=1)
        print("剩余缺失清单：cover/_missing.json（%d）" % len(remain))


if __name__ == "__main__":
    main()

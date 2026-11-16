# -*- coding: utf-8 -*-
"""给「地图库里有、实体预览里没有」的地图补齐实体 + 地形数据。

背景：实体预览的数据源是 fyscs/MapTracking-CS2（StarDance 服务器实体 dump），
只覆盖服务器上报过的 340 张图；地图库却有 698 张 ze。缺的 153 张（如 ze_devil_may_cry
鬼泣）官方源永远不会有，只能自建：
    工坊ID（来自 EXG 社区公开地图表 list.darkrp.cn）→ steamcmd 匿名下载 vpk
    → 从 world_physics.vmdl_c 提地形、从 entities/*.vents_c 提实体
产出与 _build_meshes.py 完全同格式，后面的打包/注入链路不用改：
    _meshes_raw/<pid>.bin.gz   原始网格（E 盘缓存）
    _ents_raw/<pid>.json       实体表

可断点续跑：已有产物直接跳过；每张下完立刻提取并截断临时 vpk 释放空间，
所以磁盘峰值只需要单张图的体积（大图约 1.5GB）。

用法：
    python _fetch_missing.py --limit 5          # 先试 5 张
    python _fetch_missing.py --only ze_devil_may_cry
    python _fetch_missing.py                    # 全部（按名字排序）
"""
import gzip
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_ghcrawl"))   # _build_meshes/_kv3/_meshio 在那
import _build_meshes as BM                       # noqa: E402
from _meshio import pack                          # noqa: E402
WS_JSON = os.environ.get("FYS_WS_JSON") or os.path.join(HERE, "_missing_ws.json")
LOG = os.path.join(HERE, "_fetch_missing.log")


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    only = args[args.index("--only") + 1] if "--only" in args else None

    ws = json.load(io.open(WS_JSON, encoding="utf-8"))
    items = sorted(ws.items())
    if only:
        items = [(k, v) for k, v in items if k == only]
        if not items:
            log("找不到 %s" % only)
            return 1
    if limit:
        items = items[:limit]

    log("待处理 %d 张；本地工坊包索引中…" % len(items))
    local = BM.workshop_vpk_map()
    log("本地可用包 %d 个（命中就直接用，不重下）" % len(local))

    t0 = time.time()
    ok = skip = fail = 0
    failed = []
    for n, (name, pid) in enumerate(items, 1):
        pid = str(pid)
        ep = os.path.join(BM.ENTS_DIR, pid + ".json")
        rp = os.path.join(BM.RAW_DIR, pid + ".bin.gz")
        if os.path.exists(ep) and os.path.exists(rp):
            skip += 1
            log("[%d/%d] SKIP  %-40s %s（已有）" % (n, len(items), name, pid))
            continue

        vpk = local.get(pid)
        tmpdir = None
        fetched = False
        if not vpk:
            log("[%d/%d] DL    %-40s %s" % (n, len(items), name, pid))
            vpk, tmpdir = BM.fetch_workshop_item(pid)
            fetched = True
            if not vpk:
                log("        DL-FAIL %s %s" % (name, pid))
                fail += 1
                failed.append((name, pid, "download"))
                continue

        try:
            info = {"vpk": vpk, "stem": vpk}
            if not os.path.exists(ep):
                e = BM.extract_ents_from_vpk(info, name)
                if e:
                    io.open(ep, "w", encoding="utf-8").write(
                        json.dumps(e, separators=(",", ":")))
            nb = 0
            if os.path.exists(ep):
                nb = len(json.load(io.open(ep, encoding="utf-8")))
            if not os.path.exists(rp):
                got = BM.extract_mesh_from_vpk(info, name)
                if got and got[1]:
                    io.open(rp, "wb").write(gzip.compress(pack(got[0], got[1]), 6))
            has_mesh = os.path.exists(rp)
            ok += 1
            log("[%d/%d] OK    %-40s 实体 %5d%s  用时 %.1f 分"
                % (n, len(items), name, nb,
                   "  网格 ✓" if has_mesh else "  网格 ✗", (time.time() - t0) / 60))
            if not has_mesh:
                failed.append((name, pid, "nomesh"))
        except Exception as ex:                                  # noqa: BLE001
            log("        ERR %s %s: %s" % (name, pid, ex))
            fail += 1
            failed.append((name, pid, "extract:%s" % ex))
        finally:
            if fetched and tmpdir and os.path.isdir(tmpdir):
                BM.cleanup_dir(tmpdir)          # 截断释放空间
                BM.forget_workshop_item(pid)    # 摘掉 acf，避免下次误判已装

    el = (time.time() - t0) / 60
    log("完成：成功 %d / 跳过 %d / 失败 %d，用时 %.1f 分钟" % (ok, skip, fail, el))
    if failed:
        log("失败清单：")
        for a, b, c in failed:
            log("   %-40s %s  %s" % (a, b, c))
        io.open(os.path.join(HERE, "_fetch_failed.json"), "w",
                encoding="utf-8").write(
            json.dumps([{"name": a, "pid": b, "why": c} for a, b, c in failed],
                       ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

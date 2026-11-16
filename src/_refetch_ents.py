# -*- coding: utf-8 -*-
"""重取「完整实体」——给补图产物补上属性（kv）与触发连接（cx）。

背景
----
`_fetch_missing.py` 首轮抓取用的 `extract_ents_from_vpk()` 只留了
`{cn, o, nm, uid, c, h}`，把 KV3 里的属性与 `m_connections` 丢了
（当时 `_kv3_entities()` 只看 keyValues3Data.values，连接在同级的 m_connections 里）。
结果：新补的图在预览页点开实体只能看到「该实体无附加属性 / 连接记录」，
而原有 548 张有 —— 体验不一致。

本脚本按 `keep_kv=True` 重跑一遍实体提取，覆盖 `_ents_raw/<工坊ID>.json`。
**不重新提取网格**（`_meshes_raw` 已有且正确），所以只做
「下载 → 提实体 → 清理」，比首轮省一半时间。

判据：`_ents_raw/<pid>.json` 里第一条实体已有 `kv` 或 `cx` 键 → 视为已完成。
注意「整图实体确实都没属性」的图会被反复重试；本脚本额外记录
`_refetch_done.json`（pid 列表）避免重复。

用法：
    python _refetch_ents.py                # 全部（跳过已完成的）
    python _refetch_ents.py --limit 5      # 只跑前 5 张（试跑）
    python _refetch_ents.py --only ze_mota # 只跑某一张
    python _refetch_ents.py --force        # 无视已完成标记
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_ghcrawl"))
import _build_meshes as BM                          # noqa: E402

WS_JSON = os.environ.get("FYS_WS_JSON") or os.path.join(HERE, "_missing_ws_all.json")
LOG = os.path.join(HERE, "_refetch_ents.log")
DONE = os.path.join(HERE, "_refetch_done.json")
os.environ["FYS_ENTS_FULL"] = "1"                   # 让提取器带上 kv/cx


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
    force = "--force" in args

    ws = json.load(io.open(WS_JSON, encoding="utf-8"))
    done = set(json.load(io.open(DONE, encoding="utf-8"))) \
        if os.path.exists(DONE) else set()

    items = sorted(ws.items())
    if only:
        items = [(k, v) for k, v in items if k == only]
        if not items:
            log("找不到 %s" % only)
            return 1

    todo = []
    for name, pid in items:
        pid = str(pid)
        ep = os.path.join(BM.ENTS_DIR, pid + ".json")
        if not os.path.exists(ep):
            continue                                # 首轮就没抓到，别在这浪费时间
        if not force and pid in done:
            continue
        try:
            ents = json.load(io.open(ep, encoding="utf-8"))
        except Exception as ex:                     # noqa: BLE001
            log("读取失败 %s: %s" % (pid, ex))
            continue
        if ents and any("kv" in e or "cx" in e for e in ents):
            if not force:
                continue
        todo.append((name, pid, ep))
    if limit:
        todo = todo[:limit]

    log("待重取 %d 张；本地工坊包索引中…" % len(todo))
    local = BM.workshop_vpk_map()
    log("本地可用包 %d 个（命中就直接用，不重下）" % len(local))

    t0 = time.time()
    ok = skip = fail = 0
    failed = []
    for n, (name, pid, ep) in enumerate(todo, 1):
        vpk = local.get(pid)
        tmpdir = None
        fetched = False
        if not vpk:
            log("[%d/%d] DL    %-40s %s" % (n, len(todo), name, pid))
            vpk, tmpdir = BM.fetch_workshop_item(pid)
            fetched = True
            if not vpk:
                log("        DL-FAIL %s %s" % (name, pid))
                fail += 1
                failed.append((name, pid, "download"))
                continue
        try:
            ents = BM.extract_ents_from_vpk({"vpk": vpk, "stem": vpk}, name, keep_kv=True)
            if not ents:
                fail += 1
                failed.append((name, pid, "empty"))
                log("        EMPTY  %s %s" % (name, pid))
                continue
            nk = sum(1 for e in ents if e.get("kv"))
            nc = sum(1 for e in ents if e.get("cx"))
            tmp = ep + ".tmp"
            io.open(tmp, "w", encoding="utf-8").write(
                json.dumps(ents, separators=(",", ":")))
            os.replace(tmp, ep)
            ok += 1
            done.add(pid)
            log("[%d/%d] OK    %-40s 实体 %5d  属性 %4d  连接 %3d  用时 %.1f 分"
                % (n, len(todo), name, len(ents), nk, nc, (time.time() - t0) / 60))
            if not nk and not nc:
                failed.append((name, pid, "no-attrs"))
        except Exception as ex:                                  # noqa: BLE001
            log("        ERR %s %s: %r" % (name, pid, ex))
            fail += 1
            failed.append((name, pid, "extract:%r" % (ex,)))
        finally:
            if fetched and tmpdir and os.path.isdir(tmpdir):
                BM.cleanup_dir(tmpdir)
                BM.forget_workshop_item(pid)

    io.open(DONE, "w", encoding="utf-8").write(
        json.dumps(sorted(done), ensure_ascii=False, indent=1))
    log("完成：成功 %d / 失败 %d / 用时 %.1f 分钟" % (ok, fail, (time.time() - t0) / 60))
    if failed:
        log("问题清单：")
        for a, b, c in failed:
            log("   %-40s %s  %s" % (a, b, c))
        io.open(os.path.join(HERE, "_refetch_failed.json"), "w",
                encoding="utf-8").write(
            json.dumps([{"name": a, "pid": b, "why": c} for a, b, c in failed],
                       ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

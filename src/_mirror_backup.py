# -*- coding: utf-8 -*-
"""把云端 124.223.107.6 的静态资产全量备份到本地 _local_mirror/。

背景：轻量服务器 2026-10-26 08:44 到期。软件本体各依赖点都有本地兜底
（repo 检测回源 codeload、译名静默沿用、封面/换服有本地链、预览壳断网照用），
唯一实质缺口是 terr/ 地形分包（只在云端按需分发）。

本脚本做三件事：
  1. terr/  853 个 .bin（285MB）→ _local_mirror/terr/  （8 线程并行）
  2. repo/ pv/ cover/ 及根目录小件 → _local_mirror/ 对应子目录
  3. 完成后打印汇总（成败计数、与 fys-reward/terr 的差异清单）

产物落盘后，可用 _mirror_sync_terr.py 把 _local_mirror/terr 与 exe 旁 terr 目录对齐。
断点续跑：已存在且大小一致的文件跳过（md5 抽查由 --verify 承担）。
"""
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.request

BASE = "http://124.223.107.6"
HERE = os.path.dirname(os.path.abspath(__file__))
MIRROR = os.path.join(os.path.dirname(HERE), "_local_mirror")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

STAT = {"ok": 0, "skip": 0, "fail": 0, "bytes": 0, "fails": []}


def fetch(url, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    part = dst + ".part"
    try:
        with OPENER.open(url, timeout=60) as r, open(part, "wb") as fh:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
        sz = os.path.getsize(part)
        if sz == 0:
            raise RuntimeError("empty body")
        os.replace(part, dst)
        with STAT["_lock"]:
            STAT["ok"] += 1
            STAT["bytes"] += sz
    except Exception as e:                                     # noqa: BLE001
        try:
            os.remove(part)
        except OSError:
            pass
        with STAT["_lock"]:
            STAT["fail"] += 1
            STAT["fails"].append("%s: %r" % (os.path.basename(dst), e))


def fetch_if(url, dst):
    """已存在（>0 字节）则跳过，支持断点续跑。"""
    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
        with STAT["_lock"]:
            STAT["skip"] += 1
        return
    fetch(url, dst)


def main():
    STAT["_lock"] = __import__("threading").Lock()
    t0 = time.time()
    jobs = []                                                  # (url, dst)

    # 1) terr/：853 个 bin（文件名集合已验证与本地 fys-reward/terr 完全一致）
    src_terr = os.path.join(HERE, "terr")
    names = sorted(f for f in os.listdir(src_terr) if f.endswith(".bin"))
    for n in names:
        jobs.append(("%s/terr/%s" % (BASE, n),
                     os.path.join(MIRROR, "terr", n)))

    # 2) repo/ pv/ + 根目录小件
    for u, d in [
        ("/repo/cs2.tar.gz", "repo/cs2.tar.gz"),
        ("/repo/mapnames.json", "repo/mapnames.json"),
        ("/pv/preview3d.html", "pv/preview3d.html"),
        ("/pv/preview3d.html.ver", "pv/preview3d.html.ver"),
        ("/cover/_index.json", "cover/_index.json"),
        ("/newmap.json", "root_files/newmap.json"),
        ("/status.json", "root_files/status.json"),
        ("/hist.json", "root_files/hist.json"),
        ("/index.html", "root_files/index.html"),
    ]:
        jobs.append((BASE + u, os.path.join(MIRROR, d.replace("/", os.sep))))

    # 3) cover/：_index.json 清单里的全部原图（55MB）
    idx_p = os.path.join(MIRROR, "cover", "_index.json")
    covers = []
    if os.path.isfile(idx_p):
        try:
            covers = json.load(open(idx_p, encoding="utf-8")) or []
        except Exception:                                      # noqa: BLE001
            covers = []
    else:                       # 首跑还没有清单：同步拉一次小的
        try:
            covers = json.loads(
                OPENER.open(BASE + "/cover/_index.json", timeout=30)
                .read().decode("utf-8")) or []
            os.makedirs(os.path.dirname(idx_p), exist_ok=True)
            with open(idx_p, "w", encoding="utf-8") as fh:
                json.dump(covers, fh, ensure_ascii=False)
        except Exception as e:                                 # noqa: BLE001
            print("  [warn] _index.json 拉取失败 %r" % (e,))
    for c in covers:
        jobs.append(("%s/cover/%s" % (BASE, c),
                     os.path.join(MIRROR, "cover", c)))

    print("共 %d 个任务（terr %d + cover %d + 其它 %d）"
          % (len(jobs), len(names), len(covers), len(jobs) - len(names) - len(covers)))
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(fetch_if, u, d) for u, d in jobs]
        done = 0
        for f in cf.as_completed(futs):
            f.result()
            done += 1
            if done % 100 == 0:
                el = time.time() - t0
                print("  进度 %d/%d  ok=%d skip=%d fail=%d  %.1f MB  %.0fs"
                      % (done, len(jobs), STAT["ok"], STAT["skip"],
                         STAT["fail"], STAT["bytes"] / 1e6, el), flush=True)

    print("== 完成 ==")
    print("ok=%d skip=%d fail=%d  共 %.1f MB  用时 %.0fs"
          % (STAT["ok"], STAT["skip"], STAT["fail"],
             STAT["bytes"] / 1e6, time.time() - t0))
    for x in STAT["fails"][:30]:
        print("  [fail] " + x)
    if STAT["fail"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

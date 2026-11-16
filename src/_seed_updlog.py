# -*- coding: utf-8 -*-
"""用「上一个提交」的官方归档给变更台账（upd_log.json）打种子。

为什么需要：v2.9 的「上游更新动态」靠**上次检测结果**做基准，而包内自带的数据
就是打包那一刻的最新版 —— 新装 / 刚升级的机器没有更早的基准，台账会是空的。
这里拿官方上一个提交的归档当基准，用程序**自己的比对代码**算出差异
（不是手写结论），既有历史可看，也顺带把整条比对链在真实数据上跑一遍。

用法：
    python _seed_updlog.py <旧归档.tar.gz> [新归档.tar.gz]   # 新归档省略则用当前 data/

产物：追加一条记录进 data/upd_log.json（走 history_append：去重 + 上限）。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_index as BI                                            # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    old_tar = sys.argv[1]
    new_tar = sys.argv[2] if len(sys.argv) > 2 else None

    print("=== 解析旧归档（基准）===")
    orw, omp, ompr, oinf, ocfg, oman = BI.extract(old_tar)
    if new_tar:
        print("=== 解析新归档 ===")
        nrw, nmp, nmpr, ninf, ncfg, nman = BI.extract(new_tar)
    else:
        print("=== 用当前 data\\ 当新侧 ===")
        nrw, nmp, ompr = BI.load_cache()
        ncfg = BI._read_old_cache().get("cfg")
        ninf, nman = BI._load_infect(), BI.manifest_load()
        if nman is None:
            print("!! 本地没有 repo_files.json，无法做文件级比对")
            return 1

    d = BI.diff_repo(orw, omp, oinf, nrw, nmp, ninf, ocfg, ncfg)
    fd = BI.diff_files(oman, nman)
    print("\n字段级 counts =", d.get("counts"))
    print("文件级差异 =", fd)
    for g, rows in (d.get("groups") or {}).items():
        for it in rows:
            print("  [%s] %s %s" % (g, it.get("map"),
                                    [(f.get("k"), f.get("old"), f.get("new"))
                                     for f in (it.get("fields") or [])]))

    e = BI.history_entry(fd, d.get("groups"), nman,
                         time.strftime("%Y-%m-%d %H:%M:%S"), "manual")
    if not e:
        print("\n没有实质改动，未写台账。")
        return 0
    print("\n台账条目 =", e)
    got = BI.history_append(e)
    print("写入结果 =", "已追加" if got else "重复（已存在）",
          "->", BI.UPDLOG_OUT)
    print("台账现有条数 =", len(BI.updlog_load()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

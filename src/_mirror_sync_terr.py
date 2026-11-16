# -*- coding: utf-8 -*-
"""把 _local_mirror/terr（云端备份，权威版）与 exe 旁 terr\\（本机缓存）对齐。

对齐方向：_local_mirror/terr → fys-reward/terr（覆盖 / 补缺）。
理由：云端那份是玩家分发版（客户端「没缓存才去云端拉」），服务器 10-26 到期后
不再有云端可拉，本机缓存必须与分发版一致才有完整的 3D 地形。

用法：
  python _mirror_sync_terr.py           # 只做干跑，打印差异
  python _mirror_sync_terr.py --apply   # 实际覆盖/补缺（差异文件先备份到 terr_pre_sync\）
"""
import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "_local_mirror", "terr")
DST = os.path.join(HERE, "terr")
BAK = os.path.join(os.path.dirname(HERE), "_local_mirror", "terr_pre_sync")


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    apply = "--apply" in sys.argv
    if not os.path.isdir(SRC):
        print("镜像目录不存在：%s（先跑 _mirror_backup.py）" % SRC)
        return 1
    src = {f: os.path.join(SRC, f) for f in os.listdir(SRC)
           if f.endswith(".bin")}
    dst = {f: os.path.join(DST, f) for f in os.listdir(DST)
           if f.endswith(".bin")}
    print("镜像 %d 个 / 本机缓存 %d 个" % (len(src), len(dst)))
    missing = sorted(set(src) - set(dst))
    diff = [f for f in src if f in dst]
    diff_files = []
    for f in diff:
        if md5(src[f]) != md5(dst[f]):
            diff_files.append(f)
    print("本机缺失 %d 个；内容不同 %d 个（共需同步 %d）"
          % (len(missing), len(diff_files), len(missing) + len(diff_files)))
    if not apply:
        for f in missing[:20]:
            print("  [缺] " + f)
        for f in diff_files[:20]:
            print("  [异] " + f)
        print("（干跑结束，加 --apply 执行同步）")
        return 0
    os.makedirs(BAK, exist_ok=True)
    n = 0
    for f in missing + diff_files:
        d = dst.get(f) or os.path.join(DST, f)
        if os.path.isfile(d):
            shutil.copy2(d, os.path.join(BAK, f))       # 覆盖前留底
        shutil.copy2(src[f], d)
        n += 1
        if n % 50 == 0:
            print("  已同步 %d…" % n, flush=True)
    print("== 同步完成：%d 个文件（原文件留底 %s）==" % (n, BAK))
    return 0


if __name__ == "__main__":
    sys.exit(main())

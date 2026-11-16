# -*- coding: utf-8 -*-
"""把待发布文件 PUT 到服务器 /root/（fys-put.py :8080）。

用法：
    python _put_release.py http://124.223.107.6:8080 tk7m3q9x <本地文件> [<本地文件> ...]

只上传、不部署；落点固定 /root/<basename>。上传后请自行在服务器核对 sha256。
"""
import hashlib
import os
import sys
import time
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "").rstrip("/")
TOK = sys.argv[2] if len(sys.argv) > 2 else ""
FILES = sys.argv[3:]
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

if not BASE or not TOK or not FILES:
    print("用法: python _put_release.py <base_url> <token> <file> [file ...]")
    sys.exit(2)

ok_all = True
for fp in FILES:
    name = os.path.basename(fp)
    raw = open(fp, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    url = "%s/put/%s?tok=%s" % (BASE, name, TOK)
    t0 = time.time()
    try:
        req = urllib.request.Request(url, data=raw, method="PUT")
        with OPENER.open(req, timeout=300) as r:
            code = r.status
    except Exception as e:                                      # noqa: BLE001
        print("  [!!] %-24s 上传失败 %r" % (name, e))
        ok_all = False
        continue
    dt = time.time() - t0
    print("  [%s] %-24s %d 字节 / %.1f 秒 (%.0f KB/s)" % (
        "OK" if code == 200 else "!!", name, len(raw), dt,
        len(raw) / 1024.0 / max(dt, 1e-6)))
    print("       sha256 = %s" % sha)

print("== %s ==" % ("上传完成" if ok_all else "存在失败项"))
sys.exit(0 if ok_all else 1)

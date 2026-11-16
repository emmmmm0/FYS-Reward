# -*- coding: utf-8 -*-
"""发布后线上产物验证（只读，不触发自替换）。

每次 `发布` 之后跑一次，确认客户端真的能拿到、能校验通过：
  ① version.json 可访问，ver 比当前 APP_VER 新（或等于）
  ② 线上 exe 下载实测：字节数 / sha256 与 version.json 完全一致
  ③ 模拟旧版客户端（APP_VER 临时降一级）能识别出「有更新」

用法：  python _verify_release.py            # 用当前 APP_VER 比对，不降级
        python _verify_release.py v2.2       # 模拟 v2.2 客户端（应识别到更新）
"""
import hashlib
import io
import json
import sys
import time
import urllib.request

sys.path.insert(0, ".")
import fys_reward_app as A  # noqa: E402

BASE = A.UPDATE_BASE
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ok_all = True


def say(ok, name, extra=""):
    global ok_all
    ok_all = ok_all and ok
    print("  [%s] %s%s" % ("OK" if ok else "!!", name, ("  " + extra) if extra else ""))


print("== 线上产物验证 ==")
try:
    raw = OPENER.open(BASE + "/version.json", timeout=10).read().decode("utf-8")
    meta = json.loads(raw)
except Exception as e:                                          # noqa: BLE001
    print("  [!!] version.json 无法获取：%r" % (e,))
    sys.exit(1)

say(True, "version.json 可访问", "ver=%s size=%s notes=%d条"
    % (meta.get("ver"), meta.get("size"), len(meta.get("notes") or [])))
say(bool(meta.get("sha256")), "带 sha256（缺了客户端一律拒绝更新）", str(meta.get("sha256"))[:16] + "…")

print("  下载 exe 校验中…")
t0 = time.time()
n = 0
h = hashlib.sha256()
try:
    with OPENER.open(BASE + "/FYS-Reward.exe", timeout=120) as r:
        while True:
            b = r.read(65536)
            if not b:
                break
            n += len(b)
            h.update(b)
except Exception as e:                                          # noqa: BLE001
    print("  [!!] exe 下载失败：%r" % (e,))
    sys.exit(1)

dt = time.time() - t0
say(n == meta.get("size"), "下载字节数一致", "%d 字节 / %.1f 秒（%.0f KB/s）" % (n, dt, n / 1024 / max(dt, 1e-6)))
say(h.hexdigest() == str(meta.get("sha256") or "").lower(), "sha256 一致", h.hexdigest()[:16] + "…")

# 模拟旧客户端：临时把 APP_VER 降一级，看本地判定逻辑会不会提示更新
fake = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
if fake:
    real, A.APP_VER = A.APP_VER, fake
    A._UPDATE_CACHE.update(t=0.0, info=None)
    info = A.update_check(force=True)
    A.APP_VER = real
    say(bool(info.get("has_update")), "模拟 %s 客户端会收到更新提示"
        % fake, "cur=%s → 线上 %s" % (info.get("cur"), info.get("ver")))
else:
    info = A.update_check(force=True)
    say(not info.get("has_update"), "当前版本 %s 与线上一致（不该弹更新）"
        % A.APP_VER, "线上 %s" % info.get("ver"))

print("== %s ==" % ("全部通过" if ok_all else "存在失败项"))
sys.exit(0 if ok_all else 1)

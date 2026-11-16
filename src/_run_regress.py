# -*- coding: utf-8 -*-
"""批量跑回归脚本并汇总（发版前自查用）。

用法:
  python _run_regress.py            # 跑默认清单
  python _run_regress.py a b c      # 只跑指定脚本（不带 .py）
  python _run_regress.py --all      # 跑清单里所有 _e2e_/_smoke_ 脚本
"""
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# ⑪ 测试归位（v2.15）：用例脚本搬进 tools/tests/，cwd 仍是项目根
#   （用例里按 cwd 相对路径读写 data/ 的逻辑不用动）
TESTS = os.path.join(HERE, "tools", "tests")
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

# 默认清单：快 + 不弹窗的优先（窗口类单独跑）
DEFAULT = [
    "_smoke_status", "_smoke_guard",
    "_e2e_vercmp", "_e2e_updpopup", "_e2e_upddetect", "_e2e_repocheck",
    "_e2e_away", "_e2e_relocate", "_e2e_zesrv", "_e2e_gsi", "_e2e_single",
    "_e2e_terr_cdn",
    "_e2e_mapnames", "_e2e_exgview", "_e2e_exgmerge", "_e2e_exglib",
    "_e2e_exg_local", "_e2e_clg", "_e2e_fav", "_e2e_layout",
    "_e2e_stgtheme", "_e2e_skincrop", "_e2e_cropui", "_e2e_ovpane",
    "_e2e_fxrm", "_e2e_v24_visual", "_e2e_preview667", "_e2e_repoupdate",
    "_e2e_pvgap",
    "_e2e_cover",
    # v2.14：服务器表滚轮必须滚表格自己（.srvWrap 自滚动容器），不能带整页走
    "_e2e_srvscroll",
    # v2.14：主页静态资源拆分（/static/app.css + app.js，ETag/304、长缓存）
    "_e2e_staticassets",
    # v2.14：「立即同步」分段进度（桩引擎，不联网）
    "_e2e_syncprog",
    # v2.14：新图封面同步后自动补齐（本机 HTTP 桩冒充官方图床，不碰真网）
    "_e2e_coversync",
    # v2.9 专项：地图参数变更检测 / 新接口与台账（两者都会写 data\，务必串行）
    "_probe_cfgdiff", "_probe_v29api",
    # v2.15：详情页「新旧参数对比」cfg 段（数值归一 / 假格式变化不报 / 整份 cfg
    # 新补删除要报）。纯临时目录。
    "_probe_mapdiffcfg",
    # v2.14：变更检测必须收敛（已转正的本地条目不能再报成「新增」，否则横幅永远
    # 要求「立即更新」）。纯临时目录、不联网。
    "_e2e_diffconverge",
    # v2.10：更新动态提醒条的显示/确认行为（CDP，自起自停，PrefsGuard 保护偏好）
    "_e2e_updln",
    # v2.15：界面偏好「读-改-写」并发（恢复默认外观一次连发三个 set 不能丢键）
    "_e2e_prefsrace",
    # v2.14 追加：启动先读本地缓存（服务器列表不再「先未收录、等几秒才有」）
    "_e2e_bootfast",
]

PAT = re.compile(r"^(?:PASS|FAIL|OK|NG|通过|失败|.*?(\d+)\s*/\s*(\d+).*)$")


def run(name, timeout=180):
    path = os.path.join(TESTS, name + ".py")
    if not os.path.exists(path):
        path = os.path.join(HERE, name + ".py")   # 兼容还没搬的散件
    if not os.path.exists(path):
        return name, None, "MISSING", ""
    t0 = time.time()
    try:
        p = subprocess.run([PY, path], cwd=HERE, capture_output=True,
                           timeout=timeout)
        out = (p.stdout or b"").decode("utf-8", "replace")
        err = (p.stderr or b"").decode("utf-8", "replace")
        rc = p.returncode
    except subprocess.TimeoutExpired:
        return name, None, "TIMEOUT(%ds)" % timeout, ""
    dt = time.time() - t0
    tail = "\n".join([ln for ln in (out + err).strip().splitlines()][-6:])
    return name, rc, "%.1fs" % dt, tail


def main():
    args = [a for a in sys.argv[1:]]
    if args == ["--all"]:
        names = sorted(f[:-3] for f in os.listdir(TESTS)
                       if (f.startswith("_e2e_") or f.startswith("_smoke_"))
                       and f.endswith(".py"))
    elif args:
        names = args
    else:
        names = DEFAULT
    bad = []
    for n in names:
        name, rc, extra, tail = run(n)
        flag = "OK " if rc == 0 else ("-- " if rc is None else "NG ")
        print("[%s] %-22s rc=%s %s" % (flag, name, rc, extra))
        if rc != 0:
            bad.append((name, rc, tail))
        sys.stdout.flush()
    print("\n==== 失败 %d / %d ====" % (len(bad), len(names)))
    for name, rc, tail in bad:
        print("\n--- %s (rc=%s) ---\n%s" % (name, rc, tail))


if __name__ == "__main__":
    main()

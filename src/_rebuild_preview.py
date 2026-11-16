# -*- coding: utf-8 -*-
"""预览壳重建一键链（补图专用）。

按顺序执行：
  1) _add_missing_maps.py --apply        新图条目追加进 _ghcrawl/preview_payload.b64
  2) _ghcrawl/_build_meshes.py --repack  用 payload 里的全量图过滤/打包地形 → _meshes/_manifest.json
  3) _ghcrawl/_inject3d.py               叠加 zq/sg/bb/bbm/wm/wf/wb + 写 <ROOT>/terr/<pid>.js
  4) _patch_preview_names.py --apply     删非 ze + 重算译名 + 注入运行时 JS → 根 HTML
  5) _sync_preview.py                    同步到 fys-reward/preview3d.html + terr/*.bin

用法：
    python _rebuild_preview.py              # 全跑
    python _rebuild_preview.py --from 3     # 从第 3 步开始（前几步已跑过时省时间）
    python _rebuild_preview.py --step 1     # 只跑第 1 步
"""
import os
import subprocess
import sys
import time

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
FDIR = os.path.join(ROOT, "fys-reward")
GH = os.path.join(FDIR, "_ghcrawl")
PY = sys.executable
PAYLOAD = os.path.join(GH, "preview_payload.b64")

STEPS = [
    ("追加新图条目", [PY, os.path.join(FDIR, "_add_missing_maps.py"), "--apply"], {}),
    ("过滤打包地形", [PY, os.path.join(GH, "_build_meshes.py"), "--repack"],
     {"FYS_TRACKING_B64": PAYLOAD}),
    ("叠加 3D 字段 + 地形分包", [PY, os.path.join(GH, "_inject3d.py")], {}),
    ("补译名 + 删非 ze", [PY, os.path.join(FDIR, "_patch_preview_names.py"), "--apply"], {}),
    ("同步进软件目录", [PY, os.path.join(FDIR, "_sync_preview.py")], {}),
]

args = sys.argv[1:]
only = int(args[args.index("--step") + 1]) if "--step" in args else None
start = int(args[args.index("--from") + 1]) if "--from" in args else 1

for i, (title, cmd, env) in enumerate(STEPS, 1):
    if only is not None and i != only:
        continue
    if only is None and i < start:
        print("[%d/%d] 跳过 %s" % (i, len(STEPS), title))
        continue
    e = dict(os.environ)
    e.update(env)
    print("\n" + "=" * 72)
    print("[%d/%d] %s → %s" % (i, len(STEPS), title, os.path.basename(cmd[1])))
    print("=" * 72, flush=True)
    t0 = time.time()
    rc = subprocess.call(cmd, cwd=FDIR, env=e)
    print("-- 用时 %.1fs，返回码 %d" % (time.time() - t0, rc), flush=True)
    if rc != 0:
        print("！第 %d 步失败，中止。" % i)
        sys.exit(rc)
print("\n全部完成。")

# -*- coding: utf-8 -*-
"""重打发行 zip（复用 build_dist.py 的排除规则）。

为什么单独一个脚本：`_mk_version.py` 必须在打包**之后**跑（它要读实际 exe 的
sha256），但 zip 是在生成 version.json **之前**压的 → 不重压的话，包内嵌的还是
旧 sha256。重跑整个 build_dist.py 又要再打包一遍（PyInstaller 产物可能微变，
sha256 又对不上），所以只重压 zip。

规则与 build_dist.make_zip 一致：排除 data\\（本机运行产物）、非 --full 的 terr\\、
运行期日志 startup*.log、非 --full-pv 的 preview3d.html。

用法：python fys-reward/_remake_zip.py
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG_NAME = "云朵小铺-FYS通关奖励看板"
PKG_DIR = os.path.join(ROOT, PKG_NAME)
ZIP_PATH = os.path.join(ROOT, PKG_NAME + ".zip")
PREVIEW_NAME = "preview3d.html"


def main():
    if not os.path.isdir(PKG_DIR):
        raise SystemExit("找不到包目录：%s" % PKG_DIR)
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    n = 0
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, fs in os.walk(PKG_DIR):
            dirs[:] = [d for d in dirs if d.lower() not in ("data", "terr")]
            for f in fs:
                if f.lower() in ("startup.log", "startup.old.log"):
                    continue
                if f.lower() == PREVIEW_NAME.lower():
                    continue
                fp = os.path.join(root, f)
                z.write(fp, os.path.join(PKG_NAME, os.path.relpath(fp, PKG_DIR)))
                n += 1
    print("已重打 zip：%s（%.1f MB，%d 个文件）"
          % (ZIP_PATH, os.path.getsize(ZIP_PATH) / 1048576.0, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())

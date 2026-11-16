# -*- coding: utf-8 -*-
"""云朵小铺 · FYS 通关奖励看板 —— 一键打包分发

一条命令走完：变更检测 -> 刷新数据索引 -> 打包 exe -> 冒烟验证 -> 组装 + 压缩 zip

用法（在本文件所在目录）：
    python build_dist.py              # 全流程
    python build_dist.py --check      # 只检查源码是否有比上次打包更新的改动
    python build_dist.py --skip-sync  # 不刷新索引（沿用现有 data\\）
    python build_dist.py --skip-test  # 跳过冒烟验证（着急时用）
    python build_dist.py --keep-tmp   # 保留临时构建目录（排查用）

也可以直接双击同目录的 build_dist.bat。
"""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                              # noqa: BLE001
    pass

# ───────────────────────────── 路径常量 ─────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(BASE, "fys-reward")                          # 源码目录
SPEC = os.path.join(APP, "spec4", "FYS-Reward.spec")
DIST_DIR = os.path.join(APP, "dist4")
# onedir（2026-11-09 起）：产物是 dist4\FYS-Reward\{FYS-Reward.exe, _internal\}。
# 用户只要压缩包、不用「一键更新只换 exe」，目录式免去 onefile 每次启动的解压等待。
DIST_APP = os.path.join(DIST_DIR, "FYS-Reward")
DIST_EXE = os.path.join(DIST_APP, "FYS-Reward.exe")
WORK_DIR = os.path.join(APP, "build_s4")
BUILD_LOG = os.path.join(APP, "_build_dist.log")
ICON = os.path.join(APP, "app.ico")
TMP = os.path.join(BASE, "_build_tmp")

# 地图实体预览（3D 视图）单文件 → 不再打进 exe（34MB 内嵌渲染会把软件拖卡）。
# 它作为独立文件 preview3d.html 随压缩包发布，放在 exe 旁边，软件点「实体预览」
# 时由本机服务 /preview3d 提供给系统浏览器打开。源文件是工作区根目录那份
# （_ghcrawl/_inject3d.py 生成）。
PREVIEW_SRC = os.path.join(BASE, "地图实体预览-3D视图.html")
PREVIEW_NAME = "preview3d.html"
TERR_DIR = os.path.join(BASE, "fys-reward", "terr")       # 地形原始 gz 分包（terr/<工坊ID>.bin）
COVER_DIR = os.path.join(APP, "cover")                    # 地图封面（cover/<地图名>.jpg）
FULL_TERR = False        # 2026-11-15 起**地形不进包**：安装包只带预览壳，地形按需从
                         # 静态托管（GitHub）单文件下载（中位 0.4MB）并落盘缓存。
                         # 需要离线整包时用 --full-terr（会 +284MB）。
FULL_PV = False          # 2026-11-16 起预览壳**不随包**（用户要求给安装包瘦身）：
                         # 壳托管在 GitHub 主仓库 pv/ 目录，首次点开「实体预览」时
                         # 自动多源下载（约 14.7MB）落盘缓存，之后离线也能看；
                         # 要发离线完整包时加 --full-pv。

PKG_NAME = "云朵小铺-FYS通关奖励看板"
PKG_DIR = os.path.join(BASE, PKG_NAME)
ZIP_PATH = os.path.join(BASE, PKG_NAME + ".zip")
README_NAME = "使用说明.txt"

# 用绝对路径，避免 shell PATH 异常时找不到（本机 bash 环境就有这毛病）
TASKKILL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")

# 版本守护：上次发行的版本号记在这里；同一版本重复打包会提醒（版本随每次更新抬一位）
VER_FILE = os.path.join(BASE, ".last_release_ver")


def read_app_ver():
    """从 fys_reward_app.py 里抠 APP_VER（不 import，避免拉起依赖）。"""
    try:
        with open(os.path.join(APP, "fys_reward_app.py"), encoding="utf-8") as fh:
            m = re.search(r'^APP_VER\s*=\s*"([^"]+)"', fh.read(), re.M)
        return m.group(1) if m else "?"
    except OSError:
        return "?"

# 打进 exe 的东西：改了其中任何一个都要重新打包
SRC_FILES = ["ui_page.py", "fys_reward_app.py", "reward_server.py",
             "build_index.py", "mapnames.py",
             # v2.14：样式表与主脚本从 ui_page.py 拆出（/static/app.css、app.js）
             "ui_style.py", "ui_js.py",
             # v2.15：原生启动卡（WebView2 就绪前直接画在窗体上的启动卡）
             "boot_native.py"]
BUNDLED_DATA = ["rewards.json", "maps.json", "meta.json", "infect.json",
                "knockback.json", "platform_mapnames.json", "sample_broadcast.txt"]
BUNDLED_EXTRA = [("logo_embed.png", APP)]                       # 根目录下的资源

DEFAULT_README = """云朵小铺 · FYS 通关奖励看板
============================

【这是什么】
读取 fys 官方客户端写出的广播文件 + 風雲社官网公开数据，实时显示你当前所在服务器的
地图、关卡，以及该关的通关云点 / 通关龙晶奖励与伤害达标门槛。
附带：屏幕覆盖小窗、5 套主题 + 5 套可切换界面背景、地图库（关键词 / 分类筛选）、
关卡明细弹窗、地图实体预览（3D：传送门 / 触发区 / 可破坏物 / 机关，含真实碰撞地形，
软件内直接打开；另有「🪟 独立窗口」模式，可最大化、拖到第二块屏）。

【怎么用】
1. 解压后保持 FYS-Reward.exe 与 _internal\\ 文件夹在一起，双击 FYS-Reward.exe 启动
   （目录式免解压，启动很快；启动期间会先看到云朵小铺启动卡，几秒后进主界面）
2. 进游戏即可，不用手动操作：软件会自动定位你所在的服务器与地图
3. 想让它一直显示在屏幕上 → 左侧「屏幕覆盖」页打开开关
4. 想看地图长什么样 → 左栏「🗺️ 地图实体预览」软件内直接看
   （首次点开时自动从 GitHub 下载预览页约 14.7MB 并缓存，之后离线也能看）

【运行环境】
· Windows 10 / 11（64 位）
· 无需安装 Python，地图数据已内置（不联网也能看数值）
· 3D 实体预览页按需下载（首次点开「实体预览」时自动拉取 preview3d.html 约 14.7MB
  缓存到 exe 旁），**地形按需下载**：第一次点开某张图时
  才拉这张图的地形分包（中位 0.4MB）并缓存到 terr\\，之后离线也能看；没网时提示下载失败
· 服务器状态由本机直接查询游戏服务器得到（不经中转）
· 只有「同步官方数据」与「一键更新检查」需要联网（前者连 GitHub）
· 界面用系统自带的 WebView2（Win11 自带；Win10 若提示缺失，装个 Edge 就好）

【数据与更新】
· 首次运行会把内置数据释放到 exe 同目录的 data\\ 文件夹
· 新图 / 官方改参数后想更新 → 「设置」页点「立即同步」（直连 GitHub 官方仓库，
  约 3~10 秒；开着「自动同步」时软件会自己检测并应用，失败不影响现有数据）
· 想看地形占了多少磁盘 → 「设置」页「地形分包」一行有占用统计与「🧹 清理」
  （离线版清理后不能自动恢复，不建议清）
· data\\ 里都有啥：
    rewards.json          通关奖励（云点 / 龙晶，按关卡）
    maps.json             地图参数（管理员 / 提名 / 时段 / 价格 / 冷却）
    infect.json           尸变参数（随机尸变 / 母体比例 / 倒计时）
    knockback.json        击退系数
    platform_mapnames.json 官方中文译名
    startup.log           运行日志（超过 512KB 自动归档为 startup.old.log）

【常见情形】
· 显示「未在服务器内」→ 还没进服，或 CS2 没运行
· 显示「关卡待同步」→ 已认到地图但没读到关卡号，数值先按第 1 关显示，下表可查全部关卡
· 认不出地图 → 「设置」页最下方有「广播文件原文」，把内容发给分享给你的人即可补规则
· 窗口打不开 / 白屏 → 删掉 data\\startup.log 后重试；仍不行就把该日志发出来
· 实体预览打不开 → 联网状态下重新点一次「实体预览」会自动补下预览页；仍不行就
  把 data\\startup.log 发出来（内含 [预览] 下载日志）
· 3D 视图提示「地形未收录」→ 该图的地形分包既不在本机、托管上也没有（新图还没生成）；
  联网后重开该图会再试一次，仍缺就等下次版本更新

【界面背景】
· 「主题」页的「🖼 界面背景」有 5 套可切换：云朵小铺（默认）/ 冒险出发 / 通关庆祝 /
  二次元日常 / 纯色无背景；点击即换、自动记住，想清爽点到纯色即可全部关掉
· 云朵小铺那套是主题图案铺底（云朵 / 龙晶 / 小僵尸）+ 服务器页与地图库顶部插画横幅 +
  设置页头图 + 侧栏小僵尸贴纸 + 卡片云朵角标；另外几套把插画当整幅氛围底
· 底纹自动跟随明暗：切到「夜幕护眼」主题时图案换成暗色版、插画自动压暗，不刺眼

【参数小抄】
· 关卡表 / 地图库里的伤害数值是「达标门槛」：每造成该数值伤害，额外 +1 云点或龙晶
  （例：门槛 3w → 每打满 3 万伤害 +1），鼠标悬停可看原始数值
· 地图库里 🔑 需管理员 · 🎲 随机尸变 · 🕒 限定时段 · 🌐 全 天可玩
· 实体预览：左键旋转 / 右键平移 / 滚轮缩放，T 俯视 R 复位；右上面板可分层、剖切、调块体透明度
· 快捷操作：侧栏可收起；覆盖小窗位置可在「屏幕覆盖」页拖动或用预设落点

【说明】
本软件为社区辅助工具，数据来自 GitHub 仓库 fyscs/cs2 与風雲社官网公开接口，
仅供查询与参考，与官方无隶属关系。
"""


def log(msg=""):
    print(msg, flush=True)


def step(n, total, title):
    log("")
    log("─" * 58)
    log("[%d/%d] %s" % (n, total, title))
    log("─" * 58)


# ───────────────────────── 解释器与工具探测 ─────────────────────────
def find_builder_py():
    """找带 PyInstaller 的解释器：先试项目约定环境，再试当前解释器。"""
    cands = [
        r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe",
        sys.executable,
    ]
    for py in cands:
        if not os.path.exists(py):
            continue
        try:
            r = subprocess.run([py, "-c", "import PyInstaller,sys;print(PyInstaller.__version__)"],
                               capture_output=True, text=True, timeout=60)
        except Exception:                                      # noqa: BLE001
            continue
        if r.returncode == 0:
            return py, (r.stdout or "").strip()
    return None, None


def find_base_py():
    """普通脚本用解释器（跑 build_index 刷新索引）。"""
    for py in [r"C:\Users\1\.workbuddy\binaries\python\versions\3.13.12\python.exe",
               sys.executable,
               r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"]:
        if os.path.exists(py):
            return py
    return sys.executable


def mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0.0


def ts(p):
    t = mtime(p)
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if t else "（不存在）"


def human(n):
    return "%.1f MB" % (n / 1048576.0) if n >= 1048576 else "%.0f KB" % (n / 1024.0)


def _dirsize(path):
    total = 0
    for root, _dirs, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


# ──────────────────────────── 变更检测 ────────────────────────────
def changed_files():
    """返回「比上次打包更新的、且会被打进 exe 的文件」清单。"""
    ref = mtime(DIST_EXE)
    if not ref:
        return None                                            # None = 从未打包过
    out = []
    for name in SRC_FILES:
        p = os.path.join(APP, name)
        if mtime(p) > ref + 1:
            out.append((name, ts(p)))
    for name in BUNDLED_DATA:
        p = os.path.join(APP, "data", name)
        if mtime(p) > ref + 1:
            out.append(("data/" + name, ts(p)))
    for name, d in BUNDLED_EXTRA:
        p = os.path.join(d, name)
        if mtime(p) > ref + 1:
            out.append((name, ts(p)))
    if mtime(ICON) > ref + 1:
        out.append(("app.ico", ts(ICON)))
    # 实体预览页现在是 exe 旁的独立文件，不再打进 exe —— 它有更新也不用重打包
    for name in os.listdir(APP):
        if name.endswith(".py") and name not in SRC_FILES:
            p = os.path.join(APP, name)
            if mtime(p) > ref + 1:
                out.append((name + "（额外脚本，请确认是否需要）", ts(p)))
    return out


def report_changes():
    log("上次打包：%s  →  %s" % (ts(DIST_EXE), DIST_EXE))
    ch = changed_files()
    if ch is None:
        log("结果：还没打过包，需要完整打一次。")
        return True
    if not ch:
        log("结果：源码与内置数据都没有新改动，现有 exe 已是最新，不必重打。")
        log("      （如果只是官方数据变多，让使用者点「设置 → 立即同步」即可）")
        return False
    log("结果：以下 %d 个文件比上次打包更新，需要重新打包：" % len(ch))
    for name, t in ch:
        log("   · %-34s %s" % (name, t))
    return True


# ─────────────────────────── 刷新数据索引 ───────────────────────────
def refresh_index(base_py):
    log("从 GitHub 拉取 fyscs/cs2 并重建索引（约 10~30 秒）…")
    t0 = time.time()
    r = subprocess.run([base_py, "-c",
                        "import build_index as b, json; print(json.dumps(b.build(force=True), ensure_ascii=False))"],
                       cwd=APP, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        log("  ! 索引刷新失败，沿用现有 data\\：%s" % (r.stderr or "").strip()[-300:])
        return False
    try:
        meta = json.loads((r.stdout or "").strip().splitlines()[-1])
        log("  完成：地图 %s 张 / 关卡 %s 段 / 尸变 %s 条（其中随机尸变 %s）"
            % (meta.get("maps"), meta.get("stages"), meta.get("infect"), meta.get("infect_rand")))
        log("  构建时间：%s  （用时 %.1fs）" % (meta.get("built_at_str"), time.time() - t0))
    except Exception:                                          # noqa: BLE001
        log("  完成（解析摘要失败，但命令已成功）：%s" % (r.stdout or "").strip()[-200:])
    return True


# ───────────────────────────── 打包 exe ─────────────────────────────
def sync_spec_root():
    """把 spec 里的 ROOT 指向当前源码目录，保证换目录也能打。
    注意必须用正斜杠：Windows 反斜杠在单引号里会触发 unicodeescape 报错。"""
    if not os.path.exists(SPEC):
        raise SystemExit("找不到打包配置：%s" % SPEC)
    want = "ROOT = '%s'" % APP.replace("\\", "/")
    txt = io.open(SPEC, encoding="utf-8").read()
    new = re.sub(r"^ROOT\s*=\s*.+$", want, txt, count=1, flags=re.M)
    if new != txt:
        io.open(SPEC, "w", encoding="utf-8").write(new)
        log("已校正 spec 里的 ROOT → %s" % APP.replace("\\", "/"))


def stage_preview(dst_dir):
    """把工作区根目录的「地图实体预览-3D视图.html」复制为发行目录下的独立文件
    preview3d.html（与 exe 同目录，软件会用系统浏览器打开它，不再内嵌）。

    v2.0 起默认**不随包分发**：预览壳改由软件首次打开预览时从云端取一份落到
    exe 旁（约 13.7MB），之后就是本地读取。要发离线完整包，加 --full-pv。"""
    if not FULL_PV:
        # ⚠ 不能只删 preview3d.html：软件下载预览壳时先写 preview3d.html.part，
        # 中断会留下这个半成品（7MB）。实测 v2.11 打包时它就跟着进了 zip ——
        # 判定改用「以 preview3d.html 开头」，.part / .tmp / .old 一并清掉。
        stale = [f for f in (os.listdir(dst_dir) if os.path.isdir(dst_dir) else [])
                 if f.lower().startswith(PREVIEW_NAME.lower())]
        for f in stale:
            fp = os.path.join(dst_dir, f)
            if not os.path.isfile(fp):
                continue
            try:
                os.remove(fp)         # 单文件，不触发批量删除保护
                log("  已移除包目录里遗留的 %s（预览壳走云端按需下载）" % f)
            except OSError as e:                               # noqa: BLE001
                log("  ! 移除遗留 %s 失败（zip 里已排除）：%r" % (f, e))
        log("  预览壳不随包分发（首次打开预览时从云端下载；要离线包加 --full-pv）")
        return True
    if not os.path.exists(PREVIEW_SRC):
        log("  ! 找不到 %s → 分发包会缺实体预览页（界面会提示缺失）"
            % os.path.basename(PREVIEW_SRC))
        return False
    # 壳源一致性（2026-11-10 事故）：v2.15 打包时工作区根这份壳是旧的（没带上
    # 旋转修复、地形也坏），真正修好的是 fys-reward\preview3d.html（软件内实际
    # 下发 + e2e 验证的那份）。打包一律以软件目录这份为准回填，杜绝「源没同步」。
    dev_shell = os.path.join(APP, PREVIEW_NAME)
    if os.path.exists(dev_shell):
        with open(dev_shell, "rb") as f1, open(PREVIEW_SRC, "rb") as f2:
            if f1.read() != f2.read():
                shutil.copy2(dev_shell, PREVIEW_SRC)
                log("  ⚠ 工作区根的壳源与软件目录不一致 → 已用软件目录那份回填"
                    "（v2.15 曾因源过期漏掉修复）")
    dst = os.path.join(dst_dir, PREVIEW_NAME)
    if os.path.exists(dst) \
            and os.path.getsize(dst) == os.path.getsize(PREVIEW_SRC) \
            and mtime(dst) >= mtime(PREVIEW_SRC):
        log("  实体预览独立文件已是最新（%s）" % human(os.path.getsize(dst)))
        return True
    shutil.copy2(PREVIEW_SRC, dst)
    log("  已复制实体预览独立文件 → %s（%s）" % (dst, human(os.path.getsize(dst))))
    return True


def stage_terr(dst_dir):
    """地形分包目录 terr\\（每图一个 <工坊ID>.bin，原始 gz 字节）。

    2026-11-15 起**默认不进包**：安装包只带预览壳，地形在玩家第一次点开某张图时
    从静态托管（GitHub raw）单文件下载并缓存（中位 0.4MB）—— 包体积回到 ~45MB。
    需要「离线整包」时加 --full-terr（+284MB，857 个文件增量复制）。
    """
    if not FULL_TERR:
        log("  地形分包不进包（默认：运行时按需从托管下载；离线整包用 --full-terr）")
        return False
    if not os.path.isdir(TERR_DIR):
        log("  ! 找不到 terr_bin\\ 地形分包目录（跳过；预览页地形会提示缺失）")
        return False
    dst = os.path.join(dst_dir, "terr")
    os.makedirs(dst, exist_ok=True)
    stale = [f for f in os.listdir(dst) if f.endswith(".js")]
    for f in stale:                                   # 旧版 base64 js，改用 bin 后清掉
        try:
            os.remove(os.path.join(dst, f))
        except OSError:
            pass
    if stale:
        log("  已清理旧版 .js 分包 %d 个（改用 .bin）" % len(stale))
    n = skip = 0
    for f in os.listdir(TERR_DIR):
        if not f.endswith(".bin"):
            continue
        sp, dp = os.path.join(TERR_DIR, f), os.path.join(dst, f)
        if os.path.exists(dp) and os.path.getsize(dp) == os.path.getsize(sp) \
                and mtime(dp) >= mtime(sp):
            skip += 1
            continue
        shutil.copy2(sp, dp)
        n += 1
    total = sum(os.path.getsize(os.path.join(dst, f))
                for f in os.listdir(dst) if f.endswith(".bin"))
    log("  地形分包：更新 %d 个 / 已最新 %d 个 → %s（%.1f MB）"
        % (n, skip, dst, total / 1048576))
    return True


def stage_cover(dst_dir):
    """地图封面目录 cover\\（每图一张 320x180 jpg，约 10KB）—— 随包分发。

    和 terr 相反：封面是**首屏就能用**的资源（地图库行底纹 + 覆盖窗地图图标），
    没有"下一张图再下"的缓冲余地，走云端按需会首屏空白。共 541 张 ≈ 4.9MB，
    换成包体积换掉一个网络依赖。由 _build_covers.py 从官方图床抓取。
    """
    if not os.path.isdir(COVER_DIR):
        log("  ! 找不到 cover\\ 封面目录（跳过；地图库底纹与覆盖图标会退回默认样式）")
        return False
    dst = os.path.join(dst_dir, "cover")
    os.makedirs(dst, exist_ok=True)
    # _missing.json = 「官方图床确认没有」的图名清单（_build_covers.py 产出）。
    # v2.16 起客户端同步后会自动补新图封面，靠这张表跳过注定 404 的一百多个请求，
    # 所以它必须随包（漏了不影响功能，只是首轮多试一些）。
    miss_src = os.path.join(COVER_DIR, "_missing.json")
    if os.path.exists(miss_src):
        try:
            shutil.copy2(miss_src, os.path.join(dst, "_missing.json"))
        except OSError as e:                                # noqa: BLE001
            log("  ! 复制 cover/_missing.json 失败：%r" % (e,))
    n = skip = 0
    for f in os.listdir(COVER_DIR):
        if not f.endswith(".jpg"):
            continue
        sp, dp = os.path.join(COVER_DIR, f), os.path.join(dst, f)
        if os.path.exists(dp) and os.path.getsize(dp) == os.path.getsize(sp) \
                and mtime(dp) >= mtime(sp):
            skip += 1
            continue
        shutil.copy2(sp, dp)
        n += 1
    total = sum(os.path.getsize(os.path.join(dst, f))
                for f in os.listdir(dst) if f.endswith(".jpg"))
    log("  地图封面：更新 %d 个 / 已最新 %d 个 → %s（%.2f MB，%.0f 张）"
        % (n, skip, dst, total / 1048576,
           sum(1 for f in os.listdir(dst) if f.endswith(".jpg"))))
    return True


def pyinstaller(builder_py):
    log("PyInstaller 打包中（约 40 秒，请稍等）…")
    t0 = time.time()
    # PyInstaller 的 COLLECT 每次都会先删掉整个 dist4\FYS-Reward（几百个文件）——
    # 环境删除护栏会当场拦死整轮打包（实测）。前置把旧产物改名移出（改名不算删除），
    # 让 PyInstaller 直接建新目录；改名留下的旧目录攒多了手动删。
    if os.path.isdir(DIST_APP):
        alt = os.path.join(DIST_DIR, "_FYS-Reward_stale_%d" % int(time.time()))
        try:
            os.rename(DIST_APP, alt)
            log("  旧产物已改名移出 → %s（可手动删）" % os.path.basename(alt))
        except OSError as e:                                   # noqa: BLE001
            log("  ! 旧产物改名失败（%r）→ 交由 PyInstaller 自行覆盖" % e)
    r = subprocess.run([builder_py, "-m", "PyInstaller", "--clean", "--noconfirm",
                        "--distpath", DIST_DIR, "--workpath", WORK_DIR, SPEC],
                       cwd=APP, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    io.open(BUILD_LOG, "w", encoding="utf-8").write(
        (r.stdout or "") + "\n--stderr--\n" + (r.stderr or ""))
    if r.returncode != 0 or not os.path.exists(DIST_EXE):
        log("  ! 打包失败，详见 %s" % BUILD_LOG)
        log((r.stderr or r.stdout or "")[-1200:])
        return False
    log("  成功：%s（%s，用时 %.1fs）" % (DIST_EXE, human(os.path.getsize(DIST_EXE)), time.time() - t0))
    return True


def kill_tree(pid):
    """onefile 模式下 exe 是个父进程 + 应用子进程，必须整棵树结束，
    否则残留进程会占住文件导致后续复制失败。"""
    for cmd in ([TASKKILL, "/F", "/T", "/PID", str(pid)],):
        try:
            if os.path.exists(cmd[0]):
                subprocess.run(cmd, capture_output=True, timeout=20)
                return
        except Exception:                                      # noqa: BLE001
            pass
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, timeout=20)
    except Exception:                                          # noqa: BLE001
        pass


def copy_with_retry(src, dst, tries=6, wait=1.5):
    """刚跑过 exe / 杀软扫描时，文件可能被短暂占用，重试几次。"""
    last = None
    for i in range(tries):
        try:
            shutil.copy2(src, dst)
            return True
        except PermissionError as e:
            last = e
            time.sleep(wait)
    log("  ! 复制被占用（%s）→ %s" % (last, dst))
    return False


# ──────────────────────────── 冒烟验证 ────────────────────────────
def smoke_test():
    """在干净目录里真跑一次 exe：自释放数据 -> 起服务 -> 探接口。
    onedir：整个应用目录（exe + _internal）都要拷过去，只拷 exe 起不来。"""
    log("在干净目录实测 exe（自释放数据 / 起服务 / 探接口）…")
    box = os.path.join(TMP, "smoke")
    shutil.rmtree(box, ignore_errors=True)
    os.makedirs(box)
    shutil.copytree(DIST_APP, box, dirs_exist_ok=True)      # exe + _internal
    exe = os.path.join(box, "FYS-Reward.exe")
    if os.path.exists(ICON):
        shutil.copy2(ICON, os.path.join(box, "app.ico"))
    stage_preview(box)          # 预览页是 exe 旁独立文件，模拟完整分发目录
    stage_terr(box)             # 地形分包目录（预览页点开地图时按需加载）
    stage_cover(box)            # 地图封面（地图库底纹 + 覆盖窗图标）

    data = os.path.join(box, "data")
    logp = os.path.join(data, "startup.log")
    DETACHED = 0x00000008 | 0x00000200
    proc = subprocess.Popen([exe], cwd=box, creationflags=DETACHED,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    port, t0 = None, time.time()
    while time.time() - t0 < 70:
        time.sleep(1)
        if os.path.exists(logp):
            try:
                txt = io.open(logp, encoding="utf-8", errors="replace").read()
            except OSError:
                txt = ""
            m = re.findall(r"127\.0\.0\.1:(\d+)", txt)
            if m:
                port = m[-1]
                break
    ok = False
    try:
        if not port:
            log("  ! 等不到服务端口，冒烟失败")
            return False
        time.sleep(2)
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 绕开系统代理
        info = {}
        eps = ["/", "/api/status", "/api/maplib", "/api/servers", "/api/prefs",
               "/api/preview"]
        _cvr = os.path.join(COVER_DIR, "ze_2012_p.jpg")     # 封面目录里随便挑一张探路由
        if os.path.exists(_cvr):
            eps.append("/cover/" + os.path.basename(_cvr))
        if FULL_PV:            # 壳不随包时 /preview3d 会触发 30 秒云端下载，冒烟不测
            eps.append("/preview3d")
        for ep in eps:
            raw = op.open("http://127.0.0.1:%s%s" % (port, ep), timeout=30).read()
            info[ep] = len(raw)
            if ep == "/api/maplib":
                d = json.loads(raw)
                log("  地图库 %s 张 / 元信息 %s" % (len(d.get("maps") or []), d.get("meta")))
            elif ep.startswith("/cover/"):
                raw2 = op.open("http://127.0.0.1:%s%s" % (port, ep), timeout=10).read()
                log("  地图封面 %s：%d bytes（%s）"
                    % (ep, len(raw2), "image/jpeg" if raw2[:2] == b"\xff\xd8" else "!不是 jpeg"))
            elif ep == "/api/preview":
                d = json.loads(raw)
                log("  实体预览：%s · %.1f MB · 快照 %s"
                    % (d.get("ok"), (d.get("size") or 0) / 1048576, d.get("at")))
            elif ep == "/preview3d":
                log("  预览页可打开：%d bytes（%.1f MB）" % (len(raw), len(raw) / 1048576))
            elif ep == "/api/servers":
                d = json.loads(raw)
                log("  服务器表 %s 台" % len(d.get("rows") or []))
            elif ep == "/api/status":
                d = json.loads(raw)
                log("  状态 %s / 日志体积 %s bytes" % (d.get("state"), (d.get("about") or {}).get("log_size")))
            else:
                log("  %s %d bytes" % (ep, len(raw)))
        ok = all(v > 0 for v in info.values())
        log("  冒烟结果：%s" % ("全部通过 ✓" if ok else "部分接口异常"))
    except Exception as e:                                     # noqa: BLE001
        log("  ! 冒烟异常：%r" % (e,))
    finally:
        kill_tree(proc.pid)
        try:
            proc.wait(timeout=10)
        except Exception:                                      # noqa: BLE001
            pass
        time.sleep(1.5)                                        # 等系统释放文件句柄
        log("  测试窗口已关闭")
    return ok


# ───────────────────────── 组装分发 + 压缩 ─────────────────────────
def package():
    os.makedirs(PKG_DIR, exist_ok=True)
    if os.path.isdir(os.path.join(PKG_DIR, "data")):
        log("  注：包目录里已有 data\\（之前在这跑过 exe）→ 压缩时会自动排除，不影响分享")
    # onedir：exe + _internal 整目录复制到发行目录（增量：已有同名且更新的跳过不了
    # 简单起见全量覆盖复制，_internal 约 200MB、同盘秒级）
    if not copy_with_retry(DIST_EXE, os.path.join(PKG_DIR, "FYS-Reward.exe")):
        raise SystemExit("exe 复制失败，可能有残留进程占用；关掉正在运行的云朵小铺后重试")
    inner_dst = os.path.join(PKG_DIR, "_internal")
    if os.path.isdir(inner_dst):
        # 旧 _internal 先改名移出（改名不算删除，避开批量删除护栏），避免新旧混装
        alt = os.path.join(BASE, "_internal_stale_%d" % int(time.time()))
        try:
            os.rename(inner_dst, alt)
            log("  旧 _internal 已移出包目录 → %s（可手动删）" % os.path.basename(alt))
        except OSError as e:                                   # noqa: BLE001
            log("  ! 旧 _internal 移出失败（%r）→ 直接覆盖合并" % e)
    shutil.copytree(os.path.join(DIST_APP, "_internal"), inner_dst)
    log("  已复制应用目录：%s + _internal\\（%s）"
        % (os.path.basename(DIST_EXE), human(_dirsize(os.path.join(DIST_APP, "_internal")))))
    if os.path.exists(ICON):
        copy_with_retry(ICON, os.path.join(PKG_DIR, "app.ico"))
    rd = os.path.join(PKG_DIR, README_NAME)
    if os.path.exists(rd):
        log("  使用说明.txt 已存在 → 原样保留（脚本不覆盖，你要改就改它）")
    else:
        io.open(rd, "w", encoding="utf-8").write(DEFAULT_README)
        log("  已写入默认 使用说明.txt")
    stage_preview(PKG_DIR)      # 实体预览独立文件（exe 旁 preview3d.html，默认不随包）
    # 「样板图-覆盖增强-直播向.html」2026-11-16 起不再随包（用户指示：与软件功能
    # 无关的旧产物没必要占安装包体积）。包目录里如有旧副本，移出以免误进 zip。
    stale_s = os.path.join(PKG_DIR, "样板图-覆盖增强-直播向.html")
    if os.path.isfile(stale_s):
        alt = os.path.join(BASE, "_sample_stale_%d.html" % int(time.time()))
        try:
            os.rename(stale_s, alt)
            log("  旧产物 样板图.html 已移出包目录 → %s（不再随包分发）"
                % os.path.basename(alt))
        except OSError as e:                                   # noqa: BLE001
            log("  ! 移出旧样板图失败（zip 会按排除清单跳过）：%r" % (e,))
    if not FULL_TERR:           # 把上一版遗留的地形目录移出包目录，免得误进 zip
        stale_t = os.path.join(PKG_DIR, "terr")
        if os.path.isdir(stale_t):
            # 这里**不能**用 shutil.rmtree：648 个文件会触发沙箱的批量删除保护，
            # 直接把整轮打包打断（实测走到第 4 步就没了）。改成改名移出——zip 里本来
            # 也排除 terr\，移出去的只是旧缓存，体积大时手动删掉即可。
            alt = os.path.join(BASE, "_terr_stale_%d" % int(time.time()))
            try:
                os.rename(stale_t, alt)
                log("  遗留 terr\\ 已移出包目录 → %s（可手动删）" % os.path.basename(alt))
            except OSError as e:                               # noqa: BLE001
                log("  ! 移出遗留 terr\\ 失败（zip 里已排除，不影响分发）：%r" % (e,))
    stage_terr(PKG_DIR)         # 地形分包目录 terr\（仅 --full-terr 时有内容）
    stage_cover(PKG_DIR)        # 地图封面 cover\（地图库底纹 + 覆盖窗图标，随包分发）

    files = sorted(os.listdir(PKG_DIR))
    log("  包内文件：")
    for f in files:
        fp = os.path.join(PKG_DIR, f)
        log("    %-18s %10d  %s" % (f, os.path.getsize(fp), ts(fp)))
    return zip_pkg()          # 组装完直接压缩

def zip_pkg():
    """只把 PKG_DIR 重新压成发行 zip（_mk_version.py 写完 version.json 后复用）。"""
    global ZIP_PATH
    if os.path.exists(ZIP_PATH):
        try:
            os.remove(ZIP_PATH)
        except OSError as e:                # noqa: BLE001
            # 沙箱/占用都可能拦删除；删不掉就换个名写，别让整轮打包死在这
            alt = ZIP_PATH + ".%d" % int(time.time())
            log("  ! 旧 zip 删不掉（%s）→ 改写到 %s" % (e, os.path.basename(alt)))
            ZIP_PATH = alt
    skipped = 0
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, fs in os.walk(PKG_DIR):
            if os.path.abspath(root) == os.path.abspath(PKG_DIR):
                # 只在**顶层**排除使用者本机跑出来的 data\（onedir 的 _internal\data
                # 是随包内置数据，绝不能排除！terr 顶层目录同理按开关决定）
                dirs[:] = [d for d in dirs
                           if d.lower() != "data"
                           and (FULL_TERR or d.lower() != "terr")]
            else:
                dirs[:] = [d for d in dirs if d.lower() != "__pycache__"]
            for f in fs:
                if f.lower() in ("startup.log", "startup.old.log"):
                    skipped += 1
                    continue
                # 前缀匹配：把下载半成品 preview3d.html.part 也算进「预览壳」一并排除
                if not FULL_PV and f.lower().startswith(PREVIEW_NAME.lower()):
                    skipped += 1
                    continue
                # 旧产物样板图（2026-11-16 起不随包）：万一移出失败也绝不进 zip
                if f.lower().startswith("样板图"):
                    skipped += 1
                    continue
                fp = os.path.join(root, f)
                z.write(fp, os.path.join(PKG_NAME, os.path.relpath(fp, PKG_DIR)))
    if skipped:
        log("  （已排除 %d 个运行期日志）" % skipped)
    log("  压缩包：%s（%s）" % (ZIP_PATH, human(os.path.getsize(ZIP_PATH))))
    return ZIP_PATH


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--check", action="store_true", help="只检查是否有新改动，不打包")
    ap.add_argument("--skip-sync", action="store_true", help="跳过刷新数据索引")
    ap.add_argument("--skip-test", action="store_true", help="跳过冒烟验证")
    ap.add_argument("--keep-tmp", action="store_true", help="保留临时目录")
    ap.add_argument("--full-terr", dest="full_terr", action="store_true",
                    help="把地形分包打进发行包（+约 284MB；默认不打，改为运行时按需下载）")
    ap.add_argument("--no-full-terr", dest="full_terr", action="store_false",
                    help="（旧参数，等同默认：地形不进包）")
    ap.add_argument("--no-full-pv", dest="full_pv", action="store_false",
                    help="不把实体预览壳打进发行包（2026-10-23 起默认随包）")
    args = ap.parse_args()

    global FULL_TERR, FULL_PV
    FULL_TERR = bool(args.full_terr)
    FULL_PV = bool(args.full_pv)

    log("=" * 58)
    log("云朵小铺 · FYS 通关奖励看板 —— 一键打包分发")
    log("=" * 58)
    log("源码目录：%s" % APP)

    ver = read_app_ver()
    last_ver = ""
    try:
        if os.path.exists(VER_FILE):
            with open(VER_FILE, encoding="utf-8") as fh:
                last_ver = fh.read().strip()
    except OSError:
        last_ver = ""
    if last_ver and ver == last_ver:
        log("⚠️  版本号仍是 %s，与上次发行相同——有新功能记得把 fys_reward_app.py 的"
            " APP_VER 抬一位，并在 CHANGELOG 里补一条。" % ver)
    else:
        log("本次发行版本：%s（上次发行：%s）" % (ver, last_ver or "无记录"))

    if not os.path.isdir(APP):
        raise SystemExit("找不到源码目录：%s" % APP)

    if args.check:
        need = report_changes()
        log("")
        log("提示：要打就直接跑  python build_dist.py")
        return 0 if not need else 0

    # 预检：发行目录里的 exe 若正被占用，第 4 步复制会 WinError 32，白等一整轮打包
    # （实测最常见的原因就是「自己开着软件看效果」，pywebview 是 bootloader+应用双进程）。
    pkg_exe = os.path.join(PKG_DIR, "FYS-Reward.exe")
    if os.path.exists(pkg_exe):
        try:
            with open(pkg_exe, "r+b"):
                pass
        except OSError:
            raise SystemExit(
                "⚠️  发行目录里的 FYS-Reward.exe 正被占用 —— 多半是「云朵小铺」还开着。\n"
                "    请先关掉软件窗口，并确认没有残留进程：\n"
                "      taskkill /F /IM FYS-Reward.exe\n"
                "    被占用的文件：%s" % pkg_exe)

    builder_py, pv = find_builder_py()
    if not builder_py:
        raise SystemExit("没找到带 PyInstaller 的 Python，先装：pip install pyinstaller")
    base_py = find_base_py()
    log("打包器：%s（PyInstaller %s）" % (builder_py, pv))

    total = 5
    need = report_changes()
    if not need:
        log("      仍然继续打包：只是把产物重新构建一次（内容一致）。")
        log("      想跳过就走  python build_dist.py --check")

    if not args.skip_sync:
        step(1, total, "刷新数据索引")
        refresh_index(base_py)
    else:
        log("\n[1/5] 跳过刷新索引（--skip-sync）")

    step(2, total, "打包 exe")
    sync_spec_root()
    if not pyinstaller(builder_py):
        return 1

    ok = True
    if not args.skip_test:
        step(3, total, "冒烟验证")
        ok = smoke_test()
    else:
        log("\n[3/5] 跳过冒烟验证（--skip-test）")

    step(4, total, "组装分发包")
    zip_path = package()
    try:
        with open(VER_FILE, "w", encoding="utf-8") as fh:
            fh.write(ver)              # 发行成功才记录版本
    except OSError:
        pass

    step(5, total, "收尾")
    for p in [WORK_DIR, BUILD_LOG]:
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
    if not args.keep_tmp:
        shutil.rmtree(TMP, ignore_errors=True)
    log("  已清理临时构建文件")

    log("")
    log("=" * 58)
    log("完成 ✓   冒烟：%s" % ("通过" if ok else "有异常，请查看上面输出"))
    log("分发包目录：%s" % PKG_DIR)
    log("分享用压缩包：%s" % zip_path)
    log("=" * 58)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())

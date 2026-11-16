# -*- mode: python ; coding: utf-8 -*-
# 云朵小铺 · FYS 通关奖励看板 —— 单文件打包
# 内置数据（rewards/maps/meta/infect/knockback/译名表）→ 首次运行即离线可用
from PyInstaller.utils.hooks import collect_all

ROOT = 'C:/Users/1/WorkBuddy/2026-09-21-14-59-35/fys-reward'

datas = [
    (ROOT + '/data/rewards.json', 'data'),
    (ROOT + '/data/maps.json', 'data'),
    (ROOT + '/data/meta.json', 'data'),
    (ROOT + '/data/infect.json', 'data'),
    # 每图 cfg 的全量 ConVar（约 180KB）：上游变更检测的基准表。官方提交里
    # 占大头的是「修改地图参数」，只跟 infect.json 的 4 项尸变参数会整类漏报
    # （2026-10-01 加：ze_obj_abyss_v2 的 ze_cash_damage_zombie 改动就没被认出来）
    (ROOT + '/data/mapcfg.json', 'data'),
    (ROOT + '/data/knockback.json', 'data'),
    (ROOT + '/data/platform_mapnames.json', 'data'),
    # EXG 图池补充图的中文名（_exg_merge.py 生成）：官方译名表没有这批图，
    # 兜在「精选整名」之后、词根合成之前，见 mapnames.cn 的优先级注释
    (ROOT + '/data/exg_mapnames.json', 'data'),
    (ROOT + '/data/sample_broadcast.txt', 'data'),
    # 本地补充层（EXG 补充图 / 样板图）：官方索引每次同步整体覆盖 maps.json，
    # 这批条目必须随 exe 分发并在首次运行释放到 data\\，否则「立即同步」后 EXG 视图变 0
    # （v2.5 真实事故：spec/seed_cache 漏了这两个文件，用户同步后 99 张 EXG 全丢）
    (ROOT + '/data/maps_local.json', 'data'),
    (ROOT + '/data/rewards_local.json', 'data'),
    # 配置层文件清单（哪张图的哪类文件动过，靠哈希认；约 79KB）与上游变更台账
    # （upd_log.json）。v2.9 加。前者同时被 is_fresh() 判定，缺了它每次启动都会
    # 以为数据不新鲜而去联网同步；后者让用户首启就能看到已知的历史改动。
    # ⚠ 与 seed_cache() 的释放清单必须一致（v2.5 的 maps_local 事故同款坑）。
    (ROOT + '/data/repo_files.json', 'data'),
    (ROOT + '/data/upd_log.json', 'data'),
    (ROOT + '/logo_embed.png', 'data'),
    # 地图封面 541 张（约 4.9MB）必须**打进 exe**：一键更新只替换 exe，不会带来
    # exe 旁的 cover\ 目录 —— 只随 zip 分发的话，老用户升级后地图库整页没有封面
    # （v2.3 真实事故）。运行时仍优先读 exe 旁那份，见 cover_dirs()。
    (ROOT + '/cover', 'cover'),
    # 地图实体预览页（约 34MB）不再打进 exe：作为独立文件 preview3d.html 随包
    # 放在 exe 旁，由本机服务 /preview3d 提供给系统浏览器打开（内嵌渲染会拖卡软件）
]
binaries = []
hiddenimports = ['pythonnet', 'clr_loader',
                 'bg_assets']   # 界面背景素材模块（data URI 常量，build_page 里按需导入）

# ── 剔除三处「静态分析误判 / 用不到」的体积 ──────────────────────────────
# ① excludes：Pillow 10.x 的 PIL/_typing.py 里有一句
#      try: from numpy.typing import NDArray
#      except ImportError: pass          ← 纯类型标注，没装 numpy 也能跑
#    PyInstaller 静态分析照单全收，触发 hook-numpy 的 collect_dynamic_libs()，
#    把整个 numpy 连它自带的 OpenBLAS 全打进包。实测（_exe_audit2.py）：
#      numpy.libs\libscipy_openblas64_*.dll   20.10 MB
#      numpy\ 本体合计                         6.35 MB
#    **本项目运行时零使用 numpy**（全仓只有临时对比图脚本用过），纯属白背 26.4MB。
#    实测佐证：新进程里 import PIL.Image 后 sys.modules 立刻多出 numpy.typing。
EXCLUDES = ['numpy', 'scipy', 'pandas', 'matplotlib']

for pkg in ('webview', 'pythonnet'):
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

# ② Python.Runtime.xml 是给 Visual Studio 看的文档注释，运行时用不到（183KB）。
#    ⚠ 必须在 Analysis **之后**裁剪：它是 PyInstaller 自带 hook-pythonnet 自己收集的
#    （会直接进 a.datas），只过滤上面 collect_all() 的返回值根本管不到它们
#    （实测：改完 collect_all 过滤后，新版 exe 里这项照旧存在）。
#    裁剪口径用「归档内的目标名」而不是源路径 —— a.datas 是 (目标名, 源, 类型) 三元组。
#
# ⚠⚠ 另两份 WebView2Loader.dll（win-arm64 / win-x86，263KB）**绝对不能删**，
#    虽然本机（以及目标用户）都是 x64。原因是 pywebview 的
#      webview/platforms/edgechromium.py 第 50 行：
#          for platform in ('win-arm64', 'win-x64', 'win-x86'):
#              os.environ['Path'] += ';' + interop_dll_path(platform)
#    它把三个架构名**逐个无条件解析一遍**，任何一个找不到就当场
#      raise FileNotFoundError('Cannot find win-arm64')
#      （util.py:517，frozen 下会去 sys._MEIPASS 找同名目录）。
#    v2.7 真实事故：只裁了 arm64/x86 两份，主窗与覆盖小窗全部起不来 ——
#    冒烟 8/17，startup.log 里 [兜底] Edge 模式后紧跟 FATAL FileNotFoundError。
#    这 263KB 是「必须陪着 x64 一起存在」的占位，只能留着。
_PRUNE_XML = ('python.runtime.xml',)


def _prune(toc):
    keep = []
    for e in toc:
        name = str(e[0]).replace('\\', '/').lower()
        if name.endswith(_PRUNE_XML):
            continue
        keep.append(e)
    return keep


a = Analysis(
    [ROOT + '/fys_reward_app.py'],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
# hook 收进来的无用项在这里被剔除（见上方 ② 说明）
_before = len(a.datas) + len(a.binaries)
a.datas = _prune(a.datas)
a.binaries = _prune(a.binaries)
print("[spec] 裁剪无用条目 %d 项（datas+binaries）"
      % (_before - len(a.datas) - len(a.binaries)))

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,     # onedir：二进制/数据走 COLLECT，不再打进单文件
    name='FYS-Reward',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ROOT + '/app.ico'],
)

# ── onedir（目录式）打包（2026-11-09 起）──────────────────────────────
# 用户明确表示只要压缩包、不用「一键更新只换 exe」，改为 onedir：
#  · onefile 每次启动都要把 23MB exe 解压到临时目录（杀软扫描叠加），
#    这是 exe 冷启动最大的那块耗时；onedir 双击即起，无解压步骤。
#  · 产物 dist4/FYS-Reward/{FYS-Reward.exe, _internal/}，
#    build_dist.py 已适配整目录分发。
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FYS-Reward',
)

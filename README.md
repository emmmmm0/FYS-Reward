# 云朵小铺 · FYS ZE 通关奖励看板

CS2（僵尸逃亡 ZE）风云社服务器的通关奖励查询工具：地图库、关卡奖励、服务器状态、
屏幕覆盖小窗、对局战绩（CS2 GSI）与 3D 实体预览。

非官方工具，与 Valve / 风云社官方无关；奖励数值来自官方公开仓库，仅作查询用途。

## 下载

- **推荐**：[Releases](https://github.com/emmmmm0/FYS-Reward/releases) 里下最新版
  `云朵小铺-FYS通关奖励看板.zip`，解压后双击 `FYS-Reward.exe`（免安装，解压即用）
- 老版本可在软件「设置 → 关于 → 检查更新」里升级（只替换 exe，`_internal` 与配置不动）

## 目录

| 路径 | 说明 |
|---|---|
| `src/` | 主程序源码（`fys_reward_app.py` 为入口） |
| `build/` | 打包脚本 `build_dist.py`、PyInstaller spec、版本清单生成 `_mk_version.py` |
| `tools/_upload_terr.py` | 上传 3D 地形分包到 `fys-terr` 仓库（客户端按需下载） |
| `update/version.json` | **更新清单**：客户端「检查更新」读这一份 |
| `dist/` | 各版本 exe（更新下载源，单文件 <20MB 才能走 jsDelivr） |
| `docs_使用说明.txt` | 面向玩家的使用说明 |

## 构建

Python 3.13 + PyInstaller（onedir，勿用 onefile）：

```bat
python build\build_dist.py           :: 打包到「云朵小铺-FYS通关奖励看板」
python build\build_dist.py --full-terr  :: 离线整包（把地形也打进去，+284MB）
```

## 更新机制

- 客户端读 `update/version.json`，多源：jsDelivr → ghproxy → raw
- 新版 exe 放 `dist/FYS-Reward-vX.Y.Z.exe`，清单里的 `urls` 同时给三个源
- 下载后 sha256 强校验，不通过一律不替换

## 3D 地形

安装包只带预览壳（`preview3d.html`）；地形（`terr/<工坊ID>.bin`，中位 0.4MB）在第一次
点开某张图时按需下载并缓存，托管在 [fys-terr](https://github.com/emmmmm0/fys-terr)。

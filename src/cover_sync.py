# -*- coding: utf-8 -*-
r"""地图封面管线（v2.15 结构⑦：从 fys_reward_app.py 拆出）。

职责：封面目录解析（exe 旁 cover\ + exe 内置副本）、本地查找（cover_fetch）、
新图封面直连风云社图床补齐（cover_sync，320×180、7 天冷却、_missing.json 过滤）、
封面统计（cover_stat）。

与主模块的关系：
  · 顶层只 import 标准库 + PIL，不反向 import 主模块（避免循环）；
  · BASE_DIR / State / log 通过 _app() 晚绑定 —— 调用时主模块必然已加载完
    （cover_sync 只会在同步线程 / HTTP 请求里被调）；
  · fys_reward_app 顶部 `from cover_sync import ...` re-export 全部名字，
    对外行为与拆分前一致（测试直接 A.cover_fetch_upstream 也照常工作）。
"""
import io
import json
import os
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from PIL import Image


def _app():
    """晚绑定主模块（fys_reward_app 在本文件之后才可能被完整加载）。"""
    import fys_reward_app
    return fys_reward_app


_COVER_LOCKS = {}
_COVER_LOCK_GUARD = threading.Lock()

def cover_dirs():
    """封面候选目录，按优先级返回：
      ① exe 旁的 cover\\  —— 分发包里那份；也便于单独替换 / 热修某一张图
      ② 打包进 exe 的内置副本 —— onefile 解包目录（_MEIPASS\\cover）

    ⚠ ② 不能省（v2.3 真实事故）：封面原本只随 zip 分发、放在 exe 旁，
    而一键更新**只替换 exe**，不会带来 exe 旁的 cover 目录 —— 老用户升级后
    地图库整页没有封面（全 404）。内置一份后，更新上来即刻有封面。"""
    out = [os.path.join(_app().BASE_DIR, "cover")]
    inner = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cover")
    if os.path.normcase(os.path.abspath(inner)) != os.path.normcase(os.path.abspath(out[0])):
        out.append(inner)                       # 源码目录与 exe 目录相同时不重复登记
    return out


def cover_dir(make=False):
    """封面主目录（exe 旁的 cover\\），由 _build_covers.py 生成后随包分发。
    和 terr 不同：封面是**分发资源**不是缓存 —— 首屏就要用，缺了就退回默认底纹。
    只用于统计 / 写入；**读取务必走 find_cover()**，它会把内置副本一起算上。"""
    d = cover_dirs()[0]
    if make:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
    return d


def find_cover(name):
    """按候选目录顺序找一张封面，命中返回完整路径，都没有返回 None。"""
    for d in cover_dirs():
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def _cover_lock(name):
    with _COVER_LOCK_GUARD:
        lk = _COVER_LOCKS.get(name)
        if lk is None:
            lk = _COVER_LOCKS[name] = threading.Lock()
        return lk


def cover_index_remote(force=False):
    """（已停用）云端封面清单。v2.14 起中转服务器下线，封面改为「随包分发 +
    cover_sync() 直连官方图床补新图」，本函数只剩兼容空实现，勿再新增调用。"""
    return {}


def cover_fetch(name):
    """取单张封面（v2.14 起纯本地：cover\\ + 内置副本是唯一来源）。
    返回路径；本地没有返回 None（前端静默回退默认底纹）。
    新图封面由 cover_sync() 直连 resx.fyscs.cn 补齐，不走这里。"""
    d = cover_dir(make=True)
    if not d:
        return None
    fp = os.path.join(d, name)
    return fp if os.path.isfile(fp) else None


# ── 新图封面自动补齐（v2.14）────────────────────────────────────────────
# 封面以前只有两个来源：发版时打进包 / 停用前那台服务器。前者意味着「官方出新图
# → 玩家要等下个版本才有封面」，后者已经没了。但封面真正的源头
# resx.fyscs.cn/mapimgs/ 是**风云社自己的公开图床**（网页端就在用，国内直连），
# 不是我们那台机器 —— 所以客户端完全可以自己去取。
#
# 触发点：每次地图数据同步成功之后（_sync_worker），把「当前索引里有、本地却
# 没封面」的图挑出来直连图床补齐；压成 320x180（和 _build_covers.py 同参，
# 不留几百 KB 的原图），原子落盘、失败进冷却表，不重复骚扰图床。
COVER_UPSTREAM = (os.environ.get("FYS_COVER_UPSTREAM") or
                  "https://resx.fyscs.cn/mapimgs/")
COVER_UP_TIMEOUT = 12.0
COVER_UP_WORKERS = 4                # 并发 4：新图通常个位数，够快又不至于打爆图床
COVER_UP_TRY_TTL = 7 * 86400.0      # 同一张图抓失败后 7 天内不再试（新图常是图床还没出图）
COVER_UP_MAX = 200                  # 单次上限：首跑老用户最多补 200 张，剩下的下次同步继续
COVER_W, COVER_H, COVER_Q = 320, 180, 78
_COVER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
_COVER_SYNC = {"running": False, "at": None, "checked": 0, "got": 0, "miss": 0,
               "names": [], "msg": "未开始"}
_COVER_SYNC_LOCK = threading.Lock()
_COVER_STAT_CACHE = {"t": 0.0, "v": None}


def cover_try_path():
    """封面抓取冷却表（data\\cover_try.json）：{图名: 上次失败时间戳}。"""
    return os.path.join(_app().BASE_DIR, "data", "cover_try.json")


def cover_try_load():
    try:
        with open(cover_try_path(), encoding="utf-8") as fh:
            d = json.load(fh)
        if isinstance(d, dict):
            return {str(k).lower(): float(v) for k, v in d.items()
                    if isinstance(v, (int, float))}
    except Exception:                                          # noqa: BLE001
        pass
    return {}


def cover_try_save(d):
    p = cover_try_path()
    tmp = p + ".part"
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)
        os.replace(tmp, p)
    except OSError as e:                                       # noqa: BLE001
        _app().log("cover: 冷却表写入失败 %r" % (e,))
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def cover_missing_known():
    """图床「确认没有」的图名（打包时 _build_covers.py 留下的 _missing.json）。
    有这张表就能少发几百个注定 404 的请求；缺了也不影响功能，只是多几次试错。"""
    out = set()
    for d in cover_dirs():
        p = os.path.join(d, "_missing.json")
        try:
            with open(p, encoding="utf-8") as fh:
                arr = json.load(fh)
        except Exception:                                      # noqa: BLE001
            continue
        out |= {str(n).lower() for n in arr if isinstance(n, str)}
    return out


def cover_stat(force=False):
    """本地封面张数 {count, mb}（设置页显示用，缓存 5 秒）。"""
    now = time.time()
    v = _COVER_STAT_CACHE["v"]
    if not force and v is not None and now - _COVER_STAT_CACHE["t"] < 5.0:
        return v
    cnt = 0
    size = 0
    seen = set()
    for d in cover_dirs():
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for f in names:
            if not f.lower().endswith(".jpg") or f.lower() in seen:
                continue
            try:
                size += os.path.getsize(os.path.join(d, f))
            except OSError:
                continue
            seen.add(f.lower())
            cnt += 1
    v = {"count": cnt, "mb": round(size / 1048576.0, 1)}
    _COVER_STAT_CACHE.update(t=now, v=v)
    return v


def _cover_shrink(raw):
    """原图 → 320x180 JPEG（居中裁剪；参数与 _build_covers.py 的 shrink() 一致）。
    PIL 不可用 / 图片格式怪时原样返回 —— 前端按 cover 裁切，大一点不影响显示。"""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        sw, sh = im.size
        if not sw or not sh:
            return raw
        ar_src, ar_dst = sw / float(sh), COVER_W / float(COVER_H)
        if ar_src > ar_dst:
            nw = int(sh * ar_dst)
            im = im.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
        else:
            nh = int(sw / ar_dst)
            im = im.crop((0, (sh - nh) // 2, sw, (sh - nh) // 2 + nh))
        im = im.resize((COVER_W, COVER_H), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=COVER_Q, optimize=True, progressive=True)
        return buf.getvalue()
    except Exception:                                          # noqa: BLE001
        return raw


def cover_fetch_upstream(name):
    """直连官方图床取一张封面，返回 (状态, 路径)：
       ok   已补齐（压成 320x180 落盘）
       skip 本地已有（不发请求）
       miss 图床没有这张（404）
       bad  回来的不是像样的 JPEG（代理/网关塞错误页）
       net  超时/断网/5xx（不计冷却，下次同步再试）"""
    n = (name or "").lower()
    if not re.fullmatch(r"[a-z0-9_.\-]{1,80}", n):
        return "bad", None
    have = find_cover(n + ".jpg")
    if have:
        return "skip", have
    d = cover_dir(make=True)
    if not d or not COVER_UPSTREAM:
        return "net", None
    fp = os.path.join(d, n + ".jpg")
    with _cover_lock(n + ".jpg"):
        if os.path.isfile(fp):          # 等锁期间可能已被另一个请求补上了
            return "skip", fp
        tmp = fp + ".part"
        try:
            import urllib.request
            # 走系统代理：图床在国内，多数用户直连即可；开了代理的人也不至于被卡死
            req = urllib.request.Request(COVER_UPSTREAM + n + ".jpg",
                                         headers={"User-Agent": _COVER_UA})
            with urllib.request.urlopen(req, timeout=COVER_UP_TIMEOUT) as r:
                raw = r.read()
            # JPEG 魔数校验：防代理 / 网关塞回一个 HTML 错误页当成功
            if len(raw) < 2048 or raw[:2] != b"\xff\xd8":
                return "bad", None
            out = _cover_shrink(raw)
            with open(tmp, "wb") as fh:
                fh.write(out)
            os.replace(tmp, fp)         # 原子落盘，避免半截文件被当成命中
            _COVER_STAT_CACHE["t"] = 0.0
            _app().log("cover: 补齐 %s（原图 %.0f KB → %.0f KB）"
                % (n, len(raw) / 1024.0, len(out) / 1024.0))
            return "ok", fp
        except Exception as e:                                 # noqa: BLE001
            code = getattr(e, "code", None)
            _app().log("cover: 补齐失败 %s %r" % (n, e))
            return ("miss" if code == 404 else "net"), None
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


def cover_sync(names=None, force=False, wait=False):
    """把本地缺的地图封面从官方图床补齐（v2.14）。

    什么时候跑：地图数据同步成功后自动触发（_sync_worker），也可
    /api/ctl?do=coversync 手动触发（force=1 连"图床没有"的也重试一次）。
      names  指定图名（调试/回归用），不给就取当前索引里全部 ze 图名
      force  忽略 7 天冷却与 cover/_missing.json
      wait   同步阻塞执行（回归用），默认后台线程，不挡同步流程
    返回状态字典；只有真补到了新图才抬 dgen 让前端缓存换代。
    """
    with _COVER_SYNC_LOCK:
        if _COVER_SYNC["running"] and not wait:
            return dict(_COVER_SYNC)
    if names is None:
        st = getattr(_app().State.engine, "STATE", None) or {}
        pool = set()
        for k in ("maps", "rewards"):        # 并集：rewards 独有的新图也要抓
            d = st.get(k) or {}
            if isinstance(d, dict):
                pool |= set(d.keys())
        names = sorted(n for n in pool if isinstance(n, str) and n.startswith("ze"))
        if not names:
            # 首启时索引还在后台建（_boot_load），这里别把状态写成「已齐」误导排查
            _COVER_SYNC.update(running=False, msg="索引尚未就绪，稍后再试")
            return dict(_COVER_SYNC)
    else:
        names = sorted({str(n).lower() for n in names})

    known_miss = set() if force else cover_missing_known()
    try_map = {} if force else cover_try_load()
    now = time.time()
    todo = []
    skip_local = skip_miss = skip_cool = 0
    for n in names:
        key = n.lower()
        if find_cover(key + ".jpg"):
            skip_local += 1
            continue
        if key in known_miss:
            skip_miss += 1
            continue
        t = try_map.get(key)
        if t and now - t < COVER_UP_TRY_TTL:
            skip_cool += 1
            continue
        todo.append(key)
    overflow = max(0, len(todo) - COVER_UP_MAX)
    todo = todo[:COVER_UP_MAX]

    def work():
        got, miss, net = [], [], 0
        try:
            if todo:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=COVER_UP_WORKERS) as ex:
                    for n, (st, _p) in zip(todo, ex.map(cover_fetch_upstream, todo)):
                        if st == "ok":
                            got.append(n)
                        elif st in ("miss", "bad"):
                            miss.append(n)
                        elif st == "net":
                            net += 1
        except Exception as e:                                 # noqa: BLE001
            _app().log("cover-sync: 批量补齐异常 %r" % (e,))
        finally:
            if got or miss:
                cur = cover_try_load()
                for n in got:
                    cur.pop(n, None)
                for n in miss:
                    cur[n] = time.time()
                cut = time.time() - 30 * 86400.0       # 只留 30 天内，别让表无限长
                cover_try_save({k: v for k, v in cur.items() if v >= cut})
            if got:
                try:
                    _app().State.engine.bump_data_gen()       # 有新封面 → 前端缓存换代重渲染
                except Exception:                      # noqa: BLE001
                    pass
            msg = ("新补 %d 张封面" % len(got)) if got else (
                "封面已齐（本地 %d 张）" % skip_local if not todo else "没有可补的封面")
            _COVER_SYNC.update(running=False, at=time.strftime("%Y-%m-%d %H:%M:%S"),
                               checked=len(todo), got=len(got), miss=len(miss),
                               names=got[:20], msg=msg)
            _app().log("cover-sync: 待补 %d 张 → 新增 %d / 图床没有 %d / 网络失败 %d"
                "（本地已有 %d，图床确认无 %d，冷却中 %d，超出上限 %d）"
                % (len(todo), len(got), len(miss), net,
                   skip_local, skip_miss, skip_cool, overflow))

    _COVER_SYNC.update(running=True, at=time.strftime("%Y-%m-%d %H:%M:%S"),
                       checked=len(todo), got=0, miss=0, names=[],
                       msg="正在补齐 %d 张新图封面…" % len(todo) if todo
                       else "封面已齐（本地 %d 张）" % skip_local)
    if wait:
        work()
    elif todo:
        threading.Thread(target=work, daemon=True, name="cover-sync").start()
    else:
        _COVER_SYNC["running"] = False
    return dict(_COVER_SYNC)

# -*- coding: utf-8 -*-
"""给「地图实体预览」页补译名（两件事，都打在源文件上）

① 静态：payload 里每个地图的 `cn` 用 mapnames.cn() 重算后写回。
   原来构建 _build_preview_data.py 时只查了「完美平台译名表」一层
   （`"cn": CNNAMES.get(mapkey) or ""`），而软件内地图库走的是三层
   （用户表 → 平台表 → 精选整名 → 词根），于是预览页明明能翻的图也显示英文名。

② 动态：页面里加一段 `/api/mapnames` 拉取，用软件侧最新译名**覆盖**壳内快照。
   于是以后服务器补译名，预览页即刻生效，不用重下 14MB 的预览壳。
   （file:// 直接打开时跳过，保持离线可用。）

payload 结构（同 _build_preview_data.py 的写出）：
    gzip( 4字节小端 JSON 长度 | JSON | 二进制块区 ) → base64

用法：python _patch_preview_names.py            # 预检，只报告不写
      python _patch_preview_names.py --apply    # 实际写入
改完记得跑 _sync_preview.py 同步到 fys-reward/preview3d.html
"""
import base64
import gzip
import io
import json
import os
import sys
import time

ROOT = r"C:\Users\1\WorkBuddy\2026-09-21-14-59-35"
SRC_HTML = os.path.join(ROOT, "地图实体预览-3D视图.html")
MARK = '<script id="payload" type="text/plain">'
ANCHOR = "$('q').addEventListener('input', buildSide);"
ANCHOR2 = "  CLS = DATA.classes; MAPKEYS = Object.keys(DATA.maps);"

ZEFILTER_JS = """  /* 只保留僵尸逃跑（ze_）地图：本工具只服务 ZE 玩法，ttt（恐怖分子小镇）/
     mg（小游戏）/ de（拆弹）等图不在此列。放在 MAPKEYS 生成之前，侧栏、搜索、
     徽章统计都会一起跟着只剩 ze 图。（payload 里也已物理删除，这里再兜一层，
     将来即使重建了 payload 也不会把非 ze 图带回来。） */
  (function(){
    var mm=0, ea=0, ek=0, mesh=0, drop=0;
    for(var k in DATA.maps){
      var m = DATA.maps[k];
      if(!/^ze_/i.test(m.m || '')){ delete DATA.maps[k]; drop++; continue; }
      mm++; ea += (m.n||0); ek += (m.k||0); if(m.wm) mesh++;
    }
    if(drop && DATA.meta){
      DATA.meta.maps = mm;
      DATA.meta.entities_all = ea;
      DATA.meta.entities_kept = ek;
      if(DATA.meta.mesh_maps) DATA.meta.mesh_maps = mesh;
    }
  })();
"""

sys.path.insert(0, os.path.join(ROOT, "fys-reward"))
import mapnames                                                   # noqa: E402

JS_BLOCK = """
/* ── 译名兜底（2026-09-28）─────────────────────────────────────────────
   壳里的 cn 是打包时的快照；这里向本机软件要一份最新译名来覆盖，
   于是服务器补译名后本页即刻生效，无需重新下载预览壳。
   file:// 直接打开（软件没在跑）时跳过，照旧用快照。 */
(function(){
  function pullNames(){
    if(location.protocol!=='http:' && location.protocol!=='https:') return;
    fetch('/api/mapnames', {cache:'no-store'}).then(function(r){ return r.json(); })
      .then(function(j){
        var t = (j && j.names) || null;
        if(!t) return;
        var hit = 0;
        for(var k in DATA.maps){
          var m = DATA.maps[k], c = t[m.m];
          if(c && c !== m.cn){ m.cn = c; hit++; }
        }
        if(!hit) return;
        buildSide();                                   /* 侧栏列表刷新 */
        if(cur) $('mtitle').textContent = cur.m.cn || cur.m.m;
      }).catch(function(){});
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', pullNames);
  else pullNames();
  setInterval(pullNames, 1800000);                    /* 半小时再看一次 */
})();
"""


def main():
    apply = "--apply" in sys.argv
    t0 = time.time()
    h = io.open(SRC_HTML, encoding="utf-8").read()
    print("源文件 %.2f MB" % (len(h) / 1048576))

    # ── ② JS：插入运行时拉取 ──
    n_anchor = h.count(ANCHOR)
    has_block = "pullNames" in h
    print("JS 锚点① 命中 %d 次；已含拉取块 = %s" % (n_anchor, has_block))
    if n_anchor != 1:
        print("！锚点不唯一，放弃")
        return 1
    if not has_block:
        h = h.replace(ANCHOR, ANCHOR + JS_BLOCK, 1)

    # ── ①-b JS：运行时只保留 ze 图（兜底，防止将来重建 payload 时回潮）──
    n2 = h.count(ANCHOR2)
    has_ze = "只保留僵尸逃跑" in h
    print("JS 锚点② 命中 %d 次；已含 ze 过滤 = %s" % (n2, has_ze))
    if n2 != 1:
        print("！锚点②不唯一，放弃")
        return 1
    if not has_ze:
        h = h.replace(ANCHOR2, ZEFILTER_JS + ANCHOR2, 1)

    # ── ① 静态：重算 payload 里的 cn ──
    i = h.find(MARK)
    if i < 0:
        print("！找不到 payload 段")
        return 1
    j = h.find("</script>", i)
    old_b64 = h[i + len(MARK):j]
    ab = gzip.decompress(base64.b64decode(old_b64.strip()))
    jlen = int.from_bytes(ab[:4], "little")
    bins = ab[4 + jlen:]
    payload = json.loads(ab[4:4 + jlen].decode("utf-8"))
    print("payload: JSON %.2f MB / BINS %.2f MB / maps %d"
          % (jlen / 1048576, len(bins) / 1048576, len(payload.get("maps") or {})))

    maps = payload.get("maps") or {}
    # ① 只保留僵尸逃跑（ze_）地图 —— 本工具只服务 ZE 玩法，
    #    ttt（恐怖分子小镇）/ mg（小游戏）/ de（拆弹）等图整条移除。
    #    groups / tp / pp / ip / op / kp 都是与具体地图无关的全局字典，
    #    所以删条目不会影响详情面板与图层面板。
    removed = {k: v for k, v in maps.items()
               if not (v.get("m") or "").lower().startswith("ze_")}
    for k in removed:
        del maps[k]
    payload["maps"] = maps
    meta = payload.get("meta")
    if isinstance(meta, dict) and removed:
        meta["maps"] = len(maps)
        meta["entities_all"] = max(0, (meta.get("entities_all") or 0)
                                   - sum(v.get("n") or 0 for v in removed.values()))
        meta["entities_kept"] = max(0, (meta.get("entities_kept") or 0)
                                    - sum(v.get("k") or 0 for v in removed.values()))
        if meta.get("mesh_maps"):
            meta["mesh_maps"] = max(0, meta["mesh_maps"]
                                    - sum(1 for v in removed.values() if v.get("wm")))
    print("地图：删掉非 ze %d 张，剩 %d 张（徽章 meta.maps=%s）"
          % (len(removed), len(maps), (meta or {}).get("maps")))

    changed, added, dropped = [], [], []
    for k, v in maps.items():
        m = v.get("m") or ""
        if m.startswith(("ttt_", "mg_")):
            # 恐怖分子小镇 / 小游戏两类图按需求不做译名，保持原名显示
            if v.get("cn"):
                v["cn"] = ""
                dropped.append(m)
            continue
        new = mapnames.cn(m)
        if not new:
            continue
        old = str(v.get("cn") or "")
        if new == old:
            continue
        (added if not old else changed).append((m, old, new))
        v["cn"] = new
    print("译名：新增 %d 条 / 修正 %d 条 / 清掉 ttt·mg %d 条"
          % (len(added), len(changed), len(dropped)))
    for m, old, new in (added + changed)[:8]:
        print("    %-42s %s -> %s" % (m, old or "(空)", new))

    raw = json.dumps(payload, ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    packed = len(raw).to_bytes(4, "little") + raw + bins
    new_b64 = base64.b64encode(gzip.compress(packed, 9)).decode("ascii")
    print("重新打包：JSON %.2f MB → base64 %.2f MB（原 %.2f MB）"
          % (len(raw) / 1048576, len(new_b64) / 1048576, len(old_b64) / 1048576))

    h = h[:i + len(MARK)] + new_b64 + h[j:]
    print("成品 %.2f MB（用时 %.1fs）" % (len(h) / 1048576, time.time() - t0))

    if not apply:
        print("\n== 预检完成，未写入（加 --apply 实际写入）==")
        return 0
    tmp = SRC_HTML + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(h)
    os.replace(tmp, SRC_HTML)
    print("已写入 %s" % SRC_HTML)
    print("记得跑：python _sync_preview.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

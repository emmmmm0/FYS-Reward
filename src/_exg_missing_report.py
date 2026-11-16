# -*- coding: utf-8 -*-
"""生成 EXG 缺图整合报告（_exg_missing_report.html）。

内容：概览 → exg 分类结构 → 样板条目「内容 ↔ 官方结构」逐字段对照 → 缺图清单。
用法：python _exg_missing_report.py
"""
import collections
import html
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "_exg_missing_report.html")


def rj(p):
    return json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else {}


def ranges(maps, field):
    c = collections.Counter()
    for v in maps.values():
        if isinstance(v, dict) and field in v:
            c[json.dumps(v[field], ensure_ascii=False)] += 1
    return c


def main():
    miss = rj(os.path.join(HERE, "_exg_missing.json"))
    samp = rj(os.path.join(HERE, "_sample_entry.json"))
    maps, rew = rj(os.path.join(DATA, "maps.json")), rj(os.path.join(DATA, "rewards.json"))
    maps_local = rj(os.path.join(DATA, "maps_local.json"))
    side = rj(os.path.join(DATA, "exg_local.json"))
    exg_names = rj(os.path.join(DATA, "exg_mapnames.json"))
    rows = miss.get("maps") or []
    meta = miss.get("meta") or {}
    CAT_KEY = "cat"
    CAT = (side.get("cat") if side else None) or "exg"

    # 官方字段集：必须**剔除本地补充条目**（它们多一个 cat 字段，不是官方结构）
    want, seen = [], set()
    for k, v in maps.items():
        if k in maps_local or not isinstance(v, dict):
            continue
        for kk in v:
            if kk not in seen:
                seen.add(kk)
                want.append(kk)
    swant, sseen = [], set()
    for k, v in rew.items():
        if k in maps_local:
            continue
        for st in (v.values() if isinstance(v, dict) else []):
            if isinstance(st, dict):
                for kk in st:
                    if kk not in sseen:
                        sseen.add(kk)
                        swant.append(kk)

    obj, stage = samp.get("obj") or {}, (samp.get("stage") or {}).get("1") or {}
    ok_obj = [f for f in obj if f != CAT_KEY] == want and obj.get(CAT_KEY) == CAT
    ok_stage = list(stage) == swant
    cn_n = len(exg_names)

    def obj_rows():
        out = []
        for f in want:
            c = ranges(maps, f)
            top = " / ".join(k for k, _ in c.most_common(3))
            out.append(
                "<tr><td class=f>%s</td><td class=v>%s</td><td class=d>%s</td>"
                "<td class=d>%d 张图用到</td></tr>"
                % (html.escape(f), html.escape(json.dumps(obj.get(f), ensure_ascii=False)),
                   html.escape(top), sum(c.values())))
        return "".join(out)

    def stage_rows():
        out = []
        for f in swant:
            c = collections.Counter()
            for v in rew.values():
                for st in (v.values() if isinstance(v, dict) else []):
                    if isinstance(st, dict) and f in st:
                        c[json.dumps(st[f], ensure_ascii=False)] += 1
            top = " / ".join(k for k, _ in c.most_common(3))
            out.append(
                "<tr><td class=f>%s</td><td class=v>%s</td><td class=d>%s</td>"
                "<td class=d>%d 关用到</td></tr>"
                % (html.escape(f), html.escape(json.dumps(stage.get(f), ensure_ascii=False)),
                   html.escape(top), sum(c.values())))
        return "".join(out)

    def miss_rows():
        out = []
        for i, r in enumerate(rows, 1):
            e = r.get("exg") or {}
            out.append(
                "<tr><td class=n>%d</td><td class=f>%s</td><td>%s</td><td class=d>%s</td>"
                "<td class=d>%s</td><td class=d>%s</td><td class=d>%s</td>"
                "<td class=d>%s</td></tr>"
                % (i, html.escape(r["name"]), html.escape(r.get("cn") or "—"),
                   html.escape(r.get("pid") or "—"),
                   html.escape(e.get("DifficultyName") or "—"),
                   html.escape(e.get("ZeTagStr") or "—"),
                   "有" if r.get("preview") else "无",
                   "有" if r.get("cover") else "无"))
        return "".join(out)

    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EXG 缺图整合 · 样板条目</title>
<style>
:root{--bg:#f4f6f8;--card:#fff;--fg:#1f2328;--mut:#6a737d;--line:#e4e8ec;
      --acc:#2f81f7;--ok:#1a7f37;--okbg:#e8f5ea;--code:#f0f3f6}
@media(prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#161b22;--fg:#e6edf3;
      --mut:#8b949e;--line:#30363d;--acc:#58a6ff;--ok:#3fb950;--okbg:#12301c;--code:#1c2230}}
*{box-sizing:border-box}
body{margin:0;padding:28px 20px 60px;background:var(--bg);color:var(--fg);
     font:14px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:21px;margin:0 0 4px}
.sub{color:var(--mut);font-size:13px;margin-bottom:22px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card b{display:block;font-size:24px;line-height:1.25}
.card span{color:var(--mut);font-size:12px}
h2{font-size:16px;margin:26px 0 10px}
.box{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-bottom:18px}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:12px;
       background:var(--okbg);color:var(--ok);border:1px solid var(--ok);margin-left:8px}
.badge.bad{background:#fdecec;color:#c0392b;border-color:#c0392b}
table{width:100%%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:600;font-size:12px;background:var(--code)}
td.f{font-family:ui-monospace,Consolas,monospace;color:var(--acc)}
td.v{font-family:ui-monospace,Consolas,monospace;font-weight:600}
td.d{color:var(--mut);font-size:12px}
td.n{color:var(--mut);width:38px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:820px){.two{grid-template-columns:1fr}}
.note{color:var(--mut);font-size:12.5px;margin-top:8px}
.scroll{max-height:520px;overflow:auto}
</style></head><body><div class="wrap">
<h1>EXG 缺图整合 · 地图库样板条目</h1>
<div class="sub">生成 %s ｜ 口径与 <code>_check_pool.py</code> 的 A 栏一致</div>
<div class="cards">
  <div class="card"><b>%d</b><span>EXG 图池 ze</span></div>
  <div class="card"><b>%d</b><span>官方地图库 ze</span></div>
  <div class="card"><b>%d</b><span>缺图（已整合入库）</span></div>
  <div class="card"><b>%d</b><span>同图异名（不算缺）</span></div>
</div>

<h2>分类：🧩 EXG 补充<span class="badge%s">%s</span></h2>
<div class="box">
<table>
<tr><th>项</th><th>值</th><th>说明</th></tr>
<tr><td class="f">cat</td><td class="v">"%s"</td>
    <td class="d">分类标记，直接写在地图库条目里（官方条目没有这个字段；
        地图库页面靠它出「🧩 EXG 补充」分类与行徽标）</td></tr>
<tr><td class="f">张数</td><td class="v">%d</td>
    <td class="d">落在 <code>data/maps_local.json</code> / <code>rewards_local.json</code>
        —— 本地补充层，官方同步不会覆盖（见 <code>build_index.load_local()</code>）</td></tr>
<tr><td class="f">登记表</td><td class="v">data/exg_local.json</td>
    <td class="d">每张一条：EXG 工坊ID、玩法标签、难度、估算依据（分组 + 样本数）、
        参数与奖励、3D 预览 / 封面状态</td></tr>
<tr><td class="f">中文名</td><td class="v">%d / %d</td>
    <td class="d">落进 <code>data/exg_mapnames.json</code>，接在译名回退链
        「用户 → 云端 → 平台表 → 精选整名」<b>之后</b>、词根合成之前</td></tr>
<tr><td class="f">界面</td><td class="v">🧩 EXG 补充</td>
    <td class="d">地图库分类 chip（可多选）+ 列表行 🧩 徽标 + 详情页估算说明</td></tr>
</table>
<div class="note">这批图<b>没有官方参数与奖励数据</b>：条目里的数值是
「同玩法标签 + 同难度」的库内众数估算，仅供浏览参考、不代表服务器真实配置
（界面上已明示）。</div>
</div>

<h2>样板条目：%s（%s）<span class="badge%s">%s</span></h2>
<div class="box">
<div class="note" style="margin:0 0 12px">%s</div>
<div class="two">
  <div><div class="note" style="margin:0 0 6px"><b>data/maps.json</b> · 选图参数</div>
    <table><tr><th>字段</th><th>样板取值</th><th>官方取值域</th><th></th></tr>%s</table></div>
  <div><div class="note" style="margin:0 0 6px"><b>data/rewards.json</b> · 第 1 关奖励</div>
    <table><tr><th>字段</th><th>样板取值</th><th>官方取值域</th><th></th></tr>%s</table></div>
</div>
<div class="note">样板字段集 = 官方 maps.json / rewards.json 的字段并集（逐字段校验），
数值按「同 ZeTag + 同难度」分组取库内众数。</div>
</div>

<h2>缺图清单（%d 张，已全部入库）</h2>
<div class="box"><div class="scroll"><table>
<tr><th>#</th><th>地图名</th><th>中文名</th><th>工坊ID</th><th>难度</th><th>标签</th><th>3D 预览</th><th>封面</th></tr>
%s</table></div></div>
<div class="note">这 %d 张官方图床 <b>0 张有封面</b>（全量探测过），按既定口径保持空白、不做假图。</div>
</div></body></html>
""" % (time.strftime("%Y-%m-%d %H:%M"),
       meta.get("exg", 0), meta.get("lib", 0), meta.get("missing", len(rows)),
       meta.get("alias", 0),
       "" if (side.get("cat") == CAT) else " bad",
       "cat = %s · %d 张" % (CAT, len(maps_local)) if maps_local else "分类登记表缺失",
       html.escape(CAT), len(maps_local), cn_n, len(maps_local),
       html.escape(samp.get("map", "?")), html.escape(samp.get("cn") or "—"),
       "" if ok_obj and ok_stage else " bad",
       "字段结构与官方一致（另加 cat）" if ok_obj and ok_stage else "结构不一致，请检查",
       html.escape(samp.get("_note") or ""),
       obj_rows(), stage_rows(), len(rows), miss_rows(), len(rows))

    io.open(OUT, "w", encoding="utf-8").write(doc)
    print("[ok] 报告 → %s（%.1f KB）" % (OUT, os.path.getsize(OUT) / 1024.0))
    print("     obj 字段一致：%s ｜ stage 字段一致：%s" % (ok_obj, ok_stage))
    return 0 if (ok_obj and ok_stage) else 1


if __name__ == "__main__":
    sys.exit(main())

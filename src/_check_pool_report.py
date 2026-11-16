# -*- coding: utf-8 -*-
"""把 _check_pool.json 渲染成一份可读报告，并探「官方图床有没有封面」。

用法：python _check_pool_report.py
产出：fys-reward/_check_pool_report.html
"""
import concurrent.futures as cf
import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "_check_pool.json")
OUT = os.path.join(HERE, "_check_pool_report.html")
IMG = "https://resx.fyscs.cn/mapimgs/%s.jpg"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"

_op = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def cover_ok(name):
    try:
        r = _op.open(urllib.request.Request(IMG % name, headers={"User-Agent": UA}),
                     timeout=15)
        return name, len(r.read()) > 2048
    except Exception:                                                # noqa: BLE001
        return name, False


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main():
    d = json.load(io.open(SRC, encoding="utf-8"))
    A, B = d["图池有库没有"], d["库有图池没有"]
    AA, BB = d.get("异名_A", []), d.get("异名_B", [])

    names = [x["名"] for x in A]
    print("探封面：%d 张…" % len(names))
    cov = {}
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for n, ok in ex.map(cover_ok, names):
            cov[n] = ok
    ncov = sum(1 for v in cov.values() if v)
    for x in A:
        x["图床有封面"] = cov.get(x["名"], False)

    rows_a = "\n".join(
        "<tr><td class=m><code>%s</code></td><td>%s</td><td class=p>%s</td>"
        "<td class=c>%s</td><td class=c>%s</td></tr>"
        % (esc(x["名"]), esc(x["中文"]), esc(x["pid"]),
           "<span class=no>无</span>" if not x["预览"] else "<span class=yes>有</span>",
           "<span class=yes>有</span>" if x["图床有封面"] else "<span class=no>无</span>")
        for x in A)
    rows_b = "\n".join(
        "<tr><td class=m><code>%s</code></td><td class=c>%s</td><td class=c>%s</td>"
        "<td class=c>%s</td></tr>"
        % (esc(x["名"]),
           "<span class=yes>有</span>" if x["预览"] else "<span class=no>无</span>",
           "<span class=yes>有</span>" if x["封面"] else "<span class=no>无</span>",
           esc(x["来源"]))
        for x in B)

    html = """<!doctype html><html lang=zh-CN><meta charset=utf-8>
<title>图池 ⇄ 地图库 核对报告</title>
<style>
:root{color-scheme:light dark}
body{margin:0;padding:28px 22px 60px;font:14px/1.65 -apple-system,"Segoe UI",
 "Microsoft YaHei",sans-serif;background:#f6f7f9;color:#1c1f23}
@media (prefers-color-scheme:dark){body{background:#17191c;color:#e7eaee}
 .card{background:#1f2226!important;border-color:#2c3036!important}
 th{background:#242830!important} tr:nth-child(even) td{background:#1b1e22!important}
 code{background:#22262b!important;color:#c9d1d9!important}}
h1{font-size:21px;margin:0 0 4px}
.sub{color:#6b7280;font-size:12.5px;margin-bottom:20px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:22px}
.card{background:#fff;border:1px solid #e3e6ea;border-radius:10px;padding:12px 18px;
 min-width:118px}
.card b{display:block;font-size:23px;line-height:1.25}
.card span{font-size:12px;color:#6b7280}
h2{font-size:16px;margin:26px 0 8px}
h2 em{font-style:normal;color:#6b7280;font-weight:400;font-size:12.5px}
table{border-collapse:collapse;width:100%;background:#fff;border-radius:10px;
 overflow:hidden;font-size:13px}
th{background:#eef1f4;text-align:left;padding:8px 10px;font-weight:600;font-size:12.5px;
 position:sticky;top:0}
td{padding:6px 10px;border-top:1px solid #eceff2}
tr:nth-child(even) td{background:#fafbfc}
td.m code{font-size:12px}
td.c{text-align:center;width:64px}
td.p{color:#6b7280;font-family:ui-monospace,Consolas,monospace;font-size:12px}
.yes{color:#0a8f4a;font-weight:600}.no{color:#b0b6bd}
.note{background:#fff;border-left:3px solid #4c8dff;border-radius:0 8px 8px 0;
 padding:10px 14px;margin:14px 0;font-size:13px;color:#3b4048}
@media (prefers-color-scheme:dark){.note{background:#1f2226;color:#c3c9d1}}
</style>
<h1>图池 ⇄ 地图库 核对报告</h1>
<div class=sub>生成时间 __TS__ ｜ 图池来源：EXG 公开表 list.darkrp.cn:9000/ServerList/CurrentCs2MapStatus
 ｜ 地图库 = data/maps.json ∪ data/rewards.json</div>

<div class=cards>
 <div class=card><b>__NPOOL__</b><span>图池 ze</span></div>
 <div class=card><b>__NLIB__</b><span>地图库 ze</span></div>
 <div class=card><b>__INTER__</b><span>两边都有</span></div>
 <div class=card><b>__NA__</b><span>图池有 · 库没有</span></div>
 <div class=card><b>__NB__</b><span>库有 · 图池没有</span></div>
 <div class=card><b>__NCOV__</b><span>其中图床有封面</span></div>
</div>

<div class=note>判定顺序：工坊 ID 命中 → 中文名命中 → 归一化名命中（剥掉
 <code>_p</code>/<code>_cs2</code>/<code>_z</code>/<code>_v2</code> 这类版本后缀）→
 名相似度 ≥ 0.90 且候选唯一。已剔除 __NAA__ / __NBB__ 张实为异名的条目，下表是剩下的。</div>

<h2>A · 图池有、地图库没有 —— __NA__ 张</h2>
<table><tr><th>图名</th><th>中文名</th><th>工坊 ID</th><th>预览</th><th>图床封面</th></tr>
__ROWS_A__
</table>

<h2>B · 地图库有、图池没有 —— __NB__ 张 <em>（多半是服务器已下架 / 换图池的旧图）</em></h2>
<table><tr><th>图名</th><th>预览</th><th>本地封面</th><th>来源</th></tr>
__ROWS_B__
</table>
</html>"""

    rep = (html.replace("__TS__", d["ts"])
           .replace("__NPOOL__", str(d["图池"])).replace("__NLIB__", str(d["地图库"]))
           .replace("__INTER__", str(d["图池"] - len(A)))
           .replace("__NA__", str(len(A))).replace("__NB__", str(len(B)))
           .replace("__NAA__", str(len(AA))).replace("__NBB__", str(len(BB)))
           .replace("__NCOV__", str(ncov))
           .replace("__ROWS_A__", rows_a).replace("__ROWS_B__", rows_b))
    io.open(OUT, "w", encoding="utf-8").write(rep)
    print("A=%d（图床有封面 %d）  B=%d" % (len(A), ncov, len(B)))
    print("报告 →", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

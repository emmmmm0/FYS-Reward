# -*- coding: utf-8 -*-
"""v2.4 视觉/交互优化补丁：精确替换 + 逐条校验命中次数。

用法：python _patch_v24_visual.py        只检查并报错（不改文件）
      python _patch_v24_visual.py --apply  真正写入
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "ui_page.py")

# (id, old, new, 期望命中次数)
PATCHES = [
    # ── 1. .cbtn 两套基础样式打架：947 行那块是「作者名片」专用，改名 .cbtn.pri ──
    ("cbtn-pri-old", '.cbtn{appearance:none;border:none;background:var(--accent);color:#fff;font:700 11.5px/1 inherit;',
     '.cbtn.pri{appearance:none;border:none;background:var(--accent);color:#fff;font:700 11.5px/1 inherit;', 1),
    ("cbtn-pri-hover", '.cbtn:hover{transform:translateY(-1px)}\n.cbtn:active{transform:translateY(2px);box-shadow:0 0 0 var(--softline)}',
     '.cbtn.pri:hover{transform:translateY(-1px)}\n.cbtn.pri:active{transform:translateY(2px);box-shadow:0 0 0 var(--softline)}', 1),
    # ── 2. 在线人数「热/中」两档写死 E/H 主色 → 提为 --hot/--mid，跟随主题 ──
    ("onhot", ".online.h .onnum{color:#f2608d}", ".online.h .onnum{color:var(--hot)}", 1),
    ("onmid", ".online.m .onnum{color:#f08a24}", ".online.m .onnum{color:var(--mid)}", 1),
    ("onfill-h", ".online.h .onfill{background:linear-gradient(90deg,#ff9dc0,#f2608d)}",
     ".online.h .onfill{background:linear-gradient(90deg,color-mix(in srgb,var(--hot) 62%,#fff),var(--hot))}", 1),
    ("onfill-m", ".online.m .onfill{background:linear-gradient(90deg,#ffc07d,#f08a24)}",
     ".online.m .onfill{background:linear-gradient(90deg,color-mix(in srgb,var(--mid) 62%,#fff),var(--mid))}", 1),
    ("on-n-hot", 'html[data-theme="N"] .online.h .onnum{color:#ff9dc0}\nhtml[data-theme="N"] .online.m .onnum{color:#ffc07d}', '', 1),
    # ── 3. 斑马纹：服务器表被单独排除，与紧邻的关卡表观感相反 → 统一 ──
    ("zebra-del", "/* 服务器表行底色统一（去掉斑马纹），当前所在服高亮保留 */\n"
     "#stb tr:nth-child(even):not(.cur) td{background:transparent}\n", "", 1),
    # ── 4. 服务器行 hover 写死 12% 灰 → 走主题变量（夜幕下几乎看不出反馈）──
    ("srvrow-hover", "tr.srvrow:hover{background:rgba(128,128,128,.12)}",
     "tr.srvrow:hover td{background:var(--soft)}", 1),
    # ── 5. 一键更新横条顶着 .card 却把边框内距吃掉 → 交回 .card ──
    ("updbar", ".updBar{display:flex;align-items:center;gap:10px;padding:10px 13px;\n"
     "  border:1px solid #3b6d11;background:#eaf3de;color:#27500a;flex-wrap:wrap}",
     ".updBar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}", 1),
    ("updbar-back", ".updBar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}",
     ".updBar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}\n"
     ".card.updBar{background:#eaf3de;border-color:#3b6d11;color:#27500a}", 1),
    # ── 6. 主题切换过渡漏了一堆同屏元素 → 补全选择器 ──
    ("theme-trans", "html.aTheme .srv,html.aTheme pre,html.aTheme .nav,html.aTheme .tag,html.aTheme .syncbox{",
     "html.aTheme .srv,html.aTheme pre,html.aTheme .nav,html.aTheme .tag,html.aTheme .syncbox,\n"
     "html.aTheme .cpill,html.aTheme .infoBar,html.aTheme .srvLegend,html.aTheme .libChip,\n"
     "html.aTheme .libRow,html.aTheme .itag,html.aTheme .dRow,html.aTheme .ovpane>summary,\n"
     "html.aTheme .themePal,html.aTheme .bgcard,html.aTheme .fxcard,html.aTheme .rmcard,\n"
     "html.aTheme .syncbox .sub,html.aTheme .curpill,html.aTheme .updBar{", 1),
    # ── 7. 小窗 560 宽时服务器表头溢出压字 → 省略号兜底 ──
    ("srvtab-th", "table.srvtab{table-layout:fixed}",
     "table.srvtab{table-layout:fixed}\n"
     "table.srvtab th,#stb td{overflow:hidden;text-overflow:ellipsis}", 1),
    # ── 8. 地图库 5 列表窄窗被 .main 的 overflow-x 静默裁掉 → 允许换行 ──
    ("lib-table", "<div class=\"card\"><h2>每关奖励配置</h2><table><thead><tr>",
     "<div class=\"card\"><h2>每关奖励配置</h2><table class=\"libStg\"><thead><tr>", 1),
    ("lib-table-css", "table.srvtab th,#stb td{overflow:hidden;text-overflow:ellipsis}",
     "table.srvtab th,#stb td{overflow:hidden;text-overflow:ellipsis}\n"
     "/* 地图库「每关奖励配置」5 列表：窄窗下 nowrap 会把整列挤出 .main 被裁掉 */\n"
     "table.libStg{table-layout:fixed}\n"
     "table.libStg th,table.libStg td{white-space:normal;word-break:break-word;overflow:hidden}", 1),
    # ── 9. 收藏按钮反馈太弱 → 补背景与光圈；.libPv 补样式 ──
    ("libfavd", ".libFavD.on{border-color:#f5a623;color:#c77c0a;background:#fff7e8}",
     ".libFavD.on{border-color:#f5a623;color:#a06b06;background:#fff7e8;\n"
     "  box-shadow:0 0 0 3px var(--soft)}\n"
     "/* 地图库「地图实体预览」按钮：此前只有类名没有任何规则，形同虚设 */\n"
     ".btn.libPv{background:var(--soft);border-color:var(--softline);color:var(--accent)}", 1),
    ("libfavd-n", 'html[data-theme="N"] .libFavD.on{background:#2c2415;color:#f5c26b;border-color:#8a6a2f}',
     'html[data-theme="N"] .libFavD.on{background:#3b2f14;color:#ffc078;border-color:#8a6a2f;\n'
     '  box-shadow:0 0 0 3px var(--soft)}', 1),
    # ── 10. 死规则清理：被 299/300/303 行整块覆盖的 220/221 行 ──
    ("dead-th", "th{background:var(--soft);color:var(--accent);letter-spacing:.08em;padding:9px 9px;font-size:10px}\n"
     "td{padding:9px 9px;border-bottom:2px solid var(--panel2)}\n", "", 1),
    # ── 12. 小字可读性：最影响阅读的几处提到 11px 并去掉低对比 opacity ──
    ("kv-k", ".kv .k{font-size:10.5px;", ".kv .k{font-size:11px;", 1),
    ("stgsub", ".stgsub{font-size:11px;opacity:.65;margin-top:3px}",
     ".stgsub{font-size:11.5px;color:var(--ink2);margin-top:3px}", 1),
    ("rawempty-t2", ".rawEmpty .t2{font-size:11px;color:var(--muted);margin-top:5px;line-height:1.7}",
     ".rawEmpty .t2{font-size:11.5px;color:var(--ink2);margin-top:5px;line-height:1.7}", 1),
    ("onweb", ".onweb{margin-top:3px;font-size:9.5px;line-height:1.4}",
     ".onweb{margin-top:3px;font-size:10.5px;line-height:1.4}", 1),
    ("curpill", ".curpill{display:inline-block;margin-left:7px;font-size:9.5px;",
     ".curpill{display:inline-block;margin-left:7px;font-size:10.5px;", 1),
    # ── 13. .cbtn / .sw 缺 disabled 态（点了没反馈时至少看出「在忙」） ──
    ("cbtn-dis", ".cbtn{appearance:none;border:2px solid var(--line);",
     ".cbtn:disabled{opacity:.5;cursor:not-allowed}\n"
     ".cbtn:disabled:hover{border-color:var(--line);color:var(--ink2)}\n"
     ".cbtn{appearance:none;border:2px solid var(--line);", 1),
    # ── 14. .sw 缺 disabled 态 ──
    ("sw-dis", ".cbtn:disabled{opacity:.5;cursor:not-allowed}\n.cbtn:disabled:hover{border-color:var(--line);color:var(--ink2)}",
     ".cbtn:disabled{opacity:.5;cursor:not-allowed}\n.cbtn:disabled:hover{border-color:var(--line);color:var(--ink2)}\n"
     ".sw:disabled{opacity:.5;cursor:not-allowed}", 1),
    # ── 15. .libSel 去掉焦点框不留补偿 → 补 :focus-visible（键盘可达性） ──
    ("libsel-focus", "padding:4px 9px;font:11.5px/1.4 inherit;font-family:inherit;font-weight:700;cursor:pointer;outline:none}",
     "padding:4px 9px;font:11.5px/1.4 inherit;font-family:inherit;font-weight:700;cursor:pointer;outline:none}\n"
     ".libSel:focus-visible{outline:2px solid var(--accent);outline-offset:2px}", 1),
    # ── 16. preFrame 最小高度 420px 在小窗里把工具条顶出视口 ──
    ("preframe", "#preFrame{width:100%;height:calc(100vh - 150px);min-height:420px;",
     "#preFrame{width:100%;height:calc(100vh - 150px);min-height:min(420px,calc(100vh - 200px));", 1),
    # ── 17. --hot/--mid：在线人数「热/中」档的颜色来源（此前写死 E/H 主色） ──
    ("hot-mid", ":root{--radius:20px;--r-sm:12px;",
     ":root{\n"
     "/* 在线人数「热/中」两档的强调色。此前直接写死 E/H 主题的主色，\n"
     "   切到 F/G 主题时在线数字还是粉/橙，与整页强调色打架 —— 抽成变量跟随主题。 */\n"
     "--hot:#f2608d;--mid:#f08a24;--radius:20px;--r-sm:12px;", 1),
    # 各主题按自身 accent 覆盖（E/H 恰好与旧硬编码一致，视觉零变化）
    ("hot-F", 'html[data-theme="F"]{--bg:#f2fdf7;--panel:#fff;--panel2:#f5fdf9;--zebra:#f9fefb;--thead:#dcf6ea;',
     'html[data-theme="F"]{--hot:#28a97a;--mid:#d4a017;--bg:#f2fdf7;--panel:#fff;--panel2:#f5fdf9;--zebra:#f9fefb;--thead:#dcf6ea;', 1),
    ("hot-G", 'html[data-theme="G"]{--bg:#fbf4ff;--panel:#fff;--panel2:#faf6ff;--zebra:#fcf9ff;--thead:#efe4ff;',
     'html[data-theme="G"]{--hot:#8f6bff;--mid:#e0803c;--bg:#fbf4ff;--panel:#fff;--panel2:#faf6ff;--zebra:#fcf9ff;--thead:#efe4ff;', 1),
    ("hot-N", 'html[data-theme="N"]{--bg:#16151a;--panel:#1e1d24;--panel2:#26242e;--zebra:#1b1a21;--thead:#262432;',
     'html[data-theme="N"]{--hot:#ff9dc0;--mid:#ffc07d;--bg:#16151a;--panel:#1e1d24;--panel2:#26242e;--zebra:#1b1a21;--thead:#262432;', 1),
]


def main():
    apply = "--apply" in sys.argv
    with io.open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()
    fails = []
    for item in PATCHES:
        pid, old = item[0], item[1]
        new = item[2] if len(item) > 2 else old
        want = item[3] if len(item) > 3 else 0
        if want == 0:
            # 期望「不存在」的补丁（纯保险项），存在则算异常
            if old in src:
                fails.append("%s: 期望不存在，实际命中 1 次 (%r)" % (pid, old[:50]))
            continue
        got = src.count(old)
        if got != want:
            fails.append("%s: 期望命中 %d 次，实际 %d 次 (%r)" % (pid, want, got, old[:70]))
            continue
        if new != old:
            src = src.replace(old, new)      # 预检时也在内存里串行替换，
                                             # 否则依赖前一条结果的补丁必然误报
    if fails:
        print("补丁未应用，存在问题：")
        for x in fails:
            print("  - " + x)
        return 1
    n = len([p for p in PATCHES if len(p) > 3 and p[3] != 0])
    if not apply:
        print("预检通过：%d 条全部命中预期次数（未写入）" % n)
        return 0
    with io.open(TARGET, "w", encoding="utf-8") as f:
        f.write(src)
    print("已应用 %d 条补丁 -> %s" % (n, TARGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())

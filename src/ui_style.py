# -*- coding: utf-8 -*-
"""界面样式表（原 ui_page.py 里的 <style> 块，v2.14 拆出）。

单独下发到 /static/app.css：改样式只动这个文件；
主题变量、字阶 / 间距 / 层级 token 全部定义在文件开头的 :root 里。"""

CSS = r"""
/* ═══════════════ 主题调色板 ═══════════════ */
html[data-theme="E"]{--bg:#fff6f8;--panel:#fff;--panel2:#fff7fa;--zebra:#fffafc;--thead:#ffe9f0;
--side:#ffeff5;--ink:#4a323c;--ink2:#6b4a56;--muted:#8a6a76;--line:#ffd9e4;
--accent:#f2608d;--soft:#ffe7ef;--softline:#ffc7d9;--good:#57bd8b;--goodsoft:#e6f7ee;
--glow:rgba(242,96,141,.13);--blob1:#ffe1ea;--blob2:#ffeadb;--emo:"🍓"}
html[data-theme="F"]{--hot:#28a97a;--mid:#d4a017;--bg:#f2fdf7;--panel:#fff;--panel2:#f5fdf9;--zebra:#f9fefb;--thead:#dcf6ea;
--side:#ecfaf3;--ink:#254238;--ink2:#3f6356;--muted:#4f7a67;--line:#ccefe0;
--accent:#28a97a;--soft:#ddf7ea;--softline:#b5ead3;--good:#28a97a;--goodsoft:#e4f8ee;
--glow:rgba(40,169,122,.13);--blob1:#d7f5e7;--blob2:#e6fbef;--emo:"🍀"}
html[data-theme="G"]{--hot:#8f6bff;--mid:#e0803c;--bg:#fbf4ff;--panel:#fff;--panel2:#faf6ff;--zebra:#fcf9ff;--thead:#efe4ff;
--side:#f6efff;--ink:#3c3358;--ink2:#564a7a;--muted:#756a9b;--line:#e4d9ff;
--accent:#8f6bff;--soft:#f0e8ff;--softline:#d6c6ff;--good:#54b7d6;--goodsoft:#e6f5fb;
--glow:rgba(143,107,255,.15);--blob1:#eadcff;--blob2:#dcebff;--emo:"🌸"}
html[data-theme="H"]{--bg:#fff9ef;--panel:#fff;--panel2:#fffaf1;--zebra:#fffdf8;--thead:#ffeacd;
--side:#fff4e3;--ink:#4a3a20;--ink2:#6d5730;--muted:#7f683f;--line:#ffe0b8;
--accent:#f08a24;--soft:#fff0d8;--softline:#ffd9a3;--good:#63b96a;--goodsoft:#eaf7ea;
--glow:rgba(240,138,36,.15);--blob1:#ffe8c9;--blob2:#ffeede;--emo:"🍑"}
html[data-theme="N"]{--hot:#ff9dc0;--mid:#ffc07d;--bg:#16151a;--panel:#1e1d24;--panel2:#26242e;--zebra:#1b1a21;--thead:#262432;
--side:#1a1920;--ink:#e9e4ee;--ink2:#c6bfd0;--muted:#918aa0;--line:#322f3a;
--accent:#f0a868;--soft:#2b2420;--softline:#453729;--good:#7fc79b;--goodsoft:#20302a;
--glow:rgba(0,0,0,.5);--blob1:#241f2c;--blob2:#1f2429;--emo:"🌙";
--c-new:#5fc492;--c-edit:#f0b567;--c-stage:#6db2e8;
--c-zombie:#a98fd0;--c-param:#67c0b8;--c-del:#d98a99}
:root{
/* 在线人数「热/中」两档的强调色。此前直接写死 E/H 主题的主色，
   切到 F/G 主题时在线数字还是粉/橙，与整页强调色打架 —— 抽成变量跟随主题。 */
--hot:#f2608d;--mid:#f08a24;--radius:20px;--r-sm:12px;
--mono:"Cascadia Code","JetBrains Mono",Consolas,monospace;
--disp:"Arial Rounded MT Bold","Segoe UI","Microsoft YaHei",sans-serif;
/* 字阶（v2.14 美化④）：全站字号只允许这 4 档，9~10.5px 的小字已统一提到 11px */
--fs-xs:11px;--fs-sm:12.5px;--fs-md:14px;--fs-lg:16px;
/* 间距栅格（v2.14 美化⑨）：4px 基准的几档常用值；新写样式从这里取，
   旧样式逐步迁移 —— 一次性全量替换 100+ 处 padding 风险大于收益 */
--sp-1:4px;--sp-2:8px;--sp-3:12px;--sp-4:16px;--sp-5:18px;--sp-6:24px;
/* 交互微反馈时长（v2.15 美化⑰）：hover/按压过渡统一 120ms，别再各写各的 */
--t:120ms;
/* 层级（v2.14 美化⑩）：谁压谁看这里，别再随手写 z-index 魔数 */
--z-decor:1;--z-stick:6;--z-card:10;--z-nav:100;--z-modal:1000;--z-system:9000;--z-resize:9500;--z-toast:9999;
/* 变更类别色（v2.14 美化⑪）：徽章/图表共用，夜幕主题在下方单独调亮 */
--c-new:#4caf7d;--c-edit:#e8a33d;--c-stage:#4a9ad4;
--c-zombie:#8e6fb8;--c-param:#4aa8a0;--c-del:#c66a7c}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:var(--bg);color:var(--ink);overflow:hidden;
font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;
-webkit-font-smoothing:antialiased;user-select:none}
/* 主题切换渐变统一走下方 aTheme 块（html.aTheme body/.side/.card…），
   此处不再写死 transition——否则关掉「主题过渡」动效后切主题仍会渐变 */

/* ═══════════════ 外壳 ═══════════════
   窗口放大时界面不缩放（WorkBuddy 式）：内容保持原始大小，
   由 .content 的 max-width + margin:auto 居中，背景自然铺满。 */
.shell{position:relative;display:flex;flex-direction:column;
width:100%;height:100%;overflow:hidden}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--softline);border-radius:9px}
::-webkit-scrollbar-thumb:hover{background:var(--accent)}
::selection{background:var(--softline);color:var(--ink)}
/* 键盘可达性（v2.14 美化）：Tab 导航时给焦点画主题色环。
   只用 :focus-visible —— 鼠标点击不出环，键盘移动才出，两不干扰。 */
:focus-visible{outline:2.5px solid var(--accent);outline-offset:2px;border-radius:4px}
.wbtn:focus-visible,.fold:focus-visible{outline-offset:0}

/* ═══════════════ 自绘标题栏（颜色随主题） ═══════════════ */
.tbar{height:36px;flex:none;display:flex;align-items:center;gap:8px;padding:0 6px 0 12px;
background:var(--side);border-bottom:2px solid var(--line);cursor:default}
.tlogo{font-size:var(--fs-lg);line-height:1;flex:none}
.tlogo img{width:17px;height:17px;border-radius:5px;display:block}
.ttitle{font-size:var(--fs-sm);font-weight:800;color:var(--ink2);letter-spacing:.02em;
white-space:nowrap;overflow:hidden;display:flex;align-items:center;gap:6px}
/* ═══════ ⑩ 顶栏面包屑：云朵小铺 › 当前页（消除顶栏/侧栏品牌重复） ═══════ */
.ttitle .tsep{font-style:normal;color:var(--line);font-weight:900;font-size:var(--fs-md);margin:0 -1px}

/* ═══════ 窗口边缘缩放热区 ═══════
   无边框窗（pywebview frameless）没有非客户区，系统不会在窗口边缘提供缩放
   热区，拖边沿拉不动 —— 所以这里自绘 8 块透明热区，按下时把「开始缩放」
   交回系统（/api/ctl?do=resize&edge=…），和拖动标题栏同一套做法。
   边 4px / 角 14px：角比边大且两边热区都避开角，保证「角 → 双轴缩放」优先。 */
.rz{position:fixed;z-index:var(--z-resize);background:transparent}
.rz-n{top:0;left:14px;right:14px;height:4px;cursor:ns-resize}
.rz-s{bottom:0;left:14px;right:14px;height:4px;cursor:ns-resize}
.rz-w{left:0;top:14px;bottom:14px;width:4px;cursor:ew-resize}
.rz-e{right:0;top:14px;bottom:14px;width:4px;cursor:ew-resize}
.rz-nw{top:0;left:0;width:14px;height:14px;cursor:nwse-resize}
.rz-ne{top:0;right:0;width:14px;height:14px;cursor:nesw-resize}
.rz-sw{bottom:0;left:0;width:14px;height:14px;cursor:nesw-resize}
.rz-se{bottom:0;right:0;width:14px;height:14px;cursor:nwse-resize}
/* 最大化时不给缩放热区：最大化窗拖边沿的行为系统各版本不一致，隐藏最省心 */
html.aMax .rz{display:none}
.ttitle .tpage{font-weight:800;color:var(--accent);transition:color .18s ease}
html[data-theme="N"] .ttitle .tsep{color:rgba(255,255,255,.28)}
.wbtn{appearance:none;border:none;background:transparent;color:var(--muted);
width:36px;height:28px;margin-left:2px;font-size:var(--fs-md);line-height:1;border-radius:9px;cursor:pointer}
.wbtn:hover{background:var(--soft);color:var(--accent)}
.wbtn.close:hover{background:#e05555;color:#fff}
/* 贴纸窗口按钮（样板D·软萌贴纸）：彩色圆钮+白描边+俏皮倾斜 */
.wbtn.wst{width:22px;height:22px;margin-left:4px;padding:0;border-radius:50%;flex:none;
background:var(--wbg,#7ED9B4);font-size:0;
display:inline-flex;align-items:center;justify-content:center;
box-shadow:0 0 0 2.5px #FFFFFF,0 2px 5px rgba(185,159,142,.35);
transform:rotate(var(--tl,0deg));
transition:transform .16s ease,box-shadow .16s ease,background .16s ease}
.wbtn.wst svg{width:11px;height:11px;display:block}
.wbtn.wst-min{--wbg:#7ED9B4;--tl:-8deg}
.wbtn.wst-max{--wbg:#FFD97E;--tl:0deg}
.wbtn.wst-cls{--wbg:#FF9DB0;--tl:8deg}
.wbtn.wst:hover{transform:rotate(var(--tl,0deg)) scale(1.14);
box-shadow:0 0 0 2.5px #FFFFFF,0 4px 9px rgba(185,159,142,.45)}
.wbtn.wst-cls:hover{background:#FF8CA4}
.wbtn.wst:active{transform:rotate(var(--tl,0deg)) scale(.88)}
.wbtn.wst #svgMaxRestore{display:none}
.wbtn.wst.is-max #svgMaxNormal{display:none}
.wbtn.wst.is-max #svgMaxRestore{display:block}
html.aPress .wbtn.wst{transition:transform .2s cubic-bezier(.2,.8,.3,1.5),box-shadow .16s ease,background .16s ease}
/* 夜幕主题：窗口按钮降调（深色糖衣 + 暗描边，不刺眼；悬停微亮起） */
html[data-theme="N"] .wbtn.wst{--wbg:#3d5c4e;
  box-shadow:0 0 0 2px rgba(255,255,255,.15),0 2px 5px rgba(0,0,0,.42)}
html[data-theme="N"] .wbtn.wst-max{--wbg:#61482a}
html[data-theme="N"] .wbtn.wst-cls{--wbg:#633844}
html[data-theme="N"] .wbtn.wst svg{stroke:rgba(255,255,255,.72)}
html[data-theme="N"] .wbtn.wst:hover{box-shadow:0 0 0 2px rgba(255,255,255,.22),0 4px 9px rgba(0,0,0,.5)}
html[data-theme="N"] .wbtn.wst-min:hover{background:#4d7a65}
html[data-theme="N"] .wbtn.wst-max:hover{background:#82603a}
html[data-theme="N"] .wbtn.wst-cls:hover{background:#8a4d5c}

/* ═══════════════ 布局：侧栏 + 主区 ═══════════════ */
.app{display:flex;flex:1;min-height:0;align-items:stretch}
.side{width:212px;flex:none;background:var(--side);border-right:2px solid var(--line);
padding:14px 12px 16px;display:flex;flex-direction:column;gap:14px;
transition:background .25s ease}
.side.hide{display:none}
.stop{display:flex;align-items:center;gap:8px;padding:2px 4px 0}
.logo{font-size:22px;line-height:1;flex:none}
.logo img{width:23px;height:23px;border-radius:6px;display:block}
.sname{font-size:var(--fs-md);font-weight:800;letter-spacing:.02em;flex:1;white-space:nowrap;overflow:hidden}
/* 杀软误报自助说明块：默认收起，点「🛡️ 怎么办」展开 */
.avHelp{grid-column:1/-1;margin:2px 0 4px;padding:9px 11px;border-radius:10px;
  background:var(--panel2);border:1px dashed var(--softline);
  font-size:var(--fs-xs);line-height:1.65;color:var(--ink2)}
.avHelp b{color:var(--ink)}
.avHelp ol{margin:5px 0 0 16px;padding:0}
.avHelp li{margin:0 0 3px}
.avHelp code{display:inline-block;font-family:var(--mono);font-size:var(--fs-xs);
  background:var(--soft);border:1px solid var(--line);border-radius:6px;
  padding:2px 6px;margin:3px 0;word-break:break-all;user-select:text}
/* ── 底图取景框 ──
   在原图上拖一个框 → 服务端按框裁剪 → 成品作为底图。
   覆盖窗是很扁的横条，整张铺会把主体压扁/截掉，所以要能自己框一块。 */
.cropWrap{flex-direction:column!important;align-items:stretch!important;gap:10px;
  margin-top:8px;padding:10px;border:1px dashed var(--softline);border-radius:12px;
  background:var(--panel2)}
.cropBox{position:relative;max-width:100%;width:max-content;margin:0 auto;
  line-height:0;border-radius:8px;overflow:hidden;background:
  repeating-conic-gradient(var(--soft) 0% 25%,var(--panel) 0% 50%) 50%/16px 16px;
  cursor:crosshair;user-select:none}
.cropBox img{display:block;max-width:100%;max-height:340px;pointer-events:none}
.cropSel{position:absolute;border:2px solid var(--accent);border-radius:3px;
  box-shadow:0 0 0 9999px rgba(10,8,16,.5);cursor:move}
.cropSel .ch{position:absolute;width:12px;height:12px;background:var(--accent);
  border:2px solid #fff;border-radius:3px}
.cropSel .tl{left:-7px;top:-7px;cursor:nwse-resize}
.cropSel .tm{left:calc(50% - 6px);top:-7px;cursor:ns-resize}
.cropSel .tr{right:-7px;top:-7px;cursor:nesw-resize}
.cropSel .ml{left:-7px;top:calc(50% - 6px);cursor:ew-resize}
.cropSel .mr{right:-7px;top:calc(50% - 6px);cursor:ew-resize}
.cropSel .bl{left:-7px;bottom:-7px;cursor:nesw-resize}
.cropSel .bm{left:calc(50% - 6px);bottom:-7px;cursor:ns-resize}
.cropSel .br{right:-7px;bottom:-7px;cursor:nwse-resize}
.cropSide{display:flex;flex-direction:column;gap:7px}
.cropTip{font-size:var(--fs-xs);color:var(--ink2)}
.cropRow{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
/* 版本号：跟在「云朵小铺」后面，低对比小胶囊，不抢主标题 */
.sname .ver{display:inline-block;vertical-align:1px;margin-left:6px;
  font-size:var(--fs-xs);font-weight:700;letter-spacing:0;color:var(--ink2);
  background:var(--soft);border:1px solid var(--line);border-radius:999px;
  padding:1px 6px;line-height:1.5}
.fold{appearance:none;border:2px solid var(--line);background:var(--panel);color:var(--muted);
border-radius:9px;width:24px;height:24px;font-size:var(--fs-sm);line-height:1;cursor:pointer;flex:none}
.fold:hover{color:var(--accent);border-color:var(--softline)}
.wbtn.fold{display:none;font-size:var(--fs-lg)}
body.folded .wbtn.fold{display:block}
/* 死代码清理：原来这里的 .glab / .tbtn* / .sfoot 是旧版主题按钮组
   （已被 .tcard 取代），HTML/JS 里零引用，直接删掉免得误导维护 */
.sgroup{display:flex;flex-direction:column;gap:5px}
.nav{appearance:none;cursor:pointer;font-family:inherit;font-size:var(--fs-sm);font-weight:600;
display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:10px;border:none;
background:transparent;color:var(--ink2);text-align:left}
.nav:hover{background:var(--panel2);color:var(--accent)}
/* 侧栏主菜单按钮（服务器/主题/设置） */
.mv{font-size:var(--fs-md);font-weight:800;padding:11px 12px;border-radius:13px}
.mv.on{background:var(--soft);color:var(--accent);box-shadow:inset 0 0 0 2px var(--softline)}

.main{flex:1;min-width:0;position:relative;padding:16px var(--sp-5) var(--sp-6);overflow-y:auto;overflow-x:hidden;
display:flex;flex-direction:column}
.content{max-width:1500px;margin:0 auto;width:100%;display:flex;flex-direction:column;flex:1 0 auto}
.main::before,.main::after{content:"";position:absolute;border-radius:50%;pointer-events:none;z-index:0}
.main::before{width:210px;height:210px;right:-70px;top:-90px;background:var(--blob1);filter:blur(2px)}
.main::after{width:170px;height:170px;left:-80px;bottom:-100px;background:var(--blob2);filter:blur(2px)}
.main>*{position:relative;z-index:1}
/* ═══════════ 背景装饰层 · 贴纸手账（方格本 + 胶带 + 回形针） ═══════════
   纯装饰，不占布局、不吃鼠标事件；全部用主题变量上色，五主题自动跟随。 */
.bglayer{position:absolute;inset:0;pointer-events:none;z-index:0;overflow:hidden}
.bglayer i{position:absolute;display:block}
.main{background:
linear-gradient(90deg,var(--panel2) 1.5px,transparent 1.5px) 0 0/34px 34px,
linear-gradient(180deg,var(--panel2) 1.5px,transparent 1.5px) 0 0/34px 34px,var(--bg)}
/* 原双半圆球与格纹打架，收成右上角一处柔光 */
.main::before{width:0;height:0;filter:none}
.main::after{width:0;height:0;filter:none}
html[data-theme="N"] .main{background:
linear-gradient(90deg,var(--panel2) 1.5px,transparent 1.5px) 0 0/34px 34px,
linear-gradient(180deg,var(--panel2) 1.5px,transparent 1.5px) 0 0/34px 34px,var(--bg)}
/* 胶带条（半透明色块 + 两端虚线齿） */
.bgtape{height:26px;background:var(--softline);opacity:.42;
  border-left:2px dashed var(--panel);border-right:2px dashed var(--panel)}
.bgtape.t1{width:96px;left:22%;top:-6px;transform:rotate(-13deg)}
.bgtape.t2{width:74px;right:9%;top:38%;transform:rotate(64deg)}
.bgtape.t3{width:84px;left:2%;bottom:22%;transform:rotate(28deg)}
/* 回形针 */
.bgclip{width:22px;height:34px;border:3px solid var(--softline);border-radius:11px;
  border-bottom-color:transparent;opacity:.75}
/* 云朵贴纸（圆角矩形 + 两圆叠出） */
.cl{width:120px;height:52px;border-radius:999px;background:var(--soft);opacity:.34}
.cl::before,.cl::after{content:"";position:absolute;border-radius:50%;background:inherit}
.cl::before{width:54px;height:54px;left:15px;top:-24px}
.cl::after{width:39px;height:39px;right:20px;top:-17px}
.cl.c1{right:5%;top:6%;transform:scale(.75) rotate(-7deg)}
.cl.c2{left:30%;bottom:4%;transform:scale(.6) rotate(5deg)}
/* 圆点贴纸 */
.bgdot{width:13px;height:13px;border-radius:50%;background:var(--softline);opacity:.6}
/* 星形贴纸 */
.bgstar{font-size:var(--fs-lg);opacity:.5;color:var(--accent);font-style:normal}

/* ═══════════ 贴纸手账皮肤（只覆盖外观，布局结构不变） ═══════════ */
/* 卡片：贴纸硬阴影（右下错位） */
.card{border-width:3px;border-radius:22px;box-shadow:4px 5px 0 var(--softline)}
/* 四宫格 KPI：小贴纸阴影 */
.kv{border-width:3px;border-radius:16px;box-shadow:3px 3px 0 var(--panel2)}
.kv.hiA{box-shadow:3px 3px 0 var(--softline)}
.kv.hiB{box-shadow:3px 3px 0 var(--goodsoft)}
/* 服务器名胶囊：实线 + 贴纸投影 */
.srv{border-style:solid;box-shadow:3px 3px 0 var(--panel2)}
/* 标签：不对称圆角 + 小投影 */
.tag{border-radius:8px 12px 10px 12px;box-shadow:2px 2px 0 var(--panel2)}
/* 小标题：贴纸标签块 */
h2{display:inline-block;background:var(--soft);border:2px solid var(--softline);
border-radius:12px 14px 12px 14px;padding:5px 13px;box-shadow:2px 2px 0 var(--softline)}
/* 表格：整块贴纸砖，表头换主色浅底 */
table{background:var(--panel);border:3px solid var(--line);border-radius:20px;
overflow:hidden;box-shadow:5px 6px 0 var(--softline)}
/* 当前所在服：整圈描边标记 */
tbody tr.cur td{background:var(--soft)}
tbody tr.cur{outline:3px solid var(--softline);outline-offset:-3px}
/* 关卡弹窗内表格不参与贴纸化，保持深色原样 */
.stgtab{border:none!important;border-radius:0!important;box-shadow:none!important;background:transparent!important;overflow:visible!important}
.stgtab th{background:transparent!important;color:var(--ink2)!important}
.stgtab tr.cur{outline:none!important}
.bar{display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:var(--fs-xs);font-weight:700;
border-radius:999px;padding:5px 13px;border:2px solid var(--softline);
background:var(--soft);color:var(--accent);white-space:nowrap;flex:none}
.pill i{width:7px;height:7px;border-radius:50%;background:var(--muted);flex:none}
.pill.on i{background:var(--good);box-shadow:0 0 0 4px var(--goodsoft)}
.pill.off i{background:var(--accent)}
.spacer{flex:1}
.btn{appearance:none;border:2px solid var(--line);background:var(--panel);color:var(--ink2);
font:11.5px/1 inherit;font-family:inherit;font-weight:700;border-radius:999px;padding:7px 13px;
cursor:pointer;white-space:nowrap}
.btn:hover{border-color:var(--softline);color:var(--accent)}
.btn.act{background:var(--soft);border-color:var(--softline);color:var(--accent)}
/* 禁用态：原来 disabled 后仍带 hover 高亮 + 手型光标，看不出不可点 */
.btn:disabled{opacity:.5;cursor:not-allowed;filter:grayscale(.25)}
.btn:disabled:hover{border-color:var(--line);color:var(--ink2)}

.cols{display:grid;grid-template-columns:352px minmax(0,1fr);gap:16px;align-items:start}
.colL{min-width:0}
.colR{min-width:0}
.colR h2:first-child{margin-top:0}
/* 响应式断点（唯一）：≤1024px 时多栏区收成单列；新断点规则一律用这个值 */
@media (max-width:1024px){.cols{grid-template-columns:1fr}}

.card{background:var(--panel);border:2px solid var(--line);border-radius:var(--radius);
padding:var(--sp-4) var(--sp-5);box-shadow:0 8px 20px var(--glow)}
.maprow2{display:flex;align-items:flex-start;gap:10px;flex-wrap:wrap}
.mapbox{min-width:0;flex:1;display:flex;flex-direction:column;gap:2px}
.mcn2{font-size:17.5px;font-weight:900;color:var(--ink);letter-spacing:-.2px;line-height:1.25;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mcn2.mono{font-family:var(--mono);font-size:15.5px;letter-spacing:-.3px}
.mfn2{font-family:var(--mono);font-size:var(--fs-xs);color:var(--muted);font-weight:700;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mfn2:empty{display:none}
.mtags{flex:none;display:flex;gap:6px;align-items:center;padding-top:4px}
.tag{font-size:var(--fs-xs);font-weight:800;font-family:var(--mono);border-radius:999px;padding:3px 9px;
background:var(--panel2);color:var(--muted);border:2px solid var(--line);flex:none}
.tag.hl{background:var(--soft);color:var(--accent);border-color:var(--softline)}
/* ⑫ 徽章降噪：默认值（0~1 关）弱化成无边浅字，特殊值（≥6 关）才点亮强调色
   —— 保留边框占位（只透明化颜色），状态切换不跳动 */
.tag.lo{background:transparent;border-color:transparent;color:var(--muted);box-shadow:none}
/* ⑰ 交互微反馈：统一 120ms 过渡 + 按下轻缩。放在 aTheme 主题过渡段之前，
   主题切换时的 0.32s 长过渡按文件顺序覆盖这里，两套互不打架 */
.btn,.nav,.wbtn,.libChip,.libSel,.tcard,.tag{
  transition:background-color var(--t) ease,border-color var(--t) ease,
             color var(--t) ease,transform var(--t) ease}
.btn:active,.nav:active,.libChip:active{transform:scale(.96)}
.libRow{transition:background-color var(--t) ease,border-color var(--t) ease}
.sub{color:var(--muted);font-size:var(--fs-xs);margin-top:6px;line-height:1.5}
.srv{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap;margin-top:10px;
padding:8px 12px;background:var(--panel2);border:2px dashed var(--line);border-radius:14px}
.srv .slab{font-size:var(--fs-xs);color:var(--muted);font-weight:700;flex:none}
.srv .sname{font-size:var(--fs-sm);font-weight:800;color:var(--ink2);word-break:break-all}
.srv .smeta{font-size:var(--fs-xs);color:var(--muted);font-family:var(--mono);word-break:break-all}
.hint{font-size:var(--fs-xs);color:var(--ink2);background:var(--panel2);border:2px dashed var(--line);
border-radius:14px;padding:9px 12px;margin-top:12px;line-height:1.6}
/* ⑯ 最近查看的地图：空闲态紧凑小卡（localStorage 本机记录，进服自动隐藏） */
.recent{margin-top:12px;border-top:2px solid var(--panel2);padding-top:10px}
.recent .rcLab{font-size:var(--fs-xs);font-weight:800;color:var(--muted);
letter-spacing:.04em;margin-bottom:7px}
.rcList{display:flex;flex-direction:column;gap:6px}
.rcItem{display:flex;align-items:baseline;gap:8px;min-width:0;text-align:left;cursor:pointer;
border:1.5px solid var(--line);background:var(--panel2);border-radius:10px;padding:6px 10px;
font-family:inherit;color:var(--ink2);transition:border-color var(--t) ease,color var(--t) ease}
.rcItem b{font-size:var(--fs-sm);font-weight:800;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.rcItem span{font-size:var(--fs-xs);color:var(--muted);font-family:var(--mono);flex:none;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rcItem:hover{border-color:var(--softline)}
.rcItem:hover b{color:var(--accent)}
.hint.warn{border-style:solid;border-color:var(--softline);background:var(--soft)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}
.kv{border:2px solid var(--line);border-radius:14px;padding:9px 11px;background:var(--panel2)}
.kv .k{font-size:var(--fs-xs);color:var(--muted);font-weight:700;white-space:nowrap}
.kv .v{font-family:var(--mono);font-size:var(--fs-lg);font-weight:800;margin-top:2px}
.kv.hiA{border-color:var(--accent);background:var(--soft)}
.kv.hiA .k{color:var(--accent)}
.kv.hiA .v{color:var(--accent);font-size:19px}
.kv.hiB{border-color:var(--good)}
.kv.hiB .k{color:var(--good)}
.kv.hiB .v{color:var(--good);font-size:19px}
/* 四宫格分两组：通关奖励 / 战斗伤害（改组标题 + 左侧色条） */
.kvg{display:flex;flex-direction:column;gap:6px}
.kgt{display:flex;align-items:center;gap:7px;font-size:var(--fs-xs);font-weight:800;
letter-spacing:.1em;color:var(--muted);margin:12px 0 0}
.kvg:first-child .kgt{margin-top:12px}
.kgt::after{content:"";flex:1;height:2px;background:var(--line);border-radius:2px}
.kgt .ksub{font-weight:700;letter-spacing:0}
.kvg .grid{margin-top:0}
.kv.lnA{border-left:5px solid var(--accent)}
.kv.lnB{border-left:5px solid var(--good)}
.kv .up{font-size:var(--fs-xs);font-weight:800;color:var(--muted);font-family:inherit;
margin-left:5px;border:1.5px solid var(--line);border-radius:999px;padding:0 5px}
h2{font-size:var(--fs-sm);color:var(--ink2);font-weight:800;letter-spacing:.02em;margin:16px 0 8px}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:var(--fs-sm)}
th{text-align:left;font-size:var(--fs-xs);letter-spacing:.06em;color:var(--muted);font-weight:800;
padding:8px 9px;background:var(--thead);white-space:nowrap}
th:first-child{border-radius:var(--r-sm) 0 0 var(--r-sm)}
th:last-child{border-radius:0 var(--r-sm) var(--r-sm) 0}
td{padding:7px 9px;border-bottom:2px solid var(--panel2);font-family:var(--mono);white-space:nowrap}
/* 服务器表：类名是 srvtab（.srv 已被服务器名胶囊占用），原来写成 table.srv
   一条都没命中 → 固定列宽失效 + 长地图名把表格撑破还被 .main 裁掉 */
table.srvtab{table-layout:fixed}
table.srvtab th,#stb td{overflow:hidden;text-overflow:ellipsis}
/* ⑮ 数值列右对齐 + tabular-nums：位数一多也能对位比大小（在线列有进度条，保持左对齐） */
table.srvtab th:nth-child(3),table.srvtab th:nth-child(4),
table.srvtab td:nth-child(3),table.srvtab td:nth-child(4){
  text-align:right;font-variant-numeric:tabular-nums}
table.numtab th:not(:first-child),table.numtab td:not(:first-child){
  text-align:right;font-variant-numeric:tabular-nums}
/* ⑮ 补网：关卡详情弹窗（stgtab）也是「首列文字 + 4 列数值」，与上面两表同款；
   :not(:first-child) 让特异性高于下方 table.stgtab th{ text-align:left }，右对齐生效 */
table.stgtab th:not(:first-child),table.stgtab td:not(:first-child){
  text-align:right;font-variant-numeric:tabular-nums}
/* 地图库「每关奖励配置」5 列表：窄窗下 nowrap 会把整列挤出 .main 被裁掉 */
table.libStg{table-layout:fixed}
/* 服务器表自带滚动区（v2.14 修）：表头吸顶要吸在「表格自己」的滚动容器里，
   不能挂在 .main 上 —— 否则滚轮一滚是整个页面在走（用户实测反馈）。
   max-height 让表平时全显、超出才出滚动条；overscroll-behavior:contain
   挡住滚动链，在表内滚到头也不会带着整页走。圆角由容器统一裁。 */
.srvWrap{max-height:58vh;overflow-y:auto;overscroll-behavior:contain;
border-radius:var(--r-sm);-webkit-overflow-scrolling:touch}
/* 吸顶表头（v2.14 美化⑤）：长表滚动时列名不跟走。表格原来 overflow:hidden
   会让 sticky 失效，这两张长表放开 overflow，圆角改由四角单元格自己兜 */
table.srvtab,table.libStg{overflow:visible}
table.srvtab thead th,table.libStg thead th{position:sticky;top:0;z-index:var(--z-card);
border-radius:0;box-shadow:0 3px 8px -4px rgba(0,0,0,.18)}
table.srvtab thead th:first-child,table.libStg thead th:first-child{border-radius:var(--r-sm) 0 0 0}
table.srvtab thead th:last-child,table.libStg thead th:last-child{border-radius:0 var(--r-sm) 0 0}
table.srvtab tbody tr:last-child td:first-child,
table.libStg tbody tr:last-child td:first-child{border-radius:0 0 0 var(--r-sm)}
table.srvtab tbody tr:last-child td:last-child,
table.libStg tbody tr:last-child td:last-child{border-radius:0 0 var(--r-sm) 0}
table.libStg th,table.libStg td{white-space:normal;word-break:break-word;overflow:hidden}
table.srvtab th:nth-child(1){width:34%}
table.srvtab th:nth-child(2){width:24%}
table.srvtab th:nth-child(3){width:16%}
table.srvtab th:nth-child(4){width:13%}
/* 在线列原来 10%：内容框比 .online 的 min-width(88px) 还窄，
   「⚠ 官网 N」分歧标记会被表格的 overflow:hidden 裁掉 */
table.srvtab th:nth-child(5){width:13%}
table.srvtab td{white-space:normal;word-break:break-all;font-size:var(--fs-xs);padding:7px 7px}
.mapcn{font-family:var(--disp,inherit);font-size:var(--fs-xs);color:var(--muted);opacity:1;margin-top:1px}
/* 地图名近似命中标记：官方登记名与服务器实名差 1~2 个字符时点出来（title 看详情） */
.apx{cursor:help;font-size:.86em;color:var(--muted);border-bottom:1px dotted var(--softline)}
/* 服务器行可点击 */
tr.srvrow{cursor:pointer;transition:background .12s}
tr.srvrow:hover td{background:var(--soft)}
/* 关卡明细弹窗（外壳跟随主题变量：三处弹窗共用 —— 关卡明细 / 变更明细 / 使用说明） */
.stgov{position:fixed;inset:0;z-index:var(--z-modal);background:rgba(8,6,14,.55);display:flex;align-items:center;justify-content:center}
.stgbox{width:min(520px,86%);max-height:76%;overflow:hidden;display:flex;flex-direction:column;border-radius:14px;
background:var(--panel);color:var(--ink);box-shadow:0 18px 60px var(--glow);border:1px solid var(--line)}
.stghead{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:14px 16px 8px}
.stgtitle{font-weight:700;font-size:var(--fs-md);word-break:break-all}
.stgsub{font-size:var(--fs-xs);color:var(--ink2);margin-top:3px}
.stgx{border:0;background:transparent;color:inherit;font-size:var(--fs-md);cursor:pointer;opacity:.6;padding:2px 6px;border-radius:6px}
.stgx:hover{opacity:1;background:rgba(128,128,128,.15)}
.stgbody{overflow-y:auto;padding:2px 16px 14px}
table.stgtab{width:100%;border-collapse:collapse;font-size:var(--fs-sm)}
table.stgtab th{text-align:left;font-weight:600;opacity:.6;font-size:var(--fs-xs);padding:6px 8px;border-bottom:1px solid var(--softline)}
table.stgtab td{padding:7px 8px;border-bottom:1px dashed var(--line)}
td.stgno{white-space:nowrap;font-weight:600}
tbody tr:last-child td{border-bottom:none}

/* ═══════ 使用说明（弹窗 + 设置页入口） ═══════ */
.rmbox{width:min(680px,92%);max-height:84%}
.rmdoc{font-size:var(--fs-sm);line-height:1.8}
.rmh{display:flex;align-items:center;gap:7px;font-weight:800;font-size:var(--fs-sm);
margin:15px 0 6px;color:#ffd9e8}
.rmh:first-child{margin-top:4px}
.rmh i{width:3px;height:13px;border-radius:2px;background:#f2608d;flex:none;display:block}
.rmdoc ul{margin:0;padding:0;list-style:none}
.rmdoc li{position:relative;padding-left:15px;margin-bottom:4px}
.rmdoc li:before{content:'·';position:absolute;left:5px;color:#f2608d;font-weight:900}
.rmdoc p{margin:0 0 6px}
.rmdoc b{color:#fff}
.rmdoc code{font-family:var(--mono);background:rgba(255,255,255,.09);border-radius:4px;
padding:1px 5px;font-size:var(--fs-xs)}
.rmkv{display:flex;gap:8px;align-items:baseline;font-size:var(--fs-sm);margin-bottom:3px}
.rmkv .rk{flex:none;width:158px;color:#c9c4d4;font-family:var(--mono);font-size:var(--fs-xs)}
.rmtip{margin-top:13px;padding:9px 11px;border-radius:10px;background:rgba(242,96,141,.14);
border:1px solid rgba(242,96,141,.32);font-size:var(--fs-xs);color:#ffd2e2}
.rmend{text-align:center;margin:14px 0 4px;font-size:var(--fs-xs);opacity:.55}
.rmfoot{display:flex;justify-content:center;margin:4px 0 6px}
/* 使用说明弹窗：外壳已随 .stgbox 走主题变量，这里只补强调色 */
#rmOv .rmh{color:var(--accent)}
#rmOv .rmh i{background:var(--accent)}
#rmOv .rmdoc b{color:var(--ink)}
#rmOv .rmdoc li:before{color:var(--accent)}
#rmOv .rmdoc code{background:var(--soft);color:var(--ink2)}
#rmOv .rmkv .rk{color:var(--muted)}
#rmOv .rmtip{background:var(--soft);border-color:var(--softline);color:var(--accent)}
/* 设置页入口卡 */
.rmcard{display:flex;align-items:center;gap:12px;padding:13px 15px;border:2px solid var(--line);
border-radius:14px;background:var(--panel2)}
.rmcard .ic{font-size:22px;flex:none}
.rmcard .rt{min-width:0;flex:1}
.rmcard .rt .t1{font-size:var(--fs-sm);font-weight:800;color:var(--ink)}
.rmcard .rt .t2{font-size:var(--fs-xs);color:var(--muted);margin-top:3px;line-height:1.6}
tbody tr:nth-child(even) td{background:var(--zebra)}
tbody tr.cur td{background:var(--soft);font-weight:800;color:var(--accent)}
/* 服务器表「当前所在」胶囊（高亮只标玩家所在服，不再整列标记） */
.curpill{display:inline-block;margin-left:7px;font-size:var(--fs-xs);font-weight:800;letter-spacing:.5px;
color:var(--accent);background:var(--soft);border:1px solid var(--softline);
border-radius:999px;padding:1px 8px;vertical-align:1px;white-space:nowrap}
/* 官网人数交叉校验：一致打点，不一致标出官网口径 */
.onweb .wdiff{margin-left:0}
.wdiff{display:inline-block;margin-left:4px;font-size:var(--fs-xs);color:var(--muted);
border:1px solid var(--line);border-radius:999px;padding:0 6px;vertical-align:1px;
white-space:nowrap;cursor:help}
/* 在线列：大数字 + 糖果进度条（贴纸手账样板移植），四档配色：满绿/热粉/中橙/空灰 */
.online{min-width:88px;display:inline-block;vertical-align:middle}
.onnum{font-size:17px;font-weight:800;line-height:1;letter-spacing:.3px}
.oncap{font-size:var(--fs-xs);font-weight:700;color:var(--muted);margin-left:2px}
.onbar{margin-top:5px;height:7px;border-radius:999px;background:var(--soft);
border:1px solid var(--softline);overflow:hidden}
.onfill{display:block;height:100%;border-radius:999px}
/* 在线人数四档：跟随主题变量（原来写死亮色，N 主题「空」档的进度条
   是根亮白实心条，看着像有人在线） */
.online.g .onnum{color:var(--good)}
.online.h .onnum{color:var(--hot)}
.online.m .onnum{color:var(--mid)}
.online.l .onnum{color:var(--muted)}
.online.g .onfill{background:linear-gradient(90deg,#5ecb90,var(--good))}
.online.h .onfill{background:linear-gradient(90deg,color-mix(in srgb,var(--hot) 62%,#fff),var(--hot))}
.online.m .onfill{background:linear-gradient(90deg,color-mix(in srgb,var(--mid) 62%,#fff),var(--mid))}
/* 「空」档（在线 <25%）原来用 --line：它在 --soft 轨道上几乎同色（N 主题 1.19:1、
   E 主题 1.07:1），进度条等于看不见。--softline 在五套主题里都比 --line 更深一档 */
.online.l .onfill{background:var(--softline)}

.onweb{margin-top:3px;font-size:var(--fs-xs);line-height:1.4}
.onweb .wdiff{margin-left:0}
/* 弹窗内表格配色（原先写死深色白字，浅色主题下白字打在白底上看不见；已改主题变量） */
.stgtab tr.cur{background:transparent}
.stgtab th{background:transparent;color:var(--ink2)}
.stgtab tbody tr:nth-child(even) td{background:var(--zebra)}
.stgtab tr.cur td{background:var(--soft)!important;font-weight:800;color:var(--accent)}
/* 次要说明文字挂在 <span class="s"> 上（不是 td），所以不能写 td.s 选择器，
   否则中文会继续按 td 的等宽字体渲染 */
.s{font-family:inherit;color:var(--ink2);font-weight:600}
pre{background:var(--panel2);border:2px dashed var(--line);border-radius:14px;padding:10px 12px;
font-family:var(--mono);font-size:var(--fs-xs);color:var(--ink2);white-space:pre-wrap;
word-break:break-all;max-height:120px;overflow:auto;user-select:text}
.foot{margin-top:14px;padding-top:10px;border-top:2px solid var(--line);font-size:var(--fs-xs);
color:var(--muted);line-height:1.7}

/* ─── 视图切换（服务器/主题/设置） ─── */
.view{display:none}
.view.on{display:block}
.view.on .cols{display:grid}
/* ═══════ 地图实体预览（内嵌视图，离开自动卸载 iframe） ═══════ */
.preBar2{display:flex;align-items:center;gap:8px;margin:2px 0 8px;flex-wrap:wrap}
.preBar2 #preCur2{font-weight:600;font-size:var(--fs-sm)}
.preBar2 .preHint{font-size:var(--fs-xs);opacity:.72}
#preFrame{width:100%;height:calc(100vh - 150px);min-height:min(420px,calc(100vh - 200px));border:1.5px solid var(--line,#eee);
  border-radius:14px;background:#211c2b;display:block}

/* ═══════ 动画效果（可在「主题」页逐项开关，记忆在 ui_prefs.json） ═══════ */
.val{display:inline-block;transform-origin:left center}
/* A 视图切换淡入上浮 */
@keyframes viewIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
html.aView .view.on{animation:viewIn .3s cubic-bezier(.2,.75,.3,1) both}
/* B 卡片依次入场 */
@keyframes cardIn{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
html.aStagger .view.on .stag>*{animation:cardIn .4s cubic-bezier(.2,.75,.3,1) both;
  animation-delay:calc(var(--i,0) * 55ms)}
/* C 数值变化脉冲 */
@keyframes flashVal{0%{transform:scale(1)}16%{transform:scale(1.24);color:var(--accent)}100%{transform:scale(1)}}
html.aFlash .val.flash{animation:flashVal .72s cubic-bezier(.2,.75,.3,1)}
/* D 菜单栏收缩动画 */
html.aSide .side{transition:width .32s cubic-bezier(.4,0,.2,1),
  padding .32s cubic-bezier(.4,0,.2,1),opacity .24s ease,border-right-width .32s}
html.aSide .side.hide{display:flex;width:0;padding-left:0;padding-right:0;
  opacity:0;border-right-width:0;overflow:hidden}
html.aSide .side .sr{transition:opacity .22s ease,transform .32s cubic-bezier(.4,0,.2,1)}
html.aSide .side.hide .sr{opacity:0;transform:translateX(-16px)}
html.aSide .fold{transition:transform .3s cubic-bezier(.2,.8,.3,1.4),color .15s,border-color .15s}
html.aSide .fold:hover{transform:scale(1.1)}
@keyframes foldIn{from{opacity:0;transform:translateX(-7px)}to{opacity:1;transform:none}}
html.aSide .wbtn.fold{animation:foldIn .26s cubic-bezier(.2,.75,.3,1) both}
/* E 状态呼吸灯 —— 光晕颜色跟随主题 {--good}，原来写死绿色，
   切到樱花苏打（青）/蜜桃气泡（绿）时和状态点颜色对不上 */
@keyframes breath{
  0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--good) 55%,transparent),0 0 0 3px var(--goodsoft)}
  70%{box-shadow:0 0 0 8px color-mix(in srgb,var(--good) 0%,transparent),0 0 0 3px var(--goodsoft)}
  100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--good) 0%,transparent),0 0 0 3px var(--goodsoft)}}
html.aBreath .pill.on i{animation:breath 2.2s ease-out infinite}
/* F 当前关流光（只作用于关卡表当前关行；服务器表整列都是風雲服、全部带 cur，不参与流光） */
@keyframes sheen{0%{background-position:0% 0}100%{background-position:-200% 0}}
html.aRow #tbody tr.cur td{background:linear-gradient(90deg,var(--soft),var(--softline),var(--soft));
  background-size:200% 100%;animation:sheen 3s linear infinite}
/* G 弹窗缩放淡入 */
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes zoomIn{from{opacity:0;transform:scale(.93) translateY(10px)}to{opacity:1;transform:none}}
/* ⑩ 顶栏页名切换轻挑一下 */
@keyframes tpIn{from{opacity:0;transform:translateX(-3px)}to{opacity:1;transform:none}}
html.aModal .stgov{animation:fadeIn .2s ease both}
html.aModal .stgbox{animation:zoomIn .28s cubic-bezier(.2,.8,.3,1) both}
/* H 主题切换柔和过渡 */
html.aTheme body,html.aTheme .side,html.aTheme .tbar,html.aTheme .card,html.aTheme .kv,
html.aTheme .pill,html.aTheme .btn,html.aTheme th,html.aTheme td,html.aTheme .tcard,
html.aTheme .srv,html.aTheme pre,html.aTheme .nav,html.aTheme .tag,html.aTheme .syncbox,
html.aTheme .cpill,html.aTheme .infoBar,html.aTheme .srvLegend,html.aTheme .libChip,
html.aTheme .libRow,html.aTheme .itag,html.aTheme .dRow,html.aTheme .ovpane>summary,
html.aTheme .themePal,html.aTheme .bgcard,html.aTheme .fxcard,html.aTheme .rmcard,
html.aTheme .syncbox .sub,html.aTheme .curpill,html.aTheme .updBar{
  transition:background-color .32s ease,color .32s ease,border-color .32s ease,box-shadow .32s ease}
/* I 按钮按压回弹 */
html.aPress .btn:active,html.aPress .nav:active,html.aPress .wbtn:not(.wst):active{
  transform:scale(.94);transition:transform .09s ease}
html.aPress .btn,html.aPress .tcard{
  transition:transform .2s cubic-bezier(.2,.8,.3,1.5),border-color .15s,box-shadow .15s}
html.aPress .tcard:active{transform:scale(.97)}
/* J 作者名片虚线环（设置页头像外的旋转虚线框，以前不受总开关控制） */
html.aSpin .au1 .badge .ring{animation:spin 9s linear infinite}
/* 系统级「减少动态效果」：改为**类门控**（html.rm）而非媒体查询一刀切——
   Windows 关掉「动画效果」（新装系统/远程桌面很常见）时 WebView2 会上报 reduce，
   旧写法会把全软件动画静默压成瞬时，用户还以为软件坏了。
   现在默认仍尊重系统（JS 检测后挂 rm 类），但动效卡里给了开关可强制播放（v2.2）。 */
html.rm *,html.rm *::before,html.rm *::after{animation-duration:.01ms !important;
  animation-iteration-count:1 !important;transition-duration:.01ms !important}
/* 动画效果卡片（主题页内） */
.fxcard{background:var(--panel);border:2px solid var(--line);border-radius:var(--radius);
overflow:hidden;box-shadow:0 6px 16px var(--glow)}
.fxgrid{padding:6px 16px 10px;display:grid;
grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:0 22px}
.prow{display:flex;align-items:center;gap:10px;padding:8px 6px;border-radius:9px;
border-bottom:1px dashed var(--panel2)}
.prow:hover{background:var(--panel2)}
.prow .pk{font-size:var(--fs-xs);font-weight:800;color:var(--accent);flex:none;width:15px}
.prow .pt{flex:1;min-width:0}
.prow .pt b{display:block;font-size:var(--fs-xs);font-weight:800;color:var(--ink)}
.prow .pt span{display:block;font-size:var(--fs-xs);color:var(--muted);line-height:1.4}
.sw{width:34px;height:19px;border-radius:999px;background:var(--line);position:relative;
flex:none;cursor:pointer;transition:background .18s;border:none;appearance:none}
.sw::after{content:"";position:absolute;left:2px;top:2px;width:15px;height:15px;border-radius:50%;
background:#fff;transition:transform .18s cubic-bezier(.2,.8,.3,1.4);box-shadow:0 1px 3px rgba(0,0,0,.25)}
.sw.on{background:var(--accent)}
.sw.on::after{transform:translateX(15px)}
.fxfoot{display:flex;gap:8px;padding:11px 16px 13px;border-top:2px solid var(--line);
flex-wrap:wrap;align-items:center}
.fxfoot .btn{font-size:var(--fs-xs);padding:6px 12px}
.fxfoot .fhint{font-size:var(--fs-xs);color:var(--muted);margin-left:auto}
/* 主题选择卡片 */
.themeGrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(196px,1fr));gap:12px}
.tcard{appearance:none;cursor:pointer;font-family:inherit;text-align:left;
border:2px solid var(--line);background:var(--panel);border-radius:var(--radius);
padding:14px 15px;box-shadow:0 6px 16px var(--glow);transition:border-color .15s,transform .15s}
.tcard:hover{transform:translateY(-2px);border-color:var(--softline)}
.tcard.on{border-color:var(--accent);box-shadow:0 0 0 3px var(--soft),0 6px 16px var(--glow)}
.tcard .temo2{font-size:26px;line-height:1}
.tcard .tname{font-size:var(--fs-md);font-weight:800;margin-top:8px;color:var(--ink)}
.tcard .tdot{display:inline-block;width:11px;height:11px;border-radius:50%;margin-left:7px;vertical-align:1px}
.tcard .tstate{font-size:var(--fs-xs);color:var(--muted);margin-top:2px}
/* 设置页：GitHub 同步面板 */
.syncbox{display:flex;align-items:center;gap:12px;flex-wrap:wrap;
border:2px dashed var(--line);border-radius:14px;padding:12px 14px;background:var(--panel2)}
.syncbox .btn{font-size:var(--fs-sm);padding:9px 16px}
/* 同步进度条（v2.14 体验 P1④）：同步 10~30 秒，只有一句话很难判断是不是卡死。
   分段进度由后端 State.sync.pct 提供，前端每秒轮询刷新。 */
.pbar{height:5px;border-radius:4px;background:var(--softline);overflow:hidden;margin-top:10px}
.pbar[hidden]{display:none}
.pbar i{display:block;height:100%;width:0;border-radius:4px;
background:linear-gradient(90deg,var(--accent),var(--good));transition:width .4s ease}

/* ─── 屏幕覆盖配置 ─── */
.ovChecks{display:flex;flex-wrap:wrap;gap:8px}
.ovChecks label{display:flex;align-items:center;gap:7px;font-size:var(--fs-sm);font-weight:700;
color:var(--ink2);border:2px solid var(--line);border-radius:12px;padding:7px 12px;
cursor:pointer;background:var(--panel2)}
.ovChecks label.on{border-color:var(--softline);background:var(--soft);color:var(--accent)}
/* 「需 fys 客户端在运行」分组框：虚线框把这 4 项圈在一起，单独占一行 */
/* 「需 fys 客户端在运行」行：独占一行放勾选区最下方，四个按钮跟在标注后面 */
.ovLiveNote{flex-basis:100%;display:flex;align-items:center;gap:8px;flex-wrap:wrap;
border-top:2px dashed var(--line);padding:8px 2px 0;margin-top:2px}
.ovLiveNote b{font-size:var(--fs-xs);font-weight:800;letter-spacing:.5px;color:var(--accent);white-space:nowrap}
.ovLiveNote span{font-size:var(--fs-xs);color:var(--muted)}
.ovLiveNote label{background:var(--panel)}
.ovLiveNote label.on{background:var(--soft)}
.ovChecks input{accent-color:var(--accent);width:15px;height:15px;cursor:pointer}
.ovRow{display:flex;align-items:center;gap:10px;margin-top:8px;flex-wrap:wrap}
.ovRow .k{font-size:var(--fs-sm);font-weight:700;color:var(--ink2)}
.ovRow input[type=range]{flex:1;min-width:140px;accent-color:var(--accent);cursor:pointer}
.ovRow input[type=color]{width:42px;height:30px;border:2px solid var(--line);border-radius:9px;
background:var(--panel);cursor:pointer;padding:2px}
/* 覆盖预览外框（里面直接摆小窗卡片本体，这里只当衬底） */
.ovPrev{border:2px dashed var(--line);border-radius:14px;padding:13px 14px;text-align:center;
background:var(--panel2);color:var(--ink2);font-weight:800}
/* 「启动了却看不到小窗」排障提示：常驻在启动按钮下方，低调但不能看不见 */
.ovHelp{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:9px;
padding:7px 10px;border:1px dashed var(--line);border-radius:10px;
background:var(--panel2);line-height:1.6;font-size:var(--fs-xs)}
.ovHelp b{color:var(--accent);font-size:var(--fs-xs);white-space:nowrap}
.ovHelp span{color:var(--muted);font-size:var(--fs-xs)}

/* ─── 屏幕覆盖页（2026-11-15 改版）：预览 hero + 页内分栏，替掉「一堆折叠面板」的杂乱感 ─── */
.ovHSub{font-size:var(--fs-xs);color:var(--muted);font-weight:700;margin-left:10px}
.ovHero{display:flex;gap:18px;align-items:stretch;flex-wrap:wrap}
.ovHero .ovPrev{flex:1;min-width:270px;display:flex;align-items:center;justify-content:center}
.ovHeroAct{flex:none;width:min(320px,100%);display:flex;flex-direction:column;gap:7px;justify-content:center}
.ovHeroTop{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.ovCk{display:flex;align-items:center;gap:7px;font-size:var(--fs-sm);font-weight:700;
cursor:pointer;white-space:nowrap}
.ovCk input{accent-color:var(--accent);width:15px;height:15px;cursor:pointer}
.ovTabs{display:flex;gap:7px;margin:15px 0 12px;flex-wrap:wrap}
.ovTab{border:2px solid var(--line);background:var(--panel);color:var(--ink2);font:inherit;
font-size:var(--fs-sm);font-weight:800;padding:8px 17px;border-radius:999px;cursor:pointer;
transition:.15s;box-shadow:2px 2px 0 var(--softline)}
.ovTab:hover{transform:translateY(-1px)}
.ovTab.on{background:var(--accent);border-color:var(--accent);color:#fff}
.ovPane{display:none}
.ovPane.on{display:block;animation:ovFade .18s ease}
@keyframes ovFade{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}
.ovSec{display:flex;align-items:baseline;gap:9px;font-size:var(--fs-md);font-weight:800;
margin:15px 0 8px;flex-wrap:wrap}
.ovSec:first-child{margin-top:0}
.ovSecHint{font-size:var(--fs-xs);color:var(--muted);font-weight:700}
.ovLays{display:grid;grid-template-columns:repeat(auto-fit,minmax(152px,1fr));gap:9px}
.btn.ovl{display:flex;flex-direction:column;align-items:flex-start;gap:3px;text-align:left;
padding:11px 13px;border-radius:14px;min-width:0;line-height:1.35}
.btn.ovl b{font-size:var(--fs-sm)}
.btn.ovl small{font-size:var(--fs-xs);color:var(--muted);font-weight:600}
.btn.ovl.act{background:var(--soft);border-color:var(--softline);box-shadow:0 0 0 3px var(--glow)}

/* ─── 地图库（搜索地图名 / 译名） ─── */
.libBar{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:12px}
.libSearch{display:flex;align-items:center;gap:8px;flex:1;min-width:230px;max-width:470px;
background:var(--panel2);border:2px solid var(--line);border-radius:999px;padding:0 12px}
.libSearch:focus-within{border-color:var(--softline);box-shadow:0 0 0 3px var(--glow)}
.libSearch i{font-style:normal;font-size:var(--fs-md);opacity:.65}
.libSearch input{flex:1;min-width:0;border:none;outline:none;background:transparent;color:var(--ink);
font:12.5px/1 inherit;font-family:inherit;padding:9px 0}
.libSearch input::placeholder{color:var(--muted)}
.libClr{border:none;background:transparent;color:var(--muted);font-size:var(--fs-lg);line-height:1;
cursor:pointer;padding:1px 5px;border-radius:50%}
.libClr:hover{color:var(--accent);background:var(--soft)}
/* 分类行（可多选）：独立一行，组间用细分隔条 */
.libCats{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:-3px 0 13px;
padding:8px 10px;border:2px dashed var(--line);border-radius:14px;background:var(--panel2)}
.libCatLab{font-size:var(--fs-xs);font-weight:800;color:var(--muted);letter-spacing:.02em;margin-right:2px}
.libSep{width:2px;height:15px;border-radius:2px;background:var(--line);margin:0 2px;flex:none}
/* 提示挪到行首做成小胶囊：窄窗不再被 margin-left:auto 甩到第二行最右 */
.libHint{font-size:var(--fs-xs);color:var(--muted);white-space:nowrap;flex:none;font-weight:700;
border:2px solid var(--line);border-radius:999px;padding:2px 8px;background:var(--panel)}
/* 其余分类从「全部」之后整行起排，竖线不跨行 */
/* ⑭ 分类胶囊横滑：窄窗不再折成三四行占半屏，单行左右滑；触控板/手机原生横滑，
   鼠标滚轮在胶囊区上下滚也能平移（见 ui_js 滚轮转发） */
.rowline{display:flex;align-items:center;gap:6px;flex-wrap:nowrap;flex-basis:100%;
overflow-x:auto;padding-bottom:3px;scrollbar-width:thin}
.rowline::-webkit-scrollbar{height:6px}
.rowline::-webkit-scrollbar-thumb{background:var(--line);border-radius:6px}
.rowline .libChip{flex:none}
.libChip{border:2px solid var(--line);background:var(--panel);color:var(--ink2);border-radius:999px;
padding:var(--sp-1) 11px;font:11.5px/1.4 inherit;font-family:inherit;font-weight:700;cursor:pointer}
.libChip i{font-style:normal;font-family:var(--mono);font-size:var(--fs-xs);font-weight:700;
color:var(--muted);margin-left:5px}
.libChip:hover{border-color:var(--softline)}
.libChip.on{background:var(--soft);border-color:var(--softline);color:var(--accent)}
.libChip.on i{color:var(--accent);opacity:.8}
.libSel{border:2px solid var(--line);background:var(--panel2);color:var(--ink2);border-radius:999px;
padding:4px 9px;font:11.5px/1.4 inherit;font-family:inherit;font-weight:700;cursor:pointer;outline:none}
.libSel:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.libCnt{font-size:var(--fs-xs);color:var(--muted);margin-left:auto;white-space:nowrap}
.libSplit{display:grid;grid-template-columns:322px minmax(0,1fr);gap:14px;align-items:start}
@media (max-width:1024px){.libSplit{grid-template-columns:1fr}}
.libList{max-height:66vh;overflow-y:auto;border:2px solid var(--line);border-radius:var(--radius);
background:var(--panel2);padding:6px}
.libList::-webkit-scrollbar{width:9px}
.libList::-webkit-scrollbar-thumb{background:var(--line);border-radius:9px}
.libRow{display:flex;align-items:center;gap:8px;padding:7px 9px;border-radius:var(--r-sm);
cursor:pointer;border:2px solid transparent;position:relative;overflow:hidden;
/* ⑤ 渲染跳过（v2.15 性能⑤）：视口外的行不布局不绘制，700+ 行列表首屏明显变快；
   contain-intrinsic-size 给个行的典型高度，滚动条不会明显跳动 */
content-visibility:auto;contain-intrinsic-size:auto 56px}
.libRow:hover{background:var(--soft)}
.libRow.on{background:var(--soft);border-color:var(--softline)}
/* 地图封面底图（v2.3）：cover\<地图名>.jpg 铺成行底纹；左实右透，文字与徽标始终压在上层。
   这张图抓不到的（图库未收录）就只有渐变，不会留破图。
   v2.14 美化⑦：从 div 背景图改成 <img loading="lazy"> —— 800 张卡一次全渲染，
   背景图没法懒加载，视口外的几百张都在白白解码占内存；img 原生懒加载，滚到才取 */
.libRow .libBg{position:absolute;inset:0;z-index:0;pointer-events:none;opacity:.34;
width:100%;height:100%;object-fit:cover;object-position:left center;
/* 浅色主题文字是深色 → 底图提亮褪色当水印；夜幕主题文字是浅色 → 底图压暗 */
filter:saturate(.65) brightness(1.6) contrast(.9);
-webkit-mask-image:linear-gradient(90deg,#000 0 52%,transparent);
mask-image:linear-gradient(90deg,#000 0 52%,transparent)}
html[data-theme="N"] .libRow .libBg{filter:saturate(.6) brightness(.5) contrast(.95)}
.libRow:hover .libBg{opacity:.44}
.libRow.on .libBg{opacity:.5}
.libRow .lm,.libRow .lb{position:relative;z-index:1}
.libRow .lm{flex:1;min-width:0}
.libRow .lc{font-size:var(--fs-sm);font-weight:800;color:var(--ink);white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.libRow.on .lc{color:var(--accent)}
.libRow .lf{font-family:var(--mono);font-size:var(--fs-xs);color:var(--muted);white-space:nowrap;
overflow:hidden;text-overflow:ellipsis;margin-top:1px}
.libRow .lb{flex:none;display:flex;gap:4px;align-items:center}
/* 收藏星标：未收藏淡显（悬停行变清楚），已收藏常亮金色；点击切换不触发行选中 */
.libStar{border:none;background:transparent;color:var(--muted);opacity:.3;font-size:var(--fs-md);
line-height:1;cursor:pointer;padding:2px 3px;border-radius:7px;flex:none}
.libRow:hover .libStar{opacity:.65}
.libStar:hover{opacity:1;background:var(--soft)}
.libStar.on{color:#f5a623;opacity:1}
/* 详情页收藏按钮（点亮后金色描边） */
.libFavD.on{border-color:#f5a623;color:#a06b06;background:#fff7e8;
  box-shadow:0 0 0 3px var(--soft)}
/* 地图库「地图实体预览」按钮：此前只有类名没有任何规则，形同虚设 */
.btn.libPv{background:var(--soft);border-color:var(--softline);color:var(--accent)}
/* 预览壳里没有这张图的实体档案（EXG 补充图 / 刚上线还没抓的新图）：
   按钮转成「说明态」——文案直说，点了也会给一句解释，不再静默打开别的图 */
.btn.libPv.off{background:var(--panel);border-color:var(--line);color:var(--muted)}
html[data-theme="N"] .btn.libPv.off{background:#2a2430;border-color:#3d3644;color:#9c93a3}
html[data-theme="N"] .libFavD.on{background:#3b2f14;color:#ffc078;border-color:#8a6a2f;
  box-shadow:0 0 0 3px var(--soft)}
/* 行尾小徽标：🔑需管理员 / 🎲随机尸变 / 🕒限定时段 / 🌐全天（悬停出完整说明） */
.itag{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;
border-radius:8px;border:2px solid var(--line);background:var(--panel);font-size:var(--fs-xs);
cursor:help;flex:none}
.itag.k{border-color:#ffd9a3;background:#fff8ec}
.itag.t{border-color:#cfe3f7;background:#eef6ff}
.itag.d{border-color:#ffe0b8;background:#fff8ec}
html[data-theme="N"] .itag.k{background:#33280f;border-color:#5a4520}
html[data-theme="N"] .itag.t{background:#16232f;border-color:#2b4358}
html[data-theme="N"] .itag.d{background:#33280f;border-color:#5a4520}
/* 空态组件（v2.14 美化⑥）：图标 + 主文案 + 说明 + 可选动作按钮，全站统一 */
.libEmpty,.ulEmpty{padding:26px 12px;text-align:center;color:var(--muted);font-size:var(--fs-sm);line-height:1.7}
.libEmpty .eIc,.ulEmpty .eIc{font-size:26px;line-height:1.2;margin-bottom:4px;filter:saturate(.85)}
.libEmpty .eT,.ulEmpty .eT{display:block;color:var(--ink2);font-weight:800}
.libEmpty .eS,.ulEmpty .eS{font-size:var(--fs-xs);margin-top:3px}
.libEmpty .eBtn,.ulEmpty .eBtn{margin-top:10px;font-size:var(--fs-sm);font-weight:700;color:#fff;
background:var(--accent);border:none;border-radius:999px;padding:6px 16px;cursor:pointer;font-family:inherit}
.libEmpty .eBtn:hover,.ulEmpty .eBtn:hover{filter:brightness(1.07)}
.libEmpty b{color:var(--ink2)}
/* 索引加载等待态：spinner + 已等待秒数（长加载要可感知） */
.libWaitBox{padding:32px 12px;text-align:center}
.libSpin{display:inline-block;width:22px;height:22px;border-radius:50%;
border:3px solid var(--line);border-top-color:var(--accent);
animation:libRot .9s linear infinite;margin-bottom:10px}
@keyframes libRot{to{transform:rotate(360deg)}}
.libWaitTxt{font-size:var(--fs-md);color:var(--ink2)}
.libWaitSub{margin-top:4px;font-size:var(--fs-xs);color:var(--muted);font-variant-numeric:tabular-nums}
.libWaitHint{margin-top:8px;font-size:var(--fs-xs);color:var(--muted)}
.libRow .lc mark,.libRow .lf mark{font-weight:800}
/* 从「当前地图」卡片跳进地图库时，目标行闪一下内描边，方便一眼找到（纯追加） */
@keyframes libFlash{0%,55%{box-shadow:inset 0 0 0 2px var(--accent)}100%{box-shadow:inset 0 0 0 2px transparent}}
.libRow.flash{animation:libFlash 1.5s ease-out 2}
mark.mkw{background:var(--softline);color:var(--ink);border-radius:3px;padding:0 1px}
.libDetail .card{margin-bottom:12px}
.libDetail .card h2{margin-top:0}
.libHead{display:flex;align-items:flex-start;gap:14px;flex-wrap:wrap}
/* 详情头卡封面底图（v2.12）：/cover/<名>.jpg 整幅铺底，取不到（404）层为空、卡片原样。
   浅色主题提亮褪色当水印、夜幕压暗 —— 与列表行 .libBg 同一套处理 */
.card.libCv{position:relative;overflow:hidden}
.card.libCv::before{content:'';position:absolute;inset:0;z-index:0;pointer-events:none;
background-image:var(--cv);background-size:cover;background-position:center 32%;opacity:.4;
filter:saturate(.7) brightness(1.5) contrast(.9);
-webkit-mask-image:linear-gradient(180deg,#000 0 58%,transparent 97%);
mask-image:linear-gradient(180deg,#000 0 58%,transparent 97%)}
html[data-theme="N"] .card.libCv::before{filter:saturate(.6) brightness(.5) contrast(.95);opacity:.55}
.card.libCv>*{position:relative;z-index:1}
/* v2.14 缺陷修复：封面底图只有 .4 不透明度，而背景方案（默认「云朵小铺」）会给所有
   .card 注入「白纱 + 吉祥物水印」两层背景（!important），水印会透过封面一起显形，
   封面 × 水印叠成重影（尤其卡片右半，水印本来就钉在那里）。
   带封面底图的头卡（.cvOn）把水印层摘掉——同为 !important 时按特异性取胜
   （.card.libCv.cvOn = 0,3,0 > bgCSS 注入的 .card = 0,1,0）；
   没有封面的图不加 .cvOn，水印照常显示，行为不变。 */
.card.libCv.cvOn{background-image:none!important}
html[data-theme="N"] .card.libCv.cvOn{background-image:none!important}
.libHead .big{flex:1;min-width:190px}
.libHead .cn{font-size:21px;font-weight:800;color:var(--accent);line-height:1.25;word-break:break-all}
.libHead .fn{font-family:var(--mono);font-size:var(--fs-xs);color:var(--ink2);margin-top:3px;word-break:break-all}
.libBadges{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.libBdg{display:flex;align-items:baseline;gap:5px;background:var(--panel2);border:2px solid var(--line);
border-radius:var(--r-sm);padding:4px 10px}
.libBdg b{font-size:var(--fs-md);font-weight:800;color:var(--ink)}
.libBdg span{font-size:var(--fs-xs);color:var(--muted)}
.libKb{display:flex;flex-direction:column;align-items:center;gap:1px;background:var(--soft);
border:2px solid var(--softline);border-radius:var(--r-sm);padding:8px 14px;min-width:86px}
.libKb b{font-size:20px;font-weight:800;color:var(--accent);line-height:1}
.libKb span{font-size:var(--fs-xs);color:var(--ink2);font-weight:700}
.libGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px}
/* ⑬ 参数小卡轻量化 + 孤行修复：细实线浅边、去贴纸投影、收小圆角；
   min 144px 在中等窗宽会挤出「5+1 孤行」，118px 让 6 张参数卡常态一行放下 */
.libGrid .kv{border:1.5px solid var(--line);border-radius:12px;box-shadow:none;padding:8px 10px}
.libGrid .kv .v.yes{color:var(--good)}
.libGrid .kv .v.no{color:var(--muted)}
.libNote{font-size:var(--fs-xs);color:var(--muted);line-height:1.7;margin-top:9px}
.libNote b{color:var(--ink2)}
.libRbar{height:5px;border-radius:5px;background:var(--line);overflow:hidden;margin-top:4px;min-width:40px}
.libRbar i{display:block;height:100%;background:var(--accent);border-radius:5px}
.libDetail table td:not(:first-child),.libDetail table th:not(:first-child){text-align:right}
.libDetail td .u{font-size:var(--fs-xs);color:var(--muted);font-weight:700;font-family:inherit;margin-left:3px}
.libWarn{background:var(--soft);border:2px dashed var(--softline);border-radius:var(--r-sm);
padding:13px;font-size:var(--fs-sm);color:var(--ink2);line-height:1.7}

/* ═══════ ⑦ 地图库：随机尸变（官方 ze_infect_sort_by_immunity） ═══════ */
.libRnd{display:inline-flex;align-items:center;gap:5px;font-size:var(--fs-xs);font-weight:800;
font-family:inherit;border-radius:999px;padding:2px 10px;vertical-align:3px;margin-left:6px;
background:#fff0d8;color:#c0620a;border:2px solid #ffd9a3;white-space:nowrap}
html[data-theme="N"] .libRnd{background:#3a2b18;color:#ffc078;border-color:#5a4022}
.libRnd i{width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.85;flex:none}
/* EXG 补充分类：详情页胶囊徽标 + 列表行图标（与随机尸变同款，配色偏紫以示区分） */
.libExg{display:inline-flex;align-items:center;gap:5px;font-size:var(--fs-xs);font-weight:800;
font-family:inherit;border-radius:999px;padding:2px 10px;vertical-align:3px;margin-left:6px;
background:#ece9ff;color:#5b46c8;border:2px solid #d6cffb;white-space:nowrap}
html[data-theme="N"] .libExg{background:#211d38;color:#b8aaff;border-color:#3a3260}
.itag.e{border-color:#d6cffb;background:#f2efff}
html[data-theme="N"] .itag.e{background:#211d38;border-color:#3a3260}
/* 文字版标签（EXG）：.itag 是定宽 22px 的图标格，三个字母塞不进去，
   这里放开宽度并按内容撑开，否则「EXG」会被裁成「EX」甚至溢出。 */
.itag.txt{width:auto;padding:0 6px;font-family:var(--mono);font-size:var(--fs-xs);
font-weight:800;letter-spacing:.02em;color:#5b46c8}
html[data-theme="N"] .itag.txt{color:#b8aaff}
.libInfect{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:9px;
padding:9px 12px;border-radius:var(--r-sm);border:2px dashed var(--line);background:var(--panel2)}
.libInfect.on{border-color:#ffd9a3;background:#fff8ec}
html[data-theme="N"] .libInfect.on{border-color:#5a4022;background:#2a2119}

/* ═══════ ① 数值单位小字（点 / 颗 / 万） ═══════ */
td .u{font-size:var(--fs-xs);color:var(--muted);font-weight:700;font-family:inherit;margin-left:3px}
.kv .v .u{font-size:var(--fs-xs);margin-left:2px}

/* ═══════ ③ 主题卡：色板 + 迷你缩略 ═══════ */
.tpal{display:flex;gap:5px;margin-top:9px}
.tpal i{width:100%;height:14px;border-radius:5px;border:1px solid rgba(128,128,128,.18)}
.tmini{margin-top:8px;border:2px solid var(--line);border-radius:10px;overflow:hidden;
background:var(--tmini-bg);border-color:var(--tmini-line)}
.tmini .tb{height:8px;background:var(--tmini-side)}
.tmini .tbd{padding:6px 6px 7px}
.tmini .tc{height:20px;border-radius:6px;background:var(--tmini-panel);
border:1.5px solid var(--tmini-line);margin-bottom:5px;position:relative}
.tmini .tc::after{content:"";position:absolute;left:5px;top:6px;width:20px;height:4px;
border-radius:3px;background:var(--tmini-accent)}
.tmini .tr{height:5px;border-radius:3px;background:var(--tmini-line);margin-bottom:4px}
.tmini .tr:last-child{width:62%;margin-bottom:0}
/* 主题页底部「当前主题配色说明」 */
.palgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));gap:8px}
.pc{display:flex;align-items:center;gap:8px;border:2px solid var(--line);border-radius:12px;
padding:6px 9px;background:var(--panel2)}
.pc i{width:20px;height:20px;border-radius:7px;flex:none;border:1px solid rgba(128,128,128,.2)}
.pc b{font-size:var(--fs-xs);display:block;color:var(--ink2);font-weight:800}
.pc span{font-family:var(--mono);font-size:var(--fs-xs);color:var(--muted)}
.themePal{margin-top:14px;background:var(--panel);border:3px solid var(--line);border-radius:22px;
padding:15px 17px;box-shadow:4px 5px 0 var(--softline)}

/* ═══════ ④ 主题页「界面背景」卡（可切换，素材见 bg_assets.py） ═══════ */
.bgcard{margin-top:14px;background:var(--panel);border:3px solid var(--line);border-radius:22px;
padding:15px 17px;box-shadow:4px 5px 0 var(--softline)}
.bggrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(152px,1fr));gap:11px}
.bgopt{position:relative;border:3px solid var(--line);border-radius:16px;overflow:hidden;
background:var(--panel2);cursor:pointer;padding:0;text-align:left;
font-family:inherit;transition:transform .16s,border-color .16s}
.bgopt:hover{transform:translateY(-3px)}
.bgopt.on{border-color:var(--accent);box-shadow:0 0 0 3px var(--soft)}
.bgopt .thumb{display:block;height:74px;background-size:cover;background-position:center;
background-color:var(--soft)}
.bgopt .thumb.tile{background-size:120px auto;background-repeat:repeat}
.bgopt .nm{display:block;padding:7px 9px 2px;font-size:var(--fs-sm);font-weight:800;color:var(--ink)}
.bgopt .ds{display:block;padding:0 9px 8px;font-size:var(--fs-xs);color:var(--muted);line-height:1.5}
.bgopt .em{position:absolute;right:7px;top:6px;font-size:var(--fs-lg);
filter:drop-shadow(0 1px 2px rgba(0,0,0,.3))}
.bgopt .ck{position:absolute;left:7px;top:6px;font-size:var(--fs-xs);font-weight:800;color:#fff;
background:var(--accent);border-radius:999px;padding:2px 8px;display:none}
.bgopt.on .ck{display:block}
/* v2.15 自定义背景卡的「更换图片」小按钮：卡右下角，点击不触发整卡应用 */
.bgopt .bgchg{position:absolute;right:7px;bottom:7px;border:1.5px solid var(--softline);
background:var(--panel);color:var(--ink2);border-radius:999px;font:700 11px/1 inherit;
font-family:inherit;padding:5px 9px;cursor:pointer;transition:background-color var(--t) ease}
.bgopt .bgchg:hover{background:var(--soft);color:var(--accent)}
.bgfoot{margin-top:11px}
.bgfoot .fhint{font-size:var(--fs-xs);color:var(--muted);line-height:1.7}
/* 侧栏贴纸（可自选，applyBG 挂载）+ 贴纸选择器 */
/* 三款贴纸长宽比不同：用固定高度对齐底部，宽度自适应，避免换贴纸时高度跳动 */
#cuteSticker{position:fixed;left:10px;bottom:8px;height:126px;width:auto;max-width:172px;
z-index:var(--z-stick);pointer-events:none;object-fit:contain;
transform:rotate(-5deg);filter:drop-shadow(0 10px 16px rgba(120,160,220,.42))}
.stkrow{display:flex;gap:9px;flex-wrap:wrap;margin-top:9px}
.stkopt{display:flex;align-items:center;gap:8px;border:3px solid var(--line);border-radius:15px;
background:var(--panel2);cursor:pointer;padding:5px 11px 5px 5px;font-family:inherit;
transition:transform .16s,border-color .16s}
.stkopt:hover{transform:translateY(-2px)}
.stkopt.on{border-color:var(--accent);box-shadow:0 0 0 3px var(--soft)}
.stkopt .av{width:42px;height:42px;flex:0 0 42px;border-radius:13px;background-color:var(--panel);
background-size:contain;background-repeat:no-repeat;background-position:center}
.stkopt .nm{font-size:var(--fs-sm);font-weight:800;color:var(--ink);text-align:left}
.stkopt .nm i{display:block;font-style:normal;font-weight:700;font-size:var(--fs-xs);color:var(--muted)}
.bgsep{margin:14px 0 0;padding-top:13px;border-top:2px dashed var(--line)}
.bgsep b{font-size:var(--fs-sm);color:var(--ink2)}

.heroBanner{position:relative;margin:0 0 14px;border-radius:30px;overflow:hidden;
border:4px solid var(--panel);box-shadow:0 16px 34px var(--glow)}
.heroBanner img{display:block;width:100%;height:170px;object-fit:cover;object-position:center 64%}
.heroBanner .tt{position:absolute;left:0;right:0;bottom:0;padding:30px 22px 14px;
background:linear-gradient(transparent,rgba(255,255,255,.94));font-weight:900;font-size:19px;
color:#54658c;letter-spacing:.03em;text-shadow:0 1px 0 #fff}
.heroBanner .tt small{display:block;font-weight:700;font-size:var(--fs-sm);color:#8fa0bf;
margin-top:5px;letter-spacing:0}
.heroBanner .bd{position:absolute;right:14px;top:12px;background:rgba(255,255,255,.92);
border-radius:999px;padding:5px 13px;font-size:var(--fs-sm);font-weight:800;color:#6d7fa8;
box-shadow:0 4px 12px rgba(146,186,236,.3)}
.libBanner{position:relative;margin:0 0 12px;border-radius:26px;overflow:hidden;
border:4px solid var(--panel);box-shadow:0 14px 30px var(--glow)}
.libBanner img{display:block;width:100%;height:132px;object-fit:cover;object-position:center 54%}
.libBanner .tt{position:absolute;left:0;right:0;bottom:0;padding:24px 20px 11px;
background:linear-gradient(transparent,rgba(255,255,255,.94));font-weight:900;font-size:var(--fs-lg);
color:#54658c;text-shadow:0 1px 0 #fff}
.libBanner .tt small{font-weight:700;font-size:var(--fs-sm);color:#8fa0bf;margin-left:8px}
.setBanner{display:flex;gap:16px;align-items:center;background:var(--panel);
border:4px solid var(--panel);border-radius:28px;padding:12px 18px;margin:0 0 14px;
box-shadow:0 14px 30px var(--glow)}
.setBanner img{width:158px;height:106px;object-fit:cover;object-position:center 30%;
border-radius:20px;flex:0 0 158px}
.setBanner .st{font-weight:900;font-size:16.5px;color:#54658c}
.setBanner .st small{display:block;font-weight:700;font-size:var(--fs-sm);color:#8fa0bf;
margin-top:6px;line-height:1.6}
/* 暗色主题：插画压暗 + 横幅文案转浅色，避免亮图刺眼 */
html[data-theme="N"] .heroBanner img,
html[data-theme="N"] .libBanner img,
html[data-theme="N"] .setBanner img{filter:brightness(.66) saturate(.86)}
html[data-theme="N"] .heroBanner .tt,
html[data-theme="N"] .libBanner .tt{background:linear-gradient(transparent,rgba(30,29,36,.94));
color:#e6e0ec;text-shadow:none}
html[data-theme="N"] .heroBanner .bd{background:rgba(38,36,46,.92);color:#cfc8d8}
html[data-theme="N"] .heroBanner .tt small,
html[data-theme="N"] .libBanner .tt small{color:#a49db0}
html[data-theme="N"] .setBanner .st{color:#e6e0ec}
html[data-theme="N"] .setBanner .st small{color:#a49db0}

/* ═══════ ④ 设置页「关于」卡 ═══════ */
/* 广播原文空态：没内容是给指引 + 入口，不再是一对括号 */
.rawEmpty{border:2px dashed var(--line);border-radius:14px;padding:22px 16px;text-align:center;
background:var(--panel2)}
.rawEmpty .ic{font-size:26px;display:block;margin-bottom:6px;opacity:.75}
.rawEmpty .t1{font-size:var(--fs-sm);font-weight:800;color:var(--ink2)}
.rawEmpty .t2{font-size:var(--fs-xs);color:var(--ink2);margin-top:5px;line-height:1.7}
.rawEmpty .acts{margin-top:11px;display:flex;gap:7px;justify-content:center;flex-wrap:wrap}
.rawEmpty .fn{font-size:var(--fs-xs);color:var(--muted);margin-top:10px;font-family:var(--mono);
word-break:break-all}
.aboutRow{display:flex;align-items:center;gap:10px;padding:8px 2px;
border-bottom:2px dashed var(--panel2)}
.aboutRow:last-child{border-bottom:none}
.aboutRow .al{flex:none;width:88px;font-size:var(--fs-xs);font-weight:700;color:var(--muted)}
/* 路径类一行到底 + 省略号（长路径不再折成两三行把「打开」按钮挤歪），全路径在 title 里 */
.aboutRow .av{flex:1;min-width:0;font-family:var(--mono);font-size:var(--fs-xs);color:var(--ink2);
word-break:break-all;user-select:text}
.aboutRow .av.ell{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;word-break:normal;
cursor:help}
.aboutRow .av.human{font-family:inherit;font-weight:700}
.aboutRow .acts{flex:none;display:flex;gap:6px}
/* ⑪ 运行日志体积胶囊（超 512KB 自动归档时变暖色提示） */
.aboutRow .lsz{flex:none;font-size:var(--fs-xs);font-weight:800;color:var(--muted);font-family:var(--mono);
padding:2px 7px;border-radius:9px;background:var(--panel2);white-space:nowrap}
.aboutRow .lsz:empty{display:none}
.aboutRow .lsz.big{color:#c0620a;background:#fff0d8}
html[data-theme="N"] .aboutRow .lsz.big{color:#ffc078;background:#3a2b18}
/* 设置页「更新日志」卡（about.changelog 渲染，见 fillAbout）——手风琴式：
   版本行点击展开/收起，默认只展开当前版本，整卡不再一屏占满 */
.clgvw{border-bottom:1px dashed var(--line)}
.clgvw:last-child{border-bottom:0}
.clgv{display:flex;align-items:baseline;gap:8px;padding:8px 2px;cursor:pointer;user-select:none}
.clgv:first-child{padding-top:2px}
.clgv b{font-size:var(--fs-sm);color:var(--accent)}
.clgv .clgd{font-size:var(--fs-xs);color:var(--muted);font-family:var(--mono)}
.clgv .clgct{font-size:var(--fs-xs);color:var(--muted);font-family:var(--mono)}
.clgv .clglx{margin-left:auto;font-size:var(--fs-xs);font-weight:800;color:var(--muted);white-space:nowrap}
.clgv .clgarr{flex:none;align-self:center;font-size:var(--fs-xs);color:var(--muted);transition:transform .18s}
.clgvw.open .clgarr{transform:rotate(90deg)}
/* 历史版本折叠开关：默认只显示当前版本，历史收在这里 */
.clgmore{padding:9px 2px 3px;font-size:var(--fs-xs);font-weight:800;color:var(--accent);
cursor:pointer;user-select:none;text-align:center}
.clgmore:hover{text-decoration:underline}
.clgv:hover b{filter:brightness(1.15)}
.clg{display:none;padding:0 2px 8px}
.clgvw.open .clg{display:block}
.clg li{font-size:var(--fs-xs);line-height:1.6;color:var(--ink2);margin:0 0 2px 2px}
.clg li::marker{color:var(--accent)}
.clgEmpty{font-size:var(--fs-xs);color:var(--muted);padding:6px 2px}
/* 分组式日志（v2.2 起）：新增 / 优化 / 修复 / 移除 小标题 */
.clgT{font-size:var(--fs-xs);font-weight:800;letter-spacing:.5px;margin:7px 0 3px;color:var(--ink2)}
.clgT:first-child{margin-top:2px}
.clgT b{display:inline-block;padding:1px 8px;border-radius:99px;color:#fff;
background:var(--accent);font-size:var(--fs-xs);margin-right:6px}
.clgT.t-fix b{background:#d98841}
.clgT.t-imp b{background:#4a9ad4}
.clgT.t-rem b{background:#9a8fa8}
html[data-theme="N"] .clgT{color:var(--ink)}
/* 一键更新横条（有新版才显示，插在更新日志上方） */
.updBar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.card.updBar{background:#eaf3de;border-color:#3b6d11;color:#27500a}
.updBar b{font-size:var(--fs-md)}
.updBar small{flex:1;min-width:120px;font-size:var(--fs-xs);opacity:.8;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.updBar .btn{min-width:0;padding:5px 14px;font-size:var(--fs-sm)}
html[data-theme="N"] .updBar{background:#1c2a14;border-color:#4c7a20;color:#c0dd97}
/* 主按钮（弹窗「立即更新」用）：accent 实底 */
.btn.pri{background:var(--accent);border-color:var(--accent);color:#fff}
.btn.pri:hover{color:#fff;filter:brightness(1.08)}
/* 启动时的更新提示弹窗：半透明遮罩 + 居中卡片 */
#updModal{position:fixed;inset:0;z-index:var(--z-modal);background:rgba(20,16,30,.45);
display:flex;align-items:center;justify-content:center;animation:fadeIn .18s ease}
.updM{width:min(410px,86vw);background:var(--panel);border:2px solid var(--softline);
border-radius:16px;padding:18px 20px 16px;box-shadow:0 18px 50px rgba(20,15,40,.35)}
.updMH{font-size:var(--fs-lg);font-weight:800;color:var(--ink)}
.updMH small{font-weight:700;color:var(--muted);margin-left:6px}
.updML{margin:11px 0 2px;padding-left:18px;color:var(--ink2);font-size:var(--fs-sm);line-height:1.7}
.updML li{margin-top:4px}
.updML .more{color:var(--muted)}
.updMF{display:flex;justify-content:flex-end;gap:8px;margin-top:15px}
html[data-theme="N"] .updM{box-shadow:0 18px 50px rgba(0,0,0,.6)}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}

/* ── 上游数据更新提醒（GitHub 变更检测，v2.2） ── */
.updB{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:8px 0 2px;
  background:var(--panel);border:2px solid var(--accent);border-radius:14px;
  padding:10px 14px;box-shadow:0 4px 16px rgba(0,0,0,.06);
  animation:zoomIn .3s cubic-bezier(.2,.8,.3,1) both}
.updB .ic{font-size:20px;flex:none}
.updB .tt{font-weight:800;font-size:var(--fs-md);line-height:1.35;color:var(--ink)}
.updB .tt small{display:block;font-weight:600;color:var(--muted);font-size:var(--fs-xs)}
.updB .stat{display:flex;gap:6px;flex-wrap:wrap}
.updB .stat span{font-size:var(--fs-xs);font-weight:700;padding:2px 9px;border-radius:99px;
  background:var(--panel2);border:1px solid var(--line);color:var(--ink2)}
.updB .stat .plus{color:#2e7d4f;border-color:#bfe3cd;background:#effaf3}
.updB .stat .edit{color:#b26a1a;border-color:#f3ddb8;background:#fdf6ea}
.updB .stat .minus{color:#b04a5a;border-color:#f0c7ce;background:#fdf0f2}
.updB .btn{min-width:0;padding:5px 13px;font-size:var(--fs-sm)}
/* 变更明细弹窗（复用 stgov 遮罩） */
.dGrp{margin:14px 0 4px}
.dGt{display:flex;align-items:center;gap:8px;margin-bottom:7px;font-weight:800;font-size:var(--fs-sm)}
.dGt .n{font-size:var(--fs-xs);color:#fff;border-radius:99px;padding:1px 8px;font-weight:800}
/* 计数徽章（改名 tbadge）：原先叫 .badge，与作者名片的 .au1 .badge 撞车，
   padding:2px 9px 会泄漏进头像容器，把头像挤右下 9px/2px，虚线环看着就歪（实测根因） */
.tbadge{font-size:var(--fs-xs);font-weight:800;color:#fff;border-radius:99px;padding:2px 9px;flex:none}
.b-new{background:var(--c-new)}.b-edit{background:var(--c-edit)}.b-stage{background:var(--c-stage)}
.b-zombie{background:var(--c-zombie)}.b-param{background:var(--c-param)}.b-del{background:var(--c-del)}
.b-trans{background:#7a8fd4}.b-boss{background:#a9784a}
html[data-theme="N"] .b-trans{background:#98a9e8}html[data-theme="N"] .b-boss{background:#c39468}

/* ── 地图库详情「地图参数」卡（v2.9）── */
.cfgSub{font-size:var(--fs-xs);font-weight:600;color:var(--muted);margin-left:7px}
.cfgT{font-size:var(--fs-xs);font-weight:800;color:var(--muted);margin:11px 0 3px}
.cfgCols{columns:2;column-gap:22px}
@media(max-width:1024px){.cfgCols{columns:1}}
.cfgBlk{break-inside:avoid}
.cfgRow{display:flex;align-items:baseline;gap:8px;padding:3px 0;
  border-bottom:1px dashed var(--line)}
.cfgRow .n{flex:1;font-size:var(--fs-sm);color:var(--ink2)}
.cfgRow .v{font-weight:800;font-size:var(--fs-sm);color:var(--ink);
  font-variant-numeric:tabular-nums}
.cfgRow .k{font-size:var(--fs-xs);color:var(--muted);font-family:ui-monospace,Consolas,monospace;
  max-width:42%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* ── 上游更新动态（v2.9）：常驻入口 + 台账列表 ── */
.updLn{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:8px 0 2px;
  background:var(--panel);border:2px solid var(--line);border-radius:14px;padding:9px 14px}
.updLn .ic{font-size:18px;flex:none}
.updLn .tt{font-weight:800;font-size:var(--fs-sm);line-height:1.35;color:var(--ink)}
.updLn .tt small{display:block;font-weight:600;color:var(--muted);font-size:var(--fs-xs)}
.updLn .btn{min-width:0;padding:5px 13px;font-size:var(--fs-sm)}
html[data-theme="N"] .updLn{box-shadow:0 4px 16px rgba(0,0,0,.35)}
/* 台账条目收缩面板（v2.13：内容太长翻不到底 → 每条折叠，头部常驻） */
details.ulItem{padding:7px 2px;border-top:1px solid var(--line)}
details.ulItem:first-child{border-top:none}
details.ulItem summary.ulHd{list-style:none;cursor:pointer;user-select:none;
  margin-bottom:0;border-radius:8px;padding:3px 5px}
details.ulItem summary.ulHd::-webkit-details-marker{display:none}
details.ulItem summary.ulHd:hover{background:var(--panel2)}
details.ulItem[open] summary.ulHd{margin-bottom:7px}
.ulArr{flex:none;font-size:var(--fs-xs);color:var(--muted);transition:transform .15s}
details.ulItem[open] .ulArr{transform:rotate(90deg)}
.ulBd{padding:0 2px 2px 5px}
.ulHd{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:7px}
.ulAt{font-size:var(--fs-xs);font-weight:800;color:var(--ink)}
.ulVia{font-size:var(--fs-xs);font-weight:700;color:var(--muted)}
.ulMore{font-size:var(--fs-xs);color:var(--muted);padding:4px 2px}
/* ulEmpty 与 libEmpty 已合并为统一空态组件（见 .libEmpty 处） */
.dRow{display:flex;align-items:center;gap:10px;padding:8px 12px;border:1px solid var(--line);
  border-radius:10px;margin-bottom:6px;font-size:var(--fs-sm);color:var(--ink2)}
.dRow:hover{border-color:var(--accent)}
.dRow .dNm{font-weight:800;min-width:170px;color:var(--ink)}
.dRow .dNm small{display:block;font-weight:600;color:var(--muted);font-size:var(--fs-xs)}
.dChg{display:flex;flex-wrap:wrap;gap:5px 12px;flex:1}
.dF{font-size:var(--fs-xs);white-space:nowrap}
.dF .k{color:var(--muted)}
.dF .old{color:var(--muted);text-decoration:line-through}
.dF .new{color:var(--accent);font-weight:800;background:var(--panel2);
  border:1px solid var(--line);border-radius:5px;padding:0 4px}
.dF .arr{color:var(--muted);margin:0 2px}
/* 台账明细：类别分组（🔧 地图参数 / ✏️ 通关奖励 / 🌐 地图翻译 …）
   与弹窗顶部的类别筛选 chips（v2.11，用户反馈「分不清哪条是哪类、图名没中文」） */
.dCat{display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;
  padding-right:10px;border-right:1px dashed var(--line)}
.dCat:last-child{border-right:none;padding-right:0}
/* 「本次数据更新」无变化：一行灰字，不再铺一整张卡（v2.14 视觉） */
.card.libDiffNo{padding:9px var(--sp-5);background:var(--panel2);border-style:dashed}
.dNoChg{font-size:var(--fs-xs);color:var(--muted);line-height:1.6}
.ulFilt{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 12px}
.ulF{min-width:0;padding:var(--sp-1) var(--sp-3);font-size:var(--fs-xs);font-weight:700;border-radius:99px;
  border:1px solid var(--line);background:var(--panel);color:var(--ink2);cursor:pointer}
.ulF:hover{border-color:var(--accent)}
.ulF.on{background:var(--accent);border-color:var(--accent);color:#fff}
/* 关卡明细表里的「有更新」角标 */
.updo{display:inline-block;margin-left:6px;font-size:var(--fs-xs);font-weight:800;color:var(--accent);
  background:var(--panel2);border:1px solid var(--line);border-radius:99px;padding:1px 7px;
  vertical-align:middle;cursor:help}
html[data-theme="N"] .updB{box-shadow:0 4px 16px rgba(0,0,0,.35)}
.cbtn:disabled{opacity:.5;cursor:not-allowed}
.cbtn:disabled:hover{border-color:var(--line);color:var(--ink2)}
.sw:disabled{opacity:.5;cursor:not-allowed}
.cbtn{appearance:none;border:2px solid var(--line);background:var(--panel);color:var(--ink2);
font:10.5px/1 inherit;font-family:inherit;font-weight:800;border-radius:999px;padding:4px 10px;
cursor:pointer;white-space:nowrap}
.cbtn:hover{border-color:var(--softline);color:var(--accent)}
/* 复制成功态：浅绿底 + 主题文字色（曾经 background 被下面那条实心绿覆盖，
   又保留了 color:var(--good) → 变成绿底绿字，字看不见） */
.cbtn.done{border-color:var(--good);background:var(--goodsoft);color:var(--ink)}

/* ═══════ ④b 设置页「作者名片」（云朵名片） ═══════ */
.au1{position:relative;display:flex;align-items:center;gap:16px;margin-top:16px;margin-bottom:6px;
background:var(--panel);border:3px solid var(--line);border-radius:22px;
padding:16px 18px;box-shadow:6px 7px 0 var(--softline)}
.au1 .badge{position:relative;width:62px;height:62px;flex:none;padding:0}   /* padding:0 防同名类泄漏（曾致头像偏移 9px） */
.au1 .badge img{width:62px;height:62px;border-radius:19px;display:block;
border:3px solid var(--softline);background:var(--panel2);object-fit:cover}
/* 虚线环必须是正圆：之前是圆角方形（border-radius:24px），9s 旋转时四个角不断
   向外扫，任一时刻看上去都像个「偏移的歪椭圆」（headless 截图实测确认）。
   正圆旋转 silhouette 恒定，只有虚线在缓缓走动，永远不会显得歪 */
.au1 .badge .ring{position:absolute;inset:-7px;border-radius:50%;border:2.5px dashed var(--softline);
pointer-events:none}   /* 旋转动画由 html.aSpin 统一控制，见「动画效果」区 */
.au1 .abody{min-width:0;flex:1}
.au1 .atop{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.au1 .anm{font-family:var(--disp);font-size:16.5px;font-weight:900;color:var(--ink);letter-spacing:-.2px}
.au1 .aver{font-family:var(--mono);font-size:var(--fs-xs);font-weight:800;color:var(--muted);
background:var(--panel2);border:2px solid var(--line);border-radius:999px;padding:2px 9px;
user-select:text;cursor:help}
.au1 .asay{font-size:var(--fs-md);color:var(--ink2);margin-top:6px;line-height:1.6}
.au1 .asay b{color:var(--accent);font-weight:900;font-size:var(--fs-md)}
.au1 .arow{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:11px}
.au1 .atip{font-size:var(--fs-xs);color:var(--muted)}
.au1 .seal{position:absolute;right:14px;top:-11px;font-size:var(--fs-xs);font-weight:900;letter-spacing:.14em;
color:var(--accent);background:var(--soft);border:2px solid var(--softline);border-radius:999px;
padding:2px 10px;transform:rotate(4deg);box-shadow:2px 2px 0 var(--softline)}
/* QQ 胶囊 + 复制按钮（名片、关于卡共用） */
.qqbox{display:inline-flex;align-items:center;gap:9px;border:2px solid var(--softline);
background:var(--soft);border-radius:999px;padding:5px 6px 5px 14px}
.qqbox .qlab{font-size:var(--fs-xs);font-weight:800;letter-spacing:.1em;color:var(--accent);opacity:.85}
.qqbox .qnum{font-family:var(--mono);font-size:17px;font-weight:800;letter-spacing:.4px;
color:var(--accent);user-select:text}
.cbtn.pri{appearance:none;border:none;background:var(--accent);color:#fff;font:700 11.5px/1 inherit;
font-family:inherit;border-radius:999px;padding:8px 13px;cursor:pointer;white-space:nowrap;
box-shadow:0 3px 0 var(--softline);transition:transform .12s,background .2s}
.cbtn.pri:hover{transform:translateY(-1px)}
.cbtn.pri:active{transform:translateY(2px);box-shadow:0 0 0 var(--softline)}
.cbtn.done{box-shadow:0 3px 0 var(--goodsoft)}
@keyframes spin{to{transform:rotate(360deg)}}

/* ═══════ ⑤ 服务器表：官网校验降噪 + 图例 ═══════ */
.wdot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--good);
vertical-align:1px;cursor:help;opacity:.8}
.wdiff.hot{color:#c0455f;border-color:#ffc9d6;background:#ffe9ee;font-weight:800}
html[data-theme="N"] .wdiff.hot{color:#ff9db0;border-color:#55303c;background:#3a2028}
.srvLegend{display:flex;align-items:center;gap:13px;flex-wrap:wrap;
font-size:var(--fs-xs);color:var(--muted);margin-top:7px}
.srvLegend b{color:var(--ink2);font-weight:800}
/* 表底汇总：拆成一排胶囊，各段各有落点（不再是 100 字长句） */
.infoBar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:var(--fs-xs);
color:var(--muted);margin-top:8px;padding:6px 10px;border:2px dashed var(--line);border-radius:12px}
.infoBar .spl{flex:1;min-width:0}
.cpill{display:inline-flex;align-items:center;gap:5px;font-size:var(--fs-xs);font-weight:800;
border:2px solid var(--line);border-radius:999px;padding:2px 9px;background:var(--panel2);
color:var(--ink2);white-space:nowrap;flex:none}
.cpill.a{border-color:var(--softline);background:var(--soft);color:var(--accent)}

/* ═══════ ⑥ 覆盖预览：小窗卡片本体直出 + 位置预设 ═══════ */
/* ── 覆盖设置页分区折叠（v2.3 优化 1 / 4）：常用在外面，长文收进去 ── */
.ovpane{border:1px solid var(--line);border-radius:12px;margin-top:10px;background:var(--panel2)}
.ovpane>summary{cursor:pointer;list-style:none;padding:9px 13px;font-size:var(--fs-md);font-weight:800;
color:var(--ink2);display:flex;align-items:center;gap:8px;user-select:none;transition:background .15s}
.ovpane>summary::-webkit-details-marker{display:none}
.ovpane>summary::before{content:'▶';color:var(--muted);font-size:var(--fs-xs);transition:transform .18s}
.ovpane[open]>summary::before{transform:rotate(90deg)}
.ovpane>summary:hover{background:var(--soft)}
.ovpane>summary .pk{font-size:var(--fs-xs);font-weight:800;color:var(--accent);background:var(--soft);
border-radius:99px;padding:1px 7px}
.ovpane>summary .ar{margin-left:auto;font-size:var(--fs-xs);font-weight:600;color:var(--muted)}
.ovpane .pb{padding:var(--sp-1) var(--sp-3) 12px}
.ovpane .ovRow:first-child{margin-top:0}
/* 紧凑单行预览里的分隔点 */
.ovDot{display:inline-block;width:3px;height:3px;border-radius:50%;
background:currentColor;opacity:.4;margin:0 4px;vertical-align:middle}
/* 预览行：标签固定、值超长时省略号（长地图 ID 不再被硬切，全名在 title 里） */
.ovLine{display:flex;align-items:baseline;justify-content:space-between;gap:14px;white-space:nowrap}
.ovLine .olb{opacity:.66;flex:none;font-weight:600}
.ovLine .ovVal{overflow:hidden;text-overflow:ellipsis;min-width:0;font-weight:800;
font-variant-numeric:tabular-nums}
.ovLine .ovVal.g{color:#ffce7a}
/* 覆盖页设置区并两列：左「显示内容」右「样式」（窄窗自动落回单列） */
.ov2{display:grid;grid-template-columns:1fr 1fr;gap:13px;align-items:start}
@media (max-width:1024px){.ov2{grid-template-columns:1fr}}
.ov2 .colcard{border:2px solid var(--line);border-radius:16px;padding:12px 13px;background:var(--panel2)}
.ov2 .colcard h2{margin-top:0}

/* ═══════ ⑦ 已删除：实体预览的内嵌 iframe 版式（.preBar/.preShot/.preCur/.preNote/
   .preWrap/.preMsg/.preSpin/@keyframes presp）。预览页现由软件内独立窗口打开，
   主界面这套外框、加载态样式再无任何元素引用。 ═══════ */
"""

# -*- coding: utf-8 -*-
"""
页面模板（可爱主题 + 左侧菜单：服务器/主题/设置 三视图）
=================================================================
· 主题：奶油草莓(E) / 薄荷团子(F) / 樱花苏打(G) / 蜜桃气泡(H) / 夜幕护眼(N 深色)
· 配色全部走 CSS 变量，切换主题只改 <html data-theme="?">
· 侧栏三视图：服务器（实时看板+关卡表）/ 主题（5 主题卡片）/ 设置（广播原文 + GitHub 手动同步）
· 视图与主题等界面偏好记忆在 data/ui_prefs.json（fys_view / fys_theme）
页面数据通道（与 fys_reward_app.py 约定）：
    /api/status   当前地图 / 关卡 / 通关云点 / datainfo / sync 状态
    /api/servers  風雲社僵尸逃跑服务器实时看板
    /api/ctl?do=mini|sync|syncstatus|…
"""

import zlib

import ui_js                        # 主脚本（/static/app.js）
import ui_style                     # 样式表（/static/app.css）

THEMES = [
    # (代码, 名称, emoji, 主色, 浅底, 通过色, 正文色, 侧栏, 卡片, 分隔线)
    # 与 CSS 里 html[data-theme] 的 --accent/--soft/--good/--ink/--side/--panel/--line 一一对应，
    # 主题卡色板与迷你缩略直接读这份数据（改配色只改这里 + CSS 两处）。
    ("E", "奶油草莓", "🍓", "#f2608d", "#ffe7ef", "#57bd8b", "#4a323c", "#ffeff5", "#ffffff", "#ffd9e4"),
    ("F", "薄荷团子", "🍀", "#28a97a", "#ddf7ea", "#28a97a", "#254238", "#ecfaf3", "#ffffff", "#ccefe0"),
    ("G", "樱花苏打", "🌸", "#8f6bff", "#f0e8ff", "#54b7d6", "#3c3358", "#f6efff", "#ffffff", "#e4d9ff"),
    ("H", "蜜桃气泡", "🍑", "#f08a24", "#fff0d8", "#63b96a", "#4a3a20", "#fff4e3", "#ffffff", "#ffe0b8"),
    ("N", "夜幕护眼", "🌙", "#f0a868", "#2b2420", "#7fc79b", "#e9e4ee", "#1a1920", "#1e1d24", "#322f3a"),
]

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="E"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>云朵小铺</title>
<meta name="color-scheme" content="light dark">
<link rel="icon" href="data:,">
<link rel="stylesheet" href="/static/app.css?v=__ASSETV__">
<style id="bootSplashCss">
/* ── 内置启动界面（v2.15）：页面自带的首帧启动卡。样式内联在 <head> 里，
   不等 app.css 下载就能画出来；bootReal 完成后由 JS 淡出移除。
   浅色主题 = 奶油云朵卡（A）；data-theme=N 时加 .bsDark 走夜幕星云（B）。 ── */
#bootSplash{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;
justify-content:center;background:linear-gradient(160deg,#fff6f8,#ffe7ef);
transition:opacity .45s ease}
#bootSplash.bsOut{opacity:0;pointer-events:none}
.bsCard{text-align:center;animation:bsIn .55s ease both;padding:0 20px;
position:relative;transition:transform .45s ease}
#bootSplash.bsOut .bsCard{animation:none;transform:translateY(-18px)}
.bsCard img{width:76px;height:76px;animation:bsBob 3.4s ease-in-out infinite}
.bsTitle{font:800 26px/1.3 "Microsoft YaHei",sans-serif;color:#4a323c;margin-top:10px}
.bsVer{font:600 13px/1.6 "Microsoft YaHei",sans-serif;color:#b292a0;margin-top:2px}
.bsPhase{font:700 14px/1.8 "Microsoft YaHei",sans-serif;color:#7a5568;
margin-top:22px;min-height:1.8em}
.bsBar{position:relative;width:300px;max-width:70vw;height:6px;border-radius:3px;
background:rgba(242,96,141,.16);margin:12px auto 0;overflow:hidden}
.bsBar i{position:absolute;left:0;top:0;bottom:0;width:10%;border-radius:3px;
background:linear-gradient(90deg,#f2608d,#ff8ab0,#f2608d);background-size:200% 100%;
animation:bsShimmer 1.3s linear infinite;
transition:width .55s cubic-bezier(.22,.8,.36,1)}
.bsFoot{font:600 11px/1 "Microsoft YaHei",sans-serif;color:#c4a5b3;margin-top:26px}
.bsCloud{position:absolute;background:#fff;border-radius:99px;opacity:.55;
animation:bsDrift 9s ease-in-out infinite alternate}
.bsCloud.c1{left:36px;bottom:44px;width:120px;height:38px}
.bsCloud.c2{right:52px;top:64px;width:92px;height:30px;opacity:.4;
animation-duration:11s;animation-direction:alternate-reverse}
.bsStar{position:absolute;width:3px;height:3px;border-radius:50%;background:#e9e4ee;
display:none;animation:bsTw 2.8s ease-in-out infinite}
#bootSplash.bsDark{background:linear-gradient(165deg,#221c2e,#1a1920 55%,#141318)}
#bootSplash.bsDark .bsCloud{display:none}
#bootSplash.bsDark .bsStar{display:block}
#bootSplash.bsDark .bsCard{background:rgba(30,29,36,.66);
border:1px solid rgba(240,168,104,.28);border-radius:20px;
padding:30px 52px 26px;animation-name:bsRise}
#bootSplash.bsDark .bsCard img{animation:none}
#bootSplash.bsDark .bsTitle{color:#f2ecf6}
#bootSplash.bsDark .bsVer{color:#9d92ac}
#bootSplash.bsDark .bsPhase{color:#cfc6da}
#bootSplash.bsDark .bsFoot{color:#8b8098}
#bootSplash.bsDark .bsBar{height:3px;width:280px;background:rgba(233,228,238,.14)}
#bootSplash.bsDark .bsBar i{background:linear-gradient(90deg,
rgba(240,168,104,.3),#f0a868,#f0a868,rgba(240,168,104,.3));background-size:200% 100%}
#bootSplash.bsDark.bsOut .bsCard{transform:scale(.96)}
@keyframes bsIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes bsRise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes bsBob{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes bsDrift{from{transform:translateX(0)}to{transform:translateX(60px)}}
@keyframes bsTw{0%,100%{opacity:.15}50%{opacity:1}}
@keyframes bsShimmer{from{background-position:0 0}to{background-position:-200% 0}}
</style></head><body>

<div id="bootSplash" role="status" aria-label="正在启动">
<i class="bsCloud c1"></i><i class="bsCloud c2"></i>
<i class="bsStar" style="left:14%;top:22%"></i>
<i class="bsStar" style="left:28%;top:52%;width:2px;height:2px;background:#f0a868;animation-delay:.6s"></i>
<i class="bsStar" style="right:16%;top:18%;animation-delay:1.1s"></i>
<i class="bsStar" style="right:30%;top:42%;width:2px;height:2px;background:#fff;animation-delay:.3s"></i>
<i class="bsStar" style="left:8%;top:64%;animation-delay:1.5s"></i>
<div class="bsCard">
  <img src="__LOGO__" alt="">
  <div class="bsTitle">云朵小铺</div>
  <div class="bsVer">FYS 通关奖励看板 · __VER__</div>
  <div class="bsPhase" id="bsPhase">正在启动…</div>
  <div class="bsBar"><i></i></div>
  <div class="bsFoot">正在准备界面，马上就好…</div>
</div></div>
<script>var __bsT0=Date.now();</script>

<div class="shell">

<header class="tbar pywebview-drag-region" id="titlebar">
  <button class="wbtn fold" id="reopenBtn" title="展开菜单">☰</button>
  <span class="tlogo" id="tlogo"><img src="__LOGO__" alt=""></span>
  <span class="ttitle">云朵小铺<i class="tsep">›</i><b class="tpage" id="tPage">服务器</b></span>
  <span class="spacer"></span>
  <button class="wbtn wst wst-min" id="wMin" title="最小化"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="4.5" stroke-linecap="round"><path d="M6 12h12"/></svg></button>
  <button class="wbtn wst wst-max" id="wMax" title="最大化 / 还原"><svg id="svgMaxNormal" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="3.5"/></svg><svg id="svgMaxRestore" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="3"/><path d="M6 15H5.5A2.5 2.5 0 0 1 3 12.5v-7A2.5 2.5 0 0 1 5.5 3h7A2.5 2.5 0 0 1 15 5.5V6"/></svg></button>
  <button class="wbtn wst wst-cls close" id="wClose" title="关闭"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="4.5" stroke-linecap="round"><path d="M7.5 7.5l9 9M16.5 7.5l-9 9"/></svg></button>
</header>

<div class="app">
  <aside class="side" id="side">
    <div class="stop sr">
      <span class="logo" id="logo"><img src="__LOGO__" alt=""></span>
      <span class="sname">云朵小铺<span class="ver" id="appVer" title="当前版本">__VER__</span></span>
      <button class="fold" id="foldBtn" title="收起菜单">«</button>
    </div>

    <div class="sgroup sr">
      <button class="nav mv on" data-view="srv">🎮 服务器</button>
      <button class="nav mv" data-view="ov">🖥 屏幕覆盖</button>
      <button class="nav mv" data-view="theme">🎨 主题</button>
      <button class="nav mv" data-view="lib">📚 地图库</button>
      <button class="nav mv" data-view="pre" title="软件内直接查看地图实体预览（3D 视图；离开本页自动释放渲染，另有独立窗口模式）">🗺️ 地图实体预览</button>
      <button class="nav mv" data-view="set">⚙️ 设置</button>
    </div>
  </aside>

  <main class="main">
   <div class="bglayer" aria-hidden="true">
     <i class="bgtape t1"></i><i class="bgtape t2"></i><i class="bgtape t3"></i>
     <i class="cl c1"></i><i class="cl c2"></i>
     <i class="bgclip" style="left:8%;top:14%;transform:rotate(-14deg)"></i>
     <i class="bgclip" style="right:14%;bottom:20%;transform:rotate(72deg)"></i>
     <i class="bgdot" style="left:44%;top:30%;transform:scale(.85)"></i>
     <i class="bgdot" style="left:70%;top:16%;transform:scale(.7)"></i>
     <i class="bgdot" style="left:20%;top:56%;transform:scale(.9)"></i>
     <i class="bgdot" style="left:64%;top:72%;transform:scale(.75)"></i>
     <i class="bgdot" style="left:88%;top:40%;transform:scale(.8)"></i>
     <i class="bgstar" style="left:36%;top:11%">✦</i>
     <i class="bgstar" style="left:78%;top:64%">✦</i>
     <i class="bgstar" style="left:12%;top:80%">✦</i>
   </div>
   <div class="content">
    <div class="bar">
      <span class="pill" id="pill"><i></i><span id="stateText">连接中…</span></span>
      <span class="spacer"></span>
    </div>

    <!-- 上游数据更新提醒：检测到 GitHub 数据仓变化时出现（seen 后消失） -->
    <div class="updB" id="updB" style="display:none">
      <span class="ic">🆕</span>
      <div class="tt">官方数据有更新<small id="updBSub">—</small></div>
      <div class="stat" id="updBStat"></div>
      <span class="spacer"></span>
      <button class="btn" id="updBView">查看明细</button>
      <button class="btn pri" id="updBGo">立即更新</button>
      <button class="cbtn" id="updBX" title="知道了，不再提醒">✕</button>
    </div>

    <!-- 上游更新动态：**有新记录时才出现**，看过/点 ✕ 后消失（可在「设置」页随时回看） -->
    <div class="updLn" id="updLn" style="display:none">
      <span class="ic">📜</span>
      <div class="tt">上游更新动态<small id="updLnSub">读取中…</small></div>
      <span class="spacer"></span>
      <button class="btn" id="updLnView">查看记录</button>
      <button class="cbtn" id="updLnX" title="知道了，不再提醒">✕</button>
    </div>

    <div class="view on" id="view-srv">
    <div class="cols">
      <div class="colL stag">
        <div class="card" id="secNow" style="--i:0">
          <div class="maprow2">
            <div class="mapbox">
              <div class="mcn2" id="mapCn">—</div>
              <div class="mfn2" id="mapFn"></div>
            </div>
            <div class="mtags">
              <span class="tag" id="stageTag" style="display:none"></span>
              <span class="tag" id="srcTag" style="display:none"></span>
              <button class="btn" id="pvNow" style="padding:var(--sp-1) 11px;font-size:var(--fs-xs)"
                title="去地图库看这张图：译名 / 关卡数 / 通关奖励，并高亮定位到这一行">📚 去地图库</button>
            </div>
          </div>
          <div class="sub" id="subText">正在定位当前服务器…</div>
          <div class="srv opt" id="srvBox" style="display:none">
            <span class="slab">服务器</span>
            <span class="sname" id="srvName">—</span>
            <span class="smeta" id="srvMeta"></span>
          </div>

          <div class="hint opt" id="hint" style="display:none"></div>
          <div class="opt" id="grid"></div>

          <!-- ⑯ 空闲态补位：没进服时左栏只剩「未在服务器内」大片留白；
               这里放「最近查看的地图」（localStorage 本机浏览记录，不是游玩历史），
               点一下直接跳地图库定位到那张图；进服后自动隐藏，给四宫格让位 -->
          <div class="recent" id="recentBox" style="display:none">
            <div class="rcLab">🕘 最近查看的地图</div>
            <div class="rcList" id="recentList"></div>
          </div>
        </div>
      </div>

      <div class="colR opt stag">
        <h2 style="--i:1">🎮 風雲社 · 僵尸逃跑服务器（实时地图）</h2>
        <div class="srvWrap"><table class="srvtab" style="--i:1"><thead><tr>
          <th>服务器</th><th>当前地图</th><th>通关云点</th><th>通关龙晶</th><th>在线</th>
        </tr></thead><tbody id="stb"><tr><td colspan="5" class="s">正在探测…</td></tr></tbody></table></div>
        <div class="srvLegend" id="srvLegend">
          <span><i class="wdot"></i> <b>一致</b>（与官网实时人数相同）</span>
          <span><span class="wdiff hot">⚠ 官网 N</span> 与官网人数有分歧（悬停看对比）</span>
          <span><span class="wdiff">官网 —</span> 官网暂无该台</span>
          <span><span class="apx">≈</span> 地图名按官方登记名近似匹配</span>
        </div>
        <div class="infoBar" id="infoBar" style="--i:2">
          <span class="cpill a" id="srvAt">🕒 探测中…</span>
          <span class="cpill" id="srvOn">在线 — / — 台</span>
          <span class="spl"></span>
          <span class="cpill" id="srvWeb">🌐 官网 —</span>
          <span class="cpill">↻ 每 15 秒</span>
        </div>

        <h2 style="--i:3">🧭 该图全部关卡</h2>
        <table class="numtab" style="--i:3"><thead><tr>
          <th>关卡</th><th>通关云点</th><th>通关龙晶</th><th>伤害云点</th>
        </tr></thead><tbody id="tbody"><tr><td colspan="4" class="s">—</td></tr></tbody></table>
      </div>
    </div>
    </div>

    <div class="view" id="view-ov">
      <h2 style="margin-top:0">🖥 屏幕覆盖（独立置顶小窗 · 游戏全屏也能看到）</h2>

      <!-- ① 预览 + 主操作（一进来就能看到小窗长什么样、怎么开） -->
      <div class="card ovHero">
        <div class="ovPrev" id="ovPrev"></div>
        <div class="ovHeroAct">
          <div class="ovHeroTop">
            <button class="btn pri" id="btnOvToggle">启动覆盖</button>
            <span class="sub" id="ovState" style="margin:0">未启动</span>
            <label class="ovCk"><input type="checkbox" id="ovCT"><span>鼠标穿透</span></label>
          </div>
          <div class="sub" style="margin:2px 0 0">穿透开启后点击直达游戏/桌面；取消勾选立刻恢复可拖动，两种改动都不重启小窗。</div>
          <div class="sub ovHelp" id="ovTrouble">
            <b>❓ 看不到小窗？</b>① 游戏开的是<b>独占全屏</b> → 改成「无边框窗口」；
            ② 少数机器（显卡合成异常 / 远程桌面）无边框窗看不见 → 换原生分层窗。
            <button class="btn" id="ovFixTk">改用 tkinter 透明</button>
          </div>
        </div>
      </div>

      <!-- ② 页内分栏：外观与内容 / 直播输出 / 战绩 -->
      <div class="ovTabs" role="tablist">
        <button class="ovTab on" data-tab="look">🎨 外观与内容</button>
        <button class="ovTab" data-tab="out">📺 直播输出</button>
        <button class="ovTab" data-tab="gsi">📊 战绩</button>
      </div>

      <div class="ovPane on" data-tab="look">
        <div class="ovSec">🎛 布局<span class="ovSecHint">点一下即时换，换布局会重建小窗（闪一下）</span></div>
        <div class="ovLays">
          <button class="btn ovl" data-l="card"><b>📋 卡片</b><small>标签 + 数值两栏，信息最全</small></button>
          <button class="btn ovl" data-l="compact"><b>📏 单行</b><small>一行胶囊，最省屏幕</small></button>
          <button class="btn ovl" data-l="iconic"><b>🗺️ 地图图标</b><small>左侧封面竖条 + 数值</small></button>
          <button class="btn ovl" data-l="skin"><b>🖼️ 自定义底图</b><small>整张图当背景</small></button>
        </div>

        <div class="ovSec">📋 显示内容<span class="ovSecHint">勾选即时同步到预览、小窗与直播文本</span></div>
        <div class="ovChecks" id="ovChecks"><div class="sub" style="margin:0">正在读取覆盖配置…</div></div>

        <div class="ovSec">🎨 外观</div>
        <div class="ovRow" style="margin-top:0">
          <span class="k">文字颜色</span>
          <input type="color" id="ovColor">
          <span class="k" style="margin-left:18px">字号 <b id="ovSizeV">30</b>px</span>
          <input type="range" id="ovSize" min="8" max="72" step="1">
        </div>
        <div class="ovRow">
          <span class="k">背景深度 <b id="ovBgV">55</b>%</span>
          <input type="range" id="ovBg" min="0" max="95" step="5">
        </div>

        <details class="ovpane" data-pane="adv">
          <summary>🖼️ 自定义底图与取景<span class="ar">默认收起</span></summary>
          <div class="pb">
            <div class="ovRow" style="margin-top:0">
              <span class="k">底图透明度 <b id="ovSkinOpV">62</b>%</span>
              <input type="range" id="ovSkinOp" min="20" max="95" style="vertical-align:-2px">
              <span class="sub" style="margin:0">数值越大底图越透明（能看见游戏/桌面），越小越实、文字越清楚</span>
            </div>
            <div class="ovRow">
              <span class="k">底图</span>
              <label class="btn" style="min-width:0;padding:var(--sp-1) var(--sp-3);cursor:pointer;margin-left:0">📁 上传图片
                <input type="file" id="ovSkinFile" accept="image/png,image/jpeg,image/webp" hidden></label>
              <button class="btn" id="ovSkinClear" style="min-width:0;padding:var(--sp-1) var(--sp-3);margin-left:6px">清除</button>
              <button class="btn" id="ovSkinCropBtn" style="min-width:0;padding:var(--sp-1) var(--sp-3);margin-left:6px">✂️ 取景</button>
              <span class="sub" id="ovSkinHint" style="margin:0">PNG / JPG / WEBP，≤4MB；配合「🖼️ 自定义底图」布局使用</span>
            </div>
            <div class="ovRow cropWrap" id="ovCropWrap" hidden>
              <div class="cropBox" id="ovCropBox">
                <img id="ovCropImg" alt="">
                <div class="cropSel" id="ovCropSel">
                  <span class="ch tl" data-h="nw"></span><span class="ch tm" data-h="n"></span>
                  <span class="ch tr" data-h="ne"></span><span class="ch ml" data-h="w"></span>
                  <span class="ch mr" data-h="e"></span><span class="ch bl" data-h="sw"></span>
                  <span class="ch bm" data-h="s"></span><span class="ch br" data-h="se"></span>
                </div>
              </div>
              <div class="cropSide">
                <div class="cropTip">拖动框选区域 · 拖角/边调整 · 框内拖动移动</div>
                <div class="cropRow">
                  <label class="ck"><input type="checkbox" id="ovCropRatio"> 锁定为覆盖窗比例（约 21:11）</label>
                </div>
                <div class="cropRow">
                  <button class="btn" id="ovCropReset">整张</button>
                  <button class="btn" id="ovCropApply" style="margin-left:6px">应用取景</button>
                  <button class="btn" id="ovCropCancel" style="margin-left:6px">取消</button>
                </div>
                <div class="sub" id="ovCropMsg" style="margin:0"></div>
              </div>
            </div>
          </div>
        </details>
      </div>

      <div class="ovPane" data-tab="out">
        <div class="ovSec">🖥 覆盖方式<span class="ovSecHint">两种方式任选；换模式会重建小窗</span></div>
        <div class="ovRow" style="margin-top:0">
          <button class="btn" id="ovModeF" style="min-width:0;padding:var(--sp-1) var(--sp-3)">无边框窗</button>
          <button class="btn" id="ovModeT" style="min-width:0;padding:var(--sp-1) var(--sp-3);margin-left:6px">tkinter 透明</button>
          <span class="sub" style="margin:0;margin-left:8px">tkinter = 原生分层窗（逐像素透明，不吃显卡合成，四种布局全支持）；无边框窗 = 半透明卡片，能被 OBS 窗口捕获。</span>
        </div>

        <div class="ovSec">📺 直播文本 txt（OBS 文本源）</div>
        <div class="ovRow" style="margin-top:0">
          <label class="ovCk"><input type="checkbox" id="ovTxt"><span>生成直播文本</span></label>
          <span class="sub" style="margin:0;word-break:break-all" id="ovTxtPath">—</span>
          <button class="btn" id="ovTxtLoc" title="打开文件所在位置" style="min-width:0;padding:4px 10px;flex:none">📁</button>
          <button class="btn" id="ovTxtOpen" title="打开 txt 文件" style="min-width:0;padding:4px 10px;flex:none">📄</button>
        </div>
        <div class="sub" style="margin-top:2px">OBS → 来源 → 文本(GDI+) → 勾选「从文件读取」→ 填入上面的路径；字体/颜色/描边都在 OBS 里调，画面最清晰。</div>

        <div class="ovSec">🎬 小窗进 OBS（仅无边框窗模式）</div>
        <div class="sub" style="margin:0;line-height:1.8">OBS → 来源 → 窗口捕获 → 选「FYS 屏幕覆盖」。<b>tkinter 透明窗是分层窗口，窗口捕获抓不到</b>。
          也可以把小窗拖到游戏画面里，用显示器/游戏捕获一并带进直播。</div>
      </div>

      <div class="ovPane" data-tab="gsi">
        <div class="card">
          <div class="aboutRow"><span class="al">游戏集成</span>
            <span class="av human" id="gsiLine" style="flex:1;text-align:left">正在读取…</span>
            <span class="sw" id="swGsi" title="开关 CS2 游戏状态集成（GSI）：实时识别地图/比分与本局伤害"></span></div>
          <div class="acts" style="margin-top:8px">
            <button class="btn" id="gsiInstall" title="按当前端口重写游戏目录里的 GSI 配置（换端口/重装游戏后点一下）">↻ 重写配置</button>
            <button class="btn" id="gsiRemove" title="从 CS2 目录删掉本软件的 GSI 配置（不再接收游戏数据）">🗑 卸载配置</button>
          </div>
          <div class="sub" id="gsiSub" style="margin-top:8px"><b>默认开启</b>：软件启动时自动把配置写进 CS2 目录（写完后需重启一次 CS2 才生效）；
            地图、比分与本局伤害直接来自游戏本身；官方客户端没上报关卡时，按「CT 赢的回合数 + 1」推断并标注「比分推断」。
            不想用点右侧开关关掉，关掉后不再写配置。</div>
          <div class="sub ell" id="gsiPath">配置位置 —</div>
          <div class="sub" style="margin-top:6px">本局伤害按每回合 <code>round_totaldmg</code> 峰值累加；小窗里
            「通关云点 13（1↑）」是伤害换到的个数，「伤害云点 2.4w（0.3w）」是距下一档还差多少伤害。</div>
        </div>

        <div class="ovSec">📈 最近对局<span class="ovSecHint" id="mSum"></span></div>
        <table class="numtab"><thead><tr>
          <th>对局</th><th>地图 / 关卡</th><th>比分</th><th>时长</th><th>K / D / A</th>
          <th>本局伤害</th><th>兑换（按比例推算）</th>
        </tr></thead><tbody id="mbody"><tr><td colspan="7" class="s">—</td></tr></tbody></table>
        <div class="sub" style="margin-top:6px">数据只存在本机 data\matches.json；「兑换」按该图该关官方伤害转化比向下取整，仅供参考，实际以服务器结算为准。</div>
      </div>

      <div class="sub" style="margin-top:10px">改动即时生效并自动保存；覆盖窗口可拖动，关闭后下次原地打开。</div>
    </div>

    <div class="view" id="view-theme">
      <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-top:0">
        <h2 style="margin:0">🎨 主题样式（点击即换，自动记住）</h2>
        <button class="btn" id="btnResetLook" title="主题 / 背景 / 贴纸一键回到出厂默认">↺ 恢复默认外观</button>
      </div>
      <div class="themeGrid" id="themes"></div>

      <h2>🖼 界面背景（点击即换，自动记住）</h2>
      <div class="bgcard">
        <div class="bggrid" id="bggrid"></div>
        <div class="bgsep">
          <b>🧸 侧栏贴纸（可单独自选）</b>
          <div class="stkrow" id="stkrow"></div>
        </div>

        <div class="bgfoot"><span class="fhint">底纹是「云朵小铺」主题图案（云朵 / 龙晶 / 小僵尸），
          换到夜幕护眼主题会自动切成暗色版；选「纯色无背景」只关图案与插画，贴纸仍按上面「侧栏贴纸」的选择。</span></div>
      </div>

      <h2>🎬 动画效果（逐项开关即时生效，自动记住）</h2>
      <div class="fxcard">
        <div class="fxfoot" style="border-bottom:1px dashed var(--panel2);padding-top:10px">
          <label style="display:flex;align-items:center;gap:7px;font-size:var(--fs-sm);font-weight:700;cursor:pointer;white-space:nowrap">
            <input type="checkbox" id="fxRM" style="accent-color:var(--accent);width:15px;height:15px;cursor:pointer">
            <span>跟随系统「减少动态效果」</span>
          </label>
          <span class="fhint" id="fxRMHint"></span>
        </div>
        <div class="fxgrid" id="fxgrid"></div>
        <div class="fxfoot">
          <button class="btn act" id="bAllOn">全部开启</button>
          <button class="btn" id="bAllOff">全部关闭</button>
          <button class="btn" id="bReplay">重播动画</button>
          <span class="fhint">开关自动保存，重启后仍保持</span>
        </div>
      </div>

      <div class="themePal">
        <h2 style="margin-top:0">🎨 当前主题 · <span id="palName">奶油草莓</span> 配色说明</h2>
        <div class="palgrid">
          <div class="pc"><i id="palA"></i><div><b>主色 accent</b><span id="palAv">—</span></div></div>
          <div class="pc"><i id="palS"></i><div><b>浅底 soft</b><span id="palSv">—</span></div></div>
          <div class="pc"><i id="palG"></i><div><b>通过 good</b><span id="palGv">—</span></div></div>
          <div class="pc"><i id="palI"></i><div><b>正文 ink</b><span id="palIv">—</span></div></div>
        </div>
        <div class="sub">主色用于强调（数值/标题/图标），浅底用于卡片与标签背景，通过色专给「达成/满员」类状态，
          正文色是主要文字。想换风格时先看这四色搭配，再点上面的主题卡。<br>
          全部配色只走 CSS 变量，切换主题不重新加载页面，动画开关也不受影响。</div>
      </div>
    </div>

    <div class="view" id="view-lib">
      <h2 style="margin-top:0">📚 地图库（搜索地图名 或 译名，查看每张图的关卡与参数）</h2>
      <div class="card">
        <div class="libBar">
          <label class="libSearch"><i>🔍</i>
            <input id="libQ" placeholder="搜索地图名或译名：ze_samosbor / 自肃 / 医院" autocomplete="off">
            <button class="libClr" id="libClr" title="清空搜索">×</button>
          </label>
          <select class="libSel" id="libSort">
            <option value="cn">按译名</option>
            <option value="st">按关卡数</option>
            <option value="pr">按龙晶价格</option>
          </select>
          <button class="btn" id="libReload" style="min-width:0;padding:5px 11px" title="重新读取索引（同步新图后可用）">🔄</button>
          <span class="libCnt" id="libCnt">—</span>
        </div>
        <div class="libCats" id="libChips">
          <span class="libCatLab">🎯 分类</span>
          <span class="libHint">可多选 · 同时满足（EXG 为独立视图）</span>
          <span class="libSep"></span>
          <button class="libChip on" data-t="all" title="只看 FYS 官方地图库收录的图（默认）。EXG 补充图不在这里，需要点右侧 EXG 按钮单独查看">📘 官方收录</button>
          <div class="rowline">
            <button class="libChip" data-t="exg" title="EXG 图池里有、FYS 官方地图库暂未收录的僵尸逃跑图。参数与奖励按「同类图」估算，仅供参考。点这里只看这类图，再点一次回到官方收录">🧩 EXG<i>0</i></button>
            <span class="libSep"></span>
            <button class="libChip" data-t="fav" title="只看我收藏的地图（点列表行尾的星标即可收藏 / 取消）">⭐ 我的收藏<i>0</i></button>
            <span class="libSep"></span>
            <button class="libChip" data-t="rnd" title="母体僵尸纯随机产生的地图（官方 ze_infect_sort_by_immunity = false）">🎲 随机尸变<i>0</i></button>
            <span class="libSep"></span>
            <button class="libChip" data-t="ad" title="需要管理员才能选图 / 换图（官方 maps.json 的 admin: true）">🔑 需要管理员<i>0</i></button>
            <button class="libChip" data-t="nad" title="任何人都可以选图，不需要管理员（官方 admin: false）">🆓 无需管理员<i>0</i></button>
            <span class="libSep"></span>
            <button class="libChip" data-t="nm" title="可以发起提名（官方 nomination: true）">🙋 可被提名<i>0</i></button>
            <button class="libChip" data-t="nnm" title="不可被提名，只能管理员直接选（官方 nomination: false）">🚫 不可提名<i>0</i></button>
            <span class="libSep"></span>
            <button class="libChip" data-t="tm" title="只在特定时段可玩（官方 certainTimes 是具体小时列表）">🕒 限定时段<i>0</i></button>
            <button class="libChip" data-t="at" title="全天任何时段都能玩（官方 certainTimes = [-1]）">🌐 全天可玩<i>0</i></button>
          </div>
        </div>
        <div class="libSplit">
          <div class="libList" id="libList"><div class="libEmpty">正在读取地图索引…</div></div>
          <div class="libDetail" id="libDetail"><div class="libEmpty">左侧选一张地图查看参数</div></div>
        </div>
        <div class="sub" id="libSub">支持地图名（如 ze_samosbor）与译名（如 自肃）搜索，空格分隔多个关键词。</div>
      </div>
    </div>

    <div class="view" id="view-pre">
      <div class="preBar2">
        <span id="preCur2">🗺️ 地图实体预览</span>
        <button class="btn" id="preReload" style="min-width:0;padding:4px 10px" title="重新加载当前预览">🔄 重新加载</button>
        <button class="btn" id="prePop" style="min-width:0;padding:4px 10px" title="用独立窗口打开（WebGL 在独立窗口跑，主界面零负担；可最大化、拖到第二块屏）">🪟 独立窗口</button>
        <span class="preHint">离开本页会自动释放 3D 渲染；觉得卡就点「独立窗口」。</span>
      </div>
      <iframe id="preFrame" title="地图实体预览"></iframe>
    </div>

    <div class="view" id="view-set">
      <h2 style="margin-top:0">📖 使用说明</h2>
      <div class="rmcard">
        <span class="ic">📖</span>
        <div class="rt">
          <div class="t1">第一次用？建议先看一遍</div>
          <div class="t2">怎么用、数值怎么读、认不出地图怎么办，都在里面（首次打开软件会自动弹出一次）。</div>
        </div>
        <button class="btn" id="rmOpen" style="flex:none">打开说明书</button>
      </div>

      <h2>📥 地图数据同步（GitHub · fyscs/cs2）</h2>
      <div class="syncbox">
        <span class="sub" style="margin:0" id="syncInfo">—</span>
        <span class="spacer"></span>
        <button class="btn" id="btnSync">立即同步</button>
      </div>
      <div class="pbar" id="syncBar" hidden><i id="syncBarFill"></i></div>
      <div class="sub" style="margin-top:6px">从 GitHub 重新下载 fyscs/cs2 仓库并重建索引，新图上线后点这里即可更新（约 10~30 秒，失败不影响现有数据）。数据源直连 GitHub 官方仓库，不经任何中转服务器。<b>新图封面会在同步完成后自动补齐</b>（直连风云社官方图床 resx.fyscs.cn，无需等版本更新）。</div>

      <h2>📡 上游数据更新提醒（GitHub 变更检测）</h2>
      <div class="card">
        <div class="aboutRow"><span class="al">自动同步</span>
          <span class="av human" style="flex:1;text-align:left">启动时和后台检测到变更后<b>自动下载并应用</b>（等价于自动点「立即同步」），地图库原地刷新；改了什么去「上游更新动态」看明细（默认开启，直连 GitHub 官方源）</span>
          <span class="sw" id="swUpdSync" title="点击切换，立即生效"></span></div>
        <div class="aboutRow"><span class="al">自动应用</span>
          <span class="av human" style="flex:1;text-align:left">检测到变更后自动确认提醒，横幅只提示一次不常驻（默认关闭：横幅常驻等你确认，看一眼更放心）</span>
          <span class="sw" id="swUpdAuto" title="点击切换，立即生效"></span></div>
        <div class="aboutRow"><span class="al">下架提醒</span>
          <span class="av human" style="flex:1;text-align:left">官方仓库移除的地图也在横幅与明细里提醒（下架图的本机数据保留，收藏不丢）</span>
          <span class="sw" id="swUpdDel" title="点击切换，立即生效"></span></div>
        <div class="sub" style="margin-top:8px">跟踪范围：新图上线 / 地图下架 / 通关奖励调整 /
          关卡数变化 / 尸变参数（尸变模式·尸变比·倒计时·回出生点）/ <b>地图参数</b>
          （地图与回合时间·摔伤·击退系数·僵尸技能数值·每局补给与可购买的手雷火瓶数量·
          选图价格·冷却·人数门槛·限定时段 等）。改动会在首页横幅里分类列出，
          并写明参数名与旧值 → 新值，点「查看明细」即可核对。</div>
      </div>

      <h2>🎮 CS2 游戏状态集成（GSI）</h2>
      <div class="card">
        <div class="aboutRow"><span class="al">状态</span>
          <span class="av human" id="gsiSetLine" style="flex:1;text-align:left">—</span>
          <span class="acts">
            <button class="btn" id="gsiGo" style="min-width:0;padding:var(--sp-1) 11px"
              title="开关 GSI、写入/卸载游戏配置都在战绩页">去战绩页设置</button>
          </span></div>
        <div class="sub" style="margin-top:8px">开启后软件会把配置写进 CS2 目录（game\csgo\cfg），
          地图与比分**直接来自游戏本身**（比广播文件 + 服务器查询更准）；
          官方客户端没上报关卡时，按「CT 赢的回合数 + 1」推断并标注「比分推断」。
          数据只在本机内存里流转，不上传任何地方。</div>
      </div>

      <h2>📋 广播文件原文（备用通道）</h2>
      <div class="rawEmpty" id="rawEmpty" style="display:none">
        <span class="ic">📡</span>
        <div class="t1">还没读到广播原文</div>
        <div class="t2">进入服务器并开始一局后，这里会显示 fys 官方客户端写出的实时文本。<br>
          认地图出错时，把这里的内容发给开发者，即可按真实格式补规则。</div>
        <div class="acts">
          <button class="btn" id="rawLocBtn" style="min-width:0;padding:5px 12px">📁 打开广播文件位置</button>
          <button class="btn" id="rawReBtn" style="min-width:0;padding:5px 12px">🔄 立即重读</button>
        </div>
        <div class="fn" id="rawEmptyPath">广播文件 —</div>
      </div>
      <pre id="raw">—</pre>

      <h2>💡 关于 云朵小铺</h2>
      <div class="card" id="aboutCard">
        <div class="aboutRow"><span class="al">软件</span><span class="av human">云朵小铺 · 風雲社 ZE 通关奖励看板</span></div>
        <div class="aboutRow"><span class="al">版本</span><span class="av" id="abVer">—</span></div>
        <div class="aboutRow"><span class="al">服务端口</span><span class="av" id="abPort">—</span></div>
        <div class="aboutRow"><span class="al">数据索引</span><span class="av" id="abData">—</span></div>
        <div class="aboutRow"><span class="al">数据目录</span><span class="av ell" id="abDir">—</span>
          <span class="acts">
            <button class="cbtn" id="abDirCopy" title="复制完整路径">📋</button>
            <button class="btn" id="abDirBtn" style="min-width:0;padding:var(--sp-1) 11px" title="在资源管理器中打开">📁 打开</button>
          </span></div>
        <div class="aboutRow"><span class="al">运行日志</span><span class="av ell" id="abLog">—</span><b class="lsz" id="abLogSz"></b>
          <span class="acts">
            <button class="cbtn" id="abLogCopy" title="复制完整路径">📋</button>
            <button class="btn" id="abLogBtn" style="min-width:0;padding:var(--sp-1) 11px" title="打开 startup.log">📄 打开</button>
          </span></div>
        <div class="aboutRow"><span class="al">地形分包</span><span class="av" id="abTerr">—</span>
          <span class="acts">
            <button class="btn" id="abTerrClear" style="min-width:0;padding:var(--sp-1) 11px"
                    title="清空已下载的 3D 地形缓存。地形是按需下载的，删掉后下次点开该图会自动重新下载（没网时看不了地形）">🧹 清理</button>
          </span></div>
        <div class="aboutRow"><span class="al">预览数据</span><span class="av" id="abPv">—</span></div>
        <div class="aboutRow"><span class="al">地图封面</span><span class="av" id="abCover">—</span></div>
        <div class="aboutRow"><span class="al">数据来源</span><span class="av human">GitHub fyscs/cs2 · 風雲社官网 fyscs.cn</span></div>
        <!-- 杀软误报自助：Defender 常把 Python 单文件 exe 的「自我解压」当成可疑行为拦掉。
             玩家遇到的是「打不开」，所以入口必须放在软件里（他不一定会去翻 使用说明.txt）。
             复制的是可直接在管理员 PowerShell 里跑的白名单命令。 -->
        <div class="aboutRow"><span class="al">被杀软拦截</span>
          <span class="av human">打不开 / 报「含病毒」？那是 Defender 误报</span>
          <span class="acts">
            <button class="cbtn" id="abAvCopy" title="复制加入 Defender 白名单的命令（管理员 PowerShell 里粘贴运行）">📋</button>
            <button class="btn" id="abAvBtn" style="min-width:0;padding:var(--sp-1) 11px"
                    title="查看解决办法：把软件目录加进 Defender 白名单">🛡️ 怎么办</button>
          </span></div>
        <div class="avHelp" id="abAvHelp" hidden>
          <b>这是 Windows Defender 的误报，不是真的有毒。</b>
          本软件是 Python 打包的单文件程序，启动时要先把内置数据解压到临时目录，
          这个「自我解压」行为和某些病毒很像，容易被误拦（软件没有签名证书，更容易中招）。
          <ol>
            <li>右键开始菜单 → <b>终端(管理员)</b> / PowerShell(管理员)</li>
            <li>粘贴下面的命令回车（路径已替你填好，没报错就是成功）：<br>
              <code id="abAvCmd">Add-MpPreference -ExclusionPath "…"</code>
              <button class="cbtn" id="abAvCmdCopy" title="复制这条命令">📋</button></li>
            <li>重新双击 exe 即可。撤销用 <code>Remove-MpPreference</code>。</li>
          </ol>
          用 360 / 火绒等其它杀软的话，在它的「信任区 / 白名单」里把软件目录加进去即可。
        </div>
      </div>

      <h2>📜 上游更新动态</h2>
      <div class="card" id="ulCard"><div class="clgEmpty">读取中…</div></div>

      <h2>🗒️ 更新日志</h2>
      <div class="card updBar" id="updBar" style="display:none"></div>
      <div class="card" id="clgCard"><div class="clgEmpty">读取中…</div></div>

      <div class="foot">
        <div id="fileInfo">—</div>
        <div id="built">—</div>
      </div>

      <!-- 作者名片（云朵名片）：QQ 与寄语，复制按钮见 script 里的 bindAuthor() -->
      <div class="au1">
        <span class="seal">云朵出品</span>
        <div class="badge"><img src="__LOGO__" alt=""><i class="ring"></i></div>
        <div class="abody">
          <div class="atop">
            <span class="anm">云朵小铺</span>
            <span class="aver" id="auVer" title="软件版本">—</span>
          </div>
          <div class="asay">该软件为 <b>e 宝</b> 倾力制作，如有需求可以找我 💌</div>
          <div class="arow">
            <span class="qqbox"><span class="qlab">QQ</span><span class="qnum" id="auQQ">108563013</span></span>
            <button class="cbtn pri" id="auCopy">📋 复制 QQ</button>
            <span class="atip">加好友时说明来意，通过更快～</span>
          </div>
        </div>
      </div>
    </div>
   </div>
  </main>
</div>

</div>

<script src="/static/app.js?v=__ASSETV__"></script>
<div class="stgov" id="stgOv" style="display:none" onclick="if(event.target===this)closeStages()">
  <div class="stgbox" id="stgBox">
    <div class="stghead">
      <div><div class="stgtitle" id="stgTitle">—</div><div class="stgsub" id="stgSub">加载中…</div></div>
      <button class="stgx" id="stgX" title="关闭（也可按 Esc）">✕</button>
    </div>
    <div class="stgbody" id="stgBody"></div>
  </div>
</div>
<script>$('stgX').onclick=closeStages;</script>

<!-- 上游数据更新明细弹窗（复用关卡弹窗的遮罩样式） -->
<div class="stgov" id="diffOv" style="display:none" onclick="if(event.target===this)closeDiff()">
  <div class="stgbox" style="max-width:700px">
    <div class="stghead">
      <div><div class="stgtitle">🆕 官方数据更新明细</div><div class="stgsub" id="diffSub">—</div></div>
      <button class="stgx" id="diffX" title="关闭（也可按 Esc）">✕</button>
    </div>
    <div class="stgbody" id="diffBody"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end;padding:0 16px 14px">
      <button class="btn" id="diffLater">稍后再看</button>
      <button class="btn pri" id="diffApply">✓ 立即同步更新</button>
    </div>
  </div>
</div>
<script>$('diffX').onclick=closeDiff;</script>

<!-- 上游更新动态弹窗（历史台账：官方每次改了什么，可回看） -->
<div class="stgov" id="updOv" style="display:none" onclick="if(event.target===this)closeUpdLog()">
  <div class="stgbox" style="max-width:760px">
    <div class="stghead">
      <div><div class="stgtitle">📜 上游更新动态</div><div class="stgsub" id="updOvSub">—</div></div>
      <button class="stgx" id="updOvX" title="关闭（也可按 Esc）">✕</button>
    </div>
    <div class="stgbody" id="updOvBody"></div>
  </div>
</div>
<script>$('updOvX').onclick=closeUpdLog;</script>

<!-- 使用说明弹窗：首次打开软件自动弹一次，之后在「设置」页点开 -->
<div class="stgov" id="rmOv" style="display:none" onclick="if(event.target===this)closeReadme()">
  <div class="stgbox rmbox">
    <div class="stghead">
      <div>
        <div class="stgtitle">📖 使用说明</div>
        <div class="stgsub">云朵小铺 · 風雲社 ZE 通关奖励看板</div>
      </div>
      <button class="stgx" id="rmX" title="关闭（也可按 Esc）">✕</button>
    </div>
    <div class="stgbody rmdoc">
      <p>读取 <b>fys 官方客户端</b>写出的广播文件，结合風雲社官网公开数据，实时显示你当前所在服务器的
        地图、关卡，以及该关的<b>通关云点 / 通关龙晶</b>奖励与伤害达标门槛。</p>

      <div class="rmh"><i></i>怎么用</div>
      <ul>
        <li>双击 <code>FYS-Reward.exe</code> 启动（首次启动要解压，约 3~5 秒，耐心等一下）</li>
        <li>进游戏就行，<b>不用手动操作</b>：软件会自动定位你所在的服务器与地图</li>
        <li>想让它一直挂在屏幕上 → 左侧「屏幕覆盖」页打开开关</li>
      </ul>

      <div class="rmh"><i></i>运行环境</div>
      <ul>
        <li>Windows 10 / 11（64 位）；<b>无需安装 Python</b>，断网也能用（已内置完整地图数据）</li>
        <li>界面用系统自带的 WebView2（Win11 自带；Win10 若提示缺失，装个 Edge 即可）</li>
      </ul>

      <div class="rmh"><i></i>数据与更新</div>
      <ul>
        <li>首次运行会把内置数据释放到 exe 同目录的 <code>data\</code> 文件夹</li>
        <li>新图上线后想更新 → 「设置」页点 <b>立即同步</b>（约 10~30 秒，失败不影响现有数据）</li>
      </ul>
      <div class="rmkv"><span class="rk">rewards.json</span><span>通关奖励（云点 / 龙晶，按关卡）</span></div>
      <div class="rmkv"><span class="rk">maps.json</span><span>地图参数（管理员 / 提名 / 时段 / 价格 / 冷却）</span></div>
      <div class="rmkv"><span class="rk">infect.json</span><span>尸变参数（随机尸变 / 母体比例 / 倒计时）</span></div>
      <div class="rmkv"><span class="rk">mapcfg.json</span><span>地图参数全量（31 项 ConVar，用于识别 GitHub 上的参数改动）</span></div>
      <div class="rmkv"><span class="rk">knockback.json</span><span>击退系数</span></div>
      <div class="rmkv"><span class="rk">platform_mapnames.json</span><span>官方中文译名</span></div>

      <div class="rmh"><i></i>常见情形</div>
      <ul>
        <li>显示「未在服务器内」→ 还没进服，或 CS2 没运行</li>
        <li>显示「服务器查询无响应」→ 这台服的 UDP 查询没回包（可能已离开，也可能只是丢包：
          程序会自动重试 3 轮，并把最近 45 秒内查到的数据继续挂着显示，不会一闪一闪）</li>
        <li>显示「地图获取中…」→ 已确认连着服务器，只是地图还没查到，稍等即出</li>
        <li>显示「关卡待同步」→ 已认到地图但没读到关卡号，数值先按第 1 关显示，下表可查全部关卡</li>
        <li>认不出地图 → 把「设置」页下方「广播文件原文」的内容发给作者，即可按真实格式补规则</li>
        <li>屏幕覆盖点了却看不到小窗 → ① 游戏是<b>独占全屏</b>时置顶窗会被盖住，把游戏改成「无边框窗口」；
          ② 还是看不到就切到<b>「tkinter 透明」</b>（原生分层窗，不依赖显卡合成）——「屏幕覆盖」页启动按钮
          下方有「改用 tkinter 透明」一键按钮</li>
        <li>窗口打不开 / 白屏 → 删掉 <code>data\startup.log</code> 后重试；仍不行就把该日志发出来</li>
      </ul>

      <div class="rmh"><i></i>数值怎么读</div>
      <ul>
        <li>关卡表与地图库里的伤害数值是<b>达标门槛</b>：每造成该数值伤害，额外 +1 云点或龙晶
          （例：门槛 3w → 每打满 3 万伤害 +1），鼠标悬停可看原始值</li>
        <li>地图库标记：🔑 需要管理员 · 🙋 可被提名 · 🎲 随机尸变 · 🕒 限定时段 · 🌐 全天可玩</li>
        <li>分类筛选可多选，需<b>同时满足</b>（例如「无需管理员 + 全天可玩」）</li>
      </ul>

      <div class="rmh"><i></i>说明</div>
      <p style="opacity:.75">本软件为社区辅助工具，数据来自 GitHub 仓库 <code>fyscs/cs2</code>
        与風雲社官网公开接口，仅供查询与参考，与官方无隶属关系。</p>

      <div class="rmtip">💌 使用中遇到问题、想提建议，或想补充认图规则，都可以通过作者名片上的 QQ 找到我。</div>
      <div class="rmfoot"><button class="btn" id="rmOk">我知道了</button></div>
      <div class="rmend">云朵小铺 · e 宝 倾力制作</div>
    </div>
  </div>
</div>
<script>
$('rmX').onclick=closeReadme;
$('rmOk').onclick=closeReadme;
document.addEventListener('keydown',function(e){ if(e.key==='Escape'){ closeReadme(); closeStages(); closeUpdLog(); closeDiff(); } });
</script>

<!-- 窗口边缘缩放热区：拖这里 = 拖系统窗口边框（后端交回系统接管） -->
<div class="rz rz-n"  data-edge="t"></div>
<div class="rz rz-s"  data-edge="b"></div>
<div class="rz rz-w"  data-edge="l"></div>
<div class="rz rz-e"  data-edge="r"></div>
<div class="rz rz-nw" data-edge="tl"></div>
<div class="rz rz-ne" data-edge="tr"></div>
<div class="rz rz-sw" data-edge="bl"></div>
<div class="rz rz-se" data-edge="br"></div>
</body></html>
"""


def _resource_path(*names):
    """兼容源码运行与 PyInstaller onefile 的资源定位。
    依次找：源码目录 → _MEIPASS 解包根 → _MEIPASS/data（spec 把资源放这）→ exe 旁。"""
    import os
    import sys
    cands = [os.path.join(os.path.dirname(os.path.abspath(__file__)), *names)]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        cands.append(os.path.join(bundle, *names))
        cands.append(os.path.join(bundle, "data", *names))
    if getattr(sys, "frozen", False):
        cands.append(os.path.join(os.path.dirname(sys.executable), *names))
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[0]


_ASSETS = {"ver": None, "css": None, "js": None}


def _bg_data():
    """界面背景素材（_themeart 生成的图，见 bg_assets.py）。缺失就当没有。"""
    try:
        from bg_assets import BG_DATA
        return BG_DATA
    except Exception:                                   # noqa: BLE001
        return {}


def _subst(text, ver=""):
    """构建期占位符替换（HTML 与静态 JS 共用同一套）。

    ⚠ 主题清单 / 背景素材 / 轮询间隔以前只注入主页 HTML；JS 单独下发后必须在
    JS 上也替换一遍——漏了前端就会带着 "__THEMES__" 字面量运行，主题卡与背景
    整套失效（且不报错，很难看出来）。
    """
    import json
    text = text.replace("__VER__", str(ver or "").strip())
    text = text.replace("__THEMES__", json.dumps(THEMES, ensure_ascii=False))
    text = text.replace("__BGS__", json.dumps(_bg_data(), ensure_ascii=False,
                                              separators=(",", ":")))
    return text.replace("__POLL__", "1000")


def css_asset(ver=""):
    """/static/app.css 的正文（注入后缓存，进程内只算一次）。"""
    if _ASSETS["css"] is None:
        _ASSETS["css"] = _subst(ui_style.CSS, ver)
    return _ASSETS["css"]


def js_asset(ver=""):
    """/static/app.js 的正文。"""
    if _ASSETS["js"] is None:
        _ASSETS["js"] = _subst(ui_js.JS, ver)
    return _ASSETS["js"]


def asset_ver(ver=""):
    """静态资源版本号（内容 CRC32，8 位十六进制）。

    拼进 URL 的 ?v=，内容一变 URL 就变：老用户升级后不会拿旧样式配新 DOM，
    也让静态资源可以放心长缓存（服务端只对「v 匹配当前版本」的请求给长缓存）。
    """
    if _ASSETS["ver"] is None:
        b = (css_asset(ver) + js_asset(ver)).encode("utf-8")
        _ASSETS["ver"] = "%08x" % (zlib.crc32(b) & 0xFFFFFFFF)
    return _ASSETS["ver"]


def build_page(ver="", theme="E"):
    """把版本号、主题清单、背景素材与品牌 logo 注入页面。

    ver：当前版本号（如 "v2.5"），显示在侧栏标题「云朵小铺」旁。
    在构建时就地注入而不是让前端去 /api/about 取，是因为标题栏是首屏元素——
    走接口的话会有一瞬间空白，而且断网时取不到就整个版本号不见了。
    theme：保存的界面主题代码（E/F/G/H/N）。构建期预铺 <html data-theme>，
    首帧就是保存的主题色（不用等 JS 拉偏好）；N 时启动卡走夜幕星云样式。
    """
    import base64
    html = _subst(HTML, ver)
    th = str(theme or "E").strip().upper()[:1]
    if th not in ("E", "F", "G", "H", "N"):
        th = "E"
    if th != "E":
        html = html.replace('data-theme="E"', 'data-theme="%s"' % th, 1)
    if th == "N":
        html = html.replace('<div id="bootSplash"',
                            '<div id="bootSplash" class="bsDark"', 1)
    try:
        with open(_resource_path("logo_embed.png"), "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        html = html.replace("__LOGO__", "data:image/png;base64," + b64)
    except Exception:                                   # noqa: BLE001
        html = html.replace('<img src="__LOGO__" alt="">', "☁️")
    return html.replace("__ASSETV__", asset_ver(ver))


# ══════════════════════════ 屏幕覆盖小窗页面 ══════════════════════════
# 服务于 /overlay：透明无边框置顶窗口，只展示云点数值，配置走 /api/ovcfg
OVERLAY_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;overflow:hidden;user-select:none;
font:14px/1.45 "Segoe UI","Microsoft YaHei",sans-serif}
#card{position:fixed;left:4px;top:4px;border-radius:16px;padding:9px 28px 9px 16px;
background:linear-gradient(135deg,rgba(91,58,94,var(--bg,.55)),
rgba(44,31,58,calc(var(--bg,.55)*1.06)));
display:flex;flex-direction:column;gap:1px;box-shadow:0 8px 28px rgba(0,0,0,.35)}
/* 标题行（粉色渐变条）/ 状态行（card・skin 布局专属，与样板图一致） */
.hd{display:flex;align-items:baseline;gap:8px;font-weight:800;font-size:.74em;
letter-spacing:.4px;white-space:nowrap;
margin:-9px -28px 3px -16px;padding:8px 30px 6px 16px;border-radius:15px 15px 0 0;
background:linear-gradient(90deg,rgba(240,98,146,.32),rgba(240,98,146,.05))}
.hd .srv{opacity:.66;font-weight:700}
.ft{font-size:.66em;opacity:.62;font-weight:700;white-space:normal;line-height:1.3;margin-top:3px}
.sep{white-space:nowrap;opacity:.38;letter-spacing:1px;font-size:.85em}
.r{display:flex;align-items:baseline;justify-content:space-between;gap:14px;white-space:nowrap}
.r .lb{opacity:.66;font-weight:600}
.r .vv{font-weight:800;font-family:"Arial Rounded MT Bold","Segoe UI",sans-serif;
font-variant-numeric:tabular-nums}
.r .vv.g{color:#ffce7a}
/* 未进服/未响应：只留一行紧凑状态，不再摆一列「—」 */
.r.st{opacity:.9;gap:7px;justify-content:flex-start}
.r.st .dot{width:.5em;height:.5em;border-radius:50%;background:currentColor;opacity:.75;flex:none}
.r .sm{opacity:.8;font-weight:700}
/* ── 布局 B：紧凑单行胶囊 ── */
#card.compact{border-radius:99px;padding:8px 32px 8px 18px;flex-direction:row;
align-items:center;gap:11px;white-space:nowrap}
#card.compact .cm{font-weight:800;letter-spacing:.2px}
#card.compact .cs{opacity:.6;font-size:.82em}
#card.compact .cb{font-weight:800;font-variant-numeric:tabular-nums}
#card.compact .cb .g,#card.compact .cb.g{color:#ffce7a}
#card.compact .dot{display:inline-block;width:4px;height:4px;border-radius:50%;
background:currentColor;opacity:.55;flex:none}
/* ── 布局 C：带地图图标 ── */
#card.iconic{flex-direction:row;padding:0;align-items:stretch;overflow:hidden;gap:0}
#card.iconic .thumb{flex:none;width:64px;display:flex;flex-direction:column;align-items:center;
justify-content:center;gap:2px;background:linear-gradient(160deg,rgba(255,255,255,.10),rgba(255,255,255,.03))}
#card.iconic .thumb .em{font-size:30px;filter:drop-shadow(0 2px 6px rgba(0,0,0,.5))}
/* 地图封面（v2.3）：cover\<地图名>.jpg，取不到（图库没这张 / 包里没带 cover\）
   时 onerror 后隐藏，露出下面原本的 emoji 图标 —— 永远不会出现破图占位 */
#card.iconic .thumb .cv{display:block;width:56px;height:34px;object-fit:cover;
border-radius:5px;margin-bottom:2px;box-shadow:0 1px 5px rgba(0,0,0,.45)}
#card.iconic .thumb .lv{font-size:var(--fs-xs);opacity:.65;letter-spacing:1px;text-align:center;
max-width:56px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#card.iconic .col{padding:7px 13px 9px;display:flex;flex-direction:column;gap:1px}
#card.iconic .m1{font-weight:800;white-space:nowrap}
#card.iconic .m2{font-size:.72em;opacity:.62;white-space:nowrap}
#card.iconic .nums{display:grid;grid-template-columns:repeat(2,auto);
gap:5px 18px;margin-top:4px}
#card.iconic .n .a{font-size:.6em;opacity:.62;letter-spacing:.4px}
#card.iconic .n .b{font-weight:800;font-variant-numeric:tabular-nums}
#card.iconic .n .b.g{color:#ffce7a}
/* ── 布局 D：自定义底图（共用卡片版式；LOGO 角标已按反馈移除） ── */
/* 底图放在 ::before 层上单独设 opacity：真半透明（能看见桌面/游戏），
   文字层保持不透明，再用阴影保证可读性。以前是「暗化蒙版」——
   图片整体还是不透明，滑杆只调明暗，玩家反馈「看不到桌面」（2026-11 修）。 */
#card.skin{border:1px solid rgba(255,255,255,.28);background:transparent;
text-shadow:0 1px 2px rgba(0,0,0,.92),0 0 7px rgba(0,0,0,.55)}
#card.skin::before{content:'';position:absolute;inset:0;border-radius:inherit;
background-image:var(--skin-img,none);background-size:cover;background-position:center;
opacity:var(--skin-a,.38);pointer-events:none;z-index:0}
#card.skin.nobg{border-style:dashed;border-color:rgba(255,255,255,.42)}
#card.skin .veil{position:absolute;inset:0;z-index:0;
background:linear-gradient(180deg,rgba(10,6,12,.16),rgba(10,6,12,.6));pointer-events:none}
#card.skin>#x{z-index:2}
#card.skin #rows{position:relative;z-index:1}
#x{position:absolute;right:2px;top:-2px;appearance:none;border:none;background:transparent;
color:rgba(255,255,255,.55);font-size:var(--fs-md);cursor:pointer;width:22px;height:20px;
border-radius:6px;z-index:2;opacity:0;transition:opacity .15s}
#card:hover #x{opacity:1}
#x:hover{color:#fff;background:rgba(255,255,255,.15)}
</style></head><body>
<div id="card" class="pywebview-drag-region">
  <button id="x" title="关闭覆盖">×</button>
  <div id="rows"></div>
</div>
<script>
/* last = 已上报的小窗尺寸（'WxH'），全局一份：ovResize 用它去重，别在别处再声明 */
var FLD=[], CFG=null, last='';
/* 伤害/分数换算成万（≥1000 才换算：8000→0.8w，24000→2.4w），
   与主界面 wan() / 直播文本 txt 同规则 */
function wan(v){
  if(v===null||v===undefined||v==='') return '—';
  var nv=+v;
  if(isNaN(nv)) return String(v);
  if(nv<1000) return String(nv);
  var x=Math.round(nv/10000*10)/10;
  return (x===Math.round(x)?Math.round(x):x)+'w';
}
function g(k,d){
  var c=d.current||{};
  if(k==='map')  return d.map||'—';
  if(k==='mapcn')return d.mapcn||'—';
  if(k==='stage')return d.stage?('第 '+d.stage+' / '+(d.total_stages||'?')+' 关'):'关卡 —';
  if(k==='passes')  return wrap(k, (c.rankPasses!==null&&c.rankPasses!==undefined)?c.rankPasses:'—', d);
  if(k==='dmgrank') return wrap(k, wan(c.rankDamage), d);
  if(k==='econ')    return wrap(k, (c.econPasses!==null&&c.econPasses!==undefined)?c.econPasses:'—', d);
  if(k==='dmgecon') return wrap(k, wan(c.econDamage), d);
  return '—';
}
function wrap(k, base, d){
  var x=extra(k, d);
  return x ? (base + x) : base;
}
function extra(k, d){
  var c=d.current||{}, lv=d.live||{};
  if(!lv || lv.dmg===undefined) return '';
  if(k==='passes') return (lv.rankPts!==null&&lv.rankPts!==undefined)?('（'+lv.rankPts+'↑）'):'';
  if(k==='econ')   return (lv.econPts!==null&&lv.econPts!==undefined)?('（'+lv.econPts+'↑）'):'';
  if(k==='dmgrank'||k==='dmgecon'){
    var ratio=(k==='dmgrank')?c.rankDamage:c.econDamage;
    if(!ratio||ratio<=0) return '';
    var need=ratio-(lv.dmg%ratio);
    return '（'+wan(need)+'）';
  }
  return '';
}
/* ── 布局预设（v2.2）：card 默认卡片 / compact 紧凑单行 / iconic 地图图标 / skin 自定义底图 ── */
function esc2(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
var OV_EMOJI=[['cabinet','🏛️'],['backrooms','🌀'],['insomnia','🌙'],['alien','🛸'],
  ['hospital','🏥'],['metro','🚇'],['motel','🛎️'],['escape','🏃'],['zombie','🧟'],
  ['department','🏬'],['office','🏢'],['capital','🏙️'],['factory','🏭'],['city','🌆'],
  ['ice','❄️'],['fire','🔥'],['forest','🌲'],['lake','🌊'],['mountain','⛰️'],
  ['island','🏝️'],['sus','🕵️'],['hotel','🏨'],['church','⛪'],['school','🏫'],
  ['train','🚆'],['ship','🚢'],['mine','⛏️'],['cave','🕳️'],['lab','🧪'],['space','🚀']];
function mapEmoji(n){ n=String(n||'').toLowerCase();
  for(var i=0;i<OV_EMOJI.length;i++){ if(n.indexOf(OV_EMOJI[i][0])>=0) return OV_EMOJI[i][1]; }
  return '🗺️'; }
function mapTag(n){ n=String(n||'').replace(/^ze[_-]/i,'').toUpperCase();
  return (n.slice(0,8))||'MAP'; }
function lay(){ return (CFG&&CFG.layout)||'card'; }
/* 封面图（v2.3）：读 exe 旁 cover\<地图名>.jpg；取不到就把 img 藏掉，露出底下的 emoji。
   设置页预览与真实覆盖窗各留一份同名定义 —— 两个页面不共享脚本，少一份就会在
   渲染 iconic 时抛 ReferenceError，整窗卡在「读取中…」（实测踩过）。 */
function ovCover(n, w){
  n=String(n||'').toLowerCase();
  if(!n) return '';
  var s=w?(' style="width:'+w+'px;height:'+(Math.round(w*0.586))+'px"'):'';
  return '<img class="cv" alt="" src="/cover/'+encodeURIComponent(n)+'.jpg"'+
         s+' onerror="this.style.display=\'none\'" '+
         'onload="var e=this.nextElementSibling;if(e)e.style.display=\'none\'">';
}
/* 布局类名 / 底图 / LOGO 角标：loadCfg 与 apply 都会调（幂等，每次全量重建） */
function setCardCls(){
  var c=document.getElementById('card');
  c.className='pywebview-drag-region '+(lay()==='card'?'':lay());
  if(lay()==='skin'&&CFG.skin){
    /* 底图透明度 = 真透明：op 越大层越透，桌面/游戏透得过来（与滑杆字面一致）；
       ?t=mtime 换图后立即失效缓存。文字在不透明的前景层，另有 text-shadow。 */
    var a=1-Math.max(20,Math.min(95,+(CFG.skin_op!=null?CFG.skin_op:62)))/100;
    c.style.setProperty('--skin-a', a.toFixed(3));
    c.style.setProperty('--skin-img','url(/skin/'+
      encodeURIComponent(CFG.skin)+'?t='+(CFG.skin_ts||0)+')');
    c.style.backgroundImage='';
    c.classList.remove('nobg');
  }else{
    c.style.backgroundImage='';
    c.style.removeProperty('--skin-a');
    c.style.removeProperty('--skin-img');
    c.classList.toggle('nobg', lay()==='skin');   /* 没传底图：虚线边 + 提示行 */
  }
}
/* resize 必须是全局的：apply 里的闭包 ovDraw 也要用它（v2.3 优化 6）。
   上一帧的尺寸记在顶部声明的全局 last 里（这里不要再 var 一遍，重复声明
   只是徒增困惑）。 */
function ovResize(){
  var card=document.getElementById('card');
  var h=card.offsetHeight+8, w=Math.min(560,Math.max(150,card.offsetWidth+8));
  if(last!==w+'x'+h){
    last=w+'x'+h;
    fetch('/api/ctl?do=ovresize&w='+w+'&h='+h,{cache:'no-store'}).catch(function(){});
  }
}
function apply(d){
  if(!CFG) return;
  var rows=document.getElementById('rows'), html='';
  var small=Math.round(CFG.size*0.62);
  var L=lay();
  rows.style.color=CFG.color;
  /* 卡片根字号跟着 CFG.size 走：.hd/.sep/.ft 都是 em 单位，
     不设的话缩到 8px 时标题会比数值还大。 */
  var _card=document.getElementById('card');
  if(_card) _card.style.fontSize=CFG.size+'px';
  setCardCls();
  /* 未进服 / 查询不到：一行状态就好（以前会把「地图 —、关卡 —…」整列摆出来） */
  if(!d || !d.map){
    html='<div class="r st" style="color:'+CFG.color+'">'+
      '<span class="dot"></span>'+
      '<span class="sm" style="font-size:'+small+'px">'+
      esc2((d&&d.state_text)||'未进入服务器')+'</span></div>';
    ovDraw(rows, d, html); return;
  }
  var show=CFG.show||{};
  if(L==='compact'){
    /* 单行胶囊：地图 · 译名 · 关卡 · 云点 13/2.4w · 龙晶 10/3.5w */
    var s=[];
    if(show.map!==false)    s.push('<span class="cm">'+esc2(d.map)+'</span>');
    if(show.mapcn!==false&&d.mapcn) s.push('<span class="cs">'+esc2(d.mapcn)+'</span>');
    if(show.stage!==false&&d.stage)
      s.push('<span class="cs">第 '+d.stage+' / '+(d.total_stages||'?')+' 关</span>');
    var pn=show.passes!==false, dn=show.dmgrank!==false;
    if(pn||dn) s.push('<span class="cb">云点 '+
      (pn?'<span class="g">'+esc2(g('passes',d))+'</span>':'')+((pn&&dn)?'/':'')+
      (dn?esc2(g('dmgrank',d)):'')+'</span>');
    var en=show.econ!==false, dgn=show.dmgecon!==false;
    if(en||dgn) s.push('<span class="cb">龙晶 '+
      (en?'<span class="g">'+esc2(g('econ',d))+'</span>':'')+((en&&dgn)?'/':'')+
      (dgn?esc2(g('dmgecon',d)):'')+'</span>');
    html=s.length?s.join('<i class="dot"></i>')
      :'<span class="cs">屏幕覆盖：请在主窗口选择显示内容</span>';
    ovDraw(rows, d, html); return;
  }
  if(L==='iconic'){
    /* 左地图图标 + 右数值区：用内联 flex 行布局，不依赖 #card.iconic 类，
       保证真实覆盖窗与设置页预览完全一致（之前偶发图标跑到上方）。
       字号全部跟随 CFG.size 滑杆，解决「地图图标布局改不了字号」。 */
    var sz=CFG.size||30, C=CFG.color;
    var spx=Math.max(6,Math.round(sz*0.62));          /* 地图名 / 主文本 */
    var lpx=Math.max(5,Math.round(sz*0.32));           /* 小标签 */
    var epx=Math.max(12,Math.round(sz*0.9));           /* 地图 emoji 图标 */
    var m2=[];
    if(show.mapcn!==false&&d.mapcn) m2.push(esc2(d.mapcn));
    if(show.stage!==false&&d.stage)
      m2.push('第 '+d.stage+' / '+(d.total_stages||'?')+' 关');
    var nums='';
    /* 金色 = 通关系列（通关云点 / 通关龙晶），伤害系列保持白字 */
    [['passes','通关云点','g'],['dmgrank','伤害云点',''],
     ['econ','通关龙晶','g'],['dmgecon','伤害龙晶','']].forEach(function(nd){
      if(show[nd[0]]!==false){
        var col=nd[2]?'#ffce7a':C;
        nums+='<div class="n"><div class="a" style="font-size:'+lpx+'px">'+nd[1]+
              '</div><div class="b '+(nd[2]?'g':'')+'" style="font-size:'+sz+'px;color:'+col+'">'+
              esc2(g(nd[0],d))+'</div></div>';
      }
    });
    var m1=show.map!==false?esc2(d.map):(show.mapcn!==false&&d.mapcn?esc2(d.mapcn):'');
    html='<div style="display:flex;align-items:stretch;overflow:hidden;color:'+C+'">'+
      '<div class="thumb">'+ovCover(d.map)+
        '<span class="em" style="font-size:'+epx+'px">'+mapEmoji(d.map)+'</span>'+
        '<span class="lv">'+esc2(mapTag(d.map))+'</span></div>'+
      '<div class="col">'+
        '<div class="m1" style="font-size:'+spx+'px">'+(m1||'—')+'</div>'+
        (m2.length?'<div class="m2" style="font-size:'+Math.max(6,Math.round(sz*0.5))+'px">'+m2.join(' · ')+'</div>':'')+
        (nums?'<div class="nums">'+nums+'</div>':'')+'</div></div>';
    ovDraw(rows, d, html); return;
  }
  /* card / skin：默认卡片版式（标题行 + 状态行与样板图一致） */
  var SEP='<div class="sep" style="color:'+CFG.color+'">━━━━━━━━━━━━━━</div>';
  var srvn=(d.server&&d.server.server_name)?esc2(d.server.server_name):'';
  var head='<div class="hd" style="color:'+CFG.color+'"><span>☁️ 云朵小铺</span>'+
    (srvn?'<span class="srv">'+srvn+'</span>':'')+'</div>';
  var A=['map','mapcn','stage'], B=['passes','dmgrank','econ','dmgecon'];
  var name={map:'地图',mapcn:'译名',stage:'当前关卡',
    passes:'通关云点',dmgrank:'伤害云点',econ:'通关龙晶',dmgecon:'伤害龙晶',
    };
  function row(k,f,gold){
    var v=String(g(k,d));
    html+='<div class="r" style="color:'+CFG.color+'">'+
      '<span class="lb" style="font-size:'+small+'px">'+f+'</span>'+
      '<span class="vv'+(gold?' g':'')+'" style="font-size:'+CFG.size+'px">'+esc2(v)+'</span></div>';
  }
  var ha=false, hb=false;
  A.forEach(function(k){ if(show[k]!==false){ row(k,name[k]); ha=true; } });
  B.forEach(function(k){ if(show[k]!==false){ hb=true; } });
  if(ha&&hb) html+=SEP;
  B.forEach(function(k){ if(show[k]!==false) row(k,name[k],k==='passes'||k==='econ'); });
  if(!html){
    html='<div class="r st" style="color:'+CFG.color+'">'+
      '<span class="sm" style="font-size:'+small+'px">屏幕覆盖：请在主窗口选择显示内容</span></div>';
  }else{
    if(L==='skin'&&!CFG.skin)
      html+='<div class="ft" style="color:'+CFG.color+'">🖼️ 在设置页上传底图，'
        +'这里就显示你的图片</div>';
    html=head+html;
  }
  ovDraw(rows, d, html);
}
/* 统一出口（v2.3 优化 6）：配置 rev + 数据指纹都没变就整棵 DOM 不重建。
   原来每秒都把 rows.innerHTML 整块重排一遍 —— WebView2 里就是一次可见的闪动，
   连封面图都会重新解码；服务器状态每秒刷一次、但内容常常一模一样。 */
var LASTSIG='';
function ovDraw(rows, d, html){
  var show=CFG.show||{};
  var sig=[CFG.rev,CFG.color,CFG.size,CFG.bg,CFG.layout,CFG.skin,CFG.skin_op,
           JSON.stringify(show)].join('|')+'|'+(
    d?[d.map,d.mapcn,d.stage,d.total_stages,d.server&&d.server.server_name,
       d.state_text,d.mapTimestamp||0,g('passes',d),g('dmgrank',d),
       g('econ',d),g('dmgecon',d)].join(','):'none');
  if(sig!==LASTSIG){ LASTSIG=sig; rows.innerHTML=html; }
  /* ⚠ ovResize 必须在写完 innerHTML 之后调：它量的是卡片当前高度，
     放在前面就量到上一帧的旧高度 → 小窗尺寸慢一拍（进服那一刻卡片从
     一行状态变成整张卡片，窗口要等下一轮轮询才跟上，内容先被裁一截）。
     每轮都调（不受 sig 影响）是为了自愈：某次 ovresize 请求丢了能补上。 */
  ovResize();
}
/* 配置拉取：2 秒一轮，也要 inflight 守卫（原来只给 ovtick 加了，这里没有；
   顺便删掉对不存在元素 #status 的死查询） */
var cfgInflight=false, lastCfgRev=-1;
function loadCfg(){
  if(cfgInflight) return null;      /* null：本轮没发请求（调用方要判一下） */
  cfgInflight=true;
  return fetch('/api/ovcfg',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
    FLD=d.fields||[]; CFG=d.cfg;
    /* rev 没变说明配置一个字节都没动，连底色/类名都不用重设（优化 6） */
    if(lastCfgRev!==(CFG.rev||0)){
      lastCfgRev=CFG.rev||0;
      document.getElementById('card').style.setProperty('--bg',CFG.bg);
      setCardCls();
    }
  }).catch(function(){}).then(function(){ cfgInflight=false; });
}
document.getElementById('x').addEventListener('mousedown',function(e){ e.stopPropagation(); });
document.getElementById('x').onclick=function(){ fetch('/api/ctl?do=ovclose',{cache:'no-store'}).catch(function(){}); };
/* 轮询：上一发没回来就跳过（A2S 重试时一次可能要几秒，并发发出去会乱序覆盖） */
var ovinflight=false;
function ovtick(){
  /* OV_IDLE 由 fetch 回来的数据决定（见 ovtick 下方 then） */
  if(ovinflight) return;
  ovinflight=true;
  fetch('/api/status',{cache:'no-store'})
    .then(function(r){return r.json();})
    .then(function(d){
      /* 在服内（有地图）= 需要秒级跟手；CS2 没运行时降频，省 CPU */
      OV_IDLE = !(d && d.map) && !!(d && d.server && d.server.game_running === false);
      apply(d);
    })
    .catch(function(){})
    .then(function(){ ovinflight=false; });
}
/* 首个配置到手就立刻取一次数据：原来是硬等 setInterval 的 1 秒，
   小窗开出来先摆 1 秒「读取中…」（尺寸也还是建窗时的 360×200）*/
var p0=loadCfg(); if(p0&&p0.then) p0.then(function(){ ovtick(); });
/* 轮询节流（2026-11-15）：在服内 1 秒一刷；CS2 没运行时降到 6 秒，
   只是等心跳，没必要每秒唤醒 WebView。配置 2 秒 → 每 4 次 tick 一次。 */
var OV_IDLE=false, OV_T=0;
function ovLoop(){
  clearTimeout(OV_T);
  ovtick();
  OV_T=setTimeout(ovLoop, OV_IDLE?6000:1000);
}
setInterval(loadCfg,2000);   /* 配置很小：保持 2 秒，改颜色/字号后小窗不用等节流 */
ovLoop();
document.getElementById('rows').innerHTML=
  '<div class="r st" style="color:#fff"><span class="dot"></span>'+
  '<span class="sm" style="font-size:18px">读取中…</span></div>';
</script></body></html>
"""

# -*- coding: utf-8 -*-
"""第二批可爱风 HTML 样板（可爱F~K）。

   与上一批（可爱A~E，偏配色）不同：这批改的是**造型/贴纸/图案层面**——
   云朵凸顶、胶带粘贴、卡通无缝图案底、贴纸描边、毛绒虚线边、彩虹渐变玻璃。
   全部默认停在「服务器」主页，便于横向对比；侧栏可点着切页。
   用法：python _cute_mock_gen2.py [--shot]
"""
import base64, json, os, re, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
SNAP = os.path.join(D, '_snap_app.html')
OUTD = os.path.join(D, '可爱样板-HTML')
SHOT = os.path.join(D, '验证截图-界面巡检')
CUTEART = os.path.join(D, '_cuteart')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
os.makedirs(OUTD, exist_ok=True)


def data_uri(p):
    mime = 'image/png' if p.lower().endswith('.png') else 'image/jpeg'
    return 'data:%s;base64,%s' % (mime, base64.b64encode(open(p, 'rb').read()).decode('ascii'))


PAT = data_uri(os.path.join(CUTEART, 'pat.jpg'))      # 卡通无缝图案（粉+薄荷）
SCENE = data_uri(os.path.join(CUTEART, 'scene.jpg'))  # 小兔小猫坐云朵场景


def vars_block(v):
    keys = ['bg', 'panel', 'panel2', 'zebra', 'thead', 'side', 'ink', 'ink2', 'muted', 'line',
            'accent', 'soft', 'softline', 'sl69', 'sl40', 'good', 'goodsoft', 'glow',
            'blob1', 'blob2', 'radius', 'rsm']
    return 'html[data-theme]{' + ''.join('--%s:%s;' % (k, v[k]) for k in keys) + '}'


# 所有风格共用的底子：导航胶囊 / 按钮 / 表格 / 样板角标 / 漂浮贴纸 / 预览占位
BASE = """
.card{position:relative}
/* 侧栏 + 导航 */
.side{box-shadow:6px 0 0 var(--sl40)!important}
.stop{border-bottom:3px dashed var(--softline)!important}
.sname{font-weight:900!important}
.nav{border:3px solid transparent!important;border-radius:999px!important;
  transition:transform .16s cubic-bezier(.34,1.7,.5,1),background .16s!important}
.nav:hover{transform:translateX(4px)}
.nav.on{background:var(--panel)!important;border-color:var(--softline)!important;
  box-shadow:3px 4px 0 var(--sl69)!important;transform:translateX(4px)}
/* 按钮 */
.btn{border:3px solid var(--softline)!important;border-radius:999px!important;
  box-shadow:3px 4px 0 var(--sl69)!important;font-weight:800!important;
  transition:transform .12s,box-shadow .12s!important}
.btn:hover{transform:translate(-1px,-1px);box-shadow:5px 6px 0 var(--sl69)!important}
.pill{border:3px solid var(--softline)!important;border-radius:999px!important;
  box-shadow:3px 4px 0 var(--sl69)!important;background:var(--panel)!important;
  font-weight:800!important}
/* 表格 / 输入 */
.tbl th{background:var(--thead)!important;font-weight:900!important}
.tbl td,.tbl th{border-color:var(--softline)!important}
input[type=text],input[type=search],select{
  border:3px solid var(--softline)!important;border-radius:999px!important}
/* 样板角标 */
#mkBadge{position:fixed;right:14px;top:50px;z-index:99;font:800 12px/1 var(--disp);
  color:#fff;background:var(--accent);padding:9px 15px;border-radius:999px;
  box-shadow:0 6px 18px rgba(0,0,0,.16);letter-spacing:.5px;pointer-events:none}
#mkBadge b{font-size:13.5px}
/* 漂浮贴纸 */
#mkDeco{position:fixed;inset:0;pointer-events:none;z-index:6;overflow:hidden}
#mkDeco i{position:absolute;font-style:normal;opacity:.45;
  filter:drop-shadow(0 6px 10px rgba(0,0,0,.10));animation:mkFloat 7s ease-in-out infinite}
#mkDeco i:nth-child(2n){animation-duration:9s;animation-delay:-1.6s}
#mkDeco i:nth-child(3n){animation-duration:11s;animation-delay:-3.4s}
@keyframes mkFloat{0%,100%{transform:translateY(0) rotate(-6deg)}
  50%{transform:translateY(-15px) rotate(8deg)}}
/* 预览页占位 */
#mkPreNote{display:none;position:absolute;inset:0;align-items:center;justify-content:center;
  flex-direction:column;gap:10px;color:var(--muted);font:700 15px var(--disp);text-align:center}
#view-pre.on #mkPreNote{display:flex}
"""

S = {}

# ═════════ F 云朵泡芙：卡片顶上坐着云朵 ═════════
S['F'] = dict(
    name='云朵泡芙', emoji='☁️', deco=['☁️', '🫧', '💭', '🌤️', '🐑', '✨'],
    v=dict(bg='#f3f9ff', panel='#ffffff', panel2='#f7fbff', zebra='#fbfdff', thead='#e4f2ff',
           side='#eaf6ff', ink='#2b4a66', ink2='#446b8d', muted='#89a7c2', line='#cfe8ff',
           accent='#5aa9ec', soft='#e8f4ff', softline='#93c9f3',
           sl69='rgba(147,201,243,.69)', sl40='rgba(147,201,243,.40)', good='#3f9ae0',
           goodsoft='#e9f6ff', glow='rgba(90,169,236,.18)', blob1='#e2f1ff', blob2='#f1f9ff',
           radius='30px', rsm='18px'),
    js="""(function(){
      var cs=document.querySelectorAll('.card,.libList,.libDetail,.themePal');
      for(var i=0;i<cs.length;i++){
        if(cs[i].querySelector(':scope > .mkCl')) continue;
        var c=document.createElement('span'); c.className='mkCl';
        c.innerHTML='<i></i><i></i><i></i>';
        cs[i].appendChild(c);
      }
    })();""",
    css="""
.main,.content{background:
  radial-gradient(circle at 12% 9%,rgba(255,255,255,.96) 0 46px,transparent 47px),
  radial-gradient(circle at 19% 6%,rgba(255,255,255,.96) 0 33px,transparent 34px),
  radial-gradient(580px 360px at 8% 0%,#e5f3ff,transparent 72%),
  radial-gradient(540px 330px at 96% 4%,#f0f8ff,transparent 72%),var(--bg)!important}
.side{background:linear-gradient(180deg,#eef8ff,#e3f1ff)!important}
/* 卡片：软胖大圆角 + 云朵凸顶 + 柔和云影（不用硬投影） */
.card,.libList,.libDetail,.themePal,.syncbox,.fxcard,.clgvw{
  border:3px solid var(--softline)!important;border-radius:34px 34px var(--radius) var(--radius)!important;
  box-shadow:0 12px 26px rgba(147,201,243,.30),inset 0 2px 0 rgba(255,255,255,.9)!important;
  overflow:visible!important}
.mkCl{position:absolute;left:26px;top:-21px;display:flex;align-items:flex-end;
  pointer-events:none;z-index:3}
.mkCl i{display:block;background:#fff;border:3px solid var(--softline);border-radius:50%;
  box-shadow:inset 0 -3px 0 rgba(147,201,243,.25)}
.mkCl i:nth-child(1){width:29px;height:29px;margin-right:-10px;margin-bottom:1px}
.mkCl i:nth-child(2){width:44px;height:44px;z-index:2}
.mkCl i:nth-child(3){width:25px;height:25px;margin-left:-9px;margin-bottom:1px}
.sname{color:var(--accent)}
.nav.on{background:#fff!important}
.pill i{box-shadow:0 0 0 5px rgba(90,169,236,.18)}
""")

# ═════════ G 草莓手账：胶带粘贴 + 格纹纸 ═════════
S['G'] = dict(
    name='草莓手账', emoji='🍓', deco=['🍓', '🎀', '🧸', '💗', '🍰', '🖍️'],
    v=dict(bg='#fff8f6', panel='#fffdfc', panel2='#fff9fb', zebra='#fffbfa', thead='#ffe9ef',
           side='#fff1f0', ink='#5a3b3b', ink2='#7f5656', muted='#b18d8d', line='#ffd9df',
           accent='#f26d8d', soft='#ffeaef', softline='#f79cb4',
           sl69='rgba(247,156,180,.69)', sl40='rgba(247,156,180,.40)', good='#e0557f',
           goodsoft='#fff0f4', glow='rgba(242,109,141,.15)', blob1='#ffe4ea', blob2='#fff0f3',
           radius='14px', rsm='10px'),
    js="""(function(){
      var cs=document.querySelectorAll('.card,.libList,.libDetail,.themePal');
      var cols=['rgba(255,214,224,.92)','rgba(206,234,253,.92)','rgba(215,246,228,.92)'];
      for(var i=0;i<cs.length;i++){
        var el=cs[i];
        if(el.querySelector(':scope > .mkTape')) continue;
        /* 胶带要跨在卡片边线上（top/bottom 取负值），压在框内会盖住标题 */
        var t1=document.createElement('span'); t1.className='mkTape';
        t1.style.cssText='background:'+cols[i%3]+';transform:rotate(-30deg);left:-26px;top:-15px';
        var t2=document.createElement('span'); t2.className='mkTape';
        t2.style.cssText='background:'+cols[(i+1)%3]+';transform:rotate(27deg);right:-26px;bottom:-14px';
        el.appendChild(t1); el.appendChild(t2);
      }
    })();""",
    css="""
.main,.content{background:
  repeating-linear-gradient(0deg,rgba(247,156,180,.10) 0 1px,transparent 1px 25px),
  repeating-linear-gradient(90deg,rgba(147,201,243,.10) 0 1px,transparent 1px 25px),
  linear-gradient(180deg,#fffaf8,#fff5f3)!important}
.side{background:linear-gradient(180deg,#fff3f2,#ffebec)!important}
/* 卡片：方一点 + 胶带粘贴 + 虚线缝纫边 */
.card,.libList,.libDetail,.themePal,.syncbox,.fxcard,.clgvw{
  border:2.5px dashed var(--softline)!important;border-radius:14px!important;
  box-shadow:4px 5px 0 rgba(247,156,180,.42),0 10px 20px rgba(210,150,160,.12)!important;
  overflow:visible!important}
.card::after{content:'';position:absolute;inset:5px;border:1px dotted var(--softline);
  border-radius:9px;pointer-events:none;opacity:.55}
.mkTape{position:absolute;width:96px;height:27px;pointer-events:none;z-index:4;
  box-shadow:0 2px 7px rgba(120,90,90,.16);
  -webkit-mask:linear-gradient(90deg,transparent 0,#000 6px,#000 calc(100% - 6px),transparent);
  mask:linear-gradient(90deg,transparent 0,#000 6px,#000 calc(100% - 6px),transparent)}
.card h2{color:var(--accent)}
.tbl th{background:var(--thead)!important}
""")

# ═════════ H 卡通图鉴：卡通无缝图案铺底 + 场景图点缀 ═════════
S['H'] = dict(
    name='卡通图鉴', emoji='🐰', deco=['🐰', '🐱', '🌸', '🍡', '🎈', '⭐'],
    v=dict(bg='#fff7fb', panel='#fffefd', panel2='#fffaFd', zebra='#fffcfd', thead='#ffe8f3',
           side='#fff0f7', ink='#543a4a', ink2='#7a5568', muted='#b08d9e', line='#ffd5e8',
           accent='#ef7fb2', soft='#ffeaf4', softline='#8fd9c4',
           sl69='rgba(143,217,196,.69)', sl40='rgba(143,217,196,.40)', good='#57bfa4',
           goodsoft='#eafaf5', glow='rgba(239,127,178,.16)', blob1='#ffe3f0', blob2='#e8fbf5',
           radius='24px', rsm='15px'),
    js="""(function(){
      /* 贴到卡片上会盖住表格数据，改成页面右下角一张固定的场景卡（与左下角贴纸呼应） */
      if(document.getElementById('mkScene')) return;
      var d=document.createElement('div'); d.id='mkScene';
      d.innerHTML='<span>☁️ 云朵小铺</span>';
      document.body.appendChild(d);
    })();""",
    css="""
/* 页面底：卡通无缝图案 + 白纱压淡 */
.main,.content{background:
  linear-gradient(rgba(255,252,254,.80),rgba(255,250,253,.85)),
  url("__PAT__") !important;
  background-repeat:repeat!important;background-size:auto,340px 340px!important}
.side{background:linear-gradient(180deg,rgba(255,244,249,.93),rgba(255,238,246,.95)),
  url("__PAT__") !important;background-size:auto,300px 300px!important;background-repeat:repeat!important}
/* 卡片：粉边 + 薄荷硬投影 + 右下小场景贴图 */
.card,.libList,.libDetail,.themePal,.syncbox,.fxcard,.clgvw{
  border:3px solid var(--softline)!important;border-radius:var(--radius)!important;
  box-shadow:5px 6px 0 rgba(239,127,178,.35),0 12px 24px rgba(180,140,160,.12)!important;
  background:rgba(255,255,255,.94)!important;overflow:hidden!important}
.card::before{content:'';position:absolute;left:0;top:0;width:100%;height:8px;
  background:linear-gradient(90deg,#ffc8e0,#ffe6b8,#bdf0dd,#bfe0ff);z-index:2}
/* 右下角卡通场景卡（拍立得样式） */
#mkScene{position:fixed;right:14px;bottom:16px;width:150px;height:104px;z-index:7;
  border:4px solid #fff;border-radius:16px;transform:rotate(-3deg);pointer-events:none;
  background:url("__SCENE__") center/cover;box-shadow:0 8px 20px rgba(170,120,150,.30)}
#mkScene span{position:absolute;left:0;right:0;bottom:-2px;font:800 10.5px/1.6 var(--disp);
  color:#7a5568;text-align:center;background:linear-gradient(transparent,rgba(255,255,255,.95))}
.card h2{color:var(--accent)}
.sname{color:var(--accent)}
.nav.on{background:#fff!important;border-color:var(--softline)!important}
.tbl th{background:var(--thead)!important}
""")

# ═════════ I 贴纸派对：白边贴纸卡片 + 满屏贴纸 ═════════
S['I'] = dict(
    name='贴纸派对', emoji='🧸', deco=['🧸', '💖', '⭐', '🍭', '🌈', '✨'],
    v=dict(bg='#fef8ff', panel='#ffffff', panel2='#fdf9ff', zebra='#fefbff', thead='#f6e8ff',
           side='#f9f0ff', ink='#4a3d5e', ink2='#6b5a80', muted='#a294b8', line='#ecd8ff',
           accent='#a86ee8', soft='#f4e9ff', softline='#c79bf5',
           sl69='rgba(199,155,245,.69)', sl40='rgba(199,155,245,.40)', good='#8f5ee0',
           goodsoft='#f6efff', glow='rgba(168,110,232,.16)', blob1='#f1e4ff', blob2='#ffe9f7',
           radius='26px', rsm='16px'),
    js="""(function(){
      var cs=document.querySelectorAll('.card,.libList,.libDetail,.themePal');
      for(var i=0;i<cs.length;i++){
        if(cs[i].querySelector(':scope > .mkStk')) continue;
        var d=document.createElement('span'); d.className='mkStk';
        d.textContent=['⭐','💖','🍭','🌈','✨','🧸'][i%6];
        d.style.cssText='right:'+(10+(i%3)*6)+'px;top:-17px;font-size:'+(19+(i%3)*4)+'px';
        cs[i].appendChild(d);
      }
      /* 页面左右两侧贴纸串 */
      var l=document.getElementById('mkRail');
      if(!l){
        l=document.createElement('div'); l.id='mkRail';
        var em=['💖','⭐','🍭','🌈','✨','🎈','🍬','💫','🧁','🌸','🫧','⭐'];
        var s='';
        for(var k=0;k<12;k++){
          s+='<i style="top:'+(2+k*8)+'%;left:'+(1.2+(k%2)*0.8)+'%">'+em[k]+'</i>';
          s+='<i style="top:'+(6+k*8)+'%;right:'+(1.2+(k%2)*0.8)+'%">'+em[(k+5)%12]+'</i>';
        }
        l.innerHTML=s; document.body.appendChild(l);
      }
    })();""",
    css="""
.main,.content{background:
  radial-gradient(rgba(199,155,245,.20) 2px,transparent 2.1px) 0 0/30px 30px,
  radial-gradient(600px 380px at 6% 2%,#f3e7ff,transparent 72%),
  radial-gradient(560px 340px at 97% 8%,#ffeaf8,transparent 72%),var(--bg)!important}
.side{background:linear-gradient(180deg,#faf2ff,#f4e8ff)!important}
/* 卡片：白边贴纸效果（三层描边） */
.card,.libList,.libDetail,.themePal,.syncbox,.fxcard,.clgvw{
  border:3px solid var(--softline)!important;border-radius:var(--radius)!important;
  box-shadow:0 0 0 5px #fff,0 0 0 8px var(--softline),9px 10px 0 8px rgba(199,155,245,.30)!important;
  overflow:visible!important}
.mkStk{position:absolute;pointer-events:none;z-index:5;
  filter:drop-shadow(0 4px 6px rgba(120,80,160,.28))}
#mkRail{position:fixed;inset:0;pointer-events:none;z-index:5}
#mkRail i{position:absolute;font-style:normal;font-size:17px;opacity:.5;
  animation:mkFloat 8s ease-in-out infinite}
#mkRail i:nth-child(3n){animation-duration:11s;animation-delay:-2s}
#mkRail i:nth-child(2n){font-size:14px;opacity:.38}
.card h2{color:var(--accent)}
.nav.on{background:linear-gradient(180deg,#fff,#f7efff)!important}
.pill i{box-shadow:0 0 0 5px rgba(168,110,232,.18)}
""")

# ═════════ J 毛绒玩偶：虚线毛边 + 钮扣 + 绒毛影 ═════════
S['J'] = dict(
    name='毛绒玩偶', emoji='🐼', deco=['🐼', '🧸', '🐻', '☁️', '🪡', '🧶'],
    v=dict(bg='#fbf7f2', panel='#fffdfa', panel2='#fdfaf6', zebra='#fdfbf8', thead='#f4ece2',
           side='#faf3ea', ink='#4e4034', ink2='#6f5c4b', muted='#a5947f', line='#ecdfd0',
           accent='#c98a5a', soft='#f6ecdf', softline='#d9b48c',
           sl69='rgba(217,180,140,.69)', sl40='rgba(217,180,140,.40)', good='#8fae74',
           goodsoft='#f0f5e9', glow='rgba(201,138,90,.15)', blob1='#f7ecdf', blob2='#f2efe6',
           radius='32px', rsm='20px'),
    js="""(function(){
      var cs=document.querySelectorAll('.card,.libList,.libDetail,.themePal');
      for(var i=0;i<cs.length;i++){
        if(cs[i].querySelector(':scope > .mkBtn')) continue;
        var b=document.createElement('span'); b.className='mkBtn';
        b.innerHTML='<i></i><i></i>';
        cs[i].appendChild(b);
      }
    })();""",
    css="""
.main,.content{background:
  radial-gradient(circle at 50% -6%,rgba(255,255,255,.9) 0 120px,transparent 121px),
  radial-gradient(560px 340px at 10% 4%,#f8efe3,transparent 72%),
  radial-gradient(520px 320px at 94% 8%,#f4f1e8,transparent 72%),var(--bg)!important}
.side{background:linear-gradient(180deg,#fbf5ee,#f5ece1)!important}
/* 卡片：粗虚线毛边 + 绒毛柔光 + 大圆角 */
.card,.libList,.libDetail,.themePal,.syncbox,.fxcard,.clgvw{
  border:4px dashed var(--softline)!important;border-radius:var(--radius)!important;
  box-shadow:0 0 0 5px rgba(217,180,140,.20),0 0 20px 9px rgba(217,180,140,.24),
    0 14px 0 rgba(217,180,140,.28),0 20px 34px rgba(170,140,110,.16),
    inset 0 3px 0 rgba(255,255,255,.85)!important;
  overflow:visible!important}
/* 四角钮扣 */
.mkBtn{position:absolute;right:15px;top:13px;display:flex;gap:8px;pointer-events:none;z-index:4}
.mkBtn i{position:relative;width:18px;height:18px;border-radius:50%;background:var(--softline);
  box-shadow:inset 0 2px 3px rgba(255,255,255,.8),0 2px 4px rgba(140,110,80,.3)}
.mkBtn i::after{content:'';position:absolute;left:6px;top:6px;width:6px;height:6px;
  border-radius:50%;background:rgba(110,82,54,.5)}
/* 绒毛感：外圈柔光毛边 + 内圈缝线
   注意：负 z-index 的伪元素会被「定位的卡片本体」盖住（绘制顺序在卡片背景之前），
   所以毛边只能靠 box-shadow 的大扩散模糊层做，不能另起元素。 */
.card::before{content:'';position:absolute;inset:7px;border:2px dotted rgba(217,180,140,.75);
  border-radius:calc(var(--radius) - 9px);pointer-events:none;z-index:1}
.card h2{color:var(--accent)}
.sname{color:var(--accent)}
.nav.on{background:#fffdfa!important;border-color:var(--softline)!important;border-style:dashed!important}
""")

# ═════════ K 彩虹软糖：多彩渐变描边 + 果冻高光 ═════════
S['K'] = dict(
    name='彩虹软糖', emoji='🍬', deco=['🍬', '🌈', '🍡', '💫', '🫧', '⭐'],
    v=dict(bg='#f7fbff', panel='#ffffff', panel2='#fafdff', zebra='#fcfdff', thead='#e9f4ff',
           side='#eef8ff', ink='#33455e', ink2='#4f6884', muted='#8ea5bd', line='#d7e8ff',
           accent='#4fa8e8', soft='#e6f4ff', softline='#9ed0f2',
           sl69='rgba(158,208,242,.69)', sl40='rgba(158,208,242,.40)', good='#43bfa0',
           goodsoft='#e8faf4', glow='rgba(79,168,232,.18)', blob1='#e2f2ff', blob2='#ffeef8',
           radius='28px', rsm='17px'),
    js="""(function(){
      var cs=document.querySelectorAll('.card,.libList,.libDetail,.themePal');
      for(var i=0;i<cs.length;i++){
        if(cs[i].querySelector(':scope > .mkGloss')) continue;
        var g=document.createElement('span'); g.className='mkGloss';
        cs[i].appendChild(g);
      }
    })();""",
    css="""
.main,.content{background:
  radial-gradient(620px 400px at 4% 0%,#e5f6ff,transparent 70%),
  radial-gradient(560px 360px at 98% 4%,#ffeef8,transparent 70%),
  radial-gradient(520px 340px at 60% 100%,#eafff6,transparent 72%),var(--bg)!important}
.side{background:linear-gradient(180deg,#f0f9ff,#e8f5ff)!important}
/* 卡片：彩虹渐变描边 + 果冻高光条 */
.card,.libList,.libDetail,.themePal,.syncbox,.fxcard,.clgvw{
  background:linear-gradient(var(--panel),var(--panel)) padding-box,
    linear-gradient(120deg,#ffb3d1,#ffe6a7 26%,#b7f0d8 52%,#b9dbff 74%,#e3c6ff) border-box!important;
  border:3px solid transparent!important;border-radius:var(--radius)!important;
  box-shadow:6px 8px 0 rgba(158,208,242,.45),0 14px 28px rgba(150,180,210,.14)!important;
  overflow:hidden!important}
/* 高光要窄：铺太宽整张卡会发白没对比 */
.mkGloss{position:absolute;left:0;right:0;top:0;height:26%;pointer-events:none;
  background:linear-gradient(180deg,rgba(255,255,255,.46),rgba(255,255,255,0));z-index:1}
/* 彩色内描边，让彩虹边更醒目 */
.card::after{content:'';position:absolute;left:0;right:0;top:0;height:5px;z-index:2;
  background:linear-gradient(90deg,#ffb3d1,#ffe6a7 26%,#b7f0d8 52%,#b9dbff 74%,#e3c6ff)}
.card h2{color:var(--accent)}
.sname{background:linear-gradient(90deg,#f2749f,#f0a840,#46bd9c,#4fa8e8,#a86ee8);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.tbl th{background:linear-gradient(90deg,#e8f5ff,#f4ecff)!important}
""")

SWITCHER = """
<script>
(function(){
  var V=['srv','ov','theme','lib','pre','set'];
  /* 装饰挂载要等布局完成再做：解析阶段大部分卡片还没尺寸（offsetWidth=0），
     按尺寸筛选的规则会把它们全跳过；切页后重挂一次，让刚显示的卡片也长上装饰。 */
  function MKDEC(){ try{ __JS__ }catch(e){} }
  function go(v){
    for(var i=0;i<V.length;i++){
      var e=document.getElementById('view-'+V[i]);
      if(e) e.className='view'+(V[i]===v?' on':'');
    }
    var bs=document.querySelectorAll('.mv');
    for(var j=0;j<bs.length;j++)
      bs[j].className='nav mv'+(bs[j].getAttribute('data-view')===v?' on':'');
    var c=document.querySelector('.content'); if(c) c.scrollTop=0;
    window.scrollTo(0,0);
    setTimeout(MKDEC, 60);
  }
  var bs2=document.querySelectorAll('.mv');
  for(var k=0;k<bs2.length;k++){
    bs2[k].style.cursor='pointer';
    bs2[k].onclick=function(){ go(this.getAttribute('data-view')); };
  }
  var fp=document.getElementById('view-pre');
  if(fp && !document.getElementById('mkPreNote')){
    var n=document.createElement('div'); n.id='mkPreNote';
    n.innerHTML='<div style="font-size:46px">\\uD83D\\uDDFA\\uFE0F</div>'+
      '<div>地图实体预览（3D）</div>'+
      '<div style="font-weight:600;font-size:12.5px;opacity:.8">'+
      '样板是静态页面，不含 3D 实时数据<br>在软件里点这里就是完整的 3D 视图</div>';
    fp.style.position='relative'; fp.appendChild(n);
  }
  go('srv');
  if(document.readyState==='complete') setTimeout(MKDEC, 60);
  else window.addEventListener('load', function(){ setTimeout(MKDEC, 60); });
})();
</script>
"""

SPOTS = [(19, 19), (94, 12), (22, 76), (96, 63), (52, 5), (33, 91), (78, 84), (8, 34)]


def deco_html(emojis):
    out = ['<div id="mkDeco">']
    for i, sp in enumerate(SPOTS):
        out.append('<i style="left:%d%%;top:%d%%;font-size:%dpx">%s</i>'
                   % (sp[0], sp[1], 19 + (i % 3) * 7, emojis[i % len(emojis)]))
    out.append('</div>')
    return ''.join(out)


def build():
    snap = open(SNAP, encoding='utf-8').read()
    made = []
    for key in ['F', 'G', 'H', 'I', 'J', 'K']:
        st = S[key]
        css = vars_block(st['v']) + BASE + st['css'].replace('__PAT__', PAT).replace('__SCENE__', SCENE)
        head = ('<!-- 云朵小铺 · 可爱风样板 %s「%s」\n'
                '     取自真实软件页面的完整静态导出；左侧栏可点击切换页面。\n'
                '     默认停在「服务器」主页，便于与其他风格横向对比。\n'
                '     仅外观样板，未接后端数据与 3D 预览。 -->\n' % (key, st['name']))
        add = ('<style id="mkCute">\n' + css + '\n</style>\n'
               '<div id="mkBadge">%s 样板 %s<b>%s</b></div>\n%s\n%s'
               % (st['emoji'], key, st['name'], deco_html(st['deco']),
                  SWITCHER.replace('__JS__', st.get('js', ''))))
        html = head + (snap.replace('</body>', add + '\n</body>')
                       if '</body>' in snap else snap + add)
        p = os.path.join(OUTD, '可爱%s-%s.html' % (key, st['name']))
        open(p, 'w', encoding='utf-8').write(html)
        print('  %-24s %6d KB' % (os.path.basename(p), os.path.getsize(p) // 1024))
        made.append((p, st))
    return made


def shots(made):
    port = 9417
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % port,
        '--remote-allow-origins=*', '--user-data-dir=' + os.path.join(D, '_prof_cutemock2'),
        '--no-first-run', '--window-size=1330,720', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(40):
            try:
                tabs = json.load(op.open('http://127.0.0.1:%d/json' % port, timeout=2))
                pg = [t for t in tabs if t.get('type') == 'page']
                if pg:
                    ws_url = pg[0]['webSocketDebuggerUrl']; break
            except Exception:
                time.sleep(0.5)
        ws = websocket.create_connection(ws_url, timeout=120, http_proxy_host=None)
        _id = [0]

        def send(m, p=None):
            _id[0] += 1
            ws.send(json.dumps({'id': _id[0], 'method': m, 'params': p or {}}))
            while True:
                r = json.loads(ws.recv())
                if r.get('id') == _id[0]:
                    return r.get('result', {})

        def ev(e):
            r = send('Runtime.evaluate', {'expression': e, 'returnByValue': True})
            if 'exceptionDetails' in r:
                return '__ERR__' + str(r['exceptionDetails'].get('text'))
            return r.get('result', {}).get('value')

        send('Page.enable')
        send('Runtime.enable')
        send('Emulation.setDeviceMetricsOverride',
             {'width': 1330, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})
        for idx, (p, st) in enumerate(made):
            send('Page.navigate', {'url': 'file:///' + p.replace('\\', '/')})
            for _ in range(80):
                if ev("document.readyState==='complete' && !!document.getElementById('mkCute')"):
                    break
                time.sleep(0.25)
            time.sleep(2.4)
            info = ev("({view:(document.querySelector('.view.on')||{}).id||'',"
                      "cards:document.querySelectorAll('.card').length,"
                      "deco:document.querySelectorAll('#mkDeco i').length,"
                      "extra:((document.querySelector('.mkCl,.mkTape,.mkStk,.mkBtn,.mkGloss,"
                      "#mkRail i,#mkScene')||{}).className||"
                      "(document.getElementById('mkScene')?'#mkScene':'-')})")
            d = send('Page.captureScreenshot', {'format': 'png'})
            out = os.path.join(SHOT, '可爱样板2-%s%s.png' % (list('ABCDEFGHIJK')[5 + idx], st['name']))
            open(out, 'wb').write(base64.b64decode(d['data']))
            print('  %-26s %5d KB  %s' % (os.path.basename(out),
                                          os.path.getsize(out) // 1024, info))
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == '__main__':
    print('生成第二批可爱风 HTML 样板（可爱F~K）：')
    m = build()
    if '--shot' in sys.argv:
        print('截图验证：')
        shots(m)

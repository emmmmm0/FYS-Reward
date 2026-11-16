# -*- coding: utf-8 -*-
"""界面主脚本（原 ui_page.py 里的主 <script> 块，v2.14 拆出）。

单独下发到 /static/app.js。服务端会用 build_page 的同一套占位符替换后再发
（__THEMES__ / __BGS__ / __POLL__），所以这里保留占位符原样。"""

JS = r"""
var THEMES = __THEMES__;
/* 界面背景素材（data URI）：key -> 图。由 build_page 注入，见 bg_assets.py */
var BGDATA = __BGS__;
function $(id){ return document.getElementById(id); }
function n(v){ return (v===undefined||v===null||v==="")?"—":String(v); }
/* 伤害 / 分数统一按「万」：≥1000 就换算，1 位小数（0.8w / 1.3w / 8.6w）。
   全站只有这一个换算函数（页面表格、KPI 卡、地图库、覆盖预览共用），
   后端 fys_reward_app.py 的 wan() 与覆盖小窗 OVERLAY_HTML 里的同名函数保持同规则。 */
function wan(v){
  if(v===undefined||v===null||v==="") return "—";
  var x=+v;
  if(isNaN(x)) return String(v);
  if(x<1000) return String(x);
  var r=Math.round(x/10000*10)/10;
  return (r===Math.round(r)?Math.round(r):r)+'w';
}
function get(url){ return fetch(url,{cache:'no-store'}).then(function(r){return r.json();}); }
/* 服务器名 / 地图名来自 A2S 回包（远端可控字符串），拼进 innerHTML 前必须转义，
   否则改名后的服务器（或被手工加进清单的地址）能让本页执行脚本，
   而本页能无鉴权调用 /api/ctl?do=opendata|ovopen|openpreview 这些本机操作 */
function esc(s){
  return String(s===null||s===undefined?'':s).replace(/[&<>"']/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}

/* ─── 界面偏好：主程序端口每次启动都变，localStorage 会失效，改存后端 data/ui_prefs.json ─── */
var PREFS={};
/* 偏好写盘串行链：savePrefs 是「读-改-写」语义的键（fav/theme/bg…）。
   浏览器并发连接 + ThreadingHTTPServer 不保证到达顺序 —— 连点两次收藏/取消时
   「取消」可能先于「收藏」落盘，最后盘上是被取消的旧值（v2.15 实测 fav 假红）。
   后端 _PREFS_LOCK 只保单请求原子性，跨请求顺序必须前端自己排队。 */
var _SP_CHAIN = Promise.resolve();
function savePrefs(k,v){
  PREFS[k]=v;
  _SP_CHAIN = _SP_CHAIN.then(function(){
    return get('/api/prefs?set='+encodeURIComponent(k)+'&val='+encodeURIComponent(JSON.stringify(v)));
  }).catch(function(){});
}

/* ─── 主题 ─── */
/* 主题页底部「当前主题配色说明」：颜色直接取自 THEMES，换主题即时跟着变 */
function syncPal(id){
  var t=THEMES.filter(function(x){return x[0]===id;})[0]||THEMES[0];
  var map=[['A',3,'主色 accent'],['S',4,'浅底 soft'],['G',5,'通过 good'],['I',6,'正文 ink']];
  var nm=$('palName'); if(nm) nm.textContent=t[1];
  map.forEach(function(m){
    var sw=$('pal'+m[0]), tx=$('pal'+m[0]+'v');
    if(sw) sw.style.background=t[m[1]];
    if(tx) tx.textContent=t[m[1]];
  });
}
function applyTheme(id, save){
  /* 必须校验：非法主题码（旧的 ui_prefs.json 残留、?theme=Z）会让
     html[data-theme="X"] 一条都不命中，全部 CSS 变量失效 → 整页变成白底黑字 */
  var t=THEMES.filter(function(x){return x[0]===id;})[0]||THEMES[0];
  id=t[0];
  document.documentElement.setAttribute('data-theme', id);
  /* logo 固定云朵（云朵小铺品牌），不随主题换 emoji */
  document.querySelectorAll('#themes .tcard').forEach(function(b){
    var on=b.getAttribute('data-t')===id;
    b.className='tcard'+(on?' on':'');
    b.querySelector('.tstate').textContent=on?'✓ 使用中':'';
  });
  if(save){ savePrefs('theme',id); THEME_TOUCHED=true; }   /* 用户显式选过：晚到的初始化别再改 */
  /* 内嵌实体预览实时跟随：预览页监听 p3d-th 消息热切主题（不重载 iframe） */
  var pf=document.getElementById('preFrame');
  if(pf && pf.getAttribute('data-live')==='1'){
    try{ pf.contentWindow.postMessage({type:'p3d-th',th:id},'*'); }catch(e){}
  }
  syncPal(id);
  /* 换主题要重算底纹（夜幕护眼→暗色版图案/深色纱），但不动已挂好的插画 DOM，避免闪一下 */
  var _bst=document.getElementById('bgcss');
  if(_bst&&typeof bgCSS==='function') _bst.textContent=bgCSS(bgOf(bgCur));
}
function buildThemes(){
  var box=$('themes');
  box.innerHTML='';                     /* 防御：bootReal 万一被跑两次也不重复建卡 */
  THEMES.forEach(function(t){
    var b=document.createElement('button');
    b.className='tcard'; b.setAttribute('data-t',t[0]);
    /* t = [代码, 名称, emoji, 主色, 浅底, 通过色, 正文色, 侧栏, 卡片, 分隔线]
       色板与迷你缩略全部用该主题自己的色值，选之前就能看到换完的样子 */
    b.innerHTML='<div class="temo2">'+t[2]+'</div>'+
      '<div class="tname">'+t[1]+'<span class="tdot" style="background:'+t[3]+'"></span></div>'+
      '<div class="tstate"></div>'+
      '<div class="tpal">'+
        '<i style="background:'+t[3]+'" title="主色 '+t[3]+'"></i>'+
        '<i style="background:'+t[4]+'" title="浅底 '+t[4]+'"></i>'+
        '<i style="background:'+t[5]+'" title="通过色 '+t[5]+'"></i>'+
        '<i style="background:'+t[6]+'" title="正文色 '+t[6]+'"></i>'+
      '</div>'+
      '<div class="tmini" style="--tmini-side:'+t[7]+';--tmini-bg:'+t[4]+
        ';--tmini-panel:'+t[8]+';--tmini-line:'+t[9]+';--tmini-accent:'+t[3]+'">'+
        '<div class="tb"></div><div class="tbd">'+
          '<div class="tc"></div><div class="tr"></div><div class="tr"></div>'+
        '</div></div>';
    b.onclick=function(){ applyTheme(t[0], true); };
    box.appendChild(b);
  });
  var saved=PREFS.theme||'E';                               /* 首次默认奶油草莓 */
  var m=/[?&]theme=([A-Za-z])/.exec(location.search);      /* --theme 参数优先，用于预览 */
  if(m){
    saved=m[1].toUpperCase();
  } else if(THEME_TOUCHED){
    /* 早期已经显式设过主题（bootReal 晚到）：保留现状，别用偏好值盖回去 */
    saved=document.documentElement.getAttribute('data-theme')||saved;
  }
  applyTheme(saved, false);
}

/* ─── 界面背景：可切换（素材为云朵小铺主题图，见 bg_assets.py 的 BGDATA） ───
   一套背景 = 底纹（平铺图案 or 整幅 cover 氛围图）+ 卡片角标水印 + 侧栏贴纸 +
   服务器/地图库/设置三页插画横幅。底纹与插画都走 data URI 内联，不额外落文件；
   换到夜幕护眼主题时图案底自动切暗色版、cover 底自动加深色纱。 */
var BGS=[
 {id:'none',  nm:'纯色无背景', em:'🚫', ds:'关掉图案与插画，最省资源', pat:null},
 {id:'cloud', nm:'云朵小铺',   em:'☁️', ds:'图案铺底 + 吉祥物角标 + 三页插画',
  pat:'pat', tile:1, sz:400, mascot:1, hero:'run', lib:'winner', set:'girl'},
 {id:'run',   nm:'冒险出发',   em:'🏃', ds:'出发插画作整幅氛围底',
  pat:'run', tile:0, veils:.82, mascot:0, hero:'run', lib:'winner', set:'girl'},
 {id:'win',   nm:'通关庆祝',   em:'🏆', ds:'举旗庆祝插画作底，满屏龙晶',
  pat:'winner', tile:0, veils:.82, mascot:0, hero:'winner', lib:'winner', set:'girl'},
 {id:'girl',  nm:'二次元日常', em:'💻', ds:'少女坐云朵作底，安静清爽',
  pat:'girl', tile:0, veils:.82, mascot:1, hero:'girl', lib:'winner', set:'girl'},
 /* v2.15 自定义背景：图片不走打包内联（BGDATA 里没有），运行时从 /api/bgimg
    拉来填进 BGDATA.custom；mascot/hero 都关 —— 用户自己的图上再叠吉祥物
    水印和官方插画横幅只会互相打架 */
 {id:'custom', nm:'自定义图片', em:'🖼️', ds:'选一张本机图片作整幅氛围底',
  pat:'custom', tile:0, veils:.82, mascot:0}
];
/* 侧栏贴纸独立于背景方案（可自选形象）。默认小白猫——
   挥手打招呼的小猫比云朵更有表情，在深浅主题下都清楚（可在主题页随时换） */
var STK=[
 {id:'cloud',  nm:'云朵精灵', em:'☁️', ds:'小铺吉祥物 · 抱着龙晶'},
 {id:'cat',    nm:'小白猫',   em:'🐱', ds:'挥手打招呼的小猫'},
 {id:'zombie', nm:'小僵尸',   em:'🧟', ds:'僵尸逃跑主题小人'},
 {id:'off',    nm:'不显示',   em:'🚫', ds:'侧栏不放贴纸'}
];
var stkCur='cat';
function stkOf(id){
  var hit=STK.filter(function(s){return s.id===id;})[0];
  return hit||STK[0];
}
function stkURI(s){
  return s.id==='off'?null:(BGDATA['sticker_'+s.id]||null);
}
var bgCur='cloud';
function bgOf(id){
  var hit=BGS.filter(function(b){return b.id===id;})[0];
  return hit||BGS[1];                                       /* 非法值兜底回默认「云朵小铺」 */
}

/* 底纹 CSS 字符串：亮色用白纱压淡保可读，暗色换成深纱 */
function bgCSS(b){
  if(!b||!b.pat) return '';
  var img=BGDATA[b.pat]||'';
  var dark=document.documentElement.getAttribute('data-theme')==='N';
  if(dark&&b.tile&&BGDATA.pat_dark) img=BGDATA.pat_dark;    /* 图案底：暗色专用版 */
  if(!img) return '';
  var a=b.tile?0.56:(b.veils||0.82);                        /* 平铺要透出图案，cover 要压住 */
  var v1='rgba(255,253,254,'+a+')', v2='rgba(255,250,253,'+(a+0.08)+')';
  var s1='rgba(255,249,252,'+(a+0.18)+')', s2='rgba(255,246,251,'+(a+0.24)+')';
  var g1='0.70', g2='0.70';
  if(dark){
    /* 夜幕护眼：整幅插画底（tile:0）的亮图残影在深色 UI 里非常扎眼，纱要压到
       八七折以上才融为一体；图案底（云朵小铺）有专用暗色版图，保持原有观感 */
    var dv1=b.tile?.72:.87, dv2=b.tile?.80:.93;
    v1='rgba(22,21,26,'+dv1+')'; v2='rgba(22,21,26,'+dv2+')';
    s1='rgba(20,19,26,'+(dv1+0.10)+')'; s2='rgba(20,19,26,'+(dv2+0.04)+')';
    g1='0.22'; g2='0.20';
  }
  var size=b.tile?(b.sz+'px '+Math.round(b.sz*0.92)+'px'):'cover';
  var att=b.tile?'local':'fixed';
  var css='body,.main{background-image:'+
    'radial-gradient(720px 320px at 2% -10%,rgba(214,240,255,'+g1+') 0%,rgba(214,240,255,0) 62%),'+
    'radial-gradient(780px 340px at 100% -8%,rgba(255,226,240,'+g2+') 0%,rgba(255,226,240,0) 60%),'+
    'linear-gradient('+v1+','+v2+'),url("'+img+'")!important;'+
    'background-repeat:no-repeat,no-repeat,repeat,repeat!important;'+
    'background-size:auto,auto,'+size+'!important;'+
    'background-attachment:scroll,scroll,'+att+',fixed!important;}'+
    '.side{background-image:linear-gradient(180deg,'+s1+' 0%,'+s2+' 100%),url("'+img+'")!important;'+
    'background-repeat:repeat,repeat!important;background-size:auto,'+
    (b.tile?(Math.round(b.sz*0.9)+'px '+Math.round(b.sz*0.83)+'px'):'cover')+'!important;}';
  /* 卡片右上角吉祥物淡水印（暗色主题下卡片是深色，贴白色水印反而脏，故只亮色加） */
  if(b.mascot&&!dark&&BGDATA.mascot){
    css+='.card,.rmcard,.syncbox,.fxcard,.themePal,.bgcard{'+
      'background-image:linear-gradient(rgba(255,255,255,.80),rgba(255,255,255,.86)),'+
      'url("'+BGDATA.mascot+'")!important;'+
      'background-repeat:no-repeat,no-repeat!important;background-size:cover,290px auto!important;'+
      'background-position:center,right -46px top -54px!important;}';
  }
  return css;
}

/* 三页插画横幅：每次全摘再按方案挂，保证切换视图/换方案都不重复 */
function applyHeroes(b){
  Array.prototype.forEach.call(
    document.querySelectorAll('.heroBanner,.libBanner,.setBanner'),
    function(o){ o.parentNode.removeChild(o); });
  if(!b) return;
  var srv=document.getElementById('view-srv');
  if(srv&&b.hero&&BGDATA[b.hero]){
    var d=document.createElement('div'); d.className='heroBanner';
    d.innerHTML='<img src="'+BGDATA[b.hero]+'" alt="">'+
      '<div class="bd">ZOMBIE ESCAPE · 通关奖励</div>'+
      '<div class="tt">云朵小铺 · 通关奖励看板'+
      '<small>云点 / 龙晶 达标门槛速查 · 实时服务器状态</small></div>';
    srv.insertBefore(d, srv.firstChild);
  }
  var libc=document.querySelector('#view-lib .card');
  if(libc&&b.lib&&BGDATA[b.lib]){
    var d2=document.createElement('div'); d2.className='libBanner';
    d2.innerHTML='<img src="'+BGDATA[b.lib]+'" alt="">'+
      '<div class="tt">地图库 · 奖励一览<small>点 ▸ 展开细类 · 点卡片看 3D 实体</small></div>';
    libc.insertBefore(d2, libc.firstChild);
  }
  var setv=document.getElementById('view-set');
  if(setv&&b.set&&BGDATA[b.set]){
    var d3=document.createElement('div'); d3.className='setBanner';
    d3.innerHTML='<img src="'+BGDATA[b.set]+'" alt=""><div class="st">设置 · 数据与更新'+
      '<small>官方数据自动同步 · 广播原文 / 数据目录 / 版本与更新日志</small></div>';
    setv.insertBefore(d3, setv.firstChild);
  }
}
/* 切视图回来时（DOM 被局部重建）补挂，不重复插 */
function bgHeroFix(){
  var b=bgOf(bgCur);
  if((b.hero&&!document.querySelector('.heroBanner'))||
     (b.lib&&!document.querySelector('.libBanner'))||
     (b.set&&!document.querySelector('.setBanner'))) applyHeroes(b);
}

/* 挂载/摘除侧栏贴纸（形象由 stkCur 决定，独立于背景方案） */
function renderSticker(){
  var old=document.getElementById('cuteSticker');
  if(old&&old.parentNode) old.parentNode.removeChild(old);
  var uri=stkURI(stkOf(stkCur));
  if(!uri) return;
  var i=document.createElement('img'); i.id='cuteSticker'; i.src=uri; i.alt='';
  document.body.appendChild(i);
}
/* 选择贴纸：选中态 + 立刻换图 + 记忆 */
function applySticker(id, save){
  stkCur=stkOf(id).id;
  Array.prototype.forEach.call(document.querySelectorAll('#stkrow .stkopt'), function(o){
    o.className='stkopt'+(o.getAttribute('data-s')===stkCur?' on':'');
  });
  renderSticker();
  if(save) savePrefs('sticker', stkCur);
}

function applyBG(id, save){
  var b=bgOf(id);
  bgCur=b.id;
  document.documentElement.setAttribute('data-bg', b.id);
  var st=document.getElementById('bgcss');
  if(!st){ st=document.createElement('style'); st.id='bgcss'; document.head.appendChild(st); }
  st.textContent=bgCSS(b);
  renderSticker();
  applyHeroes(b);
  Array.prototype.forEach.call(document.querySelectorAll('#bggrid .bgopt'), function(o){
    o.className='bgopt'+(o.getAttribute('data-b')===b.id?' on':'');
  });
  if(save) savePrefs('bg', b.id);
}

/* ⑯ 自定义背景图：选本机图片 → canvas 统一压成 ≤1920 宽 JPEG → POST /api/bgimg
   落盘 → 拉来当整幅氛围底。压缩在前端做，服务端只收 JPEG，一般 <1MB。 */
function pickCustom(){
  var inp=document.createElement('input');
  inp.type='file'; inp.accept='image/*';
  inp.onchange=function(){
    var f=inp.files&&inp.files[0]; if(!f) return;
    var url=URL.createObjectURL(f);
    var im=new Image();
    im.onload=function(){
      URL.revokeObjectURL(url);
      var w=im.naturalWidth, h=im.naturalHeight;
      if(!w||!h){ preNote(esc('这张图片读不出来，换一张试试')); return; }
      var sc=Math.min(1, 1920/w);                 /* 大图先缩到 1920 宽再压 */
      var cv=document.createElement('canvas');
      cv.width=Math.max(1,Math.round(w*sc)); cv.height=Math.max(1,Math.round(h*sc));
      cv.getContext('2d').drawImage(im,0,0,cv.width,cv.height);
      var uri;
      try{ uri=cv.toDataURL('image/jpeg',0.82); }
      catch(e){ preNote(esc('图片处理失败（可能是特殊格式），换一张试试')); return; }
      fetch('/api/bgimg',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({uri:uri})})
        .then(function(r){ return r.json(); })
        .then(function(j){
          if(!j||!j.ok){ preNote(esc('背景图上传失败：'+((j&&j.error)||'未知原因'))); return; }
          BGDATA.custom=uri;
          applyBG('custom', true);
        })
        .catch(function(){ preNote(esc('背景图上传失败（服务未响应）')); });
    };
    im.onerror=function(){ URL.revokeObjectURL(url);
      preNote(esc('这张图片读不出来，换一张试试')); };
    im.src=url;
  };
  inp.click();
}

function buildBGs(){
  var box=$('bggrid'); if(!box) return;
  var tcss='';
  BGS.forEach(function(b){
    if(b.pat&&BGDATA[b.pat]) tcss+='#bgthumb-'+b.id+'{background-image:url("'+BGDATA[b.pat]+'")}\n';
  });
  var st=document.getElementById('bgthumbcss');
  if(!st){ st=document.createElement('style'); st.id='bgthumbcss'; document.head.appendChild(st); }
  st.textContent=tcss;
  box.innerHTML='';                        /* 防御：bootReal 被跑两次也不重复建卡 */
  BGS.forEach(function(b){
    var o=document.createElement('button');
    o.className='bgopt'; o.setAttribute('data-b', b.id);
    o.innerHTML='<span class="thumb'+(b.tile?' tile':'')+'" id="bgthumb-'+b.id+'"></span>'+
      '<span class="ck">使用中</span><span class="em">'+b.em+'</span>'+
      '<span class="nm">'+b.nm+'</span><span class="ds">'+b.ds+'</span>';
    o.onclick=function(){
      /* 自定义卡：还没图时点击=先选图（选完自动应用）；已有图点击=直接应用 */
      if(b.id==='custom'&&!BGDATA.custom){ pickCustom(); return; }
      applyBG(b.id, true);
    };
    if(b.id==='custom'){
      var ch=document.createElement('button');
      ch.className='bgchg'; ch.type='button'; ch.textContent='更换图片';
      ch.title='重新选一张本机图片';
      ch.onclick=function(e){ e.stopPropagation(); pickCustom(); };
      o.appendChild(ch);
    }
    box.appendChild(o);
  });
  /* 首次默认「云朵小铺」= 背景默认打开；存过偏好就按存的来 */
  var saved=PREFS.bg||'cloud';
  var m=/[?&]bg=(\w+)/.exec(location.search);              /* ?bg= 预览参数 */
  if(m) saved=m[1];
  if(!BGS.filter(function(x){return x.id===saved;})[0]) saved='cloud';
  if(saved==='custom'){
    /* 自定义图不在打包资源里：先拉落盘的那张再应用，拉不到（没传过/被清了）
       就退回默认方案，别停在一张空底上 */
    get('/api/bgimg')
      .then(function(j){
        if(j&&j.ok&&j.uri){ BGDATA.custom=j.uri; applyBG('custom', false); }
        else applyBG('cloud', false);
      })
      .catch(function(){ applyBG('cloud', false); });
  } else {
    applyBG(saved, false);
  }
}

function buildStickers(){
  var row=$('stkrow'); if(!row) return;
  /* 头像图同样只内联一份（走 CSS 类），不把 base64 重复写进每个元素的属性里 */
  var tcss='';
  STK.forEach(function(s){
    var u=stkURI(s);
    if(u) tcss+='#stkav-'+s.id+'{background-image:url("'+u+'")}\n';
  });
  var st=document.getElementById('stkcss');
  if(!st){ st=document.createElement('style'); st.id='stkcss'; document.head.appendChild(st); }
  st.textContent=tcss;
  row.innerHTML='';                        /* 防御：bootReal 被跑两次也不重复建卡 */
  STK.forEach(function(s){
    var o=document.createElement('button');
    o.className='stkopt'; o.setAttribute('data-s', s.id);
    o.innerHTML='<span class="av" id="stkav-'+s.id+'"></span>'+
      '<span class="nm">'+s.nm+'<i>'+s.ds+'</i></span>';
    o.onclick=function(){ applySticker(s.id, true); };
    row.appendChild(o);
  });
  var saved=PREFS.sticker||'cat';                           /* 首次默认小白猫 */
  var m=/[?&]stk=(\w+)/.exec(location.search);             /* ?stk= 预览参数 */
  if(m) saved=m[1];
  if(!STK.filter(function(x){return x.id===saved;})[0]) saved='cloud';
  applySticker(saved, false);
}


/* ─── 动画效果（A~J，主题页内逐项开关，记忆在 ui_prefs.json） ─── */
var FX=[
 ['aView',   'A','视图切换淡入上浮','切换左侧菜单时，内容淡入 + 上浮 12px，不再硬切'],
 ['aStagger','B','卡片依次入场','卡片按 55ms 间隔错开出现，形成阅读顺序'],
 ['aFlash',  'C','数值变化脉冲','云点/龙晶数字变化时放大 24% 并闪主题色'],
 ['aSide',   'D','菜单栏收缩动画','侧栏 212→0 平滑收起，内容左移淡出（点侧栏 « 试）'],
 ['aBreath', 'E','状态呼吸灯','在线指示点向外扩散光环，表示数据在刷新'],
 ['aRow',    'F','当前关流光','当前关卡行有缓慢流动的高光'],
 ['aModal',  'G','弹窗缩放淡入','遮罩淡入 + 弹窗从 93% 弹性放大'],
 ['aTheme',  'H','主题切换柔和过渡','所有配色属性 0.32s 渐变，消除闪跳'],
 ['aPress',  'I','按钮按压回弹','按下缩到 94%，松开回弹，反馈更跟手'],
 ['aSpin',   'J','作者名片虚线环','设置页云朵名片头像外的虚线框缓慢旋转']
];
function fxSave(){
  var on=FX.filter(function(f){return document.documentElement.classList.contains(f[0]);})
           .map(function(f){return f[0];});
  savePrefs('fx',on);
}
function replay(){
  var root=document.documentElement;
  var on=FX.filter(function(f){return root.classList.contains(f[0]);}).map(function(f){return f[0];});
  on.forEach(function(c){ root.classList.remove(c); });
  void root.offsetWidth;                       /* 强制重排，动画才会重跑 */
  on.forEach(function(c){ root.classList.add(c); });
}
function setAll(on){
  FX.forEach(function(f){ document.documentElement.classList.toggle(f[0],on); });
  document.querySelectorAll('#fxgrid .sw').forEach(function(s){ s.className='sw'+(on?' on':''); });
  fxSave(); replay();
}
/* 系统「减少动态效果」压制（v2.2）：默认跟随系统，可在动效卡里关掉强制播放。
   prefs 未加载时 PREFS.fx_rm 为 undefined → 也算「跟随」，页面一打开就生效。 */
function applyRM(){
  var follow=PREFS.fx_rm!==false;
  var sysRM=false;
  try{ sysRM=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches; }
  catch(e){}
  document.documentElement.classList.toggle('rm',follow&&sysRM);
  var cb=document.getElementById('fxRM'), hint=document.getElementById('fxRMHint');
  if(cb){
    cb.checked=follow;
    hint.textContent=sysRM
      ?(follow?'检测到系统已开启「减少动态效果」，动效被压制；关掉本开关即可强制播放'
              :'已忽略系统设置，动效正常播放')
      :'系统未开启「减少动态效果」，动效正常';
  }
}
function buildFX(){
  applyRM();                    /* 系统压制检测 + 开关状态（prefs 异步加载后重算） */
  var saved=PREFS.fx||null;
  if(!saved){ saved=FX.map(function(f){return f[0];}); }   /* 首次默认全开 */
  FX.forEach(function(f){
    document.documentElement.classList.toggle(f[0], saved.indexOf(f[0])>=0);
  });
  var pb=$('fxgrid');
  pb.innerHTML='';                      /* 防御：bootReal 万一被跑两次也不重复建行 */
  FX.forEach(function(f){
    var row=document.createElement('div'); row.className='prow';
    row.innerHTML='<span class="pk">'+f[1]+'</span><span class="pt"><b>'+f[2]+'</b>'+
      '<span>'+f[3]+'</span></span>';
    var sw=document.createElement('button');
    sw.className='sw'+(document.documentElement.classList.contains(f[0])?' on':'');
    sw.onclick=function(){
      var on=document.documentElement.classList.toggle(f[0]);
      sw.className='sw'+(on?' on':''); fxSave();
    };
    row.appendChild(sw); pb.appendChild(row);
  });
  $('bAllOn').onclick=function(){ setAll(true); };
  $('bAllOff').onclick=function(){ setAll(false); };
  $('bReplay').onclick=replay;
  /* 「跟随系统减少动态效果」开关：关掉=无视系统设置强制播放动画 */
  var rmcb=$('fxRM');
  if(rmcb) rmcb.onchange=function(){
    PREFS.fx_rm=this.checked;
    savePrefs('fx_rm',this.checked);
    applyRM(); replay();
  };
  try{ matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',applyRM); }
  catch(e){}
  /* 一键恢复出厂外观：主题 E + 背景云朵小铺 + 贴纸小白猫 */
  var rb=$('btnResetLook');
  if(rb) rb.onclick=function(){
    applyTheme('E', true); applyBG('cloud', true); applySticker('cat', true);
    var b=this, old=b.textContent; b.textContent='✅ 已恢复默认';
    setTimeout(function(){ b.textContent=old; },1500);
  };
}

/* ─── 地图库：搜索地图名（ze_xxx）与译名（中文） ─── */
/* pend：从「当前地图」卡片跳过来时，索引还没加载完就先把地图名寄存这里，
   libLoad 完成后自动接着定位（见 libGoto / libLoad） */
var LIB={all:null,loading:false,cur:null,filt:[],sort:'cn',toks:[],pend:null,fav:[],cfg:{},
         tries:0,req:0};
CURVIEW='srv';    /* 当前视图：数据换代时决定要不要就地重取地图库（见 dgInvalidate） */
/* 首启竞态（v2.14 修复）：boot() 先异步取 /api/prefs，回来才跑 bootReal()，
   而 bootReal 里的 initView() 会无条件 showView('srv')、buildThemes() 会无条件
   applyTheme(PREFS.theme)。只要偏好回来得晚（首启索引在后台线程建 / STATE_READY
   未就绪时 /api/prefs 会等），这期间任何已经切过的视图、已经生效的主题都会被顶掉：
   实测「进地图库后又被弹回服务器页」，且 CURVIEW 变成 srv 后同步完成也不再就地
   刷新地图库（dgInvalidate 只在 lib 视图重取）。两个 __TOUCHED 标记表示
   「用户/深链已经显式选过」，初始化只在没人选过时才敢套默认值。 */
var VIEW_TOUCHED=false, THEME_TOUCHED=false;
/* 首启竞态：索引由后台线程加载，早于它完成的 /api/maplib 会返回空表。
   空结果**不能**当成最终结果落地 —— 空数组是 truthy，`LIB.all && !force`
   会把「共 0 张」永久缓存住，之后重进地图库也不会再取数（就是「地图库为 0」）。
   这里退避重试若干次，真为空才认命。 */
var LIB_TRIES_MAX=8;
/* ─── 数据换代后作废地图库缓存（v2.11 修） ───────────────────────────────
   用户实测：点「立即更新」同步成功，但「更新内容与地图库里的内容不匹配，
   还是以前的配置」，重启软件后才对。
   根因：服务端 STATE 换成新索引了（磁盘数据也对），但前端这两份缓存是
   「取一次长期留着」的 —— 地图库索引 LIB.all（含每图关卡奖励/击退/尸变）
   只在首次进地图库时拉一次，逐图参数 LIB.cfg 按图缓存，都不会因为数据
   更新而失效，于是界面一直画着启动时那份旧数据。
   服务端每次 load_state 会把数据代际 +1 随 /api/status 下发（dgen），
   这里发现代际变了就把两个缓存整片作废并就地重取，不用重启。
   ⚠ 用 dgen（只在索引真换掉时 +1），不是 _gen（后台定时比对也 +1）——
     否则每 30 分钟一次的静默上游比对会把用户正在看的地图库刷掉一次。 */
var DG=0, DG_SEEN=null;
function dgInvalidate(){
  DG++;                       /* 在途请求凭它丢弃旧响应（见 libLoad / libCfgLoad） */
  LIB.cfg={}; LIB.tries=0; LIB.keepNull=false;
  UL.data=null; UL.tries=0;
  ulLoad(true);               /* 「上游更新动态」台账也跟着重取 */
  if(CURVIEW==='lib'){
    /* 正在看地图库：就地重取 —— 旧行先留着（不清 LIB.all，避免闪一下「读取中」），
       新数据回来时 libGoto 会把选中项定位回同一张图 */
    LIB.pend=(LIB.cur && LIB.cur.f) ? String(LIB.cur.f) : LIB.pend;
    libLoad(true,true);       /* supersede：顶掉可能在途的旧请求 */
  } else {
    LIB.all=null;             /* 没在看：直接作废，下次进地图库自然重取 */
  }
}
/* ─── 收藏夹：存 data/ui_prefs.json 的 fav 键（小写地图名数组），走 /api/prefs ─── */
function libIsFav(f){ return LIB.fav.indexOf(String(f||'').toLowerCase())>=0; }
function libToggleFav(f){
  var k=String(f||'').toLowerCase();
  if(!k) return;
  var i=LIB.fav.indexOf(k);
  if(i>=0) LIB.fav.splice(i,1); else LIB.fav.push(k);
  savePrefs('fav',LIB.fav);
  var box=$('libList'), st=box?box.scrollTop:0;
  libCounts(); libRender();
  if(box) box.scrollTop=st;          /* 收藏时不让列表跳回顶部 */
}
function libEsc(s){
  return String(s===null||s===undefined?'':s).replace(/[&<>"]/g,function(c){
    return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c];
  });
}
/* 命中高亮：先按关键词标记字符位，再逐字符转义，避免关键词命中自己插入的标签 */
function libHl(s, toks){
  s=String(s===null||s===undefined?'':s);
  if(!toks || !toks.length) return libEsc(s);
  var low=s.toLowerCase(), mark=new Array(s.length), hit=false;
  toks.forEach(function(t){
    var p=0, i;
    while(t && (i=low.indexOf(t,p))>=0){
      for(var j=i;j<i+t.length && j<s.length;j++){ mark[j]=1; }
      hit=true; p=i+t.length;
    }
  });
  if(!hit) return libEsc(s);
  var out='', run='';
  for(var i=0;i<s.length;i++){
    if(mark[i]){ out+=libEsc(run)+'<mark class="mkw">'+libEsc(s.charAt(i))+'</mark>'; run=''; }
    else { run+=s.charAt(i); }
  }
  return out+libEsc(run);
}
function libToks(){
  var q=($('libQ').value||'').trim().toLowerCase();
  LIB.toks=q?q.split(/\s+/).filter(function(x){return !!x;}):[];
  return LIB.toks;
}
/* 关键词：地图名或译名任一命中即可；多个关键词需全部命中（空格分隔） */
function libHit(r){
  var f=(r.f||'').toLowerCase(), c=(r.c||'').toLowerCase(), t=LIB.toks;
  for(var i=0;i<t.length;i++){
    if(f.indexOf(t[i])<0 && c.indexOf(t[i])<0) return false;
  }
  return true;
}
/* 分类 chips 上的张数（跟随索引更新） */
function libCounts(){
  var a=LIB.all||[];
  function cnt(fn){ return a.filter(fn).length; }
  var box=$('libChips'); if(!box) return;
  var n={
    exg: cnt(function(r){ return r.cat==='exg'; }),
    fav: cnt(function(r){ return libIsFav(r.f); }),
    rnd: cnt(function(r){ return r.i && r.i.rand; }),
    ad:  cnt(function(r){ return r.s && r.s.ad; }),
    nad: cnt(function(r){ return !(r.s && r.s.ad); }),
    nm:  cnt(function(r){ return r.s && r.s.nm; }),
    nnm: cnt(function(r){ return !(r.s && r.s.nm); }),
    tm:  cnt(function(r){ return !libAllDay(r); }),
    at:  cnt(function(r){ return libAllDay(r); })
  };
  box.querySelectorAll('.libChip[data-t]').forEach(function(c){
    var k=c.getAttribute('data-t'), e=c.querySelector('i');
    if(e && n[k]!==undefined) e.textContent=n[k];
  });
}
/* 分类选中态同步：无选中项时「全部」自动点亮 */
function libChipSync(){
  var box=$('libChips'); if(!box) return;
  box.querySelectorAll('.libChip[data-t]').forEach(function(c){
    var k=c.getAttribute('data-t');
    if(k==='all') c.className='libChip'+((LIB.filt||[]).length?'':' on');
    else c.className='libChip'+((LIB.filt||[]).indexOf(k)>=0?' on':'');
  });
}
function libAllDay(r){
  var t=(r.s&&r.s.tm)||[];
  return !t.length || (t.length===1 && t[0]===-1);
}
/* ─── ⑯ 最近查看的地图（localStorage，纯本机浏览记录）──────────────
   只记两件事：用户在地图库打开过详情 / 服务器页识别到当前图。
   软件没有 SteamID、没有游玩历史，「最近通关」这类数据不存在 ——
   这里只展示真实可得的信息，进服状态下自动隐藏（四宫格顶替）。 */
var RECENT_KEY='fys_recent_maps', RECENT_MAX=4, RECENT_LAST='';
function pushRecent(f,cn){
  f=String(f||'').toLowerCase(); if(!f) return;
  if(f===RECENT_LAST) return;                 /* 同一张图反复渲染不重复记 */
  RECENT_LAST=f;
  var a=[]; try{ a=JSON.parse(localStorage.getItem(RECENT_KEY))||[]; }catch(e){}
  a=a.filter(function(x){ return x && x.f!==f; });
  a.unshift({f:f,c:String(cn||'')});
  if(a.length>RECENT_MAX) a.length=RECENT_MAX;
  try{ localStorage.setItem(RECENT_KEY,JSON.stringify(a)); }catch(e){}
  renderRecent();
}
function renderRecent(){
  var box=$('recentBox'), list=$('recentList'); if(!box||!list) return;
  var a=[]; try{ a=JSON.parse(localStorage.getItem(RECENT_KEY))||[]; }catch(e){}
  if(!a.length || PRE.curMap){ box.style.display='none'; return; }
  box.style.display='';
  list.innerHTML='';
  a.forEach(function(x){
    var b=document.createElement('button');
    b.className='rcItem'; b.type='button';
    b.title='去地图库查看 '+x.f;
    b.innerHTML='<b>'+esc(x.c||x.f)+'</b>'+(x.c?'<span>'+esc(x.f)+'</span>':'');
    b.onclick=function(){ libGoto(x.f); };
    list.appendChild(b);
  });
}
/* EXG 补充图总数（默认视图里它们被藏起来了，空列表/入口提示要用这个数告诉用户
   「还有一批图在 EXG 里」——不然玩家会以为地图库漏图） */
function libExgTotal(){
  var a=LIB.all||[], n=0;
  for(var i=0;i<a.length;i++) if(a[i].cat==='exg') n++;
  return n;
}
/* 分类筛选：可多选，多个分类取「同时满足」
   ✓ 官方：过滤条件来自官方 maps.json（admin / nomination / certainTimes）
     + 尸变参数表（ze_infect_sort_by_immunity）
   ✓ EXG：本地补充层（见 data/exg_local.json），**默认不进地图库**

   ⚠ EXG 是「互斥视图」而不是普通筛选项：这批图的参数与奖励是按同类图估算的，
   没有官方数据，混在官方图里会让人误以为是可信配置。所以
     · 没点 EXG  → 只显示官方收录的图（EXG 全部隐藏）
     · 点了 EXG  → **只看 EXG 图**（官方图全部隐藏）
   两个方向都是硬过滤，放在循环外先判，避免被其它分类条件抵消。*/
function libFilt(r){
  var F=LIB.filt||[];
  var isExg=(r.cat==='exg'), wantExg=(F.indexOf('exg')>=0);
  if(wantExg){ if(!isExg) return false; }
  else       { if(isExg)  return false; }
  for(var i=0;i<F.length;i++){
    var c=F[i], s=r.s||{};
    if(c==='exg')   continue;               /* 上面已判过 */
    if(c==='fav'   && !libIsFav(r.f)) return false;
    if(c==='rew'   && !r.st.length) return false;
    if(c==='multi' && r.st.length<3) return false;
    if(c==='kb'    && (r.k===null||r.k===undefined)) return false;
    if(c==='rnd'   && !(r.i && r.i.rand)) return false;
    if(c==='ad'    && !s.ad) return false;
    if(c==='nad'   && s.ad) return false;
    if(c==='nm'    && !s.nm) return false;
    if(c==='nnm'   && s.nm) return false;
    if(c==='tm'    && libAllDay(r)) return false;
    if(c==='at'    && !libAllDay(r)) return false;
  }
  return true;
}
function libWan(v){ return wan(v); }
function libHours(arr){
  if(!arr || !arr.length || (arr.length===1 && arr[0]===-1)) return {t:'全天', all:true, n:0};
  var s=arr.slice().sort(function(a,b){return a-b;});
  return {t:s[0]+':00 – '+s[s.length-1]+':00', all:false, n:s.length};
}
function libSortRows(a,b){
  /* 收藏的图永远排在最前（其余维持所选排序） */
  var fa=libIsFav(a.f)?0:1, fb=libIsFav(b.f)?0:1;
  if(fa!==fb) return fa-fb;
  if(LIB.sort==='st') return b.st.length-a.st.length || (a.c||a.f).localeCompare(b.c||b.f,'zh');
  if(LIB.sort==='pr') return ((b.s&&b.s.pr)||0)-((a.s&&a.s.pr)||0) || (a.c||a.f).localeCompare(b.c||b.f,'zh');
  return (a.c||a.f).localeCompare(b.c||b.f,'zh');
}
function libSelect(f){
  LIB.cur=(LIB.all||[]).filter(function(r){return r.f===f;})[0]||null;
  var box=$('libList');
  box.querySelectorAll('.libRow').forEach(function(x){
    x.className='libRow'+(x.getAttribute('data-f')===f?' on':'');
  });
  libDetail();
}
/* ─── 从「当前地图」卡片跳进地图库：定位到某张图 ───
   清掉搜索词与分类筛选（否则目标图可能被过滤掉、看不见），选中它、滚到中间并闪烁一次。
   索引还没加载完就把地图名寄存到 LIB.pend，libLoad 完成后自动接着定位。 */
function libPulse(f){
  /* 分段渲染下目标行可能还没插进 DOM：等几帧再试（最多约 2 秒），
     期间又做了别的筛选就放弃，免得闪到错误的行上。 */
  var seq=LIB_SEQ, tries=0;
  (function find(){
    var el=null;
    $('libList').querySelectorAll('.libRow').forEach(function(x){
      if(!el && x.getAttribute('data-f')===f) el=x;
    });
    if(!el){
      if(seq===LIB_SEQ && tries++<40) setTimeout(find, 50);
      return;
    }
    el.classList.remove('flash'); void el.offsetWidth;      /* 重启动画（连点两次也能闪） */
    el.classList.add('flash');
    if(el.scrollIntoView) el.scrollIntoView({block:'center'});
  })();
}
/* 保守近似名匹配（与后端 _lenient_key 同一套规则，保证「服务器表打 ≈ 的那张图」
   点进来能定位到同一条）：精确命中优先；否则只在「两名字互为前缀 + 长度差 ≤2 +
   全表唯一候选」时命中，一出现第二个候选就放弃 —— 不把 ze_xxx_v5 错配到 ze_xxx_v6。 */
function libFindName(f){
  f=String(f||'').toLowerCase();
  if(!f) return null;
  var all=LIB.all||[], i, k, cands=[];
  for(i=0;i<all.length;i++){
    if(String(all[i].f||'').toLowerCase()===f) return all[i];
  }
  for(i=0;i<all.length;i++){
    k=String(all[i].f||'').toLowerCase();
    if(!k) continue;
    if((k.length>f.length?k.length-f.length:f.length-k.length)>2) continue;
    if(k.indexOf(f)===0 || f.indexOf(k)===0){
      cands.push(all[i]);
      if(cands.length>1) return null;      /* 有歧义就绝不猜 */
    }
  }
  return cands[0]||null;
}
function libGoto(f){
  f=String(f||'').toLowerCase();
  showView('lib');                                        /* 先切页，避免用户看不到跳转 */
  var go=function(){
    var q=$('libQ'); if(q) q.value='';                    /* 搜索框残留会把目标图过滤掉 */
    LIB.filt=[]; libChipSync(); libToks();
    var hit=libFindName(f);
    /* EXG 图在默认视图里被硬过滤（互斥视图），列表里没有那一行可高亮，
       点「最近查看」会像没反应 —— 定位到 EXG 图时自动切到 EXG 视图 */
    if(hit && hit.cat==='exg' && LIB.filt.indexOf('exg')<0){
      LIB.filt=['exg']; libChipSync(); libToks();
    }
    if(hit){
      LIB.cur=hit; libRender(); libPulse(hit.f);
      if(String(hit.f||'').toLowerCase()!==f){
        preNote('这张图的官方登记名是 '+hit.f+'<br>已按近似名定位到它（服务器实名 '+f+'）');
      }
    } else {
      /* 找不到目标图：列表照常给全部，但别自动选中第一张 —— 否则右侧详情是另一张图，
         与「没有这张图」的提示自相矛盾。 */
      LIB.keepNull=true; libRender();
      preNote(!f ? '还没识别到当前地图 —— 先进服，或在这里搜索你要看的图'
        : ('地图库里暂时没有 '+f+'（可能还没同步到索引）<br>已显示全部地图，可用上方搜索框找找'));
    }
  };
  if(LIB.all){ go(); }
  else { LIB.pend=f; if(!LIB.loading) libLoad(); }        /* 索引未就绪 → 加载完再定位 */
}
/* 列表分段渲染（v2.14 性能 P1③）：一次 innerHTML 塞 700+ 行要 300ms+，
   期间输入框、滚动都卡住。改成先出首屏 80 行（约 30ms 就能看见），
   剩下的分片在空闲时间续上，总耗时不变但每次都让出主线程。
   选中/收藏用事件委托，不必给每行单独绑 handler。 */
var LIB_SEQ=0, LIB_CHUNK=80;
function libRowHTML(r){
  var on=(LIB.cur && LIB.cur.f===r.f)?' on':'';
  var st=r.st.length, s=r.s||{};
  /* 行尾标记：关卡数 + 图标小徽标（列表只有 322px，文字标签会挤掉译名，故一律图标化）
     ⑫ 徽章降噪：库里大多数图是「1 关」，全员高亮等于没有重点 ——
     1 关弱化成浅色细边（tag lo）、2~5 关常规、≥6 关的长图才点亮强调色（tag hl） */
  var tags = st>=6 ? '<span class="tag hl" title="长图 · '+st+' 关">'+st+' 关</span>'
           : st<=1 ? '<span class="tag lo" title="轻量短图">'+st+' 关</span>'
           : '<span class="tag" title="常规长度 · '+st+' 关">'+st+' 关</span>';
  /* EXG 图只挂一个「EXG」标签：它的管理员/时段/尸变参数全是按同类图估算的，
     再叠 🔑 🕒 🎲 这类官方属性标签会让人误以为是官方实测配置。 */
  if(r.cat!=='exg'){
    /* 官方收录：把实测参数挂成小徽标 */
    if(s.ad) tags+='<span class="itag k" title="需要管理员才能选图 / 换图（官方 admin = true）">🔑</span>';
    if(r.i && r.i.rand){
      tags+='<span class="itag d" title="纯随机尸变 · 官方 ze_infect_sort_by_immunity = false">🎲</span>';
    }
    if(libAllDay(r)){
      tags+='<span class="itag" title="全天任何时段都能玩">🌐</span>';
    } else {
      tags+='<span class="itag t" title="限定时段：每天 '+libHours(s.tm).t+' 可玩">🕒</span>';
    }
  } else {
    /* EXG：参数与奖励都是估算值，再挂 🔑 🕒 🎲 会让人误以为是官方实测配置，
       所以这类图只留一个 EXG 标签（2026-09-28 用户要求）。*/
    tags+='<span class="itag e txt" title="EXG：FYS 官方地图库未收录，来自 EXG 公开图池；参数与奖励按同类图估算，仅供参考">EXG</span>';
  }
  var fv=libIsFav(r.f);
  /* 封面底图（懒加载 img）：图库没这张图时不生成 img；404 由 onerror 隐藏，行还是原样式。
     引号约定（踩过坑）：整段 HTML 外包单引号 → 内层拼接用双引号 → JS 字符串里的引号用 \' */
  var bg=r.f?('<img class="libBg" loading="lazy" alt="" src="/cover/'+
    encodeURIComponent(String(r.f).toLowerCase())+'.jpg" '+
    'onerror="this.style.display=\'none\'">'):'';
  return '<div class="libRow'+on+'" data-f="'+libEsc(r.f)+'">'+bg+
     '<div class="lm"><div class="lc">'+libHl(r.c||r.f, LIB.toks)+'</div>'+
     '<div class="lf">'+libHl(r.f, LIB.toks)+'</div></div>'+
     '<div class="lb">'+
     '<button class="libStar'+(fv?' on':'')+'" data-fav="'+libEsc(r.f)+'" title="'+
       (fv?'取消收藏':'收藏这张图')+'">'+(fv?'★':'☆')+'</button>'+tags+'</div></div>';
}
function libBindList(){
  /* 事件委托：只绑一次（box 元素本身不会被替换），分段插入的行自动生效 */
  var box=$('libList');
  if(!box || box.__libBound) return;
  box.__libBound=1;
  box.onclick=function(e){
    var t=e.target;
    var st=t.closest?t.closest('.libStar'):null;
    if(st){ e.stopPropagation(); libToggleFav(st.getAttribute('data-fav')); return; }
    var row=t.closest?t.closest('.libRow'):null;
    if(row) libSelect(row.getAttribute('data-f'));
  };
}
function libRenderRest(seq, rows, from){
  if(seq!==LIB_SEQ || from>=rows.length) return;
  setTimeout(function(){
    if(seq!==LIB_SEQ) return;                 /* 期间又筛了一次，这批作废 */
    var box=$('libList'); if(!box) return;
    var end=Math.min(rows.length, from+LIB_CHUNK), buf=[];
    for(var i=from;i<end;i++) buf.push(libRowHTML(rows[i]));
    box.insertAdjacentHTML('beforeend', buf.join(''));
    libRenderRest(seq, rows, end);
  }, 0);
}
function libRender(){
  var box=$('libList');
  if(!LIB.all){ box.innerHTML='<div class="libEmpty">正在读取地图索引…</div>'; return; }
  libToks();
  var rows=LIB.all.filter(libFilt).filter(libHit);
  rows.sort(libSortRows);
  $('libCnt').textContent=rows.length+' / '+LIB.all.length+' 张';
  if(!rows.length){
    box.innerHTML='<div class="libEmpty">'+emptyHTML('🔍','没有匹配的地图',
      '试试更短的关键词，比如 “ze_xmas” 或 “医院”'+
      (((LIB.filt||[]).indexOf('exg')<0)
        ? '<br>要找的是 EXG 补充图？点上方 <b>🧩 EXG</b> 按钮单独查看那 '+libExgTotal()+' 张'
        : ''),
      ((LIB.filt||[]).length||$('libQ').value)?'清除筛选':'',
      'libClrAll()')+'</div>';
    LIB.cur=null; libDetail(); return;
  }
  /* 当前选中不在结果里（或还没选）→ 自动落到第一条；keepNull 时保持「不选中」 */
  if(LIB.keepNull){ LIB.keepNull=false; LIB.cur=null; }
  else if(!LIB.cur || !rows.some(function(r){return r.f===LIB.cur.f;})) LIB.cur=rows[0];
  var seq=++LIB_SEQ;
  var n=Math.min(rows.length, LIB_CHUNK), buf=[];
  for(var i=0;i<n;i++) buf.push(libRowHTML(rows[i]));
  box.innerHTML=buf.join('');
  box.scrollTop=0;
  libBindList();
  libDetail();
  if(n<rows.length) libRenderRest(seq, rows, n);
}
function libKV(k, v, flag, noTxt, yesTxt){
  var val, cls='';
  if(flag!==null && flag!==undefined){
    val=flag?yesTxt:noTxt; cls=flag?'yes':'no';
  } else {
    val=(v===null||v===undefined||v==='')?'—':v;
    if(k==='要求在线人数' || k==='要求玩家数'){
      if(v===-1||v===null||v===undefined){ val='不限'; cls='no'; }
    }
  }
  return '<div class="kv"><div class="k">'+libEsc(k)+'</div><div class="v '+cls+'">'+libEsc(val)+'</div></div>';
}
function libDetail(){
  var d=$('libDetail'), r=LIB.cur;
  if(!r){ d.innerHTML='<div class="libEmpty">左侧选一张地图查看参数</div>'; return; }
  pushRecent(r.f, r.c);   /* ⑯ 记进「最近查看」（服务器页空闲态展示） */
  var t=libHours(r.s.tm), maxRp=1;
  r.st.forEach(function(s){ if(s[1]>maxRp) maxRp=s[1]; });
  var inf=r.i, rndOn=!!(inf && inf.rand);
  var h='';
  /* v2.14 修复：r.f 为空（图库未收录）时以前仍会拼出 --cv:url('/cover/.jpg')，
     每次渲染白发一个注定 400 的请求。现在没封面就不铺 --cv、不加 cvOn，
     头卡回到普通卡片（吉祥物水印照旧），有封面才挂底图并摘掉水印层防重影。 */
  h+='<div class="card'+(r.f?' libCv cvOn':'')+'"'+(r.f
     ? ' style="--cv:url(\'/cover/'+encodeURIComponent(String(r.f).toLowerCase())+'.jpg\')"'
     : '')+'><div class="libHead"><div class="big">'+
     '<div class="cn">'+libHl(r.c||r.f, LIB.toks)+
       (rndOn?'<span class="libRnd"><i></i>随机尸变</span>':'')+
       (r.cat==='exg'?'<span class="libExg" title="EXG：官方地图库未收录，参数与奖励按同类图估算">EXG</span>':'')+'</div>'+
     '<div class="fn">'+libHl(r.f, LIB.toks)+'</div>'+
     '<button class="btn libPv'+(r.pv===false?' off':'')+'" data-f="'+libEsc(r.f)+'"'+
       (r.pv===false
         ? ' data-nopv="1" title="预览数据里还没有这张图的 3D 实体档案（多为 EXG 补充图或刚上线的新图），点击会打开实体最丰富的图"'
         : (r.pvf ? ' data-pvf="'+libEsc(r.pvf)+'" title="这张图与《'+libEsc(r.pvf)+'》是同一工坊条目的不同名字，点开会打开它的 3D 实体档案"' : ''))+'>'+
       (r.pv===false?'🗺️ 暂无实体预览':'🗺️ 地图实体预览')+'</button>'+
     '<button class="btn libFavD'+(libIsFav(r.f)?' on':'')+'" data-fav="'+libEsc(r.f)+'">'+
       (libIsFav(r.f)?'★ 已收藏':'☆ 收藏')+'</button>'+
     '<div class="libBadges">'+
       '<div class="libBdg"><b>'+r.st.length+'</b><span>关卡数</span></div>'+
       '<div class="libBdg"><b>'+((r.s.pr!==null&&r.s.pr!==undefined)?r.s.pr:'—')+'</b><span>龙晶价格</span></div>'+
       '<div class="libBdg"><b>'+((r.s.cd!==null&&r.s.cd!==undefined)?(r.s.cd+'s'):'—')+'</b><span>冷却</span></div>'+
     '</div></div>'+
     '<div class="libKb"><b>'+((r.k!==null&&r.k!==undefined)?r.k:'—')+'</b><span>击退系数</span></div>'+
     '</div></div>'+
     /* 新旧参数对比（数据同步后才有内容，libDiffLoad 异步填） */
     '<div class="card" id="libDiff" style="display:none"></div>';

  h+='<div class="card"><h2>地图设置</h2><div class="libGrid">'+
     libKV('是否需要管理员', '', r.s.ad, '否', '是')+
     libKV('可被提名', '', r.s.nm, '不可', '可以')+
     libKV('龙晶价格', r.s.pr, null)+
     libKV('冷却时间', (r.s.cd!==null&&r.s.cd!==undefined)?(r.s.cd+'s'):null, null)+
     libKV('要求玩家数', r.s.rp, null)+
     libKV('可玩时段', t.t, null)+
     '</div>'+
     (r.cat==='exg'
       ? '<div class="libNote"><b>🧩 EXG 补充</b>：这张图来自 EXG 公开图池，'+
         'FYS 官方地图库暂未收录，<b>没有官方参数与奖励数据</b>。'+
         '上面的地图设置与下方奖励按「同类图（相同玩法标签 + 相同难度）」的常见取值估算，'+
         '仅供参考，不代表该图在服务器上的真实配置。</div>'
       : '')+
     /* 尸变参数并入地图设置卡（数据源不展示） */
     (inf
       ? '<div class="libInfect'+(rndOn?' on':'')+'">'+
         '<span class="libRnd" style="margin-left:0"><i></i>'+
           (rndOn?'随机尸变 · 开启':'随机尸变 · 关闭')+'</span></div>'+
         '<div class="libGrid">'+
           libKV('尸变比', (inf.ratio!==null&&inf.ratio!==undefined)?(inf.ratio+' 人'):null, null)+
           libKV('尸变倒计时', (inf.time!==null&&inf.time!==undefined)?(inf.time+' 秒'):null, null)+
         '</div>'
       : '')+
     '</div>';

  if(r.st.length){
    h+='<div class="card"><h2>每关奖励配置</h2><table class="libStg"><thead><tr>'+
       '<th>关卡</th><th>通关云点</th><th>伤害云点</th><th>通关龙晶</th>'+
       '<th>伤害龙晶</th></tr></thead><tbody>';
    r.st.forEach(function(s){
      var bar=s[1]?Math.max(6,Math.round(s[1]/maxRp*100)):0;
      h+='<tr><td>第 '+libEsc(s[0])+' 关'+(s[1]?'<div class="libRbar"><i style="width:'+bar+'%"></i></div>':'')+'</td>'+
         '<td>'+((s[1]!==null&&s[1]!==undefined)?s[1]:'—')+'<span class="u">点</span></td>'+
         '<td title="伤害云点门槛：每造成 '+libEsc(s[2])+' 伤害额外 +1 云点">'+libWan(s[2])+'</td>'+
         '<td>'+((s[4]!==null&&s[4]!==undefined)?s[4]:'—')+'<span class="u">颗</span></td>'+
         '<td title="伤害龙晶门槛：每造成 '+libEsc(s[5])+' 伤害额外 +1 龙晶">'+libWan(s[5])+'</td></tr>';
    });
    h+='</tbody></table><div class="libNote">伤害云点 / 伤害龙晶为<b>达标门槛</b>：每造成该数值的伤害，'+
       '额外 +1 云点 / 龙晶（如 3w 伤害 = +1）。数值按 <b>万</b> 显示，鼠标悬停看原始值。'+
       '<br>柱状条为各关通关云点的相对高度。</div></div>';
  } else {
    h+='<div class="card"><h2>每关奖励配置</h2><div class="libWarn">'+
       '这张图<b>没有奖励配置</b>。<br>常见原因：大厅图 / 非 ZE 图，或该图未收录在仓库 rewards 目录里。'+
       '<br>地图设置与击退参数仍然可用。</div></div>';
  }
  /* 地图参数（官方 cfg 全量 + 选图参数）：按图异步拉，不拖慢详情首屏 */
  h+='<div class="card" id="libCfg"><h2>地图参数<span class="cfgSub">官方 cfg 全量</span></h2>'+
     '<div class="libEmpty">正在读取参数…</div></div>';
  d.innerHTML=h;
  d.scrollTop=0;
  libCfgLoad(r.f);
  libDiffLoad(r.f);
  /* 地图库 → 实体预览：切到内嵌预览视图看这张图 */
  var pv=d.querySelector('.libPv');
  if(pv) pv.onclick=function(){
    var f=pv.getAttribute('data-f');
    /* 壳里没有这张图时必须说清楚：以前是静默打开另一张推荐图，玩家以为点错了 */
    if(pv.getAttribute('data-nopv')==='1'){
      preNote('《'+libEsc(f)+'》暂无 3D 实体档案<br>'+
              '（预览数据源未收录这张图，多为 EXG 补充图或刚上线的新图）<br>'+
              '已为你打开实体最丰富的图，可先看渲染效果');
    }
    /* 同图异名：壳里收录的是另一个名字，直接用那个名字打开同一张图 */
    openPreView(pv.getAttribute('data-pvf')||f);
  };
  /* 详情页收藏按钮：与列表星标同一份清单，切换后详情跟着重画 */
  var fv=d.querySelector('.libFavD');
  if(fv) fv.onclick=function(){
    libToggleFav(fv.getAttribute('data-fav'));
    libDetail();
  };
}
/* ─── 详情页「地图参数」卡 ─────────────────────────────────────────────
   官方每图的 cfg 全量（31 项，含中文名）+ maps.json 选图参数。逐图缓存：
   详情切图很频繁，缓存后重看同一张图零请求；响应回来先校验仍是当前选中图，
   否则快速连点切图时旧响应会把新图的参数画上去。 */
/* ─── 共享：「字段 旧值 → 新值」拼装器（v2.14 美化去重） ──
   详情页对比卡 / 查看明细弹窗 / 更新动态台账三处界面共用，
   以前各抄一份，改样式要同步三处，漏一处界面就长得不一样。
   fl: {k, old, new, f(原始字段名悬停), st 或 stage(关卡号)} */
/* ─── 共享：统一空态（v2.14 美化⑥）────────────────────────────
   图标 + 主文案 + 说明 + 可选动作按钮。空态不再是死胡同：
   有明确出口的场景（搜索无结果 / 读取失败）直接给按钮。 */
function emptyHTML(ic,main,sub,btn,act){
  return '<div class="eIc">'+ic+'</div><b class="eT">'+main+'</b>'+
    (sub?'<div class="eS">'+sub+'</div>':'')+
    (btn?'<button class="eBtn" onclick="'+act+'">'+btn+'</button>':'')+
    '</div>';
}
/* 地图库「清除筛选」：空态按钮和工具栏按钮共用 */
function libClrAll(){
  $('libQ').value=''; LIB.filt=[]; libChipSync(); libRender();
}
function fldHTML(fl){
  var st=(fl.st!==null&&fl.st!==undefined&&fl.st!=='')?fl.st:fl.stage, pre='';
  if(st!==null && st!==undefined && st!==''){
    pre=(String(st).match(/^\d+$/)?('第'+st+'关 '):(String(st)+' '));
  }
  var old=(fl.old!==null&&fl.old!==undefined&&fl.old!=='');
  return '<span class="dF"'+(fl.f?' title="'+esc(fl.f)+'"':'')+'>'+
    '<span class="k">'+esc(pre)+esc(fl.k||'')+'</span>'+
    (old?'<span class="old">'+esc(String(fl.old))+'</span><span class="arr">→</span>':'')+
    '<span class="new">'+esc(String(fl.new))+'</span></span>';
}
function libCfgLoad(f){
  var key=String(f||'').toLowerCase(), box=$('libCfg');
  if(!box) return;
  if(LIB.cfg[key]){ libCfgPaint(LIB.cfg[key]); return; }
  var g=DG;                                  /* 期间若数据换代，这份参数已过期 */
  get('/api/mapparams?f='+encodeURIComponent(key)).then(function(d){
    if(g!==DG) return;
    LIB.cfg[key]=(d&&d.ok!==false)?d:{ok:false,err:(d&&d.error)||''};
    if(LIB.cur && String(LIB.cur.f||'').toLowerCase()===key) libCfgPaint(LIB.cfg[key]);
  }).catch(function(){
    if(g!==DG) return;
    if(!LIB.cur || String(LIB.cur.f||'').toLowerCase()!==key) return;
    var b=$('libCfg');
    if(b) b.innerHTML='<h2>地图参数</h2><div class="libWarn">参数读取失败，切换别的图或重进地图库再看。</div>';
  });
}
function libDiffLoad(f){
  /* 新旧参数对比：数据同步过（存在 *.prev.json 快照）且这张图有变化才显示明细。
     玩家更新完数据后想知道「这张图到底改了什么」，而不是对着新数字自己猜。
     没变化时以前整块隐藏，用户翻遍详情页也找不到这个功能（2026-10-27 反馈），
     现在留一行灰字说明「这里是比对位、当前一致」。 */
  var key=String(f||'').toLowerCase(), box=$('libDiff');
  if(!box) return;
  var g=DG;                                  /* 期间若数据换代，这份对比已过期 */
  get('/api/mapdiff?f='+encodeURIComponent(key)).then(function(d){
    if(g!==DG) return;
    if(!LIB.cur || String(LIB.cur.f||'').toLowerCase()!==key) return;
    if(!d || d.ok===false){ box.style.display='none'; return; }
    if(!d.changed){
      if(!d.has_prev){ box.style.display='none'; return; }
      /* 没变化时不再摆一整张卡（大标题 + 空态块占掉半屏，看着像详情页被截断）：
         缩成一行灰字，既让用户知道「这里是比对位」，也不碍眼（v2.14 视觉⑨） */
      box.className='card libDiffNo';
      box.innerHTML='<div class="dNoChg">🆕 本次数据更新：这张图与上次同步前一致，没有参数变化。</div>';
      box.style.display='';
      return;
    }
    box.className='card';
    var CN={'new':'b-new','edit':'b-edit','stage':'b-stage',
            'param':'b-param','zombie':'b-zombie','del':'b-del'};
    var NM={'new':'➕ 新增地图','edit':'✏️ 奖励调整','stage':'🔀 关卡数',
            'param':'🔧 地图参数','zombie':'💀 尸变参数','del':'➖ 已下架'};
    var order=['new','edit','stage','param','zombie','del'];
    var h='<h2>🆕 本次数据更新<span class="cfgSub">对比上次同步前'+
          (d.mapcn?(' · '+esc(d.mapcn)):'')+'</span></h2>'+
          '<div class="sub" style="margin:0 0 8px">左旧右新，共 <b>'+d.total+
          '</b> 项变化 · 鼠标停在数值上可看原始字段名</div>';
    order.forEach(function(gk){
      (d.groups[gk]||[]).forEach(function(it){
        h+='<div class="dCat"><span class="tbadge '+(CN[gk]||'b-param')+'">'+
           (NM[gk]||esc(gk))+'</span>';
        (it.fields||[]).forEach(function(fl){
          h+=fldHTML(fl);
        });
        h+='</div>';
      });
    });
    box.innerHTML=h;
    box.style.display='';
  }).catch(function(){ if(g===DG) box.style.display='none'; });
}
function libCfgPaint(d){
  var box=$('libCfg'); if(!box) return;
  var h='<h2>地图参数<span class="cfgSub">官方 cfg 全量</span></h2>';
  if(!d || d.ok===false || !(d.groups||[]).length){
    h+='<div class="libWarn">这张图<b>没有官方参数配置</b>。<br>'+
       '常见原因：EXG 补充图 / 大厅图 —— 官方仓库里没有它的 cfg 文件。</div>';
    box.innerHTML=h; return;
  }
  var n=0;
  d.groups.forEach(function(g){ n+=(g.items||[]).length; });
  h+='<div class="sub" style="margin:0 0 8px">共 <b>'+n+'</b> 项官方参数 · '+
     '鼠标停在右侧可看原始 ConVar 名</div><div class="cfgCols">';
  d.groups.forEach(function(g){
    h+='<div class="cfgBlk"><div class="cfgT">'+esc(g.n)+'</div>';
    (g.items||[]).forEach(function(it){
      h+='<div class="cfgRow"><span class="n">'+esc(it.n)+'</span>'+
         '<b class="v">'+esc(it.v)+'</b>'+
         '<i class="k" title="ConVar：'+esc(it.k)+'">'+esc(it.k)+'</i></div>';
    });
    h+='</div>';
  });
  h+='</div>';
  if((d.set||[]).length){
    h+='<div class="cfgT">选图参数（maps.json）</div>';
    d.set.forEach(function(it){
      h+='<div class="cfgRow"><span class="n">'+esc(it.n)+'</span><b class="v">'+esc(it.v)+'</b></div>';
    });
  }
  h+='<div class="libNote">参数取自官方仓库每图的 <b>cfg</b>（ZombiEscape - Map Configs 生成器产出）。'+
     '其中某项被官方改动时，本页顶部<b>「🆕 本次数据更新」</b>会给出<b>旧值 → 新值</b>；'+
     '更早的改动到顶部<b>「上游更新动态」</b>（设置页同名卡片）展开对应日期查看。</div>';
  box.innerHTML=h;
}
function libWait(msg){
  /* 等待态：spinner + 已等待秒数。索引加载最长要 1~2 分钟，
     一句静态「正在读取…」用户不知道它在动（2026-10-23 反馈） */
  var s=Math.round((Date.now()-(LIB.t0||Date.now()))/1000);
  var hint=s>=15?'<div class="libWaitHint">首次加载要解析全量地图数据，可能需要 1~2 分钟，不用关窗口</div>':'';
  var el=$('libList'); if(!el) return;
  el.innerHTML='<div class="libWaitBox"><span class="libSpin"></span>'+
    '<div class="libWaitTxt">'+msg+'</div>'+
    '<div class="libWaitSub">已等待 '+s+' 秒</div>'+hint+'</div>';
}
function libWaitStart(msg){
  if(!LIB.t0) LIB.t0=Date.now();      /* 重试链路里接着上次计，别从 0 重来 */
  libWait(msg);
  if(LIB.tick) clearInterval(LIB.tick);
  LIB.tick=setInterval(function(){
    if(!LIB.loading){ clearInterval(LIB.tick); LIB.tick=null; return; }
    libWait(LIB.waitMsg||'正在读取地图索引…');
  },1000);
}
function libWaitStop(){
  if(LIB.tick){ clearInterval(LIB.tick); LIB.tick=null; }
  LIB.t0=0;
}
function libLoad(force, supersede){
  /* supersede：数据换代时用来顶掉在途的那次请求（见 dgInvalidate）。
     旧的响应会凭 LIB.req 被丢弃，不会把换代前的旧数据画回去。 */
  if(LIB.loading && !supersede) return;
  if(LIB.all && !force) return;
  LIB.loading=true;
  var req=++LIB.req;
  if(!LIB.all){ libWaitStart('正在读取地图索引…'); }
  get('/api/maplib').then(function(d){
    if(req!==LIB.req) return;          /* 已被更新的一次加载取代 */
    LIB.loading=false;
    var rows=(d && d.maps) || [];
    if(!rows.length && LIB.tries<LIB_TRIES_MAX){
      /* 索引还没就绪（首启竞态）：不落地空结果，退避重试；
         期间保持「正在读取…」文案，别让用户看到「共 0 张」 */
      LIB.tries++;
      LIB.all=null;
      LIB.waitMsg='正在读取地图索引…（第 '+LIB.tries+'/'+LIB_TRIES_MAX+' 次重试）';
      libWait(LIB.waitMsg);
      setTimeout(function(){ libLoad(true); }, Math.min(1200+LIB.tries*800, 6000));
      return;
    }
    LIB.tries=0;
    libWaitStop();
    LIB.all=rows;
    LIB.cur=null;
    /* 收藏清单：PREFS 异步加载，进地图库时基本都已就绪；没就绪当空清单，下次重进自动补上 */
    LIB.fav=(Array.isArray(PREFS.fav)?PREFS.fav:[]).map(function(x){return String(x).toLowerCase();});
    var extra=((d && d.meta && d.meta.built_at)?(' · 索引构建于 '+d.meta.built_at):'');
    var nr=LIB.all.filter(function(r){ return r.i && r.i.rand; }).length;
    libCounts(); libChipSync();
    $('libSub').textContent='共 '+LIB.all.length+' 张僵尸逃跑地图 · 其中 '+nr+' 张为随机尸变 · '+
      '上方「分类」可多选（是否需管理员 / 可被提名 / 可玩时段 / 随机尸变），'+
      '支持地图名（ze_xxx）与译名（中文）搜索，空格分隔多个关键词，'+
      '搜索框按 ⏎ 回车可直接打开第一条'+extra;
    libRender();
    var pd=LIB.pend; LIB.pend=null;
    /* '' 也是有效寄存值（代表「还没识别到当前地图」）——用 !==null 判断，
       否则冷启动点一次「去地图库」那声提示会被吞掉 */
    if(pd!==null && pd!==undefined){ libGoto(pd); }
  }).catch(function(){
    if(req!==LIB.req) return;
    LIB.loading=false;
    libWaitStop();
    LIB.pend=null;
    $('libList').innerHTML='<div class="libEmpty">'+emptyHTML('📡','地图索引读取失败',
      '网络或服务暂不可用，稍等片刻再试','重试','libLoad(true)')+'</div>';
  });
}
function libInit(){
  /* 搜索防抖：一次全量重建要对 ~700 条做 filter+sort+重建 DOM，逐字触发会明显发顿。
     Enter / 清空按钮仍走立即渲染。 */
  var _libDeb=null;
  $('libQ').oninput=function(){
    if(_libDeb) clearTimeout(_libDeb);
    _libDeb=setTimeout(function(){ _libDeb=null; libRender(); }, 140);
  };
  $('libQ').onkeydown=function(e){
    if(e.key==='Enter'){
      if(_libDeb){ clearTimeout(_libDeb); _libDeb=null; }
      libRender();
      var b=$('libList').querySelector('.libRow'); if(b) b.click();
    }
  };
  $('libClr').onclick=function(){
    if(_libDeb){ clearTimeout(_libDeb); _libDeb=null; }
    $('libQ').value=''; libRender(); $('libQ').focus();
  };
  $('libReload').onclick=function(){
    /* 原来先 LIB.all=null 再调 libLoad：正在加载时 libLoad 直接 return，
       而 LIB.all 已经清空 → 按钮看起来点了没反应，页面还退回「正在读取…」 */
    if(LIB.loading){
      /* 正在加载时早退会让人以为按钮坏了 —— 转一下图标再复原 */
      var b=this, old=b.textContent;
      b.disabled=true; b.textContent='…';
      setTimeout(function(){ b.disabled=false; b.textContent=old; },900);
      return;
    }
    /* 逐图参数缓存也要一起丢：它按图存、不设过期，只清 LIB.all 的话
       详情页「地图参数」卡还会画着旧值（和「同步后仍是旧配置」同一个毛病） */
    LIB.all=null; LIB.cfg={}; libLoad(true);
  };
  $('libSort').onchange=function(){ LIB.sort=this.value; libRender(); };
  document.querySelectorAll('#libChips .libChip').forEach(function(c){
    c.onclick=function(){
      var k=c.getAttribute('data-t');
      if(k==='all'){ LIB.filt=[]; }
      else{
        var i=(LIB.filt||[]).indexOf(k);
        if(i>=0) LIB.filt.splice(i,1); else LIB.filt.push(k);
      }
      libChipSync();
      libRender();
    };
  });
}

/* ─── 视图切换：服务器 / 屏幕覆盖 / 主题 / 设置 ─── */
/* 实体预览恢复为内嵌视图（view-pre）：进页才加载 iframe，离开自动 about:blank 释放 WebGL */
var VIEWS=['srv','ov','theme','lib','set','pre'];
/* ⑩ 顶栏面包屑：各视图在标题栏显示的页名（与侧栏菜单保持一致） */
var PAGENAME={srv:'服务器',ov:'屏幕覆盖',theme:'主题',lib:'地图库',set:'设置',pre:'地图实体预览'};
function setPage(v){
  var el=$('tPage'); if(!el) return;
  var nm=PAGENAME[v]||'服务器';
  if(el.textContent!==nm){
    el.textContent=nm;
    el.style.animation='none'; void el.offsetWidth;
    el.style.animation='tpIn .26s ease';
  }
}
function showView(v){
  VIEWS.forEach(function(k){
    $('view-'+k).className='view'+(k===v?' on':'');
  });
  document.querySelectorAll('.mv').forEach(function(b){
    b.className='nav mv'+(b.getAttribute('data-view')===v?' on':'');
  });
  setPage(v);                             /* 顶栏页名跟随切换 */
  CURVIEW=v;                              /* 数据换代时据此决定要不要就地重取 */
  VIEW_TOUCHED=true;                      /* 已有显式选择：晚到的 initView 不许再顶掉 */
  bannerApply();                          /* 更新横幅只在服务器页显示 */
  if(v==='lib'){ libLoad(); }             /* 首次进入才拉取索引，695 张图约 100KB */
  if(v==='set'){ loadAbout(); loadGsi(); } /* 「关于」卡 / GSI 状态按需拉取 */
  if(v==='pre'){ preEmbedOn(); } else { preEmbedOff(); }   /* 预览：进页加载 / 离页释放 */
  if(typeof bgHeroFix==='function') bgHeroFix();           /* 背景插画随视图重建后补挂 */
  /* 视图不记忆：每次打开都回到服务器页（主题/动画仍记忆） */
}
function initView(){
  var saved='srv';
  if(VIEWS.indexOf(saved)<0) saved='srv';
  var m=/[?&]view=(\w+)/.exec(location.search);            /* ?view= 预览参数 */
  var pm=/[?&]map=([A-Za-z0-9_.\-]+)/.exec(location.search);  /* ?view=pre&map=ze_xxx 深链到某张图 */
  if(m && m[1]==='pre'){ saved='pre'; if(pm) PRE.embed=pm[1].toLowerCase(); }   /* 旧深链 ?view=pre：恢复为内嵌视图 */
  else if(m && VIEWS.indexOf(m[1])>=0) saved=m[1];
  if(pm) PRE.map=pm[1].toLowerCase();
  /* 已经有视图了（?view= 深链之外，可能来自更早的一次导航／bootReal 被跑第二次）：
     只补绑导航按钮，不再 showView —— 否则会把用户当前页顶回服务器页。 */
  if(VIEW_TOUCHED){
    document.querySelectorAll('.mv').forEach(function(b){
      b.onclick=function(){ showView(b.getAttribute('data-view')); };
    });
    return;
  }
  showView(saved);
  if(saved==='lib' && PRE.map){ libGoto(PRE.map); }        /* ?view=lib&map=ze_xxx：直接定位这张图 */
  document.querySelectorAll('.mv').forEach(function(b){
    b.onclick=function(){ showView(b.getAttribute('data-view')); };
  });
}

/* ─── 地图实体预览（软件内内嵌视图 + 独立窗口备用） ───
   预览页（preview3d.html，约 34MB）以 iframe 内嵌在 view-pre 里：进页才加载、
   离页自动 about:blank 释放 WebGL，避免常驻拖慢软件；「🪟 独立窗口」按钮走
   /api/ctl?do=openpreview 由后端拉起独立 pywebview 子进程窗口（可拖第二屏）。 */
/* curMap：实时（离开服务器即清空）
   lastMap：粘性（记住最近一次识别到的地图，退服后仍能带你去地图库查它）
   embed：内嵌预览当前加载的图（'' = 默认推荐图）
   卡片按钮固定「去地图库」，定位目标 = curMap || lastMap */
var PRE={curMap:'',lastMap:'',map:null,embed:''};
function preTarget(){
  return PRE.embed || PRE.curMap || PRE.lastMap || '';
}
/* 预览壳云端按需下载：本地已有就直接用；没有就先下一份再加载，
   期间在视图上盖一层提示，避免 iframe 干等二三十秒让人以为卡死。 */
function pvMask(html){
  var v=document.getElementById('view-pre'); if(!v) return null;
  var el=document.getElementById('pvDl');
  if(!el){
    el=document.createElement('div'); el.id='pvDl';
    el.style.cssText='position:absolute;left:0;right:0;top:0;bottom:0;z-index:var(--z-nav);'
      +'display:flex;align-items:center;justify-content:center;flex-direction:column;'
      +'gap:8px;padding:24px;text-align:center;font-size:var(--fs-md);'
      +'background:var(--panel,#fff);color:var(--ink,#3a2f36);';
    v.style.position='relative';
    var bar=v.querySelector('.preBar2');
    if(bar){ bar.style.position='relative'; bar.style.zIndex='61'; }
    if(!document.getElementById('pvbarCss')){
      var st=document.createElement('style'); st.id='pvbarCss';
      st.textContent='@keyframes pvbar{0%{margin-left:-37%}100%{margin-left:100%}}';
      /* 0% 起点定在 -37%（填充 38% 宽 → 右缘始终露出 1%）：原 -64% 起点每圈有
         1/6 时间整条完全隐形，2026-11-16 用户截图恰好抓到，看起来像「没有进度条 */
      document.head.appendChild(st);
    }
    v.appendChild(el);
  }
  el.innerHTML=html; el.style.display='flex';
  return el;
}
function pvMaskOff(){ var el=document.getElementById('pvDl'); if(el) el.style.display='none'; }
function pvBar(){
  return '<div style="margin-top:10px;width:230px;height:5px;border-radius:3px;'
    +'background:var(--soft,#f2f2f2);overflow:hidden">'
    +'<div style="height:100%;width:38%;border-radius:3px;background:var(--accent,#f2608d);'
    +'animation:pvbar 1.5s ease-in-out infinite"></div></div>';
}
function pvReady(cb){
  get('/api/preview').then(function(d){
    if(d && d.ready){ cb(true); return; }
    /* 体积文案只认后端实测值：以前这里兜底写死 16.3，与仓库里的壳（14.7MB）不符 */
    var mb=(d&&d.need)||0;
    var upd=!!(d&&d.stale);   /* 有本地缓存但云端已更新 → 文案换成「自动更新」 */
    /* 真实进度：半秒轮一次 /api/preview/progress（后端流式写盘并计数），拿到 total 就换确定进度条 */
    var paint=function(p){
      var bar;
      if(p && p.phase==='connect'){
        /* 还在逐源试连接（源挂起时后端最多等 45s 换下一个）：明确告诉玩家卡在哪 */
        bar=pvBar()
          +'<div style="font-size:var(--fs-xs);color:var(--muted,#999);margin-top:3px">正在连接镜像源 '
          +esc(p.src||'')+' …</div>';
      } else if(p && p.phase==='download'){
        if(p.total){
          var pct=Math.min(100,Math.round(p.got/p.total*100));
          bar='<div style="margin-top:10px;width:230px;height:6px;border-radius:3px;'
            +'background:var(--soft,#f2f2f2);overflow:hidden">'
            +'<div style="height:100%;width:'+pct+'%;border-radius:3px;background:var(--accent,#f2608d);'
            +'transition:width .3s"></div></div>'
            +'<div style="font-size:var(--fs-xs);color:var(--muted,#999);margin-top:3px">'+pct+'% · '
            +(p.got/1048576).toFixed(1)+' / '+(p.total/1048576).toFixed(1)+' MB</div>';
        } else {
          /* 镜像没回 Content-Length 也给真实已下载量，别让玩家对着空转条猜 */
          bar=pvBar()
            +'<div style="font-size:var(--fs-xs);color:var(--muted,#999);margin-top:3px">已下载 '
            +((p.got||0)/1048576).toFixed(1)+' MB…</div>';
        }
      } else { bar=pvBar(); }
      pvMask('<div style="font-weight:500">'+(upd?'预览数据有新版本，正在自动更新':'首次使用需要下载预览数据')+'</div>'
        +'<div style="font-size:var(--fs-sm);color:var(--muted,#999);line-height:1.7">'
        +(mb?mb+' MB · 视网速约 20~40 秒<br>':'')+(upd?'更新完成后立即生效':'下载后保存在本地，以后打开就是秒开')+'</div>'+bar);
    };
    paint(null);
    var pt=setInterval(function(){
      get('/api/preview/progress').then(function(p){
        if(p && (p.phase==='download'||p.phase==='connect')) paint(p);
      }).catch(function(){});
    },500);
    get('/api/preview/fetch').then(function(r){
      clearInterval(pt);
      pvMaskOff();
      if(r && r.ok){ cb(true); }
      else{
        /* 失败遮罩内直接给「重新加载」按钮——2026-11-16 反馈：原来文案让玩家去点
           工具条上的按钮，但遮罩盖住了工具条，根本点不到 */
        pvMask('<div style="font-weight:500">预览数据下载失败</div>'
          +'<div style="font-size:var(--fs-sm);color:var(--muted,#999);line-height:1.7">'
          +'请检查网络后点下方按钮再试一次</div>'
          +'<button class="btn pri" id="pvRetry" style="margin-top:12px">🔄 重新加载</button>');
        var rb=document.getElementById('pvRetry');
        if(rb) rb.onclick=function(){
          pvMask('<div style="font-weight:500">正在重新连接…</div>'+pvBar());
          /* ⚠ 必须重走 pvReady：它才会重新打 /api/preview/fetch（带真实进度）。
             原来这里是 preEmbedOn()，只是把 iframe 指回 /preview3d —— 服务端
             壳还是缺的，于是又 502，玩家点了等于没点（2026-11-16 反馈）。 */
          pvReady(function(ok2){
            if(!ok2) return;          /* 失败时 pvReady 内部会重新画失败遮罩（带按钮） */
            var f=$('preFrame'); if(f) f.removeAttribute('data-live');
            preEmbedOn();
          });
        };
        cb(false);
      }
    }).catch(function(){
      clearInterval(pt);
      pvMask('<div style="font-weight:500">本机服务没响应</div>'
        +'<div style="font-size:var(--fs-sm);color:var(--muted,#999)">请重启软件再试</div>');
      cb(false);
    });
  }).catch(function(){ cb(true); });
}
function preEmbedOn(){
  var f=$('preFrame'); if(!f) return;
  var m=preTarget();
  PRE.embed=m;
  $('preCur2').textContent='🗺️ 地图实体预览'+(m?('：'+m):'（未指定，展示默认推荐图）');
  if(f.getAttribute('data-live')!=='1'){
    var th=document.documentElement.getAttribute('data-theme')||'E';   /* 跟随软件主题 */
    pvReady(function(ok){
      if(!ok) return;
      f.src=location.origin+'/preview3d?'+(m?('map='+encodeURIComponent(m)+'&'):'')+'th='+th+'&embed=1';
      f.setAttribute('data-live','1');
    });
  }
}
function preEmbedOff(){
  var f=$('preFrame'); if(!f) return;
  if(f.getAttribute('data-live')==='1'){ f.src='about:blank'; f.removeAttribute('data-live'); }
}
function openPreView(map){
  map=(map||'').trim();
  if(!map) map=PRE.curMap||PRE.lastMap||'';
  if(PRE.embed!==map){ PRE.embed=map; var f=$('preFrame'); if(f) f.removeAttribute('data-live'); }
  showView('pre');
}
function preNote(txt){
  /* 轻提示：视图内嵌预览页删掉了，改用浮动 toast（3.8s 自动消失） */
  var t=document.getElementById('preToast');
  if(!t){
    t=document.createElement('div'); t.id='preToast';
    t.style.cssText='position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:var(--z-toast);'
      +'max-width:76%;padding:10px 16px;border-radius:12px;font-size:var(--fs-sm);line-height:1.6;'
      +'background:var(--panel,#fff);color:var(--ink,#3a2f36);border:1.5px solid var(--line,#eee);'
      +'box-shadow:0 8px 24px rgba(0,0,0,.16);opacity:0;transition:opacity .22s;pointer-events:none;';
    document.body.appendChild(t);
  }
  t.innerHTML=txt; t.style.opacity='1';
  clearTimeout(preNote._tm);
  preNote._tm=setTimeout(function(){ t.style.opacity='0'; }, 3800);
}
function openPreviewExt(map){
  get('/api/ctl?do=openpreview&map='+encodeURIComponent(map||'')).then(function(d){
    if(d&&d.ok){
      preNote(d.reused
        ? '地图实体预览窗口已在运行，已切换到前台'
        : '已在软件窗口打开地图实体预览'+(map?('：'+map):'')+'<br>（有系统标题栏：可最大化、可拖到第二块屏）');
    }
    else{ preNote('打开失败：'+((d&&d.error)||'未知错误')); }
  }).catch(function(){ preNote('打开失败：本机服务没响应'); });
}
function preWire(){
  /* 内嵌预览工具条：重新加载 / 独立窗口备用出口 */
  $('preReload').onclick=function(){
    var f=$('preFrame');
    if(f){ f.removeAttribute('data-live'); preEmbedOn(); }
  };
  $('prePop').onclick=function(){ openPreviewExt(preTarget()); };
  /* 卡片右侧按钮：始终是「去地图库」——有当前/最近一张图就定位到那一行，
     没有就打开全部地图给一句提示。（3D 实体预览的入口在左栏「🗺️ 地图实体预览」
     和地图库详情卡里，卡片这里固定给地图库） */
  $('pvNow').onclick=function(){ libGoto(PRE.curMap || PRE.lastMap); };
}

/* ─── 设置：GitHub 地图数据同步 ─── */
function syncUI(d){
  var s=d.sync||{}, di=d.datainfo, info;
  var bar=$('syncBar'), fill=$('syncBarFill');
  var pct=(typeof s.pct==='number')?s.pct:0;
  if(s.running){
    info='🔄 '+(s.msg||'正在同步…')+(pct>0&&pct<100?' · '+pct+'%':'');
  }
  else if(s.ok===false){ info='❌ '+(s.msg||'同步失败'); }
  else if(s.ok===true){ info='✅ '+(s.msg||'同步完成'); }
  else info='数据索引：构建于 '+((di&&di.built_at)||'—')+
    ' · 地图 '+((di&&di.maps)||'—')+' 张 · 关卡 '+((di&&di.stages)||'—')+' 段';
  $('syncInfo').textContent=info;
  /* 进度条：只在同步中且有真实分段进度时显示（同步完立刻收起） */
  if(bar && fill){
    if(s.running && pct>0){
      bar.hidden=false;
      fill.style.width=Math.max(4,Math.min(99,pct))+'%';
    } else if(!s.running){
      bar.hidden=true; fill.style.width='0';
    }
  }
  var b=$('btnSync');
  b.disabled=!!s.running;
  b.textContent=s.running?'同步中…':'立即同步';
}

/* ─── 侧栏 ─── */
function fold(on){
  $('side').className = on ? 'side hide' : 'side';
  document.body.classList.toggle('folded', !!on);
}

/* ─── 屏幕覆盖 ─── */
var OVFLD=[], OVC=null, _ovSaveT=null;
/* 覆盖配置落盘：预览是即时的，写盘做 260ms 防抖 ——
   滑杆/取色器 oninput 每动一格就写一次 overlay.json（字号 16→72 会写 29 次），
   原来还会同时重建整个预览 DOM。离散操作（勾选、模式）走 ovSave(true) 立即写。 */
function ovPushCfg(){
  if(!OVC) return;
  get('/api/ctl?do=ovsave&cfg='+encodeURIComponent(JSON.stringify(OVC))).catch(function(){});
}
function ovSave(now){
  if(!OVC) return;
  ovPreview();
  if(_ovSaveT){ clearTimeout(_ovSaveT); _ovSaveT=null; }
  if(now){ ovPushCfg(); return; }
  _ovSaveT=setTimeout(function(){ _ovSaveT=null; ovPushCfg(); }, 260);
}
/* 分区折叠状态记忆（v2.3 优化 1）：默认「布局与样式 / 显示内容」展开、
   「直播输出 / 高级 / OBS 用法」收起；手动折叠后记到 localStorage，下回打开保持。 */
var OVPK='fys_ov_panes';
function ovPaneState(){ try{ return JSON.parse(localStorage.getItem(OVPK)||'{}'); }catch(e){ return {}; } }
function ovPaneInit(){
  document.querySelectorAll('.ovpane[data-pane]').forEach(function(d){
    var k=d.getAttribute('data-pane'), s=ovPaneState();
    d.open = (k in s) ? !!s[k] : d.hasAttribute('data-open');
    d.addEventListener('toggle', function(){ try{
      var t=ovPaneState(); t[k]=d.open; localStorage.setItem(OVPK,JSON.stringify(t));
    }catch(e){} });
  });
}
/* ─── 覆盖预览：示例数据 / 标签 / 分组 / 位置预设 ─── */
var OV_DEMO={map:'ze_backrooms_insomnia',mapcn:'后室2：失眠症',stage:'第 2 / 6 关',
  /* 括号与真实小窗同规则：通关云点/龙晶（本局兑换个数↑）；伤害云点/龙晶（距下一档还差多少伤害） */
  passes:'13（1↑）',dmgrank:'2.4w（0.3w）',econ:'10（1↑）',dmgecon:'3.5w（2.3w）',srv:'風雲社 · 01'};
/* 标签必须与真实覆盖窗（fys_reward_app.py 的 NAME / OVERLAY_HTML）逐字一致，
   否则预览看到的版式和实际小窗不同。 */
var OV_NAME={map:'地图',mapcn:'译名',stage:'当前关卡',
  passes:'通关云点',dmgrank:'伤害云点',econ:'通关龙晶',dmgecon:'伤害龙晶'};
var OV_A=['map','mapcn','stage'], OV_B=['passes','dmgrank','econ','dmgecon'];
/* 封面图：读 exe 旁 cover\<地图名>.jpg（真实窗与设置页预览共用同一个函数）。
   ★ 必须定义在这行之前 —— ovSave() 会先跑 ovPreview()，函数若定义在后面的
   <script> 里，页面初始化那一瞬间 ovPreview 就会抛 ReferenceError，
   连带把「切换布局落盘」整个打断（实测：点「地图图标」不生效）。 */
function ovCover(n, w){
  n=String(n||'').toLowerCase();
  if(!n) return '';
  var s=w?(' style="width:'+w+'px;height:'+(Math.round(w*0.586))+'px"'):'';
  return '<img class="cv" alt="" src="/cover/'+encodeURIComponent(n)+'.jpg"'+
         s+' onerror="this.style.display=\'none\'" '+
         'onload="var e=this.nextElementSibling;if(e)e.style.display=\'none\'">';
}
function ovPreview(){
  if(!OVC) return;
  var sh=OVC.show||{}, C=OVC.color, bgf=Math.max(0,Math.min(1,+OVC.bg||0));
  var small=Math.round(OVC.size*0.62);
  /* 与真实覆盖窗同款底色（#card 的紫罗兰渐变）；真实窗 bg<3% 时预览也透明 */
  var cardbg=bgf>=0.03?('linear-gradient(135deg,rgba(91,58,94,'+bgf+
    '),rgba(44,31,58,'+Math.min(1,bgf*1.06)+'))'):'transparent';
  /* 样板图同款两栏行：标签左灰、数值右对齐；通关系列数值金色（与真实窗 .r 一致） */
  function row(k,gold){
    /* 值单独成节点：超长地图 ID 走省略号（.ovVal），全名放 title */
    var val=String(OV_DEMO[k]==null?'':OV_DEMO[k]).replace(/"/g,'&quot;');
    return '<div class="ovLine" style="color:'+C+'">'+
      '<span class="olb" style="font-size:'+small+'px">'+OV_NAME[k]+'</span>'+
      '<span class="ovVal'+(gold?' g':'')+'" style="font-size:'+OVC.size+'px" title="'+val+'">'+
      OV_DEMO[k]+'</span></div>';
  }
  var OV_EMOJI=[['cabinet','🏛️'],['backrooms','🌀'],['insomnia','🌙'],['alien','🛸'],
    ['hospital','🏥'],['metro','🚇'],['motel','🛎️'],['escape','🏃'],['zombie','🧟'],
    ['department','🏬'],['office','🏢'],['capital','🏙️'],['factory','🏭'],['city','🌆']];
  function ovEmoji(n){ n=String(n||'').toLowerCase();
    for(var i=0;i<OV_EMOJI.length;i++){ if(n.indexOf(OV_EMOJI[i][0])>=0) return OV_EMOJI[i][1]; }
    return '🗺️'; }
  function ovTag(n){ return String(n||'').replace(/^ze[_-]/i,'').toUpperCase().slice(0,8)||'MAP'; }
  var L=OVC.layout||'card', h='';
  if(L==='compact'){
    var s=[];
    if(sh.map)   s.push('<b style="font-weight:800">'+OV_DEMO.map+'</b>');
    if(sh.mapcn) s.push('<span style="opacity:.65">'+OV_DEMO.mapcn+'</span>');
    if(sh.stage) s.push('<span style="opacity:.65">'+OV_DEMO.stage+'</span>');
    /* 金色 = 通关系列（通关云点 / 通关龙晶），伤害系列保持白字 */
    if(sh.passes||sh.dmgrank)
      s.push('云点 <b style="font-variant-numeric:tabular-nums">'+
        (sh.passes?'<span style="color:#ffce7a">'+OV_DEMO.passes+'</span>':'')+
        ((sh.passes&&sh.dmgrank)?'/':'')+
        (sh.dmgrank?OV_DEMO.dmgrank:'')+'</b>');
    if(sh.econ||sh.dmgecon)
      s.push('龙晶 <b>'+
        (sh.econ?'<span style="color:#ffce7a">'+OV_DEMO.econ+'</span>':'')+
        ((sh.econ&&sh.dmgecon)?'/':'')+
        (sh.dmgecon?OV_DEMO.dmgecon:'')+'</b>');
    h='<div style="color:'+C+';white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+
      (s.length?s.join('<i class="ovDot"></i>'):'<span style="opacity:.7">未选择任何显示内容</span>')+'</div>';
  }else if(L==='iconic'){
    var nums='';
    /* 金色 = 通关系列（通关云点 / 通关龙晶），伤害系列保持白字 */
    [['passes','通关云点','g'],['dmgrank','伤害云点',''],
     ['econ','通关龙晶','g'],['dmgecon','伤害龙晶','']].forEach(function(nd){
      if(sh[nd[0]]) nums+='<div style="min-width:44px"><div style="font-size:'+
        Math.max(8,Math.round(OVC.size*0.32))+'px;opacity:.65;color:'+C+'">'+
        nd[1]+'</div><div style="font-weight:800;font-size:'+OVC.size+'px;color:'+C+'" class="'+nd[2]+'">'+
        OV_DEMO[nd[0]]+'</div></div>';
    });
    var m2=[sh.mapcn?OV_DEMO.mapcn:'',sh.stage?OV_DEMO.stage:''].filter(Boolean).join(' · ');
    h='<div style="display:flex;color:'+C+'">'+
      '<div style="flex:none;width:46px;display:flex;flex-direction:column;align-items:center;'+
      'justify-content:center;background:rgba(255,255,255,.08);border-radius:6px 0 0 6px">'+
      ovCover(OV_DEMO.map,40)+
      '<span style="font-size:'+Math.max(18,Math.round(OVC.size*0.9))+'px">'+ovEmoji(OV_DEMO.map)+'</span>'+
      '<span style="font-size:'+Math.max(5,Math.round(OVC.size*0.25))+'px;opacity:.6">'+ovTag(OV_DEMO.map)+'</span></div>'+
      '<div style="padding:4px 10px 6px;min-width:0">'+
      '<div style="font-weight:800;font-size:'+Math.max(7,small)+'px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+
      (sh.map?OV_DEMO.map:(sh.mapcn?OV_DEMO.mapcn:'—'))+'</div>'+
      (m2?'<div style="font-size:'+Math.max(6,Math.round(OVC.size*0.5))+'px;opacity:.65;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+m2+'</div>':'')+
      (nums?'<div style="display:flex;gap:10px;margin-top:2px">'+nums+'</div>':'')+
      '</div></div>';
  }else{
    /* card / skin：标题条 + 数值行 + 分隔线 + 状态行，顺序与样板图一致（状态固定底部） */
    var ha=false, hb=false;
    OV_A.forEach(function(k){ if(sh[k]){ h+=row(k); ha=true; } });
    OV_B.forEach(function(k){ if(sh[k]) hb=true; });
    if(ha&&hb) h+='<div style="color:'+C+';opacity:.45;font-size:'+Math.max(9,small-2)+
      'px;letter-spacing:3px;line-height:1.4">━━━━━━━━━━━━</div>';
    OV_B.forEach(function(k){ if(sh[k]) h+=row(k,k==='passes'||k==='econ'); });
    if(!h) h='<span style="color:'+C+';opacity:.7;font-size:var(--fs-md)">未选择任何显示内容</span>';
    if(L==='skin'&&!OVC.skin)
      h+='<div style="font-size:'+Math.max(6,Math.round(OVC.size*0.42))+'px;opacity:.62;'+
         'font-weight:700;color:'+C+'">🖼️ 在设置页上传底图，这里就显示你的图片</div>';
    /* 标题条：粉色渐变，与真实窗 .hd 同款（含同样的负边距全出血） */
    h='<div style="display:flex;align-items:baseline;gap:8px;font-weight:800;'+
      'font-size:'+small+'px;white-space:nowrap;color:'+C+';'+
      'margin:-9px -28px 3px -16px;padding:8px 30px 6px 16px;border-radius:15px 15px 0 0;'+
      'background:linear-gradient(90deg,rgba(240,98,146,.32),rgba(240,98,146,.05))">'+
      '<span>☁️ 云朵小铺</span>'+
      '<span style="opacity:.66">'+(OV_DEMO.srv||'')+'</span></div>'+h;
  }
  /* 小窗卡片本体直出（不再套 1920×1080 取景背景），底色随布局/透明度走 */
  if(L==='skin'){
    /* 底图单独一层设 opacity：真半透明，桌面能透过来（与真实覆盖窗同规则）。
       以前是暗化蒙版 —— 图还是不透明，只变亮变暗，玩家反馈「看不到桌面」。 */
    var a=1-Math.max(20,Math.min(95,+(OVC.skin_op!=null?OVC.skin_op:62)))/100;
    var bgl=OVC.skin?('url(/skin/'+encodeURIComponent(OVC.skin)+'?t='+(OVC.skin_ts||0)+')')
      :'linear-gradient(135deg,rgba(91,58,94,.92),rgba(44,31,58,.94))';
    $('ovPrev').innerHTML='<div style="display:inline-block;position:relative;text-align:left;'+
      'box-shadow:0 8px 28px rgba(0,0,0,.35);max-width:100%;border-radius:16px;'+
      'text-shadow:0 1px 2px rgba(0,0,0,.92),0 0 7px rgba(0,0,0,.55)">'+
      '<div style="position:absolute;inset:0;border-radius:16px;background:'+bgl+
      ' center/cover;opacity:'+a.toFixed(3)+'"></div>'+
      '<div style="position:relative;z-index:1;padding:9px 28px 9px 16px">'+h+'</div></div>';
    return;
  }
  var cs='display:inline-block;text-align:left;box-shadow:0 8px 28px rgba(0,0,0,.35);max-width:100%';
  if(L==='compact')
    cs+=';border-radius:99px;padding:8px 32px 8px 18px;background:'+cardbg;
  else if(L==='iconic')
    cs+=';border-radius:16px;overflow:hidden;background:'+cardbg;
  else
    cs+=';border-radius:16px;padding:9px 28px 9px 16px;background:'+cardbg;
  $('ovPrev').innerHTML='<div style="'+cs+'">'+h+'</div>';
}
function ovBuild(fields, cfg){
  OVFLD=fields; OVC=cfg;
  var box=$('ovChecks'); box.innerHTML='';
  /* 「当前关卡」来自 fys 客户端广播文件（fys.broadcast.assistant.txt）：不跟普通项排队，
     放到下方单独一行，与「需 fys 客户端在运行」标注在一起 */
  var LIVE={stage:1}, liveChips=[];
  /* 本局战绩三件套来自 CS2 GSI（不是广播文件），单独一组提示，别混进「需 fys 客户端」 */
  var GSIF={dmgnow:1,dmgpts:1,kdnow:1}, gsiChips=[];
  function mkChip(f){
    var lb=document.createElement('label');
    lb.className=cfg.show[f[0]]?'on':'';
    lb.innerHTML='<input type="checkbox" '+(cfg.show[f[0]]?'checked':'')+'><span>'+f[2]+'</span>';
    lb.querySelector('input').onchange=function(){
      cfg.show[f[0]]=this.checked;
      lb.className=this.checked?'on':'';
      ovSave(true);
    };
    return lb;
  }
  fields.forEach(function(f){
    if(LIVE[f[0]]) liveChips.push(mkChip(f));
    else if(GSIF[f[0]]) gsiChips.push(mkChip(f));
    else box.appendChild(mkChip(f));
  });
  if(liveChips.length){
    var note=document.createElement('div');
    note.className='ovLiveNote';
    note.innerHTML='<b>需 fys 客户端在运行</b>'+
      '<span>「当前关卡」来自 fys 客户端写出的广播文件，客户端正常运行时才更新</span>';
    liveChips.forEach(function(c){ note.appendChild(c); });
    box.appendChild(note);
  }
  if(gsiChips.length){
    var gnote=document.createElement('div');
    gnote.className='ovLiveNote';
    gnote.innerHTML='<b>需开启 CS2 游戏状态集成（GSI）</b>'+
      '<span>本局伤害 / 伤害兑换 / K-D-A 来自游戏本身（「📊 战绩」页开关）；'+
      '伤害按每回合伤害峰值累加，兑换额按该图该关「伤害 : 1 货币」比例推算，'+
      '仅供参考，实际以服务器结算为准</span>';
    gsiChips.forEach(function(c){ gnote.appendChild(c); });
    box.appendChild(gnote);
  }
  var c=$('ovColor'); c.value=cfg.color;
  c.oninput=function(){ cfg.color=this.value; ovSave(); };
  var s=$('ovSize'); s.value=cfg.size; $('ovSizeV').textContent=cfg.size;
  s.oninput=function(){ cfg.size=+this.value; $('ovSizeV').textContent=this.value; ovSave(); };
  var b=$('ovBg'); b.value=Math.round(cfg.bg*100); $('ovBgV').textContent=Math.round(cfg.bg*100);
  b.oninput=function(){ cfg.bg=+this.value/100; $('ovBgV').textContent=this.value; ovSave(); };
  var mf=$('ovModeF'), mt=$('ovModeT');
  function modeUI(){
    var m=cfg.mode||'frameless';
    mf.className='btn'+(m!=='tkinter'?' act':'');
    mt.className='btn'+(m==='tkinter'?' act':'');
  }
  mf.onclick=function(){ cfg.mode='frameless'; modeUI(); ovSave(true); };
  mt.onclick=function(){ cfg.mode='tkinter'; modeUI(); ovSave(true); };
  modeUI();
  /* 「看不到小窗」一键切换（2026-11 玩家反馈）：切到原生分层窗并把小窗拉起来。
     已在运行的话，后端 ovsave 检出 mode 变化会自己重启；没运行就在这里启动。 */
  var ovfx=$('ovFixTk');
  if(ovfx) ovfx.onclick=function(){
    cfg.mode='tkinter'; modeUI(); ovPreview();
    ovfx.disabled=true; var _t0=ovfx.textContent; ovfx.textContent='切换中…';
    get('/api/ctl?do=ovsave&cfg='+encodeURIComponent(JSON.stringify(cfg)))
      .catch(function(){})
      .then(function(){ if(!OVON) return get('/api/ctl?do=ovopen'); })
      .then(function(){ ovUI({ovon:true}); })
      .catch(function(){})
      .then(function(){ ovfx.disabled=false; ovfx.textContent=_t0; });
  };
  /* 布局预设（v2.2）：四选一，改动即时热更新小窗 */
  window.layUI=function(){
    document.querySelectorAll('.ovl').forEach(function(b){
      b.className='btn ovl'+(b.getAttribute('data-l')===(cfg.layout||'card')?' act':''); });
  };
  document.querySelectorAll('.ovl').forEach(function(b){
    b.onclick=function(){ cfg.layout=b.getAttribute('data-l'); layUI(); ovSave(true); };
  });
  layUI();
  /* 底图透明度（v2.3 引入，v2.15 改真透明）：20~95，底图整层 alpha = 1 - 值/100，
     越大越透（桌面/游戏透得过来）；文字靠 text-shadow 保可读 */
  var opv=$('ovSkinOpV');
  $('ovSkinOp').value=(cfg.skin_op!=null?cfg.skin_op:62);
  opv.textContent=$('ovSkinOp').value;
  $('ovSkinOp').oninput=function(){
    cfg.skin_op=+this.value; opv.textContent=this.value; ovPreview(); ovSave();
  };
  /* 自定义底图：上传落盘 data\overlay_skin.png（POST /api/ovskin），几秒内热生效 */
  function skinHint(){
    $('ovSkinHint').textContent=cfg.skin
      ?('已上传：'+cfg.skin+'（覆盖窗几秒内自动换新）')
      :'PNG / JPG / WEBP，≤4MB；配合「🖼️ 自定义底图」布局使用';
  }
  skinHint();
  /* ── 取景框编辑器 ──
     状态是「相对于原图的比例」(0~1)，不是像素：图片按容器缩放显示，
     存比例才能保证拖动结果与服务端裁剪一致。 */
  var CROP={x:0,y:0,w:1,h:1}, CRATIO=0;
  var cb=$('ovCropBox'), cimg=$('ovCropImg'), csel=$('ovCropSel');
  function cropShown(){
    var r=(cfg.skin_crop||{});
    return {x:+r.x||0, y:+r.y||0, w:(+r.w||1), h:(+r.h||1)};
  }
  function cropPaint(){
    if(!cimg.naturalWidth) return;
    var W=cimg.clientWidth, H=cimg.clientHeight;
    csel.style.left=(CROP.x*W)+'px';   csel.style.top=(CROP.y*H)+'px';
    csel.style.width=(CROP.w*W)+'px';  csel.style.height=(CROP.h*H)+'px';
  }
  function cropClamp(c){
    c.w=Math.max(0.02,Math.min(c.w,1)); c.h=Math.max(0.02,Math.min(c.h,1));
    c.x=Math.max(0,Math.min(c.x,1-c.w)); c.y=Math.max(0,Math.min(c.y,1-c.h));
    return c;
  }
  /* 锁定比例：按覆盖窗的实际长宽比（21:11 是 card 布局的常见比例）约束取景框，
     避免裁出来还是被压扁。⚠ 比例约束的是「裁出来的像素比」，必须先除掉图片
     自身的宽高比换算到相对坐标 —— 直接拿 21/11 当相对坐标的 w/h 比，4:3 的图
     会裁出 2.55:1 的横条（2026-09-28 实测修）。 */
  function cropLock(c,anchor){
    if(!CRATIO) return c;
    var iar=cimg.naturalHeight?(cimg.naturalWidth/cimg.naturalHeight):1;
    var rel=iar/CRATIO;                    /* 相对坐标里 h/w 的目标比 */
    var h=Math.min(c.h, c.w*rel), w=h/rel;
    if(w>c.w){ w=c.w; h=w*rel; }
    if(anchor==='n'||anchor==='nw'||anchor==='ne') c.y=c.y+(c.h-h);
    if(anchor==='w'||anchor==='nw'||anchor==='sw') c.x=c.x+(c.w-w);
    c.w=w; c.h=h; return c;
  }
  function cropOpen(){
    if(!cfg.skin){ $('ovCropMsg').textContent='先上传一张图片'; return; }
    CROP=cropShown(); CRATIO=0;
    var r=$('ovCropRatio'); if(r) r.checked=false;
    /* 取景必须看原图：拿成品（已裁过的）去框会二次裁剪，越裁越小 */
    cimg.src='/skin/overlay_skin_orig.png?t='+(cfg.skin_ts||Date.now());
    $('ovCropWrap').hidden=false;
    $('ovCropMsg').textContent='';
  }
  function cropClose(){ $('ovCropWrap').hidden=true; }
  if(cimg) cimg.onload=function(){ cropPaint(); };
  var _drag=null;
  function cropEv(e){
    var rc=cb.getBoundingClientRect();
    return {px:(e.clientX-rc.left)/rc.width, py:(e.clientY-rc.top)/rc.height};
  }
  if(cb){
    cb.addEventListener('pointerdown',function(e){
      if(!cimg.naturalWidth) return;
      var h=e.target.getAttribute&&e.target.getAttribute('data-h');
      var p=cropEv(e), s={x:CROP.x,y:CROP.y,w:CROP.w,h:CROP.h};
      if(h){ _drag={mode:'resize',h:h,s:s,p0:p}; }
      else if(e.target===cimg||e.target===cb){
        /* 框内按下=移动，框外按下=重新框 */
        var inside=(p.px>=CROP.x&&p.px<=CROP.x+CROP.w&&p.py>=CROP.y&&p.py<=CROP.y+CROP.h);
        if(inside) _drag={mode:'move',s:s,p0:p};
        else { CROP=cropClamp({x:p.px,y:p.py,w:0.02,h:0.02}); cropPaint();
               _drag={mode:'resize',h:'se',s:{x:CROP.x,y:CROP.y,w:0.02,h:0.02},p0:p}; }
      }
      if(_drag){ try{ cb.setPointerCapture(e.pointerId); }catch(_e){} e.preventDefault(); }
    });
    cb.addEventListener('pointermove',function(e){
      if(!_drag||!cimg.naturalWidth) return;
      var p=cropEv(e), s=_drag.s, dx=p.px-_drag.p0.px, dy=p.py-_drag.p0.py;
      if(_drag.mode==='move'){
        CROP=cropClamp({x:s.x+dx,y:s.y+dy,w:s.w,h:s.h});
      }else{
        var h=_drag.h, c={x:s.x,y:s.y,w:s.w,h:s.h};
        if(h.indexOf('e')>=0) c.w=Math.max(0.02,s.w+dx);
        if(h.indexOf('s')>=0) c.h=Math.max(0.02,s.h+dy);
        if(h.indexOf('w')>=0){ c.w=Math.max(0.02,s.w-dx); c.x=s.x+(s.w-c.w); }
        if(h.indexOf('n')>=0){ c.h=Math.max(0.02,s.h-dy); c.y=s.y+(s.h-c.h); }
        CROP=cropClamp(cropLock(c,h));
      }
      cropPaint();
    });
    var _up=function(){ _drag=null; };
    cb.addEventListener('pointerup',_up);
    cb.addEventListener('pointercancel',_up);
  }
  var _cbtn=$('ovSkinCropBtn');
  if(_cbtn) _cbtn.onclick=function(){
    if($('ovCropWrap').hidden) cropOpen(); else cropClose();
  };
  var _creset=$('ovCropReset');
  if(_creset) _creset.onclick=function(){ CROP={x:0,y:0,w:1,h:1}; cropPaint(); };
  var _ccancel=$('ovCropCancel');
  if(_ccancel) _ccancel.onclick=cropClose;
  var _cratio=$('ovCropRatio');
  if(_cratio) _cratio.onchange=function(){
    CRATIO=this.checked?(21/11):0;
    if(CRATIO) CROP=cropClamp(cropLock(CROP,'se'));
    cropPaint();
  };
  var _capply=$('ovCropApply');
  if(_capply) _capply.onclick=function(){
    var b=this; b.disabled=true; b.textContent='应用中…';
    fetch('/api/ovskincrop',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({crop:CROP})})
      .then(function(x){ return x.json(); })
      .then(function(j){
        if(j.ok&&j.cfg){ OVC=cfg=j.cfg; skinHint(); ovPreview(); cropClose();
                         $('ovSkinHint').textContent='取景已应用，覆盖窗几秒内换新'; }
        else $('ovCropMsg').textContent='失败：'+(j.error||'未知错误');
      })
      .catch(function(){ $('ovCropMsg').textContent='失败（服务未响应）'; })
      .then(function(){ b.disabled=false; b.textContent='应用取景'; });
  };
  $('ovSkinFile').onchange=function(){
    var f=this.files[0]; if(!f) return; this.value='';
    if(f.size>4*1024*1024){ $('ovSkinHint').textContent='图片超过 4MB，请压缩后再试'; return; }
    var r=new FileReader();
    r.onload=function(){
      $('ovSkinHint').textContent='上传中…';
      fetch('/api/ovskin',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({data:r.result})})
        .then(function(x){ return x.json(); })
        .then(function(j){
          if(j.ok&&j.cfg){ OVC=cfg=j.cfg; skinHint(); ovPreview(); }
          else $('ovSkinHint').textContent='上传失败：'+(j.error||'未知错误');
        })
        .catch(function(){ $('ovSkinHint').textContent='上传失败（服务未响应）'; });
    };
    r.readAsDataURL(f);
  };
  $('ovSkinClear').onclick=function(){
    var b=this;
    if(!cfg.skin){ b.textContent='无底图'; setTimeout(function(){ b.textContent='清除'; },1100); return; }
    b.disabled=true; b.textContent='清除中…';
    get('/api/ctl?do=ovskinclear').then(function(j){
      if(j.ok){ cfg.skin=''; cfg.skin_ts=0; skinHint(); ovPreview();
        /* 取景框里那张预览图也撤掉：不清的话清除后再点「取景」，
           编辑器还挂着旧图，底下却提示「先上传一张图片」（2026-09-28 玩家截图） */
        var ci=$('ovCropImg'); if(ci) ci.removeAttribute('src');
        var cb2=$('ovCropSel'); if(cb2) cb2.style.display='none';
        cropClose(); }
    }).catch(function(){}).then(function(){
      b.disabled=false; b.textContent='清除';
    });
  };
  /* 鼠标穿透开关：开启后小窗对鼠标透明（点击落到下层），取消勾选立刻恢复可拖动。
     两种改动都**热切**（后端把 ov_ct 跟着 /api/ovpoll 下发给小窗就地改样式），不重建小窗 */
  var ct=$('ovCT'); ct.checked=!!cfg.ov_ct;
  ct.onchange=function(){ cfg.ov_ct=this.checked; ovSave(true); };
  /* 直播文本 txt 开关（路径由后端 /api/ovcfg 带出）；
     📁=在资源管理器中定位文件  📄=直接打开 txt */
  var tx=$('ovTxt');
  tx.checked=!!cfg.livetxt;
  $('ovTxtPath').textContent=window.__ovLivetxtPath||'(勾选后生成)';
  $('ovTxtLoc').onclick=function(){ get('/api/ctl?do=opentxtloc').catch(function(){}); };
  $('ovTxtOpen').onclick=function(){ get('/api/ctl?do=opentxt').catch(function(){}); };
  tx.onchange=function(){ cfg.livetxt=this.checked; ovSave(true); };
  ovPreview();
}
/* 「看不到小窗」按钮要知道覆盖窗是否在跑（ovUI 每轮 /api/status 更新） */
var OVON=false;
function ovUI(d){
  var on=OVON=!!d.ovon;
  var b=$('btnOvToggle');
  b.textContent=on?'关闭覆盖':'启动覆盖';
  b.className='btn'+(on?' act':'');
  $('ovState').textContent=on?'覆盖窗口运行中（拖动小窗移动位置）':'未启动';
}

/* ─── 自绘标题栏：拖动 / 最小化 / 最大化 / 关闭 ─── */
var maximized=false;
function setMaxUI(on){
  maximized=!!on;
  var b=$('wMax'); if(b) b.classList.toggle('is-max',maximized);
  /* 最大化时隐藏边缘缩放热区（样式见 .rz） */
  document.documentElement.classList.toggle('aMax',maximized);
}
function toggleMax(){
  get('/api/ctl?do=maxtoggle').then(function(r){
    setMaxUI(r.max);
  }).catch(function(){});
}
function wireTitlebar(){
  $('wMin').onclick=function(){ get('/api/ctl?do=min').catch(function(){}); };
  $('wMax').onclick=toggleMax;
  $('wClose').onclick=function(){ get('/api/ctl?do=close').catch(function(){}); };
  /* 按钮上按下不触发窗口拖动 */
  document.querySelectorAll('.wbtn').forEach(function(b){
    b.addEventListener('mousedown',function(e){ e.stopPropagation(); });
  });

  /* 边缘缩放：无边框窗（frameless）没有非客户区，系统不在窗口边缘给缩放热区，
     所以自绘 8 块透明热区，按下时把「开始缩放」交回系统（HTLEFT/HTxxx）。
     这个请求会一直挂到用户松开鼠标（后端 SendMessage 进入系统模态循环），
     因此 fire-and-forget，不等它返回。 */
  document.querySelectorAll('.rz').forEach(function(z){
    z.addEventListener('mousedown',function(e){
      if(e.button!==0) return;
      e.preventDefault(); e.stopPropagation();
      get('/api/ctl?do=resize&edge='+z.getAttribute('data-edge')).catch(function(){});
    });
  });

  /* 拖动由 pywebview 内置 .pywebview-drag-region 接管，这里只保留双击最大化 */
  $('titlebar').addEventListener('dblclick',function(e){
    if(e.target.closest('.wbtn')) return;
    toggleMax();
  });
}

function render(d){
  /* 空闲判定：CS2 进程没在跑（且不是靠 GSI 认出的在服内）→ 前端降频轮询 */
  try{
    window.__idlePoll = !!(d && d.server && d.server.game_running === false && d.state !== 'ok');
  }catch(e){}
  if(!d) return;
  /* 窗口状态同步：拖拽/Snap 等系统级改变后，最大化图标自动跟着变 */
  if(d.winmax===true||d.winmax===false){
    if(maximized!==d.winmax){ setMaxUI(d.winmax); }
  }
  $('stateText').textContent = d.state_text || '未知';
  $('pill').className = 'pill ' + (d.state==='ok' ? 'on' : 'off');
  /* 数据换代（同步成功 / 后台换上全新索引）：作废地图库的旧缓存并就地重取，
     否则界面上还是启动时那份旧配置（用户实测要重启才对）。内部自带去重。 */
  if(typeof d.dgen==='number'){
    if(DG_SEEN===null){ DG_SEEN=d.dgen; }
    else if(d.dgen!==DG_SEEN){ DG_SEEN=d.dgen; dgInvalidate(); }
  }
  if(d.upddiff) updBannerSync(d.upddiff);   /* 上游数据更新提醒（内部有签名去重） */
  /* 地图标题分两行：主行中文译名（无译名时退化为地图 ID），副行英文 ID。
     不再把「ID（译名）」拼成一个等宽串 —— 长 ID 会在任意字符处硬断。 */
  /* 🗺️ 卡片右侧按钮：固定「去地图库」，所以这里只更新它的悬停提示。
     curMap 实时（离开服务器即清空）、lastMap 粘性（记住最近那张图），
     所以退服后点进去照样能定位到上一张图。 */
  var wasInSrv = !!PRE.curMap;
  PRE.curMap = d.map ? String(d.map).toLowerCase() : '';
  if(PRE.curMap){
    PRE.lastMap = PRE.curMap;
    pushRecent(d.map, d.mapcn);             /* ⑯ 识别到当前图 → 记「最近查看」 */
  } else if(wasInSrv){
    renderRecent();                         /* ⑯ 退服瞬间恢复「最近查看」补位
                                               （进服时它被隐藏，没人再调就永远不回来了） */
  }
  var pvb=$('pvNow');
  if(pvb){
    var pgoto=PRE.curMap||PRE.lastMap;
    if(pvb.getAttribute('data-k')!==pgoto){   /* 只在目标图变化时改 title，避免每秒重排 */
      pvb.setAttribute('data-k', pgoto);
      pvb.disabled=false; pvb.style.opacity='';
      pvb.title = pgoto
        ? ('去地图库看 '+pgoto+'：译名 / 关卡数 / 通关奖励，并高亮定位到这一行')
        : '去地图库浏览全部地图（还没识别到当前地图，进服后这里会直接定位到那张图）';
    }
  }

  var cn=$('mapCn'), fn=$('mapFn');
  if(d.map){
    if(d.mapcn){
      cn.textContent=d.mapcn; cn.className='mcn2';
      fn.textContent=d.map; fn.title=d.map;
    } else {
      cn.textContent=d.map; cn.className='mcn2 mono';
      fn.textContent='暂无官方译名'; fn.title='';
    }
  } else {
    cn.textContent = d.state_text || '未在服务器内';
    cn.className='mcn2'; fn.textContent=''; fn.title='';
  }

  var st=$('stageTag');
  if(d.ok && d.stage!==null && d.stage!==undefined){
    st.style.display=''; st.className='tag hl';
    /* 关卡来源：官方客户端广播（默认）或 GSI 按 CT 比分推断——必须标出来，
       别让人以为这也是官方上报的关卡号 */
    st.textContent='关卡 '+d.stage+(d.stage_src==='gsi'?'（比分推断）':'');
    st.title = d.stage_src==='gsi' ? (d.stage_why||'按 CT 赢的回合数推断') : '';
  } else if(d.ok && d.map){
    /* 关卡号没拿到：明确标出来，别让用户以为关卡识别失败/在乱猜 */
    st.style.display=''; st.className='tag';
    st.textContent='关卡待同步 · 暂按第 '+(d.shown_stage!==null&&d.shown_stage!==undefined?d.shown_stage:'1')+' 关';
  } else { st.style.display='none'; }

  var src=$('srcTag');
  var SRCNAME={server:'服务器实时',both:'实时+广播',broadcast:'fys 广播',gsi:'CS2 GSI'};
  if(d.source_text){
    src.style.display=''; src.className='tag'+(d.source!=='broadcast'?' hl':'');
    src.textContent=SRCNAME[d.source]||'fys 广播';
  } else { src.style.display='none'; }

  var sub=$('subText');
  var NST=(d.stages&&d.stages.length)||0;      /* 兜底：契约万一少字段，别整页崩成「服务未响应」 */
  if(d.ok){
    var bits=['共 '+NST+' 关'];
    if(d.stage===null||d.stage===undefined) bits.push('关卡待同步');
    sub.textContent=bits.join(' · ');
  } else if(d.state==='noreward'){
    sub.textContent='该图不在 rewards 目录（大厅图等），无通关云点';
  } else { sub.textContent = d.error || d.detail || '等待进入服务器…'; }

  var sv=d.server||{}, box=$('srvBox');
  /* 当前所在服：供服务器表判定高亮行（address 匹配优先，名称兜底）。
     仅在后端判定「确实连着」（ok/noreward）时才标，offline 时不标。 */
  window.__curSrv = ((d.state==='ok'||d.state==='noreward') && sv.available && (sv.server_name || sv.address))
    ? {address: sv.address||'', name: sv.server_name||''} : null;
  if(sv.available && (sv.server_name || sv.address)){
    box.style.display='';
    $('srvName').textContent = sv.server_name || sv.address;
    var sm=[];
    if(sv.map) sm.push(sv.map);
    if(sv.players!==null && sv.players!==undefined && sv.maxplayers) sm.push(sv.players+'/'+sv.maxplayers+' 人');
    if(sv.joined_text) sm.push('进入于 '+sv.joined_text);
    if(sv.in_server) sm.push('已连上该服');
    else if(sv.confirmed) sm.push('已确认在服内');
    /* 定位依据：netstat 看不到 CS2 连接时，当前服是靠「进服证据」推出来的，
       标一下来源，玩家截图反馈时就能一眼看清是靠哪条证据定位的 */
    if(!sv.in_server && sv.addr_source && sv.addr_source!=='netstat-udp'){
      var _SRC={'steam-log':'最近一次启动记录','browser-hist':'服务器浏览器历史',
                'cs2-log':'游戏日志','broadcast-relocate':'广播地图反查'};
      sm.push('定位依据：'+(_SRC[sv.addr_source]||sv.addr_source));
    }
    if(sv.stale) sm.push('数据 '+sv.stale_age+' 秒前（查询重试中）');
    if(!sv.query_ok && !sv.stale) sm.push('查询未响应');
    if(sv.available && !sv.game_running) sm.push('CS2 已退出');
    $('srvMeta').textContent = sm.join(' · ');
  } else { box.style.display='none'; }

  var cur=d.current||{};
  /* 数据快照比对：四宫格 / 提示条 / 关卡表只依赖这几样，内容没变就整段跳过
     （此前每秒 innerHTML 全量重建，白耗 layout/paint 还会丢悬停状态） */
  var __snap=JSON.stringify([d.state,d.map,d.mapcn,d.stage,d.shown_stage,d.source,
                             d.stage_hint,cur,d.stages]);
  var dataChanged=__snap!==window.__dataSnap;
  window.__dataSnap=__snap;
  var g=$('grid');
  if(dataChanged){
  g.innerHTML='';
  var lastKV=window.__lastKV||{}, newKV={};
  /* 四宫格分两组：「通关奖励」是进图前就该知道的固定值，「战斗伤害」是达标门槛——
     每打满该数值的伤害就额外 +1 云点/龙晶（如 3w 伤害 = 1 云点），不是本局实时累计 */
  var GROUPS=[
    ['🏆 通关奖励','进图前可查',[
      ['通关云点','rankPasses','hiA lnA',' 点','云点'],
      ['通关龙晶','econPasses','hiB lnB',' 颗','龙晶']]],
    ['💥 战斗伤害','达标奖励 · 每满一档 +1',[
      ['云点伤害','rankDamage','lnA',' 伤害','云点'],
      ['龙晶伤害','econDamage','lnB',' 伤害','龙晶']]]
  ];
  GROUPS.forEach(function(grp){
    var wrap=document.createElement('div'); wrap.className='kvg';
    wrap.innerHTML='<div class="kgt">'+grp[0]+' <span class="ksub">'+grp[1]+'</span></div>'+
      '<div class="grid"></div>';
    var grid=wrap.querySelector('.grid');
    grp[2].forEach(function(it){
      var div=document.createElement('div'); div.className='kv'+(it[2]?' '+it[2]:'');
      var isPass=(it[1]==='rankPasses'||it[1]==='econPasses');
      var raw=cur[it[1]];
      var v=isPass?n(raw):wan(raw);
      /* 伤害类是达标门槛：悬停说明「每多少伤害额外 +1」，原始值一并列出 */
      if(!isPass && raw!==null && raw!==undefined && raw!==''){
        div.title='本关每造成 '+wan(raw)+' 伤害，额外 +1 '+(it[1]==='rankDamage'?'云点':'龙晶')+
          '（门槛原始值 '+raw+'）';
      }
      div.innerHTML='<div class="k">'+it[0]+(it[4]?'<span class="up">'+it[4]+'</span>':'')+
        '</div><div class="v"><span class="val">'+v+'</span>'+
        (it[3]?'<span class="u">'+it[3]+'</span>':'')+'</div>';
      grid.appendChild(div);
      newKV[it[1]]=String(v);
      /* 效果 C：值真的变化时才脉冲（每 1 秒刷新但值不变不闪） */
      if(document.documentElement.classList.contains('aFlash') &&
         lastKV[it[1]]!==undefined && lastKV[it[1]]!==String(v)){
        var el=div.querySelector('.val');
        el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
      }
    });
    g.appendChild(wrap);
  });
  window.__lastKV=newKV;

  var hint=$('hint');
  if(!d.ok && (d.state==='offline'||d.state==='warming')){
    /* 未进服 / 正在查询：不显示提示条（用户要求隐藏），保持静默等待自动定位 */
    hint.style.display='none';
  } else if(!d.ok){
    hint.style.display=''; hint.className='hint warn';
    hint.textContent = d.state==='noreward'
      ? '已定位到服务器与地图，但这张图不在仓库 rewards 目录里（大厅图等）。'
      : '认不出地图。请把下面的广播原文发给开发者，按真实格式补规则。';
  } else if(d.stage===null || d.stage===undefined){
    /* 已定位到地图但关卡号缺：说清原因 + 说明下方数字是第几关的 */
    hint.style.display=''; hint.className='hint warn';
    var sg=(d.shown_stage!==null&&d.shown_stage!==undefined)?d.shown_stage:'1';
    hint.textContent='这张图共 '+NST+' 关，当前关卡号还没拿到，'
      +'下方数字按第 '+sg+' 关显示（下表可查全部关卡）。'
      +(d.stage_hint?('原因：'+d.stage_hint):'');
  } else { hint.style.display='none'; }

  var tb=$('tbody'); tb.innerHTML='';
  if(!d.stages || !d.stages.length){
    tb.innerHTML='<tr><td colspan="4" class="s">无数据</td></tr>';
  } else {
    d.stages.forEach(function(r){
      var tr=document.createElement('tr');
      if(d.stage!==null && String(d.stage)===String(r.stage)) tr.className='cur';
      var x=r.data||{};
      /* 伤害列与 KPI 卡 / 地图库同款「万」写法，悬停看原始值 */
      tr.innerHTML='<td>'+(String(d.stage)===String(r.stage)?'▶ ':'')+r.stage+'</td>'+
        '<td>'+n(x.rankPasses)+'<span class="u">点</span></td>'+
        '<td>'+n(x.econPasses)+'<span class="u">颗</span></td>'+
        '<td title="'+((x.rankDamage===null||x.rankDamage===undefined||x.rankDamage==='')?'':('原始值 '+x.rankDamage))+'">'+
        wan(x.rankDamage)+'</td>';
      tb.appendChild(tr);
    });
  }
  } /* end if(dataChanged) —— 数据没变时四宫格/提示条/关卡表整段跳过 */

  /* 广播原文：有内容才显示 <pre>，空的时候给空态指引（而不是一对括号） */
  var rawTxt=d.raw||'';
  var hasRaw=!!rawTxt.replace(/\s/g,'');
  $('raw').textContent = hasRaw ? rawTxt : '';
  $('raw').style.display = hasRaw ? '' : 'none';
  $('rawEmpty').style.display = hasRaw ? 'none' : '';
  if(!hasRaw){
    $('rawEmptyPath').textContent='广播文件 '+(d.broadcast_file||'—')+
      (d.raw_mtime_str?(' · 最后更新 '+d.raw_mtime_str):'');
  }
  $('fileInfo').textContent = hasRaw
    ? ('广播文件更新于 '+(d.raw_mtime_str||'—'))
    : (d.broadcast_file ? ('广播文件 '+(d.broadcast_file||'')) : '广播文件 —');
  $('built').textContent = '数据索引构建于 '+(d.built_at||'—')+' · 每 1 秒自动检测';
  fillAbout(d);
  syncUI(d);
  ovUI(d);
}

/* ─── 设置页「关于」卡 ───
   数据从 /api/about 单独取，不再挂在每秒轮询的 /api/status 上。
   原来的 about_payload() 会对云端发一次 HEAD（最长 6s）+ 扫 terr 目录，
   每秒轮询时断网就会把整个请求线程挂住，界面跟着卡 —— 典型的「只有设置页要看、
   却让所有页都买单」。改成切到设置页才拉，8 秒内不重复。 */
var ABOUT=null, ABOUT_AT=0, _abBusy=false;
function loadAbout(force){
  if(!force && ABOUT_AT && Date.now()-ABOUT_AT<8000) return;
  if(_abBusy) return;                      /* 首屏预热与进页拉取可能撞在一起 */
  _abBusy=true;
  get('/api/about').then(function(j){ ABOUT=j; ABOUT_AT=Date.now(); fillAbout(j); })
    .catch(function(){}).then(function(){ _abBusy=false; });
}
function fillAbout(d){
  var a=ABOUT; if(!a) return;
  $('abVer').textContent=(a.version||'—')+(a.built_at?(' · 索引 '+a.built_at):'');
  $('abPort').textContent=(a.port?('127.0.0.1:'+a.port):'—')+
    (a.port_note?('（'+a.port_note+'）'):'（默认固定 8777，仅本机可访问）');
  var di=a.datainfo||{};
  $('abData').textContent=(di.maps!==undefined&&di.maps!==null)
    ? (di.maps+' 张地图 / '+di.stages+' 个关卡配置') : '—';
  $('abDir').textContent=a.data_dir||'—';
  $('abDir').title=a.data_dir||'';
  $('abLog').textContent=a.log_path||'—';
  $('abLog').title=a.log_path||'';
  /* ⑪ 日志体积：超 512KB 会归档成 startup.old.log，胶囊转为暖色提示 */
  var szEl=$('abLogSz');
  if(szEl){
    var s=a.log_size;
    if(s===null||s===undefined){ szEl.textContent=''; szEl.className='lsz'; }
    else{
      szEl.textContent = s<1024 ? (s+' B') : (s<1048576 ? (s/1024).toFixed(1)+' KB' : (s/1048576).toFixed(2)+' MB');
      szEl.className='lsz'+(s>512000?' big':'');
      szEl.title = s>512000
        ? '已超过 512KB，下次写入时归档为 startup.old.log'
        : '超过 512KB 自动归档为 startup.old.log';
    }
  }
  /* 预览壳（v2.0）：实体数据，v2.14 起随包分发，落在软件目录。 */
  var pEl=$('abPv'), pvv=a.pv||{};
  if(pEl){
    pEl.textContent = pvv.ready
      ? ('已就绪 · '+((pvv.size||0)/1048576).toFixed(1)+' MB'+(pvv.at?(' · '+pvv.at):''))
      : '尚未就绪（重新解压完整压缩包可恢复）';
    pEl.title = pvv.path || '尚未下载';
  }
  window.__abPaths={dir:a.data_dir||'',log:a.log_path||''};
  /* 杀软误报自助：把「软件所在目录」拼进白名单命令。
     注意加白名单的是**目录**而不是单个 exe —— 一键更新会替换 exe，
     只信任旧 exe 的话下次更新又被拦一次。*/
  var avDir=(a.data_dir||'').replace(/[\\/]data$/,'') || (a.data_dir||'');
  var avCmd='Add-MpPreference -ExclusionPath "'+avDir+'"';
  var avCmdEl=$('abAvCmd'); if(avCmdEl) avCmdEl.textContent=avCmd;
  var avRm='Remove-MpPreference -ExclusionPath "'+avDir+'"';
  window.__abAv={cmd:avCmd, rm:avRm, dir:avDir};
  /* 封面（v2.14）：本地张数 + 上次自动补齐结果。封面随包分发，新图在
     地图数据同步后由 cover_sync() 直连官方图床补齐，不必等版本更新。*/
  var cvEl=$('abCover'), cv=a.cover||{}, cs=a.cover_sync||{};
  if(cvEl){
    var cvTxt=(cv.count||0)+' 张（本地）';
    if(cs.running) cvTxt+=' · 正在补齐 '+cs.checked+' 张…';
    else if(cs.at){
      cvTxt += cs.got ? (' · 上次补齐 '+cs.got+' 张 · '+cs.at)
                      : (' · 已是最新 · '+cs.at);
    }
    cvEl.textContent=cvTxt;
    cvEl.title='新图封面在「地图数据同步」完成后自动从官方图床补齐（resx.fyscs.cn），存进软件目录的 cover 文件夹';
  }
  /* 地形分包（v1.6）：3D 预览的真实碰撞网格，v2.14 起随包分发，落在软件目录的 terr\。
     这里显示占用并提供一键清理——体积敏感的用户清完就只剩几十 MB。 */
  var tEl=$('abTerr'), tB=$('abTerrClear'), tt=a.terr||{};
  if(tEl){
    var tcnt=tt.count||0, tmb=tt.mb||0;
    tEl.textContent = tcnt
      ? (tcnt+' / '+(tt.total||857)+' 张 · '+tmb.toFixed(1)+' MB')
      : '尚未就绪（缺文件时重新解压完整压缩包）';
    tEl.title = tcnt ? '已随包分发的地形分包，位于软件目录的 terr 文件夹' : '';
    if(tB){
      tB._last={cnt:tcnt, mb:tmb};
      if(!tB._bound){
        tB._bound=1;
        tB.onclick=function(){
          var L=tB._last||{cnt:0,mb:0};
          if(!(L.cnt>0)){
            tB.textContent='已空';
            setTimeout(function(){ tB.textContent='🧹 清理'; }, 1200);
            return;
          }
          if(!confirm('删除已缓存的 '+L.cnt+' 张地形（约 '+L.mb.toFixed(1)+' MB）？删掉后这些图看不了 3D 视图，重新解压完整压缩包可恢复。')) return;
          tB.disabled=true; tB.textContent='清理中…';
          fetch('/api/terr/clear')
            .then(function(){ return fetch('/api/about'); })
            .then(function(r){ return r.json(); })
            .then(function(j){ ABOUT=j; ABOUT_AT=Date.now(); fillAbout(j); })
            .catch(function(){})
            .then(function(){ tB.disabled=false; tB.textContent='🧹 清理'; });
        };
      }
    }
  }
  var av=$('auVer'); if(av && a.version) av.textContent=a.version;
  var sv=$('setUpdVer'); if(sv && a.version) sv.textContent='当前版本 '+a.version;
  /* 更新日志：about.changelog = [{ver,date,groups:[{t,items:[…]}]}, …]，新版本在最前。
     v2.2 起按「新增 / 优化 / 修复 / 移除」分组渲染；旧格式 items 扁平列表兼容回退。
     手风琴式——版本行可点开/收起，默认只展开当前版本；最早版本标「首发」，
     当前版本（与 version 相同）标「当前版本」。 */
  var clg=$('clgCard');
  if(clg){
    var cl=a.changelog||[];
    var CLG_TAG={'新增':'t-new','优化':'t-imp','修复':'t-fix','移除':'t-rem'};
    function clgBody(c){
      var gs=c.groups;
      if(gs&&gs.length){
        return gs.map(function(g){
          return '<div class="clgT '+(CLG_TAG[g.t]||'')+'"><b>'+esc(g.t||'')+
                 '</b>'+g.items.length+' 项</div><ul class="clg">'+
                 g.items.map(function(it){ return '<li>'+esc(it)+'</li>'; }).join('')+'</ul>';
        }).join('');
      }
      return '<ul class="clg">'+(c.items||[]).map(function(it){
        return '<li>'+esc(it)+'</li>'; }).join('')+'</ul>';
    }
    function clgCount(c){
      return (c.groups&&c.groups.length)
        ? c.groups.reduce(function(n,g){ return n+g.items.length; },0)
        : (c.items||[]).length;
    }
    /* 本函数跑在每秒一次的 status 轮询里。无脑重刷 innerHTML 会把用户点开的版本
       折叠回去（实测：点开 v1.4 后 1 秒就被弹回只剩「当前版本」）。
       内容没变就不重建，用户展开的状态自然保得住。 */
    /* v2.3：列表太长——默认只渲染当前版本，其余历史版本收进「展开全部历史版本」，
       点一下才展开；版本行手风琴交互不变 */
    function clgOne(c){
      var cur=c.ver===a.version, last=cl.indexOf(c)===cl.length-1, tag='';
      if(cur) tag='<span class="clglx">当前版本</span>';
      else if(last) tag='<span class="clglx">首发</span>';
      return '<div class="clgvw'+(cur?' open':'')+'">'+
             '<div class="clgv"><span class="clgarr">▶</span>'+
             '<b>'+esc(c.ver||'')+'</b>'+
             '<span class="clgd">'+esc(c.date||'')+'</span>'+
             '<span class="clgct">'+clgCount(c)+' 条</span>'+tag+'</div>'+
             clgBody(c)+'</div>';
    }
    var sig=(a.version||'')+'|'+cl.length+'|'+JSON.stringify(cl);
    if(clg._sig!==sig){
      clg._sig=sig;
      var curList=cl.filter(function(c){ return c.ver===a.version; });
      var oldList=cl.filter(function(c){ return c.ver!==a.version; });
      clg._oldn=oldList.length;
      clg.innerHTML = cl.length
        ? curList.map(clgOne).join('')+
          (oldList.length
            ? '<div class="clgmore">📜 展开全部 '+oldList.length+' 个历史版本 ▾</div>'+
              '<div class="clgold" hidden>'+oldList.map(clgOne).join('')+'</div>'
            : '')
        : '<div class="clgEmpty">—</div>';
    }
    if(!clg._bound){                      /* 监听挂在容器上，重建子节点不影响它 */
      clg._bound=1;
      clg.onclick=function(e){
        var m=e.target.closest('.clgmore');
        if(m){
          var o=clg.querySelector('.clgold'); if(!o) return;
          o.hidden=!o.hidden;
          m.textContent=o.hidden
            ? '📜 展开全部 '+clg._oldn+' 个历史版本 ▾'
            : '📜 收起历史版本 ▴';
          return;
        }
        var h=e.target.closest('.clgv'); if(!h) return;
        h.parentElement.classList.toggle('open');
      };
    }
  }
}

/* 通用复制（clipboard 优先，execCommand 兜底）：复制的路径 / QQ 都走这一个 */
function copyText(txt, btn, back){
  if(!txt) return;
  var done=function(){
    btn.className='cbtn done'; btn.textContent='✅';
    setTimeout(function(){ btn.className='cbtn'; btn.textContent=back; },1300);
  };
  var fallback=function(){
    try{
      var ta=document.createElement('textarea'); ta.value=txt;
      ta.style.cssText='position:fixed;top:-999px;opacity:0';
      document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); document.body.removeChild(ta); done();
    }catch(e){}
  };
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(txt).then(done, fallback);
  } else { fallback(); }
}

/* 作者名片：复制 QQ。本地 http(127.0.0.1) 属安全上下文，clipboard 可用，execCommand 兜底 */
function bindAuthor(){
  var b=$('auCopy'); if(!b) return;
  var numEl=$('auQQ');
  var qq=(numEl?numEl.textContent:'').trim();
  b.onclick=function(){
    if(b.className.indexOf('done')>=0) return;
    var done=function(){
      b.className='cbtn done'; b.textContent='✅ 已复制 '+qq;
      setTimeout(function(){ b.className='cbtn'; b.textContent='📋 复制 QQ'; },1600);
    };
    var fallback=function(){
      try{
        var ta=document.createElement('textarea'); ta.value=qq;
        ta.style.cssText='position:fixed;top:-999px;opacity:0';
        document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); document.body.removeChild(ta); done();
      }catch(e){}
    };
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(qq).then(done, fallback);
    } else { fallback(); }
  };
}

var __tickBusy=false;
var __lastOkAt=0;                    /* 上次成功拉到数据的时间（失败提示用） */
function tick(force){
  /* 上一发还没回来就不发第二发：A2S 重试时后端一次可能要 2~3 秒，
     1 秒一发会让响应乱序、旧数据盖掉新数据。
     force=true 供「🔄 立即重读」按钮用 —— 否则点它时大概率正有一发在飞，
     按钮变成「重读中…」却什么也没做。 */
  if(__tickBusy && !force) return;
  __tickBusy=true;
  get('/api/status').then(function(d){
    __lastOkAt=Date.now();
    render(d);
  }).catch(function(){
    var s='服务未响应 · 自动重试中';
    if(__lastOkAt) s+='（最后成功 '+new Date(__lastOkAt).toTimeString().slice(0,8)+'）';
    $('stateText').textContent=s;
    $('pill').className='pill off';
  }).then(function(){ __tickBusy=false; });
}

var __srvBusy=false;
function tickServers(){
  /* 同 tick()：9 台服各查 2 轮 A2S，一次可能要 1~3 秒，上一发没回来不重发 */
  if(__srvBusy) return;
  __srvBusy=true;
  get('/api/servers').then(function(d){
    var rows=(d&&d.rows)||[];
    /* 索引还没读进内存时，「未收录」是假结论（后端 rewards 空表）。
       前端分开表述：读取中…，并很快补一发，别让玩家以为官方没这张图 */
    var idx=!!(d&&d.index_ready);
    /* 快照比对：数据没变就整表跳过重建（悬停/当前行状态不再每 15 秒闪一下）。
       「当前所在」高亮依赖 /api/status 判定的 __curSrv，一并计入快照 */
    var snap=JSON.stringify([rows,window.__curSrv||null,idx]);
    var changed=snap!==window.__srvSnap;
    window.__srvSnap=snap;
    var tb=$('stb');
    if(changed){
    tb.innerHTML='';
    if(!rows.length){
      tb.innerHTML='<tr><td colspan="5" class="s">⏳ 正在加载服务器清单…（首次启动需几秒钟）</td></tr>';
    } else {
      rows.forEach(function(x){
        var tr=document.createElement('tr');
        /* 高亮只标「当前所在服」：address 匹配优先，server_name 兜底；列表外的服不标 */
        var cs=window.__curSrv||null;
        var isCur=!!cs && x.address && cs.address &&
          (x.address===cs.address ||
           (cs.name && x.name && x.name===cs.name));
        if(isCur) tr.className='cur';
        /* 官方登记名与服务器实际地图名偶有 1~2 个字符出入（后端会近似命中），
           给个小标记说明来源，免得玩家以为是数据串了 */
        var apx=x.map_approx
          ? ' <span class="apx" title="服务器地图名与官方登记名有出入，已按 '+esc(x.map_approx)+' 匹配">≈</span>'
          : '';
        var pv='—', ev='—';
        if(x.passes_min!==null && x.passes_min!==undefined){
          pv=(x.passes_min===x.passes_max)?String(x.passes_min):(x.passes_min+'~'+x.passes_max);
          pv+=' <span class="s">('+x.stages+' 关)</span>';
        } else if(x.map){ pv=idx?'<span class="s">未收录</span>':'<span class="s">读取中…</span>'; }
        if(x.econ_min!==null && x.econ_min!==undefined){
          ev=(x.econ_min===x.econ_max)?String(x.econ_min):(x.econ_min+'~'+x.econ_max);
        } else if(x.map){ ev=idx?'<span class="s">未收录</span>':'<span class="s">读取中…</span>'; }
        /* ≈ 跟「地图名」走：它说的就是名字与官方登记名有出入，
           放在「通关云点」列里容易被读成「云点数是近似值」 */
        var mapCell=esc(n(x.map))+apx;
        if(x.mapcn) mapCell+='<div class="mapcn" title="'+esc(x.mapcn)+'">'+esc(x.mapcn)+'</div>';
        /* 官网人数交叉校验：一致时只留一个小绿点（9 台全一致时不再刷 9 行「✓ 官网一致」），
           只在真有分歧时出文字，一眼就能看到是哪台对不上 */
        var webHtml='';
        if(x.web){
          var webSide='风雲社官网实时：'+(x.web.players==null?'—':x.web.players+'/'+x.web.maxplayers)+
              '　本机探测：'+(x.players==null?'—':x.players+'/'+x.maxplayers);
          if(x.web.same===true){
            webHtml+='<span class="wdot" title="与风雲社官网一致 · '+webSide+'"></span>';
          }else if(x.web.players===null||x.web.players===undefined){
            /* 官网也没探到这台：不算分歧，给个中性的小问号 */
            webHtml+='<span class="wdiff" title="官网暂无这台的数据 · '+webSide+'">官网 —</span>';
          }else{
            /* 文案压短：原来「⚠ 官网 12 ≠ 本机」在 13% 窄列里会被裁掉半截，
               完整对比（官网 x/y　本机 x/y）都放 title 里 */
            webHtml+='<span class="wdiff hot" title="'+webSide+'">⚠ 官网 '+
                x.web.players+'</span>';
          }
        }
        var pc;
        if(x.players===null||x.players===undefined){
          pc='<span class="s">—</span>'+(webHtml?'<div class="onweb">'+webHtml+'</div>':'');
        }else{
          var pct=Math.max(0,Math.min(100,Math.round(x.players/x.maxplayers*100)));
          var ocls=(x.maxplayers&&x.players>=x.maxplayers)?'g':(pct>=70?'h':(pct>=25?'m':'l'));
          pc='<div class="online '+ocls+'"><div class="onnum">'+x.players+
             '<span class="oncap">/'+x.maxplayers+'</span></div>'+
             '<div class="onbar"><i class="onfill" style="width:'+pct+'%"></i></div>'+
             (webHtml?'<div class="onweb">'+webHtml+'</div>':'')+'</div>';
        }
        tr.innerHTML='<td class="s" style="max-width:210px;white-space:normal;word-break:break-all">'+
          (isCur?'▶ ':'')+esc(x.name||x.address)+
          (isCur?'<span class="curpill">当前所在</span>':'')+
          '</td><td'+(x.map?' title="'+esc(x.map)+'"':'')+'>'+mapCell+'</td>'+
          '<td>'+pv+'</td><td>'+ev+'</td><td>'+pc+'</td>';
        if(x.map){
          tr.className=(tr.className?tr.className+' ':'')+'srvrow';
          tr.title='点击查看每关通关云点 / 龙晶';
          tr.onclick=function(){ openStages(x.map); };
        }
        tb.appendChild(tr);
      });
    }
    } /* end if(changed) —— 列表没变时不重建 */
    /* 汇总拆成一排胶囊：左＝本机探测，右＝官网同步，不再是 100 字长句 */
    var on=(d.online!==undefined?d.online:d.count)||0, all=(d.count)||0;
    var at=$('srvAt');
    at.textContent='🕒 探测于 '+(d.at||'—');
    at.title=''; at.style.cursor=''; at.onclick=null;   /* 清掉失败态留下的重试钩子 */
    $('srvOn').textContent='在线 '+on+' / '+all+' 台';
    $('srvOn').title='風雲社僵尸逃跑服固定清单 01#~09#';
    /* 官网口径：后端 /api/servers 顶层字段 web（可能是 null，用 {} 兜底） */
    var web=$('srvWeb'), w=d.web||{};
    if(w.ok){
      web.textContent='🌐 官网同步 '+((w.at)||'—')+' · 全站 '+((w.servers)||0)+' 台 / '+
        ((w.players)||0)+' 人 · 匹配 '+((w.matched)||0)+' 台';
      web.title='风雲社官网实时数据：全站 '+((w.servers)||0)+' 台 / '+((w.players)||0)+
        ' 人，本表匹配 '+((w.matched)||0)+' 台';
    } else if(w.err){
      web.textContent='🌐 官网数据未获取';
      web.title='官网数据未获取（'+w.err+'）';
    } else {
      web.textContent='🌐 官网 —';
      web.title='尚未取到官网数据';
    }
    /* 清单还空着（刚启动，watcher 第一轮没回来）：2 秒后快速补一发，
       别干等 15 秒的常规轮询 —— 2026-09-26 用户实测「打开后清单空了好一会儿」 */
    if(!rows.length) setTimeout(function(){ tickServers(); }, 2000);
    /* 索引还在读（首次安装 / 缓存损坏）：0.8 秒后补一发，一就绪立刻换成真实数值，
       不用干等 15 秒常规轮询 */
    else if(!idx) setTimeout(function(){ tickServers(); }, 800);
  }).catch(function(){
    /* 失败别无声吞掉：亮提示 + 可点击立即重试（下一轮 15s 定时也会自动补） */
    var at=$('srvAt');
    at.textContent='⚠ 服务器列表刷新失败 · 自动重试中';
    at.title='点击立即重试';
    at.style.cursor='pointer';
    at.onclick=function(){ tickServers(); };
  }).then(function(){ __srvBusy=false; });
}

function boot(){
  renderRecent();   /* ⑯ 恢复上次会话的「最近查看」（空闲态补位） */
  /* ⑭ 鼠标滚轮在分类胶囊行上下滚 → 平移横滑（触控板原生横滑不受影响） */
  document.querySelectorAll('.rowline').forEach(function(el){
    el.addEventListener('wheel',function(ev){
      if(Math.abs(ev.deltaY)>Math.abs(ev.deltaX)){
        el.scrollLeft+=ev.deltaY; ev.preventDefault();
      }
    },{passive:false});
  });
  /* 先取界面偏好（主题/视图/动画），再初始化界面 */
  get('/api/prefs').then(function(p){ PREFS=p&&p.prefs?p.prefs:{}; })
    .catch(function(){ PREFS={}; })
    .then(bootReal);
  /* 「关于」预热：延后到首屏稳定之后拉一次，避免用户不进设置页时
     「更新日志」卡一直是空的；不进每秒轮询，对性能没有影响。 */
  setTimeout(function(){ loadAbout(); }, 2500);
}
/* ── 一键更新 ─────────────────────────────────────────────────────────
   启动时后台查一次服务端版本号；有新版就在「更新日志」上方亮一条横幅，
   并弹一个居中提示窗（同一版本点过「稍后再说」就不再弹，横幅常驻可随时更新）。
   检查失败（没网/服务端下线）静默跳过，不打扰正常使用。 */
function updModal(u){
  var mb=u.size?(u.size/1048576).toFixed(1)+'MB':'';
  var notes=(u.notes||[]);
  var ov=document.createElement('div'); ov.id='updModal';
  ov.innerHTML='<div class="updM" role="dialog" aria-label="发现新版本">'+
    '<div class="updMH">🚀 发现新版本 <b>'+esc(u.ver||'')+'</b>'+
      '<small>当前 '+esc(u.cur||'')+(mb?(' · 约 '+mb):'')+'</small></div>'+
    (u.intro?'<p class="updMI">'+esc(u.intro)+'</p>':'')+
    '<ul class="updML">'+
      notes.slice(0,3).map(function(n){ return '<li>'+esc(n)+'</li>'; }).join('')+
      (notes.length>3?'<li class="more">…等共 '+notes.length+' 条更新内容</li>':'')+
    '</ul>'+
    '<div class="updMF">'+
      '<button class="btn" id="updLater">稍后再说</button>'+
      '<button class="btn pri" id="updNow">立即更新</button>'+
    '</div></div>';
  document.body.appendChild(ov);
  ov.onclick=function(e){ if(e.target===ov){ ov.remove(); savePrefs('upd_dismiss',u.ver||''); } };
  $('updLater').onclick=function(){ ov.remove(); savePrefs('upd_dismiss',u.ver||''); };
  $('updNow').onclick=function(){
    ov.remove();
    showView('set');                       /* 横幅在设置页更新日志上方，带真实进度 */
    var b=$('updGo'); if(b) b.click();
  };
}
function showUpdBar(u){
  /* 渲染设置页一键更新横幅（含下载进度/重试）。启动自动检查与设置页
     「检查更新」按钮共用这一段（2026-11-16：更新入口集中到设置页）。 */
  var bar=$('updBar'); if(!bar) return;
  if(!u||!u.has_update){ bar.style.display='none'; return; }
    var mb=u.size?(u.size/1048576).toFixed(1)+'MB':'';
    bar.style.display='flex';
    bar.innerHTML='<span>🚀</span><span>发现新版本 <b>'+esc(u.ver||'')+'</b></span>'+
      '<small>'+esc((u.notes||[])[0]||'')+(mb?(' · 约 '+mb):'')+'</small>'+
      '<button class="btn" id="updGo">一键更新</button>';
    var btn=$('updGo');
    btn.onclick=function(){
      btn.disabled=true; btn.textContent='准备下载…';
      /* 半秒轮一次下载进度，把「只能干等」换成真实 MB 进度（后端流式写盘并计数） */
      var pt=setInterval(function(){
        get('/api/update/progress').then(function(p){
          if(!p) return;
          if(p.phase==='download'&&p.total){
            btn.textContent='正在下载 '+(p.got/1048576).toFixed(1)+' / '+
              (p.total/1048576).toFixed(1)+'MB';
          } else if(p.phase==='retry'){ btn.textContent='下载中断，自动重试…'; }
          else if(p.phase==='verify'){ btn.textContent='校验完整性…'; }
          else if(p.phase==='install'){ btn.textContent='正在替换重启…'; }
        }).catch(function(){});
      },500);
      var stop=function(){ clearInterval(pt); };
      get('/api/update/apply').then(function(r){
        stop();
        if(r&&r.ok){ btn.textContent='更新完成，正在重启…'; }
        else{
          btn.disabled=false; btn.textContent='重试更新';
          bar.querySelector('small').textContent='更新失败：'+((r&&r.error)||'未知错误');
        }
      }).catch(function(){
        stop();
        btn.disabled=false; btn.textContent='重试更新';
        bar.querySelector('small').textContent='更新失败：网络中断';
      });
    };
    /* 启动弹窗提示（只在启动自动检查时弹）：同一版本点过「稍后再说」
       （或点遮罩关闭）就不再弹；设置页手动检查不重复弹（结果就地显示） */
}
function checkUpdate(){
  get('/api/update/check').then(function(u){
    showUpdBar(u);
    if(u && u.has_update && PREFS.upd_dismiss!==u.ver){ updModal(u); }
  }).catch(function(){});
}
function setUpdCheck(){
  /* 设置页「检查更新」按钮：强制刷新（绕过 10 分钟缓存），结果就地反馈 */
  var btn=$('setUpdBtn'), stat=$('setUpdStat');
  if(!btn) return;
  btn.disabled=true; btn.textContent='检查中…';
  if(stat) stat.textContent='';
  get('/api/update/check?force=1').then(function(u){
    btn.disabled=false; btn.textContent='🔄 检查更新';
    if(!u){ if(stat) stat.textContent='检查失败：网络问题，稍后再试'; return; }
    if(u.offline){ if(stat) stat.textContent='当前离线，无法检查更新'; return; }
    if(!u.has_update){
      if(stat){ stat.textContent='已是最新版 ✓'; }
      var bar=$('updBar'); if(bar) bar.style.display='none';
      return;
    }
    if(stat) stat.textContent='发现新版本 '+esc(u.ver||'')+'，点「一键更新」即可';
    showUpdBar(u);                       /* 就地渲染一键更新（含真实进度） */
    var bar=$('updBar');
    if(bar && bar.scrollIntoView) bar.scrollIntoView({behavior:'smooth',block:'center'});
  }).catch(function(){
    btn.disabled=false; btn.textContent='🔄 检查更新';
    if(stat) stat.textContent='检查失败：网络问题，稍后再试';
  });
}
/* 内置启动界面阶段文案（v2.15）：启动卡就在本页面里（#bootSplash），
   bootReal 各阶段顺手更新提示文字；页面没画启动卡时静默跳过。 */
function bsPhase(t){
  var el=document.getElementById('bsPhase');
  if(el) el.textContent=t;
}
/* 启动卡进度：按真实里程碑填充（18 界面搭建 / 55 连数据 / 100 就绪） */
function bsStep(p){
  var el=document.querySelector('#bootSplash .bsBar i');
  if(el) el.style.width=p+'%';
}
function bootReal(){
  bsPhase('正在准备界面…'); bsStep(18);
  buildFX();
  buildBGs();          /* 先定背景：applyTheme 会读 bgCur 重算底纹明暗 */
  buildStickers();     /* 侧栏贴纸独立自选，默认云朵精灵 */
  checkUpdate();       /* 一键更新：后台查一次服务端版本（失败静默） */
  /* 运行中也持续盯新版本：原来只在启动时查一次，软件一开几天就永远
     收不到提示。每 15 分钟查一次（后端有 10 分钟缓存，开销可忽略），
     发现新版横幅常驻 + 弹提示窗，不用重启软件。句柄挂 window 方便测试 */
  window.UPD_TIMER=setInterval(checkUpdate, 15*60*1000);
  buildThemes();
  libInit();
  initView();
  wireTitlebar();
  $('foldBtn').onclick=function(){ fold(true); };
  $('reopenBtn').onclick=function(){ fold(false); };
  $('btnSync').onclick=function(){
    /* 立即进「同步中…」：原来要等下一轮 1 秒轮询的 syncUI() 才变，
       点下去那一秒完全没反馈，用户会以为没点上。 */
    this.disabled=true; this.textContent='同步中…';
    $('syncInfo').textContent='🔄 正在同步…';
    get('/api/ctl?do=sync').catch(function(){
      var b=$('btnSync');
      if(b){ b.disabled=false; b.textContent='立即同步'; }
      $('syncInfo').textContent='❌ 同步请求失败（服务未响应）';
    });
  };
  /* ── 上游数据更新提醒：横幅按钮 + 明细弹窗 + 设置开关 ── */
  $('updBView').onclick=openDiff;
  $('updBGo').onclick=function(){ triggerUpdSync($('updBSub')); };
  /* ── 软件更新卡：随时手动检查是否最新版 ── */
  var suBtn=$('setUpdBtn');
  if(suBtn) suBtn.onclick=setUpdCheck;
  $('updBX').onclick=function(){
    /* 点了「知道了」立刻收起（不等下一轮轮询），状态仍由服务端 diffseen 落盘 */
    UPD_WANT=false; bannerApply();
    get('/api/ctl?do=diffseen').catch(function(){});
  };
  $('diffLater').onclick=closeDiff;
  $('diffApply').onclick=function(){ closeDiff(); triggerUpdSync($('updBSub')); };
  /* ── 上游更新动态（台账）：有新记录才出现；查看或 ✕ 即确认，之后不再挂 ── */
  $('updLnView').onclick=function(){ ulAck(); openUpdLog(); };
  $('updLnX').onclick=ulAck;
  ulLoad();
  function bindSw(id, key, def){
    var el=$(id); if(!el) return;
    var v=PREFS[key]; if(v===undefined) v=def;
    el.className='sw'+(v?' on':'');
    el.onclick=function(){
      var nv=el.className.indexOf('on')<0;
      el.className='sw'+(nv?' on':'');
      savePrefs(key, nv);
    };
  }
  bindSw('swUpdSync','upd_autosync',true);
  bindSw('swUpdAuto','upd_auto',false);
  bindSw('swUpdDel','upd_del',true);
  /* 设置页「关于」卡：打开数据目录 / 运行日志 + 复制路径（⑧） */
  $('abDirBtn').onclick=function(){ get('/api/ctl?do=opendata').catch(function(){}); };
  $('abLogBtn').onclick=function(){ get('/api/ctl?do=openlog').catch(function(){}); };
  $('abDirCopy').onclick=function(){ copyText((window.__abPaths||{}).dir, this, '📋'); };
  $('abLogCopy').onclick=function(){ copyText((window.__abPaths||{}).log, this, '📋'); };
  /* 杀软误报自助：先展开说明（里面才有可复制的命令），按钮本身复制命令 */
  var avBtn=$('abAvBtn'), avHelp=$('abAvHelp');
  if(avBtn&&avHelp) avBtn.onclick=function(){
    avHelp.hidden=!avHelp.hidden;
    avBtn.textContent=avHelp.hidden?'🛡️ 怎么办':'🛡️ 收起';
  };
  var _avc=$('abAvCopy');
  if(_avc) _avc.onclick=function(){
    copyText((window.__abAv||{}).cmd, this, '📋');
    if(avHelp){ avHelp.hidden=false; if(avBtn) avBtn.textContent='🛡️ 收起'; }
  };
  var _avcc=$('abAvCmdCopy');
  if(_avcc) _avcc.onclick=function(){ copyText((window.__abAv||{}).cmd, this, '📋'); };
  /* 广播原文空态（⑨）：打开广播文件位置 / 立即重读 */
  $('rawLocBtn').onclick=function(){ get('/api/ctl?do=opentxtloc').catch(function(){}); };
  $('rawReBtn').onclick=function(){
    var b=this, old=b.textContent; b.disabled=true; b.textContent='🔄 重读中…';
    tick(true);                       /* 强制：绕过 __tickBusy，点了就一定重读 */
    setTimeout(function(){ b.disabled=false; b.textContent=old; },900);
  };
  bindAuthor();                                   /* 作者名片：复制 QQ */
  ovPaneInit();                                    /* 覆盖设置页：分区折叠状态（优化 1） */
  ovTabsInit();                                     /* 覆盖页内分栏（外观 / 直播 / 战绩） */
  (function(){                                      /* 设置页「去战绩页设置」→ 覆盖页战绩分栏 */
    var g=$('gsiGo');
    if(g && !g.__b){ g.__b=1; g.onclick=function(){ showView('ov'); ovTab('gsi'); }; }
  })();
  preWire();                                      /* 🗺️ pre 工具条（重载/独立窗口）；pvNow=去地图库定位 */
  $('rmOpen').onclick=openReadme;                 /* 设置页：点开使用说明 */
  $('btnOvToggle').onclick=function(){
    var on=this.className.indexOf('act')>=0;
    get('/api/ctl?do='+(on?'ovclose':'ovopen')).then(function(){ ovUI({ovon:!on}); }).catch(function(){});
  };
  get('/api/ovcfg').then(function(r){ window.__ovLivetxtPath=r.livetxt_path||''; ovBuild(r.fields||[], r.cfg); })
    .catch(function(){
      /* 拉不到配置时别留一片空白，给个可点的重试 */
      var box=$('ovChecks');
      if(box) box.innerHTML='<div class="sub" style="margin:0">覆盖配置读取失败 '+
        '<a href="javascript:location.reload()" style="color:var(--accent)">点此刷新</a></div>';
    });
  bsPhase('正在连接数据服务…'); bsStep(55);
  /* 轮询节流（2026-11-15）：CS2 没运行时分母乘 4（默认 1s → 4s），
     服务器列表 15s → 60s。render() 里按 game_running 更新 __idlePoll。 */
  window.__POLL_BASE = __POLL__;
  window.__POLL_IDLE = Math.max(4000, Math.round((__POLL__||1000)*4));
  var _pollT=0, _srvT=0;
  function pollLoop(force){
    clearTimeout(_pollT);
    if(!document.hidden) tick(force);
    _pollT=setTimeout(pollLoop, window.__idlePoll?window.__POLL_IDLE:window.__POLL_BASE);
  }
  function srvLoop(){
    clearTimeout(_srvT);
    if(!document.hidden) tickServers();
    _srvT=setTimeout(srvLoop, window.__idlePoll?60000:15000);
  }
  pollLoop(); srvLoop();
  /* 窗口隐藏（最小化/被遮挡）时停轮询省 CPU；切回来立即补一发，不等下一轮 */
  document.addEventListener('visibilitychange',function(){
    if(!document.hidden){ tick(true); tickServers(); }
  });
  var m=(location.hash||'').match(/^#stages=(.+)$/);
  if(m) openStages(decodeURIComponent(m[1]));
  /* 首次打开软件自动弹一次使用说明；?noreadme 可临时跳过（截图 / 调试用） */
  if(!readmeSeen() && !/[?&]noreadme/.test(location.search)){
    markReadmeSeen();
    openReadme();
  }
  /* 内置启动界面退场（v2.15）：bootReal 跑完 = 视图/主题/数据链已接好。
     最短显示 1.8 秒——启动快时把进度条走完再淡出，不让加载界面一闪而过；
     慢启动（冷缓存/首次同步）则就绪即走，不额外拖时间。 */
  bsPhase('准备就绪'); bsStep(100);
  var bs=document.getElementById('bootSplash');
  if(bs){
    var _shown=Date.now()-((typeof __bsT0!=='undefined'&&__bsT0)||Date.now());
    setTimeout(function(){
      bs.classList.add('bsOut');
      setTimeout(function(){ if(bs.parentNode) bs.parentNode.removeChild(bs); },500);
    }, Math.max(0, 1800-_shown));
  }
}

/* ── 关卡明细弹窗 ── */
function openStages(map){
  var ov=$('stgOv'), box=$('stgBox');
  ov.style.display='';
  $('stgTitle').textContent = map;
  $('stgSub').textContent = '加载中…';
  $('stgBody').innerHTML = '';
  fetch('/api/rewards?map='+encodeURIComponent(map), {cache:'no-store'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      var cn=d.mapcn ? '（'+d.mapcn+'）' : '';
      $('stgTitle').textContent = map + cn;
      if(!d.ok || !d.stages.length){
        $('stgSub').textContent='这张图不在仓库奖励目录里（例如大厅图），没有关卡数据。';
        return;
      }
      var st=d.stages;
      var rmin=null,rmax=null,emin=null,emax=null;
      st.forEach(function(s){
        [s.rankPasses].forEach(function(v){ if(v!==null&&v!==undefined){ rmin=(rmin===null)?v:Math.min(rmin,v); rmax=(rmax===null)?v:Math.max(rmax,v);} });
        [s.econPasses].forEach(function(v){ if(v!==null&&v!==undefined){ emin=(emin===null)?v:Math.min(emin,v); emax=(emax===null)?v:Math.max(emax,v);} });
      });
      $('stgSub').textContent='共 '+st.length+' 关 · 通关云点 '+(rmin===null?'未收录':(rmin===rmax?rmin:rmin+'~'+rmax))+
        ' · 通关龙晶 '+(emin===null?'未收录':(emin===emax?emin:emin+'~'+emax))+
        (d.is_new?' · 🆕 官方新收录':'');
      var h='<table class="stgtab"><thead><tr><th>关卡</th><th>通关云点</th><th>通关龙晶</th><th>云点伤害</th><th>龙晶伤害</th></tr></thead><tbody>';
      /* 伤害两项与页面表格同款「万」写法（原来这里是 12,800 千分位，两套写法不一致） */
      var raw=function(v){ return (v===null||v===undefined||v==='')?'':(' title="原始值 '+v+'"'); };
      st.forEach(function(s){
        /* 上游变更角标：这一关有字段被官方改过 → 数值旁标「↑ 原 旧值」 */
        var upb='';
        if(s.upd){
          for(var f in s.upd){
            upb+='<span class="updo" title="'+esc(f)+' 官方调整为新值，此前是 '+
                 esc(String(s.upd[f]))+'">↑ 原 '+esc(n(s.upd[f]))+'</span>';
          }
        }
        h+='<tr><td class="stgno">第 '+s.stage+' 关'+upb+'</td>'+
           '<td>'+n(s.rankPasses)+'</td><td>'+n(s.econPasses)+'</td>'+
           '<td'+raw(s.rankDamage)+'>'+wan(s.rankDamage)+'</td>'+
           '<td'+raw(s.econDamage)+'>'+wan(s.econDamage)+'</td></tr>';
      });
      h+='</tbody></table>';
      $('stgBody').innerHTML=h;
    })
    .catch(function(){ $('stgSub').textContent='加载失败，请稍后再试。'; });
}
function closeStages(){ $('stgOv').style.display='none'; }

/* ── 上游数据更新提醒（GitHub 变更检测） ── */
/* 下架提醒关掉时，横幅计数与明细都不含「已下架」组 */
function updCounts(ud){
  var c=(ud&&ud.counts)||{};
  var del=(PREFS.upd_del!==false)?(c.del||0):0;
  var o={n:c.new||0, e:c.edit||0, s:c.stage||0, z:c.zombie||0,
         p:c.param||0, del:del};
  o.total=o.n+o.e+o.s+o.z+o.p+o.del;
  return o;
}
/* 两条更新提醒（官方数据有更新 / 上游更新动态）只属于「服务器」页：
   以前它们挂在 .content 里、不在任何视图容器内，所以切到主题、地图库、设置时
   照样横在内容顶部，看着像关不掉的广告（v2.14 体验 P1⑤）。
   这里把「该不该显示」和「当前在哪一页」分开记，切页时重新判一次。 */
var UPD_WANT=false, UPL_WANT=false;
function bannerApply(){
  var ub=$('updB'), lb=$('updLn'), srv=(typeof CURVIEW==='undefined')||CURVIEW==='srv';
  if(ub) ub.style.display=(UPD_WANT && srv)?'':'none';
  /* 两条互斥：官方数据有更新更紧要，先让它占位 */
  if(lb) lb.style.display=(UPL_WANT && srv && !UPD_WANT)?'':'none';
}
function updBannerSync(ud){
  var b=$('updB'); if(!b||!ud) return;
  var c=updCounts(ud);
  /* 签名去重：这个函数每秒跟着 status 轮询跑一次，没变化不重绘 */
  var sig=ud.detected_at+'|'+c.total+'|'+(ud.seen?1:0)+'|'+(PREFS.upd_auto?1:0);
  if(b._sig===sig) return;
  b._sig=sig;
  ulLoad(true);            /* 上游状态变了 → 台账（更新动态）跟着刷新 */
  if(!c.total || ud.seen){ UPD_WANT=false; bannerApply(); updLnSync(); return; }
  if(PREFS.upd_auto) get('/api/ctl?do=diffseen');   /* 自动确认：本次仍提示一眼，之后不再打扰 */
  var chips='';
  if(c.n)   chips+='<span class="plus">➕ 新增地图 ×'+c.n+'</span>';
  if(c.e)   chips+='<span class="edit">✏️ 奖励调整 ×'+c.e+'</span>';
  if(c.s)   chips+='<span class="edit">🔀 关卡变化 ×'+c.s+'</span>';
  if(c.z)   chips+='<span class="edit">💀 尸变参数 ×'+c.z+'</span>';
  if(c.p)   chips+='<span class="edit">🔧 地图参数 ×'+c.p+'</span>';
  if(c.del) chips+='<span class="minus">➖ 已下架 ×'+c.del+'</span>';
  $('updBStat').innerHTML=chips;
  $('updBSub').textContent=(PREFS.upd_auto?'已自动应用新数据 · ':'')+
    '检测于 '+(ud.detected_at||'—')+' · 来自 GitHub 数据仓';
  UPD_WANT=true; bannerApply();
  updLnSync();             /* 横幅占位时压住台账条，避免两条叠着 */
}
function triggerUpdSync(subEl){
  if(subEl) subEl.textContent='正在同步官方数据…（约 10~30 秒，可在「设置」页看进度）';
  var sb=document.getElementById('btnSync');
  if(sb) sb.click();          /* 复用设置页同步：跑完新 diff 为空，横幅自动消失 */
}
function openDiff(){
  $('diffOv').style.display='';
  $('diffBody').innerHTML='<div style="padding:18px 4px;color:var(--muted);font-size:var(--fs-sm)">加载中…</div>';
  $('diffSub').textContent='—';
  get('/api/upddiff').then(renderDiff).catch(function(){
    $('diffBody').innerHTML='<div style="padding:18px 4px;color:var(--muted);font-size:var(--fs-sm)">加载失败，请稍后再试。</div>';
  });
}
function closeDiff(){ $('diffOv').style.display='none'; }
function renderDiff(d){
  var gs=(d&&d.groups)||{}, c=(d&&d.counts)||{};
  var showDel=PREFS.upd_del!==false;
  var total=((c.new||0)+(c.edit||0)+(c.stage||0)+(c.zombie||0)+(c.param||0)+(showDel?(c.del||0):0));
  $('diffSub').textContent=total?('共 '+total+' 项变化 · 检测于 '+((d&&d.detected_at)||'—'))
                                 :'当前没有待查看的变更。';
  if(!total){
    $('diffBody').innerHTML='<div style="padding:18px 4px;color:var(--muted);font-size:var(--fs-sm)">数据已是最新。</div>';
    return;
  }
  function nm(e){
    return '<div class="dNm">'+esc(e.map||'')+
      (e.mapcn?'<small>'+esc(e.mapcn)+'</small>':'')+'</div>';
  }
  /* 类别色从 CSS 变量现读（v2.14 美化⑪）：夜幕主题下变量被调亮，这里自动跟随 */
  var VS=getComputedStyle(document.documentElement);
  var BG={'b-new':VS.getPropertyValue('--c-new').trim()||'#4caf7d',
          'b-edit':VS.getPropertyValue('--c-edit').trim()||'#e8a33d',
          'b-stage':VS.getPropertyValue('--c-stage').trim()||'#4a9ad4',
          'b-zombie':VS.getPropertyValue('--c-zombie').trim()||'#8e6fb8',
          'b-param':VS.getPropertyValue('--c-param').trim()||'#4aa8a0',
          'b-del':VS.getPropertyValue('--c-del').trim()||'#c66a7c'};
  var h='';
  function grp(title, cls, rows, fn){
    if(!rows||!rows.length) return;
    h+='<div class="dGrp"><div class="dGt"><span class="tbadge '+cls+'">'+title+'</span>'+
       '<span class="n" style="background:'+BG[cls]+'">'+rows.length+'</span></div>';
    rows.forEach(fn);
    h+='</div>';
  }
  grp('➕ 新增地图','b-new',gs.new,function(e){
    /* diff_repo 现在给新图带 fields（关卡数 / 选图参数概要）；旧 diff 只有 stages */
    var fs=(e.fields||[]).map(function(fl){ return fldHTML(fl); }).join('');
    if(!fs) fs='<span class="dF"><span class="k">奖励关卡</span><span class="new">'+
               (e.stages||'?')+' 关</span></span>';
    h+='<div class="dRow">'+nm(e)+'<div class="dChg">'+fs+'</div></div>';
  });
  grp('✏️ 奖励调整','b-edit',gs.edit,function(e){
    h+='<div class="dRow">'+nm(e)+'<div class="dChg">'+
       (e.fields||[]).map(function(fl){ return fldHTML(fl); }).join('')+'</div></div>';
  });
  grp('🔀 关卡变化','b-stage',gs.stage,function(e){
    var note='';
    if((e.added||[]).length)   note+='<span class="dF"><span class="k">新增第 '+e.added.join('、')+' 关</span></span>';
    if((e.removed||[]).length) note+='<span class="dF"><span class="k">移除第 '+e.removed.join('、')+' 关</span></span>';
    h+='<div class="dRow">'+nm(e)+'<div class="dChg">'+
       '<span class="dF"><span class="k">总关卡</span><span class="old">'+e.old+
       '</span><span class="arr">→</span><span class="new">'+e.new+'</span></span>'+note+'</div></div>';
  });
  grp('💀 尸变参数','b-zombie',gs.zombie,function(e){
    h+='<div class="dRow">'+nm(e)+'<div class="dChg">'+
       (e.fields||[]).map(function(fl){ return fldHTML(fl); }).join('')+'</div></div>';
  });
  grp('🔧 地图参数','b-param',gs.param,function(e){
    h+='<div class="dRow">'+nm(e)+'<div class="dChg">'+
       (e.fields||[]).map(function(fl){ return fldHTML(fl); }).join('')+'</div></div>';
  });
  if(showDel) grp('➖ 已下架','b-del',gs.del,function(e){
    h+='<div class="dRow" style="opacity:.72">'+nm(e)+
       '<div class="dChg"><span class="dF">官方仓库已移除，本机数据保留</span></div></div>';
  });
  $('diffBody').innerHTML=h;
}

/* ── 上游更新动态（台账）：官方每次改动记一条，可回看「改了什么」 ──
   数据来自 data/upd_log.json（build_index 检测到上游改动时追加，见 history_append）。
   与「官方数据有更新」横幅的区别：横幅是**待你处理的未读变更**（同步后消失），
   台账是**历史记录**（永久留存），没待办时也能查「上周改了什么」。 */
var UL={data:null,loading:false,tries:0};
/* 启动竞态兜底：/api/updlog 首次可能在后台 load_state 跑完前返回空（服务端已
   加了就绪闸门，这里再补一层），拿到空结果就退避重试几次，别把「还没记录」
   永久缓存在界面上。 */
var UL_TRIES_MAX=6;
var UL_CLS={'新增地图':'b-new','已下架':'b-del','通关奖励':'b-edit','关卡数':'b-stage',
            '地图参数':'b-param','地图翻译':'b-trans','Boss 配置':'b-boss'};
var UL_IC={'新增地图':'➕','已下架':'➖','通关奖励':'✏️','关卡数':'🔀',
           '地图参数':'🔧','地图翻译':'🌐','Boss 配置':'👹'};
/* 类别排序（新增 → 下架 → 奖励 → 关卡 → 参数 → 翻译 → Boss），与行内分组一致 */
var UL_KIND_ORD={'新增地图':0,'已下架':1,'通关奖励':2,'关卡数':3,
                 '地图参数':4,'地图翻译':5,'Boss 配置':6};
function ulLoad(force){
  if(UL.loading) return;
  if(UL.data && !force && UL.tries>=UL_TRIES_MAX) return;
  UL.loading=true;
  get('/api/updlog').then(function(d){
    UL.loading=false; UL.data=(d&&d.ok!==false)?d:{ok:false,entries:[]};
    var es=UL.data.entries||[];
    if(es.length){ UL.tries=0; }
    else if(UL.tries<UL_TRIES_MAX){
      UL.tries++;
      setTimeout(function(){ ulLoad(true); }, Math.min(1500+UL.tries*700, 6000));
    }
    ulPaint();
  }).catch(function(){
    UL.loading=false; UL.data={ok:false,entries:[]};
    if(UL.tries<UL_TRIES_MAX){
      UL.tries++;
      setTimeout(function(){ ulLoad(true); }, 2500);
    }
    ulPaint();
  });
}
/* 收缩面板（v2.13）：每条记录 = <details>，头部（日期+类别徽章+来源）常驻一行，
   明细默认收起 —— 弹窗里几十条全展开根本翻不到底，这是用户实测反馈 */
function ulItem(e,open){
  return '<details class="ulItem"'+(open?' open':'')+'>'+
         '<summary class="ulHd"><b class="ulAt">'+esc(e.at||'—')+'</b>'+ulHead(e)+
         '</summary><div class="ulBd">'+ulBody(e)+'</div></details>';
}
function ulHead(e){
  var h='';
  var ks=Object.keys(e.kinds||{});
  ks.sort(function(a,b){ return (UL_CLS[a]?0:1)-(UL_CLS[b]?0:1); });
  ks.forEach(function(k){
    h+='<span class="tbadge '+(UL_CLS[k]||'b-param')+'">'+(UL_IC[k]||'🔧')+' '+
       esc(k)+' ×'+(e.kinds[k]||0)+'</span>';
  });
  if(e.misc) h+='<span class="ulVia">含选图数据改动</span>';
  /* 收起状态也要让人知道「点开能看到旧值 → 新值」——这是最容易找不到的功能 */
  var hasVal=false;
  (e.maps||[]).forEach(function(m){
    (m.fld||[]).forEach(function(fl){
      if(fl.old!==null&&fl.old!==undefined&&fl.old!=='') hasVal=true;
    });
  });
  if(hasVal) h+='<span class="ulVia">点开看 旧 → 新</span>';
  h+='<span class="spacer"></span><span class="ulVia">'+
     (e.via==='manual'?'手动同步时检测':'后台自动检测')+'</span>'+
     '<span class="ulArr">▶</span>';
  return h;
}
function ulBody(e){
  /* 文件级类别没有字段明细时的说法（翻译/Boss 只有文件哈希可比特） */
  var PH={'地图翻译':'翻译文本更新','Boss 配置':'Boss 配置文件更新'};
  var h='';
  (e.maps||[]).forEach(function(m){
    /* 译名跟在英文图名下面（服务端 updlog_payload 现查现填，旧记录也有） */
    var cn=m.c?'<small>'+esc(m.c)+'</small>':'';
    h+='<div class="dRow"><div class="dNm" style="cursor:pointer" title="在地图库里打开这张图"'+
       ' onclick="ulJump(\''+esc(m.f)+'\')">'+esc(m.f)+cn+'</div><div class="dChg">';
    if((m.fld||[]).length){
      /* 按类别分组渲染：先给类别徽章（颜色与弹窗顶部汇总一致），
         再列该类下的字段变化 —— 不再是一长串分不清归属的数值 */
      var byG={},order=[];
      m.fld.forEach(function(fl){
        var g=fl.g||'其它改动';
        if(!byG[g]){ byG[g]=[]; order.push(g); }
        byG[g].push(fl);
      });
      order.sort(function(a,b){
        return (UL_KIND_ORD[a]||90)-(UL_KIND_ORD[b]||90); });
      order.forEach(function(g){
        h+='<span class="dCat"><span class="tbadge '+(UL_CLS[g]||'b-param')+'">'+
           (UL_IC[g]||'🔧')+' '+esc(g)+'</span>';
        byG[g].forEach(function(fl){
          /* st=关卡号（通关/伤害奖励才有）；悬停可看原始字段 / ConVar 名 */
          h+=fldHTML(fl);
        });
        h+='</span>';
      });
      /* m.k 里还有类别但 fld 没覆盖（翻译 / Boss 走文件级 diff）→ 补一条，别悄悄丢掉 */
      (m.k||[]).forEach(function(k){
        if(byG[k] || k==='新增地图') return;
        h+='<span class="dCat"><span class="tbadge '+(UL_CLS[k]||'b-param')+'">'+
           (UL_IC[k]||'🔧')+' '+esc(k)+'</span><span class="dF">'+
           '<span class="new">'+esc(PH[k]||'配置文件更新')+'</span></span></span>';
      });
    } else {
      /* 没有任何字段明细（旧版台账只存类别，或整条都是文件级）：
         新图一句话带过；其余类别给具体说法，不再干巴巴的「有改动」 */
      var ks=m.k||[];
      if(ks.indexOf('新增地图')>=0){
        h+='<span class="dF"><span class="k">➕ 新增地图</span>'+
           '<span class="new">新上架（此记录未含字段明细）</span></span>';
      } else {
        ks.forEach(function(k){
          h+='<span class="dF"><span class="k">'+esc(k)+'</span><span class="new">'+
             esc(PH[k]||'配置文件更新')+'</span></span>';
        });
      }
    }
    h+='</div></div>';
  });
  var more=(e.n||0)-(e.maps||[]).length;
  if(more>0) h+='<div class="ulMore">另有 '+more+' 张图的同类改动（同批次），此处只列前 '+
                (e.maps||[]).length+' 张。</div>';
  return h;
}
function ulJump(f){
  f=String(f||'').replace(/[^A-Za-z0-9_\-]/g,'');
  if(!f) return;
  closeUpdLog();
  libGoto(f);            /* 复用「当前地图 → 去地图库」那套：切页 + 选中 + 闪烁 */
}
var UL_EMPTY='<div class="ulEmpty">'+emptyHTML('📖','还没有更新记录',
  '从本版起，官方仓库每次改动（新增 / 下架地图、通关奖励、关卡数、地图参数、翻译、Boss '+
  '配置）都会记在这里，可回看「改了什么」。<br>'+
  '⚠ 升级到本版<b>之前</b>的上游改动无法追溯 —— 当时本地没有可对照的旧数据。')+'</div>';
function ulPaint(){
  var d=UL.data||{}, es=d.entries||[];
  var sub=$('updLnSub');
  if(sub) sub.textContent = es.length
    ? ('共 '+es.length+' 次上游更新 · 最近 '+(es[0].at||'—'))
    : '还没有记录 —— 官方下次改动就会记在这里';
  var card=$('ulCard');
  if(card){
    if(!es.length){ card.innerHTML=UL_EMPTY; }
    else {
      var h='';
      es.slice(0,3).forEach(function(e,i){ h+=ulItem(e,i===0); });
      if(es.length>3) h+='<div class="ulMore">还有 '+(es.length-3)+' 次记录…</div>';
      h+='<div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">'+
         '<button class="cbtn" id="ulMoreBtn">📜 查看全部记录</button>'+
         '<span class="ulVia">首页顶部那条提醒只在新改动时出现；点「查看记录」或 ✕ 之后就不再打扰，'+
         '记录一直留在这里。</span></div>';
      card.innerHTML=h;
      var mb=$('ulMoreBtn'); if(mb) mb.onclick=openUpdLog;
    }
  }
  if($('updOv').style.display!=='none') ulModal();
  updLnSync();
}
/* 台账「未读」判定：最新一条的指纹。看过/点 ✕ 后把指纹存进 PREFS，
   之后只有官方**又**改动了（出现更新的记录）才会重新冒出来。 */
function ulSig(){
  var es=(UL.data&&UL.data.entries)||[];
  var e=es[0];
  return e ? [e.detected||'', e.at||'', e.ts||0, e.n||0].join('|') : '';
}
function updLnSync(){
  var b=$('updLn'); if(!b) return;
  var es=(UL.data&&UL.data.entries)||[];
  var sig=ulSig();
  if(!sig || PREFS.upd_seen===sig){ UPL_WANT=false; bannerApply(); return; }
  /* 与「官方数据有更新」横幅互斥（bannerApply 里统一判），且只在服务器页显示 */
  var s=$('updLnSub');
  if(s) s.textContent=es.length>1
    ? ('共 '+es.length+' 次上游更新 · 最近 '+(es[0].at||'—'))
    : ('官方改动：'+(es[0].at||'—'));
  UPL_WANT=true;
  bannerApply();
}
function ulAck(){
  var sig=ulSig();
  var b=$('updLn'); if(b) b.style.display='none';
  if(sig && PREFS.upd_seen!==sig) savePrefs('upd_seen', sig);
}
var UL_GFILT='';          /* 弹窗类别筛选：''=全部，否则为类型名（地图参数 / 通关奖励…） */
var UL_EXPAND=null;       /* 收缩栏三态：null=只展开最新一条 / true=全展开 / false=全收起 */
function ulModal(){
  var d=UL.data||{}, es=d.entries||[];
  /* 类别汇总（全部记录），点 chip 只看那一类 —— 修改前一长串数值分不清归属 */
  var kc={};
  es.forEach(function(e){
    var ks=e.kinds||{};
    Object.keys(ks).forEach(function(k){ kc[k]=(kc[k]||0)+ks[k]; });
  });
  var ks=Object.keys(kc).sort(function(a,b){
    return (UL_KIND_ORD[a]||90)-(UL_KIND_ORD[b]||90); });
  var h='<div class="ulFilt"><button class="ulF'+(UL_GFILT===''?' on':'')+
        '" data-g="">全部</button>';
  ks.forEach(function(k){
    h+='<button class="ulF'+(UL_GFILT===k?' on':'')+'" data-g="'+esc(k)+'">'+
       (UL_IC[k]||'🔧')+' '+esc(k)+' '+kc[k]+'</button>';
  });
  h+='<button class="ulF" id="ulExp">'+(UL_EXPAND===true?'⏫ 全部收起':'⏬ 全部展开')+
     '</button></div>';
  var nb=0, ne=0, first=true;
  if(!es.length){ h+=UL_EMPTY; }
  else {
    es.forEach(function(e){
      var ms=(e.maps||[]).filter(function(m){
        return !UL_GFILT || (m.k||[]).indexOf(UL_GFILT)>=0; });
      if(!ms.length) return;
      ne++;
      nb+=ms.length;
      var view={};
      for(var k in e) view[k]=e[k];
      view.maps=ms; view.n=ms.length;
      /* 默认只展开最新一条；点「全部展开/收起」后按 UL_EXPAND 全开/全收 */
      h+=ulItem(view, UL_EXPAND===null ? first : UL_EXPAND);
      first=false;
    });
    if(!ne){ h+='<div class="ulEmpty">'+emptyHTML('🗂','这一类暂无记录','换个分类看看，或等下次后台检测到上游改动。')+'</div>'; }
    else{
      h+='<div class="ulMore">显示 '+ne+' 次更新 · 涉及 '+nb+' 张地图'+
         (UL_GFILT?('（只看 '+UL_GFILT+'）'):'')+'。条目默认收起，点日期行展开明细'+
         '；记录来自本机每次检测到的上游差异（后台每 30 分钟一次，手动「立即同步」也会记一条）。</div>';
    }
  }
  $('updOvSub').textContent = es.length
    ? ('共 '+es.length+' 次上游更新 · 显示 '+ne+' 次涉及 '+nb+' 张地图'+
       (UL_GFILT?('（只看 '+UL_GFILT+'）'):''))
    : '还没有记录';
  $('updOvBody').innerHTML=h;
  document.querySelectorAll('#updOvBody .ulF:not(#ulExp)').forEach(function(b){
    b.onclick=function(){ UL_GFILT=b.getAttribute('data-g')||''; ulModal(); };
  });
  var xb=$('ulExp');
  if(xb) xb.onclick=function(){ UL_EXPAND=(UL_EXPAND!==true); ulModal(); };
}
function openUpdLog(){
  $('updOv').style.display='';
  $('updOvSub').textContent='加载中…';
  $('updOvBody').innerHTML='<div style="padding:18px 4px;color:var(--muted);font-size:var(--fs-sm)">加载中…</div>';
  get('/api/updlog').then(function(d){
    UL.data=(d&&d.ok!==false)?d:{ok:false,entries:[]}; ulPaint();
  }).catch(function(){
    $('updOvBody').innerHTML='<div style="padding:18px 4px;color:var(--muted);font-size:var(--fs-sm)">读取失败，稍后再试。</div>';
  });
}
function closeUpdLog(){ $('updOv').style.display='none'; }

/* ═══════════ 对局战绩 + CS2 GSI（游戏状态集成） ═══════════ */
var GSI=null, MT={rows:[],sum:null,timer:0};
function fmtDur(sec){
  sec=Math.max(0,~~(sec||0));
  var m=~~(sec/60), h=~~(m/60);
  return h ? (h+' 小时 '+(m%60)+' 分') : (m+' 分 '+(sec%60)+' 秒');
}
function fmtTs(ts){
  if(!ts) return '—';
  var d=new Date(ts*1000);
  return (d.getMonth()+1)+'-'+d.getDate()+' '+('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2);
}
function matchLoad(){
  var sw=$('swGsi');
  if(sw && !sw.__b){ sw.__b=1; sw.onclick=function(){
    var on=sw.className.indexOf('on')<0;
    sw.className='sw'+(on?' on':'');
    gsiDo(on?'gsi_on':'gsi_off');
  }; }
  var go=$('gsiGo');
  if(go && !go.__b){ go.__b=1; go.onclick=function(){ showView('ov'); ovTab('gsi'); }; }
  var bi=$('gsiInstall'), br=$('gsiRemove');
  if(bi && !bi.__b){ bi.__b=1; bi.onclick=function(){ gsiDo('gsi_install'); }; }
  if(br && !br.__b){ br.__b=1; br.onclick=function(){ gsiDo('gsi_remove'); }; }
  loadGsi(); loadMatches();
  if(!MT.timer) MT.timer=setInterval(function(){
    if(CURVIEW!=='ov' || OVTAB!=='gsi' || document.hidden) return;
    loadGsi();
    MT.k=(MT.k||0)+1;
    if(MT.k%3===0) loadMatches();     /* 战绩 15 秒刷一次（局结束后不用手动刷新） */
  },5000);
}
var OVTAB='look';
function ovTab(name){
  OVTAB=name||'look';
  document.querySelectorAll('.ovTab').forEach(function(b){
    b.className='ovTab'+(b.getAttribute('data-tab')===OVTAB?' on':'');
  });
  document.querySelectorAll('.ovPane').forEach(function(p){
    p.className='ovPane'+(p.getAttribute('data-tab')===OVTAB?' on':'');
  });
  if(OVTAB==='gsi') matchLoad();
}
function ovTabsInit(){
  document.querySelectorAll('.ovTab').forEach(function(b){
    if(b.__b) return;
    b.__b=1;
    b.onclick=function(){ ovTab(b.getAttribute('data-tab')); };
  });
}
function loadGsi(){ get('/api/gsi').then(function(d){ GSI=d||{}; paintGsi(); }).catch(function(){}); }
function gsiDo(act){
  get('/api/ctl?do='+act).then(function(d){ GSI=d||{}; paintGsi(); loadMatches(); }).catch(function(){});
}
function paintGsi(){
  var d=GSI||{}, el=$('gsiLine'), sub=$('gsiSub'), pth=$('gsiPath'), sw=$('swGsi');
  if(!el) return;
  if(sw) sw.className='sw'+(d.enabled?' on':'');
  var bits=[];
  if(!d.enabled){ bits.push('未开启（点右侧开关启用）'); }
  else if(!d.connected){
    /* 分情况说人话：最常见的是「配置写在游戏启动之后」——这次会话不会加载，必须重启 CS2 */
    var cs2=(d.cs2||{});
    if(d.need_restart) bits.push('已开启 · 配置写在游戏启动之后，需要重启 CS2 才生效');
    else if(cs2.running===true) bits.push('已开启 · 等待游戏推送（进服后 1~2 秒出现）');
    else if(cs2.running===false) bits.push('已开启 · 等 CS2 启动后自动生效');
    else bits.push('已开启 · 等待游戏推送');
    if(d.received) bits.push('已收到 '+d.received+' 条，当前不在对局');
    if(d.rejected) bits.push('拒收 '+d.rejected+' 条（token 不匹配）');
  } else {
    bits.push('已连接');
    if(d.map) bits.push(d.map);
    if(d.score && (d.score.ct!==null || d.score.t!==null))
      bits.push('比分 CT '+n(d.score.ct)+' : '+n(d.score.t)+' T');
    if(d.stage_guess) bits.push('第 '+d.stage_guess+' 关（按比分推断）');
    if(d.kills!==null && d.kills!==undefined) bits.push('本局 K '+d.kills);
    if(d.dmg_round!==null && d.dmg_round!==undefined) bits.push('本回合伤害 '+d.dmg_round);
  }
  el.textContent=bits.join(' · ');
  if(sub) sub.style.display = d.enabled ? 'none' : '';
  var sl=$('gsiSetLine');
  if(sl){
    sl.textContent = !d.enabled ? '未开启' :
      (d.connected ? ('已连接 · '+(d.map||'—')+
         (d.stage_guess?(' · 第 '+d.stage_guess+' 关（比分推断）'):''))
       : '已开启 · 等待游戏推送');
  }
  var cfg=d.cfg||{};
  if(pth){
    var tail=[];
    if(cfg.port) tail.push('端口 '+cfg.port);
    var _at=d.cfg_file_at||cfg.cfg_at;
    if(_at) tail.push('配置写于 '+_at);
    if(d.received) tail.push('已收 '+d.received+' 条');
    if(d.rejected) tail.push('拒收 '+d.rejected+' 条');
    if(cfg.cfg_dirs && cfg.cfg_dirs.length)
      pth.textContent='配置位置：'+cfg.cfg_dirs[0]+'\\gamestate_integration_cloudshop.cfg'+
        (tail.length?('  ·  '+tail.join(' · ')):'');
    else if(cfg.cfg_error)
      pth.textContent='⚠ '+cfg.cfg_error+'（可手动把配置放进 CS2 的 game\\csgo\\cfg 目录）';
    else
      pth.textContent='配置位置 —（启动软件时自动写入 CS2 目录）';
  }
}
function loadMatches(){
  get('/api/matches').then(function(d){
    MT.rows=(d && d.rows)||[]; MT.sum=(d && d.summary)||{}; paintMatches();
  }).catch(function(){});
}
function paintMatches(){
  var tb=$('mbody'); if(!tb) return;
  var rows=MT.rows||[];
  if(!rows.length){
    tb.innerHTML='<tr><td colspan="7" class="s">还没有记录：开启 GSI 后进服打一局，'+
      '换图或本局结束就会自动记一条（数据只存在本机）。</td></tr>';
    var z=$('mSum'); if(z) z.textContent='';
    return;
  }
  var h='';
  rows.forEach(function(r){
    var rw=r.reward||{}, est=r.est||{};
    var sc=(r.ct===null||r.ct===undefined)?'—':('CT '+r.ct+' : '+r.t+' T');
    var ex=[];
    if(est.rankDmgPts) ex.push('云点 +'+est.rankDmgPts);
    if(est.econDmgPts) ex.push('龙晶 +'+est.econDmgPts);
    var exTxt=ex.length?ex.join(' · '):((r.dmg&&r.reward)?'未达标':'—');
    if(rw.rankPasses!==undefined && rw.rankPasses!==null)
      exTxt+=' <span class="sub">（本关 '+n(rw.rankPasses)+' 云点 / '+n(rw.econPasses)+' 龙晶）</span>';
    h+='<tr><td>'+fmtTs(r.start)+'</td>'+
       '<td>'+esc(r.mapcn||r.map||'—')+(r.stage?(' <b>第 '+r.stage+' 关</b>'):'')+'</td>'+
       '<td>'+sc+'</td><td>'+fmtDur(r.dur)+'</td>'+
       '<td>'+n(r.kills)+' / '+n(r.deaths)+' / '+n(r.assists)+'</td>'+
       '<td>'+wan(r.dmg)+'</td><td>'+exTxt+'</td></tr>';
  });
  tb.innerHTML=h;
  var s=MT.sum||{}, el=$('mSum');
  if(el) el.textContent = s.count
    ? ('共 '+s.count+' 局 · 累计伤害 '+wan(s.total_dmg)+' · 覆盖 '+s.maps+' 张图')
    : '';
}
/* ── 使用说明弹窗（首次打开自动弹；设置页可再次打开） ── */
function openReadme(){ $('rmOv').style.display=''; }
function closeReadme(){ $('rmOv').style.display='none'; }
function readmeSeen(){ return PREFS.readme_seen===true; }
function markReadmeSeen(){
  if(!readmeSeen()) savePrefs('readme_seen', true);   /* 只记一次，之后不再自动弹 */
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot);
else boot();
"""

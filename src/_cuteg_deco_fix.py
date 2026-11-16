# -*- coding: utf-8 -*-
"""「漂浮贴纸挡内容」的三个解法样板（基于 可爱G-草莓手账）。

   背景：样板里那 8 个飘着的 emoji 是 position:fixed 的独立层，z-index 高于卡片，
   在服务器表/地图库这种信息密集页会压在行数据上。窗口又几乎满铺
   （左右只剩 ~10px 边距、卡片间隙 ~12px），所以「挪到空白处」本身空间极小。

   三个方案：
     A 沉底 —— 贴纸层挪成 body 第一个子节点、z-index 归 auto：
              后出现的「定位卡片子树」按绘制顺序盖住它，只在卡片缝/底纹里透出来，
              位置大小全保留（永远不会压住数据）。
     B 避让 —— 保留浮在上层，但用 JS 扫描所有卡片/表格的实际 rect，
              只在「四边都空 21px」的网格点上放贴纸，最多 6 个，放不下就不放；
              切页/改变窗口都会重排。
     C 水印 —— 同 B 的避让，但只留 3 个、15px、透明度 .22，当底纹用。

   用法：python _cuteg_deco_fix.py
"""
import base64, json, os, re, subprocess, sys, time, urllib.request

import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
SRC = os.path.join(D, '可爱样板-HTML', '可爱G-草莓手账.html')
OUTD = os.path.join(D, '可爱样板-HTML', '贴纸方案')
SHOT = os.path.join(D, '验证截图-界面巡检')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9466
W, H = 1330, 720
EMO = ['🍓', '🎀', '🧸', '💗', '🍰', '🖍️']

# ── 各方案的注入片段 ────────────────────────────────────────
FIX_COMMON = """
/* 贴纸飘动幅度收到 ±6px：贴着卡片缝放时，15px 的漂移会直接飘进卡片里 */
#mkDeco i{animation:mkFloatFix 7s ease-in-out infinite}
#mkDeco i:nth-child(2n){animation-duration:9s;animation-delay:-1.6s}
#mkDeco i:nth-child(3n){animation-duration:11s;animation-delay:-3.4s}
@keyframes mkFloatFix{0%,100%{transform:translateY(0) rotate(-6deg)}
  50%{transform:translateY(-6px) rotate(8deg)}}
"""

CSS_A = FIX_COMMON + """
/* 方案A 沉底：贴纸层留在原地，但 z-index 归 auto 且排在 body 最前，
   于是所有「定位卡片子树」按绘制顺序压住它 —— 结构性不挡内容。 */
#mkDeco{z-index:auto}
/* 视图标题/提示条本来是 static，会被贴纸盖住 → 一并提到定位层 */
.view>h2,.view>p,.preBar2,.setBanner,.heroBanner,.libBanner{position:relative}
"""

LAYOUT_JS = """
<script id="mkDecoFixJs">
(function(){
  var EMO=__EMO__;
  var MAX=__MAX__, FS=__FS__, R=__FS__*0.55+7;
  /* 占用区扫描：不能只列几个类名 —— 服务器表那一大块根本不是 .card
     （第一版就是因此漏判，贴纸直接落在表格行上）。
     这里把「可见视图里的每个元素」都过一遍：有背景色/有边框/承载文字/是图片，
     任一命中就算占用；再把「被更大矩形包住的」删掉（父块已覆盖，省时间也够用）。 */
  function occ(){
    var out=[],i,j,el,r,cs,all=document.querySelectorAll('.view.on *');
    for(i=0;i<all.length;i++){
      el=all[i];
      if(el.closest('#mkDeco')||el.id==='mkPreNote') continue;
      r=el.getBoundingClientRect();
      if(r.width<8||r.height<8) continue;
      cs=getComputedStyle(el);
      if(cs.display==='none'||cs.visibility==='hidden'||cs.opacity==='0') continue;
      var bg=cs.backgroundColor;
      var paint=(bg&&bg!=='rgba(0, 0, 0, 0)'&&bg!=='transparent')
             || (parseFloat(cs.borderTopWidth)+parseFloat(cs.borderLeftWidth)>0)
             || el.tagName==='IMG'
             || (el.children.length===0&&(el.textContent||'').trim().length>0);
      if(paint) out.push([r.left,r.top,r.right,r.bottom]);
    }
    var ex=document.querySelectorAll('.side,.heroBanner,.libBanner,.setBanner,.preBar2,#mkBadge');
    for(i=0;i<ex.length;i++){r=ex[i].getBoundingClientRect();
      if(r.width>4&&r.height>4) out.push([r.left,r.top,r.right,r.bottom]);}
    var keep=[];
    for(i=0;i<out.length;i++){
      var a=out[i],inside=false;
      for(j=0;j<out.length;j++){
        if(j===i) continue;
        var b=out[j];
        if(a[0]>=b[0]-1&&a[1]>=b[1]-1&&a[2]<=b[2]+1&&a[3]<=b[3]+1
           && (j<i||a[0]!==b[0]||a[1]!==b[1]||a[2]!==b[2]||a[3]!==b[3])){inside=true;break;}
      }
      if(!inside) keep.push(a);
    }
    return keep;
  }
  function layout(){
    var d=document.getElementById('mkDeco'); if(!d) return;
    var i,is=d.querySelectorAll('i');
    var W=window.innerWidth,Hh=window.innerHeight,M=6;
    var box=occ(),cand=[];
    /* 顶部 52px 是标题栏 + 页头，别在那里摆贴纸 */
    for(var y=Math.max(M+R,52);y<Hh-M-R;y+=Math.round(R*2.2))
      for(var x=M+R;x<W-M-R;x+=Math.round(R*2.2)){
        var ok=true;
        for(var j=0;j<box.length;j++){var o=box[j];
          if(x+R>o[0]&&x-R<o[2]&&y+R>o[1]&&y-R<o[3]){ok=false;break;}}
        if(ok) cand.push([x,y]);
      }
    /* 候选点按「伪随机序」排一遍再挑：按 y 从上往下挑会把贴纸全堆在第一条缝里。
       挑的时候要求彼此拉开距离，不够就逐步放宽（240 → 144 → 86 → 52）。 */
    cand.sort(function(a,b){return ((a[0]*31+a[1]*17)%101)-((b[0]*31+b[1]*17)%101);});
    var pick=[],i2,j2;
    /* 变量名别叫 d —— 上面 d 是 #mkDeco 元素，重名会把它覆盖成数字，
       后面 d.setAttribute 直接报 "not a function"（实测踩过）。 */
    for(var dd=240;dd>=48&&pick.length<MAX;dd=Math.round(dd*0.6)){
      for(i2=0;i2<cand.length&&pick.length<MAX;i2++){
        var c=cand[i2],far=true;
        for(j2=0;j2<pick.length;j2++){
          var dx=c[0]-pick[j2][0],dy=c[1]-pick[j2][1];
          if(dx*dx+dy*dy<dd*dd){far=false;break;}
        }
        if(far) pick.push(c);
      }
    }
    var N=pick.length;
    for(i=0;i<is.length;i++){
      if(i<pick.length){
        is[i].style.display='';is[i].style.fontSize=FS+'px';
        is[i].style.left=pick[i][0]+'px';is[i].style.top=pick[i][1]+'px';
      } else is[i].style.display='none';
    }
    d.setAttribute('data-slots',pick.length+'/'+is.length+' 候选'+cand.length+' 占用'+box.length);
  }
  window.__mkDecoLayout=layout;
  function later(){setTimeout(layout,80);setTimeout(layout,500);setTimeout(layout,1400);}
  if(document.readyState==='complete') later(); else addEventListener('load',later);
  addEventListener('resize',function(){setTimeout(layout,150);});
  /* 切页按钮原来带 onclick，这里包一层，切完重排（新视图的卡片这时才有 rect） */
  var bs=document.querySelectorAll('.mv'),k;
  for(k=0;k<bs.length;k++){var old=bs[k].onclick;
    bs[k].onclick=(function(o){return function(){if(o)o.call(this);setTimeout(layout,300);};})(old);}
})();
</script>
"""

# 方案 D：只在留白多的页面显示（服务器表 / 地图库 这两张信息密集页自动收起）
HIDE_JS = """
<script id="mkDecoHideJs">
(function(){
  /* 信息密集页不摆装饰：服务器表 / 地图库 自动隐藏漂浮层，其余页面保持原样 */
  var HIDE={'view-srv':1,'view-lib':1};
  function sync(){
    var on=document.querySelector('.view.on'),d=document.getElementById('mkDeco');
    if(!on||!d) return;
    d.style.display=HIDE[on.id]?'none':'';
    d.setAttribute('data-slots',HIDE[on.id]?'本页已收起':'显示');
  }
  var vs=document.querySelectorAll('.view'),i;
  var mo=new MutationObserver(function(){setTimeout(sync,40);});
  for(i=0;i<vs.length;i++) mo.observe(vs[i],{attributes:true,attributeFilter:['class']});
  sync();
  addEventListener('load',function(){setTimeout(sync,300);});
})();
</script>
"""


def deco_markup(emojis, sizes=None):
    out = ['<div id="mkDeco">']
    # 位置由 JS 排（A 方案除外，A 用文件里原有的百分比位置）
    for i, e in enumerate(emojis):
        fs = (sizes or [20])[i % len(sizes or [20])]
        out.append('<i style="font-size:%dpx">%s</i>' % (fs, e))
    out.append('</div>')
    return ''.join(out)


def build_one(src, name, mode):
    html = src
    old = re.search(r'<div id="mkDeco">.*?</div>\s*', html, re.S).group(0)
    if mode == 'A':
        # 挪到 body 最前，位置/大小保持原样
        html = html.replace(old, '')
        m = re.search(r'<body[^>]*>', html)
        html = html[:m.end()] + '\n' + old.strip() + '\n' + html[m.end():]
        fix = '<style id="mkDecoFix">%s</style>\n' % CSS_A
    elif mode == 'D':
        # 位置/大小保持原样，只按当前页决定显隐
        fix = '<style id="mkDecoFix">%s</style>\n%s' % (FIX_COMMON, HIDE_JS)
    elif mode == 'E':
        # D + B 合体：信息页收起，其余页自动挑真空位 —— 推荐方案
        n = 6
        sizes = [20, 22, 18]
        html = html.replace(old, deco_markup(EMO[:n], sizes))
        js = (LAYOUT_JS.replace('__EMO__', json.dumps(EMO[:n], ensure_ascii=False))
              .replace('__MAX__', str(n)).replace('__FS__', str(sizes[0])))
        fix = '<style id="mkDecoFix">%s</style>\n%s\n%s' % (FIX_COMMON, js, HIDE_JS)
    else:
        n = 6 if mode == 'B' else 3
        sizes = [20, 22, 18] if mode == 'B' else [15]
        html = html.replace(old, deco_markup(EMO[:n], sizes))
        js = (LAYOUT_JS.replace('__EMO__', json.dumps(EMO[:n], ensure_ascii=False))
              .replace('__MAX__', str(n)).replace('__FS__', str(sizes[0])))
        op = '0.5' if mode == 'B' else '0.22'
        extra = ('#mkDeco i{opacity:%s}' % op) if mode == 'C' else ''
        fix = '<style id="mkDecoFix">%s%s</style>\n%s' % (FIX_COMMON, extra, js)
    html = html.replace('</body>', fix + '</body>')
    p = os.path.join(OUTD, name)
    open(p, 'w', encoding='utf-8').write(html)
    return p


CASES = [
    ('A', 'G贴纸A-沉到卡片下面.html', 'A 沉底',
     [('01-服务器表', 'srv'), ('02-地图库', 'lib')]),
    ('B', 'G贴纸B-自动避让.html', 'B 自动避让',
     [('01-服务器表', 'srv'), ('02-地图库', 'lib')]),
    ('C', 'G贴纸C-极度淡化.html', 'C 淡化水印',
     [('01-服务器表', 'srv'), ('02-地图库', 'lib')]),
    ('D', 'G贴纸D-分页显示.html', 'D 分页显示',
     [('01-服务器表', 'srv'), ('02-地图库', 'lib'), ('03-主题页', 'theme'), ('04-设置页', 'set')]),
    ('E', 'G贴纸E-避让加分页.html', 'E 避让+分页',
     [('01-服务器表', 'srv'), ('02-地图库', 'lib'), ('03-主题页', 'theme'), ('04-设置页', 'set')]),
]

if __name__ == '__main__':
    os.makedirs(OUTD, exist_ok=True)
    src = open(SRC, encoding='utf-8').read()
    made = []
    print('生成四个方案：')
    for key, fn, title, views in CASES:
        p = build_one(src, fn, key)
        print('  %-30s %6d KB' % (fn, os.path.getsize(p) // 1024))
        made.append((key, p, title, views))

    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    proc = subprocess.Popen(
        [EDGE, '--headless=new', '--remote-debugging-port=%d' % PORT, '--remote-allow-origins=*',
         '--user-data-dir=' + os.path.join(D, '_prof_decofix'), '--no-first-run',
         '--window-size=%d,%d' % (W, H), 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shots = []
    try:
        ws_url = None
        for _ in range(40):
            try:
                tabs = json.load(op.open('http://127.0.0.1:%d/json' % PORT, timeout=2))
                pg = [t for t in tabs if t.get('type') == 'page']
                if pg:
                    ws_url = pg[0]['webSocketDebuggerUrl']
                    break
            except Exception:
                time.sleep(0.5)
        ws = websocket.create_connection(ws_url, timeout=180, http_proxy_host=None)
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
        send('Page.addScriptToEvaluateOnNewDocument', {'source':
            "window.__e=[];addEventListener('error',function(x){__e.push(String(x.message||x))});"})
        send('Emulation.setDeviceMetricsOverride',
             {'width': W, 'height': H, 'deviceScaleFactor': 1, 'mobile': False})

        print('\n截图：')
        for key, p, title, views in made:
            send('Page.navigate', {'url': 'file:///' + p.replace('\\', '/')})
            for _ in range(120):
                if ev("document.readyState==='complete' && !!document.getElementById('mkCute')"):
                    break
                time.sleep(0.25)
            time.sleep(2.6)
            for tag, view in views:
                ev("(function(){var b=document.querySelector('.mv[data-view=\"%s\"]'); if(b) b.click();})()" % view)
                time.sleep(1.6)
                info = ev("(function(){var d=document.getElementById('mkDeco');"
                          "var v=0,is=d.querySelectorAll('i');"
                          "for(var i=0;i<is.length;i++) if(is[i].style.display!=='none') v++;"
                          "return {view:(document.querySelector('.view.on')||{}).id||'',"
                          "shown:v,note:d.getAttribute('data-slots')||'-',"
                          "err:(window.__e||[]).join('|')};})()")
                d = send('Page.captureScreenshot', {'format': 'png'})
                out = os.path.join(SHOT, 'G贴纸%s-%s.png' % (key, tag))
                open(out, 'wb').write(base64.b64decode(d['data']))
                shots.append((out, '%s · %s' % (title, tag.split('-', 1)[1])))
                print('  %-34s %5d KB  %s' % (os.path.basename(out),
                                              os.path.getsize(out) // 1024, info))
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

    try:
        from PIL import Image, ImageDraw, ImageFont
        reg = r'C:\Windows\Fonts\msyh.ttc'
        bold = r'C:\Windows\Fonts\msyhbd.ttc'
        if not os.path.exists(bold):
            bold = reg
        f = ImageFont.truetype(bold, 22)
        COLS, SC, GAP, BAR = 4, 0.46, 12, 36
        tw, th = int(W * SC), int(H * SC)
        cw = COLS * tw + (COLS + 1) * GAP
        ch = 2 * (th + BAR) + 3 * GAP
        canvas = Image.new('RGB', (cw, ch), '#f6f2f4')
        dr = ImageDraw.Draw(canvas)
        # 列 = 方案，行 = 页面
        # 对照图只放四个候选：B / C / D / E × (服务器表, 地图库)
        # （A 藏得几乎看不见，单独留图说明机制，不进对照图）
        # 按文件名挑，别按序号 —— D/E 各多两张其它页截图，序号会错位
        sel = []
        for key in ('B', 'C', 'D', 'E'):
            for tag in ('01-服务器表', '02-地图库'):
                for s in shots:
                    if os.path.basename(s[0]).startswith('G贴纸%s-' % key) and tag in s[0]:
                        sel.append(s)
                        break
        for i, (p, desc) in enumerate(sel):
            col, row = divmod(i, 2)      # 截图顺序：A srv, A lib, B srv, B lib, C srv, C lib
            r, c = row, col
            x = GAP + c * (tw + GAP)
            y = GAP + r * (th + BAR + GAP)
            im = Image.open(p).convert('RGB').resize((tw, th), Image.LANCZOS)
            canvas.paste(im, (x, y + BAR))
            dr.text((x + 4, y + 6), desc, font=f, fill='#5a3b3b')
            dr.rectangle([x - 1, y + BAR - 1, x + tw, y + BAR + th], outline='#e3d3d8')
        out = os.path.join(SHOT, 'G贴纸方案-00-三方案对照.png')
        canvas.save(out, quality=92)
        print('\n对照图：%s  %d KB  %dx%d' % (os.path.basename(out),
                                              os.path.getsize(out) // 1024,
                                              canvas.size[0], canvas.size[1]))
    except Exception as e:                                        # noqa: BLE001
        print('拼图失败：%s' % e)

# -*- coding: utf-8 -*-
"""第三批样板：可爱风「主题自适应版」——同一套造型，5 套主题各用自己的配色。

回答「你改了主题颜色，那其他主题是什么样的」：
  前两批样板用 `html[data-theme]{...}` 直接覆盖了调色板（= 换主题），
  若照那样实装，5 套主题会被压成同一种颜色。
  这批反过来 —— **颜色全部走主题变量**（--accent/--softline/--panel/--thead…），
  只改造型与点缀（云朵凸顶 / 胶囊控件 / 柔和云影 / 漂浮贴纸），
  于是 奶油草莓 / 薄荷团子 / 樱花苏打 / 蜜桃气泡 / 夜幕护眼 各自保持原配色。

产物：
  · 可爱样板-主题自适应-可切换.html     一份，底部有主题切换条（也可点主题页的卡片）
  · 可爱样板-主题<code><名称>.html      5 份，各自锁定一个主题，便于并排对比
用法：python _cute_mock_gen3.py [--shot]
"""
import base64, json, os, re, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
FR = os.path.join(D, 'fys-reward')
SNAP = os.path.join(D, '_snap_app.html')
OUTD = os.path.join(D, '可爱样板-HTML')
SHOT = os.path.join(D, '验证截图-界面巡检')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
os.makedirs(OUTD, exist_ok=True)
sys.path.insert(0, FR)


# ─────────────────────── 主题数据（唯一真源：ui_page.py） ───────────────────────
def load_themes():
    import ui_page
    src = open(os.path.join(FR, 'ui_page.py'), encoding='utf-8').read()
    out = []
    for t in ui_page.THEMES:
        code = t[0]
        m = re.search(r'html\[data-theme="%s"\]\{(.*?)\}' % code, src, re.S)
        v = dict(re.findall(r'(--[\w-]+):([^;]+);', m.group(1)))
        out.append(dict(code=code, name=t[1], emoji=t[2], accent=t[3], soft=t[4],
                        ink=t[6], side=t[7], line=t[9],
                        softline=v.get('--softline', t[9]), dark=(code == 'N')))
    return out


def rgb(h):
    h = h.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mk_vars(t):
    """每套主题一份「造型色」——只派生自该主题自己的色值。"""
    r, g, b = rgb(t['accent'])
    if t['dark']:
        return dict(mkAsh='rgba(0,0,0,.55)', mkAshL='rgba(0,0,0,.35)',
                    mkHi='rgba(255,255,255,.05)', mkCloud='#2b2836',
                    mkClLine='rgba(%d,%d,%d,.42)' % (r, g, b), mkA=t['accent'])
    return dict(mkAsh='rgba(%d,%d,%d,.26)' % (r, g, b), mkAshL='rgba(%d,%d,%d,.16)' % (r, g, b),
                mkHi='rgba(255,255,255,.92)', mkCloud='#ffffff',
                mkClLine=t['softline'], mkA=t['accent'])


def vars_block(t):
    v = mk_vars(t)
    keys = ['mkAsh', 'mkAshL', 'mkHi', 'mkCloud', 'mkClLine', 'mkA']
    return 'html[data-theme="%s"]{%s}' % (t['code'],
        ''.join('--%s:%s;' % (k, v[k]) for k in keys))


# ─────────────────────── 背景底纹（明/暗两版，按主题各自生效） ───────────────────────
def pat_uris():
    """亮色图案 + 吉祥物水印从快照里取；暗色图案从 bg_assets 取（快照里没有）。"""
    snap = open(SNAP, encoding='utf-8').read()
    css = re.search(r'<style id="bgcss">(.*?)</style>', snap, re.S).group(1)
    urls = re.findall(r'url\("(data:image/[^"]+)"\)', css)
    import bg_assets
    pat = urls[0]
    mascot = urls[2] if len(urls) > 2 else urls[-1]
    return pat, mascot, bg_assets.BG_DATA.get('pat_dark', pat)


def bg_css(pat, mascot, patdark):
    """亮色（云朵小铺方案）与暗色各出一份，用 data-theme 分流。
       背景 feature 的底纹色纱是运行时 JS 写进 #bgcss 的，静态快照只留了亮色那份，
       直接切到夜幕护眼会「浅色纱 + 白卡片」压掉暗色主题 —— 所以这里重建两份。"""
    L = ('background-repeat:no-repeat,no-repeat,repeat,repeat!important;'
         'background-size:auto,auto,400px 368px!important;'
         'background-attachment:scroll,scroll,local,fixed!important;')
    Ls = ('background-repeat:repeat,repeat!important;'
          'background-size:auto,360px 332px!important;')

    def main(v1, v2, g1, g2, img):
        return ('background-image:radial-gradient(720px 320px at 2% -10%,rgba(214,240,255,'
                + g1 + ') 0%,rgba(214,240,255,0) 62%),radial-gradient(780px 340px at 100% -8%,'
                'rgba(255,226,240,' + g2 + ') 0%,rgba(255,226,240,0) 60%),linear-gradient('
                + v1 + ',' + v2 + '),url("' + img + '")!important;') + L

    def side(s1, s2, img):
        return ('background-image:linear-gradient(180deg,' + s1 + ' 0%,' + s2
                + ' 100%),url("' + img + '")!important;') + Ls

    card = ('.card,.rmcard,.syncbox,.fxcard,.themePal,.bgcard{background-image:'
            'linear-gradient(rgba(255,255,255,.80),rgba(255,255,255,.86)),url("%s")!important;'
            'background-repeat:no-repeat,no-repeat!important;background-size:cover,290px auto!important;'
            'background-position:center,right -46px top -54px!important;' % mascot)

    light = ('html:not([data-theme="N"]) body,html:not([data-theme="N"]) .main{'
             + main('rgba(255,253,254,0.56)', 'rgba(255,250,253,0.64)', '0.70', '0.70', pat) + '}'
             + 'html:not([data-theme="N"]) .side{'
             + side('rgba(255,249,252,0.74)', 'rgba(255,246,251,0.8)', pat) + '}'
             + 'html:not([data-theme="N"]) ' + card + '}')
    dark = ('html[data-theme="N"] body,html[data-theme="N"] .main{'
            + main('rgba(22,21,26,.72)', 'rgba(22,21,26,.80)', '0.22', '0.20', patdark) + '}'
            + 'html[data-theme="N"] .side{'
            + side('rgba(20,19,26,.86)', 'rgba(20,19,26,.90)', patdark) + '}')
    return light + dark


# ─────────────────────── 造型 CSS（全部用主题变量，无一处写死颜色） ───────────────────────
STYLE = """
/* ═══ 造型层：只改形状/层次/点缀，颜色一律取主题变量 ═══ */
.card{position:relative}
.side{box-shadow:6px 0 0 var(--mkAshL)!important}
.stop{border-bottom:3px dashed var(--softline)!important}
.sname{font-weight:900!important;color:var(--accent)}
/* 云朵泡芙：卡片软胖大圆角 + 柔和云影 + 顶上一朵凸出来的云 */
.card,.libList,.libDetail,.themePal,.syncbox,.fxcard,.clgvw,.bgcard{
  position:relative;
  border:3px solid var(--softline)!important;
  border-radius:34px 34px 26px 26px!important;
  box-shadow:0 12px 26px var(--mkAsh),inset 0 2px 0 var(--mkHi)!important}
.mkCl{position:absolute;left:26px;top:-21px;display:flex;align-items:flex-end;
  pointer-events:none;z-index:3}
.mkCl i{display:block;background:var(--mkCloud);
  border:3px solid var(--mkClLine);border-radius:50%;box-shadow:inset 0 -3px 0 var(--mkAsh)}
.mkCl i:nth-child(1){width:29px;height:29px;margin-right:-10px;margin-bottom:1px}
.mkCl i:nth-child(2){width:44px;height:44px;z-index:2}
.mkCl i:nth-child(3){width:25px;height:25px;margin-left:-9px;margin-bottom:1px}
.card h2{color:var(--accent)}
/* 控件：胶囊 + 硬投影 + 按下位移 */
.nav{border:3px solid transparent!important;border-radius:999px!important;
  transition:transform .16s cubic-bezier(.34,1.7,.5,1),background .16s!important}
.nav:hover{transform:translateX(4px)}
.nav.on{background:var(--panel)!important;border-color:var(--softline)!important;
  box-shadow:3px 4px 0 var(--mkAsh)!important;transform:translateX(4px)}
.btn{border:3px solid var(--softline)!important;border-radius:999px!important;
  box-shadow:3px 4px 0 var(--mkAsh)!important;font-weight:800!important;
  transition:transform .12s,box-shadow .12s!important}
.btn:hover{transform:translate(-1px,-1px);box-shadow:5px 6px 0 var(--mkAsh)!important}
.pill,.srvtab{border:3px solid var(--softline)!important;border-radius:999px!important;
  box-shadow:3px 4px 0 var(--mkAsh)!important;font-weight:800!important;
  background:var(--panel)!important}
.tbl th{background:var(--thead)!important;font-weight:900!important}
.tbl td,.tbl th{border-color:var(--softline)!important}
input[type=text],input[type=search],select{
  border:3px solid var(--softline)!important;border-radius:999px!important}
/* 样板角标 + 漂浮贴纸 */
#mkBadge{position:fixed;right:14px;bottom:70px;z-index:99;font:800 12px/1.3 var(--disp);
  color:#fff;background:var(--accent);padding:8px 14px;border-radius:999px;white-space:nowrap;
  box-shadow:0 6px 18px var(--mkAsh);letter-spacing:.4px;pointer-events:none}
#mkBadge b{font-size:13px}
#mkDeco{position:fixed;inset:0;pointer-events:none;z-index:5;overflow:hidden}
#mkDeco i{position:absolute;font-style:normal;opacity:.42;
  filter:drop-shadow(0 6px 10px rgba(0,0,0,.10));animation:mkFloat 7s ease-in-out infinite}
#mkDeco i:nth-child(2n){animation-duration:9s;animation-delay:-1.6s}
#mkDeco i:nth-child(3n){animation-duration:11s;animation-delay:-3.4s}
@keyframes mkFloat{0%,100%{transform:translateY(0) rotate(-6deg)}
  50%{transform:translateY(-15px) rotate(8deg)}}
/* 主题切换条（样板专用，软件里没有） */
#mkBar{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:98;
  display:flex;align-items:center;flex-wrap:nowrap;gap:6px;padding:7px 11px;border-radius:999px;
  background:var(--panel);border:3px solid var(--softline);
  box-shadow:0 10px 24px var(--mkAsh);font:700 12px var(--disp);color:var(--ink)}
#mkBar .lb{color:var(--muted);margin-right:1px;white-space:nowrap}
#mkBar button{border:2.5px solid var(--softline);background:var(--side);
  color:var(--ink);border-radius:999px;padding:5px 10px;font:700 12px var(--disp);
  cursor:pointer;white-space:nowrap}
#mkBar button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
#mkBar .tip{color:var(--muted);margin-left:3px;font-weight:600;white-space:nowrap}
@media (max-width:1080px){#mkBar .tip{display:none}}
/* 预览页占位 */
#mkPreNote{display:none;position:absolute;inset:0;align-items:center;justify-content:center;
  flex-direction:column;gap:10px;color:var(--muted);font:700 15px var(--disp);text-align:center}
#view-pre.on #mkPreNote{display:flex}
"""

SPOTS = [(20, 20), (93, 13), (23, 77), (95, 64), (53, 6), (34, 92), (77, 85), (9, 35)]
DECO = ['\u2601\ufe0f', '\U0001fae7', '\U0001f4ad', '\U0001f31f', '\U0001f411', '\u2728']


def deco_html():
    out = ['<div id="mkDeco">']
    for i, sp in enumerate(SPOTS):
        out.append('<i style="left:%d%%;top:%d%%;font-size:%dpx">%s</i>'
                   % (sp[0], sp[1], 19 + (i % 3) * 7, DECO[i % len(DECO)]))
    out.append('</div>')
    return ''.join(out)


def bar_html(themes):
    b = ['<div id="mkBar"><span class="lb">\u4e3b\u9898</span>']
    for t in themes:
        b.append('<button data-th="%s">%s %s</button>' % (t['code'], t['emoji'], t['name']))
    b.append('<span class="tip">\u9020\u578b\u56fa\u5b9a\uff0c\u914d\u8272\u8ddf\u968f\u4e3b\u9898</span></div>')
    return ''.join(b)


SCRIPT = """
<script>
(function(){
  var V=['srv','ov','theme','lib','pre','set'];
  var TH={'E':'\\u5976\\u6cb9\\u8349\\u8393','F':'\\u8584\\u8377\\u56e2\\u5b50',
          'G':'\\u6a31\\u82b1\\u82cf\\u6253','H':'\\u871c\\u6843\\u6c14\\u6ce1',
          'N':'\\u591c\\u5e55\\u62a4\\u773c'};
  /* 装饰挂载要等布局完成：解析阶段卡片还没有尺寸（按尺寸筛选会全跳过）；
     切页后再补挂一次，让刚显示的卡片也长上云朵。 */
  function MKDEC(){
    try{
      var cs=document.querySelectorAll('.card,.libList,.libDetail,.themePal');
      for(var i=0;i<cs.length;i++){
        if(cs[i].querySelector(':scope > .mkCl')) continue;
        var c=document.createElement('span'); c.className='mkCl';
        c.innerHTML='<i></i><i></i><i></i>';
        cs[i].appendChild(c);
      }
    }catch(e){}
  }
  function setTheme(id){
    document.documentElement.setAttribute('data-theme', id);
    var cs=document.querySelectorAll('#themes .tcard');
    for(var i=0;i<cs.length;i++){
      var on=cs[i].getAttribute('data-t')===id;
      cs[i].className='tcard'+(on?' on':'');
      var s=cs[i].querySelector('.tstate'); if(s) s.textContent=on?'\\u2713 \\u4f7f\\u7528\\u4e2d':'';
    }
    var bs=document.querySelectorAll('#mkBar button');
    for(var j=0;j<bs.length;j++)
      bs[j].className=(bs[j].getAttribute('data-th')===id?'on':'');
    var nb=document.querySelector('#mkBadge .thn');
    if(nb) nb.textContent=TH[id]||id;
    setTimeout(MKDEC,40);
  }
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
    setTimeout(MKDEC,60);
  }
  var navs=document.querySelectorAll('.mv');
  for(var k=0;k<navs.length;k++){
    navs[k].style.cursor='pointer';
    navs[k].onclick=function(){ go(this.getAttribute('data-view')); };
  }
  var tcs=document.querySelectorAll('#themes .tcard');
  for(var m=0;m<tcs.length;m++){
    tcs[m].onclick=function(){ setTheme(this.getAttribute('data-t')); };
  }
  var bs2=document.querySelectorAll('#mkBar button');
  for(var n=0;n<bs2.length;n++){
    bs2[n].onclick=function(){ setTheme(this.getAttribute('data-th')); };
  }
  var fp=document.getElementById('view-pre');
  if(fp && !document.getElementById('mkPreNote')){
    var pn=document.createElement('div'); pn.id='mkPreNote';
    pn.innerHTML='<div style="font-size:46px">\\uD83D\\uDDFA\\uFE0F</div>'+
      '<div>\\u5730\\u56fe\\u5b9e\\u4f53\\u9884\\u89c8\\uff083D\\uff09</div>'+
      '<div style="font-weight:600;font-size:12.5px;opacity:.8">'+
      '\\u6837\\u677f\\u662f\\u9759\\u6001\\u9875\\u9762\\uff0c\\u4e0d\\u542b 3D \\u5b9e\\u65f6\\u6570\\u636e</div>';
    fp.style.position='relative'; fp.appendChild(pn);
  }
  setTheme(document.documentElement.getAttribute('data-theme')||'E');
  go('srv');
  if(document.readyState==='complete') setTimeout(MKDEC,60);
  else window.addEventListener('load', function(){ setTimeout(MKDEC,60); });
})();
</script>
"""


def build():
    snap = open(SNAP, encoding='utf-8').read()
    themes = load_themes()
    pat, mascot, patdark = pat_uris()
    bg = bg_css(pat, mascot, patdark)

    head_css = ''.join(vars_block(t) for t in themes) + STYLE
    add = ('<style id="mkCute">\n' + head_css + '\n</style>\n'
           '<div id="mkBadge">\u2601\ufe0f \u4e91\u6735\u6ce1\u8299\u6837\u677f \u00b7 \u4e3b\u9898\uff1a'
           '<b class="thn">\u5976\u6cb9\u8349\u8393</b></div>\n'
           + deco_html() + '\n' + bar_html(themes) + '\n' + SCRIPT)

    # ① 用「明/暗两版」重建 #bgcss（原静态快照只留了亮色那份）
    snap2 = re.sub(r'(<style id="bgcss">).*?(</style>)',
                   lambda m: m.group(1) + bg + m.group(2), snap, flags=re.S)
    assert snap2 != snap, '没找到 #bgcss，背景重建失败'

    made = []
    jobs = [('E', os.path.join(OUTD, '\u53ef\u7231\u6837\u677f-\u4e3b\u9898\u81ea\u9002\u5e94-\u53ef\u5207\u6362.html'), True)]
    for t in themes:
        jobs.append((t['code'],
                     os.path.join(OUTD, '\u53ef\u7231\u6837\u677f-\u4e3b\u9898%s%s.html' % (t['code'], t['name'])),
                     False))

    for code, path, is_mix in jobs:
        html = snap2.replace('data-theme="E"', 'data-theme="%s"' % code, 1)
        note = ('<!-- \u4e91\u6735\u5c0f\u94fa \u00b7 \u53ef\u7231\u98ce\u6837\u677f\u300c\u4e91\u6735\u6ce1\u8299\u300d\uff08\u4e3b\u9898\u81ea\u9002\u5e94\u7248\uff09\n'
                '     \u53d6\u81ea\u771f\u5b9e\u8f6f\u4ef6\u9875\u9762\u7684\u5b8c\u6574\u9759\u6001\u5bfc\u51fa\uff1b\u5de6\u4fa7\u680f\u53ef\u70b9\u51fb\u5207\u9875\u3002\n'
                '     \u9020\u578b\u56fa\u5b9a\uff0c\u989c\u8272\u5168\u90e8\u8d70\u4e3b\u9898\u53d8\u91cf \u2014\u2014 \u4e94\u5957\u4e3b\u9898\u5404\u4fdd\u6301\u81ea\u5df1\u7684\u914d\u8272\u3002\n'
                '     %s\n     \u4ec5\u5916\u89c2\u6837\u677f\uff0c\u672a\u63a5\u540e\u7aef\u6570\u636e\u4e0e 3D \u9884\u89c8\u3002 -->\n'
                % ('\u5e95\u90e8\u4e3b\u9898\u6761\u53ef\u73b0\u573a\u5207\u4e3b\u9898\uff08\u4e5f\u53ef\u70b9\u4e3b\u9898\u9875\u7684\u5361\u7247\uff09\u3002'
                   if is_mix else '\u672c\u4efd\u9501\u5b9a\u4e3a\u300c%s\u300d\u4e3b\u9898\u3002' % code))
        html = note + (html.replace('</body>', add + '\n</body>') if '</body>' in html else html + add)
        open(path, 'w', encoding='utf-8').write(html)
        print('  %-34s %6d KB' % (os.path.basename(path), os.path.getsize(path) // 1024))
        made.append((path, code, is_mix))
    return made, themes


def shots(made, themes):
    port = 9421
    names = {t['code']: t['emoji'] + t['name'] for t in themes}
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % port,
        '--remote-allow-origins=*', '--user-data-dir=' + os.path.join(D, '_prof_cutemock3'),
        '--no-first-run', '--window-size=1330,720', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pngs = []
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
        idx = 0
        for p, code, is_mix in made:
            send('Page.navigate', {'url': 'file:///' + p.replace('\\', '/')})
            for _ in range(80):
                if ev("document.readyState==='complete' && !!document.getElementById('mkCute')"):
                    break
                time.sleep(0.25)
            time.sleep(2.4)
            if is_mix:      # 可切换那份，额外补一张主题页
                ev("(function(){var n=document.querySelector('.mv[data-view=theme]');if(n)n.click();})()")
                time.sleep(1.6)
                info = ev("({th:document.documentElement.getAttribute('data-theme'),"
                          "view:(document.querySelector('.view.on')||{}).id||'',"
                          "accent:getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),"
                          "cl:document.querySelectorAll('.mkCl').length,"
                          "pick:document.querySelectorAll('#themes .tcard').length})")
                d = send('Page.captureScreenshot', {'format': 'png'})
                out = os.path.join(SHOT, '\u4e3b\u9898\u81ea\u9002\u5e94-00-\u4e3b\u9898\u9875\u4e0e\u5207\u6362\u6761.png')
                open(out, 'wb').write(base64.b64decode(d['data']))
                print('  %-40s %5d KB  %s' % (os.path.basename(out), os.path.getsize(out) // 1024, info))
                ev("(function(){var n=document.querySelector('.mv[data-view=srv]');if(n)n.click();})()")
                time.sleep(1.4)
            info = ev("({th:document.documentElement.getAttribute('data-theme'),"
                      "view:(document.querySelector('.view.on')||{}).id||'',"
                      "accent:getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),"
                      "bg:getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(),"
                      "cl:document.querySelectorAll('.mkCl').length,"
                      "cards:document.querySelectorAll('.card').length})")
            d = send('Page.captureScreenshot', {'format': 'png'})
            out = os.path.join(SHOT, '\u4e3b\u9898\u81ea\u9002\u5e94-%s-%s.png'
                               % ('00b' if is_mix else '%02d' % (idx + 1), names[code]))
            open(out, 'wb').write(base64.b64decode(d['data']))
            print('  %-40s %5d KB  %s' % (os.path.basename(out), os.path.getsize(out) // 1024, info))
            if not is_mix:
                pngs.append(out); idx += 1
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
    return pngs


def sheet(pngs, themes):
    """五主题对照图：纵向拼版，去掉最后那张（主题页）。"""
    from PIL import Image
    rows = pngs[:5]
    if len(rows) < 5:
        return None
    scale = 0.46
    ims = [Image.open(p).convert('RGB') for p in rows]
    w = int(ims[0].width * scale); h = int(ims[0].height * scale)
    gap = 8
    out = Image.new('RGB', (w, h * len(ims) + gap * (len(ims) - 1)), (255, 255, 255))
    for i, im in enumerate(ims):
        out.paste(im.resize((w, h), Image.LANCZOS), (0, i * (h + gap)))
    p = os.path.join(SHOT, '\u4e3b\u9898\u81ea\u9002\u5e94-06-\u4e94\u4e3b\u9898\u5bf9\u7167.png')
    out.save(p)
    print('  %-40s %5d KB  %dx%d' % (os.path.basename(p), os.path.getsize(p) // 1024, w, out.height))
    return p


if __name__ == '__main__':
    print('\u751f\u6210\u4e3b\u9898\u81ea\u9002\u5e94\u7248\u6837\u677f\uff1a')
    made, themes = build()
    if '--shot' in sys.argv:
        print('\u622a\u56fe\u9a8c\u8bc1\uff1a')
        pngs = shots(made, themes)
        sheet(pngs, themes)

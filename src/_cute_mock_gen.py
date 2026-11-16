# -*- coding: utf-8 -*-
"""由 _snap_app.html（真实页面静态快照）生成多组「可爱风」HTML 样板。

   样板 = 和软件一样的完整页面（侧栏可点着切页），不是局部改动图。
   用法：  python _cute_mock_gen.py            # 只生成 HTML
          python _cute_mock_gen.py --shot     # 生成 + 逐个截图
"""
import base64, json, os, re, subprocess, sys, time, urllib.request
import websocket

D = r'C:\Users\1\WorkBuddy\2026-09-21-14-59-35'
SNAP = os.path.join(D, '_snap_app.html')
OUTD = os.path.join(D, '可爱样板-HTML')
SHOT = os.path.join(D, '验证截图-界面巡检')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
os.makedirs(OUTD, exist_ok=True)

VIEWNAME = {'srv': '服务器', 'ov': '屏幕覆盖', 'theme': '主题', 'lib': '地图库', 'set': '设置'}


def vars_block(v):
    keys = ['bg', 'panel', 'panel2', 'zebra', 'thead', 'side', 'ink', 'ink2', 'muted', 'line',
            'accent', 'soft', 'softline', 'sl69', 'sl40', 'good', 'goodsoft', 'glow',
            'blob1', 'blob2', 'radius', 'rsm']
    return 'html[data-theme]{' + ''.join('--%s:%s;' % (k, v[k]) for k in keys) + '}'


def common():
    """所有风格共用：粗描边 + 手绘硬投影 + 圆胖控件 + 漂浮贴纸。"""
    return """
/* 卡片：厚描边 + 手绘硬投影 */
.card,.libList,.libDetail,.themePal,.syncbox,.fxcard,.clgvw{
  border:3px solid var(--softline)!important;border-radius:var(--radius)!important;
  box-shadow:6px 7px 0 var(--sl69)!important}
.card:hover{border-color:var(--accent)!important}
.card h2::after{content:'';display:inline-block;width:9px;height:9px;margin-left:9px;
  border-radius:50%;background:var(--accent);opacity:.55;vertical-align:middle}
/* 侧栏 */
.side{box-shadow:6px 0 0 var(--sl40)!important}
.stop{border-bottom:3px dashed var(--softline)!important}
.logo{border-radius:14px}
.sname{font-weight:900!important}
/* 导航：胶囊 + 硬投影 */
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
/* 顶栏状态胶囊 */
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
#mkDeco i{position:absolute;font-style:normal;opacity:.42;
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


STYLES = {}

STYLES['A'] = dict(
    name='奶油布丁', emoji='🍮', view='srv',
    v=dict(bg='#fffaf1', panel='#fffefb', panel2='#fffdf4', zebra='#fffcf3', thead='#fff1d6',
           side='#fff5e2', ink='#5a4526', ink2='#7a5f38', muted='#a89070', line='#ffe6ba',
           accent='#f2a03d', soft='#fff2da', softline='#f0b955',
           sl69='rgba(240,185,85,.69)', sl40='rgba(240,185,85,.40)', good='#e0902f',
           goodsoft='#fff3df', glow='rgba(242,160,61,.16)', blob1='#fff0cf', blob2='#ffeedd',
           radius='26px', rsm='15px'),
    deco=['🍮', '🥧', '🍯', '🧁', '🍪', '🍞'],
    extra="""
/* 布丁：奶黄斜纹底 + 焦糖圆点标题 */
.main,.content{background:
  repeating-linear-gradient(45deg,rgba(240,185,85,.06) 0 12px,transparent 12px 24px),
  radial-gradient(500px 300px at 6% 0%,#fff3d9,transparent 70%),
  radial-gradient(460px 280px at 96% 4%,#ffeeda,transparent 70%),var(--bg)!important}
.side{background:linear-gradient(180deg,#fff6e4,#fff1d8)!important}
.card h2{background:linear-gradient(90deg,var(--soft),transparent 78%);border-radius:999px;
  padding:5px 16px 5px 12px!important;display:inline-block}
.pill i{background:var(--accent)}
""")

STYLES['B'] = dict(
    name='草莓牛奶', emoji='🍓', view='lib',
    v=dict(bg='#fff6f9', panel='#ffffff', panel2='#fff8fb', zebra='#fffafc', thead='#ffe6f0',
           side='#ffeff5', ink='#5b3549', ink2='#7d5064', muted='#b08a99', line='#ffd4e3',
           accent='#ff6fa5', soft='#ffe9f2', softline='#ff9dc3',
           sl69='rgba(255,157,195,.69)', sl40='rgba(255,157,195,.40)', good='#e8558e',
           goodsoft='#ffeaf3', glow='rgba(255,111,165,.16)', blob1='#ffe0ec', blob2='#ffeef6',
           radius='30px', rsm='17px'),
    deco=['🍓', '💗', '🎀', '🍰', '🧸', '💕'],
    extra="""
/* 草莓牛奶：小波点底 + 卡片顶爱心 */
.main,.content{background:
  radial-gradient(rgba(255,157,195,.22) 2.1px,transparent 2.2px) 0 0/26px 26px,
  radial-gradient(520px 320px at 4% 2%,#ffe6f1,transparent 72%),
  radial-gradient(480px 300px at 98% 6%,#ffeef6,transparent 72%),var(--bg)!important}
.side{background:linear-gradient(180deg,#fff0f6,#ffe8f2)!important}
.card{position:relative}
.card::after{content:'\\1F497';position:absolute;right:15px;top:-13px;font-size:17px;
  filter:drop-shadow(0 3px 4px rgba(255,111,165,.35))}
.card h2{color:var(--accent)}
""")

STYLES['C'] = dict(
    name='薄荷果冻', emoji='🍀', view='set',
    v=dict(bg='#f1fdf8', panel='#ffffff', panel2='#f6fffb', zebra='#f8fffd', thead='#d9f7ec',
           side='#e6fbf2', ink='#1e4a3a', ink2='#37685a', muted='#7ba79a', line='#b6ecd7',
           accent='#2fbf8f', soft='#ddf7ec', softline='#7fd9b8',
           sl69='rgba(127,217,184,.69)', sl40='rgba(127,217,184,.40)', good='#28a97a',
           goodsoft='#e2f8ef', glow='rgba(47,191,143,.18)', blob1='#d8f8ec', blob2='#e6fbff',
           radius='24px', rsm='14px'),
    deco=['🍀', '🌿', '🧊', '💎', '🍃', '🫧'],
    extra="""
/* 薄荷果冻：玻璃拟态 + 内高光 */
.main,.content{background:
  radial-gradient(560px 340px at 8% 0%,#dcf9ef,transparent 72%),
  radial-gradient(520px 320px at 96% 4%,#e3fbff,transparent 72%),var(--bg)!important}
.side{background:linear-gradient(180deg,#e8fcf4,#dff8ee)!important}
.card h2{color:var(--accent)}
.pill i{box-shadow:0 0 0 5px rgba(47,191,143,.18)}
.nav.on{background:linear-gradient(180deg,#ffffff,#e9fcf5)!important}
""")

STYLES['D'] = dict(
    name='云朵棉花糖', emoji='☁️', view='theme',
    v=dict(bg='#f3f9ff', panel='#ffffff', panel2='#f7fbff', zebra='#fafdff', thead='#e3f1ff',
           side='#eaf5ff', ink='#2b4a66', ink2='#446b8d', muted='#89a7c2', line='#cde6fc',
           accent='#57a8ea', soft='#e6f3ff', softline='#8ec6f2',
           sl69='rgba(142,198,242,.69)', sl40='rgba(142,198,242,.40)', good='#3f9ae0',
           goodsoft='#e8f5ff', glow='rgba(87,168,234,.18)', blob1='#e0f0ff', blob2='#f0f8ff',
           radius='28px', rsm='16px'),
    deco=['☁️', '🫧', '⭐', '🌤️', '🐑', '✨'],
    extra="""
/* 云朵棉花糖：云朵凸顶卡片 + 泡泡底 */
.main,.content{background:
  radial-gradient(circle at 11% 7%,rgba(255,255,255,.96) 0 44px,transparent 45px),
  radial-gradient(circle at 18% 5%,rgba(255,255,255,.96) 0 32px,transparent 33px),
  radial-gradient(560px 340px at 8% 0%,#e3f2ff,transparent 72%),
  radial-gradient(520px 320px at 96% 4%,#eff8ff,transparent 72%),var(--bg)!important}
.side{background:linear-gradient(180deg,#eef7ff,#e4f1ff)!important}
.card{position:relative;border-radius:34px 34px var(--radius) var(--radius)!important}
.card::before{content:'\\2601';position:absolute;left:20px;top:-21px;font-size:31px;line-height:1;
  color:var(--softline);text-shadow:0 3px 0 rgba(255,255,255,.92)}
.sname{color:var(--accent)}
.nav.on{background:#fff!important;border-color:var(--softline)!important}
""")

STYLES['E'] = dict(
    name='紫罗兰梦境', emoji='🌙', view='ov',
    v=dict(bg='#f9f6ff', panel='#ffffff', panel2='#faf8ff', zebra='#fcfaff', thead='#ede6ff',
           side='#f1ecff', ink='#3b3260', ink2='#584c86', muted='#9a8fbe', line='#ded2ff',
           accent='#8f6bff', soft='#ece5ff', softline='#a488ff',
           sl69='rgba(164,136,255,.69)', sl40='rgba(164,136,255,.40)', good='#7a5cf5',
           goodsoft='#efeaff', glow='rgba(143,107,255,.18)', blob1='#e9e0ff', blob2='#f3ecff',
           radius='26px', rsm='15px'),
    deco=['🌙', '✨', '⭐', '🔮', '💫', '🪄'],
    extra="""
/* 紫罗兰梦境：星光点底 + 渐变描边 */
.main,.content{background:
  radial-gradient(rgba(164,136,255,.20) 1.6px,transparent 1.7px) 0 0/34px 34px,
  radial-gradient(580px 360px at 6% 0%,#eae1ff,transparent 72%),
  radial-gradient(520px 320px at 97% 6%,#f4ecff,transparent 72%),var(--bg)!important}
.side{background:linear-gradient(180deg,#f3edff,#ece4ff)!important}
.card{background:linear-gradient(var(--panel),var(--panel)) padding-box,
  linear-gradient(135deg,var(--softline),#c9b8ff 55%,#ffd9f0) border-box!important;
  border-color:transparent!important}
.sname{background:linear-gradient(90deg,var(--accent),#c98cff);-webkit-background-clip:text;
  background-clip:text;color:transparent}
.card h2{color:var(--accent)}
""")

SWITCHER = """
<script>
(function(){
  var V=['srv','ov','theme','lib','pre','set'];
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
  go('__VIEW__');
})();
</script>
"""

SPOTS = [(20, 20), (93, 11), (23, 75), (96, 62), (52, 5), (34, 90), (79, 83), (8, 32)]


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
    for key in ['A', 'B', 'C', 'D', 'E']:
        st = STYLES[key]
        css = vars_block(st['v']) + common() + st['extra']
        head = ('<!-- 云朵小铺 · 可爱风样板 %s「%s」\n'
                '     取自真实软件页面的完整静态导出；左侧栏可点击切换页面。\n'
                '     仅外观样板，未接后端数据与 3D 预览。 -->\n' % (key, st['name']))
        add = ('<style id="mkCute">\n' + css + '\n</style>\n'
               '<div id="mkBadge">%s 样板 %s<b>%s</b></div>\n%s\n%s'
               % (st['emoji'], key, st['name'], deco_html(st['deco']),
                  SWITCHER.replace('__VIEW__', st['view'])))
        html = head + (snap.replace('</body>', add + '\n</body>')
                       if '</body>' in snap else snap + add)
        p = os.path.join(OUTD, '可爱%s-%s.html' % (key, st['name']))
        open(p, 'w', encoding='utf-8').write(html)
        print('  %-24s %6d KB  默认页=%s' % (os.path.basename(p),
                                            os.path.getsize(p) // 1024,
                                            VIEWNAME.get(st['view'], st['view'])))
        made.append((p, st))
    return made


def shots(made):
    port = 9407
    prof = os.path.join(D, '_prof_cutemock')
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    proc = subprocess.Popen([EDGE, '--headless=new', '--remote-debugging-port=%d' % port,
        '--remote-allow-origins=*', '--user-data-dir=' + prof, '--no-first-run',
        '--window-size=1330,720', 'about:blank'],
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
        send('Emulation.setDeviceMetricsOverride',
             {'width': 1330, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})
        # 冻结动画，保证截图稳定
        for p, st in made:
            url = 'file:///' + p.replace('\\', '/')
            send('Page.navigate', {'url': url})
            for _ in range(80):
                if ev("document.readyState==='complete' && !!document.getElementById('mkCute')"):
                    break
                time.sleep(0.25)
            time.sleep(2.6)
            info = ev("({badge:(document.getElementById('mkBadge')||{}).textContent||'',"
                      "view:(document.querySelector('.view.on')||{}).id||'',"
                      "cards:document.querySelectorAll('.card').length,"
                      "deco:document.querySelectorAll('#mkDeco i').length,"
                      "stk:!!document.getElementById('cuteSticker')})")
            d = send('Page.captureScreenshot', {'format': 'png'})
            out = os.path.join(SHOT, '可爱样板-HTML%s-%s.png'
                               % (list('ABCDE')[made.index((p, st))], st['name']))
            open(out, 'wb').write(base64.b64decode(d['data']))
            print('  %-22s %5d KB  %s' % (os.path.basename(out),
                                          os.path.getsize(out) // 1024, info))
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == '__main__':
    print('生成可爱风 HTML 样板：')
    m = build()
    if '--shot' in sys.argv:
        print('截图验证：')
        shots(m)

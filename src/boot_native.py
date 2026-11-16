# -*- coding: utf-8 -*-
"""原生启动卡：把启动卡直接画在 WinForms 窗体本体上（GDI+ 位图），不等网页引擎。

背景：页面自带的 #bootSplash 要等 WebView2 控件初始化 + 首次导航 + 首帧渲染
才画得出来（实测窗口可见后还有约 1.5 秒空档）。此前这段空档只有纯色底，
用户看到「空白窗口数秒才出现加载界面」。本模块用 System.Drawing 把与页面版
同款的启动卡画成位图铺在窗体上——窗口出现的第一帧就是完整启动卡，
WebView2 就绪后页面首帧无缝接管（页面启动卡与原生卡同布局同配色）。

线程模型：BrowserForm 在 webview.start() 的 GUI 线程里创建，patch() 挂在
__init__ 上同步渲染；set_phase()/脉动线程经 Control.BeginInvoke 回 GUI 线程改图。
任何一步失败都静默降级（窗体退回纯色底），绝不阻塞启动。
"""
import os
import threading

# 可变状态（[0] 容器，GUI 线程读、任意线程写）
_PHASE = ["正在启动…"]
_PCT = [10.0]
_VER = ""
_THEME = "E"
_LOGO = None           # System.Drawing.Image（启动后常驻）
_forms = []            # 存活的 BrowserForm
_stop = threading.Event()
_pulse_started = False
_lock = threading.Lock()

# ── 配色镜像 ui_page.py 的 bootSplashCss：浅色=奶油云朵卡(A)，N=夜幕星云(B) ──
_DARK = ("N",)


def _col(hexstr, alpha=255):
    from System.Drawing import Color
    hexstr = hexstr.lstrip("#")
    return Color.FromArgb(alpha, int(hexstr[0:2], 16),
                          int(hexstr[2:4], 16), int(hexstr[4:6], 16))


def _rounded(g, brush, x, y, w, h, r, pen=None):
    """圆角矩形（GraphicsPath 四角 Arc 拼）。"""
    from System.Drawing import Drawing2D
    p = Drawing2D.GraphicsPath()
    d = 2 * r
    p.AddArc(x, y, d, d, 180, 90)
    p.AddArc(x + w - d, y, d, d, 270, 90)
    p.AddArc(x + w - d, y + h - d, d, d, 0, 90)
    p.AddArc(x, y + h - d, d, d, 90, 90)
    p.CloseFigure()
    if brush is not None:
        g.FillPath(brush, p)
    if pen is not None:
        g.DrawPath(pen, p)


def _px(sz):
    from System.Drawing import Font, FontStyle, GraphicsUnit
    return lambda: Font("Microsoft YaHei", max(1.0, float(sz)),
                        FontStyle.Bold, GraphicsUnit.Pixel)


def _render(w, h, theme, phase, pct):
    """按窗口尺寸渲染整张启动卡位图。"""
    from System.Drawing import Bitmap, Graphics, Pen, SolidBrush, StringFormat
    from System.Drawing import StringAlignment
    from System.Drawing.Drawing2D import LinearGradientBrush
    from System.Drawing.Text import TextRenderingHint

    dark = theme in _DARK
    bmp = Bitmap(w, h)
    g = Graphics.FromImage(bmp)
    g.SmoothingMode = _smooth(g)
    g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit

    # 背景：与页面 #bootSplash 同款的斜向渐变
    c1, c2 = ("#221c2e", "#141318") if dark else ("#fff6f8", "#ffe7ef")
    br = LinearGradientBrush(_rect(0, 0, w, h), _col(c1), _col(c2),
                             165.0 if dark else 160.0)
    g.FillRectangle(br, _rect(0, 0, w, h))

    s = max(0.75, min(1.35, min(w, h) / 560.0))
    # 装饰：浅色=两朵白云胶囊；深色=几颗星点
    if not dark:
        _rounded(g, SolidBrush(_col("#ffffff", 140)),
                 int(w * .04), int(h * .82), int(120 * s), int(38 * s), int(19 * s))
        _rounded(g, SolidBrush(_col("#ffffff", 100)),
                 int(w * .82), int(h * .10), int(92 * s), int(30 * s), int(15 * s))
    else:
        for fx, fy, r, hexc, a in ((.14, .22, 2.0, "#e9e4ee", 210),
                                   (.28, .52, 1.5, "#f0a868", 190),
                                   (.84, .18, 2.0, "#e9e4ee", 200),
                                   (.70, .42, 1.5, "#ffffff", 160),
                                   (.08, .64, 1.8, "#e9e4ee", 170),
                                   (.90, .60, 1.5, "#f0a868", 160)):
            g.FillEllipse(SolidBrush(_col(hexc, a)),
                          _rect(int(w * fx - r * s), int(h * fy - r * s),
                                int(2 * r * s), int(2 * r * s)))

    # 启动卡：深色=玻璃拟态（深底 + 暖橙描边），浅色=白卡
    cw, ch = int(360 * s), int(300 * s)
    cx, cy = (w - cw) // 2, (h - ch) // 2
    if dark:
        _rounded(g, SolidBrush(_col("#1e1d24", 230)), cx, cy, cw, ch, int(20 * s),
                 pen=Pen(_col("#f0a868", 72), 1.0))
    else:
        _rounded(g, SolidBrush(_col("#ffffff", 242)), cx, cy, cw, ch, int(20 * s),
                 pen=Pen(_col("#f2c7d7", 130), 1.0))

    sf = StringFormat()
    sf.Alignment = StringAlignment.Center
    sf.LineAlignment = StringAlignment.Center

    # logo
    ly = cy + int(28 * s)
    if _LOGO is not None:
        lw = int(76 * s)
        g.DrawImage(_LOGO, cx + (cw - lw) // 2, ly, lw, lw)
    else:                                   # 没有 logo 画一朵云占位
        _rounded(g, SolidBrush(_col("#f2a9c6" if not dark else "#3a3648")),
                 cx + (cw - int(72 * s)) // 2, ly + int(10 * s),
                 int(72 * s), int(44 * s), int(22 * s))

    tx = cx + cw / 2.0
    y = ly + int(76 * s) + int(12 * s)
    _draw_text(g, "云朵小铺", _px(int(26 * s)),
               SolidBrush(_col("#f2ecf6" if dark else "#4a323c")), tx, y + int(12 * s), sf)
    _draw_text(g, "FYS 通关奖励看板 · " + _VER, _px(int(13 * s)),
               SolidBrush(_col("#9d92ac" if dark else "#b292a0")),
               tx, y + int(44 * s), sf)
    _draw_text(g, phase, _px(int(14 * s)),
               SolidBrush(_col("#cfc6da" if dark else "#7a5568")),
               tx, y + int(86 * s), sf)

    # 进度条：深色细线 3px，浅色 6px
    bw, bh = int((280 if dark else 300) * s), max(3, int((3 if dark else 6) * s))
    bx = (w - bw) // 2
    by = y + int(116 * s)
    _rounded(g, SolidBrush(_col("#3a3944" if dark else "#f2608d",
                                36 if dark else 41)), bx, by, bw, bh, bh // 2)
    fill = max(int(bw * 0.08), int(bw * min(1.0, max(0.0, pct / 100.0))))
    if fill > bh:
        _rounded(g, SolidBrush(_col("#f0a868" if dark else "#f2608d")),
                 bx, by, fill, bh, bh // 2)
    _draw_text(g, "正在准备界面，马上就好…", _px(int(11 * s)),
               SolidBrush(_col("#8b8098" if dark else "#c4a5b3")),
               tx, by + bh + int(22 * s), sf)
    g.Dispose()
    return bmp


def _draw_text(g, text, font_fn, brush, x, y, sf):
    g.DrawString(text, font_fn(), brush, _pt(x, y), sf)


def _rect(x, y, w, h):
    from System.Drawing import Rectangle
    return Rectangle(int(x), int(y), int(w), int(h))


def _pt(x, y):
    from System.Drawing import PointF
    return PointF(float(x), float(y))


def _smooth(g):
    from System.Drawing import Drawing2D
    return Drawing2D.SmoothingMode.AntiAlias


# ────────────────────────────── 窗体补丁 ──────────────────────────────
def patch(ver, theme, logo_path, logfn=None):
    """挂 BrowserForm.__init__ 补丁：建窗即铺启动卡。必须在 webview.start 之前调。"""
    global _VER, _THEME, _LOGO, _pulse_started
    _VER, _THEME = ver, theme
    try:
        from webview.platforms import winforms as _wf
        from System import Array, Byte, Action
        from System.Drawing import Image
        from System.IO import MemoryStream
        from System.Windows.Forms import ImageLayout

        try:                                   # logo 只解码一次（PNG 字节 → Image）
            if logo_path and os.path.exists(logo_path):
                with open(logo_path, "rb") as fh:
                    raw = fh.read()
                ms = MemoryStream(Array[Byte](bytearray(raw)))
                _LOGO = Image.FromStream(ms)
        except Exception:                      # noqa: BLE001
            _LOGO = None

        orig = _wf.BrowserView.BrowserForm.__init__

        def _apply(f):
            try:
                cs = f.ClientSize
                f.BackgroundImage = _render(max(320, cs.Width), max(240, cs.Height),
                                            _THEME, _PHASE[0], _PCT[0])
                f.BackgroundImageLayout = ImageLayout.Stretch
            except Exception:                  # noqa: BLE001
                pass

        def _bf_init_patched(self, window, cache_dir, *a, **kw):
            global _pulse_started
            orig(self, window, cache_dir, *a, **kw)
            try:                               # 底色与卡片背景一致（缩放边缘无色差）
                hx = str(window.background_color or "#ffffff").lstrip("#")
                from System.Drawing import Color
                self.BackColor = Color.FromArgb(255, int(hx[0:2], 16),
                                                int(hx[2:4], 16), int(hx[4:6], 16))
            except Exception:                  # noqa: BLE001
                pass
            try:
                _apply(self)
                with _lock:
                    _forms.append(self)
                if not _pulse_started:
                    _pulse_started = True
                    threading.Thread(target=_pulse, daemon=True,
                                     name="boot-pulse").start()
                if logfn:
                    logfn("step: 原生启动卡已铺上窗体（主题 %s）" % _THEME)
            except Exception as e:             # noqa: BLE001
                if logfn:
                    logfn("[!] 原生启动卡渲染失败（%r），退回纯色底。" % e)

        _wf.BrowserView.BrowserForm.__init__ = _bf_init_patched
        return True
    except Exception as e:                     # noqa: BLE001
        if logfn:
            logfn("[!] 原生启动卡补丁未挂上（%r）。" % e)
        return False


def _alive():
    with _lock:
        live = [f for f in _forms
                if _form_ok(f)]
        _forms[:] = live
    return live


def _form_ok(f):
    try:
        return (not f.IsDisposed) and f.IsHandleCreated
    except Exception:                          # noqa: BLE001
        return False


def _invoke_all(fn):
    """把 fn(form) 派发到每个存活窗体的 GUI 线程。

    ⚠ Control.BeginInvoke(Delegate) 调用委托时**不带任何参数**——委托必须是
    无参签名，form 用默认参数绑进 lambda（此前 Action(lambda f: fn(f)) 直接
    触发 .NET 未处理异常「missing 1 required positional argument: 'f'」）。"""
    from System import Action
    for f in _alive():
        try:
            f.BeginInvoke(Action(lambda ff=f: fn(ff)))
        except Exception:                      # noqa: BLE001
            pass


def set_phase(text, pct=None):
    """更新阶段文案 / 进度（窗体还没建时只是记下，建窗时首帧就用最新值）。"""
    _PHASE[0] = text
    if pct is not None:
        _PCT[0] = float(pct)
    _invoke_all(lambda f: _apply_one(f))


def _apply_one(f):
    try:
        from System.Windows.Forms import ImageLayout
        cs = f.ClientSize
        f.BackgroundImage = _render(max(320, cs.Width), max(240, cs.Height),
                                    _THEME, _PHASE[0], _PCT[0])
        f.BackgroundImageLayout = ImageLayout.Stretch
    except Exception:                          # noqa: BLE001
        pass


def _pulse():
    """脉动线程：进度条缓慢爬升（封顶 90%），等页面版启动卡接管。"""
    import time
    t0 = time.time()
    while not _stop.is_set() and time.time() - t0 < 60.0:
        time.sleep(0.4)
        if not _alive():
            return
        if _PCT[0] < 88.0:
            _PCT[0] = min(88.0, _PCT[0] + (2.2 if _PCT[0] < 55 else 1.1))
            _invoke_all(lambda f: _apply_one(f))


def finish():
    """页面接管后停掉脉动（防无效重绘）。"""
    _stop.set()

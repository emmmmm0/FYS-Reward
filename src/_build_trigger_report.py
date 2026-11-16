# -*- coding: utf-8 -*-
"""从本地实体数据生成「点位与触发」报告（HTML）。

数据源：E:\\FYS-cache\\_ents_raw\\<工坊ID>.json
    —— 由 _ghcrawl/_build_meshes.py 的 extract_ents_from_vpk(keep_kv=True) 产出，
       直接从 CS2 地图 VPK 的 entity lump 里读，不依赖游戏运行。

每条实体字段：
    cn  classname      o   origin[x,y,z]      c  世界AABB中心     h  世界AABB半长
    nm  targetname     kv 白名单属性          cx 触发连接(output/target/input/param/delay)

用法：
    python _build_trigger_report.py ze_devil_may_cry ze_mota
    python _build_trigger_report.py --all-ids 3740894839
    python _build_trigger_report.py --top 5          # 触发区最多的 5 张
"""
import html
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ENTS = os.environ.get("FYS_ENTS_DIR") or r"E:\FYS-cache\_ents_raw"
OUT_DIR = os.environ.get("FYS_TRIG_OUT") or os.path.join(
    os.path.dirname(HERE), "点位触发报告")

# ────────────────────────────── 中文注解表 ──────────────────────────────
CLS_CN = {
    "trigger_multiple": ("触发区", "有人走进这块区域就触发一次（可重复）"),
    "trigger_once": ("触发区·单次", "只触发一次，之后失效"),
    "trigger_hurt": ("伤害区", "停留在区域内持续扣血"),
    "trigger_push": ("推力区", "把进去的人推开／吹走"),
    "trigger_teleport": ("传送点", "进去立刻传送到目标点"),
    "trigger_multiple_zone": ("分区触发区", "按区域判定触发"),
    "func_button": ("按钮", "靠近按 E 触发"),
    "func_rot_button": ("旋钮", "旋转式按钮"),
    "func_door": ("门", "推拉门"),
    "func_door_rotating": ("旋转门", "绕轴开合的门"),
    "func_movelinear": ("直线机关", "沿固定方向移动的机关"),
    "func_breakable": ("可破坏物", "打碎后触发连接"),
    "func_physbox": ("物理方块", "可推动的物理体"),
    "func_wall_toggle": ("可开关墙", "能启用/禁用的墙"),
    "func_brush": ("刷子实体", "通用几何实体（可开关）"),
    "logic_relay": ("逻辑中继", "纯转发：收到信号就往下传"),
    "logic_timer": ("定时器", "按间隔反复发信号"),
    "logic_case": ("多路分支", "按输入值选一路触发"),
    "logic_auto": ("开局自动", "地图开局时触发"),
    "math_counter": ("计数器", "累加到阈值后触发"),
    "point_servercommand": ("服务器指令", "向服务端发一条控制台指令"),
    "env_entity_maker": ("实体生成器", "在指定位置生成实体"),
    "env_fade": ("画面淡入淡出", ""),
    "game_text": ("屏幕文字", "在玩家屏幕显示文字"),
    "env_shake": ("屏幕震动", ""),
    "point_teleport": ("传送目标", "被 teleport 指令调用的落点"),
    "info_target": ("目标锚点", "给别的实体当参照点"),
    "info_player_start": ("玩家出生点", ""),
    "info_player_terrorist": ("人类出生点", ""),
    "info_player_counterterrorist": ("僵尸出生点", ""),
    "prop_dynamic": ("静态模型", ""),
    "prop_physics_multiplayer": ("物理道具", ""),
    "ambient_generic": ("环境音", ""),
    "env_soundscape": ("声音环境", ""),
}

OUT_CN = {
    "OnStartTouch": "有人进入时",
    "OnEndTouch": "有人离开时",
    "OnTrigger": "被触发时",
    "OnUser1": "收到 User1 信号时",
    "OnUser2": "收到 User2 信号时",
    "OnUser3": "收到 User3 信号时",
    "OnUser4": "收到 User4 信号时",
    "OnSpawn": "生成时",
    "OnMapSpawn": "地图开始时",
    "OnTimer": "计时到点时",
    "OnHitMax": "计数到上限时",
    "OnBreak": "被破坏时",
    "OnPressed": "被按下时",
    "OnPlayerUse": "玩家使用时",
    "OnFullyOpen": "完全打开时",
    "OnFullyClosed": "完全关闭时",
    "OnTrue": "判定为真时",
    "OnFalse": "判定为假时",
    "OnEventFired": "事件发生时",
    "OnNotEqualTo": "不等于时",
    "OnEqualTo": "等于时",
    "OnHalfHealth": "血量减半时",
    "OnDamaged": "受到伤害时",
    "OnKilled": "被击杀时",
    "OnIgnite": "被点燃时",
    "OnCase01": "分支 01 命中",
    "OnCase02": "分支 02 命中",
    "OnCase03": "分支 03 命中",
    "OnCase04": "分支 04 命中",
    "OnCase05": "分支 05 命中",
    "OnCase06": "分支 06 命中",
    "OnCase07": "分支 07 命中",
    "OnCase08": "分支 08 命中",
    "OnCase09": "分支 09 命中",
    "OnHurtPlayer": "玩家在区内受伤时",
    "OnStartTouchAll": "所有符合条件的进入时",
    "OnEndTouchAll": "所有符合条件的离开时",
    "OnAllPlayersLeft": "所有玩家离开时",
    "OnTriggered": "被触发时",
    "OnBlocked": "被阻挡时",
    "OnTimeout": "超时时",
    "OnPass": "通过判定时",
    "OnFail": "判定失败时",
    "OnSpawned": "生成时",
    "OnCacheLoaded": "缓存载入时",
    "OnBecomeArmed": "进入待发状态时",
    "OnDisarmed": "解除待发时",
    "OnDetonate": "起爆时",
    "OnFirstTouch": "首次接触时",
    "OnHealthChanged": "血量变化时",
    "OnGetValue": "被取值时",
    "OnHitMin": "计到下限时",
    "OnHitMax": "计到上限时",
    "OnNotTouching": "无人接触时",
    "OnOpen": "打开时",
    "OnClose": "关闭时",
    "OutValue": "输出数值",
    "OnFullyClosed": "完全关闭时",
    "OnHalfHealth": "血量减半时",
    "OnGreaterThan": "大于阈值时",
    "OnChangedFromMin": "从下限变化时",
    "OnChangedFromMax": "从上限变化时",
    "OnLessThan": "小于阈值时",
    "OnEqualTo": "等于时",
    "OnNotEqualTo": "不等于时",
}

# 特殊目标占位符
TGT_CN = {
    "!activator": "触发者", "!caller": "调用者", "!self": "自身",
    "!player": "玩家", "!pvsplayer": "视野内玩家", "!activator_held": "触发者",
    "!team1": "人类队伍", "!team2": "僵尸队伍",
}

IN_CN = {
    "Enable": "启用", "Disable": "禁用", "Toggle": "切换开关",
    "FireUser1": "发 User1", "FireUser2": "发 User2",
    "FireUser3": "发 User3", "FireUser4": "发 User4",
    "Open": "打开", "Close": "关闭", "Lock": "上锁", "Unlock": "解锁",
    "Kill": "移除", "Break": "打破", "Trigger": "触发一次",
    "Start": "开始", "Stop": "停止", "StartForward": "正向运转",
    "StartBackward": "反向运转", "StartShake": "开始震动",
    "StartSound": "播放声音", "StopSound": "停止声音",
    "Ignite": "点燃", "ShowSprite": "显示图标",
    "Command": "执行指令", "RunScriptCode": "执行脚本",
    "EnableMotion": "启用移动", "DisableMotion": "禁用移动",
    "Volume": "设置音量", "PickRandom": "随机抽取",
    "SetFogController": "设置雾效", "SetDamageFilter": "设置伤害过滤",
    "KeyValues": "改键值", "ForceSpawn": "强制生成",
    "SetHealth": "设置血量", "AddOutput": "追加输出",
    "TurnOn": "开启", "TurnOff": "关闭", "Skin": "换皮肤",
    "SetModel": "换模型", "Move": "移动", "Resume": "继续",
    "Color": "设置颜色", "Alpha": "设置透明度",
    "SetParent": "设置父级", "ClearParent": "解除父级",
    "SetDamageFilter": "设置伤害过滤", "SetHealth": "设置血量",
    "AddHealth": "加血", "SetMaxHealth": "设置最大血量",
    "SetSpeed": "设置速度", "SetGravity": "设置重力",
    "SetAngles": "设置朝向", "SetPosition": "设置位置",
    "SetScale": "设置缩放", "SetMaterialGroup": "换材质组",
    "SetLightColor": "设置灯光颜色", "SetPattern": "设置图案",
    "StartGlowing": "开始发光", "StopGlowing": "停止发光",
    "SetDamage": "设置伤害", "SetDamageType": "设置伤害类型",
    "SetTarget": "设置目标", "SetTargetName": "设置名称",
    "SetTime": "设置时间", "SetValue": "设置数值",
    "Add": "加", "Subtract": "减", "Multiply": "乘", "Divide": "除",
    "SetValueNoFire": "设置数值（不触发）",
    "Increment": "递增", "Decrement": "递减",
    "ForceSpawn": "强制生成", "Spawn": "生成",
    "Destroy": "销毁", "Delete": "删除",
    "Trace": "射线检测", "Update": "刷新",
    "StartForward": "正向运转", "StartBackward": "反向运转",
    "SetAnimation": "播放动画", "SetSequence": "设置序列",
    "InValue": "传入数值", "OutValue": "输出数值",
    "TeleportToCurrentPos": "传送到当前位置", "RunScriptInput": "执行脚本",
    "ResetTimer": "重置计时", "SetMessage": "设置文字",
    "SetText": "设置文字", "SetKeyValue": "设置键值",
    "KeyValue": "改键值", "KeyValues": "改键值",
    "FireEvent": "触发事件", "StopLoopingSound": "停止循环音",
    "SetSoundVolume": "设置音量", "SetFadeColor": "设置渐隐颜色",
    "Deactivate": "停用", "Activate": "启用",
    "SetIntMessage": "设置整数消息", "SetFloatMessage": "设置浮点消息",
    "PickRandomShuffle": "随机洗牌抽取", "PickRandom": "随机抽取",
    "TestActivator": "检测触发者", "SetInValue": "设置传入值",
    "SetHitMax": "设置上限", "SetHitMin": "设置下限",
    "SetMaxValue": "设置最大值", "SetMinValue": "设置最小值",
    "BecomeArmed": "进入待发", "Disarm": "解除待发",
    "SetDamagePercentage": "设置伤害百分比",
    "Fade": "淡入淡出", "Use": "玩家使用", "Teleport": "传送",
    "Explode": "起爆", "SetAnimationNotLooping": "播放动画（不循环）",
    "SetAnimationLooping": "播放动画（循环）",
    "AddContext": "添加上下文", "RemoveContext": "移除上下文",
    "FindEntity": "查找实体", "FindByName": "按名称查找",
    "RunScriptCode": "执行脚本", "CallScriptFunction": "调用脚本函数",
    "SetBreakable": "设为可破坏", "SetBodyGroup": "设置身体分组",
    "SetFog": "设置雾效", "SetSkybox": "设置天空盒",
    "SetModelScale": "设置模型缩放", "SetHealthPercent": "设置血量百分比",
}

# 属性键中文名（以 _build_preview_data.ATTR_WANT 的「短名」为准，与游戏内预览一致）
ATTR_CN = {
    "damage": "伤害值", "dmgcap": "单次伤害上限", "dmgtype": "伤害类型",
    "dmgmodel": "伤害判定模型", "dmgscale": "伤害倍率", "dmgdelay": "伤害延迟",
    "dmgrad": "伤害半径", "hp": "血量", "target": "目标",
    "filter": "生效过滤（谁能触发）", "filtercls": "过滤类名", "negated": "过滤取反",
    "speed": "速度", "wait": "冷却时间", "dmg": "伤害", "flags": "生成标志",
    "startoff": "初始关闭", "expldmg": "爆炸伤害", "explr": "爆炸半径",
    "magnitude": "强度", "magradius": "强度半径", "delay": "延迟",
    "mindelay": "最短延迟", "maxdelay": "最长延迟", "landmark": "锚点",
    "useLandmarkAngles": "按锚点朝向", "checkDestClear": "检查落点是否可站",
    "trigOnStart": "开局即触发", "radius": "半径", "filterAttr": "过滤属性",
}

# 原始实体数据里的长键名 → 上表的短名（与 _ghcrawl/_build_meshes.ATTR_SRC 对齐）
ATTR_ALIAS = {
    "Damage": "damage", "damagecap": "dmgcap", "damagetype": "dmgtype",
    "damagemodel": "dmgmodel", "damagescale": "dmgscale",
    "DamageDelay": "dmgdelay", "DamageType": "dmgtype", "DamageRadius": "dmgrad",
    "health": "hp", "filtername": "filter", "filterclass": "filtercls",
    "Negated": "negated", "spawnflags": "flags", "StartDisabled": "startoff",
    "ExplodeDamage": "expldmg", "ExplodeRadius": "explr",
    "iMagnitude": "magnitude", "iRadiusOverride": "magradius",
    "MinDelay": "mindelay", "MaxDelay": "maxdelay",
    "UseLandmarkAngles": "useLandmarkAngles",
    "CheckDestIfClearForPlayer": "checkDestClear",
    "triggeronstarttouch": "trigOnStart", "filterattribute": "filterAttr",
}


def cn_cls(c):
    v = CLS_CN.get(c)
    return v[0] if v else None


# 大小写不敏感查表
_OUT_L = {k.lower(): v for k, v in OUT_CN.items()}
_IN_L = {k.lower(): v for k, v in IN_CN.items()}


def cn_out(o):
    o = str(o).strip()
    v = OUT_CN.get(o) or _OUT_L.get(o.lower())
    if v:
        return v
    m = re.match(r"OnCase(\d+)$", o)
    if m:
        return "分支 %02d 命中" % int(m.group(1))
    m = re.match(r"OnUser(\d+)$", o)
    if m:
        return "收到 User%s 信号时" % m.group(1)
    return o


def cn_in(i):
    i = str(i).strip()
    return IN_CN.get(i) or _IN_L.get(i.lower()) or i


def cn_tgt(t):
    t = str(t)
    return TGT_CN.get(t) or t


def cn_attr(k):
    """原始键名 → 中文名（先按别名归一到短名，再查表）。"""
    short = ATTR_ALIAS.get(k, k)
    return ATTR_CN.get(short) or ATTR_CN.get(k) or k


# ────────────────────────────── 数据装载 ──────────────────────────────
def load_name_map():
    """工坊 ID → 地图名。多个来源合并。"""
    m = {}
    for p, unpack in (
        ("_ghcrawl/_wsmap.json", lambda d: d.get("mapping") or {}),
        ("_ghcrawl/_workshop_maps.json", lambda d: d),
        ("_missing_ws_all.json", lambda d: d),
    ):
        fp = os.path.join(HERE, p)
        if not os.path.exists(fp):
            continue
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
        except Exception:                                     # noqa: BLE001
            continue
        try:
            d = unpack(d)
        except Exception:                                     # noqa: BLE001
            continue
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            if isinstance(v, dict):
                v = v.get("item")
            v = str(v)
            if v.isdigit():
                m.setdefault(v, k)
    return m


def load_ents(pid):
    p = os.path.join(ENTS, str(pid) + ".json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:                                         # noqa: BLE001
        return None


PLAYFUL_PREFIX = ("trigger_", "func_button", "func_rot_button", "func_door",
                  "func_movelinear", "func_breakable", "func_wall_toggle",
                  "func_physbox", "func_brush", "logic_", "math_",
                  "point_servercommand", "env_entity_maker", "point_teleport",
                  "env_fade", "game_text", "env_shake")


def is_point(e):
    return str(e.get("cn", "")).startswith(PLAYFUL_PREFIX)


def size_of(e):
    h = e.get("h")
    if isinstance(h, (list, tuple)) and len(h) >= 3:
        try:
            return [round(abs(float(x)) * 2, 1) for x in h[:3]]
        except Exception:                                     # noqa: BLE001
            return None
    return None


def build_stats(ents):
    all_c = Counter(str(e.get("cn")) for e in ents)
    points = [e for e in ents if is_point(e)]
    pc = Counter(str(e.get("cn")) for e in points)
    ncx = sum(len(e.get("cx") or []) for e in points)
    return all_c, points, pc, ncx


# ────────────────────────────── HTML ──────────────────────────────
CSS = """
*{box-sizing:border-box}
body{margin:0;font:14px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
     color:#2c2c2a;background:#f6f5f2}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:22px;font-weight:600;margin:0 0 4px}
h2{font-size:16px;font-weight:600;margin:30px 0 12px;padding-bottom:7px;
   border-bottom:1px solid #ddd9d0}
.sub{color:#5f5e5a;font-size:13px;margin-bottom:18px}
.hero{background:#fff;border:1px solid #e6e2d9;border-radius:12px;padding:18px 20px;margin-bottom:8px}
.kpis{display:flex;flex-wrap:wrap;gap:26px;margin-top:14px}
.kpi b{display:block;font-size:22px;font-weight:600;color:#26215c}
.kpi span{color:#5f5e5a;font-size:12px}
.dist{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.chip{background:#eef2f8;border:1px solid #d8e0ec;border-radius:999px;
      padding:3px 11px;font-size:12px;color:#33405c}
.chip i{font-style:normal;color:#1e2a44;font-weight:600;margin-left:5px}
.sec{background:#fff;border:1px solid #e6e2d9;border-radius:12px;margin-bottom:10px;overflow:hidden}
.hd{padding:12px 16px;cursor:pointer;display:flex;align-items:center;gap:10px;
    background:#fbfaf8;border-bottom:1px solid #eeebe3}
.hd:hover{background:#f4f2ed}
.hd .tag{font-size:11px;padding:2px 8px;border-radius:5px;background:#e3eef0;
         color:#0f6e56;font-weight:600;white-space:nowrap}
.hd .nm{font-weight:600;font-size:13px;color:#1f1f1e;word-break:break-all}
.hd .pos{margin-left:auto;color:#888780;font-size:12px;white-space:nowrap}
.bd{padding:0 16px 14px;display:none}
.sec.open .bd{display:block}
.kv{display:grid;grid-template-columns:118px 1fr;gap:2px 12px;font-size:12.5px;margin-top:10px}
.kv dt{color:#77756f;padding:3px 0;border-bottom:1px dashed #eeece6}
.kv dd{margin:0;padding:3px 0;border-bottom:1px dashed #eeece6;word-break:break-all}
.kv dd b{color:#1e2a44}
.cx{margin-top:12px}
.cx .cap{font-size:12px;color:#77756f;margin-bottom:6px}
.cx .row{font-size:12.5px;padding:6px 10px;background:#f7fbfa;border-left:3px solid #14b8a6;
         border-radius:0 6px 6px 0;margin-bottom:5px;word-break:break-all}
.cx .row .who{color:#0f6e56;font-weight:600}
.cx .row .ti{color:#26215c;font-weight:600}
.cx .row .dt{color:#a85d1a;margin-left:6px}
.cx .row .pr{color:#77756f}
.none{color:#888780;font-size:12.5px;padding:8px 0}
.legend{font-size:12px;color:#5f5e5a;background:#fffdf6;border:1px solid #f0e8d2;
        border-radius:10px;padding:12px 16px;margin-bottom:16px}
.legend b{color:#7a5a12}
.foot{margin-top:36px;padding-top:14px;border-top:1px solid #e2ded5;
      color:#888780;font-size:12px}
"""

JS = """
document.querySelectorAll('.hd').forEach(function(h){
  h.addEventListener('click',function(){ h.parentNode.classList.toggle('open'); });
});
document.querySelectorAll('.sec').forEach(function(s,i){ if(i<3) s.classList.add('open'); });
var all=document.getElementById('toggleAll');
if(all) all.addEventListener('click',function(){
  var open=all.dataset.on!=='1';
  document.querySelectorAll('.sec').forEach(function(s){ s.classList.toggle('open',open); });
  all.dataset.on=open?'1':'0'; all.textContent=open?'全部收起':'全部展开';
});
"""


def esc(s):
    return html.escape(str(s), quote=False)


_BOOL = {"true": "是", "false": "否"}


def fmt_val(v):
    """布尔值与数字的友好呈现。"""
    s = str(v)
    if s.lower() in _BOOL:
        return _BOOL[s.lower()]
    return s


def render_entity(e):
    c = str(e.get("cn"))
    nm = e.get("nm") or ""
    o = e.get("o") or [0, 0, 0]
    sz = size_of(e)
    try:
        pos = "%d, %d, %d" % (round(float(o[0])), round(float(o[1])), round(float(o[2])))
    except Exception:                                         # noqa: BLE001
        pos = "—"

    label = cn_cls(c) or ""
    tag = label if label else c

    h = ['<div class="sec">']
    h.append('<div class="hd"><span class="tag">%s</span><span class="nm">%s</span>'
             '<span class="pos">%s</span></div>'
             % (esc(tag), esc(nm if nm else c), esc(pos)))
    h.append('<div class="bd">')

    rows = [("类名", c), ("名称", nm if nm else "（无）"), ("坐标", pos)]
    if sz:
        rows.append(("判定尺寸", "%s × %s × %s" % (sz[0], sz[1], sz[2])))
    desc = CLS_CN.get(c)
    if desc and desc[1]:
        rows.append(("作用", desc[1]))
    h.append('<dl class="kv">')
    for k, v in rows:
        h.append("<dt>%s</dt><dd>%s</dd>" % (esc(k), esc(v)))
    h.append("</dl>")

    kv = e.get("kv") or {}
    if kv:
        h.append('<dl class="kv">')
        for k, v in kv.items():
            h.append("<dt>%s</dt><dd><b>%s</b> <span style='color:#a09e98'>%s</span></dd>"
                     % (esc(cn_attr(k)), esc(fmt_val(v)), esc(k)))
        h.append("</dl>")

    cx = e.get("cx") or []
    if cx:
        h.append('<div class="cx"><div class="cap">触发连接 %d 条</div>' % len(cx))
        for k in cx:
            parts = ['<span class="who">%s</span>' % esc(cn_out(k.get("o"))),
                     ' → <span class="ti">%s</span>' % esc(cn_tgt(k.get("t") or "—")),
                     ' : %s' % esc(cn_in(k.get("i")))]
            p = k.get("p")
            if p not in (None, "", "0"):
                parts.append(' <span class="pr">（%s）</span>' % esc(p))
            d = k.get("d")
            if d not in (None, "", 0, "0"):
                parts.append(' <span class="dt">延迟 %ss</span>' % esc(d))
            h.append('<div class="row">%s</div>' % "".join(parts))
        h.append("</div>")
    elif not kv:
        h.append('<div class="none">该实体无附加属性 / 触发连接</div>')

    h.append("</div></div>")
    return "".join(h)


def render_map(name, pid, ents):
    all_c, points, pc, ncx = build_stats(ents)
    cn_name = ""
    lib = os.path.join(HERE, "data", "exg_mapnames.json")
    if os.path.exists(lib):
        try:
            cn_name = (json.load(io.open(lib, encoding="utf-8")) or {}).get(name, "")
        except Exception:                                     # noqa: BLE001
            pass

    out = ['<div class="hero">']
    out.append("<h1>%s</h1>" % esc(name))
    out.append('<div class="sub">%s工坊 ID %s · 共 %d 个实体</div>'
               % (("中文名：%s · " % cn_name) if cn_name else "", pid, len(ents)))
    out.append('<div class="kpis">')
    out.append('<div class="kpi"><b>%d</b><span>点位 / 机关实体</span></div>' % len(points))
    out.append('<div class="kpi"><b>%d</b><span>触发连接</span></div>' % ncx)
    out.append('<div class="kpi"><b>%d</b><span>触发区类</span></div>'
               % sum(1 for e in points if str(e.get("cn")).startswith("trigger_")))
    out.append('<div class="kpi"><b>%d</b><span>实体类名总数</span></div>' % len(all_c))
    out.append("</div>")

    top = pc.most_common(14)
    if top:
        out.append('<div class="dist">')
        for k, v in top:
            lab = cn_cls(k) or k
            out.append('<span class="chip">%s<i>%d</i></span>' % (esc(lab), v))
        out.append("</div>")
    out.append("</div>")

    # 分组渲染：触发区 → 机关/门 → 逻辑 → 其它点位
    def bucket(c):
        if c.startswith("trigger_"):
            return 0
        if c.startswith(("func_door", "func_button", "func_rot_button",
                         "func_movelinear", "func_breakable", "func_physbox",
                         "func_wall_toggle", "func_brush")):
            return 1
        if c.startswith(("logic_", "math_")):
            return 2
        return 3

    order = ["触发区 / 危险区", "机关 · 门 · 可破坏物", "逻辑 / 定时 / 计数", "其它点位"]
    grouped = defaultdict(list)
    for e in points:
        grouped[bucket(str(e.get("cn")))].append(e)

    out.append('<div class="legend">'
               "<b>怎么看这份报告：</b>「点位」是从地图文件里直接读出的实体，"
               "不依赖游戏运行。每条含<b>坐标</b>（游戏内 world 坐标，X/Y/Z）、"
               "<b>判定尺寸</b>（触发范围，单位约等于厘米）、"
               "<b>属性</b>与<b>触发连接</b>（谁触发 → 触发谁 → 干什么）。"
               "数值旁的灰色小字是官方原始键名，方便对照 cfg / 控制台。"
               "</div>")

    for i, title in enumerate(order):
        items = grouped.get(i) or []
        if not items:
            continue
        out.append("<h2>%s <span style='font-weight:400;color:#888780;font-size:13px'>"
                   "（%d）</span></h2>" % (esc(title), len(items)))
        items.sort(key=lambda e: (str(e.get("cn")), str(e.get("nm") or "")))
        for e in items:
            out.append(render_entity(e))
    return "".join(out)


def page(title, body):
    return ("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>%s</title><style>%s</style></head><body><div class=\"wrap\">"
            "%s<div class=\"foot\">数据来源：CS2 地图 VPK 的 entity lump（离线解析）· "
            "由云朵小铺实体提取管线产出</div></div><script>%s</script></body></html>"
            % (esc(title), CSS, body, JS))


def main():
    args = sys.argv[1:]
    names = load_name_map()
    rev = {}
    for pid, nm in names.items():
        rev.setdefault(nm, pid)

    want = []
    if "--all-ids" in args:
        want = [(names.get(a, a), a) for a in args[args.index("--all-ids") + 1:]]
    elif "--top" in args:
        n = int(args[args.index("--top") + 1])
        cand = []
        for f in os.listdir(ENTS):
            if not f.endswith(".json"):
                continue
            pid = f[:-5]
            try:
                d = json.load(io.open(os.path.join(ENTS, f), encoding="utf-8"))
            except Exception:                                 # noqa: BLE001
                continue
            if not d or not any(e.get("kv") or e.get("cx") for e in d):
                continue
            cand.append((sum(1 for e in d if str(e.get("cn", "")).startswith("trigger_")),
                         pid))
        cand.sort(reverse=True)
        want = [(names.get(p, p), p) for _, p in cand[:n]]
    else:
        for a in args:
            if a.startswith("--"):
                continue
            pid = rev.get(a) or (a if a.isdigit() else None)
            if not pid:
                print("跳过（找不到工坊 ID）：%s" % a)
                continue
            want.append((names.get(pid, a), pid))

    if not want:
        print("用法：python _build_trigger_report.py ze_mota ze_devil_may_cry")
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    made = []
    for nm, pid in want:
        ents = load_ents(pid)
        if not ents:
            print("缺数据：%s (%s)" % (nm, pid))
            continue
        body = render_map(nm, pid, ents)
        fp = os.path.join(OUT_DIR, "%s-点位触发.html" % nm)
        io.open(fp, "w", encoding="utf-8").write(
            page("%s 点位与触发" % nm, body))
        made.append((nm, pid, len(ents), os.path.getsize(fp)))
        print("✔ %-34s pid=%-12s 实体 %5d  → %s (%.0f KB)"
              % (nm, pid, len(ents), os.path.basename(fp),
                 os.path.getsize(fp) / 1024))

    if made:
        # 索引页
        li = "".join('<li><a href="%s-点位触发.html">%s</a> · %d 实体</li>'
                     % (esc(n), esc(n), c) for n, _, c, _ in made)
        io.open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(
            page("点位触发报告索引", "<h1>点位触发报告</h1><ul>%s</ul>" % li))
        print("\n输出目录：%s" % OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())

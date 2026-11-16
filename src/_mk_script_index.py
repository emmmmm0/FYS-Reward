# 一次性脚本：扫描 fys-reward/_*.py 与 fys-reward/tools/tests/_*.py，
# 按前缀分类 + 抽取首个 docstring 生成脚本索引
import glob, os, re, io

root = os.path.dirname(os.path.abspath(__file__))
# ⑪ 测试归位（v2.15）：回归/探针脚本搬到 tools/tests/，索引两处一起扫
files = sorted(glob.glob(os.path.join(root, '_*.py'))
               + glob.glob(os.path.join(root, 'tools', 'tests', '_*.py')))

def first_doc(path):
    try:
        src = io.open(path, encoding='utf-8', errors='replace').read(4000)
    except OSError:
        return ''
    m = re.search(r'"""(.*?)"""', src, re.S) or re.search(r"'''(.*?)'''", src, re.S)
    if not m:
        # 退而求其次：# 注释头
        lines = [l.lstrip('# ').strip() for l in src.splitlines()[:8]
                 if l.strip().startswith('#')]
        return lines[0][:110] if lines else ''
    txt = ' '.join(m.group(1).split())
    return txt[:110]


def ports_of(path):
    """脚本占用的本地端口（PORT / CDP 常量）。

    端口登记以前散在记忆文件里，新脚本随手挑一个号就可能和别的用例撞车
    （两个用例抢同一端口 → 后起的静默连到前一个实例上，假失败很难查）。
    这里从源码扫出来集中登记，重号会在索引里直接标出来（v2.14 结构⑧）。
    """
    try:
        src = io.open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return []
    got = set()
    for m in re.finditer(r'^\s*(PORT|CDP|CDP_PORT|DEBUG_PORT)\s*=\s*(\d{4,5})\b',
                         src, re.M):
        got.add((m.group(1), int(m.group(2))))
    return sorted(got, key=lambda x: (x[1], x[0]))

GROUPS = [
    ('_e2e_',   '端到端回归（起真实应用/接口，跑完即退出）'),
    ('_probe_', '探针（起服务后常驻观察，测试时手动停）'),
    ('_cdp_',   'CDP / Edge 界面巡检（截图、点按、样式核对）'),
    ('_shot_',  '截图生成（给人看的验证图）'),
    ('_dbg_|_diag|_audit|_cmp_|_check_|_bg_', '调试 / 一次性诊断（历史排查用，未必还能跑）'),
    ('_build_|_mk|_gen|_mock|_snap|_add_|_refetch', '资产 / 数据构建（生成封面、贴纸、实体提取等）'),
]
OTHER = '其他工具'

out = io.open(os.path.join(root, 'tools', 'README.md'), 'w', encoding='utf-8')
out.write('# fys-reward 脚本索引\n\n')
out.write('> 自动生成：`python _mk_script_index.py`（改完脚本后重跑即可刷新）。\n')
out.write('> 脚本在仓库根目录与 `tools/tests/`（回归/探针，v2.15 归位）两处；'
          '很多脚本按 cwd 相对路径读写 `data/`，跑的时候在项目根执行。\n\n')

# ── 端口登记表（从源码扫，比手写清单可靠）──
pmap = {}
for f in files:
    for _k, port in ports_of(f):
        pmap.setdefault(port, []).append(os.path.basename(f))
out.write('## 端口登记（自动扫描 `PORT` / `CDP` 常量）\n\n')
out.write('新脚本挑端口前先看这张表，别撞已在用的号（撞了会静默连到别的实例，'
          '表现为莫名其妙的假失败）。\n\n')
out.write('| 端口 | 使用脚本 |\n|---|---|\n')
for port in sorted(pmap):
    users = sorted(set(pmap[port]))
    mark = ' ⚠ 重号' if len(users) > 1 else ''
    out.write('| %d%s | %s |\n' % (port, mark, '、'.join('`%s`' % u for u in users)))
out.write('\n')

buckets = {g[1]: [] for g in GROUPS}
buckets[OTHER] = []
for f in files:
    name = os.path.relpath(f, root).replace('\\', '/')
    for pref, label in GROUPS:
        if any(os.path.basename(name).startswith(x.rstrip('|_')) or re.search(x, os.path.basename(name)) for x in pref.split('|')):
            buckets[label].append(name)
            break
    else:
        buckets[OTHER].append(name)

order = [g[1] for g in GROUPS] + [OTHER]
for label in order:
    names = buckets.get(label) or []
    if not names:
        continue
    out.write('## %s（%d 个）\n\n' % (label, len(names)))
    out.write('| 脚本 | 说明 |\n|---|---|\n')
    for n in names:
        d = first_doc(os.path.join(root, n)).replace('|', '\\|')
        out.write('| `%s` | %s |\n' % (n, d))
    out.write('\n')
out.close()
total = sum(len(v) for v in buckets.values())
print('indexed', total, 'scripts ->', os.path.join(root, 'tools', 'README.md'))

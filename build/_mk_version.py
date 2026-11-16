# -*- coding: utf-8 -*-
"""从 fys_reward_app.py 的 CHANGELOG[0] 生成 version.json（包目录 + 工作区根各一份）。

build_dist.py 不生成 version.json，发布前必须手写；本脚本把手写这步自动化，
保证 notes 与更新日志一字不差、sha256/size 与实际发行 exe 一致。

用法（在工作区根）：python fys-reward/_mk_version.py
"""
import ast
import hashlib
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP_PY = os.path.join(HERE, "fys_reward_app.py")
PKG_DIR = os.path.join(ROOT, "云朵小铺-FYS通关奖励看板")
EXE = os.path.join(PKG_DIR, "FYS-Reward.exe")

_CLG = {"CLG_NEW": "新增", "CLG_IMP": "优化", "CLG_FIX": "修复", "CLG_REM": "移除"}


class _FixName(ast.NodeTransformer):
    """把 CLG_NEW/CLG_FIX… 这些变量名换回字面量，好让 literal_eval 吃得下。"""

    def visit_Name(self, node):
        if node.id in _CLG:
            return ast.copy_location(ast.Constant(value=_CLG[node.id]), node)
        return node


def main():
    src = io.open(APP_PY, encoding="utf-8").read()
    tree = ast.parse(src)
    node = None
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "CHANGELOG"
                                             for t in n.targets):
            node = n
            break
    if node is None:
        raise SystemExit("在 %s 里找不到 CHANGELOG" % APP_PY)
    val = ast.literal_eval(_FixName().visit(node.value))
    top = val[0]
    notes = []
    for g in top.get("groups") or []:
        notes.extend(g.get("items") or [])
    b = open(EXE, "rb").read()
    ver = top["ver"]
    name = "FYS-Reward-%s.exe" % ver
    # 下载地址（update_apply 逐个试，每个地址 2 次）：
    #   gh-proxy 走 Release 资产实测最快（6.9MB/3.7s）→ jsDelivr → raw → ghproxy → 原件
    rel_url = "https://github.com/emmmmm0/FYS-Reward/releases/download/%s/%s" % (ver, name)
    urls = [
        "https://gh-proxy.com/" + rel_url,
        "https://cdn.jsdelivr.net/gh/emmmmm0/FYS-Reward@main/dist/%s" % name,
        "https://raw.githubusercontent.com/emmmmm0/FYS-Reward/main/dist/%s" % name,
        "https://ghproxy.net/" + rel_url,
        rel_url,
    ]
    data = {"ver": ver, "date": top.get("date", ""), "size": len(b),
            "file": name, "urls": urls,
            "sha256": hashlib.sha256(b).hexdigest(), "notes": notes}
    txt = json.dumps(data, ensure_ascii=False, indent=1)
    outs = [os.path.join(ROOT, "version.json"), os.path.join(PKG_DIR, "version.json")]
    for p in outs:
        io.open(p, "w", encoding="utf-8").write(txt)
    print("ver=%s size=%d notes=%d" % (data["ver"], data["size"], len(notes)))
    print("sha256=%s" % data["sha256"])
    print("exe=%s" % EXE)
    for p in outs:
        print("写了 %s" % p)


if __name__ == "__main__":
    main()

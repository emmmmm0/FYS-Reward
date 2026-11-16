# -*- coding: utf-8 -*-
"""把本地一个目录树推到 GitHub 仓库（创建仓库 / 增量上传文件）。

用途：本项目的源码仓库（src/ + build/ + update/ + dist/）没有本地 git 历史依赖，
直接走 contents API 上传最省事；不要求装 git，也不受 github.com 的 TLS 问题影响
（api.github.com 可用即可）。

用法：
    set GITHUB_TOKEN=ghp_xxx
    python _gh_push_tree.py --repo emmmmm0/FYS-Reward --dir ..\\_gh_repo --create-repo
    python _gh_push_tree.py --repo emmmmm0/FYS-Reward --dir ..\\_gh_repo --dry-run
    python _gh_push_tree.py ... --pin-ip 20.205.243.168    # 域名解析异常时钉 IP

⚠ 单文件 <100MB（exe 6.8MB / version.json 几百字节，够用）；dist 里的 exe 也要 <20MB，
  否则 jsDelivr 不直出（更新下载会退到 ghproxy/raw）。
"""
import argparse
import base64
import concurrent.futures
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def pin_host(host, ip):
    if not ip:
        return
    orig = socket.getaddrinfo

    def ga(h, *a, **kw):
        return orig(ip if h == host else h, *a, **kw)

    socket.getaddrinfo = ga
    print("  (已把 %s 钉到 %s)" % (host, ip))


def req(method, url, token, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "fys-push",
        "Content-Type": "application/json",
    })
    try:
        with OPENER.open(r, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw.decode("utf-8")) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode("utf-8"))
        except Exception:                                     # noqa: BLE001
            return e.code, {"message": raw[:160].decode("utf-8", "replace")}


def remote_tree(repo, branch, token):
    """远端文件 {path: sha}（一次递归拿全）。仓库空/不存在返回 {}。"""
    code, d = req("GET", "%s/repos/%s/git/trees/%s?recursive=1" % (API, repo, branch), token)
    if code != 200 or not isinstance(d, dict):
        return {}
    return {it["path"]: it.get("sha") for it in d.get("tree", []) if it.get("type") == "blob"}


def put(repo, branch, token, path, blob, sha=None, retries=4):
    # 路径里可能有中文文件名 → 必须百分号编码（否则 http.client 直接 UnicodeEncodeError）
    url = "%s/repos/%s/contents/%s" % (API, repo, urllib.parse.quote(path, safe="/"))
    content = base64.b64encode(blob).decode("ascii")
    cur = sha
    for i in range(retries):
        body = {"message": "update %s" % path, "branch": branch, "content": content}
        if cur:
            body["sha"] = cur
        # base64 后体积约为原文件 1.37 倍；大文件（如 14MB 的预览壳）用 60s 会超时
        # （GitHub 侧报 403 "The rule did not run because of a timeout"）→ 按体积放宽。
        to = 60 + int(len(blob) / 1048576.0 * 10)
        code, d = req("PUT", url, token, body, timeout=to)
        if code in (200, 201):
            return True, None
        if code in (409, 422):
            code2, d2 = req("GET", url + "?ref=" + branch, token)
            cur = d2.get("sha") if code2 == 200 and isinstance(d2, dict) else None
            time.sleep(0.4 * (i + 1))
            continue
        return False, "HTTP %s %s" % (code, (d or {}).get("message"))
    return False, "重试耗尽"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--dir", required=True, help="本地目录（不含 .git）")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--create-repo", action="store_true")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--pin-ip", default="")
    args = ap.parse_args()

    pin_host("api.github.com", args.pin_ip)
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        # 用户要求长期保存凭据（每次走设备授权太麻烦）：读用户级隐藏文件。
        # 位置在 ~/.workbuddy/.fys_gh_token，不进任何仓库、不随项目同步。
        _p = os.path.join(os.path.expanduser("~"), ".workbuddy", ".fys_gh_token")
        try:
            with open(_p, encoding="utf-8") as _fh:
                token = _fh.read().strip()
        except OSError:
            pass
    if not token and not args.dry_run:
        print("缺少 GITHUB_TOKEN（也没有 ~/.workbuddy/.fys_gh_token）")
        return 2
    root = os.path.abspath(args.dir)
    if not os.path.isdir(root):
        print("目录不存在:", root)
        return 2

    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in (".git", "__pycache__")]
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            files.append((rel, p))
    total = sum(os.path.getsize(p) for _r, p in files)
    print("本地 %d 个文件，合计 %.1f MB" % (len(files), total / 1048576.0))

    if args.create_repo and not args.dry_run:
        code, d = req("GET", "%s/repos/%s" % (API, args.repo), token)
        if code == 404:
            owner, name = args.repo.split("/")
            code2, d2 = req("POST", "%s/user/repos" % API, token,
                            {"name": name, "private": bool(args.private),
                             "description": "云朵小铺 · FYS ZE 通关奖励看板（源码 + 更新清单）",
                             "auto_init": True})
            print("建仓库:", code2, (d2 or {}).get("full_name") or (d2 or {}).get("message"))
            if code2 not in (200, 201):
                return 2
            time.sleep(2)
        elif code == 200:
            print("仓库已存在:", (d or {}).get("full_name"))

    remote = {} if args.dry_run else remote_tree(args.repo, args.branch, token)
    todo = []
    for rel, p in files:
        with open(p, "rb") as fh:
            blob = fh.read()
        if remote.get(rel) and args.dry_run:
            continue
        todo.append((rel, blob, remote.get(rel)))
    print("待上传 %d 个（%.1f MB）" % (len(todo), sum(len(b) for _r, b, _s in todo) / 1048576.0))
    if args.dry_run:
        for rel, blob, _s in todo[:12]:
            print("  -", rel, "%.0f KB" % (len(blob) / 1024.0))
        return 0

    ok = fail = 0
    t0 = time.time()
    done = [0]

    def one(item):
        rel, blob, sha = item
        return rel, put(args.repo, args.branch, token, rel, blob, sha)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for rel, (good, err) in ex.map(one, todo):
            done[0] += 1
            if good:
                ok += 1
            else:
                fail += 1
                print("  ! %s 失败：%s" % (rel, err))
            if done[0] % 20 == 0 or done[0] == len(todo):
                print("  %d/%d（成功 %d 失败 %d，%.0fs）"
                      % (done[0], len(todo), ok, fail, time.time() - t0))
    print("\n仓库地址：https://github.com/%s" % args.repo)
    print("更新清单：https://cdn.jsdelivr.net/gh/%s@%s/update/version.json" % (args.repo, args.branch))
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())

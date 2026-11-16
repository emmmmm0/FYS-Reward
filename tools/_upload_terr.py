# -*- coding: utf-8 -*-
"""把地形分包（terr/*.bin）上传到 GitHub 仓库（供软件按需单文件下载）。

为什么需要它：2026-11-15 起安装包不再带 terr\\（284MB），玩家第一次点开某张图的
3D 预览时，客户端按「基础地址 + /<工坊ID>.bin」单文件拉取并缓存。这个脚本负责把
本地生成好的分包推上托管，并写一份 index.json 方便核对。

用法（token 只需一次，存环境变量即可）：
    set GITHUB_TOKEN=ghp_xxx
    python _upload_terr.py --repo yourname/fys-terr --branch main
    python _upload_terr.py --repo yourname/fys-terr --dry-run        # 只看差异不传
    python _upload_terr.py --repo yourname/fys-terr --only-missing   # 只补远端没有的
    python _upload_terr.py --repo yourname/fys-terr --verify         # 抽 3 个走 raw 下载核对

上传完成后，软件端的 data\\terr_cdn.txt 写一行：
    https://raw.githubusercontent.com/yourname/fys-terr/main/terr
（或在系统环境变量里设 FYS_TERR_CDN，优先级更高）

⚠ 仓库必须是**公开**的：客户端是匿名 raw 下载，私有仓库要带 token 才能读，
  把 token 塞进客户端等于公开密钥，不要这么做。
⚠ GitHub Contents API：单文件 <100MB（我们最大 0.7MB）、单目录建议 <1000 个文件
  （我们 858 个，一次列目录拿得全）；超 1000 张时按 800 一组分目录并同步改客户端
  的地址模板。
"""
import argparse
import base64
import concurrent.futures
import socket
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERR_DIR = os.path.join(HERE, "terr")
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def pin_host(host, ip):
    """把某个域名钉到指定 IP（TLS SNI / 证书校验仍按域名来）。

    为什么需要：这台机器上 api.github.com 域名解析过去会「连接被拒」，
    但直连它的 IPv4 是通的（curl --resolve 实测 200）。钉 IP 后 urllib 恢复正常。
    """
    if not ip:
        return
    orig = socket.getaddrinfo

    def ga(h, *a, **kw):
        return orig(ip if h == host else h, *a, **kw)

    socket.getaddrinfo = ga
    print("  (已把 %s 钉到 %s)" % (host, ip))


def req(method, url, token, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "fys-terr-uploader",
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
            return e.code, {"message": raw[:200].decode("utf-8", "replace")}


def list_remote(repo, branch, token, path="terr"):
    """远端目录清单 {文件名: {sha,size}}（一次拿 1000 个，我们 858 个够）。"""
    url = "%s/repos/%s/contents/%s?ref=%s" % (API, repo, path, branch)
    code, data = req("GET", url, token)
    if code == 404:
        return {}
    if code != 200 or not isinstance(data, list):
        print("  ! 列远端失败 HTTP %s %s" % (code, (data or {}).get("message")))
        return None
    out = {}
    for it in data:
        if it.get("type") == "file" and it.get("name", "").endswith(".bin"):
            out[it["name"]] = {"sha": it.get("sha"), "size": it.get("size")}
    return out


def put_file(repo, branch, token, name, blob, sha=None, retries=5):
    """上传单个文件。

    ⚠ 并发 PUT 同一个分支时，GitHub contents API 会返回
      `409 <当前文件 sha> is at <分支头> but expected <我们给的 sha>` —— 意思是
      「你拿的底稿已经过期」，必须**重新取一次当前文件的 sha** 再提交，光重试同样的
      请求永远失败（实测 194 个全卡在这里）。所以每次冲突都重新 GET 一遍。
    """
    url = "%s/repos/%s/contents/terr/%s" % (API, repo, name)
    content = base64.b64encode(blob).decode("ascii")
    cur = sha
    for i in range(retries):
        body = {"message": "terr: %s" % name, "branch": branch, "content": content}
        if cur:
            body["sha"] = cur
        code, data = req("PUT", url, token, body)
        if code in (200, 201):
            return True, None
        if code in (409, 422):
            code2, d2 = req("GET", url + "?ref=" + branch, token)
            if code2 == 200 and isinstance(d2, dict):
                cur = d2.get("sha")
            else:
                cur = None
            time.sleep(min(3.0, 0.4 * (i + 1)))
            continue
        return False, "HTTP %s %s" % (code, (data or {}).get("message"))
    return False, "重试耗尽（并发冲突）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name（必须公开）")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dir", default=TERR_DIR, help="本地 terr 目录")
    ap.add_argument("--token-env", default="GITHUB_TOKEN")
    ap.add_argument("--only-missing", action="store_true", help="只传远端没有的")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="抽 3 个走 raw 下载核对字节数")
    ap.add_argument("--jobs", type=int, default=4, help="并发上传数（默认 4；太高会 409）")
    ap.add_argument("--create-repo", action="store_true",
                    help="仓库还不存在就先建一个公开仓库（需要 token 有 repo 权限）")
    ap.add_argument("--private", action="store_true", help="建私有仓库（客户端读不到，慎用）")
    ap.add_argument("--pin-ip", default="", help="把 api.github.com 钉到指定 IPv4（域名连不上时用）")
    args = ap.parse_args()

    pin_host("api.github.com", args.pin_ip)
    token = os.environ.get(args.token_env, "").strip()
    if not token and not args.dry_run:
        print("缺少 token：set %s=ghp_xxx" % args.token_env)
        return 2
    if not os.path.isdir(args.dir):
        print("找不到地形目录：%s" % args.dir)
        return 2

    local = {f: os.path.join(args.dir, f) for f in os.listdir(args.dir)
             if f.endswith(".bin")}
    if not local:
        print("目录里没有 .bin：%s" % args.dir)
        return 2
    print("本地分包 %d 个，合计 %.1f MB" %
          (len(local), sum(os.path.getsize(p) for p in local.values()) / 1048576.0))

    if args.create_repo and not args.dry_run:
        code, data = req("GET", "%s/repos/%s" % (API, args.repo), token)
        if code == 404:
            owner = args.repo.split("/")[0]
            name = args.repo.split("/")[1]
            code2, d2 = req("POST", "%s/user/repos" % API, token,
                            {"name": name, "private": bool(args.private),
                             "description": "FYS 通关看板 · 地形分包（3D 预览按需下载）",
                             "auto_init": True})
            if code2 in (200, 201):
                print("已创建仓库 %s（%s）" % (args.repo, "私有" if args.private else "公开"))
                time.sleep(1.5)                     # 等 GitHub 初始化默认分支
            else:
                print("建仓库失败 HTTP %s %s" % (code2, (d2 or {}).get("message")))
                return 2
        elif code == 200:
            print("仓库已存在：%s" % args.repo)
        else:
            print("查仓库失败 HTTP %s %s" % (code, (data or {}).get("message")))
            return 2

    remote = list_remote(args.repo, args.branch, token) if not args.dry_run else {}
    if remote is None:
        return 1
    if remote:
        print("远端已有 %d 个" % len(remote))

    todo = []
    for name, path in sorted(local.items()):
        size = os.path.getsize(path)
        r = (remote or {}).get(name)
        if r and r.get("size") == size:
            continue
        if args.only_missing and r:
            continue
        todo.append((name, path, size, r.get("sha") if r else None))
    print("需要上传 %d 个（%.1f MB）" % (len(todo), sum(t[2] for t in todo) / 1048576.0))
    if args.dry_run:
        for n, _p, s, _sha in todo[:20]:
            print("  -", n, "%.0f KB" % (s / 1024.0))
        if len(todo) > 20:
            print("  … 其余 %d 个" % (len(todo) - 20))
        return 0

    ok = fail = 0
    t0 = time.time()
    done = [0]

    def _one(item):
        name, path, size, sha = item
        with open(path, "rb") as fh:
            blob = fh.read()
        return name, put_file(args.repo, args.branch, token, name, blob, sha)

    # 并发 6：858 个文件串行要 20 分钟，6 并发约 4 分钟（API 限额 5000/h 够用）
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for name, (good, err) in ex.map(_one, todo):
            done[0] += 1
            if good:
                ok += 1
            else:
                fail += 1
                print("  ! %s 失败：%s" % (name, err))
            if done[0] % 20 == 0 or done[0] == len(todo):
                print("  %d/%d（成功 %d 失败 %d，%.0fs）"
                      % (done[0], len(todo), ok, fail, time.time() - t0))

    # 索引（客户端不用它，但人工核对/将来做增量清单方便）
    idx = {"count": len(local), "files": {n: os.path.getsize(p) for n, p in sorted(local.items())}}
    body = json.dumps(idx, ensure_ascii=False, indent=1).encode("utf-8")
    code, data = req("PUT", "%s/repos/%s/contents/terr/index.json" % (API, args.repo), token,
                     {"message": "terr: index", "branch": args.branch,
                      "content": base64.b64encode(body).decode("ascii")})
    print("索引 index.json 上传：%s" % ("成功" if code in (200, 201) else "失败 HTTP %s" % code))

    if args.verify:
        base = "%s/%s/%s/terr" % (RAW, args.repo, args.branch)
        print("\n抽查 raw 可下载性：")
        for name in sorted(local)[:3]:
            url = "%s/%s" % (base, name)
            try:
                t = time.time()
                with OPENER.open(urllib.request.Request(url, headers={"User-Agent": "x"}),
                                 timeout=25) as r:
                    n = len(r.read())
                print("  OK %s %d 字节 %.1fs" % (name, n, time.time() - t))
            except Exception as e:                            # noqa: BLE001
                print("  FAIL %s %r" % (name, e))

    print("\n客户端把这一行写进 data\\terr_cdn.txt：")
    print("  %s/%s/%s/terr" % (RAW, args.repo, args.branch))
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())

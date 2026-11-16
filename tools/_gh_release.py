# -*- coding: utf-8 -*-
"""在 GitHub Releases 发布一个版本（建 tag + 传 zip/exe 资产）。

用法（在工作区根）：
    python fys-reward/tools/_gh_release.py --repo emmmmm0/FYS-Reward --ver v2.16 \
        --zip 云朵小铺-FYS通关奖励看板.zip --exe _gh_repo/dist/FYS-Reward-v2.16.exe

凭据：GITHUB_TOKEN 环境变量，或 ~/.workbuddy/.fys_gh_token（长期保存，不进仓库）。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
UPLOAD = "https://uploads.github.com"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def req(method, url, token, body=None, timeout=60, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "fys-release",
        "Content-Type": "application/octet-stream" if raw is not None else "application/json",
    })
    try:
        with OPENER.open(r, timeout=timeout) as resp:
            payload = resp.read()
            return resp.status, (json.loads(payload.decode()) if payload else None)
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, json.loads(payload.decode())
        except Exception:                                     # noqa: BLE001
            return e.code, {"message": payload[:200].decode("utf-8", "replace")}


def bullets(notes):
    """把 CHANGELOG 拆句的 notes 还原成条目：以 ** 开头的一条新 bullet，其余续行合并。"""
    out = []
    for ln in notes:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("**") or not out:
            out.append(s)
        else:
            out[-1] += s
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ver", required=True)
    ap.add_argument("--zip", default="")
    ap.add_argument("--exe", default="")
    ap.add_argument("--manifest", default="version.json")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        try:
            with open(os.path.join(os.path.expanduser("~"), ".workbuddy", ".fys_gh_token"),
                      encoding="utf-8") as fh:
                token = fh.read().strip()
        except OSError:
            pass
    if not token and not args.dry_run:
        print("缺少 token：GITHUB_TOKEN 或 ~/.workbuddy/.fys_gh_token")
        return 2

    meta = json.load(open(args.manifest, encoding="utf-8"))
    items = bullets(meta.get("notes") or [])
    body = ["## 云朵小铺 · FYS 通关奖励看板 %s" % args.ver, ""]
    body += ["- " + it for it in items]
    body += ["", "### 下载", "",
             "- `云朵小铺-FYS通关奖励看板.zip`：完整包（解压即用，免安装）",
             "- `%s`：单文件 exe，供软件内「设置 → 关于 → 检查更新」替换使用" % meta.get("file", ""),
             "", "> 首次使用请下 zip；已在旧版的用户可在软件内直接检查更新。"]
    body = "\n".join(body)

    if args.dry_run:
        print(body)
        return 0

    code, rel = req("POST", "%s/repos/%s/releases" % (API, args.repo), token, {
        "tag_name": args.ver, "target_commitish": "main",
        "name": "%s · %s" % (args.ver, "云朵小铺 FYS 通关奖励看板"),
        "body": body, "draft": bool(args.draft), "prerelease": False,
    }, timeout=90)
    if code not in (200, 201):
        print("建 Release 失败:", code, rel)
        return 1
    rid, up = rel["id"], rel["upload_url"].split("{")[0]
    print("Release 已建:", rel["html_url"])

    for p in (args.zip, args.exe):
        if not p:
            continue
        if not os.path.exists(p):
            print("  ! 找不到", p)
            continue
        name = os.path.basename(p)
        if name.lower().endswith(".zip"):
            name = "%s.zip" % args.ver           # ASCII 名，下载链接更稳
        blob = open(p, "rb").read()
        u = "%s?name=%s" % (up, urllib.parse.quote(name))
        print("  上传 %s（%.1f MB）…" % (name, len(blob) / 1048576.0))
        c2, a = req("POST", u, token, raw=blob, timeout=1800)
        print("   ", c2, (a or {}).get("state") or (a or {}).get("message"),
              ((a or {}).get("browser_download_url") or ""))
        if c2 not in (200, 201):
            return 1
    print("完成:", rel["html_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

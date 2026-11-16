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
    ap.add_argument("--zip2", default="",
                    help="第二个 zip 资产（全量版，2026-11-16 起发版两份 zip 并发）")
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
    if meta.get("intro"):
        body += [meta["intro"], ""]
    body += ["- " + it for it in items]
    def _mb(p):
        try:
            return "%.1f MB" % (os.path.getsize(p) / 1048576.0)
        except OSError:
            return ""

    # ⚠ 资产名必须写「上传后的名字」（脚本会重命名成 v2.16.zip / v2.16-full.zip），
    # 写本地文件名会让玩家在 Releases 页面找不到对应文件（2026-11-16 反馈）。
    zp, zf = _mb(args.zip), _mb(args.zip2)
    body += ["", "### 下载（两个包，按需选一个）", "",
             "- `%s.zip`%s：**精简版**（推荐）——解压即用。不含预览数据，"
             "首次点开「地图实体预览」自动下载约 14.7MB，地形点开哪张下哪张"
             % (args.ver, "（%s）" % zp if zp else ""),
             "- `%s-full.zip`%s：**全量版**——预览页与全部 858 张地形已内置，"
             "断网也能看 3D，代价是体积大得多"
             % (args.ver, "（%s）" % zf if zf else ""),
             "", "> 首次使用推荐精简版；想完全离线再下全量版；已在旧版的用户可在"
             "软件内「设置 → 关于 → 检查更新」直接升级，不必手动下载。"]
    body = "\n".join(body)

    if args.dry_run:
        print(body)
        return 0

    # 重发同版本是常态（v2.16 一天内多次替换资产）：tag/Release 已存在时复用，
    # 先 PATCH 正文，再删同名资产重传——否则 POST 会 422 already_exists。
    rel = None
    code, cur = req("GET", "%s/repos/%s/releases/tags/%s" % (API, args.repo, args.ver),
                    token, timeout=60)
    if code == 200 and cur:
        rid = cur["id"]
        c2, rel = req("PATCH", "%s/repos/%s/releases/%d" % (API, args.repo, rid), token, {
            "name": "%s · %s" % (args.ver, "云朵小铺 FYS 通关奖励看板"),
            "body": body, "draft": bool(args.draft), "prerelease": False,
        }, timeout=90)
        if c2 not in (200, 201):
            print("更新 Release 失败:", c2, rel)
            return 1
        print("Release 已存在 → 正文已更新:", rel["html_url"])
    else:
        code, rel = req("POST", "%s/repos/%s/releases" % (API, args.repo), token, {
            "tag_name": args.ver, "target_commitish": "main",
            "name": "%s · %s" % (args.ver, "云朵小铺 FYS 通关奖励看板"),
            "body": body, "draft": bool(args.draft), "prerelease": False,
        }, timeout=90)
        if code not in (200, 201):
            print("建 Release 失败:", code, rel)
            return 1
        print("Release 已建:", rel["html_url"])
    rid, up = rel["id"], rel["upload_url"].split("{")[0]

    def asset_name(p):
        name = os.path.basename(p)
        if name.lower().endswith(".zip"):
            name = ("%s-full.zip" % args.ver) if "-全量版" in name else ("%s.zip" % args.ver)
        return name

    want = {asset_name(p) for p in (args.zip, args.zip2, args.exe) if p}
    c3, assets = req("GET", "%s/repos/%s/releases/%d/assets" % (API, args.repo, rid),
                     token, timeout=60)
    for a in (assets or []):
        if a.get("name") in want:              # 同名先删，否则上传 422 already_exists
            c4, _ = req("DELETE", "%s/repos/%s/releases/assets/%d"
                        % (API, args.repo, a["id"]), token, timeout=60)
            print("  旧资产 %s 已删（%s）" % (a["name"], c4))

    for p in (args.zip, args.zip2, args.exe):
        if not p:
            continue
        if not os.path.exists(p):
            print("  ! 找不到", p)
            continue
        name = asset_name(p)
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

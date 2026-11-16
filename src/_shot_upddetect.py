# -*- coding: utf-8 -*-
"""数据更新提醒功能实拍：预置真实变更 → 主页横幅 / 明细弹窗 / 关卡角标三连拍。
用法：python _shot_upddetect.py（自起自停应用与 Edge）
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PORT = 8798
BASE = "http://127.0.0.1:%d" % PORT
PY = (r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe")
W = os.path.dirname(HERE)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = os.path.join(W, "验证截图-界面巡检", "_prof_updshot")
OUT = os.path.join(HERE, "_upddetect_shots")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
DIFF_PATH = os.path.join(HERE, "data", "repo_diff.json")

CRAFT = {
    "detected_at": "2026-09-27 12:00:00", "detected_ts": 1790000000.0,
    "seen": False, "first": False,
    "counts": {"new": 2, "edit": 2, "stage": 1, "zombie": 1, "param": 1,
               "del": 1, "total": 8},
    "groups": {
        "new": [{"map": "ze_test_newmap", "stages": 4, "mapcn": None},
                {"map": "ze_grand_atrium", "stages": 6, "mapcn": None}],
        "edit": [
            {"map": "ze_2012_p", "fields": [
                {"stage": 1, "k": "通关云点", "f": "rankPasses", "old": 100, "new": 120},
                {"stage": 1, "k": "伤害云点", "f": "rankDamage", "old": 20000, "new": 25000}]},
            {"map": "ze_backrooms_insomnia", "fields": [
                {"stage": 2, "k": "通关龙晶", "f": "econPasses", "old": 8, "new": 10}]}],
        "stage": [{"map": "ze_motel_v2", "old": 6, "new": 7, "added": [7], "removed": []}],
        "zombie": [{"map": "ze_2012_p", "fields": [
            {"k": "尸变模式", "f": "rand", "old": "按指数降序", "new": "纯随机"},
            {"k": "尸变比", "f": "ratio", "old": "1/6", "new": "1/4"}]}],
        "param": [{"map": "ze_obj_abyss_v2", "fields": [
            {"k": "伤害与金钱转化比例 (%)", "f": "ze_cash_damage_zombie",
             "old": "1.25", "new": "1.45"}]}],
        "del": [{"map": "ze_old_library"}],
    },
}


def ev(ws, expr):
    ws.send(json.dumps({"id": ev._i, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True}}))
    ev._i += 1
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == ev._i - 1:
            return r.get("result", {}).get("result", {}).get("value")


ev._i = 1


def shot(ws, fp):
    ws.send(json.dumps({"id": ev._i, "method": "Page.captureScreenshot",
                        "params": {"format": "png"}}))
    ev._i += 1
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == ev._i - 1:
            with open(fp, "wb") as fh:
                fh.write(base64.b64decode(r["result"]["data"]))
            print("saved", fp, os.path.getsize(fp))
            return


def main():
    os.makedirs(OUT, exist_ok=True)
    bak = DIFF_PATH + ".shot.bak"
    had = os.path.exists(DIFF_PATH)
    if had:
        shutil.copyfile(DIFF_PATH, bak)
    with open(DIFF_PATH, "w", encoding="utf-8") as fh:
        json.dump(CRAFT, fh, ensure_ascii=False)
    try:
        proc = subprocess.Popen(
            [PY, os.path.join(HERE, "fys_reward_app.py"), "--port", str(PORT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc2 = subprocess.Popen(
                [EDGE, "--headless=new", "--remote-debugging-port=9399",
                 "--remote-allow-origins=*", "--user-data-dir=" + PROFILE,
                 "--no-first-run", "--window-size=1440,900", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(60):
                    try:
                        OPENER.open(BASE + "/api/prefs", timeout=3).read()
                        break
                    except Exception:
                        time.sleep(0.5)
                tabs = json.load(OPENER.open("http://127.0.0.1:9399/json", timeout=2))
                ws_url = [t for t in tabs if t.get("type") == "page"][0][
                    "webSocketDebuggerUrl"]
                ws = websocket.create_connection(ws_url, timeout=60)
                ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
                ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
                ws.send(json.dumps({"id": 3, "method": "Page.navigate",
                                    "params": {"url": BASE + "/?noreadme=1"}}))
                for _ in range(80):
                    if ev(ws, "typeof tick==='function' && !!document.getElementById('grid')"):
                        break
                    time.sleep(0.25)
                for _ in range(40):
                    if ev(ws, "document.getElementById('updB') && "
                              "document.getElementById('updB').style.display!=='none'"):
                        break
                    time.sleep(0.25)
                time.sleep(0.6)
                shot(ws, os.path.join(OUT, "upd_banner.png"))
                ev(ws, "document.getElementById('updBView').click()")
                for _ in range(30):
                    if ev(ws, "document.querySelectorAll('#diffBody .dGrp').length>0"):
                        break
                    time.sleep(0.25)
                time.sleep(0.4)
                shot(ws, os.path.join(OUT, "upd_modal.png"))
                # 再滚到底，单独留一张「地图参数」分组的图（新增组在最下面）
                ev(ws, "(function(){var b=document.getElementById('diffBody');"
                       "if(b) b.scrollTop=b.scrollHeight; return 1})()")
                time.sleep(0.4)
                shot(ws, os.path.join(OUT, "upd_modal_param.png"))
                ev(ws, "closeDiff()")
                ev(ws, "openStages('ze_2012_p')")
                for _ in range(30):
                    if ev(ws, "document.querySelectorAll('#stgBody .updo').length>0"):
                        break
                    time.sleep(0.25)
                time.sleep(0.4)
                shot(ws, os.path.join(OUT, "upd_stage.png"))
            finally:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc2.pid)],
                               capture_output=True, timeout=10)
        finally:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=10)
    finally:
        if had:
            shutil.copyfile(bak, DIFF_PATH)
            os.remove(bak)
        elif os.path.exists(DIFF_PATH):
            os.remove(DIFF_PATH)


if __name__ == "__main__":
    main()

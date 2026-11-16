# -*- coding: utf-8 -*-
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:\Users\1\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
PORT = 8799
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
proc = subprocess.Popen([PY, os.path.join(HERE, "fys_reward_app.py"), "--port", str(PORT)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for i in range(80):
        try:
            op.open("http://127.0.0.1:%d/api/prefs" % PORT, timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    for wait in (0, 3, 6, 10, 15):
        time.sleep(wait if wait == 0 else 3)
        try:
            raw = op.open("http://127.0.0.1:%d/api/maplib" % PORT, timeout=90).read().decode("utf-8")
            d = json.loads(raw)
            print("t+%2ds ok=%s maps=%s error=%s" % (wait, d.get("ok"), len(d.get("maps") or []), str(d.get("error"))[:200]))
            if d.get("ok") and d.get("maps"):
                ms = d["maps"]
                print("   pv真=%d pv假=%d pv空=%d" % (
                    sum(1 for m in ms if m.get("pv") is True),
                    sum(1 for m in ms if m.get("pv") is False),
                    sum(1 for m in ms if m.get("pv") is None)))
                by = {m["f"]: m.get("pv") for m in ms}
                print("   ze_1_schizo=%s ze_2012_p=%s" % (by.get("ze_1_schizo"), by.get("ze_2012_p")))
                break
        except Exception as ex:
            print("t+%2ds ERR %r" % (wait, ex))
finally:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=10)

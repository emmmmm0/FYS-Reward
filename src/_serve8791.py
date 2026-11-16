# -*- coding: utf-8 -*-
"""把本机服务常驻在 8791（供 _cdp_preview_fix_test.py 等 CDP 脚本连）。"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fys_reward_app as A                                          # noqa: E402
import reward_server as engine                                      # noqa: E402

A.State.engine = engine
A.State.port = 8791
A.State.url = "http://127.0.0.1:8791/"
A.start_http_server(8791)
print("READY %s" % A.State.url, flush=True)
while True:
    time.sleep(3600)

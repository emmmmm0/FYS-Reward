# -*- coding: utf-8 -*-
"""常驻开发服务（无窗口）：给 CDP 回归脚本当靶子用。

   以前每次回归都靠 `fys_reward_app.py --browser`（会弹一个系统浏览器窗口），
   或者让每个测试脚本自己 import 起服务（端口各不同、无法复用）。
   这里起一个纯 HTTP 服务并常驻，端口固定，多个 CDP 脚本可以共用一个实例。

   用法：python _dev_server.py [port]        # 默认 8807，打印 READY 后常驻
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fys_reward_app as A          # noqa: E402
import reward_server as engine      # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8807

A.State.engine = engine
meta = engine.load_state(force="--force" in sys.argv)
A.State.port = PORT
A.State.url = "http://127.0.0.1:%d/" % PORT
A.start_http_server(PORT)
print("READY %s（地图 %s / 关卡 %s）" % (A.State.url, meta.get("maps"), meta.get("stages")),
      flush=True)
while True:
    time.sleep(3600)

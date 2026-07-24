"""内联运行器 v2：同进程组内用 subprocess 启动 Flask + 运行 v5 测试。

不依赖 setsid（沙箱中 setsid 分离的子进程会在前台命令结束后被回收）。
改用 subprocess.Popen（默认同进程组），由本前台命令统一持有；测试结束后再回收服务。
"""
import os
import sys
import time
import subprocess
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tests.test_full_v5 as T

HERE = os.path.dirname(os.path.abspath(__file__))
PY = '/root/.pyenv/versions/3.11.1/bin/python3.11'


def main():
    srv = subprocess.Popen(
        [PY, '-c', 'import app; app.app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)'],
        cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # 等待服务就绪
        ok = False
        for _ in range(40):
            try:
                urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=2)
                ok = True
                break
            except Exception:
                time.sleep(0.5)
        if not ok:
            print('✗ 服务未能启动')
            return 2
        # 运行测试
        T.main()
        print(f"\n>>> INLINE RESULT: PASS={T.PASS} FAIL={T.FAIL} WARN={T.WARN}")
        return 1 if T.FAIL else 0
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:
            srv.kill()


if __name__ == '__main__':
    sys.exit(main())

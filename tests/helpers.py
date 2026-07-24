#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""Tim 学习助手 — 测试公共工具 (helpers)

将 test_full_v4.py / test_full_v5.py 中重复定义的
db / login / csrf_token / check / check_page_ok / section /
new_question / png_bytes / cleanup 等收敛到此处，消除重复代码。

测试脚本统一通过 `import helpers as H` 使用：
    import helpers as H
    H.login()
    H.check("新增错题", "POST", "/questions/add", 302, data={...})
    if cond: H.assert_true(True, "xxx")
    H.cleanup()

所有计数（PASS/FAIL/WARN）与待清理集合都保存在本模块的全局变量中，
由 H.check / H.assert_true 等内部函数直接修改，测试脚本只需读取 H.PASS 等。
"""

import os
import re
import sys
import time
import socket
import signal
import sqlite3
import base64
import subprocess
import threading
import requests

BASE = "http://127.0.0.1:5001"
TEST_PORT = 5001
DB = "data/study_assistant.db"
S = requests.Session()
SERVER_STARTED = False
_CSRF_CACHE = None    # 会话内缓存的 CSRF token（避免每个请求都回源取）

# ---- 计数器与待清理集合（模块级，便于多测试脚本共享）----
PASS = 0
FAIL = 0
WARN = 0
ERRORS = []
CLEANUP_IDS = []      # 测试创建的错题 id
CLEANUP_PLANS = []    # 测试创建的计划 id
CLEANUP_KP = []       # 测试创建的知识点名
CLEANUP_TOKENS = []   # 测试创建的 token id

# 测试数据统一以 TEST_ 前缀标记，便于「全局扫描」兜底删除，
# 即使某条数据因异常未登记到 CLEANUP_* 也不会残留到生产库。
TEST_PREFIX = "TEST_"

# 与测试数据相关的全部表（用于兜底扫描 / 验证）
_SWEEP_TABLES = (
    "mistake_records",   # timu LIKE TEST_%
    "study_plans",       # title LIKE TEST_%
    "knowledge_points",  # name LIKE TEST_%
    "base_data",         # category='knowledge_point' AND name LIKE TEST_%
    "api_tokens",        # name/token_prefix LIKE TEST_%（防御性）
)


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def login(username="tim", password="tim123"):
    global _CSRF_CACHE
    _CSRF_CACHE = None  # 登录后会话 token 刷新，作废缓存
    r = S.post(f"{BASE}/login", data={"username": username, "password": password},
               allow_redirects=False)
    return r.status_code


def csrf_token():
    global _CSRF_CACHE
    # 会话内缓存：登录后 token 不变，避免每个 check() 都回源取 token（省一次 HTTP 往返）
    if _CSRF_CACHE:
        return _CSRF_CACHE
    t = S.cookies.get("csrf_token", "")
    if not t:
        r = S.get(f"{BASE}/questions", allow_redirects=False)
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
        if m:
            t = m.group(1)
    _CSRF_CACHE = t
    return t


def check(name, method, path, expect, *, csrf=True, json_body=None, data=None,
          headers=None, follow=False):
    """统一请求校验：自动处理 CSRF、JSON/表单体、期望状态码。

    expect 可为单个 int（精确匹配）或 list/tuple（命中其一即 PASS）。
    """
    global PASS, FAIL
    url = f"{BASE}{path}"
    hdrs = dict(headers or {})
    kw = {"allow_redirects": follow, "timeout": 20}
    if method == "GET":
        resp = S.get(url, headers=hdrs, **kw)
    elif method == "POST":
        if csrf:
            if json_body is not None:
                hdrs.setdefault("X-CSRF-Token", csrf_token())
                kw["json"] = json_body
            elif data is not None:
                if isinstance(data, dict):
                    data = dict(data)
                    data["csrf_token"] = csrf_token()
                kw["data"] = data
            else:
                # 无请求体也需带 CSRF（pause/resume/delete/toggle 等表单 POST）
                hdrs.setdefault("X-CSRF-Token", csrf_token())
        else:
            if json_body is not None:
                kw["json"] = json_body
            elif data is not None:
                kw["data"] = data
        if hdrs:
            kw["headers"] = hdrs
        resp = S.post(url, **kw)
    else:
        # DELETE / PUT / PATCH 等方法：默认注入 CSRF
        if csrf:
            hdrs.setdefault("X-CSRF-Token", csrf_token())
        if hdrs:
            kw["headers"] = hdrs
        resp = S.request(method, url, **kw)

    code = resp.status_code
    ok = code == expect if isinstance(expect, int) else code in expect
    if ok:
        PASS += 1
        print(f"  ✅ {name} → {code}")
    else:
        FAIL += 1
        snippet = resp.text[:160].replace("\n", " ")
        print(f"  ❌ {name} → 期望 {expect}, 实际 {code}  | {snippet}")
        ERRORS.append(f"{name}: 期望 {expect} 实际 {code}")
    return resp


def check_page_ok(name, path):
    """页面完整性：200 且不含 Jinja/Python 错误残留、无未渲染模板变量。"""
    global PASS, FAIL
    r = S.get(f"{BASE}{path}")
    text = r.text
    has_err = ("Traceback (most recent call last)" in text
               or "UndefinedError" in text
               or "jinja2.exceptions" in text
               or "Internal Server Error" in text)
    ok = r.status_code == 200 and not has_err and "{{" not in text[-4000:]
    if ok:
        PASS += 1
        print(f"  ✅ {name} → 200 结构正常")
    else:
        FAIL += 1
        print(f"  ❌ {name} → {r.status_code} 含错误残留: {has_err}")
        ERRORS.append(f"{name}: 页面错误 status={r.status_code} err={has_err}")
    return r


def section(t):
    print(f"\n📌 {t}")


def png_bytes():
    # 1x1 透明 PNG
    return base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC')


def new_question(timu, xueke="数学", zhishidian="函数/幂", **extra):
    """新增一道测试错题并登记到 CLEANUP_IDS。返回 mistake id。"""
    data = {"xueke": xueke, "timu": timu, "zhengquedaan": "a",
            "zhishidian": zhishidian, "difficulty": "2"}
    data.update(extra)
    r = check(f"新增错题[{timu[:12]}]", "POST", "/questions/add", 302, data=data)
    c = db()
    row = c.execute("SELECT id FROM mistake_records WHERE timu=? ORDER BY id DESC LIMIT 1",
                    (timu,)).fetchone()
    c.close()
    mid = row["id"] if row else None
    if mid:
        CLEANUP_IDS.append(mid)
    return mid


# ---- 手动断言（替代测试脚本中直接操纵全局 PASS/FAIL 的写法）----
def assert_true(cond, name):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")
        ERRORS.append(name)
    return cond


def assert_false(cond, name):
    return assert_true(not cond, name)


def warn(name):
    global WARN
    WARN += 1
    print(f"  ⚠️ {name}")


def record_error(detail):
    global FAIL
    FAIL += 1
    ERRORS.append(detail)
    print(f"  ❌ {detail}")


def reset_state():
    """重置计数器与清理集合（多次运行前调用）。"""
    global PASS, FAIL, WARN
    PASS = 0
    FAIL = 0
    WARN = 0
    ERRORS.clear()
    CLEANUP_IDS.clear()
    CLEANUP_PLANS.clear()
    CLEANUP_KP.clear()
    CLEANUP_TOKENS.clear()


def _sweep_test_rows(c):
    """物理删除所有以 TEST_ 开头的测试残留（跨表一致性删除）。

    作为兜底扫描：即便某条数据因异常未登记到 CLEANUP_*，也不会残留在生产库。
    共享知识库（西城 uuid='xicheng_import'，节点名为 数学/物理 等）不含 TEST_ 前缀，
    因此不会被误删。
    返回每张表的删除计数 dict。
    """
    cnt = {}
    # 1) 收集 TEST_ 错题 / 计划 id
    mids = [r["id"] for r in c.execute(
        "SELECT id FROM mistake_records WHERE timu LIKE ?", (TEST_PREFIX + "%",)).fetchall()]
    # 1.1 安全网：XSS 注入测试的 timu 以 <script 开头（真实错题不会如此），
    #     兜底捕获未用 TEST_ 前缀的注入测试残留，避免跨版本累计。
    mids += [r["id"] for r in c.execute(
        "SELECT id FROM mistake_records WHERE timu LIKE '<script%'").fetchall()]
    pids = [r["id"] for r in c.execute(
        "SELECT id FROM study_plans WHERE title LIKE ?", (TEST_PREFIX + "%",)).fetchall()]
    cnt["mistake_records"] = len(mids)
    cnt["study_plans"] = len(pids)

    # 2) 删除错题及其全部依赖（外键未启用 ON DELETE，需手动级联）
    for mid in mids:
        c.execute("DELETE FROM review_logs WHERE mistake_id=?", (mid,))
        c.execute("DELETE FROM plan_mistakes WHERE mistake_id=?", (mid,))
        c.execute("DELETE FROM mistake_images WHERE mistake_id=?", (mid,))
        c.execute("DELETE FROM mistake_knowledge WHERE mistake_id=?", (mid,))
        c.execute("DELETE FROM mistake_records WHERE id=?", (mid,))

    # 3) 删除计划及其关联
    for pid in pids:
        c.execute("DELETE FROM plan_mistakes WHERE plan_id=?", (pid,))
        c.execute("DELETE FROM study_plans WHERE id=?", (pid,))

    # 4) 知识点（含旧 base_data 表）
    kp = c.execute("SELECT id FROM knowledge_points WHERE name LIKE ?",
                   (TEST_PREFIX + "%",)).fetchall()
    cnt["knowledge_points"] = len(kp)
    for r in kp:
        c.execute("DELETE FROM mistake_knowledge WHERE kp_id=?", (r["id"],))
        c.execute("DELETE FROM knowledge_points WHERE id=?", (r["id"],))
    c.execute("DELETE FROM base_data WHERE category='knowledge_point' AND name LIKE ?",
              (TEST_PREFIX + "%",))

    # 5) API token（防御性，测试套件当前不创建，但保留以保万全）
    tk = c.execute("SELECT id FROM api_tokens WHERE name LIKE ? OR token_prefix LIKE ?",
                   (TEST_PREFIX + "%", TEST_PREFIX + "%")).fetchall()
    cnt["api_tokens"] = len(tk)
    for r in tk:
        c.execute("DELETE FROM api_tokens WHERE id=?", (r["id"],))

    return cnt


def cleanup():
    """清理测试产生的数据，避免污染生产库。测试结束后必须调用。

    两道保险：
      1) 快速路径：删除已登记到 CLEANUP_* 的 id（与扫描互补、幂等）。
      2) 全局兜底扫描：删除任何 TEST_ 前缀残留（跨所有相关表）。
    最后重建知识点树移除孤儿节点，恢复一致状态。
    """
    c = db()
    # ---- 快速路径：已跟踪 id ----
    for mid in CLEANUP_IDS:
        try:
            c.execute("DELETE FROM review_logs WHERE mistake_id=?", (mid,))
            c.execute("DELETE FROM plan_mistakes WHERE mistake_id=?", (mid,))
            c.execute("DELETE FROM mistake_images WHERE mistake_id=?", (mid,))
            c.execute("DELETE FROM mistake_knowledge WHERE mistake_id=?", (mid,))
            c.execute("DELETE FROM mistake_records WHERE id=?", (mid,))
        except Exception:
            pass
    for pid in CLEANUP_PLANS:
        try:
            c.execute("DELETE FROM plan_mistakes WHERE plan_id=?", (pid,))
            c.execute("DELETE FROM study_plans WHERE id=?", (pid,))
        except Exception:
            pass
    for nm in CLEANUP_KP:
        try:
            c.execute("DELETE FROM base_data WHERE category='knowledge_point' AND name=?", (nm,))
            c.execute("DELETE FROM knowledge_points WHERE name=?", (nm,))
        except Exception:
            pass
    # ---- 全局兜底扫描：任何 TEST_ 残留 ----
    swept = _sweep_test_rows(c)
    c.commit()
    c.close()
    # 重建知识点树，移除因测试数据产生的孤儿节点，恢复一致状态
    try:
        S.get(f"{BASE}/api/knowledge-points/migrate", timeout=20)
    except Exception:
        pass
    tracked = len(CLEANUP_IDS) + len(CLEANUP_PLANS) + len(CLEANUP_KP)
    print(f"  清理 已跟踪 {tracked} 项 + 扫描残留 {sum(swept.values())} 项 "
          f"(错题 {swept['mistake_records']} / 计划 {swept['study_plans']} / "
          f"知识点 {swept['knowledge_points']} / token {swept['api_tokens']})")


def verify_cleanup():
    """清理后验证：统计所有 TEST_ 前缀残留。返回 (residual_dict, total)。"""
    c = db()
    residual = {}
    residual["mistake_records"] = c.execute(
        "SELECT COUNT(*) c FROM mistake_records WHERE timu LIKE ? OR timu LIKE '<script%'",
        (TEST_PREFIX + "%",)).fetchone()["c"]
    residual["study_plans"] = c.execute(
        "SELECT COUNT(*) c FROM study_plans WHERE title LIKE ?",
        (TEST_PREFIX + "%",)).fetchone()["c"]
    residual["knowledge_points"] = c.execute(
        "SELECT COUNT(*) c FROM knowledge_points WHERE name LIKE ?",
        (TEST_PREFIX + "%",)).fetchone()["c"]
    residual["base_data"] = c.execute(
        "SELECT COUNT(*) c FROM base_data WHERE category='knowledge_point' AND name LIKE ?",
        (TEST_PREFIX + "%",)).fetchone()["c"]
    residual["api_tokens"] = c.execute(
        "SELECT COUNT(*) c FROM api_tokens WHERE name LIKE ? OR token_prefix LIKE ?",
        (TEST_PREFIX + "%", TEST_PREFIX + "%")).fetchone()["c"]
    c.close()
    total = sum(residual.values())
    return residual, total


def ensure_xicheng():
    """直接（进程内）确保西城共享库就绪，避免子进程与测试服务争用 SQLite 锁。

    幂等：重复调用不会产生重复节点。
    """
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root not in sys.path:
            sys.path.insert(0, root)
        import import_xicheng_kp
        import_xicheng_kp.import_tree()
    except Exception as e:
        print(f"  ⚠️ 西城导入失败: {e}")


def reset_test_data():
    """测试前基线清理：删除遗留 TEST_ 数据、重建树、确保西城共享库存在。

    幂等、可重复运行：
      · 全局扫描删除所有 timu/title/name 以 'TEST_' 开头的测试残留
      · 重建树（migrate 现已保留共享库 uuid='xicheng_import'）
      · 进程内幂等导入西城共享库，保证节点就绪
    """
    c = db()
    try:
        _sweep_test_rows(c)
        c.commit()
    finally:
        c.close()
    # 确保西城共享库存在（进程内幂等导入；migrate 修复后不会被清空）
    ensure_xicheng()
    try:
        S.get(f"{BASE}/api/knowledge-points/migrate", timeout=20)
    except Exception:
        pass


def summary(label=""):
    """打印汇总并返回是否全部通过。"""
    total = PASS + FAIL + WARN
    print("\n" + "=" * 60)
    if label:
        print(f"  📋 {label}")
    print(f"  📊 测试：{PASS} 通过 / {FAIL} 失败 / {WARN} 警告  (共 {total})")
    if total:
        print(f"  📈 通过率：{round(PASS/total*100, 1)}%")
    if ERRORS:
        print("  ⚠️ 失败项：")
        for e in ERRORS:
            print("   -", e)
    print("=" * 60)
    return FAIL == 0


def _kill_old_server(port=5000):
    """终止占用指定端口的旧服务进程。"""
    try:
        out = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if f":{port} " in line or f":{port}\t" in line:
                m = re.search(r"pid=(\d+)", line)
                if m:
                    try:
                        os.kill(int(m.group(1)), signal.SIGTERM)
                    except Exception:
                        pass
    except Exception:
        pass
    time.sleep(1)


def start_server(port=TEST_PORT, retries=3):
    """以线程方式在当前进程内启动「当前代码」的 Flask 服务（沙箱可靠模式）。

    绑定独立测试端口（默认 5001），避免与环境中常驻的旧服务（5000）冲突，
    确保测试命中的是最新代码（如 migrate 保留共享知识库、道法2 删除修复等）。
    服务随测试进程存活，测试结束自动退出。
    """
    global SERVER_STARTED
    if SERVER_STARTED:
        return
    _kill_old_server(port)
    # 将项目根目录加入 sys.path，确保能 import app（测试脚本位于 tests/ 下）
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from app import app as flask_app

    def _run():
        flask_app.run(host="0.0.0.0", port=port, debug=False,
                      use_reloader=False, threaded=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    # 轮询就绪（带端口冲突重试）
    for attempt in range(retries):
        ready = False
        for _ in range(60):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    ready = True
                    break
            except OSError:
                time.sleep(0.2)
        if ready:
            break
        # 端口被占用（旧进程可能未释放），再杀一次重试
        _kill_old_server(port)
        time.sleep(1)

    time.sleep(0.5)
    SERVER_STARTED = True
    print(f"  🚀 测试服务已启动（端口 {port}，使用当前代码）")

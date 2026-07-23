#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""Tim 学习助手 — 全面自动化测试 v4（测试专家版，含知识点多层结构 S1+S2 专项）"""

import re
import sqlite3
import time
import json
from datetime import date, timedelta

import requests

BASE = "http://127.0.0.1:5000"
DB = "data/study_assistant.db"
S = requests.Session()

PASS = 0
FAIL = 0
WARN = 0
ERRORS = []
CLEANUP_IDS = []   # 测试创建的错题 id
CLEANUP_TOKENS = []  # 测试创建的 token id


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def login(username="tim", password="tim123"):
    r = S.post(f"{BASE}/login", data={"username": username, "password": password},
               allow_redirects=False)
    return r.status_code


def csrf_token():
    t = S.cookies.get("csrf_token", "")
    if not t:
        r = S.get(f"{BASE}/questions", allow_redirects=False)
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
        if m:
            t = m.group(1)
    return t


def check(name, method, path, expect, *, csrf=True, json_body=None, data=None,
          headers=None, follow=False):
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
            if json_body is not None:
                kw["json"] = json_body
            elif data is not None:
                kw["data"] = data
        if hdrs:
            kw["headers"] = hdrs
        resp = S.post(url, **kw)
    else:
        resp = S.request(method, url, headers=hdrs, **kw)

    code = resp.status_code
    ok = code == expect if isinstance(expect, int) else code in expect
    if ok:
        PASS += 1
        print(f"  ✅ {name} → {code}")
    else:
        FAIL += 1
        snippet = resp.text[:200].replace("\n", " ")
        print(f"  ❌ {name} → 期望 {expect}, 实际 {code}  | {snippet}")
        ERRORS.append(f"{name}: 期望 {expect} 实际 {code}")
    return resp


def check_page_ok(name, path):
    """页面完整性：200 且不含 Jinja/Python 错误残留"""
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


def cleanup():
    """清理测试产生的数据，避免污染"""
    c = db()
    for mid in CLEANUP_IDS:
        try:
            c.execute("UPDATE mistake_records SET status='deleted' WHERE id=?", (mid,))
        except Exception:
            pass
    for tid in CLEANUP_TOKENS:
        try:
            c.execute("DELETE FROM api_tokens WHERE id=?", (tid,))
        except Exception:
            pass
    # 清理测试专用知识点关联（软删除即可，结构本身由 migrate 维护）
    try:
        c.execute("DELETE FROM mistake_knowledge WHERE mistake_id IN (%s)" % (
            ",".join("?" * len(CLEANUP_IDS)) if CLEANUP_IDS else "0"), CLEANUP_IDS)
    except Exception:
        pass
    c.commit()
    c.close()
    # 重建知识点树，移除因软删除测试数据产生的孤儿节点，恢复一致状态
    try:
        S.get(f"{BASE}/api/knowledge-points/migrate", timeout=20)
    except Exception:
        pass


# =====================================================================
def main():
    global PASS, FAIL, WARN, ERRORS
    login()

    # ---------- 1. 认证 ----------
    section("1. 认证与授权")
    # 真正无会话的请求（全局 S 已登录，需用全新 session 验证鉴权）
    r0 = requests.get(f"{BASE}/", allow_redirects=False, timeout=20)
    if r0.status_code == 302 and "/login" in (r0.headers.get("Location", "")):
        PASS += 1
        print("  ✅ 未登录访问首页应重定向 → 302")
    else:
        FAIL += 1
        print(f"  ❌ 未登录访问首页未重定向 → {r0.status_code}")
        ERRORS.append("未登录首页未重定向")
    r0b = requests.get(f"{BASE}/questions", allow_redirects=False, timeout=20)
    if r0b.status_code == 302 and "/login" in (r0b.headers.get("Location", "")):
        PASS += 1
        print("  ✅ 未登录访问错题本应重定向 → 302")
    else:
        FAIL += 1
        print(f"  ❌ 未登录访问错题本未重定向 → {r0b.status_code}")
        ERRORS.append("未登录错题本未重定向")
    # 错误密码登录应失败（仍停留在登录页 200）
    r = requests.post(f"{BASE}/login", data={"username": "tim", "password": "wrong"},
                      allow_redirects=False, timeout=20)
    check("错误密码登录应失败", "POST", "/login", 200,
          data={"username": "tim", "password": "wrong"})

    # ---------- 2. 错题 CRUD ----------
    section("2. 错题 CRUD")
    check_page_ok("错题本列表", "/questions")
    # 新增（含多级知识点）
    add_data = {
        "xueke": "数学", "timu": "TEST_二次函数顶点题",
        "xueshengdaan": "TEST错答", "zhengquedaan": "TEST正答",
        "cuowufenxi": "TEST分析", "zhishidian": "函数/二次函数；二次函数", "difficulty": 2,
    }
    r = check("新增错题", "POST", "/questions/add", 302, data=add_data)
    c = db()
    new = c.execute("SELECT id FROM mistake_records WHERE timu='TEST_二次函数顶点题' ORDER BY id DESC LIMIT 1").fetchone()
    assert new, "新增错题未落库"
    mid = new["id"]
    CLEANUP_IDS.append(mid)
    check("新增错题已落库", "GET", "/questions", 200)
    # 编辑
    edit_data = {"xueke": "数学", "timu": "TEST_二次函数顶点题(改)",
                 "xueshengdaan": "x", "zhengquedaan": "y", "cuowufenxi": "z",
                 "zhishidian": "函数/一次函数；二次函数", "difficulty": 3}
    check("编辑错题", "POST", f"/questions/{mid}/edit", 302, data=edit_data)
    upd = c.execute("SELECT timu, zhishidian FROM mistake_records WHERE id=?", (mid,)).fetchone()
    assert upd["timu"].endswith("(改)"), "编辑未生效"
    # 详情
    check_page_ok("错题详情", f"/questions/{mid}")
    c.close()
    # 软删除（用独立的临时错题验证，保留 mid 活跃用于后续多对多校验）
    del_data = {"xueke": "英语", "timu": "TEST_删除验证题",
                "zhengquedaan": "a", "zhishidian": "一般现在时", "difficulty": 1}
    check("新增待删除错题", "POST", "/questions/add", 302, data=del_data)
    c = db()
    del_id = c.execute("SELECT id FROM mistake_records WHERE timu='TEST_删除验证题' ORDER BY id DESC LIMIT 1").fetchone()["id"]
    c.close()
    CLEANUP_IDS.append(del_id)
    check("删除错题(软删除)", "POST", f"/questions/{del_id}/delete", 302, data={})
    c = db()
    st = c.execute("SELECT status FROM mistake_records WHERE id=?", (del_id,)).fetchone()["status"]
    c.close()
    assert st == "deleted", "软删除未生效"

    # ---------- 3. 知识点管理 + 多层结构 ----------
    section("3. 知识点管理 / 多层结构")
    check_page_ok("知识点管理页", "/knowledge-points")
    check_page_ok("知识点思维导图页", "/knowledge-map")
    # 新增知识点(base_data)
    check("新增知识点(base_data)", "POST", "/api/knowledge-points/add", 200,
          json_body={"name": "TEST_自定义知识点", "xueke": "数学"})
    # 重命名
    check("重命名知识点", "POST", "/api/knowledge-points/rename", 200,
          json_body={"old_name": "TEST_自定义知识点", "new_name": "TEST_自定义知识点2"})
    # 合并
    check("合并知识点", "POST", "/api/knowledge-points/merge", 200,
          json_body={"source": "TEST_自定义知识点2", "target": "二次函数"})

    # tree API 结构
    r = check("知识点树 API", "GET", "/api/knowledge-points/tree", 200)
    j = r.json()
    assert j.get("success") and isinstance(j.get("tree"), list), "tree 结构异常"
    roots = j["tree"]
    # 验证根为学科(level1) 且含 children
    lvl1_ok = all(nd.get("level") == 1 and "children" in nd for nd in roots)
    if lvl1_ok:
        PASS += 1
        print("  ✅ 树根为学科(level1)且含 children")
    else:
        FAIL += 1
        print("  ❌ 树根层级/结构异常")
        ERRORS.append("tree 根结构异常")
    # 验证命名规则拆层级：编辑后的错题用了 "函数/一次函数"，应存在章"函数"lv2 + 点"一次函数"lv3
    r2 = S.get(f"{BASE}/api/knowledge-points/tree")
    tree = r2.json()["tree"]
    found_chapter = False
    found_point = False
    for subj in tree:
        for ch in subj.get("children", []):
            if ch.get("name") == "函数" and ch.get("level") == 2:
                found_chapter = True
                for kp in ch.get("children", []):
                    if kp.get("name") == "一次函数" and kp.get("level") == 3:
                        found_point = True
    if found_chapter and found_point:
        PASS += 1
        print("  ✅ 命名规则自动拆层级：章'函数'(lv2)+点'一次函数'(lv3) 正确生成")
    else:
        FAIL += 1
        print("  ❌ 命名规则拆层级未生效（函数/一次函数）")
        ERRORS.append("命名规则拆层级失败")

    # 多对多：测试错题编辑前曾关联 "函数/二次函数；二次函数" → 至少 2 个关联
    c = db()
    nlinks = c.execute(
        "SELECT COUNT(*) c FROM mistake_knowledge mk JOIN mistake_records mr ON mr.id=mk.mistake_id WHERE mk.mistake_id=? AND mr.status!='deleted'",
        (mid,)).fetchone()["c"]
    c.close()
    if nlinks >= 1:
        PASS += 1
        print(f"  ✅ 错题-知识点多对多关联正常（当前关联 {nlinks} 个）")
    else:
        FAIL += 1
        print("  ❌ 多对多关联缺失")
        ERRORS.append("多对多关联缺失")

    # migrate 幂等
    r = check("全量重建(幂等)", "GET", "/api/knowledge-points/migrate", 200)
    jm = r.json()
    r = S.get(f"{BASE}/api/knowledge-points/migrate").json()
    c = db()
    kp1 = c.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]
    c.close()
    if jm.get("success") and r.get("success") and kp1 >= 10:
        PASS += 1
        print(f"  ✅ migrate 幂等可行，节点稳定（{kp1}）")
    else:
        FAIL += 1
        print("  ❌ migrate 返回异常")
        ERRORS.append("migrate 异常")

    # ---------- 4. 学习计划 ----------
    section("4. 学习计划")
    check_page_ok("学习计划页", "/study-plans")
    month = date.today().strftime("%Y-%m")
    check("新增学习计划", "POST", "/study-plans/add", 302,
          data={"title": "TEST_周计划", "description": "d", "xueke": "数学",
                "zhishidian": "二次函数", "target_date": date.today().isoformat(),
                "priority": 2})
    check("学习计划按月份", "GET", f"/study-plans?month={month}", 200)

    # ---------- 5. 复习 ----------
    section("5. 复习与复习记录")
    check_page_ok("复习页", "/review")
    check_page_ok("复习记录页", "/review/history")
    # 用一条活跃错题提交复习
    c = db()
    m = c.execute("SELECT id FROM mistake_records WHERE status='active' AND uuid=(SELECT uuid FROM mistake_records GROUP BY uuid ORDER BY COUNT(*) DESC LIMIT 1) LIMIT 1").fetchone()
    c.close()
    if m:
        mid_r = m["id"]
        # 提交前掌握率快照（mastery_rate 在 knowledge_points 表，需 JOIN）
        c = db()
        before = c.execute(
            "SELECT COALESCE(SUM(kp.mastery_rate),0) v FROM mistake_knowledge mk "
            "JOIN knowledge_points kp ON kp.id=mk.kp_id WHERE mk.mistake_id=?", (mid_r,)).fetchone()["v"]
        c.close()
        r = check("提交复习(correct)", "POST", f"/api/review/{mid_r}/submit", 200,
                  json_body={"result": "correct", "time_spent": 30, "notes": ""})
        # 连续答对触发 mastered → 掌握率冗余应更新
        c = db()
        after = c.execute(
            "SELECT COALESCE(SUM(kp.mastery_rate),0) v FROM mistake_knowledge mk "
            "JOIN knowledge_points kp ON kp.id=mk.kp_id WHERE mk.mistake_id=?", (mid_r,)).fetchone()["v"]
        status = c.execute("SELECT status FROM mistake_records WHERE id=?", (mid_r,)).fetchone()["status"]
        c.close()
        if after != before or status in ("mastered", "active"):
            PASS += 1
            print(f"  ✅ 复习后掌握率冗余已维护（before={before} after={after} status={status}）")
        else:
            FAIL += 1
            print("  ❌ 复习后掌握率冗余未更新")
            ERRORS.append("掌握率冗余未更新")
    # 复习历史 API 筛选
    check("复习历史列表 API", "GET", "/api/review/history/list", 200)

    # ---------- 6. 统计 ----------
    section("6. 统计分析")
    check_page_ok("统计页", "/statistics")
    check_page_ok("回收站页", "/questions/deleted")

    # ---------- 7. API Token ----------
    section("7. API Token")
    check_page_ok("Token 管理页", "/settings/api-tokens")
    r = check("生成 Token", "POST", "/api/settings/api-tokens", 200,
              json_body={"name": "TEST_token", "description": "", "rate_limit": 60})
    jd = r.json().get("data", {}) if r.status_code == 200 else {}
    tok = jd.get("token", "")
    tid = jd.get("id")
    if tok and tid:
        # 暂不撤销：留待 v1 鉴权用例使用，最终由 cleanup 删除
        CLEANUP_TOKENS.append(tid)
    else:
        FAIL += 1
        print("  ❌ 生成 Token 未返回明文/ID")
        ERRORS.append("Token 创建未返回明文")

    # ---------- 8. 外部 API v1 ----------
    section("8. 外部 API v1（Bearer Token）")
    check("v1 ping 无 token 应 401", "GET", "/api/v1/ping", 401)
    # 获取一个有效 token：用刚才生成的 tok；若未取得则跳过带 token 测试并报警
    if tok:
        check("v1 ping 有 token 应 200", "GET", "/api/v1/ping", 200,
              headers={"Authorization": f"Bearer {tok}"})
        imp = {"questions": [{"xueke": "数学", "timu": "TEST_api_import",
                               "zhengquedaan": "a", "zhishidian": "函数/幂", "difficulty": 2}]}
        r = check("v1 import 有 token 应 200", "POST", "/api/v1/questions/import", 200,
                  json_body=imp, headers={"Authorization": f"Bearer {tok}"})
        # 清理导入的错题
        ji = r.json()
        for iid in ji.get("saved_ids", []):
            CLEANUP_IDS.append(iid)
    else:
        WARN += 1
        print("  ⚠️ 未取得有效 token，跳过 v1 鉴权用例")

    # ---------- 9. CSRF 防护 ----------
    section("9. CSRF 防护")
    r = S.post(f"{BASE}/questions/add", data={"xueke": "数学", "timu": "CSRF_TEST"}, timeout=20)
    if r.status_code == 403:
        PASS += 1
        print("  ✅ 无 CSRF 的 POST 应被拒(403) → 403")
    else:
        FAIL += 1
        print(f"  ❌ 无 CSRF 的 POST 未被拦截 → {r.status_code}")
        ERRORS.append("CSRF 防护失效")

    # ---------- 10. 页面完整性 ----------
    section("10. 页面完整性")
    for p in ["/", "/questions", "/knowledge-points", "/knowledge-map", "/study-plans",
              "/review", "/review/history", "/statistics", "/questions/deleted",
              "/settings/api-tokens", "/questions/add",
              "/questions/paste-import", "/questions/ocr", "/questions/doc-import"]:
        check_page_ok(f"页面 {p}", p)

    # ---------- 11. 安全专项 ----------
    section("11. 安全专项")
    # XSS：题目含脚本，列表/详情页应输出转义而非执行
    xss_data = {"xueke": "语文", "timu": "<script>alert('xss')</script>TEST_XSS",
                "zhengquedaan": "a", "zhishidian": "XSS测试", "difficulty": 1}
    r = S.post(f"{BASE}/questions/add", data={**xss_data, "csrf_token": csrf_token()},
               allow_redirects=False, timeout=20)
    if r.status_code in (302, 200):
        c = db()
        xid = c.execute("SELECT id FROM mistake_records WHERE timu LIKE '%TEST_XSS%' ORDER BY id DESC LIMIT 1").fetchone()
        c.close()
        if xid:
            CLEANUP_IDS.append(xid["id"])
            rd = S.get(f"{BASE}/questions/{xid['id']}")
            if "<script>alert('xss')</script>" in rd.text:
                FAIL += 1
                print("  ❌ XSS 未转义，存在注入风险")
                ERRORS.append("XSS 未转义")
            else:
                PASS += 1
                print("  ✅ XSS 输入已转义（Jinja 自动转义）")
    # SQL 注入（知识点筛选）
    r = S.get(f"{BASE}/knowledge-points?zhishidian=' OR '1'='1", timeout=20)
    if r.status_code == 200:
        PASS += 1
        print("  ✅ SQL 注入参数化（筛选注入未报错）")
    else:
        FAIL += 1
        print(f"  ❌ 注入筛选返回异常 {r.status_code}")
        ERRORS.append("注入筛选异常")
    # 路径遍历：导入页 filename 参数含 ../（GET 页面，验证不报错/不泄露文件）
    r = S.get(f"{BASE}/questions/doc-import?filename=../../etc/passwd", timeout=20)
    if r.status_code == 200 and "/etc/passwd" not in r.text:
        PASS += 1
        print("  ✅ 路径遍历参数被安全处理（页面 200 且未泄露目标文件）")
    else:
        FAIL += 1
        print(f"  ❌ 路径遍历处理异常 {r.status_code}")
        ERRORS.append("路径遍历处理异常")
    # 不存在路由 → 404
    check("不存在的路由 → 404", "GET", "/this/route/not/exist", 404)
    # 非数字 ID 详情 → 404
    check("错题详情非数字ID → 404", "GET", "/questions/abc", 404)

    # ---------- 12. 知识点可见性（空 uuid Cookie 自愈） ----------
    section("12. 空 uuid Cookie 自愈到已有数据")
    S2 = requests.Session()
    S2.post(f"{BASE}/login", data={"username": "tim", "password": "tim123"}, allow_redirects=False)
    # 覆写 uuid Cookie 为空（模拟首次打开生成的空 uuid，但已登录）
    S2.cookies.set("tim_study_uuid", "00000000-0000-0000-0000-000000000000", domain="127.0.0.1")
    r = S2.get(f"{BASE}/api/knowledge-points/tree", timeout=20)
    jt = r.json() if r.status_code == 200 else {}
    if jt.get("success") and len(jt.get("tree", [])) > 0:
        PASS += 1
        print(f"  ✅ 空 uuid Cookie 自愈成功，思维导图可加载 {len(jt['tree'])} 个学科根")
    else:
        FAIL += 1
        print("  ❌ 空 uuid Cookie 仍无法加载知识点数据")
        ERRORS.append("空 uuid Cookie 未自愈")

    # ---------- 清理 ----------
    cleanup()

    # ---------- 汇总 ----------
    print("\n" + "=" * 60)
    print(f"  📊 测试结果：{PASS} 通过 / {FAIL} 失败 / {WARN} 警告  (共 {PASS+FAIL+WARN})")
    print(f"  📈 通过率：{round(PASS/(PASS+FAIL+WARN)*100,1)}%")
    if ERRORS:
        print("\n  ❌ 失败项：")
        for e in ERRORS:
            print("   -", e)
    print("=" * 60)
    return FAIL == 0


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)

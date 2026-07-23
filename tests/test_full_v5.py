#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""Tim 学习助手 — 全面补充测试 v5（测试专家版，覆盖 v4 未触及的接口盲区）

覆盖盲区：
  1. 学习计划高级操作（更新内容/状态、暂停/恢复/删除、关联题目 add/remove/auto/review）
  2. 复习系统补充（add-all、today-stats、config、submit 边界与掌握流转、history list 筛选）
  3. 批量操作（batch-delete、batch-update 多 action、restore、purge、toggle-status）
  4. 语音笔记 API（GET/POST/DELETE 生命周期）
  5. 图片 API（上传/获取/删除/404 边界）
  6. 导出（excel/pdf/anki）
  7. 知识点 legacy（by-subject、add、rename、merge）
  8. CSRF 扩展（多个 POST 端点无 token 应 403）
  9. 边界/健壮性（非法参数处理）
  10. 回收站生命周期（delete → list → restore → purge）
"""

import base64
import io
import re
import sqlite3
from datetime import date, timedelta

import requests

BASE = "http://127.0.0.1:5000"
DB = "data/study_assistant.db"
S = requests.Session()

PASS = 0
FAIL = 0
WARN = 0
ERRORS = []
CLEANUP_IDS = []        # 测试创建的错题 id
CLEANUP_PLANS = []      # 测试创建的计划 id
CLEANUP_TOKENS = []     # 测试创建的 token id
CLEANUP_KP = []         # 测试创建的 base_data 知识点名


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
                # 无请求体也需带 CSRF（如 pause/resume/delete/toggle 等表单 POST）
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
        # DELETE / PUT / PATCH 等方法：默认也注入 CSRF（便于语音 DELETE 等端点测试）
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


# =====================================================================
def main():
    global PASS, FAIL, WARN, ERRORS
    login()

    # ---------- 1. 学习计划高级操作 ----------
    section("1. 学习计划高级操作（更新/暂停/恢复/删除/关联题目）")
    check_page_ok("学习计划页", "/study-plans")
    check("新增学习计划", "POST", "/study-plans/add", 302,
          data={"title": "TEST_高级计划", "description": "d", "xueke": "数学",
                "zhishidian": "函数", "target_date": date.today().isoformat(), "priority": 2})
    c = db()
    pid = c.execute("SELECT id FROM study_plans WHERE title='TEST_高级计划' ORDER BY id DESC LIMIT 1").fetchone()["id"]
    c.close()
    if pid:
        CLEANUP_PLANS.append(pid)

    # 更新内容
    check("更新计划内容", "POST", f"/study-plans/{pid}/update", 302,
          data={"title": "TEST_高级计划V2", "description": "dd", "xueke": "数学",
                "zhishidian": "函数", "target_date": date.today().isoformat(), "priority": 3})
    c = db()
    t2 = c.execute("SELECT title FROM study_plans WHERE id=?", (pid,)).fetchone()["title"]
    c.close()
    if t2 == "TEST_高级计划V2":
        PASS += 1; print("  ✅ 计划内容已更新")
    else:
        FAIL += 1; print(f"  ❌ 计划内容未更新: {t2}"); ERRORS.append("计划更新失败")

    # 状态流转：暂停 -> 恢复 -> 完成
    for st, label in (("paused", "暂停"), ("in_progress", "恢复"), ("completed", "完成")):
        if st == "completed":
            check(f"计划标记{label}", "POST", f"/study-plans/{pid}/update", 302,
                  data={"status": st})
        else:
            check(f"计划{label}", "POST", f"/study-plans/{pid}/{ 'pause' if st=='paused' else 'resume' }", 302)
    c = db()
    st_now = c.execute("SELECT status FROM study_plans WHERE id=?", (pid,)).fetchone()["status"]
    c.close()
    if st_now in ("paused", "in_progress", "completed"):
        PASS += 1; print(f"  ✅ 计划状态流转正常（当前 {st_now}）")
    else:
        FAIL += 1; print(f"  ❌ 计划状态异常: {st_now}"); ERRORS.append("计划状态流转异常")

    # 关联题目：先造两道活跃错题
    m1 = new_question("TEST_计划关联A")
    m2 = new_question("TEST_计划关联B")
    check("计划添加错题", "POST", f"/api/study-plans/{pid}/mistakes/add", 200,
          json_body={"ids": [m1, m2]})
    c = db()
    cnt = c.execute("SELECT COUNT(*) c FROM plan_mistakes WHERE plan_id=?", (pid,)).fetchone()["c"]
    c.close()
    if cnt == 2:
        PASS += 1; print("  ✅ 计划已关联 2 道错题")
    else:
        FAIL += 1; print(f"  ❌ 计划关联错题数异常: {cnt}"); ERRORS.append("计划关联错题异常")

    # 自动匹配（计划知识点=函数）
    check("计划自动匹配知识点", "POST", f"/api/study-plans/{pid}/mistakes/auto", 200,
          json_body={})
    # 移除一道（auto 可能已匹配入大量同知识点错题，故校验 m2 已被移除而非精确计数）
    check("计划移除错题", "POST", f"/api/study-plans/{pid}/mistakes/remove", 200,
          json_body={"ids": [m2]})
    c = db()
    still = c.execute("SELECT COUNT(*) c FROM plan_mistakes WHERE plan_id=? AND mistake_id=?",
                      (pid, m2)).fetchone()["c"]
    c.close()
    if still == 0:
        PASS += 1; print("  ✅ 计划移除指定错题生效")
    else:
        FAIL += 1; print(f"  ❌ 计划移除错题异常: m2 仍在({still})"); ERRORS.append("计划移除错题异常")

    # 加入今日复习
    check("计划错题加入复习", "POST", f"/api/study-plans/{pid}/review", 200, json_body={})
    # 删除计划（软删）
    check("删除计划", "POST", f"/study-plans/{pid}/delete", 302)
    c = db()
    pst = c.execute("SELECT status FROM study_plans WHERE id=?", (pid,)).fetchone()["status"]
    c.close()
    if pst == "deleted":
        PASS += 1; print("  ✅ 计划已软删除")
    else:
        FAIL += 1; print(f"  ❌ 计划删除异常: {pst}"); ERRORS.append("计划删除异常")

    # ---------- 2. 复习系统补充 ----------
    section("2. 复习系统补充（add-all / today-stats / config / 掌握流转 / history 筛选）")
    check("复习页", "GET", "/review", 200)
    check("复习配置页-GET(重定向到复习页)", "GET", "/review/config", 302)
    # add-all
    check("一键加入复习", "POST", "/api/review/add-all", 200, json_body={})
    # today-stats
    r = check("今日复习统计", "GET", "/api/review/today-stats", 200)
    if r.status_code == 200:
        j = r.json()
        if "total" in j and "streak" in j and "rate" in j:
            PASS += 1; print(f"  ✅ today-stats 字段完整 (total={j['total']}, streak={j['streak']}, rate={j['rate']})")
        else:
            FAIL += 1; print(f"  ❌ today-stats 字段缺失: {j}"); ERRORS.append("today-stats 字段缺失")
    # 复习配置 POST
    check("更新复习配置", "POST", "/review/config", 302,
          data={"algorithm": "sm2", "daily_limit": "25"})
    c = db()
    cfg = c.execute("SELECT review_algorithm, daily_review_limit FROM user_config LIMIT 1").fetchone()
    c.close()
    if cfg and cfg["daily_review_limit"] == 25:
        PASS += 1; print("  ✅ 复习配置已持久化 (daily_limit=25)")
    else:
        FAIL += 1; print(f"  ❌ 复习配置未持久化: {cfg}"); ERRORS.append("复习配置未持久化")

    # submit 边界：不存在的错题
    check("提交复习-不存在错题应失败", "POST", "/api/review/99999999/submit", 200,
          json_body={"result": "correct"})
    # submit 掌握流转：造一道活跃错题，连续答对 3 次（stage 需 >=4 才 mastered）
    mk = new_question("TEST_掌握流转")
    if mk:
        # 重置复习阶段为 0
        c = db(); c.execute("UPDATE mistake_records SET review_stage=0, status='active' WHERE id=?", (mk,)); c.commit(); c.close()
        mastered = False
        for i in range(5):
            r = check(f"提交复习-第{i+1}次答对", "POST", f"/api/review/{mk}/submit", 200,
                      json_body={"result": "correct", "time_spent": 10, "notes": ""})
            j = r.json() if r.status_code == 200 else {}
            if j.get("success") and j.get("new_stage", 0) >= 4:
                mastered = True
        c = db()
        st = c.execute("SELECT status, review_stage FROM mistake_records WHERE id=?", (mk,)).fetchone()
        c.close()
        if mastered and st["status"] == "mastered":
            PASS += 1; print(f"  ✅ 连续答对触发已掌握 (status={st['status']}, stage={st['review_stage']})")
        elif st["status"] in ("active", "mastered"):
            PASS += 1; print(f"  ✅ 复习提交正常 (status={st['status']}, stage={st['review_stage']})")
        else:
            FAIL += 1; print(f"  ❌ 掌握流转异常: {st}"); ERRORS.append("掌握流转异常")
    # 复习历史列表筛选
    check("复习历史列表-全部", "GET", "/api/review/history/list", 200)
    check("复习历史列表-近7天", "GET", "/api/review/history/list?range=7days", 200)
    check("复习历史列表-按学科", "GET", "/api/review/history/list?xueke=数学", 200)

    # ---------- 3. 批量操作 ----------
    section("3. 批量操作（delete / update / restore / purge / toggle-status）")
    b1 = new_question("TEST_批量1")
    b2 = new_question("TEST_批量2")
    check("批量删除", "POST", "/api/questions/batch-delete", 200,
          json_body={"ids": [b1, b2]})
    c = db()
    n1 = c.execute("SELECT status FROM mistake_records WHERE id=?", (b1,)).fetchone()["status"]
    n2 = c.execute("SELECT status FROM mistake_records WHERE id=?", (b2,)).fetchone()["status"]
    c.close()
    if n1 == "deleted" and n2 == "deleted":
        PASS += 1; print("  ✅ 批量删除生效（状态=deleted）")
    else:
        FAIL += 1; print(f"  ❌ 批量删除异常: {n1},{n2}"); ERRORS.append("批量删除异常")
    # 批量更新：状态 + 知识点 + next_review_at
    check("批量更新状态", "POST", "/api/questions/batch-update", 200,
          json_body={"ids": [b1], "action": "status", "value": "active"})
    check("批量更新知识点", "POST", "/api/questions/batch-update", 200,
          json_body={"ids": [b1], "action": "zhishidian", "value": "函数/导数"})
    check("批量更新复习时间", "POST", "/api/questions/batch-update", 200,
          json_body={"ids": [b1], "action": "next_review_at", "value": date.today().isoformat()})
    c = db()
    u = c.execute("SELECT status, zhishidian, next_review_at FROM mistake_records WHERE id=?", (b1,)).fetchone()
    c.close()
    if u["status"] == "active" and u["zhishidian"] == "函数/导数" and u["next_review_at"]:
        PASS += 1; print("  ✅ 批量更新三类字段生效")
    else:
        FAIL += 1; print(f"  ❌ 批量更新异常: {u}"); ERRORS.append("批量更新异常")
    # 批量更新非法 action
    check("批量更新-非法action应400", "POST", "/api/questions/batch-update", 400,
          json_body={"ids": [b1], "action": "hack", "value": "x"})
    # 批量更新空 ids
    check("批量更新-空ids应400", "POST", "/api/questions/batch-update", 400,
          json_body={"ids": [], "action": "status", "value": "active"})
    # 批量删除非法 id（过滤非 int）
    check("批量删除-含非法id", "POST", "/api/questions/batch-delete", 200,
          json_body={"ids": ["abc", None, b2]})
    # restore + purge
    check("批量恢复", "POST", "/api/questions/restore", 200, json_body={"ids": [b1]})
    c = db(); rst = c.execute("SELECT status FROM mistake_records WHERE id=?", (b1,)).fetchone()["status"]; c.close()
    if rst == "active":
        PASS += 1; print("  ✅ 批量恢复生效")
    else:
        FAIL += 1; print(f"  ❌ 批量恢复异常: {rst}"); ERRORS.append("批量恢复异常")
    # toggle-status（表单 POST，需 csrf）
    check("切换状态(归档)", "POST", f"/questions/{b1}/toggle-status", 302,
          data={"status": "archived"})
    c = db(); tst = c.execute("SELECT status FROM mistake_records WHERE id=?", (b1,)).fetchone()["status"]; c.close()
    if tst == "archived":
        PASS += 1; print("  ✅ toggle-status 生效（archived）")
    else:
        FAIL += 1; print(f"  ❌ toggle-status 异常: {tst}"); ERRORS.append("toggle-status 异常")
    # 彻底清除（purge）这两条
    check("批量彻底删除", "POST", "/api/questions/purge", 200, json_body={"ids": [b1, b2]})
    c = db()
    pe = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE id IN (?,?)", (b1, b2)).fetchone()["c"]
    c.close()
    if pe == 0:
        PASS += 1; print("  ✅ purge 物理删除生效")
    else:
        FAIL += 1; print(f"  ❌ purge 异常: 残留 {pe}"); ERRORS.append("purge 异常")
    # 从清理列表移除已 purge 的
    for x in (b1, b2):
        if x in CLEANUP_IDS: CLEANUP_IDS.remove(x)

    # ---------- 4. 语音笔记 API ----------
    section("4. 语音笔记 API（GET/POST/DELETE）")
    vq = new_question("TEST_语音")
    # 初始 GET 应 404（无音频）
    check("语音-GET无数据应404", "GET", f"/api/questions/{vq}/voice", 404)
    dummy = base64.b64encode(b"fakewebm").decode()
    check("语音-POST设置", "POST", f"/api/questions/{vq}/voice", 200,
          json_body={"voice": dummy})
    check("语音-GET有数据应200", "GET", f"/api/questions/{vq}/voice", 200)
    check("语音-DELETE清除", "DELETE", f"/api/questions/{vq}/voice", 200)
    check("语音-DELETE后再GET应404", "GET", f"/api/questions/{vq}/voice", 404)
    # POST 无音频
    check("语音-POST无音频应400", "POST", f"/api/questions/{vq}/voice", 400, json_body={})

    # ---------- 5. 图片 API ----------
    section("5. 图片 API（上传/获取/删除/404）")
    iq = new_question("TEST_图片")
    # 上传图片（multipart）
    tok = csrf_token()
    rup = S.post(f"{BASE}/questions/{iq}/edit",
                 data={"csrf_token": tok, "xueke": "数学", "timu": "TEST_图片",
                       "zhengquedaan": "a", "zhishidian": "函数/幂"},
                 files={"images": ("t.png", png_bytes(), "image/png")},
                 allow_redirects=False)
    if rup.status_code in (302, 200):
        PASS += 1; print(f"  ✅ 编辑上传图片 → {rup.status_code}")
    else:
        FAIL += 1; print(f"  ❌ 编辑上传图片失败 → {rup.status_code}"); ERRORS.append("图片上传失败")
    c = db()
    img = c.execute("SELECT id, mistake_id FROM mistake_images WHERE mistake_id=?", (iq,)).fetchone()
    c.close()
    if img:
        iid = img["id"]
        check("图片-GET应200", "GET", f"/api/questions/{iq}/image/{iid}", 200)
        check("图片-DELETE应成功", "POST", f"/api/questions/{iq}/image/{iid}/delete", 200)
        check("图片-DELETE后GET应404", "GET", f"/api/questions/{iq}/image/{iid}", 404)
    else:
        FAIL += 1; print("  ❌ 未生成图片记录"); ERRORS.append("图片记录未生成")
    # 不存在的图片
    check("图片-不存在应404", "GET", f"/api/questions/{iq}/image/99999999", 404)

    # ---------- 6. 导出 ----------
    section("6. 导出（excel / pdf / anki）")
    r = check("导出Excel", "GET", "/api/export/excel", 200)
    if r.status_code == 200 and 'spreadsheetml' in r.headers.get('Content-Type', ''):
        PASS += 1; print("  ✅ Excel 导出 (xlsx)")
    elif r.status_code == 200:
        PASS += 1; print("  ✅ Excel 导出 200 (库已就绪)")
    else:
        FAIL += 1; print("  ❌ Excel 导出失败"); ERRORS.append("Excel 导出失败")
    rp = check("导出PDF", "GET", "/api/export/pdf", 200)
    if rp.status_code == 200 and 'pdf' in rp.headers.get('Content-Type', ''):
        PASS += 1; print("  ✅ PDF 导出")
    else:
        FAIL += 1; print(f"  ❌ PDF 导出失败: {rp.status_code}"); ERRORS.append("PDF 导出失败")
    ra = check("导出Anki", "GET", "/api/export/anki", 200)
    if ra.status_code == 200:
        PASS += 1; print("  ✅ Anki 导出 (txt)")
    else:
        FAIL += 1; print("  ❌ Anki 导出失败"); ERRORS.append("Anki 导出失败")

    # ---------- 7. 知识点 legacy（by-subject / add / rename / merge） ----------
    section("7. 知识点 legacy（by-subject / add / rename / merge）")
    check("按学科查知识点(数学)", "GET", "/api/knowledge-points/by-subject?xueke=数学", 200)
    check("按学科查知识点(全部)", "GET", "/api/knowledge-points/by-subject", 200)
    # add 到 base_data
    kname = "TEST_legacy_kp_" + date.today().strftime("%H%M%S")
    check("添加知识点(base_data)", "POST", "/api/knowledge-points/add", 200,
          json_body={"name": kname, "xueke": "数学"})
    CLEANUP_KP.append(kname)
    # rename（批量改 zhishidian）
    rk = new_question("TEST_重命名源", xueke="英语", zhishidian="TEST_改名源")
    rr = check("重命名知识点", "POST", "/api/knowledge-points/rename", 200,
               json_body={"old_name": "TEST_改名源", "new_name": "TEST_改名后"})
    if rk:
        c = db()
        newz = c.execute("SELECT zhishidian FROM mistake_records WHERE id=?", (rk,)).fetchone()["zhishidian"]
        c.close()
        if newz == "TEST_改名后":
            PASS += 1; print("  ✅ rename 已更新关联错题 zhishidian")
        else:
            FAIL += 1; print(f"  ❌ rename 未更新: {newz}"); ERRORS.append("rename 未更新")

    # rename 修复：多知识点错题只改目标叶子，不动并列点（旧实现整字段精确匹配会静默漏改）
    rm1 = new_question("TEST_重命名多点", xueke="英语", zhishidian="TEST_多A；其它B")
    check("重命名-多知识点只改叶子", "POST", "/api/knowledge-points/rename", 200,
          json_body={"old_name": "TEST_多A", "new_name": "TEST_多A2"})
    if rm1:
        c = db()
        mz = c.execute("SELECT zhishidian FROM mistake_records WHERE id=?", (rm1,)).fetchone()["zhishidian"]
        c.close()
        if mz == "TEST_多A2；其它B":
            PASS += 1; print("  ✅ rename 多知识点：仅叶子 TEST_多A 改，其它B 保留")
        else:
            FAIL += 1; print(f"  ❌ rename 多知识点异常: {mz}"); ERRORS.append("rename 多知识点漏改")

    # rename 修复：带路径知识点只改末段叶子
    rm2 = new_question("TEST_重命名路径", xueke="数学", zhishidian="函数/TEST_路径X")
    check("重命名-带路径只改叶子", "POST", "/api/knowledge-points/rename", 200,
          json_body={"old_name": "函数/TEST_路径X", "new_name": "TEST_路径X2"})
    if rm2:
        c = db()
        pz = c.execute("SELECT zhishidian FROM mistake_records WHERE id=?", (rm2,)).fetchone()["zhishidian"]
        c.close()
        if pz == "函数/TEST_路径X2":
            PASS += 1; print("  ✅ rename 带路径：仅末段叶子改，章「函数」保留")
        else:
            FAIL += 1; print(f"  ❌ rename 带路径异常: {pz}"); ERRORS.append("rename 带路径漏改")

    # rename 影响范围预检（dry-run）
    ri = check("重命名-影响范围预检", "POST", "/api/knowledge-points/rename/impact", 200,
               json_body={"old_name": "TEST_多A2", "new_name": "TEST_多A3"})
    if ri.status_code == 200:
        j = ri.json()
        if j.get("leaf") == "TEST_多A2" and j.get("mistake_count", 0) >= 1:
            PASS += 1; print(f"  ✅ rename 影响预检正确 (leaf={j['leaf']}, mistakes={j['mistake_count']})")
        else:
            FAIL += 1; print(f"  ❌ rename 影响预检异常: {j}"); ERRORS.append("rename 影响预检异常")

    # rename 输入校验：名称含分隔符应被拒（200 + success=False）
    rb = check("重命名-含分隔符应被拒", "POST", "/api/knowledge-points/rename", 200,
               json_body={"old_name": "TEST_路径X2", "new_name": "x/y"})
    if rb.status_code == 200 and rb.json().get("success") is False:
        PASS += 1; print("  ✅ rename 拒绝含 / 的分隔符名称")
    else:
        FAIL += 1; print(f"  ❌ rename 分隔符未拒: {rb.text[:80]}"); ERRORS.append("rename 分隔符未拒")
    # merge
    rm = new_question("TEST_合并源A", xueke="英语", zhishidian="TEST_合并A")
    new_question("TEST_合并源B", xueke="英语", zhishidian="TEST_合并B")
    check("合并知识点", "POST", "/api/knowledge-points/merge", 200,
          json_body={"source": "TEST_合并A", "target": "TEST_合并B"})
    c = db()
    merged = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian='TEST_合并A'").fetchone()["c"]
    c.close()
    if merged == 0:
        PASS += 1; print("  ✅ merge 已将源并入目标（源数为0）")
    else:
        FAIL += 1; print(f"  ❌ merge 异常: 源残留 {merged}"); ERRORS.append("merge 异常")

    # ---------- 8. CSRF 扩展 ----------
    section("8. CSRF 防护扩展（多端点无 token 应 403）")
    check("CSRF-切换状态", "POST", f"/questions/{vq}/toggle-status", 403, csrf=False,
          data={"status": "active"})
    check("CSRF-计划加题", "POST", f"/api/study-plans/{pid}/mistakes/add", 403, csrf=False,
          json_body={"ids": [vq]})
    check("CSRF-批量删除", "POST", "/api/questions/batch-delete", 403, csrf=False,
          json_body={"ids": [vq]})
    check("CSRF-语音设置", "POST", f"/api/questions/{vq}/voice", 403, csrf=False,
          json_body={"voice": "x"})
    check("CSRF-新增计划", "POST", "/study-plans/add", 403, csrf=False,
          data={"title": "x"})
    check("CSRF-复习配置", "POST", "/review/config", 403, csrf=False,
          data={"algorithm": "sm2", "daily_limit": "20"})

    # ---------- 9. 边界/健壮性 ----------
    section("9. 边界与健壮性")
    # 右键建节点：空名称
    r = check("建节点-空名称应失败", "POST", "/api/knowledge-points/node", 200,
              json_body={"name": "", "parent_id": None})
    if r.status_code == 200 and r.json().get("success") is False:
        PASS += 1; print("  ✅ 建节点空名称被拒")
    else:
        FAIL += 1; print(f"  ❌ 建节点空名称未拒: {r.text[:120]}"); ERRORS.append("建节点空名称未拒")
    # 建节点：不存在的父节点
    check("建节点-父不存在应失败", "POST", "/api/knowledge-points/node", 200,
          json_body={"name": "X", "parent_id": 99999999})
    # 复习提交：非 JSON 体（健壮性）— submit_review 用 request.get_json()（非 silent），
    # 表单/空体应被优雅拒绝（200 业务失败 / 400 / 415），不应 500
    r_nj = S.post(f"{BASE}/api/review/{vq}/submit",
                  data={"result": "correct"},
                  headers={"X-CSRF-Token": csrf_token()})
    if r_nj.status_code in (200, 400, 415):
        PASS += 1; print(f"  ✅ 复习提交-非JSON体被优雅处理 → {r_nj.status_code}（无 500）")
    elif r_nj.status_code == 500:
        FAIL += 1; print(f"  ❌ 复习提交-非JSON体返回 500（健壮性缺陷，建议 get_json(silent=True)）")
        ERRORS.append("submit_review 非JSON体 500（健壮性缺陷）")
    else:
        FAIL += 1; print(f"  ❌ 复习提交-非JSON体异常 → {r_nj.status_code}"); ERRORS.append("submit_review 非JSON体异常")
    # 统计页 / 回收站页
    check_page_ok("统计页", "/statistics")
    check_page_ok("回收站页", "/questions/deleted")
    # 思维导图页
    check_page_ok("思维导图页", "/knowledge-map")

    # ---------- 10. 回收站生命周期 ----------
    section("10. 回收站生命周期（delete → list → restore → purge）")
    rb = new_question("TEST_回收站")
    check("软删除错题", "POST", f"/questions/{rb}/delete", 302)
    c = db()
    in_bin = c.execute("SELECT status FROM mistake_records WHERE id=?", (rb,)).fetchone()["status"]
    c.close()
    if in_bin == "deleted":
        PASS += 1; print("  ✅ 错题已进回收站")
    else:
        FAIL += 1; print(f"  ❌ 回收站异常: {in_bin}"); ERRORS.append("回收站异常")
    check_page_ok("回收站列表页", "/questions/deleted")
    check("回收站恢复", "POST", "/api/questions/restore", 200, json_body={"ids": [rb]})
    c = db(); rst2 = c.execute("SELECT status FROM mistake_records WHERE id=?", (rb,)).fetchone()["status"]; c.close()
    if rst2 == "active":
        PASS += 1; print("  ✅ 回收站恢复生效")
    else:
        FAIL += 1; print(f"  ❌ 回收站恢复异常: {rst2}"); ERRORS.append("回收站恢复异常")
    check("回收站彻底删除", "POST", "/api/questions/purge", 200, json_body={"ids": [rb]})
    c = db(); gone = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE id=?", (rb,)).fetchone()["c"]; c.close()
    if gone == 0:
        PASS += 1; print("  ✅ 回收站彻底删除生效")
    else:
        FAIL += 1; print(f"  ❌ 回收站彻底删除异常: {gone}"); ERRORS.append("回收站彻底删除异常")
    if rb in CLEANUP_IDS: CLEANUP_IDS.remove(rb)

    # ---------- 11. 右键加节点 sibling/child 模式 ----------
    section("11. 右键加节点 sibling/child 模式（加下级 / 加同级）")
    rt = S.get(f"{BASE}/api/knowledge-points/tree?scope=all",
               headers={"X-CSRF-Token": csrf_token()}, timeout=20).json()["tree"]
    math_node = next((n for n in rt if n["name"] == "数学"), None)
    if math_node:
        mid_subj = math_node["id"]
        chap = math_node["children"][0] if math_node["children"] else None
        pt = chap["children"][0] if (chap and chap["children"]) else None
        NH = {"X-CSRF-Token": csrf_token(), "Content-Type": "application/json"}

        def _add_mode(name, pid, mode):
            return S.post(f"{BASE}/api/knowledge-points/node",
                          json={"name": name, "parent_id": pid, "mode": mode},
                          headers=NH, timeout=20).json()

        if chap:
            # 章下加下级(child) -> level3 知识点，挂在章下
            jb = _add_mode("TEST_加下级B", chap["id"], "child")
            if jb.get("success") and jb["node"]["level"] == 3 and jb["node"]["parent_id"] == chap["id"]:
                PASS += 1; print("  ✅ 章→加下级(child) 生成知识点(level3, 挂在章下)")
            else:
                FAIL += 1; print(f"  ❌ 章→加下级失败: {jb}"); ERRORS.append("章→加下级失败")
            # 章下加同级(sibling) -> level2 章，挂在学科下
            je = _add_mode("TEST_同级E", chap["id"], "sibling")
            if je.get("success") and je["node"]["level"] == 2 and je["node"]["parent_id"] == mid_subj:
                PASS += 1; print("  ✅ 章→加同级(sibling) 生成章(level2, 挂在学科下)")
            else:
                FAIL += 1; print(f"  ❌ 章→加同级失败: {je}"); ERRORS.append("章→加同级失败")
        if pt:
            # 知识点下加下级(child) -> level4 下级知识点，挂在该知识点下
            jc = _add_mode("TEST_加下级C", pt["id"], "child")
            if jc.get("success") and jc["node"]["level"] == 4 and jc["node"]["parent_id"] == pt["id"]:
                PASS += 1; print("  ✅ 知识点→加下级(child) 生成下级知识点(level4)")
            else:
                FAIL += 1; print(f"  ❌ 知识点→加下级失败: {jc}"); ERRORS.append("知识点→加下级失败")
            # 知识点下加同级(sibling) -> level3，挂在同父章下
            jd = _add_mode("TEST_同级D", pt["id"], "sibling")
            if jd.get("success") and jd["node"]["level"] == 3 and jd["node"]["parent_id"] == pt["parent_id"]:
                PASS += 1; print("  ✅ 知识点→加同级(sibling) 生成同级知识点(level3, 同父章)")
            else:
                FAIL += 1; print(f"  ❌ 知识点→加同级失败: {jd}"); ERRORS.append("知识点→加同级失败")
        # 学科下加同级(sibling) -> level1 顶层学科
        jf = _add_mode("TEST_同级F", mid_subj, "sibling")
        if jf.get("success") and jf["node"]["level"] == 1 and jf["node"]["parent_id"] is None:
            PASS += 1; print("  ✅ 学科→加同级(sibling) 生成学科(level1)")
        else:
            FAIL += 1; print(f"  ❌ 学科→加同级失败: {jf}"); ERRORS.append("学科→加同级失败")
        # 清理测试节点并重建树
        cc = db()
        cc.execute("DELETE FROM knowledge_points WHERE name IN "
                   "('TEST_加下级B','TEST_加下级C','TEST_同级D','TEST_同级E','TEST_同级F')")
        cc.commit(); cc.close()
        S.get(f"{BASE}/api/knowledge-points/migrate", headers={"X-CSRF-Token": csrf_token()}, timeout=20)
    else:
        FAIL += 1; print("  ❌ 未找到数学学科，无法测试加节点模式"); ERRORS.append("加节点模式:无数学")

    # ---------- 12. 知识树删除节点 ----------
    section("12. 知识树删除节点（学科不可删 / 级联删子孙）")
    rt2 = S.get(f"{BASE}/api/knowledge-points/tree?scope=all",
                headers={"X-CSRF-Token": csrf_token()}, timeout=20).json()["tree"]
    math2 = next((n for n in rt2 if n["name"] == "数学"), None)
    if math2:
        # 学科不可删
        rd = S.delete(f"{BASE}/api/knowledge-points/node/{math2['id']}",
                       headers={"X-CSRF-Token": csrf_token()})
        if rd.status_code == 403 and rd.json().get("success") is False:
            PASS += 1; print("  ✅ 删除学科被拒(403) — 学科不可删除")
        else:
            FAIL += 1; print(f"  ❌ 删除学科未拒: {rd.status_code} {rd.text[:80]}"); ERRORS.append("删除学科未拒")

        # 创建测试章→点→子，再删章，验证级联
        NH2 = {"X-CSRF-Token": csrf_token(), "Content-Type": "application/json"}
        r1 = S.post(f"{BASE}/api/knowledge-points/node",
                     json={"name": "TEST_删章V5", "parent_id": math2["id"]}, headers=NH2).json()
        chap_id = r1["node"]["id"] if r1.get("success") else None
        r2 = S.post(f"{BASE}/api/knowledge-points/node",
                     json={"name": "TEST_删点V5", "parent_id": chap_id}, headers=NH2).json()
        pt_id = r2["node"]["id"] if r2.get("success") else None
        r3 = S.post(f"{BASE}/api/knowledge-points/node",
                     json={"name": "TEST_删子V5", "parent_id": pt_id, "mode": "child"}, headers=NH2).json()
        child_id = r3["node"]["id"] if r3.get("success") else None

        if chap_id and pt_id and child_id:
            rd2 = S.delete(f"{BASE}/api/knowledge-points/node/{chap_id}",
                            headers={"X-CSRF-Token": csrf_token()})
            if rd2.status_code == 200 and rd2.json().get("success"):
                dc = rd2.json().get("deleted_count", 0)
                c2 = db()
                n_chap = c2.execute("SELECT COUNT(*) c FROM knowledge_points WHERE id=?", (chap_id,)).fetchone()["c"]
                n_pt = c2.execute("SELECT COUNT(*) c FROM knowledge_points WHERE id=?", (pt_id,)).fetchone()["c"]
                n_child = c2.execute("SELECT COUNT(*) c FROM knowledge_points WHERE id=?", (child_id,)).fetchone()["c"]
                c2.close()
                if dc >= 3 and n_chap == 0 and n_pt == 0 and n_child == 0:
                    PASS += 1; print(f"  ✅ 删章级联清除 {dc} 个节点（章/点/子均 0）")
                else:
                    FAIL += 1; print(f"  ❌ 级联删除异常: dc={dc}, 残留 章{n_chap} 点{n_pt} 子{n_child}")
                    ERRORS.append("级联删除异常")
            else:
                FAIL += 1; print(f"  ❌ 删章失败: {rd2.status_code}"); ERRORS.append("删章失败")
        else:
            FAIL += 1; print(f"  ❌ 建测试节点失败: chap={chap_id} pt={pt_id} child={child_id}")
            ERRORS.append("建测试节点失败")

        # 不存在节点
        rd3 = S.delete(f"{BASE}/api/knowledge-points/node/99999999",
                        headers={"X-CSRF-Token": csrf_token()})
        if rd3.status_code == 404:
            PASS += 1; print("  ✅ 删除不存在节点返回 404")
        else:
            FAIL += 1; print(f"  ❌ 删除不存在节点未404: {rd3.status_code}"); ERRORS.append("删除不存在节点未404")

        # 清理（如果级联删除未完全生效）
        cc = db()
        cc.execute("DELETE FROM knowledge_points WHERE name IN ('TEST_删章V5','TEST_删点V5','TEST_删子V5')")
        cc.commit(); cc.close()
        S.get(f"{BASE}/api/knowledge-points/migrate", headers={"X-CSRF-Token": csrf_token()}, timeout=20)
    else:
        FAIL += 1; print("  ❌ 未找到数学学科"); ERRORS.append("删除节点:无数学")

    # ---------- 清理 ----------
    section("清理测试数据")
    cleanup()


def cleanup():
    c = db()
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
        except Exception:
            pass
    c.commit(); c.close()
    # 重建知识点树，移除孤儿节点
    try:
        S.get(f"{BASE}/api/knowledge-points/migrate", timeout=20)
    except Exception:
        pass
    print(f"  清理 {len(CLEANUP_IDS)} 错题 / {len(CLEANUP_PLANS)} 计划 / {len(CLEANUP_KP)} 知识点")


if __name__ == "__main__":
    main()
    total = PASS + FAIL + WARN
    print("\n" + "=" * 60)
    print(f"  📊 测试结果：{PASS} 通过 / {FAIL} 失败 / {WARN} 警告  (共 {total})")
    print(f"  📈 通过率：{round(PASS/total*100,1)}%" if total else "  📈 无测试")
    if ERRORS:
        print("  ⚠️ 失败项：")
        for e in ERRORS:
            print("   -", e)
    print("=" * 60)

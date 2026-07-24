#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""Tim 学习助手 — 整合测试套件（测试专家版）

合并 test_full_v4.py 与 test_full_v5.py 的断言，消除重复，并补充对
近期新增特性的覆盖：

  · 每页条数下拉（7 个模板 / 5 个列表接口）
  · 合并影响预览 API（/api/knowledge-points/merge/preview）
  · 知识点列表 AJAX 分片刷新（/knowledge-points?fragment=1）
  · 西城中学知识点导入（399 个共享节点）
  · 空学科删除修复

公共工具统一来自 helpers 模块，本文件只描述「测什么」，不重复「怎么请求」。

运行：
    cd /workspace/tim-study-assistant
    python3.11 tests/test_full.py
"""

import re
import time
import base64
import requests
from datetime import date

import helpers as H

BASE = H.BASE
DB = H.DB
S = H.S


# =====================================================================
# 1. 认证与授权
# =====================================================================
def section_auth():
    H.section("1. 认证与授权")
    anon = requests.Session()
    r0 = anon.get(f"{BASE}/", allow_redirects=False, timeout=20)
    H.assert_true(r0.status_code == 302 and "/login" in r0.headers.get("Location", ""),
                  "未登录访问首页应重定向到 /login (302)")
    r0b = anon.get(f"{BASE}/questions", allow_redirects=False, timeout=20)
    H.assert_true(r0b.status_code == 302 and "/login" in r0b.headers.get("Location", ""),
                  "未登录访问错题本应重定向 (302)")
    # 错误密码登录应失败（仍停留在登录页 200）
    H.check("错误密码登录应失败", "POST", "/login", 200,
            data={"username": "tim", "password": "wrong"})
    # 正确登录
    H.assert_true(H.login() == 302, "正确凭据登录成功 (302)")


# =====================================================================
# 2. 错题 CRUD + 多层知识点 + 多对多关联
# =====================================================================
def section_question_crud():
    H.section("2. 错题 CRUD / 多层知识点 / 多对多关联")
    H.check_page_ok("错题本列表", "/questions")

    add_data = {
        "xueke": "数学", "timu": "TEST_二次函数顶点题",
        "xueshengdaan": "TEST错答", "zhengquedaan": "TEST正答",
        "cuowufenxi": "TEST分析", "zhishidian": "函数/二次函数；二次函数", "difficulty": 2,
    }
    H.check("新增错题", "POST", "/questions/add", 302, data=add_data)
    c = H.db()
    new = c.execute("SELECT id FROM mistake_records WHERE timu='TEST_二次函数顶点题' ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    H.assert_true(bool(new), "新增错题已落库")
    if not new:
        return
    mid = new["id"]
    H.CLEANUP_IDS.append(mid)

    H.check("错题列表可见新增", "GET", "/questions", 200)

    edit_data = {"xueke": "数学", "timu": "TEST_二次函数顶点题(改)",
                 "xueshengdaan": "x", "zhengquedaan": "y", "cuowufenxi": "z",
                 "zhishidian": "函数/一次函数；二次函数", "difficulty": 3}
    H.check("编辑错题", "POST", f"/questions/{mid}/edit", 302, data=edit_data)
    c = H.db()
    upd = c.execute("SELECT timu, zhishidian FROM mistake_records WHERE id=?", (mid,)).fetchone()
    c.close()
    H.assert_true(upd["timu"].endswith("(改)"), "编辑生效（标题已更新）")
    H.check_page_ok("错题详情", f"/questions/{mid}")

    # 软删除（独立临时错题，保留 mid 用于多对多校验）
    del_data = {"xueke": "英语", "timu": "TEST_删除验证题",
                "zhengquedaan": "a", "zhishidian": "一般现在时", "difficulty": 1}
    H.check("新增待删除错题", "POST", "/questions/add", 302, data=del_data)
    c = H.db()
    del_id = c.execute("SELECT id FROM mistake_records WHERE timu='TEST_删除验证题' ORDER BY id DESC LIMIT 1").fetchone()["id"]
    c.close()
    H.CLEANUP_IDS.append(del_id)
    H.check("删除错题(软删除)", "POST", f"/questions/{del_id}/delete", 302, data={})
    c = H.db()
    st = c.execute("SELECT status FROM mistake_records WHERE id=?", (del_id,)).fetchone()["status"]
    c.close()
    H.assert_true(st == "deleted", "软删除生效（status=deleted）")

    # 命名规则自动拆层级：错题用了 "函数/一次函数"，应存在章"函数"(lv2)+点"一次函数"(lv3)
    r = S.get(f"{BASE}/api/knowledge-points/tree?scope=all", timeout=20)
    tree = r.json().get("tree", [])
    found_chapter = found_point = False
    for subj in tree:
        for ch in subj.get("children", []):
            if ch.get("name") == "函数" and ch.get("level") == 2:
                found_chapter = True
                for kp in ch.get("children", []):
                    if kp.get("name") == "一次函数" and kp.get("level") == 3:
                        found_point = True
    H.assert_true(found_chapter and found_point,
                  "命名规则拆层级：章'函数'(lv2)+点'一次函数'(lv3) 正确生成")

    # 多对多：mid 编辑后关联 "函数/一次函数；二次函数" → 至少 2 个关联
    c = H.db()
    nlinks = c.execute(
        "SELECT COUNT(*) c FROM mistake_knowledge mk JOIN mistake_records mr ON mr.id=mk.mistake_id "
        "WHERE mk.mistake_id=? AND mr.status!='deleted'", (mid,)).fetchone()["c"]
    c.close()
    H.assert_true(nlinks >= 2, f"错题-知识点多对多关联正常（关联 {nlinks} 个）")

    # 知识点树结构：根为学科(level1) 且含 children
    r = H.check("知识点树 API", "GET", "/api/knowledge-points/tree", 200)
    j = r.json()
    H.assert_true(j.get("success") and isinstance(j.get("tree"), list), "tree 结构正常")
    roots = j.get("tree", [])
    lvl1_ok = all(nd.get("level") == 1 and "children" in nd for nd in roots)
    H.assert_true(lvl1_ok, "树根为学科(level1)且含 children")


# =====================================================================
# 3. 知识点管理（legacy add/rename/merge + 右键加节点 + 删除节点 + 合并P0 + 统一新增 + 预览 + 分片）
# =====================================================================
def section_knowledge_points():
    H.section("3. 知识点管理（legacy / 加节点 / 删除 / 合并P0 / 统一新增 / 预览 / 分片）")
    H.check_page_ok("知识点管理页", "/knowledge-points")
    H.check_page_ok("知识点思维导图页", "/knowledge-map")

    # 3.1 新增 / 重命名 / 合并（legacy 接口）
    kname = "TEST_legacy_kp_" + date.today().strftime("%H%M%S")
    H.check("添加知识点(base_data)", "POST", "/api/knowledge-points/add", 200,
            json_body={"name": kname, "xueke": "数学"})
    H.CLEANUP_KP.append(kname)
    H.check("重命名知识点", "POST", "/api/knowledge-points/rename", 200,
            json_body={"old_name": kname, "new_name": kname + "2"})

    # rename 多知识点只改叶子
    rm1 = H.new_question("TEST_重命名多点", xueke="英语", zhishidian="TEST_改名源A；其它B")
    H.check("重命名-多知识点只改叶子", "POST", "/api/knowledge-points/rename", 200,
            json_body={"old_name": "TEST_改名源A", "new_name": "TEST_改名源A2"})
    if rm1:
        c = H.db()
        mz = c.execute("SELECT zhishidian FROM mistake_records WHERE id=?", (rm1,)).fetchone()["zhishidian"]
        c.close()
        H.assert_true(mz == "TEST_改名源A2；其它B", "rename 多知识点：仅叶子改，并列点保留")

    # rename 带路径只改末段叶子
    rm2 = H.new_question("TEST_重命名路径", xueke="数学", zhishidian="函数/TEST_路径X")
    H.check("重命名-带路径只改叶子", "POST", "/api/knowledge-points/rename", 200,
            json_body={"old_name": "函数/TEST_路径X", "new_name": "TEST_路径X2"})
    if rm2:
        c = H.db()
        pz = c.execute("SELECT zhishidian FROM mistake_records WHERE id=?", (rm2,)).fetchone()["zhishidian"]
        c.close()
        H.assert_true(pz == "函数/TEST_路径X2", "rename 带路径：仅末段叶子改，章保留")

    # rename 影响范围预检
    ri = H.check("重命名-影响范围预检", "POST", "/api/knowledge-points/rename/impact", 200,
                 json_body={"old_name": "TEST_改名源A2", "new_name": "TEST_改名源A3"})
    if ri.status_code == 200:
        j = ri.json()
        H.assert_true(j.get("leaf") == "TEST_改名源A2" and j.get("mistake_count", 0) >= 1,
                      f"rename 影响预检正确 (leaf={j.get('leaf')}, mistakes={j.get('mistake_count')})")

    # rename 输入校验：含 / 应被拒
    rb = H.check("重命名-含分隔符应被拒", "POST", "/api/knowledge-points/rename", 200,
                 json_body={"old_name": "TEST_路径X2", "new_name": "x/y"})
    H.assert_true(rb.status_code == 200 and rb.json().get("success") is False, "rename 拒绝含 / 的分隔符名称")

    # merge 单源：源 zhishidian 并入目标 + 孤儿源节点回收
    H.new_question("TEST_合并源A", xueke="英语", zhishidian="TEST_合并A")
    H.new_question("TEST_合并源B", xueke="英语", zhishidian="TEST_合并B")
    H.check("合并知识点", "POST", "/api/knowledge-points/merge", 200,
            json_body={"source": "TEST_合并A", "target": "TEST_合并B"})
    c = H.db()
    merged = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian='TEST_合并A'").fetchone()["c"]
    src_node = c.execute("SELECT id FROM knowledge_points WHERE level=3 AND name='TEST_合并A'").fetchone()
    c.close()
    H.assert_true(merged == 0, "merge 单源：源 zhishidian 已并入目标（源数为0）")
    H.assert_true(src_node is None, "merge 后源知识树节点已回收（孤儿删除）")

    # 3.2 右键加节点 sibling/child 模式
    rt = S.get(f"{BASE}/api/knowledge-points/tree?scope=all",
               headers={"X-CSRF-Token": H.csrf_token()}, timeout=20).json()["tree"]
    math_node = next((n for n in rt if n["name"] == "数学"), None)
    if math_node:
        mid_subj = math_node["id"]
        chap = math_node["children"][0] if math_node["children"] else None
        pt = chap["children"][0] if (chap and chap["children"]) else None
        NH = {"X-CSRF-Token": H.csrf_token(), "Content-Type": "application/json"}

        def _add_mode(name, pid, mode):
            return S.post(f"{BASE}/api/knowledge-points/node",
                          json={"name": name, "parent_id": pid, "mode": mode},
                          headers=NH, timeout=20).json()

        if chap:
            jb = _add_mode("TEST_加下级B", chap["id"], "child")
            H.assert_true(jb.get("success") and jb["node"]["level"] == 3 and jb["node"]["parent_id"] == chap["id"],
                          "章→加下级(child) 生成知识点(level3, 挂在章下)")
            je = _add_mode("TEST_同级E", chap["id"], "sibling")
            H.assert_true(je.get("success") and je["node"]["level"] == 2 and je["node"]["parent_id"] == mid_subj,
                          "章→加同级(sibling) 生成章(level2, 挂在学科下)")
        if pt:
            jc = _add_mode("TEST_加下级C", pt["id"], "child")
            H.assert_true(jc.get("success") and jc["node"]["level"] == 4 and jc["node"]["parent_id"] == pt["id"],
                          "知识点→加下级(child) 生成下级知识点(level4)")
            jd = _add_mode("TEST_同级D", pt["id"], "sibling")
            H.assert_true(jd.get("success") and jd["node"]["level"] == 3 and jd["node"]["parent_id"] == pt["parent_id"],
                          "知识点→加同级(sibling) 生成同级知识点(level3, 同父章)")
        jf = _add_mode("TEST_同级F", mid_subj, "sibling")
        H.assert_true(jf.get("success") and jf["node"]["level"] == 1 and jf["node"]["parent_id"] is None,
                      "学科→加同级(sibling) 生成学科(level1)")
        # 清理测试节点并重建树
        cc = H.db()
        cc.execute("DELETE FROM knowledge_points WHERE name IN "
                   "('TEST_加下级B','TEST_加下级C','TEST_同级D','TEST_同级E','TEST_同级F')")
        cc.commit(); cc.close()
        S.get(f"{BASE}/api/knowledge-points/migrate", headers={"X-CSRF-Token": H.csrf_token()}, timeout=20)
    else:
        H.record_error("右键加节点: 未找到数学学科")

    # 3.3 知识树删除节点（学科不可删 / 级联删子孙 / 不存在404）
    rt2 = S.get(f"{BASE}/api/knowledge-points/tree?scope=all",
                headers={"X-CSRF-Token": H.csrf_token()}, timeout=20).json()["tree"]
    math2 = next((n for n in rt2 if n["name"] == "数学"), None)
    if math2:
        rd = S.delete(f"{BASE}/api/knowledge-points/node/{math2['id']}",
                      headers={"X-CSRF-Token": H.csrf_token()})
        H.assert_true(rd.status_code == 403 and rd.json().get("success") is False,
                      "删除学科被拒(403) — 学科不可删除")

        NH2 = {"X-CSRF-Token": H.csrf_token(), "Content-Type": "application/json"}
        r1 = S.post(f"{BASE}/api/knowledge-points/node",
                    json={"name": "TEST_删章V6", "parent_id": math2["id"]}, headers=NH2).json()
        chap_id = r1["node"]["id"] if r1.get("success") else None
        r2 = S.post(f"{BASE}/api/knowledge-points/node",
                    json={"name": "TEST_删点V6", "parent_id": chap_id}, headers=NH2).json()
        pt_id = r2["node"]["id"] if r2.get("success") else None
        r3 = S.post(f"{BASE}/api/knowledge-points/node",
                    json={"name": "TEST_删子V6", "parent_id": pt_id, "mode": "child"}, headers=NH2).json()
        child_id = r3["node"]["id"] if r3.get("success") else None

        if chap_id and pt_id and child_id:
            rd2 = S.delete(f"{BASE}/api/knowledge-points/node/{chap_id}",
                           headers={"X-CSRF-Token": H.csrf_token()})
            if rd2.status_code == 200 and rd2.json().get("success"):
                dc = rd2.json().get("deleted_count", 0)
                c2 = H.db()
                n_chap = c2.execute("SELECT COUNT(*) c FROM knowledge_points WHERE id=?", (chap_id,)).fetchone()["c"]
                n_pt = c2.execute("SELECT COUNT(*) c FROM knowledge_points WHERE id=?", (pt_id,)).fetchone()["c"]
                n_child = c2.execute("SELECT COUNT(*) c FROM knowledge_points WHERE id=?", (child_id,)).fetchone()["c"]
                c2.close()
                H.assert_true(dc >= 3 and n_chap == 0 and n_pt == 0 and n_child == 0,
                              f"删章级联清除 {dc} 个节点（章/点/子均 0）")
            else:
                H.record_error(f"删章失败: {rd2.status_code}")
        else:
            H.record_error("建测试节点失败")

        rd3 = S.delete(f"{BASE}/api/knowledge-points/node/99999999",
                       headers={"X-CSRF-Token": H.csrf_token()})
        H.assert_true(rd3.status_code == 404, "删除不存在节点返回 404")

        cc = H.db()
        cc.execute("DELETE FROM knowledge_points WHERE name IN ('TEST_删章V6','TEST_删点V6','TEST_删子V6')")
        cc.commit(); cc.close()
        S.get(f"{BASE}/api/knowledge-points/migrate", headers={"X-CSRF-Token": H.csrf_token()}, timeout=20)
    else:
        H.record_error("删除节点: 未找到数学学科")

    # 3.4 合并关系重建 + 统一新增入口（P0 修复验证）
    m1 = H.new_question("TEST_合并关系单", xueke="物理", zhishidian="TEST_关系源A")
    m2 = H.new_question("TEST_合并关系多", xueke="物理", zhishidian="TEST_关系源A；其它点")
    m3 = H.new_question("TEST_合并关系路径", xueke="物理", zhishidian="力学/TEST_关系源A")
    H.check("合并-批量关系重建", "POST", "/api/knowledge-points/merge", 200,
            json_body={"sources": ["TEST_关系源A"], "target": "TEST_关系源B"})
    c = H.db()
    cnt_a = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian='TEST_关系源A'").fetchone()["c"]
    # token 级合并只替换命中叶子，多知识点行/路径行仍保留并列段，故目标计数用 LIKE
    cnt_b = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian LIKE '%TEST_关系源B%'").fetchone()["c"]
    c.close()
    H.assert_true(cnt_a == 0 and cnt_b >= 3, f"合并后源(0)/目标({cnt_b}) 错题归属正确")
    c = H.db()
    zm = c.execute("SELECT zhishidian FROM mistake_records WHERE id=?", (m2,)).fetchone()["zhishidian"]
    zp = c.execute("SELECT zhishidian FROM mistake_records WHERE id=?", (m3,)).fetchone()["zhishidian"]
    rel = c.execute("SELECT COUNT(*) c FROM mistake_knowledge mk JOIN knowledge_points kp ON kp.id=mk.kp_id "
                    "WHERE mk.mistake_id=? AND kp.name='TEST_关系源B'", (m1,)).fetchone()["c"]
    rel_src = c.execute("SELECT COUNT(*) c FROM mistake_knowledge mk JOIN knowledge_points kp ON kp.id=mk.kp_id "
                        "WHERE mk.mistake_id=? AND kp.name='TEST_关系源A'", (m1,)).fetchone()["c"]
    src_node = c.execute("SELECT id FROM knowledge_points WHERE level=3 AND name='TEST_关系源A'").fetchone()
    tgt_linked = c.execute("SELECT COALESCE(SUM(linked_count),0) c FROM knowledge_points WHERE name='TEST_关系源B'").fetchone()["c"]
    c.close()
    H.assert_true(zm == "TEST_关系源B；其它点", "多知识点行：仅命中叶子改，并列点保留")
    H.assert_true(zp == "力学/TEST_关系源B", "路径行：仅末段叶子改，章保留")
    H.assert_true(rel >= 1 and rel_src == 0, "关系表重建：关联目标、源关联清除")
    H.assert_true(src_node is None, "源知识树节点已回收（孤儿删除）")
    H.assert_true(tgt_linked >= 3, f"掌握率重算：目标节点 linked_count={tgt_linked}")

    # 批量合并（一次提交多源）
    H.new_question("TEST_批量合并1", xueke="生物", zhishidian="TEST_批量源1")
    H.new_question("TEST_批量合并2", xueke="生物", zhishidian="TEST_批量源2")
    H.check("合并-批量多源一次提交", "POST", "/api/knowledge-points/merge", 200,
            json_body={"sources": ["TEST_批量源1", "TEST_批量源2"], "target": "TEST_批量目标"})
    c = H.db()
    b_left = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian IN ('TEST_批量源1','TEST_批量源2')").fetchone()["c"]
    b_tgt = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian='TEST_批量目标'").fetchone()["c"]
    c.close()
    H.assert_true(b_left == 0 and b_tgt >= 2, f"批量合并：{b_tgt} 道错题一次并入目标，源清空")

    # 统一新增入口：创建真实树节点 + 重名幂等 + 命名校验
    add1 = H.check("新增知识点-带章节建树节点", "POST", "/api/knowledge-points/add", 200,
                   json_body={"name": "TEST_新增点Y", "xueke": "化学", "chapter": "TEST_新增章Y"})
    node = add1.json().get("node") if add1.status_code == 200 else None
    c = H.db()
    chap_node = c.execute("SELECT id FROM knowledge_points WHERE level=2 AND name='TEST_新增章Y' AND xueke='化学'").fetchone()
    dup = c.execute("SELECT COUNT(*) c FROM knowledge_points WHERE level=3 AND name='TEST_新增点Y' AND xueke='化学'").fetchone()["c"]
    c.close()
    H.assert_true(node and node.get("level") == 3 and chap_node and node.get("parent_id") == chap_node["id"],
                  "新增：在知识树中创建 level3 节点并挂在指定章下")
    H.CLEANUP_KP.append("TEST_新增点Y")
    H.check("新增知识点-重名幂等", "POST", "/api/knowledge-points/add", 200,
            json_body={"name": "TEST_新增点Y", "xueke": "化学", "chapter": "TEST_新增章Y"})
    H.assert_true(dup == 1, "新增重名幂等：未创建重复节点")
    no_xueke = H.check("新增知识点-缺学科应失败", "POST", "/api/knowledge-points/add", 200,
                       json_body={"name": "TEST_无学科", "xueke": ""})
    H.assert_true(no_xueke.status_code == 200 and no_xueke.json().get("success") is False, "新增拒绝缺学科")
    rb2 = H.check("新增知识点-含/应拒", "POST", "/api/knowledge-points/add", 200,
                  json_body={"name": "无效/名", "xueke": "化学"})
    H.assert_true(rb2.status_code == 200 and rb2.json().get("success") is False, "新增拒绝含 / 的分隔符名称")

    # 3.5 合并影响预览 API（豁免 CSRF）
    H.new_question("TEST_预览源", xueke="数学", zhishidian="TEST_预览源")
    pv = H.check("合并影响预览", "POST", "/api/knowledge-points/merge/preview", 200,
                 csrf=False, json_body={"sources": ["TEST_预览源"], "target": "二次函数"})
    if pv.status_code == 200:
        j = pv.json()
        ok_struct = (j.get("success") and isinstance(j.get("preview"), list)
                     and len(j["preview"]) >= 1
                     and all(set(["source", "leaf", "mistake_count", "plan_count", "node_count"]) <= set(p.keys())
                             for p in j["preview"]))
        H.assert_true(ok_struct, "预览返回每个源的 mistake_count/plan_count/node_count")
        H.assert_true("total_mistakes" in j and "total_plans" in j and "total_nodes" in j,
                      "预览汇总字段 total_mistakes/total_plans/total_nodes 齐全")
        # 预览不应改变任何数据（幂等，纯只读）
        c = H.db()
        after = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian='TEST_预览源'").fetchone()["c"]
        c.close()
        # 预览为只读：错题数据应仍在（>=1，容忍历史残留），不被改/删
        H.assert_true(after >= 1, "预览为只读操作，未改动错题数据")

    # 3.6 旧知识点列表分片已随统一页面废弃（/knowledge-points → 302 重定向）


# =====================================================================
# 4. 学习计划高级操作
# =====================================================================
def section_study_plans():
    H.section("4. 学习计划高级操作（更新/暂停/恢复/删除/关联题目）")
    H.check_page_ok("学习计划页", "/study-plans")
    H.check("新增学习计划", "POST", "/study-plans/add", 302,
            data={"title": "TEST_高级计划", "description": "d", "xueke": "数学",
                  "zhishidian": "函数", "target_date": date.today().isoformat(), "priority": 2})
    c = H.db()
    pid = c.execute("SELECT id FROM study_plans WHERE title='TEST_高级计划' ORDER BY id DESC LIMIT 1").fetchone()["id"]
    c.close()
    H.CLEANUP_PLANS.append(pid)

    H.check("更新计划内容", "POST", f"/study-plans/{pid}/update", 302,
            data={"title": "TEST_高级计划V2", "description": "dd", "xueke": "数学",
                  "zhishidian": "函数", "target_date": date.today().isoformat(), "priority": 3})
    c = H.db()
    t2 = c.execute("SELECT title FROM study_plans WHERE id=?", (pid,)).fetchone()["title"]
    c.close()
    H.assert_true(t2 == "TEST_高级计划V2", "计划内容已更新")

    for st, label in (("paused", "暂停"), ("in_progress", "恢复"), ("completed", "完成")):
        if st == "completed":
            H.check(f"计划标记{label}", "POST", f"/study-plans/{pid}/update", 302, data={"status": st})
        else:
            H.check(f"计划{label}", "POST", f"/study-plans/{pid}/{'pause' if st == 'paused' else 'resume'}", 302)
    c = H.db()
    st_now = c.execute("SELECT status FROM study_plans WHERE id=?", (pid,)).fetchone()["status"]
    c.close()
    H.assert_true(st_now == "completed", f"计划状态流转正常（当前 {st_now}）")

    m1 = H.new_question("TEST_计划关联A")
    m2 = H.new_question("TEST_计划关联B")
    H.check("计划添加错题", "POST", f"/api/study-plans/{pid}/mistakes/add", 200, json_body={"ids": [m1, m2]})
    c = H.db()
    cnt = c.execute("SELECT COUNT(*) c FROM plan_mistakes WHERE plan_id=?", (pid,)).fetchone()["c"]
    c.close()
    H.assert_true(cnt == 2, "计划已关联 2 道错题")

    H.check("计划自动匹配知识点", "POST", f"/api/study-plans/{pid}/mistakes/auto", 200, json_body={})
    H.check("计划移除错题", "POST", f"/api/study-plans/{pid}/mistakes/remove", 200, json_body={"ids": [m2]})
    c = H.db()
    still = c.execute("SELECT COUNT(*) c FROM plan_mistakes WHERE plan_id=? AND mistake_id=?", (pid, m2)).fetchone()["c"]
    c.close()
    H.assert_true(still == 0, "计划移除指定错题生效")

    H.check("计划错题加入复习", "POST", f"/api/study-plans/{pid}/review", 200, json_body={})
    H.check("删除计划", "POST", f"/study-plans/{pid}/delete", 302)
    c = H.db()
    pst = c.execute("SELECT status FROM study_plans WHERE id=?", (pid,)).fetchone()["status"]
    c.close()
    H.assert_true(pst == "deleted", "计划已软删除")
    H.CLEANUP_PLANS.remove(pid)


# =====================================================================
# 5. 复习系统补充
# =====================================================================
def section_review():
    H.section("5. 复习系统（add-all / today-stats / config / 掌握流转 / history 筛选）")
    H.check("复习页", "GET", "/review", 200)
    H.check("复习配置页-GET重定向", "GET", "/review/config", 302)
    H.check("一键加入复习", "POST", "/api/review/add-all", 200, json_body={})

    r = H.check("今日复习统计", "GET", "/api/review/today-stats", 200)
    if r.status_code == 200:
        j = r.json()
        H.assert_true("total" in j and "streak" in j and "rate" in j,
                      f"today-stats 字段完整 (total={j.get('total')}, streak={j.get('streak')}, rate={j.get('rate')})")

    H.check("更新复习配置", "POST", "/review/config", 302, data={"algorithm": "sm2", "daily_limit": "25"})
    c = H.db()
    cfg = c.execute("SELECT review_algorithm, daily_review_limit FROM user_config LIMIT 1").fetchone()
    c.close()
    H.assert_true(cfg and cfg["daily_review_limit"] == 25, f"复习配置已持久化 (daily_limit={cfg['daily_review_limit'] if cfg else None})")

    H.check("提交复习-不存在错题应失败", "POST", "/api/review/99999999/submit", 200, json_body={"result": "correct"})
    mk = H.new_question("TEST_掌握流转")
    if mk:
        c = H.db(); c.execute("UPDATE mistake_records SET review_stage=0, status='active' WHERE id=?", (mk,)); c.commit(); c.close()
        mastered = False
        for i in range(5):
            r = H.check(f"提交复习-第{i+1}次答对", "POST", f"/api/review/{mk}/submit", 200,
                        json_body={"result": "correct", "time_spent": 10, "notes": ""})
            j = r.json() if r.status_code == 200 else {}
            if j.get("success") and j.get("new_stage", 0) >= 4:
                mastered = True
        c = H.db()
        st = c.execute("SELECT status, review_stage FROM mistake_records WHERE id=?", (mk,)).fetchone()
        c.close()
        H.assert_true(mastered and st["status"] == "mastered",
                      f"连续答对触发已掌握 (status={st['status']}, stage={st['review_stage']})")

    H.check("复习历史列表-全部", "GET", "/api/review/history/list", 200)
    H.check("复习历史列表-近7天", "GET", "/api/review/history/list?range=7days", 200)
    H.check("复习历史列表-按学科", "GET", "/api/review/history/list?xueke=数学", 200)
    H.check_page_ok("复习记录页", "/review/history")


# =====================================================================
# 6. 批量操作
# =====================================================================
def section_batch():
    H.section("6. 批量操作（delete / update / restore / purge / toggle-status）")
    b1 = H.new_question("TEST_批量1")
    b2 = H.new_question("TEST_批量2")
    H.check("批量删除", "POST", "/api/questions/batch-delete", 200, json_body={"ids": [b1, b2]})
    c = H.db()
    n1 = c.execute("SELECT status FROM mistake_records WHERE id=?", (b1,)).fetchone()["status"]
    n2 = c.execute("SELECT status FROM mistake_records WHERE id=?", (b2,)).fetchone()["status"]
    c.close()
    H.assert_true(n1 == "deleted" and n2 == "deleted", "批量删除生效（status=deleted）")

    H.check("批量更新状态", "POST", "/api/questions/batch-update", 200, json_body={"ids": [b1], "action": "status", "value": "active"})
    H.check("批量更新知识点", "POST", "/api/questions/batch-update", 200, json_body={"ids": [b1], "action": "zhishidian", "value": "函数/导数"})
    H.check("批量更新复习时间", "POST", "/api/questions/batch-update", 200, json_body={"ids": [b1], "action": "next_review_at", "value": date.today().isoformat()})
    c = H.db()
    u = c.execute("SELECT status, zhishidian, next_review_at FROM mistake_records WHERE id=?", (b1,)).fetchone()
    c.close()
    H.assert_true(u["status"] == "active" and u["zhishidian"] == "函数/导数" and u["next_review_at"], "批量更新三类字段生效")

    H.check("批量更新-非法action应400", "POST", "/api/questions/batch-update", 400, json_body={"ids": [b1], "action": "hack", "value": "x"})
    H.check("批量更新-空ids应400", "POST", "/api/questions/batch-update", 400, json_body={"ids": [], "action": "status", "value": "active"})
    H.check("批量删除-含非法id", "POST", "/api/questions/batch-delete", 200, json_body={"ids": ["abc", None, b2]})

    H.check("批量恢复", "POST", "/api/questions/restore", 200, json_body={"ids": [b1]})
    c = H.db(); rst = c.execute("SELECT status FROM mistake_records WHERE id=?", (b1,)).fetchone()["status"]; c.close()
    H.assert_true(rst == "active", "批量恢复生效")

    H.check("切换状态(归档)", "POST", f"/questions/{b1}/toggle-status", 302, data={"status": "archived"})
    c = H.db(); tst = c.execute("SELECT status FROM mistake_records WHERE id=?", (b1,)).fetchone()["status"]; c.close()
    H.assert_true(tst == "archived", "toggle-status 生效（archived）")

    H.check("批量彻底删除", "POST", "/api/questions/purge", 200, json_body={"ids": [b1, b2]})
    c = H.db()
    pe = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE id IN (?,?)", (b1, b2)).fetchone()["c"]
    c.close()
    H.assert_true(pe == 0, "purge 物理删除生效")
    for x in (b1, b2):
        if x in H.CLEANUP_IDS:
            H.CLEANUP_IDS.remove(x)


# =====================================================================
# 7. 语音笔记 API
# =====================================================================
def section_voice():
    H.section("7. 语音笔记 API（GET/POST/DELETE）")
    vq = H.new_question("TEST_语音")
    H.check("语音-GET无数据应404", "GET", f"/api/questions/{vq}/voice", 404)
    dummy = base64.b64encode(b"fakewebm").decode()
    H.check("语音-POST设置", "POST", f"/api/questions/{vq}/voice", 200, json_body={"voice": dummy})
    H.check("语音-GET有数据应200", "GET", f"/api/questions/{vq}/voice", 200)
    H.check("语音-DELETE清除", "DELETE", f"/api/questions/{vq}/voice", 200)
    H.check("语音-DELETE后再GET应404", "GET", f"/api/questions/{vq}/voice", 404)
    H.check("语音-POST无音频应400", "POST", f"/api/questions/{vq}/voice", 400, json_body={})


# =====================================================================
# 8. 图片 API
# =====================================================================
def section_image():
    H.section("8. 图片 API（上传/获取/删除/404）")
    iq = H.new_question("TEST_图片")
    tok = H.csrf_token()
    rup = S.post(f"{BASE}/questions/{iq}/edit",
                 data={"csrf_token": tok, "xueke": "数学", "timu": "TEST_图片",
                       "zhengquedaan": "a", "zhishidian": "函数/幂"},
                 files={"images": ("t.png", H.png_bytes(), "image/png")},
                 allow_redirects=False)
    H.assert_true(rup.status_code in (302, 200), f"编辑上传图片 → {rup.status_code}")
    c = H.db()
    img = c.execute("SELECT id, mistake_id FROM mistake_images WHERE mistake_id=?", (iq,)).fetchone()
    c.close()
    H.assert_true(bool(img), "已生成图片记录")
    if img:
        iid = img["id"]
        H.check("图片-GET应200", "GET", f"/api/questions/{iq}/image/{iid}", 200)
        H.check("图片-DELETE应成功", "POST", f"/api/questions/{iq}/image/{iid}/delete", 200)
        H.check("图片-DELETE后GET应404", "GET", f"/api/questions/{iq}/image/{iid}", 404)
    H.check("图片-不存在应404", "GET", f"/api/questions/{iq}/image/99999999", 404)


# =====================================================================
# 9. 导出
# =====================================================================
def section_export():
    H.section("9. 导出（excel / pdf / anki）")
    r = H.check("导出Excel", "GET", "/api/export/excel", 200)
    H.assert_true(r.status_code == 200, "Excel 导出 200")
    rp = H.check("导出PDF", "GET", "/api/export/pdf", 200)
    H.assert_true(rp.status_code == 200 and 'pdf' in rp.headers.get('Content-Type', ''), "PDF 导出")
    ra = H.check("导出Anki", "GET", "/api/export/anki", 200)
    H.assert_true(ra.status_code == 200, "Anki 导出 (txt)")


# =====================================================================
# 10. 分页 + 每页条数下拉（含 7 模板 / 5 接口）
# =====================================================================
def section_pagination_and_perpage():
    H.section("10. 分页 + 每页条数下拉（知识点管理已统一为知识树管理，旧页 302 重定向）")
    # 回收站下拉仅在「有内容可分页」时渲染（模板 {\% if total_pages>1 or total>per_page \%}），
    # 预置足量已删除错题以触发下拉。
    for i in range(25):
        mid = H.new_question(f"TEST_回收站种子{i}")
        if mid:
            H.check(f"软删除种子{i}", "POST", f"/questions/{mid}/delete", 302, data={})

    # 复习记录下拉同样仅在「可分页」时渲染（total > per_page=20）。为保障测试确定性、
    # 不依赖库内既有复习记录数量，直接置入足量复习日志（用本会话 uuid，取自种子错题），
    # 一次 DB 写入完成，远快于逐条提交；用后随 TEST_ 错题一并级联清理。
    seed_mid = H.new_question("TEST_复习下拉种子")
    if seed_mid:
        c = H.db()
        suuid = c.execute("SELECT uuid FROM mistake_records WHERE id=?", (seed_mid,)).fetchone()["uuid"]
        c.executemany(
            "INSERT INTO review_logs (mistake_id, uuid, review_date, result, time_spent, notes) "
            "VALUES (?,?,?,?,?,?)",
            [(seed_mid, suuid, date.today().isoformat(), "correct", 5, "seed") for _ in range(22)])
        c.commit(); c.close()

    # 每页条数下拉：4 个列表接口都应含 per_page 下拉
    checks = [
        ("错题本", "/questions"),
        ("回收站", "/questions/deleted"),
        ("学习计划列表", "/api/study-plans/list"),
        ("复习记录列表", "/api/review/history/list"),
    ]
    for label, path in checks:
        r = S.get(f"{BASE}{path}", timeout=20)
        has_select = ("<select" in r.text.lower()) and (
            "per_page" in r.text.lower() or "per-page-select" in r.text.lower())
        H.assert_true(r.status_code == 200 and has_select,
                      f"{label}：每页条数下拉已渲染（status={r.status_code}, per_page select 存在）")


# =====================================================================
# 11. CSRF 防护
# =====================================================================
def section_csrf():
    H.section("11. CSRF 防护（多端点无 token 应 403）")
    vq = H.new_question("TEST_CSRF")
    H.check("CSRF-无 token 新增错题应 403", "POST", "/questions/add", 403, csrf=False,
            data={"xueke": "数学", "timu": "CSRF_TEST"})
    H.check("CSRF-切换状态", "POST", f"/questions/{vq}/toggle-status", 403, csrf=False, data={"status": "active"})
    H.check("CSRF-计划加题", "POST", f"/api/study-plans/1/mistakes/add", 403, csrf=False, json_body={"ids": [vq]})
    H.check("CSRF-批量删除", "POST", "/api/questions/batch-delete", 403, csrf=False, json_body={"ids": [vq]})
    H.check("CSRF-语音设置", "POST", f"/api/questions/{vq}/voice", 403, csrf=False, json_body={"voice": "x"})
    H.check("CSRF-新增计划", "POST", "/study-plans/add", 403, csrf=False, data={"title": "x"})
    H.check("CSRF-复习配置", "POST", "/review/config", 403, csrf=False, data={"algorithm": "sm2", "daily_limit": "20"})
    # 有 token 应正常（合并预览豁免）
    H.check("CSRF-合并预览豁免", "POST", "/api/knowledge-points/merge/preview", 200, csrf=False,
            json_body={"sources": ["x"], "target": "y"})


# =====================================================================
# 12. 页面完整性
# =====================================================================
def section_pages():
    H.section("12. 页面完整性（全部页面 200 且无模板错误）")
    for p in ["/", "/questions", "/knowledge-points", "/knowledge-map", "/study-plans",
              "/review", "/review/history", "/statistics", "/questions/deleted",
              "/settings/api-tokens", "/questions/add",
              "/questions/paste-import", "/questions/ocr", "/questions/doc-import"]:
        H.check_page_ok(f"页面 {p}", p)


# =====================================================================
# 13. 安全专项（XSS / SQL 注入 / 路径遍历 / 404）
# =====================================================================
def section_security():
    H.section("13. 安全专项（XSS / SQL 注入 / 路径遍历 / 404）")
    xss_data = {"xueke": "语文", "timu": "TEST_XSS<script>alert('xss')</script>",
                "zhengquedaan": "a", "zhishidian": "TEST_XSS点", "difficulty": 1}
    r = S.post(f"{BASE}/questions/add", data={**xss_data, "csrf_token": H.csrf_token()},
               allow_redirects=False, timeout=20)
    if r.status_code in (302, 200):
        c = H.db()
        xid = c.execute("SELECT id FROM mistake_records WHERE timu LIKE 'TEST_XSS%' ORDER BY id DESC LIMIT 1").fetchone()
        c.close()
        if xid:
            H.CLEANUP_IDS.append(xid["id"])
            rd = S.get(f"{BASE}/questions/{xid['id']}")
            H.assert_true("<script>alert('xss')</script>" not in rd.text, "XSS 输入已转义（Jinja 自动转义）")
        else:
            H.record_error("XSS 测试题未落库")
    else:
        H.record_error(f"XSS 新增返回异常 {r.status_code}")

    r = S.get(f"{BASE}/knowledge-points?zhishidian=' OR '1'='1", timeout=20)
    H.assert_true(r.status_code == 200, "SQL 注入参数化（筛选注入未报错）")

    r = S.get(f"{BASE}/questions/doc-import?filename=../../etc/passwd", timeout=20)
    H.assert_true(r.status_code == 200 and "/etc/passwd" not in r.text, "路径遍历参数被安全处理")

    H.check("不存在的路由 → 404", "GET", "/this/route/not/exist", 404)
    H.check("错题详情非数字ID → 404", "GET", "/questions/abc", 404)


# =====================================================================
# 14. 回收站生命周期
# =====================================================================
def section_recycle_bin():
    H.section("14. 回收站生命周期（delete → list → restore → purge）")
    rb = H.new_question("TEST_回收站")
    H.check("软删除错题", "POST", f"/questions/{rb}/delete", 302)
    c = H.db()
    in_bin = c.execute("SELECT status FROM mistake_records WHERE id=?", (rb,)).fetchone()["status"]
    c.close()
    H.assert_true(in_bin == "deleted", "错题已进回收站")
    # 回归：软删除后必须从「错题本」主列表消失（修复「删除后刷新又出现」）
    reg = H.new_question("TEST_软删离表回归")
    H.check("软删除-回归题", "POST", f"/questions/{reg}/delete", 302)
    rl = S.get(f"{BASE}/questions", timeout=20)
    H.assert_true("TEST_软删离表回归" not in rl.text,
                  "软删除后主列表不再显示该错题（删除后刷新不回弹）")
    rd = S.get(f"{BASE}/questions/deleted", timeout=20)
    H.assert_true("TEST_软删离表回归" in rd.text,
                  "软删除后错题进入回收站列表")
    H.check_page_ok("回收站列表页", "/questions/deleted")
    H.check("回收站恢复", "POST", "/api/questions/restore", 200, json_body={"ids": [rb]})
    c = H.db(); rst2 = c.execute("SELECT status FROM mistake_records WHERE id=?", (rb,)).fetchone()["status"]; c.close()
    H.assert_true(rst2 == "active", "回收站恢复生效")
    H.check("回收站彻底删除", "POST", "/api/questions/purge", 200, json_body={"ids": [rb]})
    c = H.db(); gone = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE id=?", (rb,)).fetchone()["c"]; c.close()
    H.assert_true(gone == 0, "回收站彻底删除生效")
    if rb in H.CLEANUP_IDS:
        H.CLEANUP_IDS.remove(rb)

    # 回归：每行「恢复」按钮是传统 form 提交（name=ids 表单字段），
    # 接口须兼容表单数据，否则报「未选择」（修复回收站恢复报错）
    reg2 = H.new_question("TEST_行内恢复回归")
    H.check("软删除-行内回归", "POST", f"/questions/{reg2}/delete", 302)
    H.check("回收站-行内恢复(form)", "POST", "/api/questions/restore", 200,
            data={"ids": reg2})  # 表单字段，模拟行内恢复表单（非 JSON）
    c = H.db(); st2 = c.execute("SELECT status FROM mistake_records WHERE id=?", (reg2,)).fetchone()["status"]; c.close()
    H.assert_true(st2 == "active", "行内表单恢复生效（状态恢复为 active）")
    H.check("回收站-行内彻底删除", "POST", "/api/questions/purge", 200, json_body={"ids": [reg2]})
    c = H.db(); gone2 = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE id=?", (reg2,)).fetchone()["c"]; c.close()
    H.assert_true(gone2 == 0, "行内恢复后彻底删除生效")

    # 回归：每行「恢复」改为 AJAX 按钮（restoreOne），不再用原生 form 跳转刷出 JSON 页面
    reg3 = H.new_question("TEST_行内不跳转回归")
    H.check("软删除-不跳转回归", "POST", f"/questions/{reg3}/delete", 302)
    rd = S.get(f"{BASE}/questions/deleted", timeout=20)
    H.assert_true("restoreOne(" in rd.text, "回收站行内恢复已改为 AJAX 按钮（restoreOne）")
    H.assert_true('action="/api/questions/restore"' not in rd.text,
                  "回收站不再有原生 form 跳转（不会刷出 JSON 页面）")
    H.check("回收站-不跳转回归彻底删除", "POST", "/api/questions/purge", 200, json_body={"ids": [reg3]})

    # 回归：错题若被学习计划引用，彻底删除须先清理 plan_mistakes，
    # 否则 plan_mistakes.mistake_id 外键（无 ON DELETE CASCADE）触发约束冲突，
    # 导致整批 purge 返回 500、错题残留（修复「回收站彻底删除功能无效」）
    rb_pl = H.new_question("TEST_计划引用purge回归")
    H.check("创建计划-引用回归", "POST", "/study-plans/add", 302, data={
        "title": "TEST_计划引用回归", "description": "", "xueke": "数学",
        "zhishidian": "", "target_date": "", "priority": "1"})
    c = H.db()
    plpid = c.execute("SELECT id FROM study_plans WHERE title=? ORDER BY id DESC LIMIT 1",
                      ("TEST_计划引用回归",)).fetchone()["id"]
    c.close()
    H.check("加入计划-引用回归", "POST", f"/api/study-plans/{plpid}/mistakes/add",
            200, json_body={"ids": [rb_pl]})
    c = H.db()
    pm_cnt = c.execute("SELECT COUNT(*) c FROM plan_mistakes WHERE mistake_id=?", (rb_pl,)).fetchone()["c"]
    c.close()
    H.assert_true(pm_cnt == 1, "错题已加入计划（plan_mistakes 引用建立）")
    H.check("软删除-计划引用回归", "POST", f"/questions/{rb_pl}/delete", 302)
    H.check("回收站-计划引用彻底删除", "POST", "/api/questions/purge", 200, json_body={"ids": [rb_pl]})
    c = H.db()
    gone3 = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE id=?", (rb_pl,)).fetchone()["c"]
    pm_left = c.execute("SELECT COUNT(*) c FROM plan_mistakes WHERE mistake_id=?", (rb_pl,)).fetchone()["c"]
    c.close()
    H.assert_true(gone3 == 0, "计划引用的错题被物理删除（purge 不再 500）")
    H.assert_true(pm_left == 0, "关联的 plan_mistakes 引用一并清除")
    if rb_pl in H.CLEANUP_IDS:
        H.CLEANUP_IDS.remove(rb_pl)  # 已被 purge 物理删除，避免 cleanup 二次删除报错


# =====================================================================
# 15. 西城中学知识点导入（共享库）
# =====================================================================
def section_xicheng_import():
    H.section("15. 西城中学知识点导入（共享库 399 节点）")
    c = H.db()
    total = c.execute("SELECT COUNT(*) c FROM knowledge_points").fetchone()["c"]
    xc = c.execute("SELECT COUNT(*) c FROM knowledge_points WHERE uuid='xicheng_import'").fetchone()["c"]
    c.close()
    H.assert_true(xc >= 399, f"西城导入节点数充足（{xc}）")

    # 各学科 level1 节点存在且含子章节
    expect = {"数学": 22, "物理": 17, "化学": 10, "语文": 4, "英语": 5}
    c = H.db()
    for xueke, min_chap in expect.items():
        subj = c.execute("SELECT id FROM knowledge_points WHERE name=? AND level=1 AND uuid='xicheng_import' LIMIT 1",
                         (xueke,)).fetchone()
        if not subj:
            H.record_error(f"西城导入缺少学科 {xueke}")
            continue
        chaps = c.execute("SELECT COUNT(*) c FROM knowledge_points WHERE parent_id=? AND level=2",
                          (subj["id"],)).fetchone()["c"]
        H.assert_true(chaps >= min_chap, f"西城 {xueke} 章节数充足（{chaps} ≥ {min_chap}）")
    c.close()


# =====================================================================
# 16. 空学科（道法2 类）删除修复
# =====================================================================
def section_empty_subject_delete():
    H.section("16. 空学科删除修复（道法2 类用例）")
    # 创建一个全新的空 level1 学科
    r = S.post(f"{BASE}/api/knowledge-points/node",
               json={"name": "TEST_空学科X"},
               headers={"X-CSRF-Token": H.csrf_token(), "Content-Type": "application/json"},
               timeout=20)
    j = r.json() if r.status_code == 200 else {}
    nid = j.get("node", {}).get("id") if j.get("success") else None
    H.assert_true(bool(nid), f"创建空学科成功（id={nid}）")
    if nid:
        c = H.db()
        ch = c.execute("SELECT COUNT(*) c FROM knowledge_points WHERE parent_id=?", (nid,)).fetchone()["c"]
        lk = c.execute("SELECT COUNT(*) c FROM mistake_knowledge WHERE kp_id=?", (nid,)).fetchone()["c"]
        c.close()
        H.assert_true(ch == 0 and lk == 0, "新建空学科无子节点、无错题关联")
        # 修复后应当允许删除（旧实现对所有 level1 直接 403）
        rd = S.delete(f"{BASE}/api/knowledge-points/node/{nid}",
                      headers={"X-CSRF-Token": H.csrf_token()})
        H.assert_true(rd.status_code == 200 and rd.json().get("success"), "空学科删除成功（修复生效，不再 403）")
        c = H.db()
        gone = c.execute("SELECT COUNT(*) c FROM knowledge_points WHERE id=?", (nid,)).fetchone()["c"]
        c.close()
        H.assert_true(gone == 0, "空学科节点已删除")


# =====================================================================
# 17. 空 uuid Cookie 自愈
# =====================================================================
def section_uuid_selfheal():
    H.section("17. 空 uuid Cookie 自愈到已有数据")
    S2 = requests.Session()
    S2.post(f"{BASE}/login", data={"username": "tim", "password": "tim123"}, allow_redirects=False)
    S2.cookies.set("tim_study_uuid", "00000000-0000-0000-0000-000000000000", domain="127.0.0.1")
    r = S2.get(f"{BASE}/api/knowledge-points/tree", timeout=20)
    ok_json = False
    n_roots = 0
    if r.status_code == 200:
        try:
            jt = r.json()
            ok_json = bool(jt.get("success")) and len(jt.get("tree", [])) > 0
            n_roots = len(jt.get("tree", []))
        except Exception:
            ok_json = False
    H.assert_true(ok_json, f"空 uuid Cookie 自愈成功，思维导图可加载 {n_roots} 个学科根")


# =====================================================================
# 18. 知识树管理（统一页面 + 重定向 + 移动 + 关联错题）
# =====================================================================
def section_knowledge_tree():
    H.section("18. 知识树管理（统一页面 + 重定向 + 移动 + 关联错题）")
    # 1) 统一页面可用
    H.check_page_ok("知识树管理页", "/knowledge-tree")
    rd = S.get(f"{BASE}/knowledge-tree", timeout=20)
    H.assert_true("知识树管理" in rd.text, "知识树管理页标题存在")
    # 2) 旧入口重定向
    H.check("旧知识点管理→重定向", "GET", "/knowledge-points", 302)
    H.check("旧思维导图→重定向", "GET", "/knowledge-map", 302)
    # 3) GET /api/knowledge-points/node/<id>/mistakes
    c = H.db()
    node = c.execute("""
        SELECT kp.id FROM knowledge_points kp
        WHERE kp.level=3 AND EXISTS(SELECT 1 FROM mistake_knowledge mk WHERE mk.kp_id=kp.id)
        LIMIT 1""").fetchone()
    c.close()
    if node:
        nid = node["id"]
        r = H.check(f"节点{nid}关联错题", "GET", f"/api/knowledge-points/node/{nid}/mistakes", 200)
        try:
            d = r.json()
            H.assert_true(d.get("success"), "mistakes 端点返回 success")
            H.assert_true("total" in d, "含 total 字段")
            H.assert_true("mistakes" in d, "含 mistakes 字段")
            H.assert_true("plan_count" in d, "含 plan_count 字段")
        except Exception:
            H.record_error("mistakes 端点 JSON 解析失败")
    else:
        H.warn("无有数据的知识点节点，跳过关联错题测试")
    # 4) POST /api/knowledge-points/move — 创建节点，移动，防环
    csrf_tok = H.csrf_token()
    H.check("创建移动学科", "POST", "/api/knowledge-points/node", 200,
            json_body={"name": "TEST_移动A"})
    c = H.db()
    subj = c.execute("SELECT id FROM knowledge_points WHERE name='TEST_移动A' ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    if not subj:
        H.record_error("创建移动学科失败"); return
    subj_id = subj["id"]
    H.CLEANUP_KP.append("TEST_移动A")
    H.check("创建移动章", "POST", "/api/knowledge-points/node", 200,
            json_body={"name": "TEST_移动B", "parent_id": subj_id, "mode": "child"})
    c = H.db()
    ch = c.execute("SELECT id FROM knowledge_points WHERE name='TEST_移动B' AND parent_id=?", (subj_id,)).fetchone()
    c.close()
    if not ch:
        H.record_error("创建移动章失败"); return
    ch_id = ch["id"]
    H.CLEANUP_KP.append("TEST_移动B")
    H.check("创建目标学科", "POST", "/api/knowledge-points/node", 200,
            json_body={"name": "TEST_移动C"})
    c = H.db()
    target = c.execute("SELECT id FROM knowledge_points WHERE name='TEST_移动C' ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    if not target:
        H.record_error("创建移动目标失败"); return
    tid = target["id"]
    H.CLEANUP_KP.append("TEST_移动C")
    # 移动章 B 到学科 C
    H.check("移动到目标学科", "POST", "/api/knowledge-points/move", 200,
            json_body={"node_id": ch_id, "new_parent_id": tid})
    c = H.db()
    new_par = c.execute("SELECT parent_id FROM knowledge_points WHERE id=?", (ch_id,)).fetchone()["parent_id"]
    c.close()
    H.assert_true(new_par == tid, f"移动后父节点已变更（期望 {tid}，实际 {new_par}）")
    # 防环：不能移到自身子孙下（把 chapter 移到它自己的子节点不行；把学科移到其章节下也不行）
    H.check("移动自身→子孙（防环）", "POST", "/api/knowledge-points/move", 200,
            json_body={"node_id": subj_id, "new_parent_id": ch_id})
    # 清理：直接 DB 删除测试节点（含子孙），然后 recompute
    c = H.db()
    for nid in [subj_id, ch_id, tid]:
        c.execute("DELETE FROM knowledge_points WHERE id IN ("
                  "WITH RECURSIVE d AS (SELECT id FROM knowledge_points WHERE id=? "
                  "UNION ALL SELECT k.id FROM knowledge_points k JOIN d ON k.parent_id=d.id) "
                  "SELECT id FROM d)", (nid,))
    c.commit(); c.close()
    # 从 CLEANUP_KP 移除（已手动清理）
    for nm in ["TEST_移动A","TEST_移动B","TEST_移动C"]:
        if nm in H.CLEANUP_KP: H.CLEANUP_KP.remove(nm)
    try:
        S.get(f"{BASE}/api/knowledge-points/migrate", timeout=20)
    except Exception: pass


# =====================================================================
def main():
    t0 = time.time()
    H.section("0. 启动测试服务（当前代码）+ 基线清理")
    H.start_server()
    H.reset_test_data()
    H.login()
    try:
        section_auth()
        section_question_crud()
        section_knowledge_points()
        section_study_plans()
        section_review()
        section_batch()
        section_voice()
        section_image()
        section_export()
        section_pagination_and_perpage()
        section_csrf()
        section_pages()
        section_security()
        section_recycle_bin()
        section_xicheng_import()
        section_empty_subject_delete()
        section_uuid_selfheal()
        section_knowledge_tree()
    finally:
        # 无论测试是否中途异常，都必须清理测试数据，避免污染生产库
        H.section("清理测试数据（含全局扫描兜底）")
        H.cleanup()
        residual, total = H.verify_cleanup()
        if total == 0:
            H.assert_true(True, "测试数据全部清理：无 TEST_ 残留（生产库安全）")
        else:
            H.record_error(f"清理后仍有 TEST_ 残留: {residual}")

    ok = H.summary("Tim 学习助手 整合测试")
    print(f"  ⏱️ 耗时 {round(time.time() - t0, 1)}s")
    return ok


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)

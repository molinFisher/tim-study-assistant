"""聚焦验证：仅验证本次 P0 改动（合并关系重建 + 统一新增入口）。

同一进程内线程起 Flask（app.test_client 不需要），复用 test_full_v5 的
helper（login/check/db/new_question），只跑合并一致性 + 统一新增相关断言。
"""
import os
import sys
import time
import threading
import sqlite3
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from app import app

# 以 importlib 加载 tests/test_full_v5.py（未必是包）
_spec = importlib.util.spec_from_file_location(
    "test_full_v5_mod", os.path.join(HERE, "tests", "test_full_v5.py"))
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)


def db():
    c = sqlite3.connect(T.DB)
    c.row_factory = sqlite3.Row
    return c


def serve():
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


def run():
    T.login()
    print("📌 P0 聚焦：合并关系重建 + 统一新增入口")

    # ---- 合并：token 级改写 + 关系表重建 + 多知识点行 + 路径 + 孤儿回收 ----
    m1 = T.new_question("FOC_合并单", xueke="物理", zhishidian="FOC_关系源A")
    m2 = T.new_question("FOC_合并多", xueke="物理", zhishidian="FOC_关系源A；其它点")
    m3 = T.new_question("FOC_合并路径", xueke="物理", zhishidian="力学/FOC_关系源A")
    T.check("合并-批量关系重建", "POST", "/api/knowledge-points/merge", 200,
              json_body={"sources": ["FOC_关系源A"], "target": "FOC_关系源B"})
    c = db()
    # token 级合并：精确 ='FOC_关系源B' 只匹配单知识点记录 m1；
    # m2/m3 在 token 级验证中确认叶子已被替换（多知识点行 / 路径行）。
    cnt_a_exact = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian='FOC_关系源A'").fetchone()["c"]
    cnt_b_exact = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian='FOC_关系源B'").fetchone()["c"]
    cnt_b_like = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian LIKE '%FOC_关系源B%' AND id IN (?,?,?)",
                           (m1, m2, m3)).fetchone()["c"]
    cnt_a_like = c.execute("SELECT COUNT(*) c FROM mistake_records WHERE zhishidian LIKE '%FOC_关系源A%' AND id IN (?,?,?)",
                           (m1, m2, m3)).fetchone()["c"]
    if cnt_a_exact == 0 and cnt_b_exact >= 1 and cnt_b_like == 3 and cnt_a_like == 0:
        T.PASS += 1; print(f"  ✅ 合并后 3 题 token 级归属正确 (精确目标={cnt_b_exact} LIKE={cnt_b_like} LIKE源={cnt_a_like})")
    else:
        T.FAIL += 1; print(f"  ❌ 合并错题归属异常: 精确源={cnt_a_exact} 精确目标={cnt_b_exact} LIKE目标={cnt_b_like} LIKE源={cnt_a_like}")
        T.ERRORS.append("合并归属异常")
    # 多知识点行只改命中叶子
    zm = c.execute("SELECT zhishidian FROM mistake_records WHERE id=?", (m2,)).fetchone()["zhishidian"]
    if zm == "FOC_关系源B；其它点":
        T.PASS += 1; print("  ✅ 多知识点行：仅命中叶子改，并列点保留")
    else:
        T.FAIL += 1; print(f"  ❌ 多知识点行异常: {zm}"); T.ERRORS.append("合并多知识点行异常")
    # 路径行只改末段叶子
    zp = c.execute("SELECT zhishidian FROM mistake_records WHERE id=?", (m3,)).fetchone()["zhishidian"]
    if zp == "力学/FOC_关系源B":
        T.PASS += 1; print("  ✅ 路径行：仅末段叶子改，章保留")
    else:
        T.FAIL += 1; print(f"  ❌ 路径行异常: {zp}"); T.ERRORS.append("合并路径行异常")
    # 关系表重建
    rel = c.execute("SELECT COUNT(*) c FROM mistake_knowledge mk "
                    "JOIN knowledge_points kp ON kp.id=mk.kp_id "
                    "WHERE mk.mistake_id=? AND kp.name='FOC_关系源B'", (m1,)).fetchone()["c"]
    rel_src = c.execute("SELECT COUNT(*) c FROM mistake_knowledge mk "
                        "JOIN knowledge_points kp ON kp.id=mk.kp_id "
                        "WHERE mk.mistake_id=? AND kp.name='FOC_关系源A'", (m1,)).fetchone()["c"]
    src_node = c.execute("SELECT id FROM knowledge_points WHERE level=3 AND name='FOC_关系源A'").fetchone()
    c.close()
    if rel >= 1 and rel_src == 0:
        T.PASS += 1; print("  ✅ 关系表重建：错题关联到目标节点，源节点关联已清除")
    else:
        T.FAIL += 1; print(f"  ❌ 关系表重建异常: 目标关联={rel} 源关联={rel_src}"); T.ERRORS.append("合并关系表未重建")
    if src_node is None:
        T.PASS += 1; print("  ✅ 源知识树节点已回收（孤儿删除）")
    else:
        T.FAIL += 1; print("  ❌ 源节点未回收"); T.ERRORS.append("合并源节点未回收")
    # 掌握率重算
    c = db()
    tg_linked = c.execute("SELECT COALESCE(SUM(linked_count),0) c FROM knowledge_points WHERE name='FOC_关系源B'").fetchone()["c"]
    c.close()
    if tg_linked >= 3:
        T.PASS += 1; print(f"  ✅ 掌握率重算：目标节点 linked_count={tg_linked}")
    else:
        T.FAIL += 1; print(f"  ❌ 掌握率未重算: {tg_linked}"); T.ERRORS.append("合并掌握率未重算")

    # ---- 统一新增入口：建真实树节点 + 重名幂等 + 命名校验 ----
    add1 = T.check("新增知识点-带章节建树节点", "POST", "/api/knowledge-points/add", 200,
                   json_body={"name": "FOC_新增点Y", "xueke": "化学", "chapter": "FOC_新增章Y"})
    node = add1.json().get("node") if add1.status_code == 200 else None
    c = db()
    chap_node = c.execute("SELECT id FROM knowledge_points WHERE level=2 AND name='FOC_新增章Y' AND xueke='化学'").fetchone()
    if node and node.get("level") == 3 and chap_node and node.get("parent_id") == chap_node["id"]:
        T.PASS += 1; print("  ✅ 新增：在知识树中创建 level3 节点并挂在指定章下")
    else:
        T.FAIL += 1; print(f"  ❌ 新增未建正确树节点: node={node}"); T.ERRORS.append("新增未建树节点")
    T.check("新增知识点-重名幂等", "POST", "/api/knowledge-points/add", 200,
              json_body={"name": "FOC_新增点Y", "xueke": "化学", "chapter": "FOC_新增章Y"})
    dup = c.execute("SELECT COUNT(*) c FROM knowledge_points WHERE level=3 AND name='FOC_新增点Y' AND xueke='化学'").fetchone()["c"]
    c.close()
    if dup == 1:
        T.PASS += 1; print("  ✅ 新增重名幂等：未创建重复节点")
    else:
        T.FAIL += 1; print(f"  ❌ 重名产生重复节点: {dup}"); T.ERRORS.append("新增重名未幂等")
    rb = T.check("新增知识点-含/应拒", "POST", "/api/knowledge-points/add", 200,
                   json_body={"name": "无效/名", "xueke": "化学"})
    if rb.status_code == 200 and rb.json().get("success") is False:
        T.PASS += 1; print("  ✅ 新增拒绝含 / 的分隔符名称")
    else:
        T.FAIL += 1; print(f"  ❌ 新增分隔符未拒: {rb.text[:80]}"); T.ERRORS.append("新增分隔符未拒")

    # 清理
    c = db()
    for mid in (m1, m2, m3):
        try:
            c.execute("DELETE FROM mistake_knowledge WHERE mistake_id=?", (mid,))
            c.execute("DELETE FROM mistake_records WHERE id=?", (mid,))
        except Exception:
            pass
    c.execute("DELETE FROM knowledge_points WHERE name LIKE 'FOC_%'")
    c.execute("DELETE FROM base_data WHERE category='knowledge_point' AND name LIKE 'FOC_%'")
    c.commit(); c.close()

    print(f"\n>>> 聚焦结果: PASS={T.PASS} FAIL={T.FAIL}")
    if T.ERRORS:
        print("  失败项:", T.ERRORS)
    return T.FAIL


if __name__ == '__main__':
    threading.Thread(target=serve, daemon=True).start()
    time.sleep(2)
    fail = run()
    sys.exit(1 if fail else 0)

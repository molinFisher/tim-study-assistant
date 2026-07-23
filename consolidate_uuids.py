"""
一次性数据合并脚本：单租户场景下，将分散在多个浏览器 uuid 下的
错题/计划/复习/配置数据归并到「数据最多的主 uuid」，并重建知识点
多层结构（自动按学科名去重），消除同一学科在多个 uuid 下重复出现、
录入选择器只显示稀疏知识点的根因。

执行方式：
    cd /workspace/tim-study-assistant
    python3.11 consolidate_uuids.py
"""
import sqlite3
import sys

DB = "data/study_assistant.db"

# 选择「活跃错题数最多」的 uuid 作为主 uuid
conn = sqlite3.connect(DB, timeout=10)
conn.row_factory = sqlite3.Row


def q(sql, args=()):
    return conn.execute(sql, args).fetchall()


print("== 合并前 uuid 分布 ==")
for r in q("SELECT uuid, COUNT(*) c FROM mistake_records WHERE status!='deleted' GROUP BY uuid ORDER BY c DESC"):
    print("  ", r["uuid"], r["c"])

# 主 uuid = 活跃错题最多的
canon = q("SELECT uuid FROM mistake_records WHERE status!='deleted' GROUP BY uuid ORDER BY COUNT(*) DESC LIMIT 1")[0]["uuid"]
print("\n== 主 uuid ==")
print("  ", canon)

# 待归并的 uuid 列表
others = [r["uuid"] for r in q("SELECT DISTINCT uuid FROM mistake_records WHERE uuid<>?", (canon,))]
print("== 待归并 uuid ==")
for u in others:
    print("  ", u)

# 1) 错题主表
conn.execute("UPDATE mistake_records SET uuid=? WHERE uuid<>?", (canon, canon))
# 2) 复习日志
conn.execute("UPDATE review_logs SET uuid=? WHERE uuid<>?", (canon, canon))
# 3) 学习计划
conn.execute("UPDATE study_plans SET uuid=? WHERE uuid<>?", (canon, canon))
# 4) 用户配置
conn.execute("UPDATE user_config SET uuid=? WHERE uuid<>?", (canon, canon))
conn.commit()

print("\n== 归并后 uuid 分布（应为单一主 uuid）==")
for r in q("SELECT uuid, COUNT(*) c FROM mistake_records WHERE status!='deleted' GROUP BY uuid"):
    print("  ", r["uuid"], r["c"])
for t in ("review_logs", "study_plans", "user_config"):
    n = q(f"SELECT COUNT(*) c FROM {t} WHERE uuid<>?", (canon,))[0]["c"]
    print(f"  {t} 非主uuid行数: {n}")

conn.close()

# 5) 重建知识点多层结构（删旧 -> 按命名规则从 zhishidian 重建 -> 统计 rollup）
#    此时全部错题已归并到主 uuid，且 ensure_subject/ensure_node 为全局查找，
#    天然把「数学/英语/物理」等重复学科合并为单一节点。
print("\n== 重建知识点多层结构 ==")
sys.path.insert(0, ".")
import knowledge_tree  # noqa: E402

total = knowledge_tree.migrate_all_knowledge()
print(f"  处理错题数: {total}")

# 6) 校验
conn = sqlite3.connect(DB, timeout=10)
conn.row_factory = sqlite3.Row
print("\n== 合并后知识点顶层学科（应无重复）==")
for r in conn.execute("SELECT name, linked_count FROM knowledge_points WHERE level=1 ORDER BY name"):
    print("  ", r["name"], "关联", r["linked_count"])
dup = conn.execute(
    "SELECT name, COUNT(*) c FROM knowledge_points WHERE level=1 GROUP BY name HAVING COUNT(*)>1"
).fetchall()
print("\n  重复学科节点数:", len(dup))
conn.close()
print("\n完成。")

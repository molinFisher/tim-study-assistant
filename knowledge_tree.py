"""
Tim 学习助手 - 知识点多层结构（思维导图数据模型）操作层

数据模型：
  - knowledge_points : 父子引用树（parent_id 自引用 + level 语义分层）
      level 1 = 学科（复用现有 mistake_records.xueke 字段）
      level 2 = 章
      level 3 = 知识点
  - mistake_knowledge : 错题 <-> 知识点 多对多关联表

命名规则（决策①：命名规则自动拆层级）：
  - zhishidian 字段用 '；' / ';' 分隔同一道错题关联的多个知识点（决策②：多对多）
  - 单个知识点内部用 '/' 表示 章/知识点 层级，例如 "函数/二次函数"
    · 无 '/'  -> 直接作为 level3 知识点，挂在 level1 学科节点下
    · 含 '/'  -> '/' 之前为 level2 章，最后一段为 level3 知识点
    · 多级 '/' -> 除最后一段外合并为单个 level2 章名（决策④：归一化合并策略自定）

单租户场景下知识点库为共享库：知识点节点按 (level, name, parent_id) 全局唯一，
不随浏览器 uuid 分裂；录入选择器可拉取全库（scope=all），思维导图按账号视图展示。
"""
from database import get_db, query_db, execute_db, rows_to_dicts


# ============ 工具函数 ============

def normalize_name(s):
    """清洗知识点名称：去首尾空白、归一化全角空格。"""
    return (s or '').replace('　', ' ').strip()


def split_knowledge_entries(zhishidian):
    """将 zhishidian 拆分为多个知识点条目（按中/英文分号）。"""
    if not zhishidian:
        return []
    parts = []
    for raw in str(zhishidian).replace('；', ';').split(';'):
        n = normalize_name(raw)
        if n:
            parts.append(n)
    return parts


def parse_path(entry):
    """
    解析单个知识点条目，返回 (chapter, point) 元组。
      · 无 '/'  : (None, entry)
      · 含 '/'  : (除最后一段外合并成的章名, 最后一段)
    """
    entry = normalize_name(entry)
    if '/' in entry:
        segs = [normalize_name(s) for s in entry.split('/') if normalize_name(s)]
        if len(segs) >= 2:
            return '/'.join(segs[:-1]), segs[-1]
    return None, entry


# ============ 节点确保（幂等） ============

def ensure_subject(xueke, uuid):
    """确保 level1 学科节点存在（全局查找，避免跨 uuid 重复建节点），返回节点 id。

    单租户场景下知识点库为共享库：按 (level, name, parent_id) 全局唯一匹配，
    不论当前 uuid 是否已存在该学科，都复用同一节点，从根本上杜绝「数学/英语」
    等学科在多个 uuid 下重复出现。新建节点时仍记录传入 uuid 作为归属标记。
    """
    xueke = normalize_name(xueke)
    if not xueke:
        return None
    row = query_db(
        "SELECT id FROM knowledge_points WHERE level=1 AND name=? AND parent_id IS NULL",
        (xueke,), one=True)
    if row:
        return row['id']
    return execute_db(
        """INSERT INTO knowledge_points (parent_id, level, name, xueke, uuid, sort_order, created_at, updated_at)
           VALUES (NULL, 1, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
        (xueke, xueke, uuid))


def ensure_node(name, level, xueke, uuid, parent_id):
    """确保指定 (level, name, parent_id) 的知识点节点存在（全局查找），返回节点 id。

    与 ensure_subject 同理：共享库内按 (level, name, parent_id) 唯一匹配，
    复用既有节点，避免同一 章/知识点 在多个 uuid 下分裂。
    """
    if parent_id is None:
        row = query_db(
            "SELECT id FROM knowledge_points WHERE level=? AND name=? AND parent_id IS NULL",
            (level, name), one=True)
    else:
        row = query_db(
            "SELECT id FROM knowledge_points WHERE level=? AND name=? AND parent_id=?",
            (level, name, parent_id), one=True)
    if row:
        return row['id']
    return execute_db(
        """INSERT INTO knowledge_points (parent_id, level, name, xueke, uuid, sort_order, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
        (parent_id, level, name, xueke, uuid))


def link_mistake(mistake_id, kp_id, uuid):
    """建立错题-知识点多对多关联（幂等）。"""
    existing = query_db(
        "SELECT id FROM mistake_knowledge WHERE mistake_id=? AND kp_id=?",
        (mistake_id, kp_id), one=True)
    if existing:
        return
    execute_db(
        "INSERT INTO mistake_knowledge (mistake_id, kp_id, uuid, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (mistake_id, kp_id, uuid))


# ============ 错题 -> 知识点 同步 ============

def sync_mistake_knowledge(mistake_id, xueke, zhishidian, uuid, replace=True):
    """
    根据错题的 xueke / zhishidian 重建其知识点关联。
      · replace=True  : 先清除旧关联再重建（用于编辑后同步）
      · replace=False : 仅增量补充（用于批量迁移，由调用方统一 recompute）
    自动创建 学科/章/知识点 节点并维护多对多关联；销毁式重建保证一致性。
    """
    if replace:
        execute_db("DELETE FROM mistake_knowledge WHERE mistake_id=?", (mistake_id,))
    subject_id = ensure_subject(xueke, uuid)
    if subject_id is None:
        return
    for entry in split_knowledge_entries(zhishidian):
        chapter, point = parse_path(entry)
        parent_id = subject_id
        if chapter:
            parent_id = ensure_node(chapter, 2, xueke, uuid, subject_id)
        kp_id = ensure_node(point, 3, xueke, uuid, parent_id)
        link_mistake(mistake_id, kp_id, uuid)


# ============ 统计冗余维护 ============

def recompute_knowledge_stats(uuid):
    """
    重算 knowledge_points 的冗余统计字段（linked_count / mastered_count /
    review_count / mastery_rate）。先算叶子(level3)，再逐级向上 rollup。
    mastery_rate = 已掌握错题数 / 关联错题数 * 100（红<40 / 黄40~75 / 绿>75）。
    """
    # 1) 叶子节点(level3)：直接按关联错题聚合
    leaves = query_db("SELECT id FROM knowledge_points WHERE uuid=? AND level=3", (uuid,))
    for lv in leaves:
        kid = lv['id']
        row = query_db(
            '''SELECT COUNT(*) as linked,
                      SUM(CASE WHEN mr.status='mastered' THEN 1 ELSE 0 END) as mastered,
                      COALESCE(SUM(mr.review_count),0) as reviews
               FROM mistake_knowledge mk
               JOIN mistake_records mr ON mr.id = mk.mistake_id
               WHERE mk.kp_id=? AND mr.status != 'deleted' ''',
            (kid,), one=True)
        linked = row['linked'] or 0
        mastered = row['mastered'] or 0
        reviews = row['reviews'] or 0
        rate = round(mastered / linked * 100, 1) if linked else 0.0
        execute_db(
            "UPDATE knowledge_points SET linked_count=?, mastered_count=?, review_count=?, mastery_rate=? WHERE id=?",
            (linked, mastered, reviews, rate, kid))

    # 2) 逐级向上 rollup（章 level2 -> 学科 level1）
    for lvl in (2, 1):
        nodes = query_db("SELECT id FROM knowledge_points WHERE uuid=? AND level=?", (uuid, lvl))
        for n in nodes:
            nid = n['id']
            row = query_db(
                '''SELECT COALESCE(SUM(linked_count),0) as linked,
                          COALESCE(SUM(mastered_count),0) as mastered,
                          COALESCE(SUM(review_count),0) as reviews
                   FROM knowledge_points WHERE uuid=? AND parent_id=?''',
                (uuid, nid), one=True)
            linked = row['linked'] or 0
            mastered = row['mastered'] or 0
            reviews = row['reviews'] or 0
            rate = round(mastered / linked * 100, 1) if linked else 0.0
            execute_db(
                "UPDATE knowledge_points SET linked_count=?, mastered_count=?, review_count=?, mastery_rate=? WHERE id=?",
                (linked, mastered, reviews, rate, nid))


# ============ 树构建（供思维导图消费） ============

def get_knowledge_tree(uuid=None, xueke=None):
    """
    递归构建知识点层级树（按 parent_id）。
    返回根节点(level1 学科)列表，每个节点含 children 子节点。
    字段：id/name/level/xueke/linked_count/mastered_count/review_count/mastery_rate/children

    uuid 过滤说明（单租户共享库）：
      · uuid 为具体值 -> 仅返回该 uuid 下的知识点（思维导图按账号视图）
      · uuid 为 None    -> 返回全库所有知识点（录入选择器 scope=all 使用）
    """
    sql = "SELECT id, parent_id, level, name, xueke, linked_count, mastered_count, review_count, mastery_rate FROM knowledge_points"
    where = []
    params = []
    if uuid:
        where.append("uuid=?")
        params.append(uuid)
    if xueke:
        where.append("xueke=?")
        params.append(xueke)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY level, sort_order, name"
    nodes = rows_to_dicts(query_db(sql, params))

    by_id = {}
    for n in nodes:
        n['children'] = []
        by_id[n['id']] = n

    roots = []
    for n in nodes:
        pid = n['parent_id']
        if pid is not None and pid in by_id:
            by_id[pid]['children'].append(n)
        else:
            roots.append(n)
    return roots


# ============ 全量迁移（幂等，供初始化 / 手动触发） ============

def migrate_all_knowledge():
    """
    对全部历史错题重建知识点多层结构（销毁式重建，天然幂等）。
    1) 清空 knowledge_points / mistake_knowledge
    2) 遍历每个 uuid 下的错题，按命名规则同步关联（不重复 recompute）
    3) 每个 uuid 完成后统一 recompute 统计冗余
    返回迁移的错题数量。
    """
    conn = get_db()
    conn.execute("DELETE FROM mistake_knowledge")
    conn.execute("DELETE FROM knowledge_points")
    conn.commit()
    conn.close()

    uuids = [r['uuid'] for r in query_db("SELECT DISTINCT uuid FROM mistake_records")]
    total = 0
    for uid in uuids:
        rows = query_db(
            "SELECT id, xueke, zhishidian FROM mistake_records WHERE uuid=? AND status != 'deleted' AND zhishidian != ''",
            (uid,))
        for r in rows:
            sync_mistake_knowledge(r['id'], r['xueke'], r['zhishidian'], uid, replace=False)
            total += 1
        recompute_knowledge_stats(uid)
    return total

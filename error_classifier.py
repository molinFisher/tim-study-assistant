"""
Tim 学习助手 - 错误类型自动归类

数据库没有显式「错误类型」字段，这里根据「错误分析」(cuowufenxi) 文本，
辅以「题目」(timu) / 「知识点」(zhishidian) 的弱信号，用关键词词频打分，
把每道错题归类到固定错误类型之一。

错误类型定义和关键词来自 base_data 表（category='error_type'）。
归类结果仅为启发式推断，非精确人工标签，仅供统计参考。
"""

import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_error_types():
    """从 base_data 表加载错误类型和关键词（优先DB，回退硬编码）"""
    from config import Config
    pairs = Config.get_error_types()
    types_list = [p[0] for p in pairs]
    keywords_map = {p[0]: p[1] for p in pairs}
    return types_list, keywords_map


# 模块加载时从 DB 获取
ERROR_TYPES, _ERROR_KEYWORDS = _load_error_types()

# 主信号权重（来自 cuowufenxi）
_PRIMARY_WEIGHT = 1.0
# 弱信号权重（来自 timu / zhishidian）
_WEAK_WEIGHT = 0.3


def _score(text, keywords):
    """统计关键词在文本中的命中次数（子串计数）。"""
    if not text:
        return 0
    return sum(text.count(kw) for kw in keywords)


def classify_error(cuowufenxi='', timu='', zhishidian=''):
    """
    对单道错题归类错误类型。

    参数：
      cuowufenxi : 错误分析文本（主信号，决定是否归类）
      timu       : 题目文本（弱信号，仅在已有主信号时用于区分并列）
      zhishidian : 知识点文本（弱信号，同上）
    返回：ERROR_TYPES 中的某一项。

    说明：错误类型本质是「错在哪」，应来自错误分析文本；timu/zhishidian 多为
    学科或知识点用词，仅作为同分时的微弱区分，不会独立触发归类，避免误判。
    """
    # 主信号：仅依据错误分析文本
    primary_scores = {}
    for etype in ERROR_TYPES:
        if etype == '其他':
            continue
        keywords = _ERROR_KEYWORDS.get(etype, [])
        primary_scores[etype] = _score(cuowufenxi, keywords) * _PRIMARY_WEIGHT

    # 没有主信号（错误分析为空或无关键词）→ 无法归类
    if max(primary_scores.values()) <= 0:
        return '其他'

    # 仅在有主信号的类型中，叠加弱信号打破并列
    best_type = '其他'
    best_score = -1
    for etype in ERROR_TYPES:
        if etype == '其他':
            continue
        if primary_scores[etype] <= 0:
            continue
        score = primary_scores[etype]
        score += _score(timu, _ERROR_KEYWORDS.get(etype, [])) * _WEAK_WEIGHT
        score += _score(zhishidian, _ERROR_KEYWORDS.get(etype, [])) * _WEAK_WEIGHT
        # 并列时保持 ERROR_TYPES 顺序（靠前的类型优先级更高）
        if score > best_score:
            best_score = score
            best_type = etype

    return best_type


def _field(rec, key):
    """兼容 sqlite3.Row 与 dict 取值（Row 没有 .get()）。"""
    if hasattr(rec, 'get'):
        return rec.get(key, '') or ''
    try:
        return rec[key] or ''
    except (KeyError, IndexError, TypeError):
        return ''


def classify_batch(records):
    """
    对一批错题记录（sqlite3.Row 或 dict）批量归类并计数。

    返回：{error_type: count}，键顺序与 ERROR_TYPES 一致，未命中的类型计数为 0。
    """
    counts = {et: 0 for et in ERROR_TYPES}
    for rec in records:
        cuowufenxi = _field(rec, 'cuowufenxi')
        timu = _field(rec, 'timu')
        zhishidian = _field(rec, 'zhishidian')
        etype = classify_error(cuowufenxi, timu, zhishidian)
        if etype not in counts:
            counts[etype] = 0
        counts[etype] += 1
    return counts

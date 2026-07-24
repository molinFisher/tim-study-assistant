"""分页辅助函数 —— 消除 6 条路由中重复的分页逻辑。"""


def paginate(request, default_per_page=20):
    """从 request 中提取分页参数，返回 (page, per_page, offset) 三元组。

    Args:
        request: Flask request 对象
        default_per_page: 默认每页条数

    Returns:
        (page, per_page, offset) — page 已 clamp 到 >=1，per_page clamp 到 [5,100]
    """
    page = request.args.get('page', 1, type=int) or 1
    per_page = request.args.get('per_page', default_per_page, type=int) or default_per_page
    per_page = max(5, min(per_page, 100))
    page = max(1, page)
    offset = (page - 1) * per_page
    return page, per_page, offset


def pagination_meta(total, page, per_page):
    """计算分页元信息。

    Returns:
        dict with keys: page, per_page, total, total_pages, offset
    """
    total_pages = max(1, (total + per_page - 1) // per_page)
    return {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'offset': (page - 1) * per_page,
    }

"""
Blueprint 模块注册。

当前架构采用渐进式拆分策略：
- app.py 中已用注释分块标注各功能模块（# ==== 模块名 ====）
- 后续可按需将各模块提取到 blueprints/ 下的独立文件
- 每个蓝图文件需包含 create_xxx_blueprint() 工厂函数

蓝图拆分清单（待后续按需执行）：
  blueprints/questions.py    — 错题 CRUD（~15 routes）
  blueprints/knowledge.py    — 知识点管理（~12 routes）
  blueprints/study_plans.py  — 学习计划（~10 routes）
  blueprints/review.py       — 复习功能（~7 routes）
  blueprints/ocr.py          — OCR/文档导入（~4 routes）
  blueprints/export.py       — 数据导出（~3 routes）
  blueprints/auth.py         — 认证（~2 routes）
  blueprints/api_v1.py       — 外部 API（~2 routes）
"""


def register_all(app):
    """注册所有蓝图（占位，后续按需启用）。"""
    # from .questions import create_questions_blueprint
    # app.register_blueprint(create_questions_blueprint())
    pass

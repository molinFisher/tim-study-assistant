"""
Tim 学习助手 - 工具函数模块
UUID 管理、图片存储、SM-2/艾宾浩斯复习算法、图表生成
"""
import uuid as uuid_mod
import os
import io
import base64
from datetime import datetime, timedelta
from PIL import Image as PILImage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import request, make_response
from config import Config


# ========== 中文字体设置 ==========
def _setup_cjk_font():
    """
    探测系统中可用于 matplotlib 的 CJK 字体并设为默认，避免图表中文显示为方块。
    找不到时不抛错，仅退化为默认字体（可能显示方块，但不影响功能）。
    """
    try:
        from matplotlib import font_manager

        candidates = []
        for f in font_manager.fontManager.ttflist:
            name = (f.name or '').lower()
            if any(k in name for k in ('cjk', 'noto sans sc', 'wenquanyi',
                                       'source han', 'simhei', 'yahei', 'heiti')):
                candidates.append(f)

        # 优先选 Noto Sans CJK SC / Source Han Sans SC
        chosen = None
        for prefer in ('Noto Sans CJK SC', 'Source Han Sans SC'):
            for f in candidates:
                if f.name == prefer:
                    chosen = f
                    break
            if chosen:
                break
        if chosen is None and candidates:
            chosen = candidates[0]

        if chosen is not None:
            try:
                font_manager.fontManager.addfont(chosen.fname)
            except Exception:
                pass
            plt.rcParams['font.sans-serif'] = [chosen.name]
            plt.rcParams['axes.unicode_minus'] = False
            return chosen.name
    except Exception:
        pass
    return None


_setup_cjk_font()


# ========== UUID 用户标识 ==========

def get_or_create_uuid():
    """从 Cookie 获取 UUID；无 cookie 时优先复用 DB 已有用户（最多记录的 uuid）。
    若 Cookie 中的 uuid 已无任何错题（例如首次打开时生成的空 uuid），同样回退到
    数据最多的 uuid，避免「账号存在但思维导图/错题本一片空白」的问题。仅当 DB
    全空时才真正创建新 uuid。Cookie 会在响应中被写回该 uuid，实现自愈。"""
    user_uuid = request.cookies.get(Config.COOKIE_NAME)
    from database import query_db
    if user_uuid:
        # Cookie 存在但该 uuid 下没有数据 -> 视为空账号，回退到数据最多的 uuid
        try:
            cnt = query_db(
                "SELECT COUNT(*) AS c FROM mistake_records WHERE uuid=? AND status != 'deleted'",
                (user_uuid,), one=True)
            if not cnt or cnt['c'] == 0:
                user_uuid = None
        except Exception:
            user_uuid = None
    if not user_uuid:
        try:
            row = query_db(
                'SELECT uuid, COUNT(*) AS cnt FROM mistake_records '
                'GROUP BY uuid ORDER BY cnt DESC LIMIT 1', one=True)
            if row and row['cnt'] > 0:
                user_uuid = str(row['uuid'])
        except Exception:
            pass
        if not user_uuid:
            user_uuid = str(uuid_mod.uuid4())
    return user_uuid


def set_uuid_cookie(response, user_uuid):
    """设置 UUID Cookie"""
    response.set_cookie(
        Config.COOKIE_NAME,
        user_uuid,
        max_age=Config.COOKIE_MAX_AGE,
        httponly=True,
        samesite='Lax'
    )
    return response


def ensure_user_config(uuid):
    """确保用户配置存在，不存在则创建"""
    from database import query_db, execute_db
    existing = query_db(
        'SELECT id FROM user_config WHERE uuid=?', (uuid,), one=True
    )
    if not existing:
        execute_db(
            'INSERT INTO user_config (uuid, review_algorithm, daily_review_limit) VALUES (?, ?, ?)',
            (uuid, Config.DEFAULT_REVIEW_ALGORITHM, Config.DEFAULT_DAILY_REVIEW_LIMIT)
        )


def get_user_config(uuid):
    """获取用户配置"""
    from database import query_db
    config = query_db(
        'SELECT * FROM user_config WHERE uuid=?', (uuid,), one=True
    )
    return dict(config) if config else {
        'review_algorithm': Config.DEFAULT_REVIEW_ALGORITHM,
        'daily_review_limit': Config.DEFAULT_DAILY_REVIEW_LIMIT,
    }


# ========== 智能图片存储 ==========

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def save_image(file, mistake_id):
    """
    智能存储图片：<100KB 存 BLOB，>=100KB 存文件系统
    返回 image_id
    """
    from database import execute_db
    file_data = file.read()
    file_size = len(file_data)
    original_name = file.filename
    mime_type = file.content_type or 'image/png'

    if file_size < Config.IMAGE_BLOB_THRESHOLD:
        # 存 BLOB
        image_id = execute_db(
            """INSERT INTO mistake_images
               (mistake_id, image_data, image_type, file_size, mime_type, original_name)
               VALUES (?, ?, 'blob', ?, ?, ?)""",
            (mistake_id, file_data, file_size, mime_type, original_name)
        )
    else:
        # 存文件系统
        ext = os.path.splitext(original_name)[1] or '.png'
        filename = f"{uuid_mod.uuid4().hex}{ext}"
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        image_id = execute_db(
            """INSERT INTO mistake_images
               (mistake_id, image_path, image_type, file_size, mime_type, original_name)
               VALUES (?, ?, 'file', ?, ?, ?)""",
            (mistake_id, filepath, file_size, mime_type, original_name)
        )
    return image_id


def get_image_data(image_record):
    """根据存储类型获取图片二进制数据"""
    if image_record['image_type'] == 'blob':
        return image_record['image_data']
    else:
        filepath = image_record['image_path']
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                return f.read()
        return None


def delete_image_files(image_records):
    """删除文件系统上的图片文件"""
    for record in image_records:
        if record['image_type'] == 'file' and record['image_path']:
            filepath = record['image_path']
            if os.path.exists(filepath):
                os.remove(filepath)


# ========== SM-2 间隔重复算法 ==========

def calculate_sm2_next_review(stage, result):
    """
    SM-2 简化版间隔重复算法
    stage: 当前复习阶段 (0-5)
    result: 复习结果 (correct/incorrect/partial)
    返回: (new_stage, next_review_date)
    """
    intervals = Config.SM2_INTERVALS

    if result == 'correct':
        new_stage = min(stage + 1, 5)
    elif result == 'partial':
        new_stage = max(stage, 1)
    else:  # incorrect
        new_stage = 0

    days = intervals.get(new_stage, 30)
    next_date = datetime.now() + timedelta(days=days)
    return new_stage, next_date


# ========== 艾宾浩斯遗忘曲线算法 ==========

def calculate_ebbinghaus_next_review(stage, result):
    """
    艾宾浩斯遗忘曲线间隔重复算法
    stage: 当前复习阶段 (0-7)
    result: 复习结果 (correct/incorrect/partial)
    返回: (new_stage, next_review_date)
    """
    intervals = Config.EBBINGHAUS_INTERVALS

    if result == 'correct':
        new_stage = min(stage + 1, 7)
    elif result == 'partial':
        new_stage = max(stage, 1)
    else:  # incorrect
        new_stage = max(stage - 1, 0)

    minutes = intervals.get(new_stage, 21600)  # 默认 15 天
    next_date = datetime.now() + timedelta(minutes=minutes)
    return new_stage, next_date


# ========== 统一复习计算入口 ==========

def calculate_next_review(algorithm, stage, result):
    """根据算法类型计算下次复习日期"""
    if algorithm == 'ebbinghaus':
        return calculate_ebbinghaus_next_review(stage, result)
    else:
        return calculate_sm2_next_review(stage, result)


# ========== Matplotlib 图表生成 ==========

def generate_pie_chart(labels, values, title=''):
    """生成饼图，返回 Base64 编码"""
    plt.figure(figsize=(7, 5))
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#E91E63',
              '#9C27B0', '#00BCD4', '#FF5722', '#607D8B']
    plt.pie(values, labels=labels, autopct='%1.1f%%',
            colors=colors[:len(labels)], startangle=90,
            textprops={'fontsize': 11})
    plt.title(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    return _fig_to_base64()


def generate_bar_chart(labels, values, title='', xlabel='', ylabel=''):
    """生成柱状图，返回 Base64 编码"""
    plt.figure(figsize=(9, 5))
    colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63',
              '#9C27B0', '#00BCD4']
    bars = plt.bar(labels, values, color=colors[:len(labels)], edgecolor='white', linewidth=0.8)
    for bar, val in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.01,
                 str(val), ha='center', fontsize=10, fontweight='bold')
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel(xlabel, fontsize=11)
    plt.ylabel(ylabel, fontsize=11)
    plt.xticks(rotation=30, ha='right', fontsize=10)
    plt.tight_layout()
    return _fig_to_base64()


def generate_line_chart(x_labels, values, title='', xlabel='', ylabel=''):
    """生成折线图，返回 Base64 编码"""
    plt.figure(figsize=(9, 5))
    plt.plot(x_labels, values, marker='o', linewidth=2,
             markersize=6, color='#2196F3', markerfacecolor='#FF9800')
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel(xlabel, fontsize=11)
    plt.ylabel(ylabel, fontsize=11)
    plt.xticks(rotation=30, ha='right', fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    return _fig_to_base64()


def generate_radar_chart(categories, values, title=''):
    """生成雷达图，返回 Base64 编码"""
    import numpy as np
    N = len(categories)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]

    values_plot = list(values) + [values[0]]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.fill(angles, values_plot, alpha=0.25, color='#2196F3')
    ax.plot(angles, values_plot, linewidth=2, color='#2196F3')
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_yticklabels([])
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    return _fig_to_base64()


def strip_latex(text, max_len=80):
    """去掉 LaTeX 标记，返回纯文本摘要。
    用于列表页等不需要渲染 LaTeX 的场景。
    """
    import re
    if not text:
        return ''
    original = text
    # 去掉 $$ ... $$ 块
    text = re.sub(r'\$\$.*?\$\$', '', text, flags=re.DOTALL)
    # 去掉 $ ... $ 行内公式
    text = re.sub(r'\$[^$]*\$', '', text)
    # 去掉 \begin{...} \end{...} 残留
    text = re.sub(r'\\begin\{[^}]*\}', '', text)
    text = re.sub(r'\\end\{[^}]*\}', '', text)
    # 去掉 LaTeX 命令如 \dfrac, \text, \displaystyle, \[4pt] 等
    text = re.sub(r'\\[a-zA-Z]+(\{[^}]*\})*', '', text)
    text = re.sub(r'\\\[[^\]]*\]', '', text)
    # 去掉多余的 LaTeX 符号残留
    text = re.sub(r'[\\{}]', '', text)
    text = re.sub(r'\$+', '', text)
    text = re.sub(r'\[[0-9.]*pt\]', '', text)  # 去掉间距标记 [4pt] 等
    # 去掉多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = text.strip()
    # 如果纯文本太短，尝试从原始文本中提取非 LaTeX 的行作为摘要
    if len(text) < 10:
        # 取第一行非空非 LaTeX 文本
        lines = [l.strip() for l in original.split('\n')
                 if l.strip() and not l.strip().startswith(('$', '\\'))]
        if lines:
            text = ' '.join(lines[:2])
    if len(text) > max_len:
        text = text[:max_len] + '...'
    return text


def _fig_to_base64():
    """将当前 matplotlib figure 转为 Base64 字符串"""
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

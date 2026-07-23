"""
Tim 学习助手 - 数据库初始化与操作层
使用原生 sqlite3，参数化查询防注入
"""
import sqlite3
import os
from config import Config


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """初始化数据库：创建所有表和索引"""
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # ========== 1. 错题记录表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mistake_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL,
            sys_platform TEXT NOT NULL DEFAULT 'web',
            bstudio_create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            xueke TEXT NOT NULL,
            timu TEXT NOT NULL,
            xueshengdaan TEXT DEFAULT '',
            zhengquedaan TEXT DEFAULT '',
            cuowufenxi TEXT DEFAULT '',
            zhishidian TEXT DEFAULT '',
            difficulty INTEGER DEFAULT 1,
            review_count INTEGER DEFAULT 0,
            last_review_at TIMESTAMP,
            next_review_at TIMESTAMP,
            review_stage INTEGER DEFAULT 0,
            review_algorithm TEXT DEFAULT 'sm2',
            status TEXT DEFAULT 'active',
            voice_data TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ========== 2. 错题图片表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mistake_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mistake_id INTEGER NOT NULL,
            image_data BLOB,
            image_path TEXT,
            image_type TEXT NOT NULL,
            file_size INTEGER,
            mime_type TEXT,
            original_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (mistake_id) REFERENCES mistake_records(id) ON DELETE CASCADE
        )
    ''')

    # ========== 3. 学习计划表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            xueke TEXT DEFAULT '',
            zhishidian TEXT DEFAULT '',
            target_date DATE,
            priority INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    # ========== 4. 复习记录表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS review_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mistake_id INTEGER NOT NULL,
            uuid TEXT NOT NULL,
            review_date DATE NOT NULL,
            result TEXT NOT NULL,
            time_spent INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (mistake_id) REFERENCES mistake_records(id) ON DELETE CASCADE
        )
    ''')

    # ========== 5. 用户配置表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            review_algorithm TEXT DEFAULT 'sm2',
            daily_review_limit INTEGER DEFAULT 20,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ========== 6. 基础数据表（学科/错误类型/知识点） ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS base_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            extra TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ========== 7. 用户表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ========== 创建索引 ==========
    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_mr_uuid ON mistake_records(uuid)',
        'CREATE INDEX IF NOT EXISTS idx_mr_xueke ON mistake_records(xueke)',
        'CREATE INDEX IF NOT EXISTS idx_mr_zhishidian ON mistake_records(zhishidian)',
        'CREATE INDEX IF NOT EXISTS idx_mr_create_time ON mistake_records(bstudio_create_time)',
        'CREATE INDEX IF NOT EXISTS idx_mr_next_review ON mistake_records(next_review_at)',
        'CREATE INDEX IF NOT EXISTS idx_mr_status ON mistake_records(status)',
        'CREATE INDEX IF NOT EXISTS idx_mi_mistake_id ON mistake_images(mistake_id)',
        'CREATE INDEX IF NOT EXISTS idx_sp_uuid ON study_plans(uuid)',
        'CREATE INDEX IF NOT EXISTS idx_rl_mistake_id ON review_logs(mistake_id)',
        'CREATE INDEX IF NOT EXISTS idx_rl_date ON review_logs(review_date)',
    ]
    for idx_sql in indexes:
        cursor.execute(idx_sql)

    # ========== 8. API Token 表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            token_prefix TEXT NOT NULL,
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            rate_limit INTEGER DEFAULT 60,
            last_used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON api_tokens(user_id)')

    # 迁移：确保 voice_data 列存在
    try:
        cursor.execute("ALTER TABLE mistake_records ADD COLUMN voice_data TEXT DEFAULT ''")
    except Exception:
        pass

    # 种子数据：学科（如果 base_data 为空）
    cnt = cursor.execute("SELECT COUNT(*) FROM base_data").fetchone()[0]
    if cnt == 0:
        import json as _json
        seeds = [
            ('subject', '数学', '', 1),
            ('subject', '物理', '', 2),
            ('subject', '道法', '', 3),
            ('subject', '语文', '', 4),
            ('subject', '英语', '', 5),
            ('subject', '生物', '', 6),
            ('subject', '化学', '', 7),
            ('subject', '信奥', '', 8),
            ('error_type', '计算错误', _json.dumps(['计算','算错','粗心','进位','符号','运算','加减','乘除','漏算']), 1),
            ('error_type', '概念不清', _json.dumps(['概念','理解','混淆','定义','性质','定理','不清','没掌握']), 2),
            ('error_type', '审题失误', _json.dumps(['审题','读题','看错','漏看','题意','条件','没看清']), 3),
            ('error_type', '公式记忆错误', _json.dumps(['公式','记错','记混','记不住','背错']), 4),
            ('error_type', '方法不当', _json.dumps(['方法','思路','步骤','技巧','不会做']), 5),
            ('error_type', '其他', '[]', 6),
        ]
        cursor.executemany(
            "INSERT INTO base_data(category,name,extra,sort_order) VALUES(?,?,?,?)",
            seeds)
        # 知识点种子：从已有 zhishidian 去重
        cur2 = conn.cursor()
        kps = cur2.execute("SELECT DISTINCT zhishidian FROM mistake_records WHERE zhishidian!=''").fetchall()
        for (kp,) in kps:
            cursor.execute("INSERT INTO base_data(category,name,sort_order) VALUES('knowledge_point',?,99)", (kp,))
        cur2.close()

    # 种子用户（默认 tim / tim123）
    uc = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if uc == 0:
        from werkzeug.security import generate_password_hash
        cursor.execute("INSERT INTO users(username, password_hash) VALUES(?,?)",
                       ('tim', generate_password_hash('tim123')))

    conn.commit()
    conn.close()
    print("��� 数据库初始化完成")


# ========== 便捷操作函数 ==========

def row_to_dict(row):
    """将 sqlite3.Row 转为可变 dict"""
    return dict(row) if row else None

def rows_to_dicts(rows):
    """将 sqlite3.Row 列表转为 dict 列表"""
    return [dict(r) for r in rows]

def query_db(query, args=(), one=False):
    """通用查询（自动过滤 mistake_records 中已删除的数据）"""
    if 'mistake_records' in query and 'WHERE 1=1' in query:
        query = query.replace('WHERE 1=1', "WHERE status != 'deleted'")
    conn = get_db()
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """通用写入，返回 lastrowid"""
    conn = get_db()
    cur = conn.execute(query, args)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def execute_many(query, args_list):
    """批量写入"""
    conn = get_db()
    conn.executemany(query, args_list)
    conn.commit()
    conn.close()

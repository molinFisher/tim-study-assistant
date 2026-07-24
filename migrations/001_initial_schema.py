"""001: 初始 Schema —— 创建所有核心表与索引。

此迁移对应 init_db() 中的完整建表逻辑。
后续 DDL 变更通过新的迁移文件追加，不再直接修改 init_db()。
"""


def up(conn):
    cur = conn.cursor()

    # 错题记录
    cur.execute('''
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

    # 错题图片
    cur.execute('''
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

    # 学习计划
    cur.execute('''
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

    # 复习记录
    cur.execute('''
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

    # 用户配置
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            review_algorithm TEXT DEFAULT 'sm2',
            daily_review_limit INTEGER DEFAULT 20,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 基础数据
    cur.execute('''
        CREATE TABLE IF NOT EXISTS base_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            extra TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 用户表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 计划-错题关联
    cur.execute('''
        CREATE TABLE IF NOT EXISTS plan_mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            mistake_id INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES study_plans(id),
            FOREIGN KEY (mistake_id) REFERENCES mistake_records(id),
            UNIQUE(plan_id, mistake_id)
        )
    ''')

    # API Token
    cur.execute('''
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

    # 知识点多层结构
    cur.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            level INTEGER NOT NULL DEFAULT 3,
            name TEXT NOT NULL,
            xueke TEXT DEFAULT '',
            uuid TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            linked_count INTEGER DEFAULT 0,
            mastered_count INTEGER DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            mastery_rate REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES knowledge_points(id) ON DELETE CASCADE
        )
    ''')

    # 错题-知识点多对多
    cur.execute('''
        CREATE TABLE IF NOT EXISTS mistake_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mistake_id INTEGER NOT NULL,
            kp_id INTEGER NOT NULL,
            uuid TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (mistake_id) REFERENCES mistake_records(id) ON DELETE CASCADE,
            FOREIGN KEY (kp_id) REFERENCES knowledge_points(id) ON DELETE CASCADE,
            UNIQUE(mistake_id, kp_id)
        )
    ''')

    # 索引
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
        'CREATE INDEX IF NOT EXISTS idx_pm_plan_id ON plan_mistakes(plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_pm_mistake_id ON plan_mistakes(mistake_id)',
        'CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash)',
        'CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON api_tokens(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_kp_uuid ON knowledge_points(uuid)',
        'CREATE INDEX IF NOT EXISTS idx_kp_parent ON knowledge_points(parent_id)',
        'CREATE INDEX IF NOT EXISTS idx_kp_xueke ON knowledge_points(xueke)',
        'CREATE INDEX IF NOT EXISTS idx_mk_mistake ON mistake_knowledge(mistake_id)',
        'CREATE INDEX IF NOT EXISTS idx_mk_kp ON mistake_knowledge(kp_id)',
        'CREATE INDEX IF NOT EXISTS idx_mk_uuid ON mistake_knowledge(uuid)',
    ]
    for idx_sql in indexes:
        cur.execute(idx_sql)


def down(conn):
    """回滚：删除所有表（危险操作，仅开发环境使用）"""
    tables = [
        'mistake_knowledge', 'knowledge_points', 'api_tokens',
        'plan_mistakes', 'review_logs', 'study_plans',
        'base_data', 'user_config', 'users', 'mistake_images', 'mistake_records',
    ]
    for t in tables:
        conn.execute(f"DROP TABLE IF EXISTS {t}")

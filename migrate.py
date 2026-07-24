"""数据库迁移管理器。

设计：
- 每个迁移是一个 .py 文件，包含 up() 和 down() 两个函数
- 迁移文件命名: NNN_description.py（NNN 为三位数字序号）
- 在数据库中维护 _migrations 表记录已应用的迁移
- 启动时自动检测并执行未应用的迁移（按序号升序）
"""

import os
import importlib.util
import sqlite3
from config import Config

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')


def _ensure_meta_table(conn):
    """确保迁移元数据表存在"""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()


def _get_applied(conn):
    """获取已应用的迁移名称列表"""
    rows = conn.execute("SELECT name FROM _migrations ORDER BY id").fetchall()
    return {r[0] for r in rows}


def _load_migration(filepath):
    """加载迁移模块，返回 (name, up_func, down_func)"""
    name = os.path.splitext(os.path.basename(filepath))[0]
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return name, getattr(mod, 'up', None), getattr(mod, 'down', None)


def run_migrations():
    """执行所有未应用的迁移"""
    if not os.path.isdir(MIGRATIONS_DIR):
        return

    migration_files = sorted(
        [f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.py') and not f.startswith('_')]
    )

    if not migration_files:
        return

    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_meta_table(conn)
    applied = _get_applied(conn)

    for mf in migration_files:
        name = os.path.splitext(mf)[0]
        if name in applied:
            continue

        filepath = os.path.join(MIGRATIONS_DIR, mf)
        try:
            mig_name, up_fn, _ = _load_migration(filepath)
            print(f"  📦 执行迁移: {mig_name}")
            up_fn(conn)
            conn.execute("INSERT INTO _migrations(name) VALUES(?)", (mig_name,))
            conn.commit()
            print(f"  ✅ {mig_name} 完成")
        except Exception as e:
            conn.rollback()
            print(f"  ❌ 迁移 {name} 失败: {e}")
            raise

    conn.close()


def rollback_last():
    """回滚最近一次迁移"""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    _ensure_meta_table(conn)
    row = conn.execute("SELECT name FROM _migrations ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        print("没有可回滚的迁移")
        conn.close()
        return

    name = row[0]
    filepath = os.path.join(MIGRATIONS_DIR, f"{name}.py")
    if not os.path.exists(filepath):
        print(f"迁移文件不存在: {filepath}")
        conn.close()
        return

    try:
        _, _, down_fn = _load_migration(filepath)
        print(f"  ⏪ 回滚迁移: {name}")
        down_fn(conn)
        conn.execute("DELETE FROM _migrations WHERE name=?", (name,))
        conn.commit()
        print(f"  ✅ {name} 已回滚")
    except Exception as e:
        conn.rollback()
        print(f"  ❌ 回滚失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback_last()
    else:
        run_migrations()

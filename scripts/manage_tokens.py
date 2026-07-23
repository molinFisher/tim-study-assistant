#!/usr/bin/env python3
"""
API Token 命令行管理工具
用法:
  python scripts/manage_tokens.py create --user tim --name "桌面客户端" --rate 120
  python scripts/manage_tokens.py list
  python scripts/manage_tokens.py revoke --id 1
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, query_db, execute_db
from api_auth import create_token_record, get_token_prefix


def cmd_create(args):
    """创建新的 API Token"""
    user = query_db("SELECT id, username FROM users WHERE username = ?", (args.user,), one=True)
    if not user:
        print(f"❌ 用户 '{args.user}' 不存在")
        sys.exit(1)

    full_token, token_id = create_token_record(
        user_id=user['id'],
        name=args.name,
        description=args.desc or '',
        rate_limit=args.rate
    )

    print("✅ Token 创建成功！")
    print(f"   ID:      {token_id}")
    print(f"   名称:    {args.name}")
    print(f"   用户:    {args.user}")
    print(f"   限速:    {args.rate} 次/分钟")
    print(f"   Token:   {full_token}")
    print()
    print("⚠️  请立即保存以上 Token，明文仅显示这一次！")


def cmd_list(args):
    """列出所有 API Token"""
    rows = query_db(
        '''SELECT t.*, u.username
           FROM api_tokens t
           JOIN users u ON t.user_id = u.id
           ORDER BY t.created_at DESC'''
    )

    if not rows:
        print("(暂无 API Token)")
        return

    print(f"{'ID':<5} {'用户':<10} {'名称':<16} {'前缀':<16} {'状态':<6} {'限速':<8} {'最后使用'}")
    print("-" * 90)
    for t in rows:
        status = '启用' if t['is_active'] else '已停用'
        last = t['last_used_at'][:16] if t['last_used_at'] else '从未使用'
        print(f"{t['id']:<5} {t['username']:<10} {t['name']:<16} {t['token_prefix']:<16} {status:<6} {t['rate_limit']}/min   {last}")


def cmd_revoke(args):
    """撤销（停用）API Token"""
    token = query_db("SELECT id, name FROM api_tokens WHERE id = ?", (args.id,), one=True)
    if not token:
        print(f"❌ Token ID {args.id} 不存在")
        sys.exit(1)

    execute_db("UPDATE api_tokens SET is_active = 0 WHERE id = ?", (args.id,))
    print(f"✅ Token「{token['name']}」(ID={args.id}) 已停用")


def main():
    parser = argparse.ArgumentParser(description='API Token 管理工具')
    sub = parser.add_subparsers(dest='cmd', required=True)

    # create
    p_create = sub.add_parser('create', help='创建 Token')
    p_create.add_argument('--user', required=True, help='用户名')
    p_create.add_argument('--name', required=True, help='Token 名称')
    p_create.add_argument('--desc', help='描述')
    p_create.add_argument('--rate', type=int, default=60, help='速率限制（次/分钟），默认 60')
    p_create.set_defaults(func=cmd_create)

    # list
    p_list = sub.add_parser('list', help='列出所有 Token')
    p_list.set_defaults(func=cmd_list)

    # revoke
    p_revoke = sub.add_parser('revoke', help='撤销 Token')
    p_revoke.add_argument('--id', type=int, required=True, help='Token ID')
    p_revoke.set_defaults(func=cmd_revoke)

    args = parser.parse_args()

    # 确保数据库已初始化
    init_db()

    args.func(args)


if __name__ == '__main__':
    main()

"""
API Token 认证模块
- Token 生成：tim_ + 32 位随机十六进制
- Token 存储：SHA256 哈希，不存明文
- 认证装饰器：从 Authorization header 提取 Bearer token
"""
import hashlib
import secrets
from functools import wraps
from datetime import datetime
from flask import request, jsonify, g
from database import query_db, execute_db


def generate_api_token():
    """生成 API Token: tim_ + 32 位随机十六进制（128 位熵）"""
    return 'tim_' + secrets.token_hex(16)


def hash_token(token):
    """对 token 做 SHA256 哈希存储"""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def get_token_prefix(token):
    """提取 token 前 12 字符用于 UI 展示（含 tim_ 前缀 + 8 字符）"""
    return token[:12]


def create_token_record(user_id, name='', description='', rate_limit=60, expires_at=None):
    """
    创建 API Token 并保存到数据库。
    返回 (full_token, token_id) — 明文 token 仅在此刻可获取，请提示用户保存。
    """
    full_token = generate_api_token()
    token_hash_val = hash_token(full_token)
    token_prefix = get_token_prefix(full_token)

    token_id = execute_db(
        '''INSERT INTO api_tokens
           (user_id, token_hash, token_prefix, name, description, rate_limit, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (user_id, token_hash_val, token_prefix, name, description, rate_limit, expires_at)
    )
    return full_token, token_id


def api_token_required(f):
    """
    API Token 认证装饰器。
    从 Authorization: Bearer <token> 提取 token，
    验证后设置 g.api_token_id、g.api_user_id、g.api_username、g.api_token_rate_limit。
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': 'UNAUTHORIZED',
                'message': '缺少有效的 Authorization header (Bearer Token)'
            }), 401

        token = auth_header[7:].strip()
        if not token:
            return jsonify({
                'success': False,
                'error': 'UNAUTHORIZED',
                'message': 'Token 不能为空'
            }), 401

        token_hash_val = hash_token(token)

        row = query_db(
            '''SELECT t.*, u.username, u.id as uid
               FROM api_tokens t
               JOIN users u ON t.user_id = u.id
               WHERE t.token_hash = ? AND t.is_active = 1''',
            (token_hash_val,), one=True
        )

        if not row:
            return jsonify({
                'success': False,
                'error': 'INVALID_TOKEN',
                'message': 'Token 无效或已被停用'
            }), 401

        # 检查过期
        if row['expires_at']:
            try:
                expires = datetime.fromisoformat(row['expires_at'].replace('Z', '+00:00'))
                if datetime.utcnow() > expires:
                    return jsonify({
                        'success': False,
                        'error': 'TOKEN_EXPIRED',
                        'message': 'Token 已过期'
                    }), 401
            except Exception:
                pass

        # 更新最后使用时间
        execute_db(
            'UPDATE api_tokens SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?',
            (row['id'],)
        )

        g.api_token_id = row['id']
        g.api_user_id = row['user_id']
        g.api_username = row['username']
        g.api_token_rate_limit = row['rate_limit']

        return f(*args, **kwargs)

    return decorated

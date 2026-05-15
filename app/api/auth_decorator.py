"""认证装饰器"""
from functools import wraps
from flask import request, jsonify
from app.models.user import User

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '')
        if not token:
            return jsonify({'code': 4001, 'message': '缺少认证令牌'}), 401
        # 简单验证：token 即 user_id
        kwargs['user_id'] = token
        return f(*args, **kwargs)
    return decorated

def require_admin(user_id):
    """检查用户是否为管理员（admin 或 super_admin）"""
    user = User.get_by_id(user_id)
    return user and user.get('role') in ('admin', 'super_admin')

def require_super_admin(user_id):
    """检查用户是否为超级管理员"""
    user = User.get_by_id(user_id)
    return user and user.get('role') == 'super_admin'
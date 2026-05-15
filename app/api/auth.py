"""认证接口 - 支持公司+部门注册"""
from flask import Blueprint, request, jsonify
from app.services.auth_service import AuthService
from app.api.auth_decorator import require_auth

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    result = AuthService.register(
        username=data.get('username', ''),
        password=data.get('password', ''),
        email=data.get('email', ''),
        wechat_id=data.get('wechat_id', ''),
        company_name=data.get('companyName', ''),
        department_name=data.get('departmentName', '')
    )
    if result['success']:
        return jsonify({'code': result['code'], 'message': '注册成功', 'data': {
            'token': result['token'],
            'user': {
                'id': result['user_id'],
                'username': result['username'],
                'role': result.get('role', 'customer'),
                'company_id': result.get('company_id'),
                'department_id': result.get('department_id'),
            }
        }}), 201
    return jsonify({'code': result['code'], 'message': result['error']}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    result = AuthService.login(data.get('username', ''), data.get('password', ''))
    if result['success']:
        return jsonify({'code': result['code'], 'message': '登录成功', 'data': {
            'token': result['token'],
            'user': {
                'id': result['user_id'],
                'username': result['username'],
                'role': result.get('role', 'customer'),
                'company_id': result.get('company_id'),
                'department_id': result.get('department_id'),
            }
        }})
    return jsonify({'code': result['code'], 'message': result['error']}), 401

@auth_bp.route('/profile', methods=['GET'])
@require_auth
def get_profile(user_id):
    profile = AuthService.get_user_profile(user_id)
    if profile:
        return jsonify({'code': 0, 'message': '获取成功', 'data': profile})
    return jsonify({'code': 5001, 'message': '用户不存在'}), 404

@auth_bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile(user_id):
    data = request.json or {}
    AuthService.update_profile(user_id, email=data.get('email'), wechat_id=data.get('wechat_id'))
    return jsonify({'code': 0, 'message': '更新成功'})
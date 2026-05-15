"""话术库管理接口"""
from flask import Blueprint, request, jsonify
from app.models.message import Message
from app.models.user import User
from app.api.auth_decorator import require_auth

msg_bp = Blueprint('message', __name__, url_prefix='/api/messages')

def get_user_company(user_id):
    user = User.get_by_id(user_id)
    if not user or not user.get('company_id'):
        return None
    return user['company_id']

@msg_bp.route('', methods=['GET'])
@require_auth
def list_messages(user_id):
    """获取话术列表"""
    company_id = get_user_company(user_id)
    if not company_id:
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 50, type=int)
    category_id = request.args.get('category_id', type=int)
    keyword = request.args.get('keyword', '')
    
    result = Message.get_by_company(
        company_id=company_id,
        department_id=None,
        user_id=None,
        category_id=category_id,
        keyword=keyword,
        page=page,
        page_size=page_size
    )
    return jsonify({'code': 0, 'message': '获取成功', 'data': result})

@msg_bp.route('', methods=['POST'])
@require_auth
def create_message(user_id):
    """创建话术"""
    company_id = get_user_company(user_id)
    if not company_id:
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    
    user = User.get_by_id(user_id)
    data = request.json or {}
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    
    if not title or not content:
        return jsonify({'code': 1002, 'message': '标题和内容必填'}), 400
    
    result = Message.create(
        company_id=company_id,
        title=title,
        content=content,
        level=data.get('level', 'private'),
        department_id=user.get('department_id'),
        user_id=user_id,
        category_id=data.get('category_id'),
        tags=data.get('tags', []),
        images=data.get('images', []),
        files=data.get('files', [])
    )
    if result:
        return jsonify({'code': 0, 'message': '创建成功', 'data': result}), 201
    return jsonify({'code': 5000, 'message': '创建失败'}), 500

@msg_bp.route('/<int:msg_id>', methods=['GET'])
@require_auth
def get_message(user_id, msg_id):
    """获取单个话术"""
    msg = Message.get_by_id(msg_id)
    if msg:
        return jsonify({'code': 0, 'message': '获取成功', 'data': msg})
    return jsonify({'code': 4042, 'message': '话术不存在'}), 404

def require_message_owner(user_id, msg_id):
    """检查用户是否有权限操作此话术
    - 管理员可以操作所有话术
    - 普通用户只能操作自己创建的话术
    """
    user = User.get_by_id(user_id)
    if not user:
        return False, '用户不存在'
    # 管理员可以操作所有话术
    if user.get('role') == 'admin':
        return True, None
    # 获取话术信息
    msg = Message.get_by_id(msg_id)
    if not msg:
        return False, '话术不存在'
    # 普通用户只能操作自己创建的话术
    if msg.get('user_id') == user_id:
        return True, None
    return False, '只能修改自己创建的话术'

@msg_bp.route('/<int:msg_id>', methods=['PUT'])
@require_auth
def update_message(user_id, msg_id):
    """更新话术 - 只能修改自己的话术（管理员除外）"""
    can_edit, error_msg = require_message_owner(user_id, msg_id)
    if not can_edit:
        return jsonify({'code': 4031, 'message': error_msg}), 403
    
    data = request.json or {}
    Message.update(msg_id, title=data.get('title'), content=data.get('content'), 
                   category_id=data.get('category_id'), tags=data.get('tags'))
    return jsonify({'code': 0, 'message': '更新成功'})

@msg_bp.route('/<int:msg_id>', methods=['DELETE'])
@require_auth
def delete_message(user_id, msg_id):
    """删除话术 - 只能删除自己的话术（管理员除外）"""
    can_delete, error_msg = require_message_owner(user_id, msg_id)
    if not can_delete:
        return jsonify({'code': 4031, 'message': error_msg}), 403
    
    Message.delete(msg_id)
    return jsonify({'code': 0, 'message': '删除成功'})
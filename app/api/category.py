"""话术分类管理接口"""
from flask import Blueprint, request, jsonify
from app.models.category import Category
from app.models.user import User
from app.api.auth_decorator import require_auth

cat_bp = Blueprint('category', __name__, url_prefix='/api/categories')

def get_user_company(user_id):
    user = User.get_by_id(user_id)
    if not user or not user.get('company_id'):
        return None
    return user['company_id']

@cat_bp.route('', methods=['GET'])
@require_auth
def list_categories(user_id):
    """获取分类列表"""
    company_id = get_user_company(user_id)
    if not company_id:
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    cats = Category.get_by_company(company_id)
    return jsonify({'code': 0, 'message': '获取成功', 'data': cats})

@cat_bp.route('', methods=['POST'])
@require_auth
def create_category(user_id):
    """创建分类"""
    user = User.get_by_id(user_id)
    company_id = get_user_company(user_id)
    if not company_id:
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 1002, 'message': '分类名称必填'}), 400
    
    level = data.get('level', 'private')  # private/department/public
    result = Category.create(
        company_id=company_id,
        name=name,
        level=level,
        department_id=user.get('department_id'),
        user_id=user_id,
        parent_id=data.get('parent_id'),
        color=data.get('color', '#2563EB')
    )
    if result:
        return jsonify({'code': 0, 'message': '创建成功', 'data': result}), 201
    return jsonify({'code': 5000, 'message': '创建失败'}), 500

@cat_bp.route('/<int:cat_id>', methods=['PUT'])
@require_auth
def update_category(user_id, cat_id):
    """更新分类"""
    user = User.get_by_id(user_id)
    if not user or user.get('role') != 'admin':
        return jsonify({'code': 4031, 'message': '仅管理员可更新分类'}), 403
    
    data = request.json or {}
    Category.update(cat_id, name=data.get('name'), color=data.get('color'), sort_order=data.get('sort_order'))
    return jsonify({'code': 0, 'message': '更新成功'})

@cat_bp.route('/<int:cat_id>', methods=['DELETE'])
@require_auth
def delete_category(user_id, cat_id):
    """删除分类"""
    user = User.get_by_id(user_id)
    if not user or user.get('role') != 'admin':
        return jsonify({'code': 4031, 'message': '仅管理员可删除分类'}), 403
    Category.delete(cat_id)
    return jsonify({'code': 0, 'message': '删除成功'})
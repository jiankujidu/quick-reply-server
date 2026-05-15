"""部门管理接口"""
from flask import Blueprint, request, jsonify
from app.models.department import Department
from app.models.user import User
from app.api.auth_decorator import require_auth

dept_bp = Blueprint('department', __name__, url_prefix='/api/departments')

def get_user_company(user_id):
    user = User.get_by_id(user_id)
    if not user or not user.get('company_id'):
        return None
    return user['company_id']

@dept_bp.route('', methods=['GET'])
@require_auth
def list_departments(user_id):
    """获取当前公司的部门列表"""
    company_id = get_user_company(user_id)
    if not company_id:
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    depts = Department.get_by_company(company_id)
    return jsonify({'code': 0, 'message': '获取成功', 'data': depts})

@dept_bp.route('', methods=['POST'])
@require_auth
def create_department(user_id):
    """创建部门"""
    from app.models.user import User
    user = User.get_by_id(user_id)
    if not user or user.get('role') != 'admin':
        return jsonify({'code': 4031, 'message': '仅管理员可创建部门'}), 403
    
    company_id = get_user_company(user_id)
    if not company_id:
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 1002, 'message': '部门名称必填'}), 400
    
    result = Department.create(company_id, name)
    if result:
        return jsonify({'code': 0, 'message': '创建成功', 'data': result}), 201
    return jsonify({'code': 5000, 'message': '创建失败'}), 500

@dept_bp.route('/<int:dept_id>', methods=['PUT'])
@require_auth
def update_department(user_id, dept_id):
    """更新部门"""
    from app.models.user import User
    user = User.get_by_id(user_id)
    if not user or user.get('role') != 'admin':
        return jsonify({'code': 4031, 'message': '仅管理员可更新部门'}), 403
    
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 1002, 'message': '部门名称必填'}), 400
    
    Department.update(dept_id, name)
    return jsonify({'code': 0, 'message': '更新成功'})

@dept_bp.route('/<int:dept_id>', methods=['DELETE'])
@require_auth
def delete_department(user_id, dept_id):
    """删除部门"""
    from app.models.user import User
    user = User.get_by_id(user_id)
    if not user or user.get('role') != 'admin':
        return jsonify({'code': 4031, 'message': '仅管理员可删除部门'}), 403
    
    Department.delete(dept_id)
    return jsonify({'code': 0, 'message': '删除成功'})
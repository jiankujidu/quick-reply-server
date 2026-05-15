"""公司管理接口"""
from flask import Blueprint, request, jsonify
from app.models.company import Company
from app.api.auth_decorator import require_auth

company_bp = Blueprint('company', __name__, url_prefix='/api/company')

@company_bp.route('', methods=['GET'])
@require_auth
def get_company(user_id):
    """获取公司信息（当前用户所属公司）"""
    from app.models.user import User
    user = User.get_by_id(user_id)
    if not user or not user.get('company_id'):
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    
    company = Company.get_by_id(user['company_id'])
    if not company:
        return jsonify({'code': 4041, 'message': '公司不存在'}), 404
    return jsonify({'code': 0, 'message': '获取成功', 'data': company})

@company_bp.route('', methods=['POST'])
@require_auth
def create_company(user_id):
    """创建公司（管理员）"""
    from app.models.user import User
    user = User.get_by_id(user_id)
    if not user or user.get('role') != 'admin':
        return jsonify({'code': 4031, 'message': '仅管理员可创建公司'}), 403
    
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 1002, 'message': '公司名称必填'}), 400
    
    # 检查是否已存在公司
    if Company.get_by_name(name):
        return jsonify({'code': 1001, 'message': '公司已存在'}), 400
    
    result = Company.create(name)
    if result:
        return jsonify({'code': 0, 'message': '创建成功', 'data': result}), 201
    return jsonify({'code': 5000, 'message': '创建失败'}), 500

@company_bp.route('/all', methods=['GET'])
@require_auth
def list_all_companies(user_id):
    """获取所有公司列表（管理员）"""
    from app.models.user import User
    user = User.get_by_id(user_id)
    if not user or user.get('role') != 'admin':
        return jsonify({'code': 4031, 'message': '仅管理员可查看'}), 403
    
    companies = Company.get_all()
    return jsonify({'code': 0, 'message': '获取成功', 'data': companies})
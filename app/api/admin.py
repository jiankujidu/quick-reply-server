"""管理员接口 - 用户/公司/部门/分类/话术管理"""
from flask import Blueprint, request, jsonify
from app.models.user import User
from app.models.department import Department
from app.models.company import Company
from app.models.category import Category
from app.models.message import Message
from app.api.auth_decorator import require_auth, require_admin, require_super_admin

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

def get_user_company(user_id):
    user = User.get_by_id(user_id)
    if not user or not user.get('company_id'):
        return None
    return user['company_id']

# ==================== 统计 ====================
@admin_bp.route('/stats', methods=['GET'])
@require_auth
def get_stats(user_id):
    """获取统计数据"""
    stats = {
        'users': User.count_all(),
        'companies': Company.count_all() if hasattr(Company, 'count_all') else len(Company.get_all()),
        'messages': Message.count_all() if hasattr(Message, 'count_all') else 0,
        'categories': Category.count_all() if hasattr(Category, 'count_all') else 0,
    }
    return jsonify({'code': 0, 'data': stats})

# ==================== 公司管理 ====================
@admin_bp.route('/company', methods=['GET'])
@require_auth
def get_company(user_id):
    """获取当前用户公司信息"""
    company_id = get_user_company(user_id)
    if not company_id:
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    comp = Company.get_by_id(company_id)
    return jsonify({'code': 0, 'data': comp})

@admin_bp.route('/companies', methods=['GET'])
@require_auth
def list_companies(user_id):
    """获取所有公司列表（管理员）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    companies = Company.get_all()
    return jsonify({'code': 0, 'data': {'items': companies}})

@admin_bp.route('/companies', methods=['POST'])
@require_auth
def create_company(user_id):
    """创建公司（仅超级管理员）"""
    if not require_super_admin(user_id):
        return jsonify({'code': 4032, 'message': '仅超级管理员可创建公司'}), 403
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 1002, 'message': '公司名称必填'}), 400
    result = Company.create(name)
    if result:
        return jsonify({'code': 0, 'message': '创建成功', 'data': result}), 201
    return jsonify({'code': 5000, 'message': '公司名称已存在'}), 400

@admin_bp.route('/companies/<int:comp_id>', methods=['PUT'])
@require_auth
def update_company(user_id, comp_id):
    """更新公司"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 1002, 'message': '公司名称必填'}), 400
    conn = Company.get_db()
    c = conn.cursor()
    try:
        c.execute('UPDATE companies SET name = ?, updated_at = ? WHERE id = ?', (name, __import__('datetime').datetime.now().isoformat(), comp_id))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'message': '更新成功'})
    except Exception as e:
        conn.close()
        return jsonify({'code': 5000, 'message': f'更新失败: {str(e)}'}), 500

@admin_bp.route('/companies/<int:comp_id>', methods=['DELETE'])
@require_auth
def delete_company(user_id, comp_id):
    """删除公司（仅超级管理员，级联删除所有关联数据）"""
    if not require_super_admin(user_id):
        return jsonify({'code': 4032, 'message': '仅超级管理员可删除公司'}), 403
    conn = Company.get_db()
    c = conn.cursor()
    # 级联删除：先删关联数据
    c.execute('DELETE FROM messages WHERE company_id = ?', (comp_id,))
    c.execute('DELETE FROM categories WHERE company_id = ?', (comp_id,))
    c.execute('UPDATE users SET company_id = NULL, department_id = NULL WHERE company_id = ?', (comp_id,))
    c.execute('DELETE FROM departments WHERE company_id = ?', (comp_id,))
    c.execute('DELETE FROM companies WHERE id = ?', (comp_id,))
    conn.commit()
    affected = c.rowcount
    conn.close()
    if affected > 0:
        return jsonify({'code': 0, 'message': '已删除公司及所有关联数据'})
    return jsonify({'code': 4040, 'message': '公司不存在'}), 404

# ==================== 部门管理 ====================
@admin_bp.route('/departments', methods=['GET'])
@require_auth
def list_depts(user_id):
    """获取部门列表"""
    company_id = get_user_company(user_id)
    if not company_id:
        if require_admin(user_id):
            ci = request.args.get('company_id', type=int)
            if ci:
                depts = Department.get_by_company(ci)
            else:
                conn = Department.get_db()
                c = conn.cursor()
                c.execute('''SELECT d.id, d.company_id, d.name, d.created_at, c.name as company_name FROM departments d LEFT JOIN companies c ON d.company_id = c.id ORDER BY d.id''')
                depts = [{'id': r[0], 'company_id': r[1], 'name': r[2], 'created_at': r[3], 'company_name': r[4]} for r in c.fetchall()]
                conn.close()
            return jsonify({'code': 0, 'data': {'items': depts}})
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    depts = Department.get_by_company(company_id)
    return jsonify({'code': 0, 'data': depts})

@admin_bp.route('/departments', methods=['POST'])
@require_auth
def create_dept(user_id):
    """创建部门"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    data = request.json or {}
    company_id = data.get('company_id')
    name = data.get('name', '').strip()
    if not company_id or not name:
        return jsonify({'code': 1002, 'message': '公司和部门名称必填'}), 400
    result = Department.create(company_id, name)
    if result:
        return jsonify({'code': 0, 'message': '创建成功', 'data': result}), 201
    return jsonify({'code': 5000, 'message': '创建失败，可能名称重复'}), 400

@admin_bp.route('/departments/<int:dept_id>', methods=['PUT'])
@require_auth
def update_dept(user_id, dept_id):
    """更新部门"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 1002, 'message': '部门名称必填'}), 400
    ok = Department.update(dept_id, name)
    if ok:
        return jsonify({'code': 0, 'message': '更新成功'})
    return jsonify({'code': 4040, 'message': '部门不存在'}), 404

@admin_bp.route('/departments/<int:dept_id>', methods=['DELETE'])
@require_auth
def delete_dept(user_id, dept_id):
    """删除部门（超级管理员可强制删除）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    # 超级管理员级联删除
    is_super = require_super_admin(user_id)
    if is_super:
        conn = Department.get_db()
        c = conn.cursor()
        c.execute('UPDATE users SET department_id = NULL WHERE department_id = ?', (dept_id,))
        c.execute('DELETE FROM categories WHERE department_id = ?', (dept_id,))
        c.execute('DELETE FROM departments WHERE id = ?', (dept_id,))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'message': '已删除部门及关联数据'})
    ok = Department.delete(dept_id)
    if ok:
        return jsonify({'code': 0, 'message': '已删除'})
    return jsonify({'code': 4040, 'message': '部门不存在'}), 404

# ==================== 分类管理（Admin） ====================
@admin_bp.route('/categories', methods=['GET'])
@require_auth
def list_categories(user_id):
    """获取所有分类（管理员）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    conn = Category.get_db()
    c = conn.cursor()
    c.execute('''SELECT cat.id, cat.company_id, cat.department_id, cat.user_id, cat.name, cat.level, cat.parent_id, cat.color, cat.sort_order, cat.created_at, co.name as company_name, d.name as department_name, u.username FROM categories cat LEFT JOIN companies co ON cat.company_id = co.id LEFT JOIN departments d ON cat.department_id = d.id LEFT JOIN users u ON cat.user_id = CAST(u.id AS TEXT) ORDER BY cat.sort_order, cat.id''')
    rows = c.fetchall()
    conn.close()
    items = [{'id': r[0], 'company_id': r[1], 'department_id': r[2], 'user_id': r[3], 'name': r[4], 'level': r[5], 'parent_id': r[6], 'color': r[7], 'sort_order': r[8], 'created_at': r[9], 'company_name': r[10], 'department_name': r[11], 'username': r[12]} for r in rows]
    return jsonify({'code': 0, 'data': {'items': items}})

@admin_bp.route('/categories', methods=['POST'])
@require_auth
def create_category(user_id):
    """创建分类（管理员）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    data = request.json or {}
    name = data.get('name', '').strip()
    level = data.get('level', 'company')
    company_id = data.get('company_id')
    department_id = data.get('department_id')
    color = data.get('color', '#2563EB')
    sort_order = data.get('sort_order', 0)
    if not name:
        return jsonify({'code': 1002, 'message': '分类名称必填'}), 400
    if level != 'personal' and not company_id:
        return jsonify({'code': 1002, 'message': '请选择所属公司'}), 400
    result = Category.create(company_id=company_id, name=name, level=level, department_id=department_id, color=color, sort_order=sort_order)
    if result:
        return jsonify({'code': 0, 'message': '创建成功', 'data': result}), 201
    return jsonify({'code': 5000, 'message': '创建失败'}), 500

@admin_bp.route('/categories/<int:cat_id>', methods=['PUT'])
@require_auth
def update_category(user_id, cat_id):
    """更新分类（管理员）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    data = request.json or {}
    Category.update(cat_id, name=data.get('name'), color=data.get('color'), sort_order=data.get('sort_order'))
    return jsonify({'code': 0, 'message': '更新成功'})

@admin_bp.route('/categories/<int:cat_id>', methods=['DELETE'])
@require_auth
def delete_category(user_id, cat_id):
    """删除分类（超级管理员可强制删除含子分类和话术的）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    is_super = require_super_admin(user_id)
    if is_super:
        # 级联删除该分类下的所有子分类和话术
        conn = Category.get_db()
        c = conn.cursor()
        c.execute('DELETE FROM messages WHERE category_id = ?', (cat_id,))
        c.execute('DELETE FROM categories WHERE parent_id = ?', (cat_id,))
        c.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'message': '已删除分类及关联数据'})
    Category.delete(cat_id)
    return jsonify({'code': 0, 'message': '已删除'})

# ==================== 话术管理（Admin） ====================
@admin_bp.route('/messages', methods=['GET'])
@require_auth
def list_messages(user_id):
    """获取所有话术（管理员）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    conn = Category.get_db()
    c = conn.cursor()
    c.execute('''SELECT m.id, m.title, m.content, m.category_id, m.level, m.created_by, m.created_at, m.updated_at, m.cloud_id, cat.name as category_name, cat.color as category_color, u.username FROM messages m LEFT JOIN categories cat ON m.category_id = cat.id LEFT JOIN users u ON m.created_by = u.id ORDER BY m.id DESC''')
    rows = c.fetchall()
    conn.close()
    items = [{'id': r[0], 'title': r[1], 'content': r[2], 'category_id': r[3], 'level': r[4], 'created_by': r[5], 'created_at': r[6], 'updated_at': r[7], 'cloud_id': r[8], 'category_name': r[9], 'category_color': r[10], 'username': r[11]} for r in rows]
    return jsonify({'code': 0, 'data': {'items': items}})

@admin_bp.route('/messages', methods=['POST'])
@require_auth
def create_message(user_id):
    """创建话术（管理员）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可操作'}), 403
    data = request.json or {}
    title = data.get('title', '')
    content = data.get('content', '').strip()
    category_id = data.get('category_id')
    created_by = data.get('created_by')
    level = data.get('level', 'personal')
    if not content:
        return jsonify({'code': 1002, 'message': '话术内容必填'}), 400
    result = Message.create_admin(title=title, content=content, category_id=category_id, created_by=created_by, level=level)
    if result:
        return jsonify({'code': 0, 'message': '创建成功', 'data': result}), 201
    return jsonify({'code': 5000, 'message': '创建失败'}), 500

@admin_bp.route('/messages/<int:msg_id>', methods=['PUT'])
@require_auth
def update_message(user_id, msg_id):
    """更新话术（仅创建者或管理员）"""
    msg = Message.get_by_id(msg_id)
    if not msg:
        return jsonify({'code': 4040, 'message': '话术不存在'}), 404
    is_creator = str(msg.get('created_by')) == str(user_id)
    is_admin = require_admin(user_id)
    if not is_creator and not is_admin:
        return jsonify({'code': 4032, 'message': '只能编辑自己的话术'}), 403
    data = request.json or {}
    Message.update(msg_id, title=data.get('title'), content=data.get('content'), category_id=data.get('category_id'), updated_by=user_id)
    return jsonify({'code': 0, 'message': '更新成功'})

@admin_bp.route('/messages/<int:msg_id>', methods=['DELETE'])
@require_auth
def delete_message(user_id, msg_id):
    """删除话术（超级管理员可直接硬删除）"""
    msg = Message.get_by_id(msg_id)
    if not msg:
        return jsonify({'code': 4040, 'message': '话术不存在'}), 404
    is_creator = str(msg.get('created_by')) == str(user_id)
    is_admin = require_admin(user_id)
    if not is_creator and not is_admin:
        return jsonify({'code': 4032, 'message': '只能删除自己的话术'}), 403
    # 超级管理员直接硬删除
    is_super = require_super_admin(user_id)
    if is_super:
        conn = Message.get_db()
        c = conn.cursor()
        c.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'message': '已强制删除'})
    Message.delete(msg_id)
    return jsonify({'code': 0, 'message': '已删除'})

# ==================== 用户管理 ====================
@admin_bp.route('/users', methods=['GET'])
@require_auth
def list_users(user_id):
    """获取用户列表"""
    # 超级管理员可以看到所有用户
    if require_super_admin(user_id):
        conn = User.get_db()
        c = conn.cursor()
        c.execute('''SELECT u.id, u.username, u.email, u.wechat_id, u.company_id, u.department_id, u.role, u.is_active, u.created_at, c.name as company_name, d.name as department_name FROM users u LEFT JOIN companies c ON u.company_id = c.id LEFT JOIN departments d ON u.department_id = d.id ORDER BY u.id DESC''')
        rows = c.fetchall()
        conn.close()
        items = [{'id': r[0], 'username': r[1], 'email': r[2], 'wechat_id': r[3], 'company_id': r[4], 'department_id': r[5], 'role': r[6], 'is_active': r[7], 'created_at': r[8], 'company_name': r[9], 'department_name': r[10]} for r in rows]
        return jsonify({'code': 0, 'data': items})
    company_id = get_user_company(user_id)
    if not company_id:
        return jsonify({'code': 4041, 'message': '用户无所属公司'}), 404
    users = User.get_by_company(company_id)
    return jsonify({'code': 0, 'message': '获取成功', 'data': users})

@admin_bp.route('/users', methods=['POST'])
@require_auth
def create_user(user_id):
    """创建用户（管理员）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可创建用户'}), 403
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'code': 1002, 'message': '用户名和密码必填'}), 400
    import hashlib
    hashed = hashlib.sha256(password.encode()).hexdigest()
    # 超级管理员可以指定任意公司
    if require_super_admin(user_id):
        company_id = data.get('company_id')
    else:
        company_id = get_user_company(user_id)
    result = User.create(username=username, password=hashed, company_id=company_id, department_id=data.get('department_id'), role=data.get('role', 'customer'), email=data.get('email', ''), wechat_id=data.get('wechat_id', ''))
    if result:
        return jsonify({'code': 0, 'message': '创建成功', 'data': result}), 201
    return jsonify({'code': 5000, 'message': '用户名已存在'}), 400

@admin_bp.route('/users/<target_id>', methods=['PUT'])
@require_auth
def update_user(user_id, target_id):
    """更新用户"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可更新用户'}), 403
    data = request.json or {}
    # 超级管理员可以修改任何用户的角色（包括设为admin），但不能修改其他super_admin
    is_super = require_super_admin(user_id)
    updates = {}
    if data.get('role') is not None:
        updates['role'] = data.get('role')
    if data.get('department_id') is not None:
        updates['department_id'] = data.get('department_id')
    if data.get('is_active') is not None:
        updates['is_active'] = 1 if data.get('is_active') else 0
    if is_super and data.get('company_id') is not None:
        updates['company_id'] = data.get('company_id')
    User.update_user(target_id, **updates)
    return jsonify({'code': 0, 'message': '更新成功'})

@admin_bp.route('/users/<target_id>', methods=['DELETE'])
@require_auth
def delete_user(user_id, target_id):
    """删除用户（超级管理员可强制硬删除）"""
    if not require_admin(user_id):
        return jsonify({'code': 4031, 'message': '仅管理员可删除用户'}), 403
    is_super = require_super_admin(user_id)
    if is_super:
        # 级联删除：删除用户的所有话术和分类
        conn = User.get_db()
        c = conn.cursor()
        c.execute('DELETE FROM messages WHERE user_id = ?', (str(target_id),))
        c.execute("DELETE FROM categories WHERE user_id = ? AND level = 'personal'", (str(target_id),))
        c.execute('DELETE FROM users WHERE id = ?', (target_id,))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'message': '已强制删除用户及关联数据'})
    User.delete(target_id)
    return jsonify({'code': 0, 'message': '删除成功'})

"""认证服务"""
import hashlib
from app.models.user import User
from app.models.company import Company
from app.models.department import Department

class AuthService:
    @staticmethod
    def _hash_password(pwd):
        return hashlib.sha256(pwd.encode()).hexdigest()

    @staticmethod
    def register(username, password, email='', wechat_id='', company_name='', department_name=''):
        """注册 - 支持公司+部门创建"""
        # 检查用户名
        if not username or not password:
            return {'success': False, 'code': 1001, 'error': '用户名和密码必填'}
        if len(password) < 6:
            return {'success': False, 'code': 1002, 'error': '密码至少6位'}
        
        hashed_pwd = AuthService._hash_password(password)
        
        company_id = None
        department_id = None
        
        # 处理公司：如果传了companyName则创建或获取公司
        if company_name:
            existing = Company.get_by_name(company_name)
            if existing:
                company_id = existing['id']
            else:
                result = Company.create(company_name)
                if result:
                    company_id = result['id']
                else:
                    return {'success': False, 'code': 1003, 'error': '公司创建失败'}
        
        # 处理部门：如果传了departmentName则创建或获取部门
        if department_name and company_id:
            depts = Department.get_by_company(company_id)
            for d in depts:
                if d['name'] == department_name:
                    department_id = d['id']
                    break
            if not department_id:
                result = Department.create(company_id, department_name)
                if result:
                    department_id = result['id']
        
        # 创建用户
        result = User.create(
            username=username,
            password=hashed_pwd,
            company_id=company_id,
            department_id=department_id,
            role='admin' if not company_id else 'customer',
            email=email,
            wechat_id=wechat_id
        )
        
        if result:
            return {
                'success': True, 'code': 0,
                'user_id': result['id'], 'username': result['username'],
                'token': result['id'],
                'role': result.get('role', 'customer'),
                'company_id': result.get('company_id'),
                'department_id': result.get('department_id'),
            }
        return {'success': False, 'code': 1004, 'error': '用户名已存在'}

    @staticmethod
    def login(username, password):
        hashed = AuthService._hash_password(password)
        user = User.authenticate(username, hashed)
        if user:
            return {
                'success': True, 'code': 0,
                'user_id': user['id'], 'username': user['username'],
                'token': user['id'],
                'role': user.get('role', 'customer'),
                'company_id': user.get('company_id'),
                'department_id': user.get('department_id'),
            }
        return {'success': False, 'code': 1005, 'error': '用户名或密码错误'}

    @staticmethod
    def get_user_profile(user_id):
        return User.get_by_id(user_id)

    @staticmethod
    def update_profile(user_id, email=None, wechat_id=None):
        return User.update_profile(user_id, email, wechat_id)
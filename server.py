"""
快回复后端服务器 v4.0 - 团队协作版
- 多租户：公司 → 部门 → 用户
- 角色：管理员(admin) + 客服(agent)
- 话术3层分类：company / department / personal
- WebSocket实时推送
- RESTful CRUD
"""

from flask import Flask, request, jsonify, send_file, send_from_directory, g
from flask_cors import CORS
from flask_sock import Sock
import os
import sqlite3
import uuid
import hashlib
import secrets
import json
import threading
import time
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
sock = Sock(app)

# ===== 配置 =====
HOST = '0.0.0.0'
PORT = 5000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'quickreply_v4.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ===== 全局WebSocket连接管理 =====
# {company_id: [set of ws connections]}
ws_connections: dict[int, set] = {}
ws_lock = threading.Lock()


def ws_broadcast(company_id: int, event: str, data: dict):
    """向指定公司所有在线用户推送WebSocket消息，company_id=0时广播给所有公司"""
    with ws_lock:
        if company_id == 0:
            # 全量广播
            for cid, conns in ws_connections.items():
                dead = set()
                for ws in conns:
                    try:
                        ws.send(json.dumps({'event': event, 'data': data}, ensure_ascii=False))
                    except Exception:
                        dead.add(ws)
                for ws in dead:
                    ws_connections[cid].discard(ws)
            return
        if company_id not in ws_connections:
            return
        dead = set()
        for ws in ws_connections[company_id]:
            try:
                ws.send(json.dumps({'event': event, 'data': data}, ensure_ascii=False))
            except Exception:
                dead.add(ws)
        for ws in dead:
            ws_connections[company_id].discard(ws)


# ===== 邮件配置 =====
# ⚠️  请填写你的163邮箱SMTP信息  ⚠️
#   sender:     发送方邮箱地址
#   password:   163邮箱 → 设置 → POP3/SMTP/IMAP → 客户端授权密码（非登录密码）
EMAIL_CONFIG = {
    'enabled': True,
    'smtp_host': 'smtp.163.com',
    'smtp_port': 465,
    'sender': 'your_email@163.com',       # ← 替换为你的163邮箱
    'password': 'your_smtp_password',     # ← 替换为SMTP授权码
    'use_tls': True,
}

def send_email(to: str, subject: str, body: str) -> bool:
    """发送邮件，返回是否成功"""
    if not EMAIL_CONFIG['enabled']:
        return False
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender']
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        with smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_host'], EMAIL_CONFIG['smtp_port']) as s:
            s.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
            s.sendmail(EMAIL_CONFIG['sender'], [to], msg.as_string())
        return True
    except Exception as e:
        print(f"[邮件发送失败] {e}")
        return False


# ===== 数据库 =====
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_db():
    """数据库迁移：为已存在的数据库添加缺失的列"""
    conn = get_db()
    c = conn.cursor()
    # 添加 email 列（如果不存在）
    try:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
        print("[DB] Added email column to users table")
    except Exception:
        pass  # 列已存在
    conn.commit()
    conn.close()


def init_db():
    conn = get_db()
    c = conn.cursor()

    # 公司表
    c.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # 部门表
    c.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    ''')

    # 用户表
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'agent',
            company_id INTEGER NOT NULL,
            department_id INTEGER,
            created_at TEXT NOT NULL,
            last_login TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    ''')

    # 分类表（3层）
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            level TEXT NOT NULL,
            parent_id INTEGER,
            company_id INTEGER NOT NULL,
            department_id INTEGER,
            color TEXT DEFAULT '#1890FF',
            sort_order INTEGER DEFAULT 0,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (parent_id) REFERENCES categories(id),
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (department_id) REFERENCES departments(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    # 话术表
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT NOT NULL,
            category_id INTEGER,
            attachments TEXT DEFAULT '[]',
            created_by INTEGER NOT NULL,
            updated_by INTEGER,
            updated_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id),
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (updated_by) REFERENCES users(id)
        )
    ''')

    # 验证码表
    c.execute('''
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            purpose TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0
        )
    ''')

    # Token表
    c.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 初始化默认公司和管理员
    c.execute("SELECT id FROM users WHERE username = 'admin'")
    if not c.fetchone():
        # 只在 admin 用户不存在时初始化
        c.execute("SELECT id FROM companies WHERE name = '默认公司'")
        row = c.fetchone()
        if row:
            company_id = row[0]
        else:
            now = datetime.now().isoformat()
            c.execute("INSERT INTO companies (name, created_at) VALUES (?, ?)", ('默认公司', now))
            company_id = c.lastrowid
            c.execute("INSERT INTO departments (name, company_id, created_at) VALUES (?, ?, ?)", ('默认部门', company_id, now))
        # 获取默认部门
        c.execute("SELECT id FROM departments WHERE company_id = ? LIMIT 1", (company_id,))
        dept_row = c.fetchone()
        dept_id = dept_row[0] if dept_row else None
        now = datetime.now().isoformat()
        pwd = hash_password('admin123')
        c.execute(
            "INSERT INTO users (username, password, role, company_id, department_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ('admin', pwd, 'super_admin', company_id, dept_id, now)
        )

    conn.commit()
    conn.close()
    _migrate_db()
    print(f"[DB] Initialized at {DATABASE}")


def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_hex(32)


# ===== 认证中间件 =====
def get_current_user():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT u.id, u.username, u.role, u.company_id, u.department_id, u.status
        FROM users u JOIN tokens t ON u.id = t.user_id
        WHERE t.token = ?
    ''', (token,))
    user = c.fetchone()
    conn.close()
    return user


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'code': 4011, 'message': '请先登录'}), 401
        if user['status'] != 'active':
            return jsonify({'code': 4012, 'message': '账号已被禁用'}), 403
        g.user = dict(user)
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'code': 4011, 'message': '请先登录'}), 401
        if user['role'] not in ('admin', 'super_admin'):
            return jsonify({'code': 4031, 'message': '需要管理员权限'}), 403
        if user['status'] != 'active':
            return jsonify({'code': 4012, 'message': '账号已被禁用'}), 403
        g.user = dict(user)
        return f(*args, **kwargs)
    return decorated


# ===== 认证接口 =====
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    company_name = data.get('companyName', '').strip()
    department_name = data.get('departmentName', '').strip()

    if not username or not password or not company_name:
        return jsonify({'code': 4001, 'message': '用户名、密码、公司名不能为空'}), 400

    if len(password) < 6:
        return jsonify({'code': 4002, 'message': '密码至少6位'}), 400

    conn = get_db()
    c = conn.cursor()

    # 检查用户名是否已存在
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'code': 4003, 'message': '用户名已被注册'}), 400

    now = datetime.now().isoformat()
    pwd_hash = hash_password(password)

    # 创建公司
    c.execute("INSERT INTO companies (name, created_at) VALUES (?, ?)", (company_name, now))
    company_id = c.lastrowid

    # 创建部门
    dept_name = department_name or '默认部门'
    c.execute("INSERT INTO departments (name, company_id, created_at) VALUES (?, ?, ?)", (dept_name, company_id, now))
    dept_id = c.lastrowid

    # 创建用户（默认是admin管理员）
    # 注意：标准注册流程不填邮箱，邮箱仅在邮箱验证码注册(/api/auth/register_email)时写入
    c.execute(
        "INSERT INTO users (username, password, role, company_id, department_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (username, pwd_hash, 'admin', company_id, dept_id, now)
    )
    user_id = c.lastrowid

    # 创建默认分类
    for level, name in [('company', '📁 公司话术'), ('department', '📂 部门话术'), ('personal', '📝 个人话术')]:
        c.execute(
            "INSERT INTO categories (name, level, company_id, department_id, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, level, company_id, None if level == 'company' else dept_id, user_id, now)
        )

    # 生成Token
    token = generate_token()
    expires = (datetime.now() + timedelta(days=7)).isoformat()
    c.execute("INSERT INTO tokens (user_id, token, created_at, expires_at) VALUES (?, ?, ?, ?)",
              (user_id, token, now, expires))

    conn.commit()
    conn.close()

    return jsonify({
        'code': 0,
        'message': '注册成功',
        'data': {
            'token': token,
            'user': {
                'id': user_id,
                'username': username,
                'role': 'admin',
                'companyId': company_id,
                'companyName': company_name,
                'departmentId': dept_id,
                'departmentName': dept_name
            }
        }
    })


@app.route('/api/auth/send_code', methods=['POST'])
def send_verification_code():
    """发送邮箱验证码（注册用）"""
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    purpose = data.get('purpose', 'register')


    if not email or '@' not in email:
        return jsonify({'code': 4001, 'message': '请输入有效的邮箱地址'}), 400

    conn = get_db()
    c = conn.cursor()


    # 检查邮箱是否已被注册
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return jsonify({'code': 4002, 'message': '该邮箱已注册'}), 400

    # 生成6位验证码
    code = secrets.token_hex(3)[:6].upper()
    now = datetime.now().isoformat()
    expires = (datetime.now() + timedelta(minutes=10)).isoformat()

    # 标记旧验证码已使用
    c.execute("UPDATE verification_codes SET used = 1 WHERE email = ? AND purpose = ? AND used = 0", (email, purpose))
    c.execute("INSERT INTO verification_codes (email, code, purpose, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
              (email, code, purpose, now, expires))
    conn.commit()
    conn.close()

    # 发送邮件
    html_body = f"""
    <html><body>
    <h2>快回复 - 邮箱验证</h2>
    <p>您好，您正在注册快回复团队账号。</p>
    <p>您的验证码是：<b style='font-size:24px;color:#1890FF'>{code}</b></p>
    <p>有效期10分钟，请勿告知他人。</p>
    <hr><p style='color:#999;font-size:12px'>优品生物 · 快回复团队协作平台</p>
    </body></html>
    """
    ok = send_email(email, '【快回复】您的注册验证码', html_body)

    if not ok:
        return jsonify({'code': 5001, 'message': '邮件发送失败，请检查邮箱地址或联系管理员'}), 500

    return jsonify({'code': 0, 'message': '验证码已发送到您的邮箱'})


@app.route('/api/auth/verify_code', methods=['POST'])
def verify_code():
    """验证邮箱验证码"""
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip().upper()
    purpose = data.get('purpose', 'register')

    if not email or not code:
        return jsonify({'code': 4001, 'message': '邮箱和验证码不能为空'}), 400


    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM verification_codes WHERE email = ? AND code = ? AND purpose = ? AND used = 0 AND expires_at > ? ORDER BY id DESC LIMIT 1",
              (email, code, purpose, datetime.now().isoformat()))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'code': 4003, 'message': '验证码无效或已过期'}), 400

    c.execute("UPDATE verification_codes SET used = 1 WHERE id = ?", (row['id'],))
    conn.commit()
    conn.close()

    return jsonify({'code': 0, 'message': '验证成功'})


@app.route('/api/auth/register_email', methods=['POST'])
def register_with_email():
    """邮箱验证码注册（免密码登录流程）"""
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip().upper()
    company_name = data.get('companyName', '').strip()
    department_name = data.get('departmentName', '').strip()

    if not email or '@' not in email:
        return jsonify({'code': 4001, 'message': '请输入有效的邮箱地址'}), 400
    if not company_name:
        return jsonify({'code': 4001, 'message': '公司名不能为空'}), 400

    # 验证验证码
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM verification_codes WHERE email = ? AND code = ? AND purpose = 'register' AND used = 0 AND expires_at > ? ORDER BY id DESC LIMIT 1",
              (email, code, datetime.now().isoformat()))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'code': 4004, 'message': '验证码无效或已过期'}), 400

    c.execute("UPDATE verification_codes SET used = 1 WHERE id = ?", (row['id'],))

    # 检查邮箱是否已注册
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return jsonify({'code': 4002, 'message': '该邮箱已注册'}), 400

    # 生成随机密码（用户无需知道）
    random_password = secrets.token_hex(8)
    pwd_hash = hash_password(random_password)
    now = datetime.now().isoformat()

    # 创建公司
    c.execute("INSERT INTO companies (name, created_at) VALUES (?, ?)", (company_name, now))
    company_id = c.lastrowid

    # 创建部门
    dept_name = department_name or '默认部门'
    c.execute("INSERT INTO departments (name, company_id, created_at) VALUES (?, ?, ?)", (dept_name, company_id, now))
    dept_id = c.lastrowid

    # 用email作为username注册
    c.execute("INSERT INTO users (username, password, email, role, company_id, department_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (email, pwd_hash, email, 'admin', company_id, dept_id, now))
    user_id = c.lastrowid

    # 创建默认分类
    for level, name in [('company', '📁 公司话术'), ('department', '📂 部门话术'), ('personal', '📝 个人话术')]:
        c.execute("INSERT INTO categories (name, level, company_id, department_id, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                  (name, level, company_id, None if level == 'company' else dept_id, user_id, now))

    # 生成Token
    token = generate_token()
    expires = (datetime.now() + timedelta(days=7)).isoformat()
    c.execute("INSERT INTO tokens (user_id, token, created_at, expires_at) VALUES (?, ?, ?, ?)",
              (user_id, token, now, expires))

    conn.commit()
    conn.close()

    return jsonify({
        'code': 0,
        'message': '注册成功',
        'data': {
            'token': token,
            'user': {
                'id': user_id,
                'username': email,
                'email': email,
                'role': 'admin',
                'companyId': company_id,
                'companyName': company_name,
                'departmentId': dept_id,
                'departmentName': dept_name
            }
        }
    })


@app.route('/api/auth/send_reset_code', methods=['POST'])
def send_reset_code():
    """发送密码重置验证码"""
    data = request.json or {}
    email = data.get('email', '').strip().lower()

    if not email or '@' not in email:
        return jsonify({'code': 4001, 'message': '请输入有效的邮箱地址'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    if not c.fetchone():
        conn.close()
        # 为防止邮箱枚举攻击，返回成功
        return jsonify({'code': 0, 'message': '如果该邮箱已注册，验证码已发送'})

    code = secrets.token_hex(3)[:6].upper()
    now = datetime.now().isoformat()
    expires = (datetime.now() + timedelta(minutes=10)).isoformat()
    c.execute("UPDATE verification_codes SET used = 1 WHERE email = ? AND purpose = 'reset' AND used = 0", (email,))
    c.execute("INSERT INTO verification_codes (email, code, purpose, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
              (email, code, 'reset', now, expires))
    conn.commit()
    conn.close()


    html_body = f"""
    <html><body>
    <h2>快回复 - 密码重置</h2>
    <p>您好，您申请重置密码。</p>
    <p>您的验证码是：<b style='font-size:24px;color:#FF4D4F'>{code}</b></p>
    <p>有效期10分钟，如非本人操作请忽略。</p>
    <hr><p style='color:#999;font-size:12px'>优品生物 · 快回复团队协作平台</p>
    </body></html>
    """
    send_email(email, '【快回复】密码重置验证码', html_body)
    return jsonify({'code': 0, 'message': '验证码已发送到您的邮箱'})


@app.route('/api/auth/reset_password', methods=['POST'])
def reset_password():
    """通过验证码重置密码"""
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip().upper()
    new_password = data.get('password', '').strip()

    if not email or '@' not in email:
        return jsonify({'code': 4001, 'message': '请输入有效的邮箱地址'}), 400
    if len(new_password) < 6:
        return jsonify({'code': 4002, 'message': '密码至少6位'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM verification_codes WHERE email = ? AND code = ? AND purpose = 'reset' AND used = 0 AND expires_at > ? ORDER BY id DESC LIMIT 1",
              (email, code, datetime.now().isoformat()))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'code': 4003, 'message': '验证码无效或已过期'}), 400

    c.execute("UPDATE verification_codes SET used = 1 WHERE id = ?", (row['id'],))
    pwd_hash = hash_password(new_password)
    c.execute("UPDATE users SET password = ? WHERE email = ?", (pwd_hash, email))
    conn.commit()
    conn.close()

    return jsonify({'code': 0, 'message': '密码重置成功，请使用新密码登录'})



@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'code': 4001, 'message': '用户名和密码不能为空'}), 400

    conn = get_db()
    c = conn.cursor()
    pwd_hash = hash_password(password)
    c.execute(
        "SELECT id, username, role, company_id, department_id, status FROM users WHERE username = ? AND password = ?",
        (username, pwd_hash)
    )
    user = c.fetchone()

    if not user:
        conn.close()
        return jsonify({'code': 4013, 'message': '用户名或密码错误'}), 401

    if user['status'] != 'active':
        conn.close()
        return jsonify({'code': 4012, 'message': '账号已被禁用'}), 403

    # 更新最后登录
    c.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user['id']))

    # 生成Token
    token = generate_token()
    expires = (datetime.now() + timedelta(days=7)).isoformat()
    c.execute("INSERT INTO tokens (user_id, token, created_at, expires_at) VALUES (?, ?, ?, ?)",
              (user['id'], token, datetime.now().isoformat(), expires))
    conn.commit()

    # 获取公司名和部门名
    c.execute("SELECT name FROM companies WHERE id = ?", (user['company_id'],))
    company = c.fetchone()
    dept_name = None
    if user['department_id']:
        c.execute("SELECT name FROM departments WHERE id = ?", (user['department_id'],))
        dept = c.fetchone()
        if dept:
            dept_name = dept['name']

    conn.close()

    return jsonify({
        'code': 0,
        'message': '登录成功',
        'data': {
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'companyId': user['company_id'],
                'companyName': company['name'] if company else '',
                'departmentId': user['department_id'],
                'departmentName': dept_name
            }
        }
    })


@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return jsonify({'code': 0, 'message': '登出成功'})


@app.route('/api/auth/profile', methods=['GET'])
@require_auth
def get_profile():
    user = g.user
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM companies WHERE id = ?", (user['company_id'],))
    company = c.fetchone()
    dept_name = None
    if user['department_id']:
        c.execute("SELECT name FROM departments WHERE id = ?", (user['department_id'],))
        dept = c.fetchone()
        if dept:
            dept_name = dept['name']
    c.execute("SELECT COUNT(*) FROM users WHERE company_id = ?", (user['company_id'],))
    member_count = c.fetchone()[0]
    conn.close()

    return jsonify({
        'code': 0,
        'data': {
            'id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'companyId': user['company_id'],
            'companyName': company['name'] if company else '',
            'departmentId': user['department_id'],
            'departmentName': dept_name,
            'memberCount': member_count
        }
    })


@app.route('/api/auth/refresh', methods=['POST'])
@require_auth
def refresh_token():
    """刷新Token，返回新Token（有效期7天）"""
    user = g.user
    old_token = request.headers.get('Authorization', '').replace('Bearer ', '')
    conn = get_db()
    c = conn.cursor()
    # 删除旧Token
    c.execute("DELETE FROM tokens WHERE token = ?", (old_token,))
    # 生成新Token
    new_token = generate_token()
    expires = (datetime.now() + timedelta(days=7)).isoformat()
    c.execute("INSERT INTO tokens (user_id, token, created_at, expires_at) VALUES (?, ?, ?, ?)",
              (user['id'], new_token, datetime.now().isoformat(), expires))
    conn.commit()
    conn.close()
    return jsonify({'code': 0, 'data': {'token': new_token}})


@app.route('/api/upload', methods=['POST'])
@require_auth
def upload_file():
    """通用文件上传"""
    if 'file' not in request.files:
        return jsonify({'code': 4001, 'message': '没有文件'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'code': 4002, 'message': '文件名为空'}), 400
    # 按日期分目录
    date_dir = datetime.now().strftime('%Y%m%d')
    save_dir = os.path.join(UPLOAD_DIR, date_dir)
    os.makedirs(save_dir, exist_ok=True)
    # 生成安全文件名
    ext = os.path.splitext(f.filename)[1]
    safe_name = f"{secrets.token_hex(8)}{ext}"
    save_path = os.path.join(save_dir, safe_name)
    f.save(save_path)
    # 返回可访问的URL
    url = f"{request.host_url}uploads/{date_dir}/{safe_name}"
    return jsonify({'code': 0, 'data': {'url': url, 'filename': f.filename}})


# 静态文件服务（uploads目录）
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ===== 公司/部门接口（管理员） =====
@app.route('/api/admin/company', methods=['GET'])
@require_admin
def get_company():
    user = g.user
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, created_at FROM companies WHERE id = ?", (user['company_id'],))
    row = c.fetchone()
    c.execute("SELECT id, name, created_at FROM departments WHERE company_id = ? ORDER BY created_at", (user['company_id'],))
    depts = [{'id': r['id'], 'name': r['name'], 'createdAt': r['created_at']} for r in c.fetchall()]
    conn.close()
    if not row:
        return jsonify({'code': 4041, 'message': '公司不存在'}), 404
    return jsonify({'code': 0, 'data': {
        'id': row['id'], 'name': row['name'], 'createdAt': row['created_at'], 'departments': depts
    }})


def require_super_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'code': 4011, 'message': '请先登录'}), 401
        if user['role'] != 'super_admin':
            return jsonify({'code': 4032, 'message': '需要超级管理员权限'}), 403
        g.user = dict(user)
        return f(*args, **kwargs)
    return decorated

@app.route('/api/admin/companies', methods=['GET'])
@require_admin
def admin_list_companies():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, created_at FROM companies ORDER BY id")
    rows = c.fetchall()
    conn.close()
    items = [{'id': r['id'], 'name': r['name'], 'created_at': r['created_at']} for r in rows]
    return jsonify({'code': 0, 'data': {'items': items, 'total': len(items)}})

@app.route('/api/admin/companies', methods=['POST'])
@require_super_admin
def admin_create_company():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 4001, 'message': '公司名称不能为空'}), 400
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT INTO companies (name, created_at) VALUES (?, ?)", (name, now))
    conn.commit()
    company_id = c.lastrowid
    conn.close()

    # WebSocket广播，广播给所有公司（超管创建，全量通知）
    ws_broadcast(0, 'company_created', {'id': company_id, 'name': name})

    return jsonify({'code': 0, 'message': '创建成功', 'data': {'id': company_id, 'name': name}})

@app.route('/api/admin/companies/<int:company_id>', methods=['DELETE'])
@require_super_admin
def admin_delete_company(company_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
    if not c.fetchone():
        conn.close()
        return jsonify({'code': 4041, 'message': '公司不存在'}), 404
    # 级联删除：分类、话术、部门、用户
    c.execute("DELETE FROM tokens WHERE user_id IN (SELECT id FROM users WHERE company_id = ? AND role != 'super_admin')", (company_id,))
    c.execute("DELETE FROM messages WHERE category_id IN (SELECT id FROM categories WHERE company_id = ?)", (company_id,))
    c.execute("DELETE FROM categories WHERE company_id = ?", (company_id,))
    c.execute("DELETE FROM users WHERE company_id = ? AND role != 'super_admin'", (company_id,))
    # Unlink super_admin users from the deleted company
    c.execute("UPDATE users SET company_id = NULL, department_id = NULL WHERE company_id = ? AND role = 'super_admin'", (company_id,))
    c.execute("DELETE FROM departments WHERE company_id = ?", (company_id,))
    c.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()

    # WebSocket广播
    ws_broadcast(0, 'company_deleted', {'id': company_id})

    return jsonify({'code': 0, 'message': '删除成功'})

@app.route('/api/admin/departments', methods=['GET'])
@require_admin
def admin_list_departments():
    company_id = request.args.get('company_id', type=int)
    conn = get_db()
    c = conn.cursor()
    # 超管无指定 company_id 时看所有部门，普通管理员只看自己公司
    if company_id:
        c.execute("SELECT d.id, d.name, d.company_id, d.created_at, co.name as company_name FROM departments d LEFT JOIN companies co ON d.company_id = co.id WHERE d.company_id = ? ORDER BY d.id", (company_id,))
    elif g.user.get('role') == 'super_admin' or g.user.get('id') == 1:
        c.execute("SELECT d.id, d.name, d.company_id, d.created_at, co.name as company_name FROM departments d LEFT JOIN companies co ON d.company_id = co.id ORDER BY d.id")
    else:
        c.execute("SELECT d.id, d.name, d.company_id, d.created_at, co.name as company_name FROM departments d LEFT JOIN companies co ON d.company_id = co.id WHERE d.company_id = ? ORDER BY d.id", (g.user['company_id'],))
    rows = c.fetchall()
    conn.close()
    items = [{'id': r['id'], 'name': r['name'], 'company_id': r['company_id'], 'created_at': r['created_at'], 'company_name': r['company_name']} for r in rows]
    return jsonify({'code': 0, 'data': {'items': items, 'total': len(items)}})


@app.route('/api/admin/departments', methods=['POST'])
@require_admin
def create_department():
    user = g.user
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 4001, 'message': '部门名称不能为空'}), 400

    company_id = data.get('company_id') or user.get('company_id')
    if not company_id:
        return jsonify({'code': 4002, 'message': '请选择公司'}), 400
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO departments (name, company_id, created_at) VALUES (?, ?, ?)",
              (name, company_id, datetime.now().isoformat()))
    dept_id = c.lastrowid
    conn.commit()
    conn.close()

    # WebSocket广播
    ws_broadcast(company_id, 'department_created', {'id': dept_id, 'name': name, 'company_id': company_id})

    return jsonify({'code': 0, 'message': '创建成功', 'data': {'id': dept_id, 'name': name}})


@app.route('/api/admin/departments/<int:dept_id>', methods=['PUT'])
@require_admin
def update_department(dept_id):
    user = g.user
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 4001, 'message': '部门名称不能为空'}), 400

    conn = get_db()
    c = conn.cursor()
    # 超管可更新任意部门，普通管理员仅限本公司
    if user.get('role') == 'super_admin' or user.get('id') == 1:
        c.execute("UPDATE departments SET name = ? WHERE id = ?", (name, dept_id))
    else:
        c.execute("UPDATE departments SET name = ? WHERE id = ? AND company_id = ?", (name, dept_id, user['company_id']))
    conn.commit()
    conn.close()
    return jsonify({'code': 0, 'message': '更新成功'})


@app.route('/api/admin/departments/<int:dept_id>', methods=['DELETE'])
@require_admin
def delete_department(dept_id):
    user = g.user
    conn = get_db()
    c = conn.cursor()
    # 检查是否有用户
    c.execute("SELECT COUNT(*) FROM users WHERE department_id = ?", (dept_id,))
    if c.fetchone()[0] > 0:
        conn.close()
        return jsonify({'code': 4002, 'message': '该部门有用户，无法删除'}), 400
    # 超管可删除任意部门，普通管理员仅限本公司
    if user.get('role') == 'super_admin' or user.get('id') == 1:
        c.execute("DELETE FROM departments WHERE id = ?", (dept_id,))
    else:
        c.execute("DELETE FROM departments WHERE id = ? AND company_id = ?", (dept_id, user['company_id']))
    conn.commit()
    conn.close()
    return jsonify({'code': 0, 'message': '删除成功'})


# ===== 用户管理（管理员） =====
@app.route('/api/admin/users', methods=['GET'])
@require_admin
def list_users():
    user = g.user
    conn = get_db()
    c = conn.cursor()
    # 超级管理员(id=1)可看所有用户，公司管理员只看本公司
    if user['id'] == 1:
        c.execute('''
            SELECT u.id, u.username, u.email, u.role, u.company_id, u.department_id,
                   u.status, u.created_at, u.last_login,
                   co.name as company_name, d.name as department_name
            FROM users u
            LEFT JOIN companies co ON u.company_id = co.id
            LEFT JOIN departments d ON u.department_id = d.id
            ORDER BY u.created_at DESC
        ''')
    else:
        c.execute('''
            SELECT u.id, u.username, u.email, u.role, u.company_id, u.department_id,
                   u.status, u.created_at, u.last_login,
                   co.name as company_name, d.name as department_name
            FROM users u
            LEFT JOIN companies co ON u.company_id = co.id
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.company_id = ?
            ORDER BY u.created_at DESC
        ''', (user['company_id'],))
    rows = c.fetchall()
    conn.close()
    items = [{
        'id': r['id'], 'username': r['username'], 'email': r['email'],
        'role': r['role'], 'company_id': r['company_id'],
        'company_name': r['company_name'],
        'department_id': r['department_id'],
        'department_name': r['department_name'],
        'status': r['status'], 'created_at': r['created_at'],
        'last_login': r['last_login']
    } for r in rows]
    return jsonify({'code': 0, 'data': {'items': items, 'total': len(items)}})


@app.route('/api/admin/users', methods=['POST'])
@require_admin
def create_user():
    user = g.user
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'agent')
    company_id = data.get('companyId') or user.get('company_id')
    department_id = data.get('departmentId')

    if not username or not password:
        return jsonify({'code': 4001, 'message': '用户名和密码不能为空'}), 400
    if len(password) < 6:
        return jsonify({'code': 4002, 'message': '密码至少6位'}), 400
    if role not in ['admin', 'agent']:
        role = 'agent'

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'code': 4003, 'message': '用户名已存在'}), 400

    pwd_hash = hash_password(password)
    c.execute(
        "INSERT INTO users (username, password, role, company_id, department_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (username, pwd_hash, role, company_id, department_id, datetime.now().isoformat())
    )
    conn.commit()
    user_id = c.lastrowid
    conn.close()

    ws_broadcast(company_id, 'user_created', {'id': user_id, 'username': username, 'role': role})

    return jsonify({'code': 0, 'message': '创建成功', 'data': {'id': user_id}})


@app.route('/api/admin/users/<int:uid>', methods=['PUT'])
@require_admin
def update_user(uid):
    data = request.json or {}

    conn = get_db()
    c = conn.cursor()
    # 超管可操作任意用户，普通管理员仅限本公司
    if g.user.get('role') == 'super_admin' or g.user.get('id') == 1:
        c.execute("SELECT id FROM users WHERE id = ?", (uid,))
    else:
        c.execute("SELECT id FROM users WHERE id = ? AND company_id = ?", (uid, g.user['company_id']))
    if not c.fetchone():
        conn.close()
        return jsonify({'code': 4041, 'message': '用户不存在'}), 404

    updates, params = [], []
    if 'role' in data and data['role'] in ['admin', 'agent']:
        updates.append("role = ?")
        params.append(data['role'])
    if 'departmentId' in data:
        updates.append("department_id = ?")
        params.append(data['departmentId'])
    if 'status' in data and data['status'] in ['active', 'disabled']:
        updates.append("status = ?")
        params.append(data['status'])
    if 'password' in data and data['password']:
        updates.append("password = ?")
        params.append(hash_password(data['password']))

    if updates:
        params.append(uid)
        c.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()

    return jsonify({'code': 0, 'message': '更新成功'})


@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@require_admin
def delete_user(uid):
    if uid == g.user['id']:
        return jsonify({'code': 4004, 'message': '不能删除自己'}), 400

    conn = get_db()
    c = conn.cursor()
    # 超管可删除任意用户，普通管理员仅限本公司
    if g.user.get('role') == 'super_admin' or g.user.get('id') == 1:
        c.execute("SELECT id FROM users WHERE id = ?", (uid,))
    else:
        c.execute("SELECT id FROM users WHERE id = ? AND company_id = ?", (uid, g.user['company_id']))
    if not c.fetchone():
        conn.close()
        return jsonify({'code': 4041, 'message': '用户不存在'}), 404

    # 级联清理：删除用户的话术和令牌
    c.execute("DELETE FROM messages WHERE created_by = ?", (uid,))
    c.execute("DELETE FROM tokens WHERE user_id = ?", (uid,))
    c.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
    conn.close()

    ws_broadcast(g.user['company_id'], 'user_deleted', {'id': uid})

    return jsonify({'code': 0, 'message': '删除成功'})


# ===== 管理员统计 =====
@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def admin_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM companies")
    companies = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM messages")
    messages = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM categories")
    categories = c.fetchone()[0]
    conn.close()
    return jsonify({'code': 0, 'data': {
        'users': users, 'companies': companies,
        'messages': messages, 'categories': categories
    }})


# ===== 管理员分类管理 =====
@app.route('/api/admin/categories', methods=['GET'])
@require_admin
def admin_list_categories():
    user = g.user
    conn = get_db()
    c = conn.cursor()
    if user['id'] == 1:  # 超级管理员看所有
        c.execute('''
            SELECT cat.id, cat.name, cat.level, cat.parent_id, cat.company_id,
                   cat.department_id, cat.color, cat.sort_order, cat.created_by, cat.created_at,
                   co.name as company_name, dp.name as department_name,
                   u.username
            FROM categories cat
            LEFT JOIN companies co ON cat.company_id = co.id
            LEFT JOIN departments dp ON cat.department_id = dp.id
            LEFT JOIN users u ON cat.created_by = u.id
            ORDER BY cat.sort_order, cat.id
        ''')
    else:
        c.execute('''
            SELECT cat.id, cat.name, cat.level, cat.parent_id, cat.company_id,
                   cat.department_id, cat.color, cat.sort_order, cat.created_by, cat.created_at,
                   co.name as company_name, dp.name as department_name,
                   u.username
            FROM categories cat
            LEFT JOIN companies co ON cat.company_id = co.id
            LEFT JOIN departments dp ON cat.department_id = dp.id
            LEFT JOIN users u ON cat.created_by = u.id
            WHERE cat.company_id = ?
            ORDER BY cat.sort_order, cat.id
        ''', (user['company_id'],))
    rows = c.fetchall()
    conn.close()
    items = []
    for r in rows:
        items.append({
            'id': r['id'], 'name': r['name'], 'level': r['level'],
            'parent_id': r['parent_id'], 'company_id': r['company_id'],
            'department_id': r['department_id'], 'color': r['color'],
            'sort_order': r['sort_order'], 'created_by': r['created_by'],
            'created_at': r['created_at'], 'company_name': r['company_name'],
            'department_name': r['department_name'], 'username': r['username']
        })
    return jsonify({'code': 0, 'data': {'items': items, 'total': len(items)}})


@app.route('/api/admin/categories', methods=['POST'])
@require_admin
def admin_create_category():
    data = request.get_json()
    name = data.get('name', '').strip()
    level = data.get('level', 'company')
    color = data.get('color', '#1890FF')
    sort_order = data.get('sort_order', 0)
    company_id = data.get('company_id')
    department_id = data.get('department_id')

    if not name:
        return jsonify({'code': 4001, 'message': '分类名称不能为空'}), 400
    if level in ('company', 'department') and not company_id:
        return jsonify({'code': 4002, 'message': '公司级/部门级分类必须指定公司'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO categories (name, level, company_id, department_id, color, sort_order, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, level, company_id, department_id, color, sort_order, g.user['id'], datetime.now().isoformat()))
    cat_id = c.lastrowid
    conn.commit()
    conn.close()

    ws_broadcast(g.user['company_id'], 'category_created', {'id': cat_id, 'name': name})
    return jsonify({'code': 0, 'data': {'id': cat_id}, 'message': '创建成功'})


@app.route('/api/admin/categories/<int:cid>', methods=['PUT'])
@require_admin
def admin_update_category(cid):
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM categories WHERE id = ?", (cid,))
    if not c.fetchone():
        conn.close()
        return jsonify({'code': 4041, 'message': '分类不存在'}), 404

    updates = []
    params = []
    for field in ('name', 'level', 'color', 'sort_order', 'company_id', 'department_id'):
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
    if not updates:
        conn.close()
        return jsonify({'code': 0, 'message': '无更新'})

    params.append(cid)
    c.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

    ws_broadcast(g.user['company_id'], 'category_updated', {'id': cid})
    return jsonify({'code': 0, 'message': '更新成功'})


@app.route('/api/admin/categories/<int:cid>', methods=['DELETE'])
@require_admin
def admin_delete_category(cid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM categories WHERE id = ?", (cid,))
    if not c.fetchone():
        conn.close()
        return jsonify({'code': 4041, 'message': '分类不存在'}), 404

    c.execute("DELETE FROM messages WHERE category_id = ?", (cid,))
    c.execute("DELETE FROM categories WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

    ws_broadcast(g.user['company_id'], 'category_deleted', {'id': cid})
    return jsonify({'code': 0, 'message': '删除成功'})


# ===== 管理员话术管理 =====
@app.route('/api/admin/messages', methods=['GET'])
@require_admin
def admin_list_messages():
    user = g.user
    conn = get_db()
    c = conn.cursor()
    if user['id'] == 1:  # 超级管理员看所有
        c.execute('''
            SELECT m.id, m.title, m.content, m.category_id, m.attachments,
                   m.created_by, m.updated_by, m.updated_at, m.created_at,
                   cat.name as category_name, cat.level as level, cat.color as category_color,
                   u.username
            FROM messages m
            LEFT JOIN categories cat ON m.category_id = cat.id
            LEFT JOIN users u ON m.created_by = u.id
            ORDER BY m.id DESC
        ''')
    else:
        c.execute('''
            SELECT m.id, m.title, m.content, m.category_id, m.attachments,
                   m.created_by, m.updated_by, m.updated_at, m.created_at,
                   cat.name as category_name, cat.level as level, cat.color as category_color,
                   u.username
            FROM messages m
            LEFT JOIN categories cat ON m.category_id = cat.id
            LEFT JOIN users u ON m.created_by = u.id
            WHERE cat.company_id = ?
            ORDER BY m.id DESC
        ''', (user['company_id'],))
    rows = c.fetchall()
    conn.close()
    items = []
    for r in rows:
        items.append({
            'id': r['id'], 'title': r['title'], 'content': r['content'],
            'category_id': r['category_id'], 'attachments': r['attachments'],
            'created_by': r['created_by'], 'updated_by': r['updated_by'],
            'updated_at': r['updated_at'], 'created_at': r['created_at'],
            'category_name': r['category_name'], 'level': r['level'],
            'category_color': r['category_color'], 'username': r['username']
        })
    return jsonify({'code': 0, 'data': {'items': items, 'total': len(items)}})


@app.route('/api/admin/messages', methods=['POST'])
@require_admin
def admin_create_message():
    data = request.get_json()
    title = data.get('title', '')
    content = data.get('content', '').strip()
    category_id = data.get('category_id')
    created_by = data.get('created_by')

    if not content:
        return jsonify({'code': 4001, 'message': '话术内容不能为空'}), 400
    if not created_by:
        return jsonify({'code': 4002, 'message': '必须指定创建者'}), 400

    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('''
        INSERT INTO messages (title, content, category_id, attachments, created_by, updated_by, updated_at, created_at)
        VALUES (?, ?, ?, '[]', ?, ?, ?, ?)
    ''', (title, content, category_id, created_by, created_by, now, now))
    msg_id = c.lastrowid
    conn.commit()
    conn.close()

    ws_broadcast(g.user['company_id'], 'message_created', {'id': msg_id})
    return jsonify({'code': 0, 'data': {'id': msg_id}, 'message': '创建成功'})


@app.route('/api/admin/messages/<int:mid>', methods=['PUT'])
@require_admin
def admin_update_message(mid):
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM messages WHERE id = ?", (mid,))
    if not c.fetchone():
        conn.close()
        return jsonify({'code': 4041, 'message': '话术不存在'}), 404

    updates = []
    params = []
    for field in ('title', 'content', 'category_id', 'updated_by'):
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(mid)
        c.execute(f"UPDATE messages SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()

    ws_broadcast(g.user['company_id'], 'message_updated', {'id': mid})
    return jsonify({'code': 0, 'message': '更新成功'})


@app.route('/api/admin/messages/<int:mid>', methods=['DELETE'])
@require_admin
def admin_delete_message(mid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM messages WHERE id = ?", (mid,))
    if not c.fetchone():
        conn.close()
        return jsonify({'code': 4041, 'message': '话术不存在'}), 404

    c.execute("DELETE FROM messages WHERE id = ?", (mid,))
    conn.commit()
    conn.close()

    ws_broadcast(g.user['company_id'], 'message_deleted', {'id': mid})
    return jsonify({'code': 0, 'message': '删除成功'})


# ===== 分类管理 =====
@app.route('/api/categories', methods=['GET'])
@require_auth
def list_categories():
    user = g.user
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT id, name, level, parent_id, department_id, color, sort_order, created_by, created_at
        FROM categories
        WHERE company_id = ?
        ORDER BY sort_order, id
    ''', (user['company_id'],))
    rows = c.fetchall()
    conn.close()

    items = [{
        'id': r['id'], 'name': r['name'], 'level': r['level'],
        'parentId': r['parent_id'], 'departmentId': r['department_id'],
        'color': r['color'], 'sortOrder': r['sort_order'],
        'createdBy': r['created_by'], 'createdAt': r['created_at']
    } for r in rows]
    return jsonify({'code': 0, 'data': items})


@app.route('/api/categories', methods=['POST'])
@require_auth
def create_category():
    user = g.user
    data = request.json or {}
    name = data.get('name', '').strip()
    level = data.get('level', 'personal')
    if not name:
        return jsonify({'code': 4001, 'message': '名称不能为空'}), 400
    if level not in ['company', 'department', 'personal']:
        return jsonify({'code': 4001, 'message': '层级只能是 company/department/personal'}), 400

    # 权限检查：只有管理员能创建公司级分类（兼容 admin 和 super_admin）
    if level == 'company' and user['role'] not in ('admin', 'super_admin'):
        return jsonify({'code': 4031, 'message': '只有管理员能创建公司级分类'}), 403

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO categories (name, level, parent_id, company_id, department_id, color, sort_order, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, level, data.get('parentId'), user['company_id'],
         user['department_id'] if level != 'company' else None,
         data.get('color', '#1890FF'), data.get('sortOrder', 0),
         user['id'], datetime.now().isoformat())
    )
    cat_id = c.lastrowid
    conn.commit()
    conn.close()

    cat_data = {'id': cat_id, 'name': name, 'level': level, 'createdBy': user['id']}
    ws_broadcast(user['company_id'], 'category_created', cat_data)

    return jsonify({'code': 0, 'message': '创建成功', 'data': cat_data})


@app.route('/api/categories/<int:cid>', methods=['PUT'])
@require_auth
def update_category(cid):
    user = g.user
    data = request.json or {}

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, level, created_by FROM categories WHERE id = ? AND company_id = ?", (cid, user['company_id']))
    cat = c.fetchone()
    if not cat:
        conn.close()
        return jsonify({'code': 4041, 'message': '分类不存在'}), 404

    # 权限：只有管理员能修改公司级，客服只能修改自己创建的部门/个人级
    if cat['level'] == 'company' and user['role'] != 'admin':
        conn.close()
        return jsonify({'code': 4031, 'message': '权限不足'}), 403

    updates, params = [], []
    if 'name' in data and data['name'].strip():
        updates.append("name = ?")
        params.append(data['name'].strip())
    if 'color' in data:
        updates.append("color = ?")
        params.append(data['color'])
    if 'sortOrder' in data:
        updates.append("sort_order = ?")
        params.append(data['sortOrder'])

    if updates:
        params.append(cid)
        c.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()

    ws_broadcast(user['company_id'], 'category_updated', {'id': cid})

    return jsonify({'code': 0, 'message': '更新成功'})


@app.route('/api/categories/<int:cid>', methods=['DELETE'])
@require_auth
def delete_category(cid):
    user = g.user

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, level, created_by FROM categories WHERE id = ? AND company_id = ?", (cid, user['company_id']))
    cat = c.fetchone()
    if not cat:
        conn.close()
        return jsonify({'code': 4041, 'message': '分类不存在'}), 404

    if cat['level'] == 'company' and user['role'] != 'admin':
        conn.close()
        return jsonify({'code': 4031, 'message': '只有管理员能删除公司级分类'}), 403

    # 删除该分类下所有话术
    c.execute("DELETE FROM messages WHERE category_id = ?", (cid,))
    c.execute("DELETE FROM categories WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

    ws_broadcast(user['company_id'], 'category_deleted', {'id': cid})

    return jsonify({'code': 0, 'message': '删除成功'})


# ===== 话术(消息)管理 =====
def can_access_category(user: dict, cat_level: str, cat_dept_id: int, cat_created_by: int) -> bool:
    """检查用户是否能操作某分类"""
    if user['role'] == 'admin':
        return True
    if cat_level == 'company':
        return True  # 所有人可见
    if cat_level == 'department':
        return user['department_id'] == cat_dept_id
    if cat_level == 'personal':
        return cat_created_by == user['id']
    return False


def can_edit_category(user: dict, cat_level: str, cat_created_by: int, cat_dept_id: int) -> bool:
    """检查用户是否能编辑某分类"""
    if user['role'] == 'admin':
        return True
    if cat_level == 'company':
        return False  # 非管理员不能编辑公司级分类
    if cat_level == 'department':
        return user['department_id'] == cat_dept_id
    if cat_level == 'personal':
        return cat_created_by == user['id']
    return False


@app.route('/api/messages', methods=['GET'])
@require_auth
def list_messages():
    user = g.user
    category_id = request.args.get('categoryId', type=int)
    keyword = request.args.get('keyword', '').strip()
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 50, type=int)
    offset = (page - 1) * page_size

    conn = get_db()
    c = conn.cursor()

    # 构建可见分类查询
    base_where = "c.company_id = ?"
    base_params = [user['company_id']]

    if user['role'] == 'admin':
        pass  # 管理员看所有
    elif user['role'] == 'agent':
        # 客服看：公司级 + 自己部门的部门级 + 个人级（自己创建的）
        dept_filter = "c.level = 'company' OR c.level = 'department' OR (c.level = 'personal' AND c.created_by = ?)"
        base_params.append(user['id'])

    c.execute(f'''
        SELECT m.id, m.title, m.content, m.category_id, m.attachments,
               m.created_by, m.updated_by, m.updated_at, m.created_at,
               c.name as category_name, c.level as category_level, c.color as category_color,
               u.username as creator_name
        FROM messages m
        JOIN categories c ON m.category_id = c.id
        JOIN users u ON m.created_by = u.id
        WHERE {base_where}
        {"AND (" + dept_filter + ")" if user['role'] == 'agent' else ""}
        {"AND m.category_id = ?" if category_id else ""}
        {"AND (m.title LIKE ? OR m.content LIKE ?)" if keyword else ""}
        ORDER BY m.updated_at DESC
        LIMIT ? OFFSET ?
    ''', base_params + ([category_id] if category_id else []) + ([f'%{keyword}%', f'%{keyword}%'] if keyword else []) + [page_size, offset])
    rows = c.fetchall()

    c.execute(f'''
        SELECT COUNT(*)
        FROM messages m
        JOIN categories c ON m.category_id = c.id
        WHERE {base_where}
        {"AND (" + dept_filter + ")" if user['role'] == 'agent' else ""}
        {"AND m.category_id = ?" if category_id else ""}
        {"AND (m.title LIKE ? OR m.content LIKE ?)" if keyword else ""}
    ''', base_params + ([category_id] if category_id else []) + ([f'%{keyword}%', f'%{keyword}%'] if keyword else []))
    total = c.fetchone()[0]
    conn.close()

    items = [{
        'id': r['id'], 'title': r['title'], 'content': r['content'],
        'categoryId': r['category_id'], 'categoryName': r['category_name'],
        'categoryLevel': r['category_level'], 'categoryColor': r['category_color'],
        'attachments': json.loads(r['attachments']) if r['attachments'] else [],
        'createdBy': r['created_by'], 'creatorName': r['creator_name'],
        'updatedBy': r['updated_by'], 'updatedAt': r['updated_at'], 'createdAt': r['created_at']
    } for r in rows]

    return jsonify({'code': 0, 'data': {'items': items, 'total': total, 'page': page, 'pageSize': page_size}})


@app.route('/api/messages', methods=['POST'])
@require_auth
def create_message():
    user = g.user
    data = request.json or {}
    content = data.get('content', '').strip()
    category_id = data.get('categoryId')

    if not content:
        return jsonify({'code': 4001, 'message': '内容不能为空'}), 400
    if not category_id:
        return jsonify({'code': 4001, 'message': '请选择分类'}), 400

    conn = get_db()
    c = conn.cursor()

    # 检查分类
    c.execute("SELECT id, level, department_id, created_by FROM categories WHERE id = ? AND company_id = ?",
              (category_id, user['company_id']))
    cat = c.fetchone()
    if not cat:
        conn.close()
        return jsonify({'code': 4041, 'message': '分类不存在'}), 404

    if not can_access_category(user, cat['level'], cat['department_id'], cat['created_by']):
        conn.close()
        return jsonify({'code': 4031, 'message': '无权在此分类添加话术'}), 403

    attachments = json.dumps(data.get('attachments', []), ensure_ascii=False)
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO messages (title, content, category_id, attachments, created_by, updated_by, updated_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (data.get('title', '').strip() or None, content, category_id, attachments, user['id'], user['id'], now, now)
    )
    msg_id = c.lastrowid
    conn.commit()
    conn.close()

    msg_data = {
        'id': msg_id, 'title': data.get('title', ''), 'content': content,
        'categoryId': category_id, 'createdBy': user['id']
    }
    ws_broadcast(user['company_id'], 'message_created', msg_data)

    return jsonify({'code': 0, 'message': '创建成功', 'data': msg_data})


@app.route('/api/messages/<int:mid>', methods=['PUT'])
@require_auth
def update_message(mid):
    user = g.user
    data = request.json or {}

    conn = get_db()
    c = conn.cursor()

    c.execute('''
        SELECT m.id, m.created_by, m.category_id, c.level as category_level,
               c.department_id as cat_dept_id, c.created_by as cat_created_by
        FROM messages m JOIN categories c ON m.category_id = c.id
        WHERE m.id = ? AND c.company_id = ?
    ''', (mid, user['company_id']))
    msg = c.fetchone()
    if not msg:
        conn.close()
        return jsonify({'code': 4041, 'message': '话术不存在'}), 404

    # 权限：管理员可编辑所有，客服只能编辑自己创建的
    if user['role'] != 'admin' and msg['created_by'] != user['id']:
        conn.close()
        return jsonify({'code': 4031, 'message': '只能编辑自己创建的话术'}), 403

    updates, params = [], []
    if 'content' in data and data['content'].strip():
        updates.append("content = ?")
        params.append(data['content'].strip())
    if 'title' in data:
        updates.append("title = ?")
        params.append(data['title'].strip() or None)
    if 'categoryId' in data:
        updates.append("category_id = ?")
        params.append(data['categoryId'])
    if 'attachments' in data:
        updates.append("attachments = ?")
        params.append(json.dumps(data['attachments'], ensure_ascii=False))

    if updates:
        updates.append("updated_by = ?")
        params.append(user['id'])
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(mid)
        c.execute(f"UPDATE messages SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()

    ws_broadcast(user['company_id'], 'message_updated', {'id': mid, 'updatedBy': user['id']})

    return jsonify({'code': 0, 'message': '更新成功'})


@app.route('/api/messages/<int:mid>', methods=['DELETE'])
@require_auth
def delete_message(mid):
    user = g.user

    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT m.id, m.created_by, c.company_id
        FROM messages m JOIN categories c ON m.category_id = c.id
        WHERE m.id = ? AND c.company_id = ?
    ''', (mid, user['company_id']))
    msg = c.fetchone()
    if not msg:
        conn.close()
        return jsonify({'code': 4041, 'message': '话术不存在'}), 404

    if user['role'] != 'admin' and msg['created_by'] != user['id']:
        conn.close()
        return jsonify({'code': 4031, 'message': '只能删除自己创建的话术'}), 403

    c.execute("DELETE FROM messages WHERE id = ?", (mid,))
    conn.commit()
    conn.close()

    ws_broadcast(user['company_id'], 'message_deleted', {'id': mid})

    return jsonify({'code': 0, 'message': '删除成功'})


# ===== WebSocket =====
@app.route('/ws')
def websocket_endpoint():
    """WebSocket连接端点 /ws"""
    return jsonify({'code': 0, 'message': 'WebSocket endpoint active'}), 200


@sock.route('/ws')
def ws_handler(ws):
    """处理WebSocket连接"""
    user = None
    company_id = None

    try:
        # 第一个消息：发送认证token
        msg = ws.receive(timeout=15)
        payload = json.loads(msg)
        token = payload.get('token', '')

        if not token:
            ws.close()
            return

        # 验证token
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            SELECT u.id, u.username, u.role, u.company_id, u.department_id
            FROM users u JOIN tokens t ON u.id = t.user_id
            WHERE t.token = ? AND t.expires_at > ?
        ''', (token, datetime.now().isoformat()))
        user = c.fetchone()
        conn.close()

        if not user:
            ws.close()
            return

        user = dict(user)
        company_id = user['company_id']

        # 注册连接
        with ws_lock:
            if company_id not in ws_connections:
                ws_connections[company_id] = set()
            ws_connections[company_id].add(ws)

        print(f"[WS] User {user['username']} connected (company={company_id})")

        # 发送欢迎消息
        ws.send(json.dumps({'event': 'connected', 'data': {
            'userId': user['id'], 'username': user['username'], 'companyId': company_id
        }}))

        # 持续监听消息（心跳保持连接）
        while True:
            msg = ws.receive(timeout=60)
            if msg is None:
                break
            data = json.loads(msg)
            event = data.get('event', '')

            if event == 'ping':
                ws.send(json.dumps({'event': 'pong', 'data': {'time': datetime.now().isoformat()}}))
            elif event == 'sync_request':
                # 客户端请求同步，确认收到
                ws.send(json.dumps({'event': 'sync_ack', 'data': {'requestedAt': data.get('at', '')}}))

    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        if company_id:
            with ws_lock:
                if company_id in ws_connections:
                    ws_connections[company_id].discard(ws)
        print(f"[WS] User disconnected")


# ===== 管理后台页面 =====
@app.route('/admin')
def admin_page():
    admin_path = os.path.join(BASE_DIR, 'admin.html')
    if os.path.exists(admin_path):
        return send_file(admin_path)
    return jsonify({'status': 'ok', 'message': '管理页面未找到'}), 404


# ========== 工具接口 ==========

@app.route('/api/utils/phone-location', methods=['GET'])
def phone_location():
    """查询手机号码归属地（无需登录）"""
    phone = request.args.get('phone', '').strip()
    if not phone or len(phone) < 7:
        return jsonify({'location': ''})
    
    # 纯数字提取
    import re
    digits = re.sub(r'\D', '', phone)
    if not digits:
        return jsonify({'location': ''})
    
    # 常用号段归属地映射（覆盖主要运营商）
    location_map = {
        # 移动
        '134': '移动', '135': '移动', '136': '移动', '137': '移动', '138': '移动', '139': '移动',
        '150': '移动', '151': '移动', '152': '移动', '157': '移动', '158': '移动', '159': '移动',
        '178': '移动', '182': '移动', '183': '移动', '184': '移动', '187': '移动', '188': '移动',
        '195': '移动', '197': '移动', '198': '移动',
        # 联通
        '130': '联通', '131': '联通', '132': '联通', '155': '联通', '156': '联通',
        '166': '联通', '175': '联通', '176': '联通', '185': '联通', '186': '联通',
        '196': '联通',
        # 电信
        '133': '电信', '149': '电信', '153': '电信', '173': '电信', '177': '电信',
        '180': '电信', '181': '电信', '189': '电信', '191': '电信', '193': '电信', '199': '电信',
        # 广电
        '192': '广电',
        # 虚拟运营商
        '170': '虚拟运营商', '171': '虚拟运营商', '165': '虚拟运营商', '167': '虚拟运营商',
    }
    
    # 区号+城市映射（部分常用）
    area_map = {
        '010': '北京', '021': '上海', '020': '广州', '022': '天津', '023': '重庆',
        '024': '沈阳', '025': '南京', '027': '武汉', '028': '成都', '029': '西安',
        '0311': '石家庄', '0312': '保定', '0315': '唐山', '0316': '廊坊', '0351': '太原',
        '0411': '大连', '0431': '长春', '0451': '哈尔滨', '0531': '济南', '0532': '青岛',
        '0551': '合肥', '0571': '杭州', '0574': '宁波', '0591': '福州', '0592': '厦门',
        '0631': '威海', '0731': '长沙', '0755': '深圳', '0756': '珠海', '0769': '东莞',
        '0791': '南昌', '0851': '贵阳', '0898': '海口', '0917': '宝鸡', '0931': '兰州',
        '0512': '苏州', '0510': '无锡', '0516': '徐州', '0513': '南通', '0519': '常州',
        '0371': '郑州', '0377': '南阳', '0379': '洛阳', '0533': '淄博', '0535': '烟台',
        '0536': '潍坊', '0635': '聊城', '0538': '泰安', '0546': '东营', '0530': '菏泽',
        '0734': '衡阳', '0736': '常德', '0743': '湘西', '0745': '怀化', '0746': '永州',
        '0762': '河源', '0763': '清远', '0768': '潮州', '0751': '韶关', '0752': '惠州',
        '0753': '梅州', '0754': '汕尾', '0757': '佛山', '0758': '肇庆', '0759': '湛江',
        '0760': '中山', '0754': '揭阳', '0768': '潮州', '0771': '南宁', '0772': '柳州',
        '0773': '桂林', '0774': '梧州', '0775': '玉林', '0777': '百色', '0792': '九江',
        '0793': '上饶', '0795': '新余', '0796': '吉安', '0797': '赣州', '0798': '景德镇',
        '0813': '自贡', '0816': '绵阳', '0817': '南充', '0830': '泸州', '0831': '宜宾',
        '0832': '内江', '0833': '乐山', '0835': '雅安', '0837': '巴中', '0838': '德阳',
        '0839': '广元', '0852': '遵义', '0853': '安顺', '0854': '黔南', '0855': '黔东南',
        '0856': '铜仁', '0857': '毕节', '0858': '六盘水', '0871': '昆明', '0872': '大理',
        '0873': '红河', '0874': '曲靖', '0876': '文山', '0877': '玉溪', '0878': '楚雄',
        '0883': '临沧', '0886': '怒江', '0887': '保山', '0888': '丽江', '0891': '拉萨',
        '0892': '日喀则', '0893': '山南', '0910': '咸阳', '0911': '延安', '0912': '榆林',
        '0913': '渭南', '0916': '汉中', '0919': '铜川', '0932': '定西', '0933': '平凉',
        '0934': '庆阳', '0935': '武威', '0936': '张掖', '0937': '酒泉', '0938': '天水',
        '0939': '陇南', '0941': '甘南', '0943': '白银', '0951': '银川', '0952': '石嘴山',
        '0953': '吴忠', '0971': '西宁', '0972': '海东', '0973': '黄南', '0974': '海北',
        '0975': '海南藏', '0976': '果洛', '0977': '海西', '0990': '克拉玛依', '0991': '乌鲁木齐',
        '0992': '伊犁', '0993': '昌吉', '0994': '吐鲁番', '0995': '哈密', '0996': '巴音郭楞',
        '0997': '阿克苏', '0998': '喀什', '0999': '和田',
        # 浙江更多
        '0573': '嘉兴', '0575': '绍兴', '0576': '台州', '0577': '温州', '0578': '丽水', '0580': '舟山',
        '0579': '金华', '0581': '衢州',
        # 江苏更多
        '0511': '镇江', '0514': '扬州', '0515': '盐城', '0517': '淮安', '0523': '泰州',
        # 山东更多
        '0534': '德州', '0539': '临沂', '0543': '滨州',
        # 河南更多
        '0372': '安阳', '0373': '新乡', '0374': '许昌', '0375': '平顶山', '0376': '信阳',
        '0378': '开封', '0391': '焦作', '0392': '鹤壁', '0393': '濮阳', '0394': '驻马店',
        '0395': '漯河', '0396': '三门峡', '0398': '商丘', '0399': '周口',
        # 湖北更多
        '0710': '襄阳', '0711': '鄂州', '0712': '孝感', '0713': '黄冈', '0714': '黄石',
        '0715': '咸宁', '0716': '荆州', '0717': '宜昌', '0718': '恩施', '0719': '十堰',
        '0722': '随州', '0724': '荆门', '0728': '仙桃/潜江',
        # 湖南更多
        '0730': '岳阳', '0732': '湘潭', '0733': '株洲', '0735': '郴州', '0737': '益阳',
        '0738': '娄底', '0739': '邵阳', '0744': '张家界',
        # 广东更多
        '0660': '汕尾', '0662': '阳江', '0663': '揭阳', '0664': '云浮', '0668': '茂名',
        '0750': '江门', '0754': '汕尾', '0763': '清远', '0766': '云浮',
        # 四川更多
        '0814': '攀枝花', '0818': '达州', '0825': '遂宁', '0826': '广安', '0827': '巴中',
        # 福建更多
        '0593': '宁德', '0594': '莆田', '0595': '泉州', '0596': '漳州', '0597': '龙岩',
        # 安徽更多
        '0552': '蚌埠', '0553': '芜湖', '0554': '淮南', '0555': '马鞍山', '0556': '安庆',
        '0557': '阜阳', '0558': '亳州', '0559': '黄山', '0561': '淮北', '0562': '铜陵',
        '0563': '宣城', '0564': '六安', '0565': '巢湖', '0566': '池州',
        # 河北更多
        '0313': '张家口', '0314': '承德', '0317': '沧州', '0318': '衡水', '0319': '邢台',
        '0335': '秦皇岛', '0352': '大同', '0353': '阳泉', '0354': '晋中', '0355': '长治',
        '0356': '晋城', '0359': '运城', '0370': '商丘', '0410': '抚顺', '0412': '鞍山',
        '0413': '本溪', '0414': '丹东', '0415': '丹东', '0416': '锦州', '0417': '营口',
        '0418': '阜新', '0419': '辽阳', '0427': '盘锦', '0429': '朝阳', '0432': '吉林市',
        '0433': '延边', '0434': '四平', '0435': '通化', '0436': '白城', '0437': '辽源',
        '0438': '松原', '0452': '齐齐哈尔', '0453': '牡丹江', '0454': '佳木斯',
        '0456': '黑河', '0457': '大兴安岭', '0458': '伊春', '0459': '大庆',
        # 江西更多
        '0790': '新余', '0794': '宜春',
        # 陕西更多
        '0914': '商洛', '0915': '安康', '0916': '汉中',
        # 山西更多
        '0350': '忻州', '0357': '临汾', '0358': '吕梁',
        # 内蒙古
        '0471': '呼和浩特', '0472': '包头', '0473': '乌海', '0474': '乌兰察布',
        '0475': '赤峰', '0476': '鄂尔多斯', '0477': '呼伦贝尔', '0478': '巴彦淖尔',
        '0479': '锡林郭勒', '0482': '兴安盟', '0483': '阿拉善',
        # 辽宁更多
        '0415': '丹东', '0417': '营口', '0418': '阜新', '0427': '盘锦',
        # 吉林更多
        '0431': '长春', '0432': '吉林', '0433': '延边', '0434': '四平',
        '0435': '通化', '0436': '白城', '0437': '辽源', '0438': '松原',
        # 黑龙江更多
        '0451': '哈尔滨', '0452': '齐齐哈尔', '0453': '牡丹江',
        '0454': '佳木斯', '0455': '绥化', '0456': '黑河', '0457': '大兴安岭',
        '0458': '伊春', '0459': '大庆',
        # 海南
        '0890': '儋州', '0898': '海口', '0899': '三亚',
        # 广西
        '0771': '南宁', '0772': '柳州', '0773': '桂林', '0774': '梧州',
        '0775': '玉林', '0776': '百色', '0777': '河池', '0778': '北海',
        '0779': '防城港', '0780': '崇左',
        # 贵州
        '0851': '贵阳', '0852': '遵义', '0853': '安顺', '0854': '黔南',
        '0855': '黔东南', '0856': '铜仁', '0857': '毕节', '0858': '六盘水',
        # 云南
        '0871': '昆明', '0872': '大理', '0873': '红河', '0874': '曲靖',
        '0875': '普洱', '0876': '文山', '0877': '玉溪', '0878': '楚雄',
        '0879': '普洱', '0883': '临沧', '0886': '怒江', '0887': '保山',
        '0888': '丽江', '0889': '迪庆',
        # 甘肃
        '0931': '兰州', '0932': '定西', '0933': '平凉', '0934': '庆阳',
        '0935': '武威', '0936': '张掖', '0937': '酒泉', '0938': '天水',
        '0939': '陇南', '0941': '甘南', '0943': '白银',
        # 宁夏
        '0951': '银川', '0952': '石嘴山', '0953': '吴忠', '0954': '固原', '0955': '中卫',
        # 青海
        '0971': '西宁', '0972': '海东', '0973': '黄南', '0974': '海北',
        '0975': '海南藏', '0976': '果洛', '0977': '海西',
        # 新疆
        '0901': '塔城', '0902': '哈密', '0903': '阿克苏', '0906': '阿勒泰',
        '0908': '喀什', '0909': '昌吉', '0910': '咸阳', '0990': '克拉玛依',
        '0991': '乌鲁木齐', '0992': '伊犁', '0993': '昌吉', '0994': '吐鲁番',
        '0995': '哈密', '0996': '巴音郭楞', '0997': '阿克苏', '0998': '喀什', '0999': '和田',
        # 西藏
        '0891': '拉萨', '0892': '日喀则', '0893': '山南', '0894': '林芝',
        '0895': '那曲', '0896': '阿里', '0897': '昌都',
    }
    
    carrier = location_map.get(digits[:3], '')
    
    # 手机号：11位，根据号段判断
    if len(digits) == 11 and digits[0] == '1':
        # 根据第4-7位查更精确的归属地（简化版）
        prefix = digits[:4]  # 号段+第4位
        # 常见精确匹配
        precise_map = {
            # 移动 - 北京
            '1358': '北京移动', '1361': '北京移动', '1365': '北京移动', '1370': '北京移动',
            '1381': '北京移动', '1391': '北京移动', '1501': '北京移动', '1512': '北京移动',
            '1520': '北京移动', '1551': '北京移动', '1560': '北京移动', '1581': '北京移动',
            '1860': '北京移动', '1861': '北京移动', '1881': '北京移动',
            # 移动 - 上海
            '1350': '上海移动', '1361': '上海移动', '1376': '上海移动', '1381': '上海移动',
            '1391': '上海移动', '1500': '上海移动', '1510': '上海移动', '1521': '上海移动',
            '1569': '上海移动', '1580': '上海移动', '1590': '上海移动', '1820': '上海移动',
            '1830': '上海移动', '1870': '上海移动', '1880': '上海移动',
            # 移动 - 广州/广东
            '1353': '广东移动', '1360': '广东移动', '1362': '广东移动', '1370': '广东移动',
            '1380': '广东移动', '1392': '广东移动', '1501': '广东移动', '1510': '广东移动',
            '1520': '广东移动', '1530': '广东移动', '1560': '广东移动', '1580': '广东移动',
            '1590': '广东移动', '1882': '广东移动',
            # 移动 - 浙江
            '1356': '浙江移动', '1366': '浙江移动', '1375': '浙江移动', '1386': '浙江移动',
            '1395': '浙江移动', '1506': '浙江移动', '1575': '浙江移动', '1585': '浙江移动',
            '1595': '浙江移动', '1885': '浙江移动',
            # 移动 - 福建
            '1359': '福建移动', '1367': '福建移动', '1370': '福建移动', '1395': '福建移动',
            '1508': '福建移动', '1588': '福建移动', '1598': '福建移动', '1865': '福建移动',
            '1885': '福建移动',
            # 移动 - 湖北
            '1347': '湖北移动', '1354': '湖北移动', '1363': '湖北移动', '1397': '湖北移动',
            '1507': '湖北移动', '1582': '湖北移动', '1592': '湖北移动', '1827': '湖北移动',
            '1867': '湖北移动', '1887': '湖北移动',
            # 移动 - 四川
            '1358': '四川移动', '1368': '四川移动', '1377': '四川移动', '1388': '四川移动',
            '1399': '四川移动', '1508': '四川移动', '1588': '四川移动', '1598': '四川移动',
            '1808': '四川移动', '1818': '四川移动', '1888': '四川移动',
            # 移动 - 安徽
            '1385': '安徽移动', '1396': '安徽移动', '1505': '安徽移动', '1555': '安徽移动',
            '1565': '安徽移动', '1585': '安徽移动', '1595': '安徽移动', '1815': '安徽移动',
            '1885': '安徽移动',
            # 联通 - 北京
            '1300': '北京联通', '1310': '北京联通', '1324': '北京联通', '1550': '北京联通',
            '1560': '北京联通', '1850': '北京联通', '1860': '北京联通',
            # 联通 - 上海
            '1301': '上海联通', '1312': '上海联通', '1324': '上海联通', '1561': '上海联通',
            '1851': '上海联通', '1861': '上海联通',
            # 联通 - 广东
            '1302': '广东联通', '1312': '广东联通', '1322': '广东联通', '1559': '广东联通',
            '1562': '广东联通', '1852': '广东联通', '1862': '广东联通',
            # 联通 - 浙江
            '1306': '浙江联通', '1315': '浙江联通', '1555': '浙江联通', '1566': '浙江联通',
            '1856': '浙江联通', '1866': '浙江联通',
            # 联通 - 福建
            '1308': '福建联通', '1318': '福建联通', '1558': '福建联通', '1858': '福建联通',
            '1868': '福建联通',
            # 联通 - 湖北
            '1301': '湖北联通', '1316': '湖北联通', '1327': '湖北联通', '1557': '湖北联通',
            '1857': '湖北联通', '1867': '湖北联通',
            # 电信 - 北京
            '1330': '北京电信', '1530': '北京电信', '1770': '北京电信', '1800': '北京电信',
            '1890': '北京电信',
            # 电信 - 上海
            '1331': '上海电信', '1531': '上海电信', '1771': '上海电信', '1801': '上海电信',
            '1891': '上海电信',
            # 电信 - 广东
            '1332': '广东电信', '1533': '广东电信', '1771': '广东电信', '1802': '广东电信',
            '1892': '广东电信',
            # 电信 - 浙江
            '1336': '浙江电信', '1534': '浙江电信', '1776': '浙江电信', '1806': '浙江电信',
            '1896': '浙江电信',
            # 电信 - 福建
            '1339': '福建电信', '1539': '福建电信', '1809': '福建电信', '1899': '福建电信',
            # 电信 - 湖北
            '1337': '湖北电信', '1537': '湖北电信', '1776': '湖北电信', '1807': '湖北电信',
            '1897': '湖北电信',
            # 电信 - 四川
            '1338': '四川电信', '1538': '四川电信', '1808': '四川电信', '1809': '四川电信',
            '1898': '四川电信',
            # 电信 - 安徽
            '1330': '安徽电信', '1539': '安徽电信', '1810': '安徽电信', '1890': '安徽电信',
        }
        
        result = precise_map.get(prefix, '')
        if result:
            return jsonify({'location': result})
        
        # 降级：只返回运营商
        if carrier:
            return jsonify({'location': carrier})
        return jsonify({'location': '未知'})
    
    # 固定电话：根据区号查城市
    if len(digits) >= 10 and digits[0] in ('0',):
        area_code = digits[:4] if digits[1] in ('1','2') else digits[:3]
        city = area_map.get(area_code, '')
        if city:
            return jsonify({'location': city})
        return jsonify({'location': '未知'})
    
    # 其他情况
    if carrier:
        return jsonify({'location': carrier})
    return jsonify({'location': '未知'})


@app.route('/health')
def health():
    with ws_lock:
        total_conn = sum(len(v) for v in ws_connections.values())
    return jsonify({
        'status': 'ok',
        'service': 'quick-reply-v4',
        'version': '4.0',
        'ws_connections': total_conn,
        'db': DATABASE
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({'code': 4040, 'message': '接口不存在'}), 404


@app.errorhandler(413)
def too_large(e):
    return jsonify({'code': 4002, 'message': '文件过大(最大100MB)'}), 413


if __name__ == '__main__':
    init_db()
    print('=' * 60)
    print('  快回复后端服务器 v4.0 - 团队协作版')
    print('=' * 60)
    print(f'  本地:   http://localhost:{PORT}')
    print(f'  WebSocket: ws://localhost:{PORT}/ws')
    print(f'  管理后台: http://localhost:{PORT}/admin')
    print('=' * 60)
    print('  默认管理员: admin / admin123')
    print('  核心接口:')
    print('    POST   /api/auth/login      登录')
    print('    GET    /api/auth/profile    个人资料')
    print('    GET    /api/categories      分类列表')
    print('    POST   /api/categories      创建分类')
    print('    GET    /api/messages        话术列表')
    print('    POST   /api/messages        创建话术')
    print('    PUT    /api/messages/:id    更新话术')
    print('    DELETE /api/messages/:id    删除话术')
    print('    GET    /api/admin/users     用户列表(管理员)')
    print('    POST   /api/admin/users     创建用户(管理员)')
    print('  WebSocket消息事件:')
    print('    connected | ping/pong | sync_request')
    print('    message_created | message_updated | message_deleted')
    print('    category_created | category_updated | category_deleted')
    print('    user_created | user_deleted')
    print('=' * 60)
    app.run(host=HOST, port=PORT, debug=False, threaded=True)

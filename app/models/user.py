"""用户模型 - 支持公司+部门结构"""
import sqlite3
from datetime import datetime
from config.config import Config

class User:
    @staticmethod
    def get_db():
        return sqlite3.connect(Config.DATABASE)

    @staticmethod
    def init_db():
        conn = User.get_db()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                company_id INTEGER,
                department_id INTEGER,
                role TEXT DEFAULT 'customer',
                email TEXT DEFAULT '',
                wechat_id TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                last_login TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (company_id) REFERENCES companies(id),
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
        ''')
        conn.commit()
        conn.close()

    @staticmethod
    def create(username, password, company_id=None, department_id=None, role='customer', email='', wechat_id=''):
        import uuid
        conn = User.get_db()
        c = conn.cursor()
        user_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        try:
            c.execute(
                'INSERT INTO users (id, username, password, company_id, department_id, role, email, wechat_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (user_id, username, password, company_id, department_id, role, email, wechat_id, created_at)
            )
            conn.commit()
            conn.close()
            return {'id': user_id, 'username': username, 'company_id': company_id, 'department_id': department_id, 'role': role, 'created_at': created_at}
        except sqlite3.IntegrityError:
            conn.close()
            return None

    @staticmethod
    def authenticate(username, password):
        conn = User.get_db()
        c = conn.cursor()
        c.execute(
            'SELECT id, username, company_id, department_id, role FROM users WHERE username = ? AND password = ? AND is_active = 1',
            (username, password)
        )
        user = c.fetchone()
        if user:
            c.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user[0]))
            conn.commit()
        conn.close()
        if user:
            return {'id': user[0], 'username': user[1], 'company_id': user[2], 'department_id': user[3], 'role': user[4]}
        return None

    @staticmethod
    def get_by_id(user_id):
        conn = User.get_db()
        c = conn.cursor()
        c.execute('''
            SELECT u.id, u.username, u.email, u.wechat_id, u.company_id, u.department_id, u.role, u.created_at, u.last_login, c.name, d.name
            FROM users u
            LEFT JOIN companies c ON u.company_id = c.id
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.id = ?
        ''', (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                'id': row[0], 'username': row[1], 'email': row[2], 'wechat_id': row[3],
                'company_id': row[4], 'department_id': row[5], 'role': row[6],
                'created_at': row[7], 'last_login': row[8],
                'company_name': row[9], 'department_name': row[10]
            }
        return None

    @staticmethod
    def get_by_company(company_id):
        conn = User.get_db()
        c = conn.cursor()
        c.execute('SELECT id, username, email, department_id, role, is_active FROM users WHERE company_id = ? ORDER BY id', (company_id,))
        rows = c.fetchall()
        conn.close()
        return [{'id': r[0], 'username': r[1], 'email': r[2], 'department_id': r[3], 'role': r[4], 'is_active': r[5]} for r in rows]

    @staticmethod
    def get_by_department(department_id):
        conn = User.get_db()
        c = conn.cursor()
        c.execute('SELECT id, username, email, role, is_active FROM users WHERE department_id = ? ORDER BY id', (department_id,))
        rows = c.fetchall()
        conn.close()
        return [{'id': r[0], 'username': r[1], 'email': r[2], 'role': r[3], 'is_active': r[4]} for r in rows]

    @staticmethod
    def update_profile(user_id, email=None, wechat_id=None):
        conn = User.get_db()
        c = conn.cursor()
        if email is not None:
            c.execute('UPDATE users SET email = ? WHERE id = ?', (email, user_id))
        if wechat_id is not None:
            c.execute('UPDATE users SET wechat_id = ? WHERE id = ?', (wechat_id, user_id))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def update_user(user_id, role=None, department_id=None, is_active=None):
        conn = User.get_db()
        c = conn.cursor()
        if role is not None:
            c.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
        if department_id is not None:
            c.execute('UPDATE users SET department_id = ? WHERE id = ?', (department_id, user_id))
        if is_active is not None:
            c.execute('UPDATE users SET is_active = ? WHERE id = ?', (is_active, user_id))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def delete(user_id):
        conn = User.get_db()
        c = conn.cursor()
        c.execute('UPDATE users SET is_active = 0 WHERE id = ?', (user_id,))
        conn.commit()
        affected = c.rowcount
        conn.close()
        return affected > 0
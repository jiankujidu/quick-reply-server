"""分类模型"""
import sqlite3
from datetime import datetime
from config.config import Config

class Category:
    @staticmethod
    def get_db():
        return sqlite3.connect(Config.DATABASE)

    @staticmethod
    def init_db():
        conn = Category.get_db()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                department_id INTEGER,
                user_id TEXT,
                name TEXT NOT NULL,
                level TEXT DEFAULT 'private',
                parent_id INTEGER,
                color TEXT DEFAULT '#2563EB',
                sort_order INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (company_id) REFERENCES companies(id),
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
        ''')
        conn.commit()
        conn.close()

    @staticmethod
    def create(company_id, name, level='private', department_id=None, user_id=None, parent_id=None, color='#2563EB', sort_order=0):
        conn = Category.get_db()
        c = conn.cursor()
        created_at = datetime.now().isoformat()
        try:
            c.execute(
                'INSERT INTO categories (company_id, department_id, user_id, name, level, parent_id, color, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (company_id, department_id, user_id, name, level, parent_id, color, sort_order, created_at)
            )
            conn.commit()
            cat_id = c.lastrowid
            conn.close()
            return {'id': cat_id, 'company_id': company_id, 'name': name, 'level': level, 'created_at': created_at}
        except Exception as e:
            conn.close()
            return None

    @staticmethod
    def get_by_company(company_id):
        conn = Category.get_db()
        c = conn.cursor()
        c.execute('''
            SELECT id, company_id, department_id, user_id, name, level, parent_id, color, sort_order, created_at
            FROM categories WHERE company_id = ? ORDER BY sort_order, id
        ''', (company_id,))
        rows = c.fetchall()
        conn.close()
        return [{'id': r[0], 'company_id': r[1], 'department_id': r[2], 'user_id': r[3], 'name': r[4], 'level': r[5], 'parent_id': r[6], 'color': r[7], 'sort_order': r[8], 'created_at': r[9]} for r in rows]

    @staticmethod
    def get_by_id(cat_id):
        conn = Category.get_db()
        c = conn.cursor()
        c.execute('''
            SELECT id, company_id, department_id, user_id, name, level, parent_id, color, sort_order, created_at
            FROM categories WHERE id = ?
        ''', (cat_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'company_id': row[1], 'department_id': row[2], 'user_id': row[3], 'name': row[4], 'level': row[5], 'parent_id': row[6], 'color': row[7], 'sort_order': row[8], 'created_at': row[9]}
        return None

    @staticmethod
    def update(cat_id, name=None, color=None, sort_order=None):
        conn = Category.get_db()
        c = conn.cursor()
        if name is not None:
            c.execute('UPDATE categories SET name = ? WHERE id = ?', (name, cat_id))
        if color is not None:
            c.execute('UPDATE categories SET color = ? WHERE id = ?', (color, cat_id))
        if sort_order is not None:
            c.execute('UPDATE categories SET sort_order = ? WHERE id = ?', (sort_order, cat_id))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def delete(cat_id):
        conn = Category.get_db()
        c = conn.cursor()
        # 先删除子分类
        c.execute('DELETE FROM categories WHERE parent_id = ?', (cat_id,))
        c.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def count_all():
        conn = Category.get_db()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM categories')
        count = c.fetchone()[0]
        conn.close()
        return count
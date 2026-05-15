"""部门模型"""
import sqlite3
from datetime import datetime
from config.config import Config

class Department:
    @staticmethod
    def get_db():
        return sqlite3.connect(Config.DATABASE)

    @staticmethod
    def init_db():
        conn = Department.get_db()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        ''')
        conn.commit()
        conn.close()

    @staticmethod
    def create(company_id, name):
        conn = Department.get_db()
        c = conn.cursor()
        created_at = datetime.now().isoformat()
        try:
            c.execute('INSERT INTO departments (company_id, name, created_at) VALUES (?, ?, ?)',
                      (company_id, name, created_at))
            conn.commit()
            dept_id = c.lastrowid
            conn.close()
            return {'id': dept_id, 'company_id': company_id, 'name': name, 'created_at': created_at}
        except sqlite3.IntegrityError:
            conn.close()
            return None

    @staticmethod
    def get_by_company(company_id):
        conn = Department.get_db()
        c = conn.cursor()
        c.execute('SELECT id, company_id, name, created_at FROM departments WHERE company_id = ? ORDER BY id',
                  (company_id,))
        rows = c.fetchall()
        conn.close()
        return [{'id': r[0], 'company_id': r[1], 'name': r[2], 'created_at': r[3]} for r in rows]

    @staticmethod
    def get_by_id(dept_id):
        conn = Department.get_db()
        c = conn.cursor()
        c.execute('SELECT id, company_id, name, created_at FROM departments WHERE id = ?', (dept_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'company_id': row[1], 'name': row[2], 'created_at': row[3]}
        return None

    @staticmethod
    def delete(dept_id):
        conn = Department.get_db()
        c = conn.cursor()
        c.execute('DELETE FROM departments WHERE id = ?', (dept_id,))
        conn.commit()
        affected = c.rowcount
        conn.close()
        return affected > 0

    @staticmethod
    def update(dept_id, name):
        conn = Department.get_db()
        c = conn.cursor()
        c.execute('UPDATE departments SET name = ? WHERE id = ?', (name, dept_id))
        conn.commit()
        affected = c.rowcount
        conn.close()
        return affected > 0
"""公司模型"""
import sqlite3
from datetime import datetime
from config.config import Config

class Company:
    @staticmethod
    def get_db():
        return sqlite3.connect(Config.DATABASE)

    @staticmethod
    def init_db():
        conn = Company.get_db()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        ''')
        conn.commit()
        conn.close()

    @staticmethod
    def create(name):
        conn = Company.get_db()
        c = conn.cursor()
        created_at = datetime.now().isoformat()
        try:
            c.execute('INSERT INTO companies (name, created_at) VALUES (?, ?)', (name, created_at))
            conn.commit()
            company_id = c.lastrowid
            conn.close()
            return {'id': company_id, 'name': name, 'created_at': created_at}
        except sqlite3.IntegrityError:
            conn.close()
            return None

    @staticmethod
    def get_by_name(name):
        conn = Company.get_db()
        c = conn.cursor()
        c.execute('SELECT id, name, created_at FROM companies WHERE name = ?', (name,))
        row = c.fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'name': row[1], 'created_at': row[2]}
        return None

    @staticmethod
    def get_by_id(company_id):
        conn = Company.get_db()
        c = conn.cursor()
        c.execute('SELECT id, name, created_at FROM companies WHERE id = ?', (company_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'name': row[1], 'created_at': row[2]}
        return None

    @staticmethod
    def get_all():
        conn = Company.get_db()
        c = conn.cursor()
        c.execute('SELECT id, name, created_at FROM companies ORDER BY id')
        rows = c.fetchall()
        conn.close()
        return [{'id': r[0], 'name': r[1], 'created_at': r[2]} for r in rows]

    @staticmethod
    def count_all():
        conn = Company.get_db()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM companies')
        count = c.fetchone()[0]
        conn.close()
        return count

    @staticmethod
    def delete(comp_id):
        conn = Company.get_db()
        c = conn.cursor()
        c.execute('DELETE FROM companies WHERE id = ?', (comp_id,))
        conn.commit()
        affected = c.rowcount
        conn.close()
        return affected > 0
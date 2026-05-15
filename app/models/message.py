"""话术消息模型"""
import sqlite3
from datetime import datetime
from config.config import Config

class Message:
    @staticmethod
    def get_db():
        return sqlite3.connect(Config.DATABASE)

    @staticmethod
    def init_db():
        conn = Message.get_db()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                department_id INTEGER,
                user_id TEXT,
                category_id INTEGER,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                level TEXT DEFAULT 'private',
                tags TEXT DEFAULT '',
                images TEXT DEFAULT '',
                files TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT,
                is_deleted INTEGER DEFAULT 0,
                FOREIGN KEY (company_id) REFERENCES companies(id),
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
        ''')
        conn.commit()
        conn.close()

    @staticmethod
    def create(company_id, title, content, level='private', department_id=None, user_id=None, category_id=None, tags=None, images=None, files=None):
        conn = Message.get_db()
        c = conn.cursor()
        created_at = datetime.now().isoformat()
        tags_json = ','.join(tags) if tags else ''
        images_json = ','.join(images) if images else ''
        files_json = ','.join(files) if files else ''
        try:
            c.execute(
                'INSERT INTO messages (company_id, department_id, user_id, category_id, title, content, level, tags, images, files, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (company_id, department_id, user_id, category_id, title, content, level, tags_json, images_json, files_json, created_at)
            )
            conn.commit()
            msg_id = c.lastrowid
            conn.close()
            return {'id': msg_id, 'title': title, 'content': content, 'level': level, 'created_at': created_at}
        except Exception as e:
            conn.close()
            return None

    @staticmethod
    def get_by_company(company_id, department_id=None, user_id=None, category_id=None, keyword=None, page=1, page_size=50):
        conn = Message.get_db()
        c = conn.cursor()
        offset = (page - 1) * page_size
        
        conditions = ['company_id = ?', 'is_deleted = 0']
        params = [company_id]
        
        if department_id is not None:
            conditions.append('(department_id = ? OR department_id IS NULL)')
            params.append(department_id)
        if user_id is not None:
            conditions.append('user_id = ?')
            params.append(user_id)
        if category_id is not None:
            conditions.append('category_id = ?')
            params.append(category_id)
        if keyword:
            conditions.append('(title LIKE ? OR content LIKE ?)')
            params.extend([f'%{keyword}%', f'%{keyword}%'])
        
        where_clause = ' AND '.join(conditions)
        
        c.execute(f'SELECT COUNT(*) FROM messages WHERE {where_clause}', params)
        total = c.fetchone()[0]
        
        c.execute(f'''
            SELECT m.id, m.title, m.content, m.level, m.tags, m.images, m.files, m.created_at, m.updated_at, m.category_id,
                   c.name as category_name
            FROM messages m
            LEFT JOIN categories c ON m.category_id = c.id
            WHERE {where_clause}
            ORDER BY m.id DESC
            LIMIT ? OFFSET ?
        ''', params + [page_size, offset])
        
        rows = c.fetchall()
        conn.close()
        
        items = []
        for r in rows:
            items.append({
                'id': r[0], 'title': r[1], 'content': r[2], 'level': r[3],
                'tags': r[4].split(',') if r[4] else [],
                'images': r[5].split(',') if r[5] else [],
                'files': r[6].split(',') if r[6] else [],
                'created_at': r[7], 'updated_at': r[8],
                'category_id': r[9], 'category_name': r[10]
            })
        
        return {'items': items, 'total': total, 'page': page, 'page_size': page_size}

    @staticmethod
    def get_by_id(msg_id):
        conn = Message.get_db()
        c = conn.cursor()
        c.execute('''
            SELECT m.id, m.title, m.content, m.level, m.tags, m.images, m.files, m.created_at, m.updated_at, 
                   m.category_id, m.department_id, m.user_id,
                   c.name as category_name
            FROM messages m
            LEFT JOIN categories c ON m.category_id = c.id
            WHERE m.id = ? AND m.is_deleted = 0
        ''', (msg_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                'id': row[0], 'title': row[1], 'content': row[2], 'level': row[3],
                'tags': row[4].split(',') if row[4] else [],
                'images': row[5].split(',') if row[5] else [],
                'files': row[6].split(',') if row[6] else [],
                'created_at': row[7], 'updated_at': row[8],
                'category_id': row[9], 'department_id': row[10], 'user_id': row[11],
                'category_name': row[12]
            }
        return None

    @staticmethod
    def update(msg_id, title=None, content=None, category_id=None, tags=None):
        conn = Message.get_db()
        c = conn.cursor()
        updates = []
        params = []
        if title is not None:
            updates.append('title = ?')
            params.append(title)
        if content is not None:
            updates.append('content = ?')
            params.append(content)
        if category_id is not None:
            updates.append('category_id = ?')
            params.append(category_id)
        if tags is not None:
            updates.append('tags = ?')
            params.append(','.join(tags) if tags else '')
        if updates:
            updates.append('updated_at = ?')
            params.append(datetime.now().isoformat())
            params.append(msg_id)
            c.execute(f'UPDATE messages SET {", ".join(updates)} WHERE id = ?', params)
            conn.commit()
        conn.close()
        return True

    @staticmethod
    def delete(msg_id):
        conn = Message.get_db()
        c = conn.cursor()
        c.execute('UPDATE messages SET is_deleted = 1 WHERE id = ?', (msg_id,))
        conn.commit()
        affected = c.rowcount
        conn.close()
        return affected > 0

    @staticmethod
    def count_all():
        conn = Message.get_db()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM messages WHERE is_deleted = 0')
        count = c.fetchone()[0]
        conn.close()
        return count

    @staticmethod
    def create_admin(title, content, category_id=None, created_by=None, level='personal', company_id=1):
        """管理员创建话术（简化版）"""
        return Message.create(
            company_id=company_id, title=title or '', content=content,
            level=level, category_id=category_id, user_id=str(created_by) if created_by else None
        )
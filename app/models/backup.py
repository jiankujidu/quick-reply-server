"""备份模型"""
import sqlite3
import os
import zipfile
import json
from datetime import datetime
from config.config import Config

class Backup:
    @staticmethod
    def get_db():
        return sqlite3.connect(Config.DATABASE)

    @staticmethod
    def init_db():
        conn = Backup.get_db()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                version INTEGER DEFAULT 3,
                message_count INTEGER DEFAULT 0,
                description TEXT DEFAULT '',
                is_auto INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.commit()
        conn.close()

    @staticmethod
    def create(user_id, uploaded_file, description='', is_auto=0):
        import uuid
        conn = Backup.get_db()
        c = conn.cursor()
        backup_id = str(uuid.uuid4())
        filename = f"{backup_id}.zip"
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

        uploaded_file.save(filepath)
        file_size = os.path.getsize(filepath)

        # 解析备份信息
        message_count = 0
        version = 3
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                if 'data.json' in zf.namelist():
                    data = json.loads(zf.read('data.json').decode('utf-8'))
                    version = data.get('version', 3)
                    message_count = len(data.get('messages', []))
        except Exception:
            pass

        created_at = datetime.now().isoformat()
        c.execute(
            'INSERT INTO backups (id, user_id, filename, file_path, file_size, version, message_count, description, is_auto, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (backup_id, user_id, filename, filepath, file_size, version, message_count, description, is_auto, created_at)
        )
        conn.commit()
        conn.close()
        return {
            'id': backup_id, 'filename': filename, 'file_size': file_size,
            'version': version, 'message_count': message_count, 'created_at': created_at
        }

    @staticmethod
    def get_by_user(user_id, page=1, page_size=20):
        conn = Backup.get_db()
        c = conn.cursor()
        offset = (page - 1) * page_size
        c.execute(
            'SELECT id, filename, file_size, version, message_count, description, is_auto, created_at FROM backups WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (user_id, page_size, offset)
        )
        rows = c.fetchall()
        c.execute('SELECT COUNT(*) FROM backups WHERE user_id = ?', (user_id,))
        total = c.fetchone()[0]
        conn.close()
        return {
            'items': [{'id': r[0], 'filename': r[1], 'file_size': r[2], 'version': r[3],
                       'message_count': r[4], 'description': r[5], 'is_auto': r[6], 'created_at': r[7]} for r in rows],
            'total': total, 'page': page, 'page_size': page_size
        }

    @staticmethod
    def get_by_id(backup_id, user_id):
        conn = Backup.get_db()
        c = conn.cursor()
        c.execute(
            'SELECT id, filename, file_path, file_size, version, message_count, created_at FROM backups WHERE id = ? AND user_id = ?',
            (backup_id, user_id)
        )
        row = c.fetchone()
        conn.close()
        if row:
            return {
                'id': row[0], 'filename': row[1], 'file_path': row[2],
                'file_size': row[3], 'version': row[4], 'message_count': row[5], 'created_at': row[6]
            }
        return None

    @staticmethod
    def get_latest(user_id):
        conn = Backup.get_db()
        c = conn.cursor()
        c.execute(
            'SELECT id, filename, file_path, file_size, version, message_count, created_at FROM backups WHERE user_id = ? ORDER BY created_at DESC LIMIT 1',
            (user_id,)
        )
        row = c.fetchone()
        conn.close()
        if row:
            return {
                'id': row[0], 'filename': row[1], 'file_path': row[2],
                'file_size': row[3], 'version': row[4], 'message_count': row[5], 'created_at': row[6]
            }
        return None

    @staticmethod
    def delete(backup_id, user_id):
        conn = Backup.get_db()
        c = conn.cursor()
        backup = Backup.get_by_id(backup_id, user_id)
        if not backup:
            conn.close()
            return False
        # 删除文件
        if os.path.exists(backup['file_path']):
            os.remove(backup['file_path'])
        c.execute('DELETE FROM backups WHERE id = ?', (backup_id,))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def get_stats(user_id):
        conn = Backup.get_db()
        c = conn.cursor()
        c.execute(
            'SELECT COUNT(*), COALESCE(SUM(file_size), 0), COALESCE(MAX(created_at), "") FROM backups WHERE user_id = ?',
            (user_id,)
        )
        row = c.fetchone()
        c.execute('SELECT COALESCE(SUM(message_count), 0) FROM backups WHERE user_id = ?', (user_id,))
        total_msgs = c.fetchone()[0]
        conn.close()
        return {
            'backup_count': row[0] or 0,
            'total_size': row[1] or 0,
            'total_messages': total_msgs,
            'latest_backup': row[2]
        }
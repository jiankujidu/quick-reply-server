"""备份服务"""
from app.models.backup import Backup

class BackupService:
    @staticmethod
    def upload(user_id, file, description='', is_auto=0):
        return Backup.create(user_id, file, description, is_auto)

    @staticmethod
    def get_list(user_id, page=1, page_size=20):
        return Backup.get_by_user(user_id, page, page_size)

    @staticmethod
    def get_latest(user_id):
        return Backup.get_latest(user_id)

    @staticmethod
    def get_by_id(backup_id, user_id):
        return Backup.get_by_id(backup_id, user_id)

    @staticmethod
    def delete_backup(backup_id, user_id):
        return Backup.delete(backup_id, user_id)

    @staticmethod
    def get_stats(user_id):
        return Backup.get_stats(user_id)
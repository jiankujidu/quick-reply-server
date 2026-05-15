# 配置文件
import os

class Config:
    # 服务器配置
    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'quick-reply-secret-key-2026')

    # 数据库配置
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATABASE = os.path.join(BASE_DIR, 'quickreply_server.db')

    # 上传配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'backups')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = {'zip'}

    # 分页配置
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # 速率限制
    RATELIMIT_DEFAULT = "200 per day"
# 快回复后端服务器 - 完整生产级版本
# Python Flask + SQLite | 模块化架构

import os
from app.main import app
from config.config import Config

# 静态文件目录（项目根目录）
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/admin')
def admin_page():
    """管理后台页面"""
    try:
        with open(os.path.join(STATIC_DIR, 'admin.html'), 'r', encoding='utf-8') as f:
            return f.read(), {'Content-Type': 'text/html; charset=utf-8'}
    except FileNotFoundError:
        return '<h1>404 - 管理后台页面不存在</h1>', 404

if __name__ == '__main__':
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
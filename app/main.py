"""Flask 应用工厂"""
from flask import Flask, jsonify
from flask_cors import CORS
from config.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化所有数据库表
    from app.models.user import User
    from app.models.backup import Backup
    from app.models.company import Company
    from app.models.department import Department
    from app.models.category import Category
    from app.models.message import Message
    
    User.init_db()
    Backup.init_db()
    Company.init_db()
    Department.init_db()
    Category.init_db()
    Message.init_db()

    # CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册蓝图
    from app.api.auth import auth_bp
    from app.api.backup import backup_bp
    from app.api.company import company_bp
    from app.api.department import dept_bp
    from app.api.category import cat_bp
    from app.api.message import msg_bp
    from app.api.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(company_bp)
    app.register_blueprint(dept_bp)
    app.register_blueprint(cat_bp)
    app.register_blueprint(msg_bp)
    app.register_blueprint(admin_bp)

    # 健康检查
    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'quick-reply-server', 'version': '1.1.0'})

    # 全局错误处理
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'code': 4040, 'message': '接口不存在'}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'code': 5000, 'message': '服务器内部错误'}), 500

    return app

app = create_app()
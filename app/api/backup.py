"""备份接口"""
from flask import Blueprint, request, jsonify, send_file
from app.services.backup_service import BackupService
from app.api.auth_decorator import require_auth

backup_bp = Blueprint('backup', __name__, url_prefix='/api/backup')

@backup_bp.route('/upload', methods=['POST'])
@require_auth
def upload(user_id):
    if 'file' not in request.files:
        return jsonify({'code': 4002, 'message': '没有文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 4002, 'message': '没有选择文件'}), 400
    description = request.form.get('description', '')
    result = BackupService.upload(user_id, file, description)
    return jsonify({'code': 0, 'message': '上传成功', 'data': result})

@backup_bp.route('/list', methods=['GET'])
@require_auth
def list_backups(user_id):
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    result = BackupService.get_list(user_id, page, page_size)
    return jsonify({'code': 0, 'message': '获取成功', 'data': result})

@backup_bp.route('/latest', methods=['GET'])
@require_auth
def latest_backup(user_id):
    result = BackupService.get_latest(user_id)
    if result:
        return jsonify({'code': 0, 'message': '获取成功', 'data': result})
    return jsonify({'code': 4041, 'message': '暂无备份'}), 404

@backup_bp.route('/download', methods=['GET'])
@require_auth
def download(user_id):
    backup_id = request.args.get('backup_id')
    if backup_id:
        result = BackupService.get_by_id(backup_id, user_id)
    else:
        result = BackupService.get_latest(user_id)
    if not result:
        return jsonify({'code': 4041, 'message': '备份不存在'}), 404
    import os
    if not os.path.exists(result['file_path']):
        return jsonify({'code': 4042, 'message': '文件不存在'}), 404
    return send_file(result['file_path'], as_attachment=True, download_name='quickreply_backup.zip')

@backup_bp.route('/delete', methods=['DELETE'])
@require_auth
def delete_backup(user_id):
    backup_id = request.args.get('backup_id')
    if not backup_id:
        return jsonify({'code': 4002, 'message': '缺少备份ID'}), 400
    ok = BackupService.delete_backup(backup_id, user_id)
    if ok:
        return jsonify({'code': 0, 'message': '删除成功'})
    return jsonify({'code': 4041, 'message': '备份不存在'}), 404

@backup_bp.route('/stats', methods=['GET'])
@require_auth
def stats(user_id):
    result = BackupService.get_stats(user_id)
    return jsonify({'code': 0, 'message': '获取成功', 'data': result})
# 快回复后端服务器 v2.0 - 精简版

单文件 Flask 服务，只做备份上传/下载，无需注册。

## 功能

- ✅ 密码登录（默认密码：`admin123`）
- ✅ 备份上传/下载/列表/删除
- ✅ 单文件部署，零依赖（除 Flask）

## 快速启动

```bash
pip install flask flask-cors
python server.py
```

Windows 双击 `start.bat`

## API 接口

### 登录
```
POST /api/auth/login
Body: {"password": "admin123"}
Response: {"code": 0, "data": {"token": "admin123"}}
```

### 上传备份
```
POST /api/backup/upload
Header: X-Password: admin123
file: <zip文件>
Response: {"code": 0, "data": {"id": "...", "file_size": 12345}}
```

### 备份列表
```
GET /api/backup/list?page=1&page_size=20
Header: X-Password: admin123
```

### 最新备份
```
GET /api/backup/latest
Header: X-Password: admin123
```

### 下载备份
```
GET /api/backup/download?id=<backup_id>
Header: X-Password: admin123
Response: ZIP 文件流
```

### 删除备份
```
DELETE /api/backup/delete?id=<backup_id>
Header: X-Password: admin123
```

## 配置

修改 `server.py` 中的：
- `ADMIN_PASSWORD` - 登录密码
- `PORT` - 端口号（默认 5000）

## 部署到云服务器

1. 上传整个文件夹到服务器
2. `pip install flask flask-cors`
3. `python server.py`
4. 或用 gunicorn: `gunicorn -w 2 -b 0.0.0.0:5000 server:app`

## 目录结构

```
quick-reply-server/
├── server.py          # 主程序（单文件）
├── start.bat          # Windows 启动脚本
├── requirements.txt   # 依赖
├── backups/           # 备份存储目录（自动创建）
└── quickreply.db     # 数据库（自动创建）
```

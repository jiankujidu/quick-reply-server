#!/usr/bin/env python3
"""
快回复后端 - 登录问题修复工具
2026-05-12 修复版

关键发现：
1. 数据库名: quickreply_server.db (不是 app.db!)
2. 密码哈希: SHA256 (不是 Werkzeug pbkdf2!)
3. 用户名: 19920410 (不是 admin!)

此脚本会：
1. 连接到正确的数据库
2. 显示所有用户
3. 重置指定用户的密码（使用正确的SHA256哈希）
"""

import os
import sys
import sqlite3
import hashlib

# ============================================================
# 配置（与后端 config.py 一致）
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'quickreply_server.db')

DEFAULT_PASSWORD = '123456'

def sha256_hash(password):
    """与后端 AuthService._hash_password 完全一致的哈希方式"""
    return hashlib.sha256(password.encode()).hexdigest()

def print_sep(char='='):
    print(char * 70)

def main():
    print_sep()
    print("  快回复后端 - 登录问题修复工具")
    print("  (使用正确的SHA256哈希 + 正确的数据库名)")
    print_sep()
    print()
    
    # 第1步：确认数据库
    print(f"📂 数据库路径: {DATABASE}")
    
    if not os.path.exists(DATABASE):
        print(f"❌ 数据库文件不存在!")
        print(f"\n当前目录文件:")
        for f in os.listdir(BASE_DIR):
            if f.endswith('.db'):
                print(f"  - {f} ({os.path.getsize(os.path.join(BASE_DIR, f))} bytes)")
        input("\n按回车退出...")
        sys.exit(1)
    
    db_size = os.path.getsize(DATABASE)
    print(f"✅ 数据库存在，大小: {db_size} bytes")
    print()
    
    # 第2步：连接并诊断
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # 检查表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"📊 数据库表: {tables}")
    
    if 'users' not in tables:
        print("❌ users 表不存在!")
        input("\n按回车退出...")
        sys.exit(1)
    
    # 检查users表结构
    cursor.execute("PRAGMA table_info(users)")
    columns = [(r[1], r[2]) for r in cursor.fetchall()]
    print(f"\n📝 users 表结构:")
    for col_name, col_type in columns:
        print(f"  - {col_name} ({col_type})")
    
    # 第3步：列出所有用户
    print()
    print_sep('-')
    print("  所有用户列表")
    print_sep('-')
    
    cursor.execute("SELECT id, username, password, role, is_active FROM users ORDER BY created_at")
    users = cursor.fetchall()
    
    if not users:
        print("❌ 数据库中没有用户！需要先注册。")
        
        # 提示创建默认管理员
        print("\n是否要创建默认管理员？")
        create = input("输入 y 创建 admin/123456: ").strip().lower()
        if create == 'y':
            import uuid
            from datetime import datetime
            user_id = str(uuid.uuid4())
            hashed = sha256_hash(DEFAULT_PASSWORD)
            now = datetime.now().isoformat()
            cursor.execute(
                '''INSERT INTO users (id, username, password, role, email, wechat_id, created_at, is_active) 
                   VALUES (?, ?, ?, ?, '', '', ?, 1)''',
                (user_id, 'admin', hashed, 'admin', now)
            )
            conn.commit()
            print(f"\n✅ 已创建管理员:")
            print(f"   用户名: admin")
            print(f"   密码: {DEFAULT_PASSWORD}")
            print(f"   ID: {user_id}")
        else:
            conn.close()
            input("\n按回车退出...")
            sys.exit(1)
    else:
        print(f"共 {len(users)} 个用户:\n")
        for i, u in enumerate(users):
            uid, uname, upwd, role, active = u
            status = "✅" if active else "❌禁用"
            pwd_preview = upwd[:20] + "..." if len(upwd) > 20 else upwd
            print(f"  [{i+1}] {status} 用户名: {uname} | 角色: {role} | 密码哈希: {pwd_preview}")
            print(f"      ID: {uid}")
    
    # 第4步：选择要重置的用户
    print()
    target = input("请输入要重置密码的用户名（直接回车重置所有活跃用户）: ").strip()
    
    if not target:
        # 重置所有活跃用户
        new_password = input(f"请输入新密码（直接回车使用 '{DEFAULT_PASSWORD}'）: ").strip() or DEFAULT_PASSWORD
        confirm = input("确认密码: ").strip()
        if new_password != confirm:
            print("❌ 密码不匹配")
            conn.close()
            sys.exit(1)
        
        hashed = sha256_hash(new_password)
        cursor.execute("UPDATE users SET password=? WHERE is_active=1", (hashed,))
        count = cursor.rowcount
        conn.commit()
        print(f"\n✅ 已重置 {count} 个用户的密码为: {new_password}")
        
    else:
        # 重置指定用户
        cursor.execute("SELECT id, username FROM users WHERE username=?", (target,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ 未找到用户: {target}")
            conn.close()
            input("\n按回车退出...")
            sys.exit(1)
        
        new_password = input(f"请输入新密码（直接回车使用 '{DEFAULT_PASSWORD}'）: ").strip() or DEFAULT_PASSWORD
        confirm = input("确认密码: ").strip()
        if new_password != confirm:
            print("❌ 密码不匹配")
            conn.close()
            sys.exit(1)
        
        hashed = sha256_hash(new_password)
        cursor.execute("UPDATE users SET password=? WHERE username=?", (hashed, target))
        conn.commit()
        print(f"\n✅ 已重置用户 '{target}' 的密码为: {new_password}")
    
    # 验证
    print()
    print("🔍 验证登录...")
    test_user = target if target else (users[0][1] if users else 'admin')
    test_pwd = new_password if 'new_password' in dir() else DEFAULT_PASSWORD
    test_hash = sha256_hash(test_pwd)
    
    cursor.execute("SELECT id, username FROM users WHERE username=? AND password=?", (test_user, test_hash))
    verified = cursor.fetchone()
    
    if verified:
        print(f"✅ 验证通过！用户 {test_user} 可以使用密码 {test_pwd} 登录")
    else:
        print(f"❌ 验证失败！")
    
    conn.close()
    
    print()
    print_sep()
    print("  ✅ 修复完成！")
    print_sep()
    print(f"\n请在App中使用以下凭据登录：")
    print(f"  用户名: {test_user}")
    print(f"  密码: {test_pwd}")
    print(f"\n服务器地址: http://100.66.1.3:5000")
    print(f"\n⚠️  如果仍然报错 'Null is not a subtype of Map'，")
    print(f"     那是Flutter端解析问题，不是密码问题。")

if __name__ == '__main__':
    main()

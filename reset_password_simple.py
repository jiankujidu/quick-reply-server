#!/usr/bin/env python3
"""
快回复后端 - 密码重置工具（简单版）
使用方法：
1. 双击运行，或命令行：python reset_password_simple.py
2. 输入新密码（直接回车使用 admin123）
"""

import os
import sys
import sqlite3
from werkzeug.security import generate_password_hash

# 配置
DEFAULT_PASSWORD = 'admin123'
DB_PATH = 'app.db'  # 假设数据库在当前目录

def print_sep(char='='):
    print(char * 60)

def reset_password():
    print_sep()
    print("  快回复 - 管理员密码重置")
    print_sep()
    print()
    
    # 检查数据库文件
    if not os.path.exists(DB_PATH):
        print(f"❌ 未找到数据库文件: {DB_PATH}")
        print(f"\n当前目录: {os.getcwd()}")
        print(f"请确认：")
        print(f"  1. 此脚本在 quick-reply-server 文件夹中")
        print(f"  2. 存在 app.db 文件")
        input("\n按回车键退出...")
        sys.exit(1)
    
    print(f"✅ 找到数据库: {DB_PATH}")
    
    # 连接数据库
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查users表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("❌ 数据库中不存在 users 表")
            conn.close()
            input("\n按回车键退出...")
            sys.exit(1)
        
        # 查找admin用户
        cursor.execute("SELECT id, username FROM users WHERE username='admin'")
        user = cursor.fetchone()
        
        if not user:
            print("❌ 未找到 admin 用户")
            print("\n所有用户：")
            cursor.execute("SELECT username FROM users")
            for row in cursor.fetchall():
                print(f"  - {row[0]}")
            conn.close()
            input("\n按回车键退出...")
            sys.exit(1)
        
        print(f"✅ 找到用户: admin (ID: {user[0]})")
        
        # 获取新密码
        print()
        new_password = input(f"请输入新密码（直接回车使用 '{DEFAULT_PASSWORD}'）: ").strip()
        if not new_password:
            new_password = DEFAULT_PASSWORD
            print(f"✅ 使用默认密码: {DEFAULT_PASSWORD}")
        
        # 确认密码
        confirm = input("确认密码: ").strip()
        if new_password != confirm:
            print("❌ 密码不匹配")
            input("\n按回车键退出...")
            sys.exit(1)
        
        # 生成密码哈希
        print(f"\n🔐 正在生成密码哈希...")
        new_hash = generate_password_hash(new_password)
        
        # 更新密码
        cursor.execute("UPDATE users SET password=? WHERE username='admin'", (new_hash,))
        conn.commit()
        
        print(f"✅ 密码已更新")
        print()
        print_sep()
        print("  ✅ 密码重置成功！")
        print_sep()
        print(f"\n请使用以下凭据登录：")
        print(f"  用户名: admin")
        print(f"  密码: {new_password}")
        print(f"\n⚠️  请注意：")
        print(f"  1. 如果Flask服务器正在运行，请重启它")
        print(f"  2. 清除浏览器缓存后再试")
        print(f"  3. 访问: http://100.66.1.3:5000/admin")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        input("\n按回车键退出...")
        sys.exit(1)
    
    input("\n按回车键退出...")

if __name__ == '__main__':
    reset_password()

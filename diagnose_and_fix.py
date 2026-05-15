#!/usr/bin/env python3
"""
快回复后端 - 诊断并修复登录问题
使用方法：python diagnose_and_fix.py
"""

import os
import sys
import sqlite3

def print_sep(char='='):
    print(char * 70)

def print_section(title):
    print()
    print_sep('-')
    print(f"  {title}")
    print_sep('-')
    print()

def main():
    print_sep()
    print("  快回复后端 - 诊断并修复登录问题")
    print_sep()
    print()
    print("此脚本将：")
    print("  1. 诊断数据库和用户信息")
    print("  2. 显示详细的问题信息")
    print("  3. 提供针对性的修复方案")
    print()
    input("按回车键开始诊断...")
    print()
    
    # ============================================================
    # 第1步：查找数据库
    # ============================================================
    print_section("第1步：查找数据库")
    
    db_paths = [
        'app.db',
        'instance/app.db',
        '../app.db',
        'database/app.db',
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            print(f"✅ 找到数据库: {path}")
            break
    
    if not db_path:
        print("❌ 未找到数据库文件！")
        print("\n当前目录:", os.getcwd())
        print("\n目录中的文件:")
        for f in os.listdir('.'):
            if f.endswith('.db') or 'db' in f.lower():
                print(f"  - {f}")
        print("\n💡 解决方案:")
        print("  1. 请确认此脚本在 quick-reply-server 文件夹中")
        print("  2. 如果数据库在其他位置，请修改脚本")
        input("\n按回车键退出...")
        sys.exit(1)
    
    print(f"\n数据库完整路径: {os.path.abspath(db_path)}")
    
    # ============================================================
    # 第2步：连接数据库并诊断
    # ============================================================
    print_section("第2步：连接数据库并诊断")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"✅ 成功连接数据库")
        
        # 检查所有表
        print(f"\n📊 数据库中的表:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if not tables:
            print("  ❌ 数据库中没有表！")
            conn.close()
            input("\n按回车键退出...")
            sys.exit(1)
        
        for table in tables:
            print(f"  - {table[0]}")
        
        # 检查users表
        if 'users' not in [t[0] for t in tables]:
            print(f"\n❌ 数据库中不存在 users 表！")
            print(f"  这可能是一个空数据库，或者表名不同")
            conn.close()
            input("\n按回车键退出...")
            sys.exit(1)
        
        print(f"\n✅ 找到 users 表")
        
        # 检查users表结构
        print(f"\n📝 users 表结构:")
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # 检查所有用户
        print(f"\n👥 所有用户:")
        cursor.execute("SELECT id, username, email FROM users")
        users = cursor.fetchall()
        
        if not users:
            print("  ❌ 没有用户！")
            print(f"\n💡 需要创建 admin 用户")
        else:
            for user in users:
                print(f"  - ID: {user[0]}, 用户名: {user[1]}, 邮箱: {user[2] if len(user) > 2 else 'N/A'}")
        
        # 检查admin用户
        print(f"\n🔍 查找 admin 用户:")
        cursor.execute("SELECT id, username, password FROM users WHERE username='admin'")
        admin = cursor.fetchone()
        
        if not admin:
            print("  ❌ 未找到 admin 用户！")
            print(f"\n💡 需要创建 admin 用户")
        else:
            print(f"  ✅ 找到 admin 用户")
            print(f"  ID: {admin[0]}")
            print(f"  用户名: {admin[1]}")
            print(f"  密码哈希: {admin[2][:50]}...")
            
            # 检查密码哈希格式
            if admin[2].startswith('pbkdf2:sha256'):
                print(f"  ✅ 密码哈希格式正确 (Werkzeug pbkdf2)")
            elif admin[2].startswith('$2b$'):
                print(f"  ⚠️  密码哈希格式为 bcrypt (可能需要不同的验证方法)")
            else:
                print(f"  ⚠️  密码哈希格式未知")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ 连接数据库时出错: {e}")
        input("\n按回车键退出...")
        sys.exit(1)
    
    # ============================================================
    # 第3步：提供修复方案
    # ============================================================
    print_section("第3步：修复方案")
    
    if not admin:
        print("📝 方案1: 创建 admin 用户")
        print("  运行: python create_admin.py")
    else:
        print("📝 方案1: 重置 admin 密码")
        print("  运行: python reset_password_simple.py")
        print("\n📝 方案2: 创建新的管理员用户")
        print("  运行: python create_new_admin.py")
    
    print("\n📝 方案3: 检查后端登录代码")
    print("  查看 app/api/auth.py 中的登录逻辑")
    
    # ============================================================
    # 第4步：创建修复脚本
    # ============================================================
    print_section("第4步：创建修复脚本")
    
    create_fix_scripts()
    
    print()
    print_sep()
    print("  ✅ 诊断完成！")
    print_sep()
    print()
    print("请查看上面的诊断信息，然后运行相应的修复脚本。")
    print()
    input("按回车键退出...")

def create_fix_scripts():
    """创建修复脚本"""
    
    # 脚本1: 创建admin用户
    script1 = '''#!/usr/bin/env python3
"""创建 admin 用户"""
import sqlite3
from werkzeug.security import generate_password_hash

db_path = 'app.db'
password = 'admin123'
hash_pw = generate_password_hash(password)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute(
        "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
        ('admin', 'admin@example.com', hash_pw, 'admin')
    )
    conn.commit()
    print("✅ admin 用户创建成功！")
    print(f"   用户名: admin")
    print(f"   密码: {password}")
except Exception as e:
    print(f"❌ 创建用户失败: {e}")
finally:
    conn.close()
'''
    
    with open('create_admin.py', 'w', encoding='utf-8') as f:
        f.write(script1)
    print("✅ 已创建 create_admin.py")
    
    # 脚本2: 重置密码
    script2 = '''#!/usr/bin/env python3
"""重置 admin 密码"""
import sqlite3
from werkzeug.security import generate_password_hash

db_path = 'app.db'
new_password = input("请输入新密码（直接回车使用 admin123）: ").strip() or 'admin123'
new_hash = generate_password_hash(new_password)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("UPDATE users SET password=? WHERE username='admin'", (new_hash,))
    conn.commit()
    print(f"✅ 密码已重置为: {new_password}")
except Exception as e:
    print(f"❌ 重置密码失败: {e}")
finally:
    conn.close()
'''
    
    with open('reset_password_simple.py', 'w', encoding='utf-8') as f:
        f.write(script2)
    print("✅ 已创建 reset_password_simple.py (更新版)")
    
    # 脚本3: 创建新管理员
    script3 = '''#!/usr/bin/env python3
"""创建新的管理员用户"""
import sqlite3
from werkzeug.security import generate_password_hash

db_path = 'app.db'
username = input("请输入新用户名（默认: admin2）: ").strip() or 'admin2'
password = input("请输入密码（默认: admin123）: ").strip() or 'admin123'
email = f"{username}@example.com"
hash_pw = generate_password_hash(password)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute(
        "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
        (username, email, hash_pw, 'admin')
    )
    conn.commit()
    print(f"✅ 新管理员创建成功！")
    print(f"   用户名: {username}")
    print(f"   密码: {password}")
    print(f"\n请使用此账号登录，然后修复 admin 账号")
except Exception as e:
    print(f"❌ 创建用户失败: {e}")
finally:
    conn.close()
'''
    
    with open('create_new_admin.py', 'w', encoding='utf-8') as f:
        f.write(script3)
    print("✅ 已创建 create_new_admin.py")

if __name__ == '__main__':
    main()

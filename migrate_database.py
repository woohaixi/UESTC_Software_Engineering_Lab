"""
数据库迁移脚本
保留现有用户数据，添加新表和字段
"""
import sqlite3
import hashlib
from datetime import datetime

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def migrate_database():
    print("开始数据库迁移...")
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # 1. 检查并添加 users 表的新字段
    print("\n1. 检查 users 表...")
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'role' not in columns:
        print("  - 添加 role 字段...")
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    
    if 'status' not in columns:
        print("  - 添加 status 字段...")
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
    
    if 'last_login' not in columns:
        print("  - 添加 last_login 字段...")
        cursor.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
    
    if 'warning_count' not in columns:
        print("  - 添加 warning_count 字段...")
        cursor.execute("ALTER TABLE users ADD COLUMN warning_count INTEGER DEFAULT 0")
    
    # 移除 phone 字段（SQLite 不支持直接删除列，所以我们保留它）
    if 'phone' in columns:
        print("  - phone 字段已存在（保留）")
    
    # 2. 创建 login_logs 表（如果不存在）
    print("\n2. 检查 login_logs 表...")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='login_logs'
    """)
    if not cursor.fetchone():
        print("  - 创建 login_logs 表...")
        cursor.execute('''
            CREATE TABLE login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                success INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                logout_time TIMESTAMP,
                session_duration INTEGER
            )
        ''')
    else:
        print("  - login_logs 表已存在")
    
    # 3. 迁移旧的 login_attempts 数据到 login_logs
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='login_attempts'
    """)
    if cursor.fetchone():
        print("\n3. 迁移 login_attempts 数据到 login_logs...")
        cursor.execute("""
            INSERT INTO login_logs (username, success, ip_address, login_time)
            SELECT username, success, ip_address, attempt_time
            FROM login_attempts
            WHERE NOT EXISTS (
                SELECT 1 FROM login_logs 
                WHERE login_logs.username = login_attempts.username 
                AND login_logs.login_time = login_attempts.attempt_time
            )
        """)
        migrated = cursor.rowcount
        print(f"  - 已迁移 {migrated} 条记录")
    
    # 4. 创建 qa_records 表（如果不存在）
    print("\n4. 检查 qa_records 表...")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='qa_records'
    """)
    if not cursor.fetchone():
        print("  - 创建 qa_records 表...")
        cursor.execute('''
            CREATE TABLE qa_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                tool_used TEXT,
                confidence_score REAL,
                source_info TEXT,
                review_status TEXT DEFAULT 'pending',
                reviewer TEXT,
                review_comment TEXT,
                review_time TIMESTAMP,
                is_visible INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        print("  - qa_records 表已存在")
        # 检查并添加 is_visible 字段
        cursor.execute("PRAGMA table_info(qa_records)")
        qa_columns = [col[1] for col in cursor.fetchall()]
        if 'is_visible' not in qa_columns:
            print("  - 添加 is_visible 字段到 qa_records...")
            cursor.execute("ALTER TABLE qa_records ADD COLUMN is_visible INTEGER DEFAULT 1")
    
    # 5. 创建 user_warnings 表（如果不存在）
    print("\n5. 检查 user_warnings 表...")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='user_warnings'
    """)
    if not cursor.fetchone():
        print("  - 创建 user_warnings 表...")
        cursor.execute('''
            CREATE TABLE user_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                qa_record_id INTEGER,
                warning_reason TEXT,
                warning_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER DEFAULT 0
            )
        ''')
    else:
        print("  - user_warnings 表已存在")
    
    # 6. 创建默认管理员账户（如果不存在）
    print("\n6. 检查默认账户...")
    cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
    if cursor.fetchone()[0] == 0:
        print("  - 创建管理员账户 (admin/admin123)...")
        cursor.execute('''
            INSERT INTO users (username, password, email, role, status, mfa_enabled)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('admin', hash_password('admin123'), 'admin@system.com', 'admin', 'active', 0))
    else:
        print("  - 管理员账户已存在")
        # 更新现有管理员的角色
        cursor.execute("UPDATE users SET role = 'admin' WHERE username = 'admin'")
    
    # 6. 创建默认审核员账户（如果不存在）
    cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('reviewer',))
    if cursor.fetchone()[0] == 0:
        print("  - 创建审核员账户 (reviewer/reviewer123)...")
        cursor.execute('''
            INSERT INTO users (username, password, email, role, status, mfa_enabled)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('reviewer', hash_password('reviewer123'), 'reviewer@system.com', 'reviewer', 'active', 0))
    else:
        print("  - 审核员账户已存在")
    
    # 7. 显示现有用户列表
    print("\n7. 当前用户列表:")
    cursor.execute('SELECT username, email, role, status, warning_count, created_at FROM users')
    users = cursor.fetchall()
    for user in users:
        username, email, role, status, warning_count, created_at = user
        print(f"  - {username:15} | {email or '未设置':25} | {role:10} | {status:10} | 警告:{warning_count or 0}次 | {created_at}")
    
    conn.commit()
    conn.close()
    
    print("\n✅ 数据库迁移完成！")
    print("\n默认账户:")
    print("  管理员: admin / admin123")
    print("  审核员: reviewer / reviewer123")
    print("\n所有现有用户数据已保留！")

if __name__ == '__main__':
    try:
        migrate_database()
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()

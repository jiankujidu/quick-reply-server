import sqlite3, sys

db = r'C:\Users\Administrator\Desktop\优品生物\quick-reply-server\quickreply_v4.db'
try:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in cur.fetchall()]
    print('Current users columns:', cols)
    if 'email' not in cols:
        cur.execute('ALTER TABLE users ADD COLUMN email TEXT DEFAULT ""')
        conn.commit()
        print('Added email column')
    cur.execute("PRAGMA table_info(tokens)")
    token_cols = [r[1] for r in cur.fetchall()]
    print('Current tokens columns:', token_cols)
    if 'token' not in token_cols:
        cur.execute('ALTER TABLE tokens ADD COLUMN token TEXT')
        conn.commit()
        print('Added token column to tokens')
    # Check data
    cur.execute("SELECT COUNT(*) FROM users")
    print(f'Users: {cur.fetchone()[0]}')
    cur.execute("SELECT COUNT(*) FROM messages")
    print(f'Messages: {cur.fetchone()[0]}')
    cur.execute("SELECT COUNT(*) FROM categories")
    print(f'Categories: {cur.fetchone()[0]}')
    conn.close()
    print('DB check done')
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)

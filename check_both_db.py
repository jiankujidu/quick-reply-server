import sqlite3

for db in [r'D:\quick-reply-server\quickreply_v4.db', r'D:\quick-reply-server\quickreply_server.db']:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT username, password, role FROM users WHERE username='admin'")
    rows = cur.fetchall()
    print(f'{db}:')
    for r in rows:
        print(f'  {r}')
    cur.execute('SELECT COUNT(*) FROM users')
    print(f'  Total users: {cur.fetchone()[0]}')
    conn.close()
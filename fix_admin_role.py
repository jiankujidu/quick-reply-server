import sqlite3

conn = sqlite3.connect('D:/quick-reply-server/quickreply_server.db')
cursor = conn.execute("UPDATE users SET role='admin' WHERE username='admin'")
print(f'Rows updated: {cursor.rowcount}')
conn.commit()
row = conn.execute("SELECT id, username, role FROM users WHERE username='admin'").fetchone()
print(f'Verified: {row}')
conn.close()

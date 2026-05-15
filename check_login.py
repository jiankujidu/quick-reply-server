import sqlite3, hashlib

db_path = r'D:\quick-reply-server\quickreply_v4.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT id, username, password, role, status FROM users WHERE username='admin'")
rows = cur.fetchall()
print("=== Admin user in DB ===")
for r in rows:
    print(f"ID: {r[0]}, Username: {r[1]}, Password: {r[2]}, Role: {r[3]}, Status: {r[4]}")

# Check how password is stored - is it plain text or hashed?
pw_in_db = rows[0][2] if rows else None
if pw_in_db:
    # Try plain text
    print(f"\nPlain text 'admin123' == stored: {pw_in_db == 'admin123'}")
    # Try SHA256
    sha = hashlib.sha256('admin123'.encode()).hexdigest()
    print(f"SHA256('admin123'): {sha[:20]}...")
    print(f"SHA256 match: {pw_in_db == sha}")

conn.close()
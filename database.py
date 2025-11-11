# db.py
import sqlite3
from pathlib import Path
import hashlib, os

DB_PATH = Path(__file__).parent / "co_app.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def table_has_column(table, column):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    conn.close()
    return column in cols

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # users table (add email column support)
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        name TEXT,
        regno TEXT,
        email TEXT,
        password_hash TEXT,
        role TEXT
    )""")
    # marks table
    cur.execute("""CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        internal INTEGER,
        co1_obt REAL, co1_max REAL,
        co2_obt REAL, co2_max REAL,
        co3_obt REAL, co3_max REAL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    # questions
    cur.execute("""CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        co TEXT,
        question TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        answered INTEGER DEFAULT 0,
        FOREIGN KEY(student_id) REFERENCES users(id)
    )""")
    # answers
    cur.execute("""CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER,
        staff_id INTEGER,
        answer TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(question_id) REFERENCES questions(id),
        FOREIGN KEY(staff_id) REFERENCES users(id)
    )""")
    # resources
    cur.execute("""CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER,
        co TEXT,
        title TEXT,
        type TEXT,
        url TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(staff_id) REFERENCES users(id)
    )""")
    # activities
    cur.execute("""CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        activity_type TEXT,
        details TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(student_id) REFERENCES users(id)
    )""")

    conn.commit()
    conn.close()

def hash_password(password, salt="co_app_salt_2025"):
    return hashlib.sha256((password + salt).encode()).hexdigest()

def create_user(username, name, regno, email, password, role="student"):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username,name,regno,email,password_hash,role) VALUES (?,?,?,?,?,?)",
                   (username,name,regno,email, hash_password(password), role))
        conn.commit()
        return True
    except Exception as e:
        print("create_user error:", e)
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    row=cur.fetchone()
    conn.close()
    return row

def get_user_by_id(uid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    row=cur.fetchone()
    conn.close()
    return row

if __name__ == "__main__":
    init_db()
    # create default demo accounts (with emails) if not exists
    if not get_user_by_username("staff1"):
        create_user("staff1","Staff One","STAFF001","staff1@example.com","staffpass", role="staff")
    if not get_user_by_username("student1"):
        create_user("student1","Student One","REG001","student1@example.com","studentpass", role="student")
    print("DB initialized, sample users created.")

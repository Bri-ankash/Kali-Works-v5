import sqlite3
import os

DB_PATH = 'data/smartpochi_backup.db'
os.makedirs('data', exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Existing tables
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fname TEXT, lname TEXT, id_pass TEXT,
        email TEXT, mobile TEXT, password TEXT,
        account_number TEXT, verified INTEGER DEFAULT 0,
        approved INTEGER DEFAULT 0, premium INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0,
        two_fa_enabled INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admin_sessions (
        token TEXT PRIMARY KEY, created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT, timestamp TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS csv_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER, filename TEXT,
        uploaded_at TEXT, analysis TEXT
    )''')

    # NEW TABLES
    c.execute('''CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER, title TEXT,
        target_amount REAL, current_amount REAL DEFAULT 0,
        period TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER, name TEXT,
        amount_owed REAL DEFAULT 0,
        due_date TEXT, status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS staff_salaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER, staff_name TEXT,
        amount REAL, paid_date TEXT,
        status TEXT DEFAULT 'paid',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS float_tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER, float_amount REAL,
        alert_threshold REAL DEFAULT 1000,
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS otp_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER, code TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print('Database initialized!')

import psycopg2
import os

DB_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id SERIAL PRIMARY KEY,
        fname TEXT, lname TEXT, id_pass TEXT,
        email TEXT UNIQUE, mobile TEXT UNIQUE,
        password TEXT, account_number TEXT,
        verified INTEGER DEFAULT 0,
        approved INTEGER DEFAULT 0,
        premium INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0,
        two_fa_enabled INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admin_sessions (
        token TEXT PRIMARY KEY, created_at TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        action TEXT, timestamp TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS csv_uploads (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, filename TEXT,
        uploaded_at TEXT, analysis TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS goals (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, title TEXT,
        target_amount REAL, current_amount REAL DEFAULT 0,
        period TEXT, created_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS suppliers (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, name TEXT,
        amount_owed REAL DEFAULT 0,
        due_date TEXT, status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS staff_salaries (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, staff_name TEXT,
        amount REAL, paid_date TEXT,
        status TEXT DEFAULT 'paid',
        created_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS float_tracker (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, float_amount REAL,
        alert_threshold REAL DEFAULT 1000,
        recorded_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS otp_codes (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, code TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS budgets (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, category TEXT,
        budget_amount REAL, spent_amount REAL DEFAULT 0,
        month TEXT, created_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, invoice_number TEXT,
        client_name TEXT, client_email TEXT,
        items TEXT, total REAL, status TEXT DEFAULT 'unpaid',
        created_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS net_worth (
        id SERIAL PRIMARY KEY,
        client_id INTEGER,
        assets REAL DEFAULT 0,
        liabilities REAL DEFAULT 0,
        recorded_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, name TEXT,
        phone TEXT, email TEXT,
        amount_owed REAL DEFAULT 0,
        notes TEXT, status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT NOW()
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS loans (
        id SERIAL PRIMARY KEY,
        client_id INTEGER, lender TEXT,
        principal REAL, interest_rate REAL,
        months INTEGER, start_date TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )''')

    conn.commit()
    conn.close()
    print("Database initialized!")

if __name__ == '__main__':
    init_db()

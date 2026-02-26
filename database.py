import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "kaliworks.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Clients
    c.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fname TEXT,
        lname TEXT,
        email TEXT UNIQUE,
        mobile TEXT,
        password TEXT,
        account_number TEXT UNIQUE,
        verified INTEGER DEFAULT 0,
        approved INTEGER DEFAULT 0,
        premium INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0,
        failed_attempts INTEGER DEFAULT 0,
        locked_until TEXT,
        created_at TEXT
    )
    """)

    # Email verification tokens
    c.execute("""
    CREATE TABLE IF NOT EXISTS email_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        token TEXT,
        expires_at TEXT
    )
    """)

    # Admin sessions
    c.execute("""
    CREATE TABLE IF NOT EXISTS admin_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT,
        expires_at TEXT
    )
    """)

    # Admin 2FA codes
    c.execute("""
    CREATE TABLE IF NOT EXISTS admin_2fa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        code TEXT,
        expires_at TEXT
    )
    """)

    # CSV uploads
    c.execute("""
    CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        filename TEXT,
        uploaded_at TEXT
    )
    """)

    conn.commit()
    conn.close()

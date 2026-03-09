# ================================
# Kali Works V5 – Production SaaS
# ================================

import os
import sqlite3
import secrets
import hashlib
import smtplib
import random
import csv
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from collections import defaultdict

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

import os

# Ensure folder exists
os.makedirs("data/uploads", exist_ok=True)

# Update database path
DB_PATH = 'data/kaliworks_backup.db'

# Update upload folder path
UPLOAD_FOLDER = 'data/uploads'


# ------------------------
# CONFIG
# ------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = 'data/kaliworks_backup.db'
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_APP_PASSWORD = os.getenv("ADMIN_APP_PASSWORD")
ADMIN_2FA_ENABLED = True  # FIXED: mandatory 2FA for admin
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SESSION_EXPIRY_MINUTES = 30

admin_2fa_codes = {}

# ------------------------
# DATABASE INIT
# ------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fname TEXT,
        lname TEXT,
        id_pass TEXT,
        email TEXT UNIQUE,
        mobile TEXT,
        password TEXT,
        account_number TEXT UNIQUE,
        verified INTEGER DEFAULT 0,
        approved INTEGER DEFAULT 0,
        premium INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS admin_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        timestamp TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS csv_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        filename TEXT,
        uploaded_at TEXT,
        analysis TEXT,
        FOREIGN KEY(client_id) REFERENCES clients(id)
    )""")
    conn.commit()
    conn.close()

init_db()

# ------------------------
# UTILITIES
# ------------------------
def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def send_email(to_email: str, subject: str, body_html: str):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = ADMIN_EMAIL
        msg['To'] = to_email
        msg.set_content("This email requires HTML support.")
        msg.add_alternative(body_html, subtype='html')
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(ADMIN_EMAIL, ADMIN_APP_PASSWORD)
            server.send_message(msg)
        print(f"[DEBUG] Email sent to {to_email}")
    except Exception as e:
        print("Email error:", e)

def log_action(action: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO audit_logs (action, timestamp) VALUES (?, ?)", (action, str(datetime.now())))
    conn.commit()
    conn.close()

def create_admin_session():
    token = secrets.token_hex(16)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO admin_sessions (token, created_at) VALUES (?, ?)", (token, str(datetime.now())))
    conn.commit()
    conn.close()
    return token

def verify_admin_session(token: str):
    if not token:
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT created_at FROM admin_sessions WHERE token=?", (token,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    created_at = datetime.fromisoformat(row[0])
    return datetime.now() - created_at < timedelta(minutes=SESSION_EXPIRY_MINUTES)

# ------------------------
# LIGHTWEIGHT CSV ANALYSIS ENGINE
# ------------------------
def analyze_csv(file_path: str):
    result = {
        "money_in": 0.0,
        "money_out": 0.0,
        "profit_loss": 0.0,
        "top_consumers": {},
        "money_leaks": []
    }
    consumers = defaultdict(float)
    try:
        with open(file_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                amt = float(row.get("Amount", 0))
                desc = row.get("Description", "").lower()
                if amt > 0:
                    result["money_in"] += amt
                else:
                    result["money_out"] += abs(amt)
                    if any(flag in desc for flag in ["bet", "gamble", "casino"]):
                        result["money_leaks"].append({"desc": desc, "amt": abs(amt)})
                consumer = row.get("Sender", row.get("Receiver", "Unknown"))
                consumers[consumer] += abs(amt)
        result["top_consumers"] = dict(sorted(consumers.items(), key=lambda x: x[1], reverse=True)[:5])
        result["profit_loss"] = result["money_in"] - result["money_out"]
    except Exception as e:
        print("[DEBUG] CSV analysis error:", e)
    return result

# ------------------------
# ROUTES: LANDING / REGISTER / LOGIN
# ------------------------
@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/register_page", response_class=HTMLResponse)
def show_register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/login_page", response_class=HTMLResponse)
def show_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/admin_login_page", response_class=HTMLResponse)
def show_admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

# ------------------------
# REGISTRATION & EMAIL VERIFICATION
# ------------------------
@app.post("/register")
def register(
    request: Request,
    fname: str = Form(...),
    lname: str = Form(...),
    id_pass: str = Form(...),
    email: str = Form(...),
    mobile: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Passwords do not match"})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM clients WHERE email=?", (email,))
    if c.fetchone():
        conn.close()
        return templates.TemplateResponse(
            "registration_pending.html",
            {"request": request, "message": "Already registered. Wait for admin approval."}
        )
    hashed = hash_password(password)
    c.execute(
        """INSERT INTO clients (fname,lname,id_pass,email,mobile,password)
           VALUES (?,?,?,?,?,?)""",
        (fname, lname, id_pass, email, mobile, hashed)
    )
    conn.commit()
    conn.close()

    verify_link = f"http://localhost:8000/confirm_email?email={email}"
    email_html = f"""<html><body>
      <h2>Welcome to Kali Works!</h2>
      <p>Click below to confirm your email:</p>
      <a href="{verify_link}" style="padding:10px 20px;background-color:green;color:white;text-decoration:none;">Confirm Email</a>
    </body></html>"""
    send_email(email, "Confirm your Kali Works account", email_html)
    return templates.TemplateResponse(
        "registration_pending.html",
        {"request": request, "message": "Status Pending. Check your email to verify."}
    )

@app.get("/confirm_email", response_class=HTMLResponse)
def confirm_email_page(request: Request, email: str):
    return templates.TemplateResponse("verify_page.html", {"request": request, "email": email})

@app.post("/confirm_email")
def confirm_email(request: Request, email: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE clients SET verified=1 WHERE email=?", (email,))
    conn.commit()
    conn.close()
    return templates.TemplateResponse(
        "registration_pending.html",
        {"request": request, "message": "Email Verified ✅. Waiting for admin approval."}
    )

# ------------------------
# CLIENT LOGIN & DASHBOARD
# ------------------------
@app.post("/client_login")
def client_login(request: Request, account_number: str = Form(...), password: str = Form(...)):
    hashed = hash_password(password)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, approved, blocked, premium FROM clients WHERE account_number=? AND password=? AND verified=1",
        (account_number, hashed)
    )
    user = c.fetchone()
    conn.close()
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials or not approved."})
    if user[1] != 1:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Awaiting admin approval."})
    if user[2] == 1:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Account blocked."})
    client_id, _, _, premium = user
    response = RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)
    response.set_cookie(key="client_id", value=str(client_id))
    response.set_cookie(key="premium", value=str(premium))
    return response

@app.get("/client_dashboard/{client_id}", response_class=HTMLResponse)
def client_dashboard(request: Request, client_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # FIXED: fetch all relevant fields
    c.execute("SELECT fname,lname,premium,account_number FROM clients WHERE id=?", (client_id,))
    user = c.fetchone()
    conn.close()
    if not user:
        return RedirectResponse("/")
    fname, lname, premium, account_number = user

    # Retrieve uploaded CSVs
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT filename, analysis, uploaded_at FROM csv_uploads WHERE client_id=? ORDER BY uploaded_at DESC",
        (client_id,)
    )
    uploads = c.fetchall()
    conn.close()

    return templates.TemplateResponse("client_dashboard.html", {
        "request": request,
        "client_id": client_id,
        "fname": fname,
        "lname": lname,
        "premium": premium,
        "account_number": account_number,
        "uploads": uploads,
        "panda_assistant_enabled": True  # FIXED: always show Panda
    })

# ------------------------
# CSV UPLOAD
# ------------------------
@app.post("/upload_csv")
def upload_csv(request: Request, client_id: int = Form(...), file: UploadFile = File(...)):
    filename = f"{client_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    analysis = analyze_csv(str(file_path))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO csv_uploads (client_id, filename, uploaded_at, analysis) VALUES (?,?,?,?)",
        (client_id, filename, str(datetime.now()), str(analysis))
    )
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ------------------------
# ADMIN LOGIN & 2FA
# ------------------------
@app.get("/admin_login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin_login", response_class=HTMLResponse)
def admin_login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Invalid credentials"})
    # FIXED: 2FA mandatory
    code = str(random.randint(100000, 999999))
    admin_2fa_codes[username] = code
    email_html = f"<p>Your KaliWorks admin 2FA code is: <b>{code}</b></p>"
    send_email(ADMIN_EMAIL, "KaliWorks Admin 2FA Verification", email_html)
    return templates.TemplateResponse("admin_2fa.html", {"request": request, "username": username})

@app.post("/admin_2fa_verify", response_class=HTMLResponse)
def admin_2fa_verify_post(request: Request, username: str = Form(...), code: str = Form(...)):
    expected_code = admin_2fa_codes.get(username)
    if expected_code != code:
        return templates.TemplateResponse("admin_2fa.html", {"request": request, "username": username, "error": "Incorrect code"})
    admin_2fa_codes.pop(username, None)
    token = create_admin_session()
    response = RedirectResponse("/admin_dashboard", status_code=303)
    response.set_cookie("admin_session", token)
    return response

# ------------------------
# ADMIN DASHBOARD & ACTIONS
# ------------------------
@app.get("/admin_dashboard", response_class=HTMLResponse)
def admin_dashboard_page(request: Request):
    token = request.cookies.get("admin_session")
    if not verify_admin_session(token):
        return RedirectResponse("/admin_login_page")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM clients")
    total_clients = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clients WHERE premium=1")
    premium_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clients WHERE blocked=1")
    blocked_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clients WHERE verified=1")
    verified_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clients WHERE approved=0 AND verified=1")
    pending_count = c.fetchone()[0]
    c.execute("SELECT * FROM clients WHERE approved=0 AND verified=1")
    new_regs = c.fetchall()
    c.execute("SELECT * FROM clients WHERE approved=1")
    approved_clients = c.fetchall()
    conn.close()

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "total_clients": total_clients,
        "premium_count": premium_count,
        "blocked_count": blocked_count,
        "verified_count": verified_count,
        "pending_count": pending_count,
        "new_regs": new_regs,
        "approved_clients": approved_clients
    })

# ------------------------
# APPROVE CLIENT
# ------------------------
@app.post("/approve_client")
def approve_client(client_id: int = Form(...), account_number: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE clients SET approved=1, account_number=? WHERE id=?", (account_number, client_id))
    c.execute("SELECT email FROM clients WHERE id=?", (client_id,))
    email = c.fetchone()[0]
    conn.commit()
    conn.close()
    send_email(email, "Kali Works Account Approved", f"<p>Your account has been approved.<br>Your Unique Account Number: <b>{account_number}</b></p>")
    log_action(f"Approved client {client_id}")
    return RedirectResponse("/admin_dashboard", status_code=303)

@app.post("/toggle_premium")
def toggle_premium(client_id: int = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT premium FROM clients WHERE id=?", (client_id,))
    current = c.fetchone()[0]
    new_value = 0 if current == 1 else 1
    c.execute("UPDATE clients SET premium=? WHERE id=?", (new_value, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin_dashboard", status_code=303)

@app.post("/toggle_block")
def toggle_block(client_id: int = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT blocked FROM clients WHERE id=?", (client_id,))
    current = c.fetchone()[0]
    new_value = 0 if current == 1 else 1
    c.execute("UPDATE clients SET blocked=? WHERE id=?", (new_value, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin_dashboard", status_code=303)

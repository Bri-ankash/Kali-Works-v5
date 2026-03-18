# ================================
# Smart Pochi – Production SaaS
# ================================

import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from database import get_conn, DB_URL, init_db
import secrets
import hashlib
import smtplib
import random
import threading
import csv
import json
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from collections import defaultdict

from fastapi import FastAPI, Request, Form, UploadFile, File, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

os.makedirs("data/uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)

from database import init_db, get_conn, DB_URL

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ADMIN_USERNAME = "Kalali"
ADMIN_PASSWORD = "@Kalali1."
ADMIN_EMAIL = "kaliworks61@gmail.com"
ADMIN_APP_PASSWORD = "mhsoqboqfqgacbmw"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

admin_2fa_codes = {}
client_2fa_codes = {}

app = FastAPI(title="Smart Pochi")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

init_db()

# ─── UTILITIES ────────────────────────────────────
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def send_email(to_email, subject, body_html):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = ADMIN_EMAIL
        msg['To'] = to_email
        msg.set_content("This email requires HTML support.")
        msg.add_alternative(body_html, subtype='html')
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(ADMIN_EMAIL, ADMIN_APP_PASSWORD)
            server.send_message(msg)
        print(f"[EMAIL] Sent to {to_email}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")

def verify_admin_session(token):
    if not token: return False
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT created_at FROM admin_sessions WHERE token=%s", (token,))
    row = c.fetchone()
    conn.close()
    if not row: return False
    created = datetime.fromisoformat(str(row['created_at']))
    return datetime.now() - created < timedelta(hours=8)

def get_client(client_id):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM clients WHERE id=%s", (client_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def log_action(action):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO audit_logs (action, timestamp) VALUES (%s,%s)", (action, str(datetime.now())))
    conn.commit()
    conn.close()

# ─── PDF ANALYSIS ─────────────────────────────────
def analyze_pdf_text(file_path):
    result = {"money_in":0.0,"money_out":0.0,"profit_loss":0.0,
              "top_consumers":{},"money_leaks":[],"transactions":[],
              "daily_totals":{},"tax_estimate":0.0,"health_score":0}
    try:
        consumers = defaultdict(float)
        with open(file_path, 'rb') as f:
            content = f.read().decode('latin-1', errors='ignore')
        lines = content.split('\n')
        for line in lines:
            amounts = re.findall(r'[\d,]+\.\d{2}', line)
            for amt_str in amounts:
                try:
                    amt = float(amt_str.replace(',',''))
                    if amt <= 0: continue
                    line_lower = line.lower()
                    if any(w in line_lower for w in ['received','deposit','credit','from','you received']):
                        result['money_in'] += amt
                    elif any(w in line_lower for w in ['sent','paid','withdraw','buy','payment','transfer','you sent']):
                        result['money_out'] += amt
                        if any(w in line_lower for w in ['bet','gambl','casino','sportpesa','betin','odibets','mcheza']):
                            result['money_leaks'].append({'desc':line.strip()[:60],'amt':amt})
                    name_match = re.search(r'(?:to|from)\s+([A-Z][a-z]+ [A-Z][a-z]+)', line)
                    if name_match:
                        consumers[name_match.group(1)] += amt
                except: continue
        result['top_consumers'] = dict(sorted(consumers.items(), key=lambda x:x[1], reverse=True)[:5])
        result['profit_loss'] = result['money_in'] - result['money_out']
        result['tax_estimate'] = round(result['money_in'] * 0.16, 2)
        # Health score
        score = 50
        if result['money_in'] > result['money_out']: score += 20
        if len(result['money_leaks']) == 0: score += 15
        if result['profit_loss'] > 0: score += 15
        result['health_score'] = min(100, score)
    except Exception as e:
        print(f"[PDF Error] {e}")
    return result

# ─── CSV ANALYSIS ─────────────────────────────────
def analyze_csv(file_path):
    result = {"money_in":0.0,"money_out":0.0,"profit_loss":0.0,
              "top_consumers":{},"money_leaks":[],"transactions":[],
              "daily_totals":{},"tax_estimate":0.0,"health_score":0}
    consumers = defaultdict(float)
    daily = defaultdict(float)
    try:
        with open(file_path, newline='', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    amt = float(str(row.get("Amount","0")).replace(',',''))
                    desc = str(row.get("Description","")).lower()
                    date = str(row.get("Date",""))[:10]
                    if amt > 0:
                        result['money_in'] += amt
                        daily[date] += amt
                    else:
                        result['money_out'] += abs(amt)
                        if any(f in desc for f in ['bet','gambl','casino','sportpesa','betin','odibets','mcheza']):
                            result['money_leaks'].append({'desc':desc[:60],'amt':abs(amt)})
                    consumer = row.get("Sender", row.get("Receiver","Unknown"))
                    consumers[consumer] += abs(amt)
                    result['transactions'].append({'date':date,'amount':amt,'desc':desc[:40]})
                except: continue
        result['top_consumers'] = dict(sorted(consumers.items(), key=lambda x:x[1], reverse=True)[:5])
        result['daily_totals'] = dict(sorted(daily.items())[-30:])
        result['profit_loss'] = result['money_in'] - result['money_out']
        result['tax_estimate'] = round(result['money_in'] * 0.16, 2)
        score = 50
        if result['money_in'] > result['money_out']: score += 20
        if len(result['money_leaks']) == 0: score += 15
        if result['profit_loss'] > 0: score += 15
        result['health_score'] = min(100, score)
    except Exception as e:
        print(f"[CSV Error] {e}")
    return result

# ─── LANDING ──────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/register_page", response_class=HTMLResponse)
def show_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/login_page", response_class=HTMLResponse)
def show_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# ─── REGISTRATION ─────────────────────────────────
@app.post("/register")
def register(request: Request, fname: str=Form(...), lname: str=Form(...),
             id_pass: str=Form(...), email: str=Form(...), mobile: str=Form(...),
             password: str=Form(...), confirm_password: str=Form(...)):
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {"request":request,"error":"Passwords do not match"})
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT id FROM clients WHERE email=%s OR mobile=%s", (email, mobile))
    if c.fetchone():
        conn.close()
        return templates.TemplateResponse("register.html", {"request":request,"error":"Email or phone already registered."})
    hashed = hash_password(password)
    c.execute("INSERT INTO clients (fname,lname,id_pass,email,mobile,password) VALUES (%s,%s,%s,%s,%s,%s)",
              (fname,lname,id_pass,email,mobile,hashed))
    conn.commit()
    conn.close()
    BASE_URL = "https://smart-pochi.onrender.com"
    verify_link = f"{BASE_URL}/confirm_email?email={email}"
    html = f"""<div style='font-family:Arial;padding:20px;background:#0a1220;color:#e8f4ff;border-radius:10px'>
        <h2 style='color:#0ea5e9'>Welcome to Smart Pochi! 🐼</h2>
        <p>Click below to verify your email and activate your account:</p>
        <a href='{verify_link}' style='display:inline-block;padding:12px 24px;background:#0ea5e9;color:#000;border-radius:8px;text-decoration:none;font-weight:bold'>✅ Verify My Email</a>
        <p style='color:#7a99bb;margin-top:16px'>If you did not register, ignore this email.</p>
    </div>"""
    send_email(email, "Verify your Smart Pochi account", html)
    return templates.TemplateResponse("registration_pending.html", {"request":request,"message":"Registration successful! Check your email to verify your account."})

@app.get("/confirm_email", response_class=HTMLResponse)
def confirm_email_page(request: Request, email: str):
    return templates.TemplateResponse("verify_page.html", {"request":request,"email":email})

@app.post("/confirm_email")
def confirm_email(request: Request, email: str=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("UPDATE clients SET verified=1 WHERE email=%s", (email,))
    conn.commit()
    conn.close()
    return templates.TemplateResponse("email_verified.html", {"request":request,"message":"Email verified! ✅ Waiting for admin approval."})

# ─── CLIENT LOGIN ─────────────────────────────────
@app.post("/client_login")
def client_login(request: Request, account_number: str=Form(...), password: str=Form(...)):
    hashed = hash_password(password)
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM clients WHERE account_number=%s AND password=%s AND verified=1", (account_number, hashed))
    client = c.fetchone()
    conn.close()
    if not client:
        return templates.TemplateResponse("login.html", {"request":request,"error":"Invalid credentials or account not verified."})
    client = dict(client)
    if client['blocked']:
        return templates.TemplateResponse("login.html", {"request":request,"error":"Your account has been blocked. Contact support."})
    if not client['approved']:
        return templates.TemplateResponse("login.html", {"request":request,"error":"Account pending admin approval."})
    if client['two_fa_enabled']:
        code = str(random.randint(100000,999999))
        client_2fa_codes[client['id']] = code
        html = f"<p>Your Smart Pochi 2FA code is: <b style='font-size:24px'>{code}</b></p>"
        send_email(client['email'], "Smart Pochi Login Code", html)
        resp = RedirectResponse(f"/client_2fa/{client['id']}", status_code=303)
        return resp
    resp = RedirectResponse(f"/client_dashboard/{client['id']}", status_code=303)
    resp.set_cookie("client_id", str(client['id']))
    return resp

@app.get("/client_2fa/{client_id}", response_class=HTMLResponse)
def client_2fa_page(request: Request, client_id: int):
    return templates.TemplateResponse("client_2fa.html", {"request":request,"client_id":client_id})

@app.post("/client_2fa_verify")
def client_2fa_verify(request: Request, client_id: int=Form(...), code: str=Form(...)):
    if client_2fa_codes.get(client_id) == code:
        resp = RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)
        resp.set_cookie("client_id", str(client_id))
        return resp
    return templates.TemplateResponse("client_2fa.html", {"request":request,"client_id":client_id,"error":"Invalid code."})

# ─── CLIENT DASHBOARD ─────────────────────────────
@app.get("/client_dashboard/{client_id}", response_class=HTMLResponse)
def client_dashboard(request: Request, client_id: int):
    client = get_client(client_id)
    if not client:
        return RedirectResponse("/login_page")
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    # Get uploads (limit 5 for normal, unlimited for premium)
    limit = 100 if client['premium'] else 5
    c.execute("SELECT * FROM csv_uploads WHERE client_id=%s ORDER BY uploaded_at DESC LIMIT %s", (client_id, limit))
    uploads = [dict(r) for r in c.fetchall()]
    # Parse analysis
    for u in uploads:
        try: u['analysis'] = eval(u['analysis'])
        except: u['analysis'] = {}
    # Goals
    c.execute("SELECT * FROM goals WHERE client_id=%s", (client_id,))
    goals = [dict(r) for r in c.fetchall()]
    # Suppliers (premium)
    suppliers = []
    if client['premium']:
        c.execute("SELECT * FROM suppliers WHERE client_id=%s ORDER BY due_date", (client_id,))
        suppliers = [dict(r) for r in c.fetchall()]
    # Staff salaries (premium)
    salaries = []
    if client['premium']:
        c.execute("SELECT * FROM staff_salaries WHERE client_id=%s ORDER BY paid_date DESC LIMIT 10", (client_id,))
        salaries = [dict(r) for r in c.fetchall()]
    # Float tracker (premium)
    float_data = None
    if client['premium']:
        c.execute("SELECT * FROM float_tracker WHERE client_id=%s ORDER BY recorded_at DESC LIMIT 1", (client_id,))
        row = c.fetchone()
        float_data = dict(row) if row else None
    # Budgets
    c.execute("SELECT * FROM budgets WHERE client_id=%s ORDER BY month DESC", (client_id,))
    budgets = [dict(r) for r in c.fetchall()]
    # Invoices
    c.execute("SELECT * FROM invoices WHERE client_id=%s ORDER BY created_at DESC", (client_id,))
    invoices = [dict(r) for r in c.fetchall()]
    # Net Worth
    c.execute("SELECT * FROM net_worth WHERE client_id=%s ORDER BY recorded_at DESC LIMIT 6", (client_id,))
    net_worth_data = [dict(r) for r in c.fetchall()]
    # Customers
    c.execute("SELECT * FROM customers WHERE client_id=%s ORDER BY created_at DESC", (client_id,))
    customers = [dict(r) for r in c.fetchall()]
    # Loans
    c.execute("SELECT * FROM loans WHERE client_id=%s ORDER BY created_at DESC", (client_id,))
    loans = [dict(r) for r in c.fetchall()]
    conn.close()
    return templates.TemplateResponse("client_dashboard.html", {
        "request": request,
        "client": client,
        "uploads": uploads,
        "goals": goals,
        "suppliers": suppliers,
        "salaries": salaries,
        "float_data": float_data,
        "budgets": budgets,
        "invoices": invoices,
        "net_worth": net_worth_data,
        "customers": customers,
        "loans": loans,
        "upload_count": len(uploads),
        "max_uploads": 100 if client['premium'] else 5
    })

# ─── FILE UPLOAD ──────────────────────────────────
@app.post("/upload_csv")
def upload_csv(request: Request, client_id: int=Form(...), file: UploadFile=File(...)):
    client = get_client(client_id)
    if not client:
        return RedirectResponse("/login_page")
    # Check upload limit for normal users
    if not client['premium']:
        conn = get_conn()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT COUNT(*) FROM csv_uploads WHERE client_id=%s", (client_id,))
        count = c.fetchone()[0]
        conn.close()
        if count >= 5:
            return RedirectResponse(f"/client_dashboard/{client_id}?error=Upload+limit+reached.+Upgrade+to+Premium.", status_code=303)
    # Validate file type
    ext = '.' + file.filename.split('.')[-1].lower()
    if ext not in ['.csv', '.pdf']:
        return RedirectResponse(f"/client_dashboard/{client_id}?error=Only+PDF+or+CSV+files+allowed", status_code=303)
    filename = f"{client_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    if ext == '.pdf':
        analysis = analyze_pdf_text(str(file_path))
    else:
        analysis = analyze_csv(str(file_path))
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO csv_uploads (client_id,filename,uploaded_at,analysis) VALUES (%s,%s,%s,%s)",
              (client_id, filename, str(datetime.now()), str(analysis)))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── DELETE UPLOAD ────────────────────────────────
@app.post("/delete_upload")
def delete_upload(request: Request, upload_id: int=Form(...), client_id: int=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT filename FROM csv_uploads WHERE id=%s AND client_id=%s", (upload_id, client_id))
    row = c.fetchone()
    if row:
        try: os.remove(UPLOAD_DIR / row[0])
        except: pass
        c.execute("DELETE FROM csv_uploads WHERE id=%s", (upload_id,))
        conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── GOALS ────────────────────────────────────────
@app.post("/add_goal")
def add_goal(request: Request, client_id: int=Form(...), title: str=Form(...),
             target_amount: float=Form(...), period: str=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO goals (client_id,title,target_amount,period) VALUES (%s,%s,%s,%s)",
              (client_id, title, target_amount, period))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

@app.post("/delete_goal")
def delete_goal(goal_id: int=Form(...), client_id: int=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("DELETE FROM goals WHERE id=%s AND client_id=%s", (goal_id, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── SUPPLIERS (PREMIUM) ──────────────────────────
@app.post("/add_supplier")
def add_supplier(request: Request, client_id: int=Form(...), name: str=Form(...),
                 amount_owed: float=Form(...), due_date: str=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO suppliers (client_id,name,amount_owed,due_date) VALUES (%s,%s,%s,%s)",
              (client_id, name, amount_owed, due_date))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

@app.post("/delete_supplier")
def delete_supplier(supplier_id: int=Form(...), client_id: int=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("DELETE FROM suppliers WHERE id=%s AND client_id=%s", (supplier_id, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── STAFF SALARIES (PREMIUM) ─────────────────────
@app.post("/add_salary")
def add_salary(request: Request, client_id: int=Form(...), staff_name: str=Form(...),
               amount: float=Form(...), paid_date: str=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO staff_salaries (client_id,staff_name,amount,paid_date) VALUES (%s,%s,%s,%s)",
              (client_id, staff_name, amount, paid_date))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── FLOAT TRACKER (PREMIUM) ──────────────────────
@app.post("/update_float")
def update_float(request: Request, client_id: int=Form(...),
                 float_amount: float=Form(...), alert_threshold: float=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO float_tracker (client_id,float_amount,alert_threshold) VALUES (%s,%s,%s)",
              (client_id, float_amount, alert_threshold))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── SETTINGS ─────────────────────────────────────
@app.post("/change_password")
def change_password(request: Request, client_id: int=Form(...),
                    old_password: str=Form(...), new_password: str=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT id FROM clients WHERE id=%s AND password=%s", (client_id, hash_password(old_password)))
    if not c.fetchone():
        conn.close()
        return RedirectResponse(f"/client_dashboard/{client_id}?error=Wrong+current+password", status_code=303)
    c.execute("UPDATE clients SET password=%s WHERE id=%s", (hash_password(new_password), client_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}?success=Password+changed", status_code=303)

@app.post("/toggle_2fa")
def toggle_2fa(request: Request, client_id: int=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT two_fa_enabled FROM clients WHERE id=%s", (client_id,))
    row = c.fetchone()
    new_val = 0 if row[0] else 1
    c.execute("UPDATE clients SET two_fa_enabled=%s WHERE id=%s", (new_val, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── CLIENT LOGOUT ────────────────────────────────
@app.get("/client_logout")
def client_logout():
    resp = RedirectResponse("/login_page")
    resp.delete_cookie("client_id")
    return resp

# ─── PANDA BOT API ────────────────────────────────
@app.post("/panda_chat")
async def panda_chat(request: Request):
    body = await request.json()
    msg = body.get("message","").lower()
    client_id = body.get("client_id")
    client = get_client(client_id) if client_id else None
    premium = client['premium'] if client else False

    if any(w in msg for w in ['server','admin','password','database','secret','token']):
        return JSONResponse({"reply":"🐼 I can't share system information. I'm here to help with your finances!"})
    if 'upload' in msg or 'pdf' in msg or 'csv' in msg:
        return JSONResponse({"reply":"🐼 To analyze your M-Pesa statement, upload a PDF or CSV file using the upload button above!"})
    if 'money in' in msg or 'income' in msg:
        return JSONResponse({"reply":"🐼 Money In shows all funds received in your M-Pesa. Upload a statement to see your totals!"})
    if 'money out' in msg or 'expense' in msg:
        return JSONResponse({"reply":"🐼 Money Out shows all payments and transfers made. Keep this lower than Money In for profit!"})
    if 'leak' in msg or 'gambling' in msg or 'bet' in msg:
        if premium:
            return JSONResponse({"reply":"🐼 Premium feature! Your money leak report flags betting, gambling and unusual outflows automatically."})
        return JSONResponse({"reply":"🐼 Money leak detection is a Premium feature. Upgrade to KES 3,500/month to access it!"})
    if 'health' in msg or 'score' in msg:
        if premium:
            return JSONResponse({"reply":"🐼 Your Business Health Score (0-100) is calculated from your income, expenses and spending habits!"})
        return JSONResponse({"reply":"🐼 Business Health Score is a Premium feature. Upgrade to unlock it!"})
    if 'tax' in msg or 'kra' in msg:
        if premium:
            return JSONResponse({"reply":"🐼 Your tax estimate is based on 16% VAT of your total income. Always consult a tax professional for official filing!"})
        return JSONResponse({"reply":"🐼 Tax estimation is a Premium feature. Upgrade to KES 3,500/month!"})
    if 'premium' in msg or 'upgrade' in msg:
        return JSONResponse({"reply":"🐼 Premium Plan is KES 3,500/month! You get unlimited uploads, charts, money leak detection, tax estimates, health score and more. Contact support to upgrade!"})
    if 'goal' in msg or 'target' in msg:
        return JSONResponse({"reply":"🐼 Use the Goal Tracker to set monthly income targets and track your progress!"})
    if 'supplier' in msg:
        if premium:
            return JSONResponse({"reply":"🐼 Track what you owe suppliers in the Supplier Tracker section below!"})
        return JSONResponse({"reply":"🐼 Supplier tracking is a Premium feature!"})
    if 'hello' in msg or 'hi' in msg or 'hey' in msg:
        return JSONResponse({"reply":f"🐼 Hello! I'm Panda, your Smart Pochi assistant! {'You have Premium access — ask me anything!' if premium else 'Ask me about your finances or how to use Smart Pochi!'}"})
    return JSONResponse({"reply":"🐼 I'm here to help with your M-Pesa analysis! Ask me about uploads, income, expenses, goals or Premium features."})

# ─── ADMIN ────────────────────────────────────────
@app.get("/smartpochi-admin", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request":request})

@app.post("/admin_login", response_class=HTMLResponse)
def admin_login_post(request: Request, username: str=Form(...), password: str=Form(...)):
    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        return templates.TemplateResponse("admin_login.html", {"request":request,"error":"Invalid credentials"})
    code = str(random.randint(100000,999999))
    admin_2fa_codes[username] = code
    html = f"<p>Your Smart Pochi admin 2FA code is: <b style='font-size:28px;color:#0ea5e9'>{code}</b></p>"
    threading.Thread(target=send_email, args=(ADMIN_EMAIL, "Smart Pochi Admin 2FA", html)).start()
    return templates.TemplateResponse("admin_2fa.html", {"request":request,"username":username,"code":code})

@app.post("/admin_2fa_verify", response_class=HTMLResponse)
def admin_2fa_verify(request: Request, username: str=Form(...), code: str=Form(...)):
    if admin_2fa_codes.get(username) != code:
        return templates.TemplateResponse("admin_2fa.html", {"request":request,"username":username,"error":"Invalid code"})
    token = secrets.token_hex(32)
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO admin_sessions (token,created_at) VALUES (%s,%s)", (token, str(datetime.now())))
    conn.commit()
    conn.close()
    resp = RedirectResponse("/admin_dashboard", status_code=303)
    resp.set_cookie("admin_token", token, httponly=True)
    return resp

@app.get("/admin_dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, admin_token: str=Cookie(default=None)):
    if not verify_admin_session(admin_token):
        return RedirectResponse("/smartpochi-admin")
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT COUNT(*) FROM clients")
    total = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) FROM clients WHERE premium=1")
    premium = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) FROM clients WHERE blocked=1")
    blocked = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) FROM clients WHERE verified=1")
    verified = c.fetchone()["count"]
    c.execute("SELECT * FROM clients WHERE approved=0 AND verified=1")
    pending = [dict(r) for r in c.fetchall()]
    c.execute("SELECT * FROM clients WHERE approved=1 ORDER BY id DESC")
    approved = [dict(r) for r in c.fetchall()]
    c.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 20")
    logs = [dict(r) for r in c.fetchall()]
    conn.close()
    return templates.TemplateResponse("admin_dashboard.html", {
        "request":request,
        "total":total,"premium":premium,"blocked":blocked,"verified":verified,
        "pending_clients":pending,"approved_clients":approved,"logs":logs
    })

@app.post("/approve_client")
def approve_client(request: Request, client_id: int=Form(...),
                   account_number: str=Form(...), admin_token: str=Cookie(default=None)):
    if not verify_admin_session(admin_token):
        return RedirectResponse("/smartpochi-admin")
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("UPDATE clients SET approved=1, account_number=%s WHERE id=%s", (account_number, client_id))
    conn.commit()
    c.execute("SELECT email, fname FROM clients WHERE id=%s", (client_id,))
    row = c.fetchone()
    conn.close()
    if row:
        html = f"""<div style='font-family:Arial;padding:20px;background:#0a1220;color:#e8f4ff;border-radius:10px'>
            <h2 style='color:#0ea5e9'>Smart Pochi Account Approved! 🎉</h2>
            <p>Hello {row[0]},</p>
            <p>Your account has been approved. Your login account number is:</p>
            <h1 style='color:#0ea5e9;letter-spacing:3px'>{account_number}</h1>
            <p>Login at: <a href='https://smart-pochi.onrender.com/login_page' style='color:#0ea5e9'>Smart Pochi</a></p>
        </div>"""
        send_email(row[1], "Smart Pochi Account Approved!", html)
    log_action(f"Approved client {client_id} with account {account_number}")
    return RedirectResponse("/admin_dashboard", status_code=303)

@app.post("/toggle_premium")
def toggle_premium(client_id: int=Form(...), admin_token: str=Cookie(default=None)):
    if not verify_admin_session(admin_token):
        return RedirectResponse("/smartpochi-admin")
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT premium FROM clients WHERE id=%s", (client_id,))
    row = c.fetchone()
    new_val = 0 if row[0] else 1
    c.execute("UPDATE clients SET premium=%s WHERE id=%s", (new_val, client_id))
    conn.commit()
    conn.close()
    log_action(f"Toggled premium for client {client_id} to {new_val}")
    return RedirectResponse("/admin_dashboard", status_code=303)

@app.post("/toggle_block")
def toggle_block(client_id: int=Form(...), admin_token: str=Cookie(default=None)):
    if not verify_admin_session(admin_token):
        return RedirectResponse("/smartpochi-admin")
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT blocked FROM clients WHERE id=%s", (client_id,))
    row = c.fetchone()
    new_val = 0 if row[0] else 1
    c.execute("UPDATE clients SET blocked=%s WHERE id=%s", (new_val, client_id))
    conn.commit()
    conn.close()
    log_action(f"Toggled block for client {client_id} to {new_val}")
    return RedirectResponse("/admin_dashboard", status_code=303)

@app.get("/admin_logout")
def admin_logout(admin_token: str=Cookie(default=None)):
    if admin_token:
        conn = get_conn()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("DELETE FROM admin_sessions WHERE token=%s", (admin_token,))
        conn.commit()
        conn.close()
    resp = RedirectResponse("/smartpochi-admin")
    resp.delete_cookie("admin_token")
    return resp

# ─── BUDGET TRACKER ───────────────────────────────
@app.post("/add_budget")
def add_budget(request: Request, client_id: int=Form(...), category: str=Form(...),
               budget_amount: float=Form(...), month: str=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO budgets (client_id,category,budget_amount,month) VALUES (%s,%s,%s,%s)",
              (client_id, category, budget_amount, month))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

@app.post("/delete_budget")
def delete_budget(budget_id: int=Form(...), client_id: int=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("DELETE FROM budgets WHERE id=%s AND client_id=%s", (budget_id, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── INVOICE GENERATOR ────────────────────────────
@app.post("/create_invoice")
def create_invoice(request: Request, client_id: int=Form(...),
                   client_name: str=Form(...), client_email: str=Form(...),
                   items: str=Form(...), total: float=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT COUNT(*) FROM invoices WHERE client_id=%s", (client_id,))
    count = c.fetchone()[0] + 1
    inv_num = f"SP-INV-{client_id}-{count:03d}"
    c.execute("INSERT INTO invoices (client_id,invoice_number,client_name,client_email,items,total) VALUES (%s,%s,%s,%s,%s,%s)",
              (client_id, inv_num, client_name, client_email, items, total))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

@app.post("/mark_invoice_paid")
def mark_invoice_paid(invoice_id: int=Form(...), client_id: int=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("UPDATE invoices SET status='paid' WHERE id=%s AND client_id=%s", (invoice_id, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

@app.post("/delete_invoice")
def delete_invoice(invoice_id: int=Form(...), client_id: int=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("DELETE FROM invoices WHERE id=%s AND client_id=%s", (invoice_id, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── NET WORTH ────────────────────────────────────
@app.post("/add_net_worth")
def add_net_worth(client_id: int=Form(...), assets: float=Form(...), liabilities: float=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO net_worth (client_id,assets,liabilities) VALUES (%s,%s,%s)",
              (client_id, assets, liabilities))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── CUSTOMERS ────────────────────────────────────
@app.post("/add_customer")
def add_customer(client_id: int=Form(...), name: str=Form(...), phone: str=Form(...),
                 email: str=Form(""), amount_owed: float=Form(0), notes: str=Form("")):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO customers (client_id,name,phone,email,amount_owed,notes) VALUES (%s,%s,%s,%s,%s,%s)",
              (client_id, name, phone, email, amount_owed, notes))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

@app.post("/delete_customer")
def delete_customer(customer_id: int=Form(...), client_id: int=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("DELETE FROM customers WHERE id=%s AND client_id=%s", (customer_id, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

# ─── LOANS ────────────────────────────────────────
@app.post("/add_loan")
def add_loan(client_id: int=Form(...), lender: str=Form(...), principal: float=Form(...),
             interest_rate: float=Form(...), months: int=Form(...), start_date: str=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("INSERT INTO loans (client_id,lender,principal,interest_rate,months,start_date) VALUES (%s,%s,%s,%s,%s,%s)",
              (client_id, lender, principal, interest_rate, months, start_date))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

@app.post("/delete_loan")
def delete_loan(loan_id: int=Form(...), client_id: int=Form(...)):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("DELETE FROM loans WHERE id=%s AND client_id=%s", (loan_id, client_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/client_dashboard/{client_id}", status_code=303)

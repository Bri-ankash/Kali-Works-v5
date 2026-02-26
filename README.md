**🚀 Kali Works V5**
Intelligent Financial SaaS Platform
� � � � �

---

**🎯 Overview**
Kali Works V5 is a lightweight, secure, and intelligent SaaS platform designed to manage financial data through CSV uploads, smart analytics, and an integrated Panda Assistant.
Built for speed, clarity, and structured client management.

---

**🌟 Core Features**

**👥 Client Dashboard**
Secure login & email verification
Account approval system
Premium status management
CSV upload interface
Financial summaries (Money In, Money Out, Profit/Loss)
Panda Assistant access

**🤖 Panda Assistant**
Available to all users:
Basic navigation help
Simple profit questions
Upload guidance

**Premium Users Unlock:**
Advanced CSV analysis
Profit breakdown
Top consumers detection
Money leak identification

**🔐 Admin Dashboard**
🔒 Mandatory 2FA login
👤 Approve / Reject new clients
⭐ Toggle Premium access
🚫 Block / Unblock clients
📊 View platform statistics
📝 Audit logging system

---

**📊 CSV Financial Analysis Engine**
Automatically calculates:
💰 Total Money In
💸 Total Money Out
📈 Profit / Loss
⚠️ Money Leaks (e.g., gambling patterns)
🏆 Top Consumers
Lightweight. Fast. Efficient.

---

**🛠 Tech Stack**
Layer
Technology
Backend
FastAPI
Language
Python 3.11+
Database
SQLite
Templates
Jinja2
Email
SMTP (Gmail)
Deployment
Render / Cloud Ready
Dev Env
Termux

---

**⚙️ Installation (Termux)**

**1️⃣ Clone Repository**
git clone https://github.com/Bri-ankash/kali-works-v5.git�
cd kali-works-v5

**2️⃣ Create Virtual Environment**
python3 -m venv venv
source venv/bin/activate

**3️⃣ Install Dependencies**
pip install -r requirements.txt

**4️⃣ Run Application**
uvicorn main:app --reload

**5️⃣ Open in Browser**
http://127.0.0.1:8000�

---

**📂 Project Structure**
main.py → Core FastAPI logic
templates/ → Client & Admin HTML dashboards
static/ → CSS & frontend assets
uploads/ → CSV storage (ignored in Git)
kaliworks.db → SQLite database (ignored)
.env → Environment variables (ignored)

---

**🔒 Security Highlights**
SHA-256 password hashing
Admin 2FA mandatory
Session expiration system
Sensitive files excluded via .gitignore

---

**📬 Contact Me**
👨‍💻 GitHub
https://github.com/Bri-ankash�
📧 Email
briankash61@gmail.com

---

**🏆 Kali Works Philosophy**
Lightweight. Secure. Structured. Intelligent.
Built with precision. Designed for growth.

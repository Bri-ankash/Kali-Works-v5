Kali Works V5 – Production SaaS
Kali Works V5 is a lightweight, fast, and secure SaaS platform designed to manage client accounts, upload CSV data, and provide insights through an intelligent Panda assistant. It supports both free and premium clients, with premium clients getting enhanced analysis features.
Features
Client Management
Registration, email verification, and admin approval.
Account blocking/unblocking by admin.
Premium status toggling for clients.
Panda Assistant
Provides financial insights from uploaded CSVs.
Free clients have access to basic queries (e.g., “Where do I upload my PDF?” or “Am I making a profit?”).
Premium clients receive full analysis, including profit/loss breakdown and top consumers.
CSV Uploads & Analysis
Upload CSV files with transaction data.
Automatic analysis of income, expenses, and money leaks.
Admin Features
Mandatory 2FA for admin login.
Dashboard showing client statistics.
Approve clients, toggle premium status, block/unblock accounts.
Audit logs for admin actions.
Security
Passwords hashed with SHA-256.
Session expiration for both clients and admin.
Sensitive files (.env, database, virtual environment) ignored in Git via .gitignore.
Tech Stack
Python 3.11+
FastAPI
SQLite
Jinja2 Templates
Termux (for development on mobile)
SMTP for email notifications
Setup & Run (Termux)
Clone the repository:
Bash
Copy code
git clone https://github.com/Bri-ankash/kali-works-v5.git
cd kali-works-v5
Create and activate a virtual environment:
Bash
Copy code
python3 -m venv venv
source venv/bin/activate
Install dependencies:
Bash
Copy code
pip install -r requirements.txt
Run the application:
Bash
Copy code
uvicorn main:app --reload
Access the app at http://127.0.0.1:8000/.
File Structure
main.py – Application logic and routes.
templates/ – HTML templates for client/admin dashboards.
static/ – CSS, JS, images.
uploads/ – Uploaded CSV files (auto-created).
kaliworks.db – SQLite database (ignored in Git).
.env – Environment variables for sensitive info (ignored in Git).
Contact Me
GitHub: Bri-ankash�
Email: briankash61@gmail.com

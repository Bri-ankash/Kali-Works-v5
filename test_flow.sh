#!/bin/bash
# Kali Works V4 full test flow (Termux-friendly)

cd ~/kaliworks

# Activate virtual environment
source venv/bin/activate

echo "Starting Kali Works V4..."
# Run in background
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

sleep 3  # give server time to start

echo "Server started at http://127.0.0.1:8000"

# Simulate registration via sqlite (you can adjust values)
EMAIL="testclient@example.com"
FIRST="Test"
LAST="Client"
ID_PASS="ID123456"
MOBILE="0712345678"
PASSWORD="Password123"

sqlite3 kaliworks.db <<SQL
INSERT INTO clients (fname, lname, id_pass, email, mobile, password)
VALUES ('$FIRST','$LAST','$ID_PASS','$EMAIL','$MOBILE','$(python -c "import hashlib; print(hashlib.sha256(b\"$PASSWORD\").hexdigest())")');
SQL

echo "Client registered: $EMAIL"

# Simulate email verification
sqlite3 kaliworks.db "UPDATE clients SET verified=1 WHERE email='$EMAIL';"
echo "Client email verified ✅"

# Simulate admin approval and assign unique account number
ACCOUNT_NUMBER="KW-$(date +%s)"
sqlite3 kaliworks.db "UPDATE clients SET approved=1, account_number='$ACCOUNT_NUMBER' WHERE email='$EMAIL';"
echo "Admin approved client, assigned account number: $ACCOUNT_NUMBER"

# Simulate client login check
LOGIN_OK=$(sqlite3 kaliworks.db "SELECT id FROM clients WHERE account_number='$ACCOUNT_NUMBER' AND password='$(python -c "import hashlib; print(hashlib.sha256(b\"$PASSWORD\").hexdigest())")' AND verified=1 AND approved=1;")

if [ -n "$LOGIN_OK" ]; then
    echo "Client login successful. ID: $LOGIN_OK ✅"
else
    echo "Client login failed ❌"
fi

echo "Test flow complete. Server still running in background (PID $UVICORN_PID)"
echo "Visit http://127.0.0.1:8000 to see the landing page"

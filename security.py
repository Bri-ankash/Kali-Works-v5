from passlib.context import CryptContext
import secrets
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def generate_token():
    return secrets.token_urlsafe(32)

def expiry(minutes=15):
    return (datetime.utcnow() + timedelta(minutes=minutes)).isoformat()

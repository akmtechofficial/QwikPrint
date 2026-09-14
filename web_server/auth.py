import os
import hmac
import hashlib
import binascii
import json
import base64
import secrets
import time
from fastapi import Request, Response
from web_server.database import db

SESSION_SECRET = os.environ.get("SESSION_SECRET")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_hex(32)
    print("[Auth Warning] SESSION_SECRET not set in environment. Generated transient session secret key.")

def hash_password(password: str) -> str:
    """Hashes password using PBKDF2 HMAC SHA-256 with salt."""
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return binascii.hexlify(salt).decode('ascii') + "$" + binascii.hexlify(pwd_hash).decode('ascii')

def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies plaintext password against stored PBKDF2 hash."""
    try:
        salt_hex, hash_hex = stored_hash.split("$")
        salt = binascii.unhexlify(salt_hex.encode('ascii'))
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return binascii.hexlify(pwd_hash).decode('ascii') == hash_hex
    except Exception:
        return False

def create_session_data(user_id: str, shop_id: str) -> str:
    """Creates an HMAC SHA-256 signed session token with expiration."""
    exp = int(time.time()) + (86400 * 30) # 30 days
    data = {"user_id": user_id, "shop_id": shop_id, "exp": exp}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
    sig = hmac.new(SESSION_SECRET.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def decode_session_data(session_str: str) -> dict:
    """Decodes and verifies HMAC SHA-256 signed session cookie."""
    try:
        if "." not in session_str:
            return {}
        payload_b64, sig = session_str.rsplit(".", 1)
        expected_sig = hmac.new(SESSION_SECRET.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return {}
        
        raw = base64.urlsafe_b64decode(payload_b64.encode('utf-8')).decode('utf-8')
        data = json.loads(raw)
        
        if data.get("exp", 0) < time.time():
            return {}
            
        return data
    except Exception:
        return {}

def get_current_user_and_shop(request: Request) -> tuple[dict, dict]:
    """Retrieves authenticated user and shop from session cookie."""
    cookie = request.cookies.get("qwikprint_session")
    if not cookie:
        return None, None

    sess = decode_session_data(cookie)
    user_id = sess.get("user_id")
    shop_id = sess.get("shop_id")

    if not user_id or not shop_id:
        return None, None

    user = db.get_user(user_id) if hasattr(db, 'get_user') else None
    shop = db.get_shop(shop_id)

    return user, shop

import os
import hashlib
import binascii
import json
import base64
from fastapi import Request, Response
from web_server.database import db

SECRET_KEY = "qwikprint_secret_key_super_secure_auth_token"

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
    """Creates a base64 encoded session string."""
    data = {"user_id": user_id, "shop_id": shop_id, "key": SECRET_KEY}
    return base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')

def decode_session_data(session_str: str) -> dict:
    """Decodes session cookie."""
    try:
        raw = base64.b64decode(session_str.encode('utf-8')).decode('utf-8')
        data = json.loads(raw)
        if data.get("key") == SECRET_KEY:
            return data
        return {}
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

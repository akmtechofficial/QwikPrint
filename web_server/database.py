import os
import json
import uuid
import datetime
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

HAS_POSTGRES = False
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

import sqlite3

SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "qwikprint.db")

class SupabaseDatabase:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.host = os.getenv("SUPABASE_DB_HOST", "")
        self.port = int(os.getenv("SUPABASE_DB_PORT", "5432"))
        self.dbname = os.getenv("SUPABASE_DB_NAME", "postgres")
        self.user = os.getenv("SUPABASE_DB_USER", "postgres")
        self.password = os.getenv("SUPABASE_DB_PASSWORD", "")
        self.allow_sqlite_dev = os.getenv("ALLOW_SQLITE_DEV", "true").lower() == "true"
        
        self.use_postgres = False
        self.init_db()

    def get_connection(self):
        if HAS_POSTGRES and (self.db_url or self.password or self.host):
            try:
                if self.db_url:
                    conn = psycopg2.connect(self.db_url, connect_timeout=5)
                else:
                    conn = psycopg2.connect(
                        host=self.host,
                        port=self.port,
                        dbname=self.dbname,
                        user=self.user,
                        password=self.password,
                        connect_timeout=5
                    )
                self.use_postgres = True
                return conn, True
            except Exception as e:
                if not self.allow_sqlite_dev:
                    raise RuntimeError(f"[Database Error] Production PostgreSQL connection failed: {e}. Set ALLOW_SQLITE_DEV=true in .env.local for local dev testing.")
                print(f"[Supabase Warning] Could not connect to PostgreSQL: {e}. Using local SQLite fallback for dev environment.")

        if not self.allow_sqlite_dev:
            raise RuntimeError("[Database Error] PostgreSQL credentials not configured. Please set DATABASE_URL or SUPABASE_DB_PASSWORD in .env.local.")

        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        self.use_postgres = False
        return conn, False

    def init_db(self):
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()

        if is_pg:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(100) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name VARCHAR(255),
                phone VARCHAR(50),
                role VARCHAR(50) DEFAULT 'shop_owner',
                created_at VARCHAR(100)
            );
            CREATE TABLE IF NOT EXISTS shops (
                shop_id VARCHAR(100) PRIMARY KEY,
                owner_id VARCHAR(100),
                api_key VARCHAR(255) UNIQUE,
                name VARCHAR(255) NOT NULL,
                owner_name VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(50),
                address TEXT,
                bw_rate FLOAT DEFAULT 2.0,
                color_rate FLOAT DEFAULT 10.0,
                duplex_discount FLOAT DEFAULT 0.5,
                created_at VARCHAR(100)
            );
            CREATE TABLE IF NOT EXISTS devices (
                device_id VARCHAR(100) PRIMARY KEY,
                shop_id VARCHAR(100) NOT NULL,
                device_name VARCHAR(255) NOT NULL,
                secret_token VARCHAR(255) NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                last_seen_at VARCHAR(100),
                created_at VARCHAR(100)
            );
            CREATE TABLE IF NOT EXISTS print_jobs (
                job_id VARCHAR(100) PRIMARY KEY,
                shop_id VARCHAR(100) NOT NULL,
                device_id VARCHAR(100),
                original_filename VARCHAR(255) NOT NULL,
                file_path TEXT NOT NULL,
                page_count INT DEFAULT 1,
                copies INT DEFAULT 1,
                color_mode VARCHAR(50) DEFAULT 'bw',
                duplex VARCHAR(50) DEFAULT 'single',
                page_range VARCHAR(50) DEFAULT 'all',
                payment_method VARCHAR(50) DEFAULT 'cash',
                payment_status VARCHAR(50) DEFAULT 'pending',
                total_cost FLOAT DEFAULT 0.0,
                status VARCHAR(50) DEFAULT 'PAYMENT_PENDING',
                error TEXT,
                created_at VARCHAR(100),
                updated_at VARCHAR(100)
            );
            """)
            conn.commit()

            cursor.execute("""
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS owner_id VARCHAR(100);
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS api_key VARCHAR(255);
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS owner_name VARCHAR(255);
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS email VARCHAR(255);
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS phone VARCHAR(50);
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS address TEXT;
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS bw_rate FLOAT DEFAULT 2.0;
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS color_rate FLOAT DEFAULT 10.0;
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS duplex_discount FLOAT DEFAULT 0.5;
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS paper_rates TEXT;
            """)
            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM shops;")
            # No mock seed insertion - database starts clean for real shop registrations
        else:
            # SQLite Table Init
            for col_def in [
                ("owner_id", "TEXT"), ("api_key", "TEXT"), ("owner_name", "TEXT"), 
                ("email", "TEXT"), ("phone", "TEXT"), ("address", "TEXT"), 
                ("bw_rate", "REAL DEFAULT 2.0"), ("color_rate", "REAL DEFAULT 10.0"), 
                ("duplex_discount", "REAL DEFAULT 0.5"), ("paper_rates", "TEXT")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE shops ADD COLUMN {col_def[0]} {col_def[1]};")
                except Exception:
                    pass
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                full_name TEXT, phone TEXT, role TEXT DEFAULT 'shop_owner', created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS shops (
                shop_id TEXT PRIMARY KEY, owner_id TEXT, api_key TEXT UNIQUE, name TEXT NOT NULL, owner_name TEXT,
                email TEXT, phone TEXT, address TEXT, bw_rate REAL DEFAULT 2.0, color_rate REAL DEFAULT 10.0,
                duplex_discount REAL DEFAULT 0.5, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY, shop_id TEXT NOT NULL, device_name TEXT NOT NULL,
                secret_token TEXT NOT NULL, status TEXT DEFAULT 'active', last_seen_at TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS print_jobs (
                job_id TEXT PRIMARY KEY, shop_id TEXT NOT NULL, device_id TEXT, original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL, page_count INTEGER DEFAULT 1, copies INTEGER DEFAULT 1, color_mode TEXT DEFAULT 'bw',
                duplex TEXT DEFAULT 'single', page_range TEXT DEFAULT 'all', payment_method TEXT DEFAULT 'cash',
                payment_status TEXT DEFAULT 'pending', total_cost REAL DEFAULT 0.0, status TEXT DEFAULT 'PAYMENT_PENDING',
                error TEXT, created_at TEXT, updated_at TEXT
            );
            """)
            conn.commit()

        conn.close()

        conn.close()

    # User operations
    def create_user_and_shop(self, full_name: str, email: str, phone: str, shop_name: str, password_hash: str) -> tuple[dict, dict]:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        user_id = f"USER_{uuid.uuid4().hex[:8].upper()}"
        shop_id = f"SHOP_{uuid.uuid4().hex[:6].upper()}"
        api_key = f"QWIK_KEY_{shop_id}_{uuid.uuid4().hex[:6].upper()}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if is_pg:
            cursor.execute("""
            INSERT INTO users (user_id, email, password_hash, full_name, phone, role, created_at)
            VALUES (%s, %s, %s, %s, %s, 'shop_owner', %s);
            """, (user_id, email.lower().strip(), password_hash, full_name, phone, now))
            
            cursor.execute("""
            INSERT INTO shops (shop_id, owner_id, api_key, name, owner_name, email, phone, address, bw_rate, color_rate, duplex_discount, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 2.0, 10.0, 0.5, %s);
            """, (shop_id, user_id, api_key, shop_name, full_name, email, phone, "Main Market", now))
            
            cursor.execute("""
            INSERT INTO devices (device_id, shop_id, device_name, secret_token, status, last_seen_at, created_at)
            VALUES (%s, %s, %s, %s, 'active', %s, %s);
            """, (f"DEV_{shop_id[-6:]}", shop_id, "Main Counter PC", "DEV_SECRET_KEY", now, now))
            conn.commit()
        else:
            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, 'shop_owner', ?);
            """, (user_id, email.lower().strip(), password_hash, full_name, phone, now))
            
            cursor.execute("""
            INSERT INTO shops VALUES (?, ?, ?, ?, ?, ?, ?, 'Main Market', 2.0, 10.0, 0.5, ?);
            """, (shop_id, user_id, api_key, shop_name, full_name, email, phone, now))
            
            cursor.execute("""
            INSERT INTO devices VALUES (?, ?, ?, ?, 'active', ?, ?);
            """, (f"DEV_{shop_id[-6:]}", shop_id, "Main Counter PC", "DEV_SECRET_KEY", now, now))
            conn.commit()

        conn.close()
        return self.get_user(user_id), self.get_shop(shop_id)

    def get_user_by_email(self, email: str) -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM users WHERE email = %s;" if is_pg else "SELECT * FROM users WHERE email = ?;"
        cursor.execute(query, (email.lower().strip(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user(self, user_id: str) -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM users WHERE user_id = %s;" if is_pg else "SELECT * FROM users WHERE user_id = ?;"
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_shop(self, user_id: str) -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM shops WHERE owner_id = %s LIMIT 1;" if is_pg else "SELECT * FROM shops WHERE owner_id = ? LIMIT 1;"
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    # API Key operations
    def get_shop_by_api_key(self, api_key: str) -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM shops WHERE api_key = %s;" if is_pg else "SELECT * FROM shops WHERE api_key = ?;"
        cursor.execute(query, (api_key.strip(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def regenerate_shop_api_key(self, shop_id: str) -> str:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        new_key = f"QWIK_KEY_{shop_id}_{uuid.uuid4().hex[:6].upper()}"
        query = "UPDATE shops SET api_key = %s WHERE shop_id = %s;" if is_pg else "UPDATE shops SET api_key = ? WHERE shop_id = ?;"
        cursor.execute(query, (new_key, shop_id))
        conn.commit()
        conn.close()
        return new_key

    # Shop details update
    def update_shop_details(self, shop_id: str, name: str, owner_name: str, phone: str, address: str, email: str):
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        query = "UPDATE shops SET name = %s, owner_name = %s, phone = %s, address = %s, email = %s WHERE shop_id = %s;" if is_pg \
            else "UPDATE shops SET name = ?, owner_name = ?, phone = ?, address = ?, email = ? WHERE shop_id = ?;"
        cursor.execute(query, (name, owner_name, phone, address, email, shop_id))
        conn.commit()
        conn.close()

    def get_shop(self, shop_id: str) -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM shops WHERE shop_id = %s;" if is_pg else "SELECT * FROM shops WHERE shop_id = ?;"
        cursor.execute(query, (shop_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_shop_devices(self, shop_id: str) -> list:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM devices WHERE shop_id = %s;" if is_pg else "SELECT * FROM devices WHERE shop_id = ?;"
        cursor.execute(query, (shop_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_shop_pricing(self, shop_id: str, bw_rate: float, color_rate: float, duplex_discount: float):
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        query = "UPDATE shops SET bw_rate = %s, color_rate = %s, duplex_discount = %s WHERE shop_id = %s;" if is_pg \
            else "UPDATE shops SET bw_rate = ?, color_rate = ?, duplex_discount = ? WHERE shop_id = ?;"
        cursor.execute(query, (bw_rate, color_rate, duplex_discount, shop_id))
        conn.commit()
        conn.close()

    def get_shop_paper_rates(self, shop_id: str) -> list:
        default_rates = [
            {"name": "A4", "bw_rate": 2.0, "color_rate": 10.0, "enabled": True},
            {"name": "A3", "bw_rate": 5.0, "color_rate": 20.0, "enabled": True},
            {"name": "Legal", "bw_rate": 3.0, "color_rate": 12.0, "enabled": True},
            {"name": "Letter", "bw_rate": 2.0, "color_rate": 10.0, "enabled": False},
            {"name": "Photo 4x6", "bw_rate": 10.0, "color_rate": 25.0, "enabled": False}
        ]
        shop = self.get_shop(shop_id)
        if shop and shop.get("paper_rates"):
            try:
                rates = json.loads(shop["paper_rates"])
                if isinstance(rates, list) and len(rates) > 0:
                    return rates[:5]
            except Exception:
                pass
        return default_rates

    def update_shop_paper_rates(self, shop_id: str, paper_rates: list) -> list:
        sanitized = paper_rates[:5]
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        rates_json = json.dumps(sanitized)
        query = "UPDATE shops SET paper_rates = %s WHERE shop_id = %s;" if is_pg else "UPDATE shops SET paper_rates = ? WHERE shop_id = ?;"
        cursor.execute(query, (rates_json, shop_id))
        conn.commit()
        conn.close()
        return sanitized

    def get_device(self, device_id: str) -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM devices WHERE device_id = %s;" if is_pg else "SELECT * FROM devices WHERE device_id = ?;"
        cursor.execute(query, (device_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_device_last_seen(self, device_id: str):
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        query = "UPDATE devices SET last_seen_at = %s WHERE device_id = %s;" if is_pg else "UPDATE devices SET last_seen_at = ? WHERE device_id = ?;"
        cursor.execute(query, (now, device_id))
        conn.commit()
        conn.close()

    def register_device(self, shop_id: str, device_name: str) -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        device_id = f"DEV_{uuid.uuid4().hex[:8].upper()}"
        secret_token = f"TOKEN_{uuid.uuid4().hex}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        query = """
        INSERT INTO devices (device_id, shop_id, device_name, secret_token, status, last_seen_at, created_at)
        VALUES (%s, %s, %s, %s, 'active', %s, %s);
        """ if is_pg else """
        INSERT INTO devices (device_id, shop_id, device_name, secret_token, status, last_seen_at, created_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?);
        """
        cursor.execute(query, (device_id, shop_id, device_name, secret_token, now, now))
        conn.commit()
        conn.close()
        return {"device_id": device_id, "secret_token": secret_token}

    def create_print_job(self, shop_id: str, original_filename: str, file_path: str, page_count: int, 
                         copies: int, color_mode: str, duplex: str, page_range: str, 
                         payment_method: str, total_cost: float) -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        job_id = f"JOB_{uuid.uuid4().hex[:10].upper()}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        initial_status = "QUEUED" if payment_method == "online" else "PAYMENT_PENDING"
        payment_status = "paid" if payment_method == "online" else "pending"

        query = """
        INSERT INTO print_jobs (
            job_id, shop_id, original_filename, file_path, page_count, copies, 
            color_mode, duplex, page_range, payment_method, payment_status, 
            total_cost, status, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """ if is_pg else """
        INSERT INTO print_jobs (
            job_id, shop_id, original_filename, file_path, page_count, copies, 
            color_mode, duplex, page_range, payment_method, payment_status, 
            total_cost, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        cursor.execute(query, (job_id, shop_id, original_filename, file_path, page_count, copies, 
                              color_mode, duplex, page_range, payment_method, payment_status, 
                              total_cost, initial_status, now, now))
        conn.commit()
        conn.close()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM print_jobs WHERE job_id = %s;" if is_pg else "SELECT * FROM print_jobs WHERE job_id = ?;"
        cursor.execute(query, (job_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_shop_jobs(self, shop_id: str, limit: int = 50) -> list:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM print_jobs WHERE shop_id = %s ORDER BY created_at DESC LIMIT %s;" if is_pg \
            else "SELECT * FROM print_jobs WHERE shop_id = ? ORDER BY created_at DESC LIMIT ?;"
        cursor.execute(query, (shop_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_queued_and_pending_jobs(self, shop_id: str) -> tuple[list, list]:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM print_jobs WHERE shop_id = %s AND status IN ('QUEUED', 'PAYMENT_PENDING', 'CREATED');" if is_pg \
            else "SELECT * FROM print_jobs WHERE shop_id = ? AND status IN ('QUEUED', 'PAYMENT_PENDING', 'CREATED');"
        cursor.execute(query, (shop_id,))
        rows = cursor.fetchall()
        conn.close()
        
        queued = []
        pending_cash = []
        for r in rows:
            d = dict(r)
            if d["status"] == "QUEUED":
                queued.append(d)
            elif d["status"] in ["PAYMENT_PENDING", "CREATED"]:
                pending_cash.append(d)
        return queued, pending_cash

    def claim_job(self, job_id: str, device_id: str) -> tuple[bool, dict]:
        conn, is_pg = self.get_connection()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        
        # Atomic Update: Only updates if status is currently 'QUEUED'
        q_update = "UPDATE print_jobs SET status = 'CLAIMED', device_id = %s, updated_at = %s WHERE job_id = %s AND status = 'QUEUED';" if is_pg \
            else "UPDATE print_jobs SET status = 'CLAIMED', device_id = ?, updated_at = ? WHERE job_id = ? AND status = 'QUEUED';"
        cursor.execute(q_update, (device_id, now, job_id))
        conn.commit()
        
        updated_rows = cursor.rowcount
        conn.close()
        
        if updated_rows == 1:
            return True, self.get_job(job_id)
        else:
            # Already claimed or not queued
            return False, self.get_job(job_id) or {}

    def update_job_status(self, job_id: str, status: str, error: str = None) -> bool:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        query = "UPDATE print_jobs SET status = %s, error = %s, updated_at = %s WHERE job_id = %s;" if is_pg \
            else "UPDATE print_jobs SET status = ?, error = ?, updated_at = ? WHERE job_id = ?;"
        cursor.execute(query, (status, error, now, job_id))
        conn.commit()
        conn.close()
        return True

    def confirm_cash_payment(self, job_id: str) -> bool:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        query = "UPDATE print_jobs SET status = 'QUEUED', payment_status = 'paid', updated_at = %s WHERE job_id = %s;" if is_pg \
            else "UPDATE print_jobs SET status = 'QUEUED', payment_status = 'paid', updated_at = ? WHERE job_id = ?;"
        cursor.execute(query, (now, job_id))
        conn.commit()
        conn.close()
        return True

db = SupabaseDatabase()

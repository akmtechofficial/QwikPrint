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
        self.allow_sqlite_dev = os.getenv("ALLOW_SQLITE_DEV", "false").lower() == "true"
        
        self.use_postgres = False
        self.init_db()

    def get_connection(self):
        if HAS_POSTGRES and (self.db_url or self.password or self.host):
            try:
                if self.db_url:
                    db_url = self.db_url
                    if "sslmode=" not in db_url:
                        db_url += ("&" if "?" in db_url else "?") + "sslmode=require"
                    conn = psycopg2.connect(db_url, connect_timeout=10)
                else:
                    conn = psycopg2.connect(
                        host=self.host,
                        port=self.port,
                        dbname=self.dbname,
                        user=self.user,
                        password=self.password,
                        sslmode='require',
                        connect_timeout=10
                    )
                self.use_postgres = True
                print("[Database] Successfully connected to PostgreSQL!")
                return conn, True
            except Exception as e:
                print(f"[Database Warning] Could not connect to PostgreSQL: {e}. Falling back to local SQLite database.")

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
            CREATE TABLE IF NOT EXISTS plans (
                plan_id VARCHAR(100) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                duration_days INT NOT NULL,
                price FLOAT NOT NULL,
                description TEXT,
                created_at VARCHAR(100)
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                subscription_id VARCHAR(100) PRIMARY KEY,
                shop_id VARCHAR(100) NOT NULL,
                plan_id VARCHAR(100),
                plan_name VARCHAR(255),
                amount FLOAT DEFAULT 0.0,
                payment_gateway VARCHAR(50) DEFAULT 'payflux',
                transaction_id VARCHAR(255),
                status VARCHAR(50) DEFAULT 'success',
                starts_at VARCHAR(100),
                expires_at VARCHAR(100),
                created_at VARCHAR(100)
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
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'active';
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS plan_name VARCHAR(255) DEFAULT 'Trial Plan';
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS plan_expires_at VARCHAR(100);
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN DEFAULT FALSE;
            """)
            conn.commit()
        else:
            # SQLite Table Init
            for col_def in [
                ("owner_id", "TEXT"), ("api_key", "TEXT"), ("owner_name", "TEXT"), 
                ("email", "TEXT"), ("phone", "TEXT"), ("address", "TEXT"), 
                ("bw_rate", "REAL DEFAULT 2.0"), ("color_rate", "REAL DEFAULT 10.0"), 
                ("duplex_discount", "REAL DEFAULT 0.5"), ("paper_rates", "TEXT"),
                ("subscription_status", "TEXT DEFAULT 'active'"),
                ("plan_name", "TEXT DEFAULT 'Trial Plan'"),
                ("plan_expires_at", "TEXT"),
                ("is_suspended", "INTEGER DEFAULT 0")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE shops ADD COLUMN {col_def[0]} {col_def[1]};")
                except Exception:
                    pass
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                full_name TEXT, phone TEXT, role TEXT DEFAULT 'shop_owner', created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS shops (
                shop_id TEXT PRIMARY KEY, owner_id TEXT, api_key TEXT UNIQUE, name TEXT NOT NULL, owner_name TEXT,
                email TEXT, phone TEXT, address TEXT, bw_rate REAL DEFAULT 2.0, color_rate REAL DEFAULT 10.0,
                duplex_discount REAL DEFAULT 0.5, created_at TEXT, subscription_status TEXT DEFAULT 'active',
                plan_name TEXT DEFAULT 'Trial Plan', plan_expires_at TEXT, is_suspended INTEGER DEFAULT 0
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
            CREATE TABLE IF NOT EXISTS plans (
                plan_id TEXT PRIMARY KEY, name TEXT NOT NULL, duration_days INTEGER NOT NULL,
                price REAL NOT NULL, description TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                subscription_id TEXT PRIMARY KEY, shop_id TEXT NOT NULL, plan_id TEXT, plan_name TEXT,
                amount REAL DEFAULT 0.0, payment_gateway TEXT DEFAULT 'payflux', transaction_id TEXT,
                status TEXT DEFAULT 'success', starts_at TEXT, expires_at TEXT, created_at TEXT
            );
            """)
            conn.commit()

        # Seed default plans if empty
        try:
            cursor.execute("SELECT COUNT(*) FROM plans;")
            count = cursor.fetchone()[0]
            if count == 0:
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                default_plans = [
                    ("plan-1m", "1 Month Starter", 30, 199.0, "30 Days Unlimited Printing Access", now),
                    ("plan-3m", "3 Months Pro", 90, 499.0, "90 Days Unlimited Printing Access (Save 15%)", now),
                    ("plan-12m", "1 Year Enterprise", 365, 1499.0, "365 Days Unlimited Printing Access (Best Value)", now)
                ]
                for p in default_plans:
                    q = "INSERT INTO plans (plan_id, name, duration_days, price, description, created_at) VALUES (%s, %s, %s, %s, %s, %s);" if is_pg \
                        else "INSERT INTO plans (plan_id, name, duration_days, price, description, created_at) VALUES (?, ?, ?, ?, ?, ?);"
                    cursor.execute(q, p)
                conn.commit()
        except Exception as e:
            print(f"[Database Warning] Error seeding default plans: {e}")

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

    def calculate_print_cost(self, shop_id: str, paper_size: str = "A4", page_count: int = 1, 
                             copies: int = 1, color_mode: str = "bw", duplex: str = "single") -> float:
        shop = self.get_shop(shop_id)
        if not shop:
            return 0.0
        
        rates = self.get_shop_paper_rates(shop_id)
        selected_rate = None
        for r in rates:
            if r.get("name", "").lower() == (paper_size or "A4").lower() and r.get("enabled", True):
                selected_rate = r
                break
        
        if selected_rate:
            bw_rate = selected_rate.get("bw_rate", shop.get("bw_rate", 2.0))
            color_rate = selected_rate.get("color_rate", shop.get("color_rate", 10.0))
        else:
            bw_rate = shop.get("bw_rate", 2.0)
            color_rate = shop.get("color_rate", 10.0)

        rate_per_page = color_rate if color_mode.lower() == "color" else bw_rate
        duplex_multiplier = (1.0 - shop.get("duplex_discount", 0.5)) if duplex.lower() in ["double", "duplex"] else 1.0
        total = max(1, page_count) * max(1, copies) * rate_per_page * duplex_multiplier
        return round(float(total), 2)

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

    def reject_cash_payment(self, job_id: str) -> bool:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        query = "UPDATE print_jobs SET status = 'REJECTED', payment_status = 'rejected', error = 'Cash payment rejected by shop counter', updated_at = %s WHERE job_id = %s;" if is_pg \
            else "UPDATE print_jobs SET status = 'REJECTED', payment_status = 'rejected', error = 'Cash payment rejected by shop counter', updated_at = ? WHERE job_id = ?;"
        cursor.execute(query, (now, job_id))
        conn.commit()
        conn.close()
        return True

    def get_active_file_paths(self) -> set:
        """Returns normalized basenames of files belonging to active (non-terminal) print jobs."""
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT file_path FROM print_jobs WHERE status IN ('PAYMENT_PENDING', 'CREATED', 'QUEUED', 'CLAIMED', 'PROCESSING', 'PRINTING');"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        active_files = set()
        for r in rows:
            fp = dict(r).get("file_path", "")
            if fp:
                active_files.add(os.path.basename(fp).lower())
        return active_files

    # Master Admin & Subscription Helper Methods
    def get_all_shops(self):
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM shops ORDER BY created_at DESC;"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def toggle_shop_suspension(self, shop_id: str, suspend: bool) -> bool:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        is_susp_val = bool(suspend) if is_pg else (1 if suspend else 0)
        status_val = 'suspended' if suspend else 'active'
        query = "UPDATE shops SET is_suspended = %s, subscription_status = %s WHERE shop_id = %s;" if is_pg \
            else "UPDATE shops SET is_suspended = ?, subscription_status = ? WHERE shop_id = ?;"
        cursor.execute(query, (is_susp_val, status_val, shop_id))
        conn.commit()
        conn.close()
        return True

    def update_shop_subscription(self, shop_id: str, duration_days: int, plan_name: str = "Custom Renewal") -> dict:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        
        q_get = "SELECT plan_expires_at FROM shops WHERE shop_id = %s;" if is_pg else "SELECT plan_expires_at FROM shops WHERE shop_id = ?;"
        cursor.execute(q_get, (shop_id,))
        row = cursor.fetchone()
        
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        start_dt = now_dt
        if row and dict(row).get("plan_expires_at"):
            try:
                curr_exp = datetime.datetime.fromisoformat(dict(row)["plan_expires_at"])
                if curr_exp > now_dt:
                    start_dt = curr_exp
            except Exception:
                pass
        
        new_exp_dt = start_dt + datetime.timedelta(days=duration_days)
        new_exp_str = new_exp_dt.isoformat()
        
        q_upd = "UPDATE shops SET subscription_status = 'active', plan_name = %s, plan_expires_at = %s, is_suspended = FALSE WHERE shop_id = %s;" if is_pg \
            else "UPDATE shops SET subscription_status = 'active', plan_name = ?, plan_expires_at = ?, is_suspended = 0 WHERE shop_id = ?;"
        cursor.execute(q_upd, (plan_name, new_exp_str, shop_id))
        conn.commit()
        conn.close()
        
        return {
            "shop_id": shop_id,
            "plan_name": plan_name,
            "plan_expires_at": new_exp_str,
            "subscription_status": "active"
        }

    def verify_shop_active_subscription(self, shop_id: str) -> tuple:
        """Returns (is_valid: bool, reason: str, expiry_date: str)"""
        shop = self.get_shop(shop_id)
        if not shop:
            return False, "Shop not found", ""
        
        if shop.get("is_suspended"):
            return False, "Account suspended by Admin", shop.get("plan_expires_at", "")
        
        exp_str = shop.get("plan_expires_at")
        if not exp_str:
            return True, "Active", ""
        
        try:
            exp_dt = datetime.datetime.fromisoformat(exp_str)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            if exp_dt < now_dt:
                return False, "Subscription plan expired", exp_str
        except Exception:
            pass

        return True, "Active", exp_str

    def get_plans(self):
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM plans ORDER BY price ASC;"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def save_plan(self, plan_data: dict) -> bool:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        plan_id = plan_data.get("plan_id") or f"plan-{uuid.uuid4().hex[:8]}"
        name = plan_data.get("name", "Custom Plan")
        duration_days = int(plan_data.get("duration_days", 30))
        price = float(plan_data.get("price", 0.0))
        description = plan_data.get("description", "")
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        q_up = """
        INSERT INTO plans (plan_id, name, duration_days, price, description, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (plan_id) DO UPDATE SET
            name = EXCLUDED.name,
            duration_days = EXCLUDED.duration_days,
            price = EXCLUDED.price,
            description = EXCLUDED.description;
        """ if is_pg else """
        INSERT OR REPLACE INTO plans (plan_id, name, duration_days, price, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        cursor.execute(q_up, (plan_id, name, duration_days, price, description, now))
        conn.commit()
        conn.close()
        return True

    def delete_plan(self, plan_id: str) -> bool:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        q_del = "DELETE FROM plans WHERE plan_id = %s;" if is_pg else "DELETE FROM plans WHERE plan_id = ?;"
        cursor.execute(q_del, (plan_id,))
        conn.commit()
        conn.close()
        return True

    def create_subscription_record(self, sub_data: dict) -> bool:
        conn, is_pg = self.get_connection()
        cursor = conn.cursor()
        sub_id = sub_data.get("subscription_id") or f"sub-{uuid.uuid4().hex[:10]}"
        shop_id = sub_data.get("shop_id")
        plan_id = sub_data.get("plan_id")
        plan_name = sub_data.get("plan_name", "")
        amount = float(sub_data.get("amount", 0.0))
        gw = sub_data.get("payment_gateway", "payflux")
        tx_id = sub_data.get("transaction_id", f"tx-{uuid.uuid4().hex[:12]}")
        status = sub_data.get("status", "success")
        starts_at = sub_data.get("starts_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
        expires_at = sub_data.get("expires_at", "")
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        q_ins = """
        INSERT INTO subscriptions (subscription_id, shop_id, plan_id, plan_name, amount, payment_gateway, transaction_id, status, starts_at, expires_at, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """ if is_pg else """
        INSERT INTO subscriptions (subscription_id, shop_id, plan_id, plan_name, amount, payment_gateway, transaction_id, status, starts_at, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        cursor.execute(q_ins, (sub_id, shop_id, plan_id, plan_name, amount, gw, tx_id, status, starts_at, expires_at, created_at))
        conn.commit()
        conn.close()
        return True

    def get_subscriptions(self):
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        query = "SELECT * FROM subscriptions ORDER BY created_at DESC;"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_admin_dashboard_stats(self):
        conn, is_pg = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total_shops FROM shops;")
        total_shops = dict(cursor.fetchone() or {}).get("total_shops", 0)

        cursor.execute("SELECT COUNT(*) as suspended_shops FROM shops WHERE is_suspended = TRUE;" if is_pg else "SELECT COUNT(*) as suspended_shops FROM shops WHERE is_suspended = 1;")
        suspended_shops = dict(cursor.fetchone() or {}).get("suspended_shops", 0)

        cursor.execute("SELECT COUNT(*) as total_jobs, SUM(total_cost) as total_revenue FROM print_jobs WHERE status = 'COMPLETED';")
        job_stats = dict(cursor.fetchone() or {})

        cursor.execute("SELECT SUM(amount) as subscription_revenue FROM subscriptions WHERE status = 'success';")
        sub_revenue = dict(cursor.fetchone() or {}).get("subscription_revenue") or 0.0

        conn.close()
        return {
            "total_shops": total_shops,
            "suspended_shops": suspended_shops,
            "completed_print_jobs": job_stats.get("total_jobs") or 0,
            "print_revenue": job_stats.get("total_revenue") or 0.0,
            "subscription_revenue": sub_revenue
        }

db = SupabaseDatabase()

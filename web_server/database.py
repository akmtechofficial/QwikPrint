import os
import json
import uuid
import datetime
import time
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
        self.last_pg_check = 0
        self.pg_failed = False

        self.init_db()

    def get_connection(self):
        """
        Retrieves a database connection. Tries PostgreSQL (Supabase) if configured and reachable.
        Caches failure states to avoid 10-second query delays and falls back smoothly to SQLite.
        """
        now = time.time()
        
        # Retry PostgreSQL every 120 seconds if previously failed
        if HAS_POSTGRES and (self.db_url or self.password or self.host):
            if not self.pg_failed or (now - self.last_pg_check > 120):
                self.last_pg_check = now
                try:
                    if self.db_url:
                        db_url = self.db_url
                        if "sslmode=" not in db_url:
                            db_url += ("&" if "?" in db_url else "?") + "sslmode=require"
                        conn = psycopg2.connect(db_url, connect_timeout=3)
                    else:
                        conn = psycopg2.connect(
                            host=self.host,
                            port=self.port,
                            dbname=self.dbname,
                            user=self.user,
                            password=self.password,
                            sslmode='require',
                            connect_timeout=3
                        )
                    self.use_postgres = True
                    self.pg_failed = False
                    return conn, True
                except Exception as e:
                    if not self.pg_failed:
                        print(f"[Database Warning] Could not connect to PostgreSQL: {e}. Active mode: Local SQLite database.")
                    self.pg_failed = True
                    self.use_postgres = False

        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        self.use_postgres = False
        return conn, False

    def get_sqlite_conn(self):
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

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
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'active';
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS plan_name VARCHAR(255) DEFAULT 'Trial Plan';
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS plan_expires_at VARCHAR(100);
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS is_suspended INT DEFAULT 0;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_ip VARCHAR(100);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS device_fingerprint VARCHAR(255);
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS registration_ip VARCHAR(100);
            ALTER TABLE shops ADD COLUMN IF NOT EXISTS device_fingerprint VARCHAR(255);
            """)
            conn.commit()
            conn.close()

        # Always initialize local SQLite as backup mirror
        s_conn = self.get_sqlite_conn()
        s_cursor = s_conn.cursor()
        s_cursor.executescript("""
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
        s_conn.commit()

        for table_name, col_def in [
            ("shops", ("owner_id", "TEXT")), ("shops", ("api_key", "TEXT")), ("shops", ("owner_name", "TEXT")), 
            ("shops", ("email", "TEXT")), ("shops", ("phone", "TEXT")), ("shops", ("address", "TEXT")), 
            ("shops", ("bw_rate", "REAL DEFAULT 2.0")), ("shops", ("color_rate", "REAL DEFAULT 10.0")), 
            ("shops", ("duplex_discount", "REAL DEFAULT 0.5")), ("shops", ("paper_rates", "TEXT")),
            ("shops", ("subscription_status", "TEXT DEFAULT 'active'")),
            ("shops", ("plan_name", "TEXT DEFAULT 'Trial Plan'")),
            ("shops", ("plan_expires_at", "TEXT")),
            ("shops", ("is_suspended", "INTEGER DEFAULT 0")),
            ("shops", ("registration_ip", "TEXT")),
            ("shops", ("device_fingerprint", "TEXT")),
            ("users", ("registration_ip", "TEXT")),
            ("users", ("device_fingerprint", "TEXT"))
        ]:
            try:
                s_cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_def[0]} {col_def[1]};")
            except Exception:
                pass
        s_conn.commit()

        # Seed default plans if empty across SQLite
        try:
            s_cursor.execute("SELECT COUNT(*) FROM plans;")
            count = s_cursor.fetchone()[0]
            if count == 0:
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                default_plans = [
                    ("plan-1m", "1 Month Starter", 30, 199.0, "30 Days Unlimited Printing Access", now),
                    ("plan-3m", "3 Months Pro", 90, 499.0, "90 Days Unlimited Printing Access (Save 15%)", now),
                    ("plan-12m", "1 Year Enterprise", 365, 1499.0, "365 Days Unlimited Printing Access (Best Value)", now)
                ]
                for p in default_plans:
                    s_cursor.execute("INSERT INTO plans (plan_id, name, duration_days, price, description, created_at) VALUES (?, ?, ?, ?, ?, ?);", p)
                s_conn.commit()
        except Exception as e:
            print(f"[Database Warning] Error seeding SQLite default plans: {e}")
        finally:
            s_conn.close()

        # Seed Super Admin User (admin@qwikprint.in / @Qwikprint)
        try:
            import hashlib, binascii
            admin_email = os.getenv("SUPERADMIN_EMAIL", "admin@qwikprint.in").lower().strip()
            admin_pwd = os.getenv("SUPERADMIN_PASSWORD", "@Qwikprint")

            def _hash_pass(pwd):
                salt = b"qwikprint_secure_salt_2026"
                pwd_hash = hashlib.pbkdf2_hmac('sha256', pwd.encode('utf-8'), salt, 100000)
                return binascii.hexlify(pwd_hash).decode('ascii')

            admin_hash = _hash_pass(admin_pwd)
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Save admin to SQLite
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("SELECT user_id FROM users WHERE email = ?;", (admin_email,))
            row = s_cursor.fetchone()
            if not row:
                s_cursor.execute("""
                INSERT INTO users (user_id, email, password_hash, full_name, phone, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """, ("usr-superadmin", admin_email, admin_hash, "Super Admin", "9999999999", "super_admin", now))
            else:
                s_cursor.execute("""
                UPDATE users SET password_hash = ?, role = 'super_admin' WHERE email = ?;
                """, (admin_hash, admin_email))
            s_conn.commit()
            s_conn.close()

            print(f"[Database] Super Admin password and role updated for: {admin_email}")
        except Exception as e:
            print(f"[Database Warning] Could not seed super admin user: {e}")

    def get_plans(self):
        """
        Retrieves all configured pricing plans.
        Uses primary DB (PostgreSQL / Supabase) if connected, with automatic SQLite fallback & cross-sync!
        """
        conn, is_pg = self.get_connection()
        plans = []

        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
            query = "SELECT * FROM plans ORDER BY price ASC;"
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            plans = [dict(r) for r in rows]
        except Exception as e:
            print(f"[Database Warning] Error fetching plans from primary DB: {e}")

        # Fallback to local SQLite if primary returned empty or failed
        if not plans:
            try:
                s_conn = self.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("SELECT * FROM plans ORDER BY price ASC;")
                rows = s_cursor.fetchall()
                s_conn.close()
                plans = [dict(r) for r in rows]
            except Exception as e:
                print(f"[Database Error] SQLite fallback get_plans failed: {e}")

        return plans

    def save_plan(self, plan_data: dict) -> bool:
        """
        Saves or updates a subscription pricing plan in BOTH PostgreSQL (Supabase) and local SQLite.
        """
        plan_id = plan_data.get("plan_id") or f"plan-{uuid.uuid4().hex[:8]}"
        name = plan_data.get("name", "Custom Plan")
        duration_days = int(plan_data.get("duration_days", 30))
        price = float(plan_data.get("price", 0.0))
        description = plan_data.get("description", "")
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 1. Save to local SQLite (Guaranteed persistent mirror)
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            q_sqlite = """
            INSERT OR REPLACE INTO plans (plan_id, name, duration_days, price, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """
            s_cursor.execute(q_sqlite, (plan_id, name, duration_days, price, description, now))
            s_conn.commit()
            s_conn.close()
        except Exception as e:
            print(f"[Database Error] Failed saving plan to SQLite: {e}")

        # 2. Save to PostgreSQL / Supabase if connected
        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                q_pg = """
                INSERT INTO plans (plan_id, name, duration_days, price, description, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (plan_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    duration_days = EXCLUDED.duration_days,
                    price = EXCLUDED.price,
                    description = EXCLUDED.description;
                """
                cursor.execute(q_pg, (plan_id, name, duration_days, price, description, now))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Database Warning] Failed saving plan to PostgreSQL: {e}")

        return True

    def delete_plan(self, plan_id: str) -> bool:
        """
        Deletes a pricing plan from BOTH PostgreSQL and local SQLite.
        """
        # Delete from SQLite
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("DELETE FROM plans WHERE plan_id = ?;", (plan_id,))
            s_conn.commit()
            s_conn.close()
        except Exception as e:
            print(f"[Database Error] SQLite delete_plan failed: {e}")

        # Delete from PostgreSQL
        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM plans WHERE plan_id = %s;", (plan_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Database Warning] PostgreSQL delete_plan failed: {e}")

        return True

    def update_shop_subscription(self, shop_id: str, duration_days: int, plan_name: str = None) -> dict:
        """
        Extends/updates a shop's active subscription in BOTH PostgreSQL and SQLite.
        """
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        
        # Check current expiration
        current_exp = None
        user_shop = self.get_shop_by_id(shop_id)
        if user_shop and user_shop.get("plan_expires_at"):
            try:
                exp_dt = datetime.datetime.fromisoformat(user_shop["plan_expires_at"])
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
                if exp_dt > now_dt:
                    current_exp = exp_dt
            except Exception:
                pass

        start_base = current_exp if current_exp else now_dt
        new_exp_dt = start_base + datetime.timedelta(days=duration_days)
        new_exp_str = new_exp_dt.isoformat()
        
        actual_plan_name = plan_name or f"{duration_days} Days Plan"

        # Update SQLite
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("""
            UPDATE shops SET 
                subscription_status = 'active',
                plan_name = ?,
                plan_expires_at = ?,
                is_suspended = 0
            WHERE shop_id = ?;
            """, (actual_plan_name, new_exp_str, shop_id))
            s_conn.commit()
            s_conn.close()
        except Exception as e:
            print(f"[Database Error] SQLite update_shop_subscription failed: {e}")

        # Update PostgreSQL
        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE shops SET 
                    subscription_status = 'active',
                    plan_name = %s,
                    plan_expires_at = %s,
                    is_suspended = 0
                WHERE shop_id = %s;
                """, (actual_plan_name, new_exp_str, shop_id))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Database Warning] PostgreSQL update_shop_subscription failed: {e}")

        return {
            "success": True,
            "shop_id": shop_id,
            "plan_name": actual_plan_name,
            "plan_expires_at": new_exp_str,
            "is_active": True
        }

    def get_shop_by_id(self, shop_id: str):
        conn, is_pg = self.get_connection()
        shop = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
            query = "SELECT * FROM shops WHERE shop_id = %s;" if is_pg else "SELECT * FROM shops WHERE shop_id = ?;"
            cursor.execute(query, (shop_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                shop = dict(row)
        except Exception as e:
            print(f"[Database Warning] PostgreSQL get_shop_by_id failed: {e}")

        if not shop:
            try:
                s_conn = self.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("SELECT * FROM shops WHERE shop_id = ?;", (shop_id,))
                row = s_cursor.fetchone()
                s_conn.close()
                if row:
                    shop = dict(row)
            except Exception as e:
                print(f"[Database Error] SQLite get_shop_by_id failed: {e}")

        return shop

    def get_all_shops(self):
        conn, is_pg = self.get_connection()
        shops = []
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
            cursor.execute("SELECT * FROM shops ORDER BY created_at DESC;")
            rows = cursor.fetchall()
            conn.close()
            shops = [dict(r) for r in rows]
        except Exception:
            pass

        if not shops:
            try:
                s_conn = self.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("SELECT * FROM shops ORDER BY created_at DESC;")
                rows = s_cursor.fetchall()
                s_conn.close()
                shops = [dict(r) for r in rows]
            except Exception:
                pass

        return shops

    def create_user_and_shop(self, email: str, password_hash: str, full_name: str = "", phone: str = "", shop_name: str = "", registration_ip: str = "", device_fingerprint: str = ""):
        conn, is_pg = self.get_connection()
        user_id = f"usr-{uuid.uuid4().hex[:8]}"
        shop_id = f"shop-{uuid.uuid4().hex[:8]}"
        api_key = f"QWIK_KEY_{shop_id}_{uuid.uuid4().hex[:6].upper()}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        trial_exp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)).isoformat()

        user_data = {
            "user_id": user_id, "email": email, "password_hash": password_hash,
            "full_name": full_name or "Shop Owner", "phone": phone or "N/A", "role": "shop_owner", "created_at": now
        }
        shop_data = {
            "shop_id": shop_id, "owner_id": user_id, "api_key": api_key, "name": shop_name or "My Print Shop",
            "owner_name": full_name or "Shop Owner", "email": email, "phone": phone or "N/A",
            "address": "Main Xerox Counter", "bw_rate": 2.0, "color_rate": 10.0, "duplex_discount": 0.5,
            "created_at": now, "subscription_status": "active", "plan_name": "7-Day Free Trial", "plan_expires_at": trial_exp
        }

        # Save to SQLite
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("INSERT INTO users (user_id, email, password_hash, full_name, phone, role, created_at, registration_ip, device_fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                             (user_id, email, password_hash, user_data["full_name"], user_data["phone"], "shop_owner", now, registration_ip, device_fingerprint))
            s_cursor.execute("INSERT INTO shops (shop_id, owner_id, api_key, name, owner_name, email, phone, address, bw_rate, color_rate, duplex_discount, created_at, subscription_status, plan_name, plan_expires_at, registration_ip, device_fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                             (shop_id, user_id, api_key, shop_data["name"], shop_data["owner_name"], email, shop_data["phone"], shop_data["address"], 2.0, 10.0, 0.5, now, "active", "7-Day Free Trial", trial_exp, registration_ip, device_fingerprint))
            s_conn.commit()
            s_conn.close()
        except Exception as e:
            print(f"[Database Error] SQLite create_user_and_shop failed: {e}")

        # Save to PostgreSQL
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (user_id, email, password_hash, full_name, phone, role, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s);",
                               (user_id, email, password_hash, user_data["full_name"], user_data["phone"], "shop_owner", now))
                cursor.execute("INSERT INTO shops (shop_id, owner_id, api_key, name, owner_name, email, phone, address, bw_rate, color_rate, duplex_discount, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                               (shop_id, user_id, api_key, shop_data["name"], shop_data["owner_name"], email, shop_data["phone"], shop_data["address"], 2.0, 10.0, 0.5, now))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Database Warning] PostgreSQL create_user_and_shop failed: {e}")

        return user_data, shop_data

    def get_user_by_email(self, email: str):
        conn, is_pg = self.get_connection()
        user = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
            query = "SELECT * FROM users WHERE LOWER(email) = %s;" if is_pg else "SELECT * FROM users WHERE LOWER(email) = ?;"
            cursor.execute(query, (email.lower().strip(),))
            row = cursor.fetchone()
            conn.close()
            if row:
                user = dict(row)
        except Exception:
            pass

        if not user:
            try:
                s_conn = self.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?;", (email.lower().strip(),))
                row = s_cursor.fetchone()
                s_conn.close()
                if row:
                    user = dict(row)
            except Exception:
                pass

        return user

    def get_user_shop(self, user_id: str):
        conn, is_pg = self.get_connection()
        shop = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
            query = "SELECT * FROM shops WHERE owner_id = %s;" if is_pg else "SELECT * FROM shops WHERE owner_id = ?;"
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                shop = dict(row)
        except Exception:
            pass

        if not shop:
            try:
                s_conn = self.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("SELECT * FROM shops WHERE owner_id = ?;", (user_id,))
                row = s_cursor.fetchone()
                s_conn.close()
                if row:
                    shop = dict(row)
            except Exception:
                pass

        return shop

    def is_ip_or_device_registered(self, ip: str, device_fp: str):
        if not ip and not device_fp:
            return False, ""
        s_conn = self.get_sqlite_conn()
        s_cursor = s_conn.cursor()
        s_cursor.execute("SELECT email FROM users WHERE (registration_ip = ? AND registration_ip != '127.0.0.1') OR (device_fingerprint = ? AND device_fingerprint != '');", (ip, device_fingerprint))
        row = s_cursor.fetchone()
        s_conn.close()
        if row:
            return True, row["email"]
        return False, ""

    def get_shop_jobs(self, shop_id: str, limit: int = 50):
        conn, is_pg = self.get_connection()
        jobs = []
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
            query = "SELECT * FROM print_jobs WHERE shop_id = %s ORDER BY created_at DESC LIMIT %s;" if is_pg else "SELECT * FROM print_jobs WHERE shop_id = ? ORDER BY created_at DESC LIMIT ?;"
            cursor.execute(query, (shop_id, limit))
            rows = cursor.fetchall()
            conn.close()
            jobs = [dict(r) for r in rows]
        except Exception:
            pass

        if not jobs:
            try:
                s_conn = self.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("SELECT * FROM print_jobs WHERE shop_id = ? ORDER BY created_at DESC LIMIT ?;", (shop_id, limit))
                rows = s_cursor.fetchall()
                s_conn.close()
                jobs = [dict(r) for r in rows]
            except Exception:
                pass

        return jobs

    def create_print_job(self, job_data: dict) -> str:
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Save to SQLite
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("""
            INSERT INTO print_jobs (
                job_id, shop_id, device_id, original_filename, file_path,
                page_count, copies, color_mode, duplex, page_range,
                payment_method, payment_status, total_cost, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                job_id, job_data["shop_id"], job_data.get("device_id", ""), job_data["original_filename"],
                job_data["file_path"], job_data.get("page_count", 1), job_data.get("copies", 1),
                job_data.get("color_mode", "bw"), job_data.get("duplex", "single"), job_data.get("page_range", "all"),
                job_data.get("payment_method", "cash"), job_data.get("payment_status", "pending"),
                job_data.get("total_cost", 0.0), job_data.get("status", "PAYMENT_PENDING"), now, now
            ))
            s_conn.commit()
            s_conn.close()
        except Exception as e:
            print(f"[Database Error] SQLite create_print_job failed: {e}")

        # Save to PostgreSQL if connected
        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO print_jobs (
                    job_id, shop_id, device_id, original_filename, file_path,
                    page_count, copies, color_mode, duplex, page_range,
                    payment_method, payment_status, total_cost, status, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    job_id, job_data["shop_id"], job_data.get("device_id", ""), job_data["original_filename"],
                    job_data["file_path"], job_data.get("page_count", 1), job_data.get("copies", 1),
                    job_data.get("color_mode", "bw"), job_data.get("duplex", "single"), job_data.get("page_range", "all"),
                    job_data.get("payment_method", "cash"), job_data.get("payment_status", "pending"),
                    job_data.get("total_cost", 0.0), job_data.get("status", "PAYMENT_PENDING"), now, now
                ))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Database Warning] PostgreSQL create_print_job failed: {e}")

        return job_id

    def update_job_status(self, job_id: str, status: str, payment_status: str = None, error: str = None):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Update SQLite
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            if payment_status and error:
                s_cursor.execute("UPDATE print_jobs SET status = ?, payment_status = ?, error = ?, updated_at = ? WHERE job_id = ?;", (status, payment_status, error, now, job_id))
            elif payment_status:
                s_cursor.execute("UPDATE print_jobs SET status = ?, payment_status = ?, updated_at = ? WHERE job_id = ?;", (status, payment_status, now, job_id))
            else:
                s_cursor.execute("UPDATE print_jobs SET status = ?, updated_at = ? WHERE job_id = ?;", (status, now, job_id))
            s_conn.commit()
            s_conn.close()
        except Exception as e:
            print(f"[Database Error] SQLite update_job_status failed: {e}")

        # Update PostgreSQL
        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                if payment_status and error:
                    cursor.execute("UPDATE print_jobs SET status = %s, payment_status = %s, error = %s, updated_at = %s WHERE job_id = %s;", (status, payment_status, error, now, job_id))
                elif payment_status:
                    cursor.execute("UPDATE print_jobs SET status = %s, payment_status = %s, updated_at = %s WHERE job_id = %s;", (status, payment_status, now, job_id))
                else:
                    cursor.execute("UPDATE print_jobs SET status = %s, updated_at = %s WHERE job_id = %s;", (status, now, job_id))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Database Warning] PostgreSQL update_job_status failed: {e}")

    def update_shop_pricing(self, shop_id: str, bw_rate: float, color_rate: float, duplex_discount: float):
        # Update SQLite
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("UPDATE shops SET bw_rate = ?, color_rate = ?, duplex_discount = ? WHERE shop_id = ?;", (bw_rate, color_rate, duplex_discount, shop_id))
            s_conn.commit()
            s_conn.close()
        except Exception:
            pass

        # Update PostgreSQL
        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE shops SET bw_rate = %s, color_rate = %s, duplex_discount = %s WHERE shop_id = %s;", (bw_rate, color_rate, duplex_discount, shop_id))
                conn.commit()
                conn.close()
            except Exception:
                pass

    def get_shop_paper_rates(self, shop_id: str):
        shop = self.get_shop_by_id(shop_id)
        if shop and shop.get("paper_rates"):
            try:
                return json.loads(shop["paper_rates"])
            except Exception:
                pass
        return [
            {"size": "A4", "bw_rate": shop.get("bw_rate", 2.0) if shop else 2.0, "color_rate": shop.get("color_rate", 10.0) if shop else 10.0},
            {"size": "A3", "bw_rate": 5.0, "color_rate": 20.0},
            {"size": "Legal", "bw_rate": 3.0, "color_rate": 12.0}
        ]

    def update_shop_paper_rates(self, shop_id: str, rates: list):
        rates_json = json.dumps(rates)
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("UPDATE shops SET paper_rates = ? WHERE shop_id = ?;", (rates_json, shop_id))
            s_conn.commit()
            s_conn.close()
        except Exception:
            pass

        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE shops SET paper_rates = %s WHERE shop_id = %s;", (rates_json, shop_id))
                conn.commit()
                conn.close()
            except Exception:
                pass

    def update_shop_details(self, shop_id: str, name: str, owner_name: str, phone: str, address: str, email: str):
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("UPDATE shops SET name = ?, owner_name = ?, phone = ?, address = ?, email = ? WHERE shop_id = ?;", (name, owner_name, phone, address, email, shop_id))
            s_conn.commit()
            s_conn.close()
        except Exception:
            pass

        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE shops SET name = %s, owner_name = %s, phone = %s, address = %s, email = %s WHERE shop_id = %s;", (name, owner_name, phone, address, email, shop_id))
                conn.commit()
                conn.close()
            except Exception:
                pass

    def regenerate_shop_api_key(self, shop_id: str) -> str:
        new_key = f"QWIK_KEY_{shop_id}_{uuid.uuid4().hex[:6].upper()}"
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("UPDATE shops SET api_key = ? WHERE shop_id = ?;", (new_key, shop_id))
            s_cursor.execute("DELETE FROM devices WHERE shop_id = ?;", (shop_id,))
            s_conn.commit()
            s_conn.close()
        except Exception:
            pass

        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE shops SET api_key = %s WHERE shop_id = %s;", (new_key, shop_id))
                cursor.execute("DELETE FROM devices WHERE shop_id = %s;", (shop_id,))
                conn.commit()
                conn.close()
            except Exception:
                pass

        return new_key

    def verify_shop_active_subscription(self, shop_id: str):
        if not shop_id:
            return True, "Active", ""
        
        shop = self.get_shop_by_id(shop_id)
        if not shop:
            return True, "Active", ""

        if shop.get("is_suspended"):
            return False, "Shop account suspended by Super Admin", shop.get("plan_expires_at", "")

        exp_str = shop.get("plan_expires_at", "")
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

    def get_shop_by_api_key(self, api_key: str):
        conn, is_pg = self.get_connection()
        shop = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
            cursor.execute("SELECT * FROM shops WHERE api_key = %s;" if is_pg else "SELECT * FROM shops WHERE api_key = ?;", (api_key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                shop = dict(row)
        except Exception:
            pass

        if not shop:
            try:
                s_conn = self.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("SELECT * FROM shops WHERE api_key = ?;", (api_key,))
                row = s_cursor.fetchone()
                s_conn.close()
                if row:
                    shop = dict(row)
            except Exception:
                pass

        return shop

    def get_shop_devices(self, shop_id: str):
        conn, is_pg = self.get_connection()
        devices = []
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
            cursor.execute("SELECT * FROM devices WHERE shop_id = %s;" if is_pg else "SELECT * FROM devices WHERE shop_id = ?;", (shop_id,))
            rows = cursor.fetchall()
            conn.close()
            devices = [dict(r) for r in rows]
        except Exception:
            pass

        if not devices:
            try:
                s_conn = self.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("SELECT * FROM devices WHERE shop_id = ?;", (shop_id,))
                rows = s_cursor.fetchall()
                s_conn.close()
                devices = [dict(r) for r in rows]
            except Exception:
                pass

        return devices

    def get_device(self, device_id: str):
        conn, is_pg = self.get_connection()
        device = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor) if is_pg else conn.cursor()
            cursor.execute("SELECT * FROM devices WHERE device_id = %s;" if is_pg else "SELECT * FROM devices WHERE device_id = ?;", (device_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                device = dict(row)
        except Exception:
            pass

        if not device:
            try:
                s_conn = self.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("SELECT * FROM devices WHERE device_id = ?;", (device_id,))
                row = s_cursor.fetchone()
                s_conn.close()
                if row:
                    device = dict(row)
            except Exception:
                pass

        return device

    def register_device(self, shop_id: str, device_name: str = "Windows Desktop PC"):
        device_id = f"dev-{uuid.uuid4().hex[:8]}"
        secret_token = f"tok-{uuid.uuid4().hex[:16]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("INSERT INTO devices (device_id, shop_id, device_name, secret_token, status, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                             (device_id, shop_id, device_name, secret_token, "active", now))
            s_conn.commit()
            s_conn.close()
        except Exception:
            pass

        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO devices (device_id, shop_id, device_name, secret_token, status, created_at) VALUES (%s, %s, %s, %s, %s, %s);",
                               (device_id, shop_id, device_name, secret_token, "active", now))
                conn.commit()
                conn.close()
            except Exception:
                pass

        return {"device_id": device_id, "secret_token": secret_token}

    def delete_shop_completely(self, shop_id: str):
        shop = self.get_shop_by_id(shop_id)
        owner_id = shop.get("owner_id") if shop else None

        # Delete from SQLite
        try:
            s_conn = self.get_sqlite_conn()
            s_cursor = s_conn.cursor()
            s_cursor.execute("DELETE FROM print_jobs WHERE shop_id = ?;", (shop_id,))
            s_cursor.execute("DELETE FROM devices WHERE shop_id = ?;", (shop_id,))
            s_cursor.execute("DELETE FROM subscriptions WHERE shop_id = ?;", (shop_id,))
            s_cursor.execute("DELETE FROM shops WHERE shop_id = ?;", (shop_id,))
            if owner_id:
                s_cursor.execute("DELETE FROM users WHERE user_id = ?;", (owner_id,))
            s_conn.commit()
            s_conn.close()
        except Exception as e:
            print(f"[Database Error] SQLite delete_shop_completely failed: {e}")

        # Delete from PostgreSQL
        conn, is_pg = self.get_connection()
        if is_pg:
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM print_jobs WHERE shop_id = %s;", (shop_id,))
                cursor.execute("DELETE FROM devices WHERE shop_id = %s;", (shop_id,))
                cursor.execute("DELETE FROM subscriptions WHERE shop_id = %s;", (shop_id,))
                cursor.execute("DELETE FROM shops WHERE shop_id = %s;", (shop_id,))
                if owner_id:
                    cursor.execute("DELETE FROM users WHERE user_id = %s;", (owner_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Database Warning] PostgreSQL delete_shop_completely failed: {e}")

        return True

db = SupabaseDatabase()

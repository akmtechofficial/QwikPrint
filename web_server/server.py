import os
import time
import glob
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web_server.routes.customer import router as customer_router
from web_server.routes.shop import router as shop_router
from web_server.routes.auth import router as auth_router
from web_server.routes.agent_api import router as agent_router
from web_server.routes.admin import router as admin_router
from web_server.routes.payment import router as payment_router
from web_server.database import db

app = FastAPI(title="QwikPrint 100% Pure Python Print Server", version="1.0.0")

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Double Slash URL Cleaner Middleware
@app.middleware("http")
async def clean_double_slash_middleware(request, call_next):
    path = request.url.path
    if "//" in path:
        import re
        clean_path = re.sub(r"/+", "/", path)
        query = request.url.query
        target = f"{clean_path}?{query}" if query else clean_path
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=target, status_code=307)
    return await call_next(request)

# Simple In-Memory IP Rate Limiter
IP_REQUEST_LOG = {}
RATE_LIMIT_MAX_REQUESTS = 120  # per minute
RATE_LIMIT_WINDOW = 60         # seconds

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    
    # Clean up old window logs periodically
    if client_ip in IP_REQUEST_LOG:
        timestamps = [t for t in IP_REQUEST_LOG[client_ip] if now - t < RATE_LIMIT_WINDOW]
        IP_REQUEST_LOG[client_ip] = timestamps
        if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Too many requests. Please rate limit your requests."}, status_code=429)
    else:
        IP_REQUEST_LOG[client_ip] = []
        
    IP_REQUEST_LOG[client_ip].append(now)
    return await call_next(request)

# Mount Static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
uploads_dir = os.path.join(static_dir, "uploads")
private_uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "private_uploads"))

os.makedirs(uploads_dir, exist_ok=True)
os.makedirs(private_uploads_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Routers
app.include_router(customer_router)
app.include_router(shop_router)
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(admin_router)
app.include_router(payment_router)

async def auto_purge_expired_files_task():
    """
    Mandatory File Security & Privacy Lifecycle Daemon:
    Runs every 60 seconds to automatically delete print files from private_uploads & static/uploads:
    1. Older than 10 minutes (600s) AND NOT associated with an active job.
    2. Older than 2 hours (7200s) even if pending payment.
    """
    print("[File Lifecycle Daemon] Auto-cleanup worker active (Active-Job Protection Policy).")
    while True:
        try:
            now = time.time()
            soft_purge_seconds = 600    # 10 minutes for finished/orphaned files
            hard_purge_seconds = 7200   # 2 hours absolute limit

            try:
                active_basenames = db.get_active_file_paths()
            except Exception as db_err:
                print(f"[Auto Purge Warning] Could not fetch active jobs from DB: {db_err}. Skipping purge cycle to protect active files.")
                await asyncio.sleep(60)
                continue

            target_dirs = [private_uploads_dir, uploads_dir]
            for target_dir in target_dirs:
                if os.path.exists(target_dir):
                    for file_path in glob.glob(os.path.join(target_dir, "*")):
                        if os.path.isfile(file_path):
                            basename = os.path.basename(file_path).lower()
                            file_age = now - os.path.getmtime(file_path)
                            is_active = basename in active_basenames

                            if (not is_active and file_age > soft_purge_seconds) or (file_age > hard_purge_seconds):
                                try:
                                    os.remove(file_path)
                                    print(f"[Auto Purge] Permanently deleted file ({int(file_age)}s old, active={is_active}): {os.path.basename(file_path)}")
                                except Exception as e:
                                    print(f"[Auto Purge Warning] Could not remove {file_path}: {e}")
        except Exception as err:
            print(f"[Auto Purge Daemon Error] {err}")

        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    # Production Mode Startup Requirements Check (P0 Security Guarantee)
    if os.getenv("ENVIRONMENT", "").lower() in ("production", "prod"):
        sec = os.getenv("SESSION_SECRET")
        if not sec or len(sec) < 16 or sec in ("qwikprint_super_secret_session_key_2026", "secret"):
            raise RuntimeError("P0 Startup Security Error: High-entropy SESSION_SECRET environment variable is required in production mode.")
        
        pf_key = os.getenv("PAYFLUX_SECRET_KEY") or os.getenv("PAYFLUX_API_KEY")
        if not pf_key or "sk_test_your" in pf_key or pf_key == "sk_test_your_merchant_secret_key":
            raise RuntimeError("P0 Startup Security Error: Valid PAYFLUX_SECRET_KEY environment variable is required in production mode.")

        pwd = os.getenv("SUPERADMIN_PASSWORD")
        if not pwd or pwd in ("@Qwikprint", "admin", "123456"):
            raise RuntimeError("P0 Startup Security Error: Strong SUPERADMIN_PASSWORD environment variable is required in production mode.")

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError("P0 Startup Security Error: DATABASE_URL environment variable is required in production mode.")

    # Start periodic file cleanup task in background
    asyncio.create_task(auto_purge_expired_files_task())

@app.get("/health")
async def health():
    return {"status": "ok", "app": "QwikPrint Pure Python Engine", "file_retention_policy": "10_minutes_max"}

if __name__ == "__main__":
    is_dev = "--dev" in sys.argv or "--reload" in sys.argv or os.getenv("QWIKPRINT_ENV", "").lower() in ("dev", "development")
    uvicorn.run("web_server.server:app", host="0.0.0.0", port=8000, reload=is_dev)


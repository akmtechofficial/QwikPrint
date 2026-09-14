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
from web_server.database import db

app = FastAPI(title="QwikPrint 100% Pure Python Print Server", version="1.0.0")

# Mount Static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
uploads_dir = os.path.join(static_dir, "uploads")
os.makedirs(uploads_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Routers
app.include_router(customer_router)
app.include_router(shop_router)
app.include_router(auth_router)
app.include_router(agent_router)

async def auto_purge_expired_files_task():
    """
    Mandatory File Security & Privacy Lifecycle Daemon:
    Runs every 60 seconds to automatically delete print files:
    1. Older than 10 minutes (600s) AND NOT associated with an active job (PAYMENT_PENDING, QUEUED, CLAIMED, PRINTING).
    2. Older than 2 hours (7200s) even if pending payment (prevents disk bloat from abandoned requests).
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
                print(f"[Auto Purge Warning] Could not fetch active jobs: {db_err}")
                active_basenames = set()

            if os.path.exists(uploads_dir):
                for file_path in glob.glob(os.path.join(uploads_dir, "*")):
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
    # Start periodic file cleanup task in background
    asyncio.create_task(auto_purge_expired_files_task())

@app.get("/health")
async def health():
    return {"status": "ok", "app": "QwikPrint Pure Python Engine", "file_retention_policy": "10_minutes_max"}

if __name__ == "__main__":
    is_dev = "--dev" in sys.argv or "--reload" in sys.argv or os.getenv("QWIKPRINT_ENV", "").lower() in ("dev", "development")
    uvicorn.run("web_server.server:app", host="0.0.0.0", port=8000, reload=is_dev)


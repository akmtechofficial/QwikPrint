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
    Runs every 60 seconds to automatically delete all uploaded print files
    that are older than 10 minutes (600 seconds) from server storage.
    """
    print("[File Lifecycle Daemon] Auto-cleanup worker active (10-Minute Purge Policy).")
    while True:
        try:
            now = time.time()
            max_age_seconds = 600 # 10 Minutes

            if os.path.exists(uploads_dir):
                for file_path in glob.glob(os.path.join(uploads_dir, "*")):
                    if os.path.isfile(file_path):
                        file_age = now - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            try:
                                os.remove(file_path)
                                print(f"[Auto Purge 10m] Permanently deleted expired print file ({int(file_age)}s old): {os.path.basename(file_path)}")
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
    uvicorn.run("web_server.server:app", host="0.0.0.0", port=8000, reload=True)

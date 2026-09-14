from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from web_server.database import db
import os

router = APIRouter()

def validate_agent_auth(x_device_id: str = Header(None), x_device_token: str = Header(None)):
    if not x_device_id or not x_device_token:
        raise HTTPException(status_code=401, detail="Authentication headers X-Device-Id and X-Device-Token are required")
    
    device = db.get_device(x_device_id)
    if not device or device["secret_token"] != x_device_token:
        raise HTTPException(status_code=401, detail="Unauthorized device credentials")
    
    if device.get("status", "active").lower() in ["disabled", "revoked"]:
        raise HTTPException(status_code=403, detail="Device has been disabled by shop owner. Printing stopped.")
    
    return device

@router.get("/api/agent/version-check")
async def version_check(current_version: str = "1.0.0"):
    latest_version = "4.0.5"
    return {
        "success": True,
        "currentVersion": current_version,
        "latestVersion": latest_version,
        "updateAvailable": current_version != latest_version,
        "downloadUrl": "https://github.com/akmtechofficial/QwikPrint/releases/latest"
    }

@router.post("/api/agent/verify-key")
async def verify_api_key(request: Request, payload: dict):
    """Verifies Shopkeeper API Key and binds 1 API Key to 1 PC Desktop Agent."""
    api_key = payload.get("apiKey", "").strip()
    if not api_key:
        return JSONResponse({"success": False, "error": "API Key is required"}, status_code=400)

    shop = db.get_shop_by_api_key(api_key)
    if not shop:
        return JSONResponse({"success": False, "error": "Invalid API Key. Please copy your Secret Key from your Web Dashboard."}, status_code=404)

    shop_id = shop["shop_id"]
    devices = db.get_shop_devices(shop_id)
    
    if devices:
        device = devices[0]
        device_id = device["device_id"]
        secret_token = device["secret_token"]
    else:
        creds = db.register_device(shop_id, "Windows Desktop PC")
        device_id = creds["device_id"]
        secret_token = creds["secret_token"]

    base_url = str(request.base_url).rstrip("/")
    return {
        "success": True,
        "shopId": shop_id,
        "shopName": shop["name"],
        "deviceId": device_id,
        "deviceToken": secret_token,
        "bwRate": shop.get("bw_rate", 2.0),
        "colorRate": shop.get("color_rate", 10.0),
        "duplexDiscount": shop.get("duplex_discount", 0.5),
        "serverUrl": base_url,
        "message": f"Successfully paired with '{shop['name']}' (1 API Key = 1 PC License Active)!"
    }

@router.get("/api/agent/paper-rates")
async def get_agent_paper_rates(shop_id: str, x_device_id: str = Header(None), x_device_token: str = Header(None)):
    validate_agent_auth(x_device_id, x_device_token)
    rates = db.get_shop_paper_rates(shop_id)
    return {"success": True, "paperRates": rates}

@router.post("/api/agent/paper-rates")
async def update_agent_paper_rates(payload: dict, x_device_id: str = Header(None), x_device_token: str = Header(None)):
    validate_agent_auth(x_device_id, x_device_token)
    shop_id = payload.get("shopId")
    paper_rates = payload.get("paperRates", [])
    if not shop_id:
        raise HTTPException(status_code=400, detail="shopId is required")
    if len(paper_rates) > 5:
        return JSONResponse({"success": False, "error": "Maximum 5 paper sizes allowed"}, status_code=400)
    
    updated = db.update_shop_paper_rates(shop_id, paper_rates)
    return {"success": True, "message": "Paper sizes & rates updated successfully!", "paperRates": updated}

@router.post("/api/agent/heartbeat")
async def heartbeat(payload: dict, x_device_id: str = Header(None), x_device_token: str = Header(None)):
    device = validate_agent_auth(x_device_id, x_device_token)
    db.update_device_last_seen(device["device_id"])
    return {"success": True, "status": "online"}

@router.get("/api/agent/queue")
async def fetch_queue(request: Request, x_device_id: str = Header(None), x_device_token: str = Header(None)):
    device = validate_agent_auth(x_device_id, x_device_token)
    shop_id = device["shop_id"]
    
    queued, pending_cash = db.get_queued_and_pending_jobs(shop_id)

    formatted_queued = []
    for q in queued:
        formatted_queued.append({
            "jobId": q["job_id"],
            "shopId": q["shop_id"],
            "status": q["status"],
            "file": {"originalName": q["original_filename"], "pageCount": q["page_count"]},
            "printOptions": {"copies": q["copies"], "colorMode": q["color_mode"], "duplex": q["duplex"], "pageRange": q["page_range"]},
            "pricing": {"totalCost": q["total_cost"]},
            "createdAt": q["created_at"]
        })

    formatted_cash = []
    for c in pending_cash:
        formatted_cash.append({
            "jobId": c["job_id"],
            "shopId": c["shop_id"],
            "status": c["status"],
            "file": {"originalName": c["original_filename"], "pageCount": c["page_count"]},
            "printOptions": {"copies": c["copies"], "colorMode": c["color_mode"], "duplex": c["duplex"], "pageRange": c["page_range"]},
            "pricing": {"totalCost": c["total_cost"]},
            "createdAt": c["created_at"]
        })

    return {
        "success": True,
        "jobs": formatted_queued,
        "cashPendingJobs": formatted_cash
    }

@router.post("/api/agent/claim-job")
async def claim_job(payload: dict, x_device_id: str = Header(None), x_device_token: str = Header(None)):
    device = validate_agent_auth(x_device_id, x_device_token)
    job_id = payload.get("jobId")
    if not job_id:
        raise HTTPException(status_code=400, detail="jobId required")

    success, job = db.claim_job(job_id, device["device_id"])
    if not success:
        return JSONResponse({"error": "Job already claimed or not queued"}, status_code=409)

    return {"success": True, "job": job}

@router.get("/api/agent/download-url")
@router.post("/api/agent/download-url")
async def get_download_url(request: Request, jobId: str = None, payload: dict = None, x_device_id: str = Header(None), x_device_token: str = Header(None)):
    validate_agent_auth(x_device_id, x_device_token)
    j_id = jobId or (payload.get("jobId") if payload else None)
    if not j_id:
        raise HTTPException(status_code=400, detail="jobId required")
    
    base_url = str(request.base_url).rstrip("/")
    file_download_url = f"{base_url}/api/agent/download-file/{j_id}"
    return {"success": True, "downloadUrl": file_download_url}

@router.get("/api/agent/download-file/{job_id}")
async def download_file(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job record not found")
    
    file_path = job.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        filename = os.path.basename(file_path)
        alt_path = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", filename)
        if os.path.exists(alt_path):
            file_path = alt_path

    if not file_path or not os.path.exists(file_path):
        print(f"[Download 404] File for job {job_id} not found at {file_path}")
        raise HTTPException(status_code=404, detail="Print file not found on server")

    return FileResponse(
        path=file_path,
        filename=job["original_filename"],
        media_type="application/octet-stream"
    )

@router.post("/api/agent/update-status")
async def update_status(payload: dict, x_device_id: str = Header(None), x_device_token: str = Header(None)):
    validate_agent_auth(x_device_id, x_device_token)
    job_id = payload.get("jobId")
    status = payload.get("status")
    error = payload.get("error")
    
    if not job_id or not status:
        raise HTTPException(status_code=400, detail="jobId and status required")

    db.update_job_status(job_id, status, error)

    # File lifecycle: Auto-delete print file from disk immediately post successful printing or cancellation
    if status.upper() in ["PRINTED", "CANCELLED", "EXPIRED"]:
        job = db.get_job(job_id)
        if job and job.get("file_path"):
            fp = job["file_path"]
            if not os.path.exists(fp):
                fp = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", os.path.basename(fp))
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                    print(f"[File Lifecycle] Auto-deleted temporary file ({status}): {fp}")
                except Exception as clean_err:
                    print(f"[File Lifecycle Warning] Could not remove file: {clean_err}")

    return {"success": True, "status": status}

@router.post("/api/jobs/{job_id}/confirm-cash")
async def confirm_cash(request: Request, job_id: str, x_device_id: str = Header(None), x_device_token: str = Header(None)):
    # Authenticate via Device token OR session cookie
    if x_device_id and x_device_token:
        validate_agent_auth(x_device_id, x_device_token)
    else:
        from web_server.auth import get_current_user_and_shop
        user, shop = get_current_user_and_shop(request)
        if not user or not shop:
            raise HTTPException(status_code=401, detail="Unauthorized shopkeeper session")
            
    db.confirm_cash_payment(job_id)
    return {"success": True, "message": "Cash payment confirmed!"}

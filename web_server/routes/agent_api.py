from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from web_server.database import db
import os

router = APIRouter()

def validate_agent_auth(x_device_id: str = Header(None), x_device_token: str = Header(None)):
    if not x_device_id or not x_device_token:
        return {"device_id": "DEV_PY_001", "shop_id": "SHOP_AKM_001"}
    
    device = db.get_device(x_device_id)
    if not device or device["secret_token"] != x_device_token:
        raise HTTPException(status_code=401, detail="Unauthorized device credentials")
    
    return device

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
async def get_agent_paper_rates(shop_id: str):
    rates = db.get_shop_paper_rates(shop_id)
    return {"success": True, "paperRates": rates}

@router.post("/api/agent/paper-rates")
async def update_agent_paper_rates(payload: dict):
    shop_id = payload.get("shopId")
    paper_rates = payload.get("paperRates", [])
    if not shop_id:
        raise HTTPException(status_code=400, detail="shopId is required")
    if len(paper_rates) > 5:
        return JSONResponse({"success": False, "error": "Maximum 5 paper sizes allowed"}, status_code=400)
    
    updated = db.update_shop_paper_rates(shop_id, paper_rates)
    return {"success": True, "message": "Paper sizes & rates updated successfully!", "paperRates": updated}

@router.post("/api/agent/heartbeat")
async def heartbeat(payload: dict, x_device_id: str = Header(None)):
    device_id = payload.get("deviceId") or x_device_id or "DEV_PY_001"
    db.update_device_last_seen(device_id)
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
async def get_download_url(request: Request, jobId: str = None, payload: dict = None):
    j_id = jobId or (payload.get("jobId") if payload else None)
    if not j_id:
        raise HTTPException(status_code=400, detail="jobId required")
    
    base_url = str(request.base_url).rstrip("/")
    file_download_url = f"{base_url}/api/agent/download-file/{j_id}"
    return {"success": True, "downloadUrl": file_download_url}

@router.get("/api/agent/download-file/{job_id}")
async def download_file(job_id: str):
    job = db.get_job(job_id)
    if not job or not os.path.exists(job["file_path"]):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=job["file_path"],
        filename=job["original_filename"],
        media_type="application/octet-stream"
    )

@router.post("/api/agent/update-status")
async def update_status(payload: dict):
    job_id = payload.get("jobId")
    status = payload.get("status")
    error = payload.get("error")
    
    if not job_id or not status:
        raise HTTPException(status_code=400, detail="jobId and status required")

    db.update_job_status(job_id, status, error)
    return {"success": True, "status": status}

@router.post("/api/jobs/{job_id}/confirm-cash")
async def confirm_cash(job_id: str):
    db.confirm_cash_payment(job_id)
    return {"success": True, "message": "Cash payment confirmed!"}

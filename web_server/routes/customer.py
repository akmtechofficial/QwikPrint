import os
import uuid
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from web_server.database import db
from web_server.page_counter import get_page_count, get_pdf_info

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

def validate_safe_upload_path(file_path: str) -> str:
    """
    Validates that a client-provided file path resolves strictly inside UPLOAD_DIR.
    Prevents path traversal vulnerabilities.
    """
    if not file_path:
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    clean_path = str(file_path).strip()
    if ".." in clean_path or "/" in clean_path or "\\" in clean_path:
        if not clean_path.startswith(UPLOAD_DIR):
            raise HTTPException(status_code=400, detail="Path traversal forbidden: File path outside upload directory")

    if not os.path.isabs(clean_path):
        resolved_path = os.path.abspath(os.path.join(UPLOAD_DIR, os.path.basename(clean_path)))
    else:
        resolved_path = os.path.abspath(clean_path)

    try:
        common = os.path.commonpath([resolved_path, UPLOAD_DIR])
        if common != UPLOAD_DIR:
            raise HTTPException(status_code=400, detail="Path traversal forbidden: File path outside upload directory")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path structure")

    return resolved_path

@router.get("/s/{shop_id}", response_class=HTMLResponse)
async def customer_portal(request: Request, shop_id: str):
    shop = db.get_shop(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    is_valid, reason, exp_date = db.verify_shop_active_subscription(shop_id)
    paper_rates = db.get_shop_paper_rates(shop_id)
    return templates.TemplateResponse(
        request=request,
        name="customer.html",
        context={
            "shop": shop,
            "paper_rates": paper_rates,
            "is_locked": not is_valid,
            "lock_reason": reason
        }
    )

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

@router.post("/api/customer/upload")
async def upload_document(shop_id: str = Form(...), file: UploadFile = File(...)):
    shop = db.get_shop(shop_id)
    if not shop:
        return JSONResponse({"error": "Invalid Shop ID"}, status_code=404)

    is_valid, reason, exp_date = db.verify_shop_active_subscription(shop_id)
    if not is_valid:
        return JSONResponse({
            "error": f"🔒 Shop Account Locked ({reason}). Document upload disabled. Please contact the shop owner to renew their subscription."
        }, status_code=403)

    content = await file.read()

    # Server-side 25 MB size limit
    if len(content) > MAX_FILE_SIZE_BYTES:
        return JSONResponse({
            "error": f"File '{file.filename}' is too large ({len(content) // (1024*1024)} MB). Maximum allowed size is 25 MB."
        }, status_code=413)

    raw_ext = os.path.splitext(file.filename)[1].lower() or ".pdf"
    allowed_exts = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".txt"]
    ext = raw_ext if raw_ext in allowed_exts else ".pdf"

    safe_basename = f"upload_{uuid.uuid4().hex[:10]}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, safe_basename)

    with open(saved_path, "wb") as f:
        f.write(content)

    pdf_info = get_pdf_info(saved_path)
    paper_rates = db.get_shop_paper_rates(shop_id)

    preview_url = f"/static/uploads/{safe_basename}"

    if pdf_info["is_encrypted"] and not pdf_info["unlocked"]:
        return {
            "success": True,
            "is_password_protected": True,
            "filename": file.filename,
            "saved_path": saved_path,
            "preview_url": preview_url,
            "paper_rates": paper_rates,
            "message": "This PDF is password protected. Please enter password to unlock."
        }

    return {
        "success": True,
        "is_password_protected": False,
        "filename": file.filename,
        "saved_path": saved_path,
        "preview_url": preview_url,
        "page_count": pdf_info["page_count"],
        "paper_rates": paper_rates,
        "bw_rate": shop.get("bw_rate", 2.0),
        "color_rate": shop.get("color_rate", 10.0),
        "duplex_discount": shop.get("duplex_discount", 0.5)
    }

@router.post("/api/customer/unlock-pdf")
async def unlock_pdf(saved_path: str = Form(...), password: str = Form(...)):
    safe_path = validate_safe_upload_path(saved_path)
    if not os.path.exists(safe_path):
        return JSONResponse({"error": "Uploaded file not found"}, status_code=404)

    pdf_info = get_pdf_info(safe_path, password=password)

    if pdf_info["unlocked"]:
        return {
            "success": True,
            "page_count": pdf_info["page_count"],
            "message": "PDF unlocked successfully!"
        }
    else:
        return JSONResponse({"success": False, "error": "Incorrect password. Please try again."}, status_code=400)

@router.post("/api/customer/upload-rendered")
async def upload_rendered_canvas(
    shop_id: str = Form(...),
    rendered_file: UploadFile = File(...)
):
    """Accepts the rendered canvas PNG blob and saves it as the print file."""
    shop = db.get_shop(shop_id)
    if not shop:
        return JSONResponse({"error": "Invalid Shop ID"}, status_code=404)

    unique_filename = f"rendered_{uuid.uuid4().hex[:10]}.png"
    saved_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(saved_path, "wb") as f:
        content = await rendered_file.read()
        f.write(content)

    return {
        "success": True,
        "saved_path": saved_path,
        "filename": unique_filename
    }

@router.post("/api/customer/submit-job")
async def submit_print_job(
    shop_id: str = Form(...),
    original_filename: str = Form(...),
    file_path: str = Form(...),
    paper_size: str = Form("A4"),
    page_count: int = Form(1),
    copies: int = Form(1),
    color_mode: str = Form("bw"),
    duplex: str = Form("single"),
    page_range: str = Form("all"),
    payment_method: str = Form("cash"),
    total_cost: float = Form(0.0)
):
    safe_file_path = validate_safe_upload_path(file_path)

    # Authoritative Server-Side Price Calculation (Do not trust client side total_cost)
    server_calculated_cost = db.calculate_print_cost(
        shop_id=shop_id,
        paper_size=paper_size,
        page_count=page_count,
        copies=copies,
        color_mode=color_mode,
        duplex=duplex
    )

    job = db.create_print_job(
        shop_id=shop_id,
        original_filename=original_filename,
        file_path=safe_file_path,
        page_count=page_count,
        copies=copies,
        color_mode=color_mode,
        duplex=duplex,
        page_range=page_range,
        payment_method=payment_method,
        total_cost=server_calculated_cost
    )

    return {
        "success": True,
        "job_id": job["job_id"],
        "status": job["status"],
        "total_cost": server_calculated_cost,
        "message": "Print job submitted successfully!"
    }

@router.get("/api/customer/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Customer-facing: poll live status of a submitted print job."""
    job = db.get_job(job_id)
    if not job:
        return {"success": False, "error": "Job not found"}
    return {
        "success": True,
        "status": job["status"],
        "total_cost": job.get("total_cost", 0),
        "job_id": job["job_id"]
    }

@router.post("/api/customer/cancel-job/{job_id}")
async def cancel_job(job_id: str):
    """Customer-facing: cancel a pending (PENDING_CASH / QUEUED) job."""
    job = db.get_job(job_id)
    if not job:
        return {"success": False, "error": "Job not found"}
    if job["status"] not in ("PENDING_CASH", "QUEUED"):
        return {"success": False, "error": "Job cannot be cancelled at this stage"}
    ok = db.update_job_status(job_id, "CANCELLED")
    return {"success": ok}

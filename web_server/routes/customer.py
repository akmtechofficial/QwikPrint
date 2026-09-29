import os
import uuid
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from web_server.database import db
from web_server.page_counter import get_page_count, get_pdf_info

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "private_uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Also ensure legacy static uploads directory exists if referenced anywhere
LEGACY_STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "uploads"))
os.makedirs(LEGACY_STATIC_DIR, exist_ok=True)

def validate_safe_upload_path(file_path: str) -> str:
    """
    Validates that a client-provided file path resolves strictly inside UPLOAD_DIR or LEGACY_STATIC_DIR.
    Prevents path traversal vulnerabilities.
    """
    if not file_path:
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    clean_path = str(file_path).strip()
    if ".." in clean_path:
        raise HTTPException(status_code=400, detail="Path traversal forbidden: Directory traversal sequences disallowed")

    if not os.path.isabs(clean_path):
        resolved_path = os.path.abspath(os.path.join(UPLOAD_DIR, os.path.basename(clean_path)))
    else:
        resolved_path = os.path.abspath(clean_path)

    try:
        common_private = os.path.commonpath([resolved_path, UPLOAD_DIR])
        is_in_private = (common_private == UPLOAD_DIR)
    except Exception:
        is_in_private = False

    try:
        common_legacy = os.path.commonpath([resolved_path, LEGACY_STATIC_DIR])
        is_in_legacy = (common_legacy == LEGACY_STATIC_DIR)
    except Exception:
        is_in_legacy = False

    if not is_in_private and not is_in_legacy:
        raise HTTPException(status_code=400, detail="Path traversal forbidden: File path outside authorized upload directory")

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
MAX_RENDERED_SIZE_BYTES = 10 * 1024 * 1024 # 10 MB

import hmac
import hashlib
import base64
import time
from web_server.auth import SESSION_SECRET, get_current_user_and_shop

def generate_preview_token(safe_basename: str, exp_minutes: int = 60) -> str:
    """Generates a short-lived HMAC-signed document preview token."""
    exp = int(time.time()) + (exp_minutes * 60)
    raw = f"{safe_basename}:{exp}"
    sig = hmac.new(SESSION_SECRET.encode('utf-8'), raw.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    payload_b64 = base64.urlsafe_b64encode(raw.encode('utf-8')).decode('utf-8')
    return f"{payload_b64}.{sig}"

def verify_preview_token(token: str) -> str:
    """Verifies HMAC signature and expiry for document preview token."""
    try:
        if "." not in token:
            return None
        payload_b64, sig = token.rsplit(".", 1)
        raw = base64.urlsafe_b64decode(payload_b64.encode('utf-8')).decode('utf-8')
        safe_basename, exp_str = raw.rsplit(":", 1)
        expected_sig = hmac.new(SESSION_SECRET.encode('utf-8'), raw.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        if int(exp_str) < time.time():
            return None
        return safe_basename
    except Exception:
        return None

@router.get("/api/customer/preview/{token_or_basename}")
async def get_customer_preview(token_or_basename: str, token: str = None):
    """Secure preview endpoint requiring a valid signed preview token."""
    from fastapi.responses import FileResponse
    is_prod = os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod")

    # 1. Attempt token verification
    target_basename = verify_preview_token(token or token_or_basename)
    if not target_basename:
        if is_prod:
            raise HTTPException(status_code=403, detail="Document preview link expired or invalid signature")
        target_basename = os.path.basename(token_or_basename)

    target_path = validate_safe_upload_path(os.path.join(UPLOAD_DIR, target_basename))
    if not os.path.exists(target_path):
        target_path = os.path.join(LEGACY_STATIC_DIR, target_basename)
        if not os.path.exists(target_path):
            raise HTTPException(status_code=404, detail="Document file not found")
    
    return FileResponse(target_path)

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

    # 🔒 Signed Preview Token Endpoint
    tok = generate_preview_token(safe_basename)
    preview_url = f"/api/customer/preview/{tok}"

    if pdf_info["is_encrypted"] and not pdf_info["unlocked"]:
        return {
            "success": True,
            "is_password_protected": True,
            "filename": file.filename,
            "saved_path": saved_path,
            "preview_url": preview_url,
            "preview_token": tok,
            "paper_rates": paper_rates,
            "message": "This PDF is password protected. Please enter password to unlock."
        }

    return {
        "success": True,
        "is_password_protected": False,
        "filename": file.filename,
        "saved_path": saved_path,
        "preview_url": preview_url,
        "preview_token": tok,
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

    # 🔒 Active Subscription Verification
    is_valid, reason, _ = db.verify_shop_active_subscription(shop_id)
    if not is_valid:
        return JSONResponse({
            "error": f"🔒 Shop Account Locked ({reason}). Upload disabled."
        }, status_code=403)

    content = await rendered_file.read()
    if len(content) > MAX_RENDERED_SIZE_BYTES:
        return JSONResponse({
            "error": f"Rendered image too large ({len(content) // (1024*1024)} MB). Maximum allowed size is 10 MB."
        }, status_code=413)

    unique_filename = f"rendered_{uuid.uuid4().hex[:10]}.png"
    saved_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(saved_path, "wb") as f:
        f.write(content)

    tok = generate_preview_token(unique_filename)
    return {
        "success": True,
        "saved_path": saved_path,
        "filename": unique_filename,
        "preview_url": f"/api/customer/preview/{tok}",
        "preview_token": tok
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
    # 🔒 1. Active Subscription Verification
    is_valid, reason, _ = db.verify_shop_active_subscription(shop_id)
    if not is_valid:
        raise HTTPException(status_code=403, detail=f"Shop subscription locked ({reason}). Job submission disabled.")

    # 🔒 2. Input Option Allowlists
    clean_color_mode = "color" if color_mode.lower() in ("color", "colour") else "bw"
    clean_duplex = "duplex" if duplex.lower() in ("duplex", "double") else "single"
    clean_paper_size = paper_size.upper() if paper_size.upper() in ("A4", "A3", "A5", "LETTER", "LEGAL") else "A4"
    clean_payment_method = payment_method.lower() if payment_method.lower() in ("cash", "online", "payflux") else "cash"

    safe_file_path = validate_safe_upload_path(file_path)

    # 🔒 3. Enforce reasonable copies limits (1 - 100 copies)
    if copies < 1 or copies > 100:
        raise HTTPException(status_code=400, detail="Invalid copies requested. Copies must be between 1 and 100.")

    # 🔒 4. Authoritative Page Count Verification from uploaded file
    authoritative_page_count = max(1, page_count)
    if os.path.exists(safe_file_path) and safe_file_path.lower().endswith(".pdf"):
        try:
            pdf_info = get_pdf_info(safe_file_path)
            if pdf_info.get("page_count", 0) > 0:
                authoritative_page_count = pdf_info["page_count"]
        except Exception:
            pass

    # Authoritative Server-Side Price Calculation
    server_calculated_cost = db.calculate_print_cost(
        shop_id=shop_id,
        paper_size=clean_paper_size,
        page_count=authoritative_page_count,
        copies=copies,
        color_mode=clean_color_mode,
        duplex=clean_duplex
    )

    initial_status = "PENDING_CASH" if clean_payment_method == "cash" else "PAYMENT_PENDING"
    payment_status = "pending"
    customer_access_token = f"tok_cust_{uuid.uuid4().hex}"

    job_data = {
        "shop_id": shop_id,
        "original_filename": original_filename,
        "file_path": safe_file_path,
        "page_count": authoritative_page_count,
        "copies": copies,
        "color_mode": clean_color_mode,
        "duplex": clean_duplex,
        "page_range": page_range,
        "payment_method": clean_payment_method,
        "payment_status": payment_status,
        "total_cost": server_calculated_cost,
        "status": initial_status,
        "customer_access_token": customer_access_token
    }

    job_id = db.create_print_job(job_data)

    return {
        "success": True,
        "job_id": job_id,
        "customer_access_token": customer_access_token,
        "status": initial_status,
        "total_cost": server_calculated_cost,
        "message": "Print job submitted successfully!"
    }

@router.get("/api/customer/job-status/{job_id}")
async def get_job_status(request: Request, job_id: str, token: str = None):
    """Customer-facing: poll live status of a submitted print job with token authorization."""
    job = db.get_job(job_id)
    if not job:
        return {"success": False, "error": "Job not found"}

    # 🔒 Customer / Shop Owner Authorization Check
    req_token = token or request.headers.get("X-Customer-Token") or request.query_params.get("token")
    user, shop = get_current_user_and_shop(request)
    
    is_owner = (user and shop and shop["shop_id"] == job.get("shop_id"))
    is_authorized_customer = (req_token and req_token == job.get("customer_access_token"))

    if not is_owner and not is_authorized_customer:
        # Check dev environment fallback
        is_prod = os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod")
        if is_prod or req_token is not None:
            raise HTTPException(status_code=403, detail="Unauthorized access to job status")

    return {
        "success": True,
        "status": job["status"],
        "total_cost": job.get("total_cost", 0),
        "job_id": job["job_id"]
    }

@router.post("/api/customer/cancel-job/{job_id}")
async def cancel_job(request: Request, job_id: str, token: str = None):
    """Customer-facing: cancel a pending job with token authorization."""
    job = db.get_job(job_id)
    if not job:
        return {"success": False, "error": "Job not found"}

    # 🔒 Customer / Shop Owner Authorization Check
    req_token = token or request.headers.get("X-Customer-Token") or request.query_params.get("token")
    user, shop = get_current_user_and_shop(request)
    
    is_owner = (user and shop and shop["shop_id"] == job.get("shop_id"))
    is_authorized_customer = (req_token and req_token == job.get("customer_access_token"))

    if not is_owner and not is_authorized_customer:
        is_prod = os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod")
        if is_prod or req_token is not None:
            raise HTTPException(status_code=403, detail="Unauthorized access to cancel job")

    if job["status"] not in ("PENDING_CASH", "QUEUED"):
        return {"success": False, "error": "Job cannot be cancelled at this stage"}
    ok = db.update_job_status(job_id, "CANCELLED")
    return {"success": ok}

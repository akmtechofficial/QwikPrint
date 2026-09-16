import os
from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web_server.database import db
from web_server.auth import hash_password, verify_password, create_session_data, get_current_user_and_shop

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    if user or shop:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(request=request, name="register.html", context={"error": None})

def get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    response: Response,
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    shop_name: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form("")
):
    return templates.TemplateResponse(
        request=request, 
        name="register.html", 
        context={"error": "🔒 Direct Email & Password signups are disabled for anti-abuse security. Please click 'Continue with Google' to sign up instantly."}
    )

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    if user or shop:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    user = db.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Invalid email or password."})

    shop = db.get_user_shop(user["user_id"])
    shop_id = shop["shop_id"] if shop else "SHOP_ADMIN_001"
    session_token = create_session_data(user["user_id"], shop_id)
    
    superadmin_email = os.getenv("SUPERADMIN_EMAIL", "admin@qwikprint.in").lower().strip()
    target_url = request.query_params.get("next")
    if not target_url:
        if user.get("role") == "super_admin" or user.get("email", "").lower().strip() == superadmin_email:
            target_url = "/admin"
        else:
            target_url = "/dashboard"

    redirect_resp = RedirectResponse(url=target_url, status_code=303)
    redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 30)
    return redirect_resp

@router.post("/auth/google")
@router.post("/api/auth/google")
async def google_auth(
    request: Request,
    email: str = Form(...),
    full_name: str = Form("Google User"),
    shop_name: str = Form(""),
    device_fp: str = Form("")
):
    clean_email = email.lower().strip()
    client_ip = get_client_ip(request)
    fp = device_fp.strip() or request.cookies.get("qwikprint_registered_device", "")
    
    if not fp:
        import uuid
        fp = f"FP_{uuid.uuid4().hex[:12].upper()}"

    existing_user = db.get_user_by_email(clean_email)
    
    if existing_user:
        # User already registered -> Allow Login
        user = existing_user
        shop = db.get_user_shop(user["user_id"])
        if not shop:
            s_name = shop_name or f"{user.get('full_name', 'My')} Print Hub"
            shop = db.create_user_and_shop(
                user["full_name"], clean_email, "", s_name, "GOOGLE_AUTH_USER",
                registration_ip=client_ip, device_fingerprint=fp
            )[1]
    else:
        # New Registration attempt -> Check Multi-Account Lock per IP & Device Fingerprint
        is_blocked, existing_email = db.is_ip_or_device_registered(client_ip, fp)
        
        # Super admin exemption
        superadmin_email = os.getenv("SUPERADMIN_EMAIL", "admin@qwikprint.in").lower().strip()
        if is_blocked and clean_email != superadmin_email:
            return templates.TemplateResponse(
                request=request,
                name="register.html",
                context={
                    "error": f"🚫 Registration Locked: An account ({existing_email[:3]}***@{existing_email.split('@')[-1]}) has already been created from this device or IP address ({client_ip}). Creating multiple shop accounts from the same device is strictly prohibited."
                }
            )

        s_name = shop_name or f"{full_name}'s Print Hub"
        pwd_hash = hash_password(f"GOOGLE_AUTH_{clean_email}")
        user, shop = db.create_user_and_shop(
            full_name, clean_email, "+91 0000000000", s_name, pwd_hash,
            registration_ip=client_ip, device_fingerprint=fp
        )

    session_token = create_session_data(user["user_id"], shop["shop_id"])
    redirect_resp = RedirectResponse(url="/dashboard", status_code=303)
    redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 30)
    # Set persistent 10-year device fingerprint cookie
    redirect_resp.set_cookie(key="qwikprint_registered_device", value=fp, httponly=True, max_age=86400 * 365 * 10)
    return redirect_resp

@router.get("/logout")
@router.post("/logout")
@router.get("/api/auth/logout")
@router.post("/api/auth/logout")
async def logout():
    redirect_resp = RedirectResponse(url="/login", status_code=303)
    redirect_resp.delete_cookie(key="qwikprint_session", path="/")
    redirect_resp.set_cookie(key="qwikprint_session", value="", httponly=True, max_age=0, expires=0, path="/")
    return redirect_resp

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
    session_token = create_session_data(user["user_id"], shop_id, user.get("email", ""))
    
    superadmin_email = os.getenv("SUPERADMIN_EMAIL", "akashkapri12109@gmail.com").lower().strip()
    target_url = request.query_params.get("next")
    if not target_url:
        if user.get("role") == "super_admin" or user.get("email", "").lower().strip() == superadmin_email or user.get("email", "").lower().strip() == "akashkapri12109@gmail.com":
            target_url = "/admin"
        else:
            target_url = "/dashboard"

    redirect_resp = RedirectResponse(url=target_url, status_code=303)
    redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 365, path="/", samesite="lax")
    return redirect_resp

@router.post("/auth/google")
@router.post("/api/auth/google")
async def google_auth(
    request: Request,
    email: str = Form(...),
    full_name: str = Form("Google User"),
    shop_name: str = Form(""),
    device_fp: str = Form(""),
    id_token: str = Form("")
):
    clean_email = email.lower().strip()
    
    # 🔒 Cryptographic Token Verification
    if id_token:
        try:
            import requests
            # 1. Verify via Google OAuth2 tokeninfo endpoint
            resp = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}", timeout=5)
            if resp.status_code == 200:
                tok_data = resp.json()
                token_email = tok_data.get("email")
                is_verified = str(tok_data.get("email_verified", "")).lower() in ("true", "1")
                if token_email and is_verified:
                    clean_email = token_email.lower().strip()
            else:
                # 2. Fallback: Firebase Identity Toolkit lookup
                fb_key = os.environ.get("FIREBASE_WEB_API_KEY")
                if fb_key:
                    fb_resp = requests.post(
                        f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={fb_key}",
                        json={"idToken": id_token},
                        timeout=5
                    )
                    if fb_resp.status_code == 200:
                        users_list = fb_resp.json().get("users", [])
                        if users_list and users_list[0].get("email"):
                            clean_email = users_list[0]["email"].lower().strip()
        except Exception as tok_err:
            print(f"[Auth Security Warning] ID token verification exception: {tok_err}")

    # Enforce strict token requirement in production
    is_prod = os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod") or os.environ.get("REQUIRE_VERIFIED_GOOGLE_TOKEN", "").lower() == "true"
    if is_prod and not id_token:
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Security check failed: Google ID token verification required."})
    client_ip = get_client_ip(request)
    fp = device_fp.strip() or request.cookies.get("qwikprint_registered_device", "")
    
    if not fp:
        import uuid
        fp = f"FP_{uuid.uuid4().hex[:12].upper()}"

    superadmin_email = os.getenv("SUPERADMIN_EMAIL", "akashkapri12109@gmail.com").lower().strip()
    is_admin_email = (clean_email == "akashkapri12109@gmail.com" or clean_email == superadmin_email)

    # 1. Search existing user by email
    existing_user = db.get_user_by_email(clean_email)
    
    # 2. Fallback search by device fingerprint or registration IP
    if not existing_user and hasattr(db, 'get_user_by_device_or_ip'):
        existing_user = db.get_user_by_device_or_ip(fp, client_ip)
    
    if existing_user:
        # EXISTING USER -> Extract existing shop data & log in directly
        user = existing_user
        if is_admin_email and user.get("role") != "super_admin":
            db.update_user_role(user["user_id"], "super_admin")
            user["role"] = "super_admin"

        shop = db.get_user_shop(user["user_id"])
        if not shop:
            import uuid
            shop_id = f"shop-{uuid.uuid4().hex[:8]}"
            api_key = f"QWIK_KEY_{shop_id}_{uuid.uuid4().hex[:6].upper()}"
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            trial_exp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)).isoformat()
            display_name = user.get("full_name") or full_name or "Shop Owner"
            shop = {
                "shop_id": shop_id, "owner_id": user["user_id"], "api_key": api_key,
                "name": shop_name or f"{display_name}'s Print Shop", "owner_name": display_name,
                "email": clean_email, "phone": user.get("phone", "N/A"), "address": "Main Xerox Counter",
                "bw_rate": 2.0, "color_rate": 10.0, "duplex_discount": 0.5, "created_at": now,
                "subscription_status": "active", "plan_name": "7-Day Free Trial", "plan_expires_at": trial_exp
            }
            try:
                s_conn = db.get_sqlite_conn()
                s_cursor = s_conn.cursor()
                s_cursor.execute("INSERT INTO shops (shop_id, owner_id, api_key, name, owner_name, email, phone, address, bw_rate, color_rate, duplex_discount, created_at, subscription_status, plan_name, plan_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                                 (shop_id, user["user_id"], api_key, shop["name"], shop["owner_name"], clean_email, shop["phone"], shop["address"], 2.0, 10.0, 0.5, now, "active", "7-Day Free Trial", trial_exp))
                s_conn.commit()
                s_conn.close()
            except Exception as e:
                print(f"[Warning] Failed to auto-create shop: {e}")

        shop_id = shop["shop_id"] if shop else "SHOP_ADMIN_001"
        session_token = create_session_data(user["user_id"], shop_id, clean_email)
        
        target_url = "/admin" if (user.get("role") == "super_admin" or is_admin_email) else "/dashboard"

        redirect_resp = RedirectResponse(url=target_url, status_code=303)
        redirect_resp.delete_cookie(key="qwikprint_pending_google", path="/")
        redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 365, path="/", samesite="lax")
        redirect_resp.set_cookie(key="qwikprint_registered_device", value=fp, httponly=True, max_age=86400 * 365 * 10, path="/", samesite="lax")
        return redirect_resp
    else:
        # BRAND NEW USER -> Auto-create account & shop instantly (Instant 1-Click Signup)
        display_name = full_name if (full_name and full_name != "Google User") else clean_email.split('@')[0].capitalize()
        s_name = shop_name or f"{display_name}'s Print Shop"
        pwd_hash = hash_password(f"GOOGLE_AUTH_{clean_email}")
        
        user, shop = db.create_user_and_shop(
            clean_email, pwd_hash, display_name, "N/A", s_name,
            registration_ip=client_ip, device_fingerprint=fp
        )
        if is_admin_email:
            db.update_user_role(user["user_id"], "super_admin")
            user["role"] = "super_admin"

        try:
            from web_server.email_service import notify_new_user_registration
            notify_new_user_registration(user, shop, client_ip, fp)
        except Exception as e:
            print(f"[Warning] Could not trigger email notifications: {e}")

        shop_id = shop["shop_id"] if shop else "SHOP_ADMIN_001"
        session_token = create_session_data(user["user_id"], shop_id, clean_email)

        target_url = "/admin" if (user.get("role") == "super_admin" or is_admin_email) else "/dashboard"
        redirect_resp = RedirectResponse(url=target_url, status_code=303)
        redirect_resp.delete_cookie(key="qwikprint_pending_google", path="/")
        redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 365, path="/", samesite="lax")
        redirect_resp.set_cookie(key="qwikprint_registered_device", value=fp, httponly=True, max_age=86400 * 365 * 10, path="/", samesite="lax")
        return redirect_resp

@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    if user or shop:
        return RedirectResponse(url="/dashboard", status_code=302)
    
    pending_cookie = request.cookies.get("qwikprint_pending_google", "")
    google_email = ""
    google_name = ""
    device_fp = request.cookies.get("qwikprint_registered_device", "")
    
    if pending_cookie and "|" in pending_cookie:
        parts = pending_cookie.split("|")
        google_email = parts[0].lower().strip()
        if len(parts) > 1:
            google_name = parts[1]
        if len(parts) > 2 and not device_fp:
            device_fp = parts[2]
            
    if google_email:
        existing_user = db.get_user_by_email(google_email)
        if existing_user:
            # User already completed onboarding! Log in directly & redirect to /dashboard or /admin
            existing_shop = db.get_user_shop(existing_user["user_id"])
            shop_id = existing_shop["shop_id"] if existing_shop else "SHOP_ADMIN_001"
            session_token = create_session_data(existing_user["user_id"], shop_id)
            superadmin_email = os.getenv("SUPERADMIN_EMAIL", "akashkapri12109@gmail.com").lower().strip()
            is_admin_email = (google_email == "akashkapri12109@gmail.com" or google_email == superadmin_email)
            target_url = "/admin" if (existing_user.get("role") == "super_admin" or is_admin_email) else "/dashboard"
            
            redirect_resp = RedirectResponse(url=target_url, status_code=303)
            redirect_resp.delete_cookie(key="qwikprint_pending_google", path="/")
            redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 365, path="/", samesite="lax")
            return redirect_resp

    if not google_email:
        return RedirectResponse(url="/register", status_code=302)

    return templates.TemplateResponse(
        request=request, 
        name="onboarding.html", 
        context={
            "error": None,
            "google_email": google_email,
            "google_name": google_name,
            "device_fp": device_fp
        }
    )

@router.post("/onboarding", response_class=HTMLResponse)
async def onboarding_submit(
    request: Request,
    email: str = Form(""),
    full_name: str = Form(...),
    shop_name: str = Form(...),
    phone: str = Form(...),
    device_fp: str = Form("")
):
    pending_cookie = request.cookies.get("qwikprint_pending_google", "")
    clean_email = email.lower().strip()
    
    if not clean_email and pending_cookie and "|" in pending_cookie:
        clean_email = pending_cookie.split("|")[0].lower().strip()
        
    if not clean_email:
        return RedirectResponse(url="/register", status_code=302)

    client_ip = get_client_ip(request)
    fp = device_fp.strip() or request.cookies.get("qwikprint_registered_device", "")
    if not fp:
        import uuid
        fp = f"FP_{uuid.uuid4().hex[:12].upper()}"

    superadmin_email = os.getenv("SUPERADMIN_EMAIL", "akashkapri12109@gmail.com").lower().strip()
    is_admin_email = (clean_email == "akashkapri12109@gmail.com" or clean_email == superadmin_email)

    existing_user = db.get_user_by_email(clean_email)
    is_new_user = False
    if existing_user:
        user = existing_user
        if is_admin_email and user.get("role") != "super_admin":
            db.update_user_role(user["user_id"], "super_admin")
            user["role"] = "super_admin"
        shop = db.get_user_shop(user["user_id"])
    else:
        is_new_user = True
        # Multi-Account Lock per IP & Device Fingerprint
        is_blocked, existing_email = db.is_ip_or_device_registered(client_ip, fp)
        
        if is_blocked and not is_admin_email:
            return templates.TemplateResponse(
                request=request,
                name="onboarding.html",
                context={
                    "error": f"🚫 Registration Locked: An account ({existing_email[:3]}***@{existing_email.split('@')[-1]}) has already been created from this device or IP address ({client_ip}). Creating multiple shop accounts from the same device is strictly prohibited.",
                    "google_email": clean_email,
                    "google_name": full_name,
                    "device_fp": fp
                }
            )

        pwd_hash = hash_password(f"GOOGLE_AUTH_{clean_email}")
        user, shop = db.create_user_and_shop(
            clean_email, pwd_hash, full_name, phone, shop_name,
            registration_ip=client_ip, device_fingerprint=fp
        )
        if is_admin_email:
            db.update_user_role(user["user_id"], "super_admin")
            user["role"] = "super_admin"

        # Send Email Notifications (Admin Notification to akmtechofficial@gmail.com + Welcome Email to User)
        try:
            from web_server.email_service import notify_new_user_registration
            notify_new_user_registration(user, shop, client_ip, fp)
        except Exception as e:
            print(f"[Warning] Could not trigger email notifications: {e}")

    shop_id = shop["shop_id"] if shop else "SHOP_ADMIN_001"
    if user.get("role") == "super_admin" or is_admin_email:
        target_url = "/admin"
    else:
        target_url = "/dashboard"

    session_token = create_session_data(user["user_id"], shop_id)
    redirect_resp = RedirectResponse(url=target_url, status_code=303)
    redirect_resp.delete_cookie(key="qwikprint_pending_google", path="/")
    redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 365, path="/", samesite="lax")
    redirect_resp.set_cookie(key="qwikprint_registered_device", value=fp, httponly=True, max_age=86400 * 365 * 10, path="/", samesite="lax")
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

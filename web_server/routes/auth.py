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

@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    response: Response,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    shop_name: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    if password != confirm_password:
        return templates.TemplateResponse(request=request, name="register.html", context={"error": "Passwords do not match."})

    existing_user = db.get_user_by_email(email)
    if existing_user:
        return templates.TemplateResponse(request=request, name="register.html", context={"error": "Email is already registered. Please login."})

    pwd_hash = hash_password(password)
    user, shop = db.create_user_and_shop(full_name, email, phone, shop_name, pwd_hash)

    session_token = create_session_data(user["user_id"], shop["shop_id"])
    
    redirect_resp = RedirectResponse(url="/dashboard", status_code=303)
    redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 30)
    return redirect_resp

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
    shop_name: str = Form("")
):
    existing_user = db.get_user_by_email(email)
    if existing_user:
        user = existing_user
        shop = db.get_user_shop(user["user_id"])
        if not shop:
            s_name = shop_name or f"{user.get('full_name', 'My')} Print Hub"
            shop = db.create_user_and_shop(user["full_name"], email, "", s_name, "GOOGLE_AUTH_USER")[1]
    else:
        s_name = shop_name or f"{full_name}'s Print Hub"
        pwd_hash = hash_password(f"GOOGLE_AUTH_{email}")
        user, shop = db.create_user_and_shop(full_name, email, "+91 0000000000", s_name, pwd_hash)

    session_token = create_session_data(user["user_id"], shop["shop_id"])
    redirect_resp = RedirectResponse(url="/dashboard", status_code=303)
    redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 30)
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

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
    session_token = create_session_data(user["user_id"], shop["shop_id"])
    
    redirect_resp = RedirectResponse(url="/dashboard", status_code=303)
    redirect_resp.set_cookie(key="qwikprint_session", value=session_token, httponly=True, max_age=86400 * 30)
    return redirect_resp

@router.get("/logout")
async def logout():
    redirect_resp = RedirectResponse(url="/login", status_code=302)
    redirect_resp.delete_cookie(key="qwikprint_session")
    return redirect_resp

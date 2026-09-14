import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web_server.database import db
from web_server.auth import get_current_user_and_shop
from web_server.qr_generator import generate_shop_qr_base64

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

import json

@router.get("/dashboard", response_class=HTMLResponse)
async def shop_dashboard(request: Request):
    user, shop = get_current_user_and_shop(request)
    
    if not shop:
        shop = db.get_shop("SHOP_AKM_001")

    jobs = db.get_shop_jobs(shop["shop_id"], limit=50)
    paper_rates = db.get_shop_paper_rates(shop["shop_id"])
    
    total_revenue = sum(j["total_cost"] for j in jobs if j["payment_status"] == "paid")
    total_jobs = len(jobs)
    total_pages = sum(j["page_count"] * j["copies"] for j in jobs)

    base_url = str(request.base_url).rstrip("/")
    customer_url = f"{base_url}/s/{shop['shop_id']}"
    qr_base64 = generate_shop_qr_base64(customer_url)

    api_key = shop.get("api_key") or f"QWIK_KEY_{shop['shop_id']}_8F2A1C"

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "user": user,
        "shop": shop,
        "api_key": api_key,
        "paper_rates": paper_rates,
        "jobs": jobs,
        "total_revenue": total_revenue,
        "total_jobs": total_jobs,
        "total_pages": total_pages,
        "customer_url": customer_url,
        "qr_base64": qr_base64
    })

@router.post("/api/shop/details")
async def update_shop_details(
    shop_id: str = Form(...),
    name: str = Form(...),
    owner_name: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    email: str = Form(...)
):
    db.update_shop_details(shop_id, name, owner_name, phone, address, email)
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/api/shop/pricing")
async def update_pricing(
    shop_id: str = Form(...),
    bw_rate: float = Form(...),
    color_rate: float = Form(...),
    duplex_discount: float = Form(...)
):
    db.update_shop_pricing(shop_id, bw_rate, color_rate, duplex_discount)
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/api/shop/paper-rates")
async def update_shop_paper_rates(
    shop_id: str = Form(...),
    paper_rates_json: str = Form(...)
):
    try:
        rates = json.loads(paper_rates_json)
        db.update_shop_paper_rates(shop_id, rates[:5])
    except Exception as e:
        print(f"[Paper Rates Error] {e}")
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/api/shop/regenerate-key")
async def regenerate_key(shop_id: str = Form(...)):
    db.regenerate_shop_api_key(shop_id)
    return RedirectResponse(url="/dashboard", status_code=303)

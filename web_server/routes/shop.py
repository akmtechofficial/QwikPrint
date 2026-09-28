import os
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from web_server.database import db
from web_server.auth import get_current_user_and_shop
from web_server.qr_generator import generate_shop_qr_base64
import json

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

def verify_shop_authorization(request: Request, requested_shop_id: str):
    user, shop = get_current_user_and_shop(request)
    if not user or not shop:
        raise HTTPException(status_code=401, detail="Authentication required. Please login.")
    if shop["shop_id"] != requested_shop_id:
        raise HTTPException(status_code=403, detail="Forbidden: You are not authorized to manage this shop.")
    return user, shop

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    plans = db.get_plans()
    return templates.TemplateResponse(request=request, name="index.html", context={
        "user": user,
        "shop": shop,
        "plans": plans
    })

def get_canonical_base_url(request: Request) -> str:
    """
    Returns a stable, canonical base URL for the shop QR code and portal link.
    Prefers explicit PUBLIC_URL/APP_URL/CANONICAL_URL env vars or production forwarded headers
    over transient local request host headers.
    """
    for env_var in ("PUBLIC_URL", "APP_URL", "CANONICAL_URL"):
        val = os.getenv(env_var)
        if val and val.strip() and "localhost" not in val and "127.0.0.1" not in val:
            return val.strip().rstrip("/")
    
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    forwarded_proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    if forwarded_host and "localhost" not in forwarded_host and "127.0.0.1" not in forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")

    server_url = os.getenv("SERVER_URL")
    if server_url and server_url.strip() and "localhost" not in server_url and "127.0.0.1" not in server_url:
        return server_url.strip().rstrip("/")

    return str(request.base_url).rstrip("/")

def get_dashboard_context(request: Request, active_tab: str):
    user, shop = get_current_user_and_shop(request)
    if not user or not shop:
        return None, None, None

    jobs = db.get_shop_jobs(shop["shop_id"], limit=50)
    paper_rates = db.get_shop_paper_rates(shop["shop_id"])
    
    total_revenue = sum(j["total_cost"] for j in jobs if j["payment_status"] == "paid")
    total_jobs = len(jobs)
    total_pages = sum(j["page_count"] * j["copies"] for j in jobs)

    base_url = get_canonical_base_url(request)
    customer_url = f"{base_url}/s/{shop['shop_id']}"
    qr_base64 = generate_shop_qr_base64(customer_url)

    api_key = shop.get("api_key") or f"QWIK_KEY_{shop['shop_id']}_8F2A1C"

    context = {
        "request": request,
        "user": user,
        "shop": shop,
        "active_tab": active_tab,
        "api_key": api_key,
        "paper_rates": paper_rates,
        "jobs": jobs,
        "total_revenue": total_revenue,
        "total_jobs": total_jobs,
        "total_pages": total_pages,
        "customer_url": customer_url,
        "qr_base64": qr_base64
    }
    return user, shop, context

@router.get("/dashboard", response_class=HTMLResponse)
async def shop_dashboard_overview(request: Request):
    user, shop, context = get_dashboard_context(request, "overview")
    if not user or not shop:
        return RedirectResponse(url="/login", status_code=302)
    resp = templates.TemplateResponse(request=request, name="dashboard_overview.html", context=context)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp

@router.get("/dashboard/queue", response_class=HTMLResponse)
async def shop_dashboard_queue(request: Request):
    user, shop, context = get_dashboard_context(request, "queue")
    if not user or not shop:
        return RedirectResponse(url="/login", status_code=302)
    resp = templates.TemplateResponse(request=request, name="dashboard_queue.html", context=context)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp

@router.get("/dashboard/profile", response_class=HTMLResponse)
async def shop_dashboard_profile(request: Request):
    user, shop, context = get_dashboard_context(request, "profile")
    if not user or not shop:
        return RedirectResponse(url="/login", status_code=302)
    resp = templates.TemplateResponse(request=request, name="dashboard_profile.html", context=context)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp

@router.get("/dashboard/rates", response_class=HTMLResponse)
async def shop_dashboard_rates(request: Request):
    user, shop, context = get_dashboard_context(request, "rates")
    if not user or not shop:
        return RedirectResponse(url="/login", status_code=302)
    resp = templates.TemplateResponse(request=request, name="dashboard_rates.html", context=context)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp

@router.get("/dashboard/spooler", response_class=HTMLResponse)
async def shop_dashboard_spooler(request: Request):
    user, shop, context = get_dashboard_context(request, "spooler")
    if not user or not shop:
        return RedirectResponse(url="/login", status_code=302)
    resp = templates.TemplateResponse(request=request, name="dashboard_spooler.html", context=context)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp

@router.get("/dashboard/qr-poster", response_class=HTMLResponse)
async def shop_dashboard_qr(request: Request):
    user, shop, context = get_dashboard_context(request, "qr_poster")
    if not user or not shop:
        return RedirectResponse(url="/login", status_code=302)
    resp = templates.TemplateResponse(request=request, name="dashboard_qr.html", context=context)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp

@router.get("/api/shop/qr-poster/download-pdf")
async def download_shop_poster_pdf(request: Request):
    user, shop = get_current_user_and_shop(request)
    if not user or not shop:
        return RedirectResponse(url="/login", status_code=302)

    base_url = get_canonical_base_url(request)
    customer_url = f"{base_url}/s/{shop['shop_id']}"

    from web_server.pdf_poster_generator import create_shop_poster_pdf
    pdf_bytes = create_shop_poster_pdf(shop, customer_url)

    filename = f"QwikPrint_Counter_Poster_{shop['shop_id']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}", "Cache-Control": "no-store, no-cache, must-revalidate, private"}
    )

@router.get("/download/agent")
@router.get("/api/download/agent")
async def download_desktop_agent():
    exe_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "downloads", "QwikPrint_Desktop_Spooler_v2.4.exe"))
    if not os.path.exists(exe_path):
        # Fallback search root dist
        fallback = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dist", "PrintAgent.exe"))
        if os.path.exists(fallback):
            exe_path = fallback
        else:
            raise HTTPException(status_code=404, detail="Desktop agent installer file not found")

    with open(exe_path, "rb") as f:
        content = f.read()

    file_size = len(content)
    return Response(
        content=content,
        media_type="application/vnd.microsoft.portable-executable",
        headers={
            "Content-Disposition": 'attachment; filename="QwikPrint_Desktop_Spooler_v2.4.exe"',
            "Content-Length": str(file_size),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=86400"
        }
    )

@router.get("/dashboard/billing", response_class=HTMLResponse)
async def shop_dashboard_billing(request: Request):
    user, shop, context = get_dashboard_context(request, "billing")
    if not user or not shop:
        return RedirectResponse(url="/login", status_code=302)
    resp = templates.TemplateResponse(request=request, name="dashboard_billing.html", context=context)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp

@router.post("/api/shop/details")
async def update_shop_details(
    request: Request,
    shop_id: str = Form(...),
    name: str = Form(...),
    owner_name: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    email: str = Form(...)
):
    verify_shop_authorization(request, shop_id)
    db.update_shop_details(shop_id, name, owner_name, phone, address, email)
    return RedirectResponse(url="/dashboard/profile", status_code=303)

@router.post("/api/shop/pricing")
async def update_pricing(
    request: Request,
    shop_id: str = Form(...),
    bw_rate: float = Form(...),
    color_rate: float = Form(...),
    duplex_discount: float = Form(...)
):
    verify_shop_authorization(request, shop_id)
    db.update_shop_pricing(shop_id, bw_rate, color_rate, duplex_discount)
    return RedirectResponse(url="/dashboard/rates", status_code=303)

@router.post("/api/shop/paper-rates")
async def update_shop_paper_rates(
    request: Request,
    shop_id: str = Form(...),
    paper_rates_json: str = Form(...)
):
    verify_shop_authorization(request, shop_id)
    try:
        rates = json.loads(paper_rates_json)
        db.update_shop_paper_rates(shop_id, rates[:5])
    except Exception as e:
        print(f"[Paper Rates Error] {e}")
    return RedirectResponse(url="/dashboard/rates", status_code=303)

@router.post("/api/shop/regenerate-key")
async def regenerate_key(request: Request, shop_id: str = Form(...)):
    verify_shop_authorization(request, shop_id)
    db.regenerate_shop_api_key(shop_id)
    return RedirectResponse(url="/dashboard/spooler", status_code=303)

@router.get("/shadcn-components", response_class=HTMLResponse)
async def shadcn_components_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    return templates.TemplateResponse(request=request, name="shadcn_components.html", context={
        "user": user,
        "shop": shop
    })



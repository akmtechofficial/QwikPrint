import os
import uuid
import requests
from fastapi import APIRouter, Request, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web_server.database import db
from web_server.auth import get_current_user_and_shop

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

PAYFLUX_API_KEY = os.getenv("PAYFLUX_API_KEY", "")
PAYFLUX_MERCHANT_ID = os.getenv("PAYFLUX_MERCHANT_ID", "")
PAYFLUX_BASE_URL = os.getenv("PAYFLUX_BASE_URL", "https://fampay-merchant-api.onrender.com")

@router.get("/subscription", response_class=HTMLResponse)
async def subscription_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    if not user and not shop:
        return RedirectResponse(url="/login?next=/subscription", status_code=302)

    user_shop = shop
    if not user_shop:
        shops = db.get_all_shops()
        if shops:
            user_shop = shops[0]
        else:
            user_shop = {
                "shop_id": "SHOP_DEFAULT",
                "name": "My Printing Shop",
                "plan_name": "Trial Plan",
                "plan_expires_at": "",
                "is_suspended": False
            }

    is_valid, reason, exp_date = db.verify_shop_active_subscription(user_shop.get("shop_id"))
    plans = db.get_plans()

    return templates.TemplateResponse(
        request=request,
        name="subscription.html",
        context={
            "shop": user_shop,
            "is_valid": is_valid,
            "reason": reason,
            "plans": plans
        }
    )

@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    plans = db.get_plans()
    return templates.TemplateResponse(
        request=request,
        name="pricing.html",
        context={
            "shop": shop,
            "user": user,
            "plans": plans
        }
    )

@router.post("/api/payments/create-order")
async def create_payflux_order(request: Request, payload: dict = Body(...)):
    user, shop = get_current_user_and_shop(request)
    shop_id = shop.get("shop_id") if shop else None
    
    if not shop_id:
        shops = db.get_all_shops()
        if shops:
            shop_id = shops[0].get("shop_id")

    if not shop_id:
        raise HTTPException(status_code=400, detail="No registered shop found for subscription renewal")

    plan_id = payload.get("plan_id")
    plan_name = payload.get("plan_name", "Subscription Plan")
    amount = float(payload.get("amount", 0.0))

    order_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"

    duration_days = int(payload.get("duration_days", 0))
    if duration_days <= 0 and plan_id:
        plans = db.get_plans()
        for p in plans:
            if p.get("plan_id") == plan_id:
                duration_days = int(p.get("duration_days", 30))
                break

    if duration_days <= 0:
        duration_days = 30
        if "Free" in plan_name or "Trial" in plan_name or "7" in plan_name or amount == 0:
            duration_days = 7
        elif "2 Month" in plan_name or "60" in plan_name:
            duration_days = 60
        elif "3 Month" in plan_name or "90" in plan_name:
            duration_days = 90
        elif "1 Year" in plan_name or "365" in plan_name or "12 Month" in plan_name:
            duration_days = 365

    # Check if Payflux API Key is set
    if PAYFLUX_API_KEY:
        try:
            callback_url = str(request.base_url).rstrip("/") + f"/api/payments/payflux/callback?order_id={order_id}&shop_id={shop_id}&days={duration_days}&plan_name={plan_name}&amount={amount}"
            payflux_payload = {
                "merchant_id": PAYFLUX_MERCHANT_ID,
                "api_key": PAYFLUX_API_KEY,
                "order_id": order_id,
                "amount": amount,
                "purpose": f"QwikPrint - {plan_name}",
                "redirect_url": callback_url
            }
            resp = requests.post(f"{PAYFLUX_BASE_URL}/create-payment", json=payflux_payload, timeout=8)
            res_json = resp.json()
            if resp.status_code == 200 and res_json.get("payment_url"):
                return {"success": True, "payment_url": res_json["payment_url"], "order_id": order_id}
        except Exception as e:
            print(f"[Payflux Gateway Warning] API call failed: {e}. Falling back to gateway modal mode.")

    # Gateway Modal payload for frontend interactive payment gateway (works for ₹0 and paid plans)
    return {
        "success": True,
        "show_gateway_modal": True,
        "order_id": order_id,
        "shop_id": shop_id,
        "plan_id": plan_id,
        "plan_name": plan_name,
        "amount": amount,
        "duration_days": duration_days
    }

@router.post("/api/payments/confirm-order")
async def confirm_payflux_order(request: Request, payload: dict = Body(...)):
    user, shop = get_current_user_and_shop(request)
    shop_id = shop.get("shop_id") if shop else payload.get("shop_id")
    
    if not shop_id:
        shops = db.get_all_shops()
        if shops:
            shop_id = shops[0].get("shop_id")

    if not shop_id:
        raise HTTPException(status_code=400, detail="No registered shop found for payment confirmation")

    plan_name = payload.get("plan_name", "Subscription Plan")
    duration_days = int(payload.get("duration_days", 30))
    amount = float(payload.get("amount", 0.0))
    order_id = payload.get("order_id") or f"PAY-{uuid.uuid4().hex[:10].upper()}"
    payment_method = payload.get("payment_method", "payflux_gateway")

    result = db.update_shop_subscription(shop_id, duration_days, plan_name)
    db.create_subscription_record({
        "shop_id": shop_id,
        "plan_id": payload.get("plan_id", "custom"),
        "plan_name": plan_name,
        "amount": amount,
        "payment_gateway": payment_method,
        "transaction_id": order_id,
        "status": "success",
        "expires_at": result.get("plan_expires_at")
    })

    return {
        "success": True,
        "message": f"Successfully subscribed to {plan_name} for {duration_days} days!",
        "expires_at": result.get("plan_expires_at")
    }

@router.get("/api/payments/payflux/callback")
@router.post("/api/payments/payflux/callback")
async def payflux_callback(request: Request):
    params = request.query_params
    order_id = params.get("order_id")
    shop_id = params.get("shop_id")
    duration_days = int(params.get("days", 30))
    plan_name = params.get("plan_name", "Payflux Renewal")
    amount = float(params.get("amount", 0.0))

    if shop_id:
        result = db.update_shop_subscription(shop_id, duration_days, plan_name)
        db.create_subscription_record({
            "shop_id": shop_id,
            "plan_name": plan_name,
            "amount": amount,
            "payment_gateway": "payflux",
            "transaction_id": order_id or f"tx-{uuid.uuid4().hex[:8]}",
            "status": "success",
            "expires_at": result.get("plan_expires_at")
        })

    return RedirectResponse(url="/subscription", status_code=302)

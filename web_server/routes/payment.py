import os
import uuid
import time
import hmac
import hashlib
import requests
from fastapi import APIRouter, Request, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web_server.database import db
from web_server.auth import get_current_user_and_shop

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

PAYFLUX_SECRET_KEY = os.getenv("PAYFLUX_SECRET_KEY", os.getenv("PAYFLUX_API_KEY", "sk_test_your_merchant_secret_key"))
PAYFLUX_BASE_URL = os.getenv("PAYFLUX_BASE_URL", "https://fampay-merchant-api.onrender.com").rstrip("/")

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
@router.post("/api/create-order")
async def create_payflux_order(request: Request, payload: dict = Body(...)):
    user, shop = get_current_user_and_shop(request)
    shop_id = shop.get("shop_id") if shop else payload.get("shop_id")
    
    if not shop_id:
        shops = db.get_all_shops()
        if shops:
            shop_id = shops[0].get("shop_id")

    if not shop_id:
        raise HTTPException(status_code=400, detail="No registered shop found for subscription renewal")

    plan_id = payload.get("plan_id")
    plan_name = payload.get("plan_name", "Subscription Plan")
    amount = float(payload.get("amount", 0.0))

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

    order_id = f"ord_live_{uuid.uuid4().hex[:12]}"
    idempotency_key = f"order_req_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    base_url = str(request.base_url).rstrip("/")
    return_url = f"{base_url}/payment-success?order_id={order_id}"

    customer_email = (user.get("email") if user else None) or (shop.get("email") if shop else None) or "customer@qwikprint.in"
    customer_name = (user.get("full_name") if user else None) or (shop.get("name") if shop else None) or "Shop Owner"
    customer_phone = (user.get("phone") if user else None) or (shop.get("phone") if shop else None) or "9876543210"

    # 1. Initiate Payflux Order Call to Server-Side Payflux API
    if PAYFLUX_SECRET_KEY and "sk_test_your" not in PAYFLUX_SECRET_KEY:
        try:
            payflux_headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {PAYFLUX_SECRET_KEY}",
                "Idempotency-Key": idempotency_key
            }
            payflux_body = {
                "amount": amount,
                "customerName": customer_name,
                "customerEmail": customer_email,
                "customerPhone": customer_phone,
                "returnUrl": return_url
            }

            resp = requests.post(
                f"{PAYFLUX_BASE_URL}/api/v1/orders",
                headers=payflux_headers,
                json=payflux_body,
                timeout=10
            )

            if resp.status_code in (200, 201):
                res_json = resp.json()
                if res_json.get("success") and res_json.get("data"):
                    pf_data = res_json["data"]
                    checkout_token = pf_data.get("checkoutToken")
                    pf_order_id = pf_data.get("id", order_id)
                    checkout_url = pf_data.get("checkoutUrl") or f"{PAYFLUX_BASE_URL}/payflux/checkout?order_id={pf_order_id}&token={checkout_token}"
                    return {
                        "success": True,
                        "orderId": pf_order_id,
                        "checkoutToken": checkout_token,
                        "checkoutUrl": checkout_url,
                        "upiId": pf_data.get("upiId"),
                        "amount": amount,
                        "plan_id": plan_id,
                        "plan_name": plan_name,
                        "duration_days": duration_days
                    }
        except Exception as e:
            print(f"[Payflux Gateway Error] Server API call failed: {e}.")

    # Hosted Payflux Redirect Order Response
    checkout_token = f"pfchk_{order_id}_{uuid.uuid4().hex[:12]}"
    checkout_url = f"{PAYFLUX_BASE_URL}/payflux/checkout?order_id={order_id}&token={checkout_token}"
    return {
        "success": True,
        "orderId": order_id,
        "order_id": order_id,
        "checkoutToken": checkout_token,
        "checkoutUrl": checkout_url,
        "shop_id": shop_id,
        "plan_id": plan_id,
        "plan_name": plan_name,
        "amount": amount,
        "duration_days": duration_days
    }

@router.get("/payment-success", response_class=HTMLResponse)
async def payment_success_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    params = request.query_params
    order_id = params.get("orderId") or params.get("order_id") or "PAY-SUCCESS"

    if shop:
        result = db.update_shop_subscription(shop["shop_id"], 30, "Payflux Subscribed Plan")
        db.create_subscription_record({
            "shop_id": shop["shop_id"],
            "plan_id": "payflux-plan",
            "plan_name": "Payflux Subscribed Plan",
            "amount": 0.0,
            "payment_gateway": "payflux_sdk",
            "transaction_id": order_id,
            "status": "success",
            "expires_at": result.get("plan_expires_at")
        })

    return templates.TemplateResponse(
        request=request,
        name="subscription.html",
        context={
            "shop": shop,
            "is_valid": True,
            "reason": "Active",
            "plans": db.get_plans()
        }
    )

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
    order_id = payload.get("order_id") or payload.get("orderId") or f"PAY-{uuid.uuid4().hex[:10].upper()}"
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

import os
import json
import uuid
import time
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
    if not user or not shop:
        return RedirectResponse(url="/login?next=/subscription", status_code=302)

    shop_id = shop["shop_id"]
    sub_state = db.get_subscription_state(shop_id)
    is_trial_eligible = db.is_trial_eligible(shop_id)
    all_plans = db.get_plans()

    filtered_plans = []
    for p in all_plans:
        p_name = p.get("name", "").lower()
        p_price = float(p.get("price", 0))
        is_trial_plan = (p_price in (0.0, 1.0, 2.0)) or ("trial" in p_name) or ("free" in p_name)

        if is_trial_plan:
            if is_trial_eligible:
                filtered_plans.append(p)
        else:
            filtered_plans.append(p)

    resp = templates.TemplateResponse(
        request=request,
        name="subscription.html",
        context={
            "shop": shop,
            "user": user,
            "is_valid": sub_state["is_valid"],
            "reason": sub_state["reason"],
            "sub_state": sub_state,
            "plans": filtered_plans,
            "is_trial_eligible": is_trial_eligible
        }
    )
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp

@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    plans = db.get_plans()
    is_trial_eligible = db.is_trial_eligible(shop["shop_id"]) if shop else True

    filtered_plans = []
    for p in plans:
        p_name = p.get("name", "").lower()
        p_price = float(p.get("price", 0))
        is_trial_plan = (p_price in (0.0, 1.0, 2.0)) or ("trial" in p_name) or ("free" in p_name)
        if is_trial_plan:
            if is_trial_eligible:
                filtered_plans.append(p)
        else:
            filtered_plans.append(p)

    return templates.TemplateResponse(
        request=request,
        name="pricing.html",
        context={
            "shop": shop,
            "user": user,
            "plans": filtered_plans,
            "is_trial_eligible": is_trial_eligible
        }
    )

@router.post("/api/payments/create-order")
@router.post("/api/create-order")
async def create_payflux_order(request: Request, payload: dict = Body(...)):
    user, shop = get_current_user_and_shop(request)
    if not user or not shop:
        raise HTTPException(status_code=401, detail="Authentication required to create subscription order")

    shop_id = shop["shop_id"]
    plan_id = payload.get("plan_id")
    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")

    # Authoritative Server-Side Plan Lookup
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Subscription plan '{plan_id}' not found")

    plan_name = plan["name"]
    amount = float(plan["price"])
    duration_days = int(plan["duration_days"])

    # Trial Plan Handling
    if amount == 0.0 or "trial" in plan_name.lower() or "free" in plan_name.lower():
        if not db.is_trial_eligible(shop_id):
            raise HTTPException(status_code=400, detail="Free trial has already been claimed for this shop account.")
        
        trial_result = db.claim_trial(shop_id, duration_days=duration_days)
        return {
            "success": True,
            "is_trial": True,
            "message": "7-Day Free Trial activated successfully!",
            "expires_at": trial_result.get("plan_expires_at")
        }

    order_id = f"ord_live_{uuid.uuid4().hex[:12]}"
    idempotency_key = f"order_req_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    base_url = str(request.base_url).rstrip("/")
    return_url = f"{base_url}/payment-success?order_id={order_id}&plan_id={plan_id}"

    # Save DB payment order record
    db.create_payment_order({
        "order_id": order_id,
        "shop_id": shop_id,
        "plan_id": plan_id,
        "amount": amount,
        "currency": "INR",
        "status": "PENDING"
    })

    customer_email = user.get("email") or shop.get("email") or "customer@qwikprint.in"
    customer_name = user.get("full_name") or shop.get("name") or "Shop Owner"
    customer_phone = user.get("phone") or shop.get("phone") or "9876543210"

    # Gateway API Call
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

def verify_payflux_gateway_order(order_id: str) -> dict:
    """Verifies transaction status directly with PayFlux Payment Gateway server."""
    is_prod = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
    if not PAYFLUX_SECRET_KEY or "sk_test_your" in PAYFLUX_SECRET_KEY:
        if is_prod:
            raise HTTPException(status_code=500, detail="Payment gateway secret key is unconfigured in production mode.")
        # In dev mode without configured secret key, return fallback response
        return {"status": "PAID", "amount": None}
    
    try:
        headers = {
            "Authorization": f"Bearer {PAYFLUX_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        resp = requests.get(f"{PAYFLUX_BASE_URL}/api/v1/orders/{order_id}", headers=headers, timeout=8)
        if resp.status_code == 200:
            res_json = resp.json()
            data = res_json.get("data", {})
            status = data.get("status", "").upper()
            paid_amount = float(data.get("amount", 0)) if data.get("amount") else None
            return {"status": status, "amount": paid_amount, "raw": data}
    except Exception as e:
        print(f"[PayFlux Gateway Verification Exception] {e}")
    return {"status": "UNKNOWN", "amount": None}

@router.get("/payment-success", response_class=HTMLResponse)
async def payment_success_page(request: Request):
    user, shop = get_current_user_and_shop(request)
    if not user or not shop:
        return RedirectResponse(url="/login", status_code=302)

    order_id = request.query_params.get("orderId") or request.query_params.get("order_id") or ""
    
    # 🔒 UI-ONLY Success Page (Golden Rule: Frontend redirect MUST NOT grant subscription authority)
    sub_state = db.get_subscription_state(shop["shop_id"])
    msg = "Payment request received. Your subscription will activate once confirmed by the payment gateway."
    if sub_state["is_valid"]:
        msg = "Payment successful! Your subscription is currently active."

    resp = templates.TemplateResponse(
        request=request,
        name="subscription.html",
        context={
            "shop": shop,
            "user": user,
            "is_valid": sub_state["is_valid"],
            "reason": sub_state["reason"],
            "sub_state": sub_state,
            "plans": db.get_plans(),
            "payment_success_msg": msg
        }
    )
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return resp

@router.post("/api/payments/confirm-order")
async def confirm_payflux_order(request: Request, payload: dict = Body(...)):
    user, shop = get_current_user_and_shop(request)
    if not user or not shop:
        raise HTTPException(status_code=401, detail="Authentication required to confirm payment")

    shop_id = shop["shop_id"]
    order_id = payload.get("order_id") or payload.get("orderId")
    plan_id = payload.get("plan_id")

    if not order_id or not plan_id:
        raise HTTPException(status_code=400, detail="order_id and plan_id are required for confirmation")

    # 1. Database-level Idempotency Check
    existing_subs = db.get_subscriptions()
    for sub in existing_subs:
        if sub.get("transaction_id") == order_id and sub.get("status") == "success":
            return {
                "success": True,
                "message": "Payment already confirmed and activated.",
                "expires_at": sub.get("expires_at")
            }

    # 2. DB Order Ownership & Plan Verification
    db_order = db.get_payment_order(order_id)
    if db_order:
        if db_order["shop_id"] != shop_id:
            raise HTTPException(status_code=403, detail="Payment order does not belong to your shop account")
        if db_order["plan_id"] != plan_id:
            raise HTTPException(status_code=400, detail="Payment order plan mismatch")

    # 3. Authoritative Plan Lookup
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_name = plan["name"]
    duration_days = int(plan["duration_days"])
    expected_amount = float(plan["price"])

    # 4. Gateway Server-Side Status & Exact Amount Verification
    gateway_info = verify_payflux_gateway_order(order_id)
    gw_status = gateway_info.get("status")
    gw_amount = gateway_info.get("amount")

    # Enforce strict gateway status & exact amount check if key is configured
    if PAYFLUX_SECRET_KEY and "sk_test_your" not in PAYFLUX_SECRET_KEY:
        if gw_status not in ("PAID", "SUCCESS", "COMPLETED"):
            raise HTTPException(status_code=400, detail=f"Payment verification failed: Gateway order status is '{gw_status}'")
        if gw_amount is not None and abs(gw_amount - expected_amount) > 0.01:
            raise HTTPException(status_code=400, detail=f"Payment amount mismatch: expected ₹{expected_amount:.2f}, received ₹{gw_amount:.2f}")

    payment_method = payload.get("payment_method", "payflux_gateway")
    result = db.update_shop_subscription(shop_id, duration_days, plan_name)
    db.create_subscription_record({
        "shop_id": shop_id,
        "plan_id": plan_id,
        "plan_name": plan_name,
        "amount": expected_amount,
        "payment_gateway": payment_method,
        "transaction_id": order_id,
        "status": "success",
        "expires_at": result.get("plan_expires_at")
    })
    db.update_payment_order_status(order_id, "PAID")

    return {
        "success": True,
        "message": f"Successfully subscribed to {plan_name} for {duration_days} days!",
        "expires_at": result.get("plan_expires_at")
    }

@router.post("/api/payments/webhook")
async def payflux_webhook(request: Request):
    """Server-to-Server Webhook callback from PayFlux Gateway with HMAC Signature Verification."""
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode('utf-8')) if raw_body else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body in webhook payload")

    # 🔒 1. Cryptographic HMAC Webhook Signature Verification
    sig_header = (request.headers.get("X-PayFlux-Signature") or request.headers.get("X-Signature") or request.headers.get("Signature") or "").strip()
    if sig_header.lower().startswith("sha256="):
        sig_header = sig_header[7:].strip()

    is_prod = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")

    secret_key = os.getenv("PAYFLUX_SECRET_KEY") or os.getenv("PAYFLUX_API_KEY") or PAYFLUX_SECRET_KEY

    if secret_key and "sk_test_your" not in secret_key:
        import hmac, hashlib
        expected_sig = hmac.new(secret_key.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
        
        is_sig_valid = hmac.compare_digest(sig_header.lower(), expected_sig.lower()) if sig_header else False

        if not is_sig_valid:
            raise HTTPException(status_code=401, detail="Unauthorized webhook: Cryptographic HMAC signature verification failed")
    elif is_prod:
        raise HTTPException(status_code=401, detail="Webhook rejected: Payment secret key unconfigured in production mode")

    # 🔒 2. Payload Validation & Order Matching
    order_id = payload.get("order_id") or payload.get("orderId") or payload.get("id")
    event_type = payload.get("event") or payload.get("type") or ""
    status = payload.get("status", "").upper()

    if not order_id:
        raise HTTPException(status_code=400, detail="Missing order_id in webhook payload")

    # DB Order Verification
    db_order = db.get_payment_order(order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found in database")

    shop_id = db_order["shop_id"]
    plan_id = db_order["plan_id"]
    expected_amount = float(db_order["amount"])

    # 🔒 3. Independent Server-to-Server Gateway Re-Verification
    gateway_info = verify_payflux_gateway_order(order_id)
    gw_status = gateway_info.get("status")
    gw_amount = gateway_info.get("amount")

    if PAYFLUX_SECRET_KEY and "sk_test_your" not in PAYFLUX_SECRET_KEY:
        if gw_status not in ("PAID", "SUCCESS", "COMPLETED"):
            raise HTTPException(status_code=400, detail=f"Webhook verification failed: Gateway order status is '{gw_status}'")
        if gw_amount is not None and abs(gw_amount - expected_amount) > 0.01:
            raise HTTPException(status_code=400, detail=f"Webhook amount mismatch: expected ₹{expected_amount:.2f}, received ₹{gw_amount:.2f}")

    # Explicit event allowlist check
    allowed_events = ("order.paid", "payment.success", "payment.completed", "")
    if status in ("PAID", "SUCCESS", "COMPLETED") and event_type.lower() in allowed_events:
        existing_subs = db.get_subscriptions()
        already_processed = any(sub.get("transaction_id") == order_id and sub.get("status") == "success" for sub in existing_subs)
        if already_processed:
            return {"success": True, "message": "Order already processed"}

        plan = db.get_plan(plan_id)
        if plan:
            duration_days = int(plan["duration_days"])
            plan_name = plan["name"]
            res = db.update_shop_subscription(shop_id, duration_days, plan_name)
            db.create_subscription_record({
                "shop_id": shop_id,
                "plan_id": plan_id,
                "plan_name": plan_name,
                "amount": expected_amount,
                "payment_gateway": "payflux_webhook",
                "transaction_id": order_id,
                "status": "success",
                "expires_at": res.get("plan_expires_at")
            })
            db.update_payment_order_status(order_id, "PAID")
            return {"success": True, "message": "Subscription activated via verified webhook"}

    return {"success": True, "message": "Webhook processed"}


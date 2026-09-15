import os
import uuid
import datetime
import requests
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from database import db

payment_bp = Blueprint('payment', __name__)

PAYFLUX_API_KEY = os.getenv("PAYFLUX_API_KEY", "")
PAYFLUX_MERCHANT_ID = os.getenv("PAYFLUX_MERCHANT_ID", "")
PAYFLUX_BASE_URL = os.getenv("PAYFLUX_BASE_URL", "https://fampay-merchant-api.onrender.com")

@payment_bp.route("/subscription", methods=["GET"])
def subscription_page():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login", next="/subscription"))

    # Find shop owned by user
    shops = db.get_all_shops()
    user_shop = None
    for s in shops:
        if s.get("owner_id") == user_id or s.get("email") == session.get("user_email"):
            user_shop = s
            break
    
    if not user_shop and shops:
        user_shop = shops[0]
    
    if not user_shop:
        user_shop = {
            "shop_id": "SHOP_DEFAULT",
            "name": "My Printing Shop",
            "plan_name": "Trial Plan",
            "plan_expires_at": "",
            "is_suspended": False
        }

    is_valid, reason, exp_date = db.verify_shop_active_subscription(user_shop.get("shop_id"))
    plans = db.get_plans()

    return render_template(
        "subscription.html",
        shop=user_shop,
        is_valid=is_valid,
        reason=reason,
        plans=plans
    )

@payment_bp.route("/api/payments/create-order", methods=["POST"])
def create_payflux_order():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.json or {}
    plan_id = data.get("plan_id")
    plan_name = data.get("plan_name", "Subscription Plan")
    amount = float(data.get("amount", 199.0))

    shops = db.get_all_shops()
    shop_id = None
    for s in shops:
        if s.get("owner_id") == user_id or s.get("email") == session.get("user_email"):
            shop_id = s.get("shop_id")
            break
    
    if not shop_id and shops:
        shop_id = shops[0].get("shop_id")

    if not shop_id:
        return jsonify({"success": False, "error": "No associated shop found for subscription renewal"}), 400

    order_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"

    # Duration mapping
    duration_days = 30
    if "3 Month" in plan_name or "90" in plan_name:
        duration_days = 90
    elif "1 Year" in plan_name or "365" in plan_name or "12 Month" in plan_name:
        duration_days = 365

    # Check if Payflux API keys are configured
    if PAYFLUX_API_KEY:
        try:
            payflux_payload = {
                "merchant_id": PAYFLUX_MERCHANT_ID,
                "api_key": PAYFLUX_API_KEY,
                "order_id": order_id,
                "amount": amount,
                "purpose": f"QwikPrint - {plan_name}",
                "redirect_url": request.host_url + f"api/payments/payflux/callback?order_id={order_id}&shop_id={shop_id}&days={duration_days}&plan_name={plan_name}&amount={amount}"
            }
            resp = requests.post(f"{PAYFLUX_BASE_URL}/create-payment", json=payflux_payload, timeout=8)
            res_json = resp.json()
            if resp.status_code == 200 and res_json.get("payment_url"):
                return jsonify({"success": True, "payment_url": res_json["payment_url"], "order_id": order_id})
        except Exception as e:
            print(f"[Payflux Gateway Warning] Payflux API call failed: {e}. Falling back to instant auto-activation mode.")

    # Fallback / Instant auto-activation if Payflux API key is in setup mode
    result = db.update_shop_subscription(shop_id, duration_days, plan_name)
    db.create_subscription_record({
        "shop_id": shop_id,
        "plan_id": plan_id,
        "plan_name": plan_name,
        "amount": amount,
        "payment_gateway": "payflux",
        "transaction_id": order_id,
        "status": "success",
        "expires_at": result.get("plan_expires_at")
    })

    return jsonify({
        "success": True,
        "auto_activated": True,
        "message": f"Successfully subscribed to {plan_name} for {duration_days} days!",
        "expires_at": result.get("plan_expires_at")
    })

@payment_bp.route("/api/payments/payflux/callback", methods=["GET", "POST"])
def payflux_callback():
    order_id = request.args.get("order_id") or request.form.get("order_id")
    shop_id = request.args.get("shop_id") or request.form.get("shop_id")
    duration_days = int(request.args.get("days", 30))
    plan_name = request.args.get("plan_name", "Payflux Renewal")
    amount = float(request.args.get("amount", 0.0))

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

    return redirect(url_for("payment.subscription_page"))

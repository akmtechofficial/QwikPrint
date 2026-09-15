import os
import functools
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from database import db

admin_bp = Blueprint('admin', __name__)

SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "admin@qwikprint.in")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "admin123")

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        user_email = session.get("user_email")
        user_role = session.get("user_role")
        if user_email == SUPERADMIN_EMAIL or user_role == "super_admin":
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": "Unauthorized: Super Admin access required"}), 403
    return decorated_function

@admin_bp.route("/admin", methods=["GET"])
def admin_page():
    user_email = session.get("user_email")
    user_role = session.get("user_role")
    if user_email != SUPERADMIN_EMAIL and user_role != "super_admin":
        return redirect(url_for("login", next="/admin"))

    stats = db.get_admin_dashboard_stats()
    shops = db.get_all_shops()
    plans = db.get_plans()
    subscriptions = db.get_subscriptions()

    return render_template(
        "admin.html",
        stats=stats,
        shops=shops,
        plans=plans,
        subscriptions=subscriptions
    )

@admin_bp.route("/api/admin/stats", methods=["GET"])
@admin_required
def get_stats():
    return jsonify({"success": True, "stats": db.get_admin_dashboard_stats()})

@admin_bp.route("/api/admin/shops", methods=["GET"])
@admin_required
def get_shops():
    return jsonify({"success": True, "shops": db.get_all_shops()})

@admin_bp.route("/api/admin/shops/<shop_id>/subscription", methods=["POST"])
@admin_required
def grant_subscription(shop_id):
    data = request.json or {}
    duration_days = int(data.get("duration_days", 30))
    plan_name = data.get("plan_name", f"{duration_days} Days Admin Extension")
    
    result = db.update_shop_subscription(shop_id, duration_days, plan_name)
    db.create_subscription_record({
        "shop_id": shop_id,
        "plan_id": "admin-grant",
        "plan_name": plan_name,
        "amount": 0.0,
        "payment_gateway": "admin_granted",
        "transaction_id": f"admin-{os.urandom(4).hex()}",
        "status": "success",
        "expires_at": result.get("plan_expires_at")
    })
    return jsonify({"success": True, "data": result})

@admin_bp.route("/api/admin/shops/<shop_id>/suspend", methods=["POST"])
@admin_required
def suspend_shop(shop_id):
    data = request.json or {}
    suspend = bool(data.get("suspend", True))
    db.toggle_shop_suspension(shop_id, suspend)
    return jsonify({"success": True, "suspended": suspend})

@admin_bp.route("/api/admin/plans", methods=["GET", "POST"])
@admin_required
def handle_plans():
    if request.method == "POST":
        data = request.json or {}
        if not data.get("name") or not data.get("duration_days") or data.get("price") is None:
            return jsonify({"success": False, "error": "Missing required fields: name, duration_days, price"}), 400
        db.save_plan(data)
        return jsonify({"success": True, "message": "Plan saved successfully"})
    
    return jsonify({"success": True, "plans": db.get_plans()})

@admin_bp.route("/api/admin/plans/<plan_id>", methods=["DELETE"])
@admin_required
def delete_plan(plan_id):
    db.delete_plan(plan_id)
    return jsonify({"success": True, "message": "Plan deleted"})

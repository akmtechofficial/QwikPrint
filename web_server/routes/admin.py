import os
import uuid
from fastapi import APIRouter, Request, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web_server.database import db
from web_server.auth import get_current_user_and_shop

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "admin@qwikprint.in")

def is_super_admin(request: Request):
    user, shop = get_current_user_and_shop(request)
    if user and (user.get("email") == SUPERADMIN_EMAIL or user.get("role") == "super_admin"):
        return True, user
    return False, user

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    is_admin, user = is_super_admin(request)
    if not is_admin:
        # Default allow first logged in user if superadmin environment variable matches or for admin portal access
        if not user:
            return RedirectResponse(url="/login?next=/admin", status_code=302)

    stats = db.get_admin_dashboard_stats()
    shops = db.get_all_shops()
    plans = db.get_plans()
    subscriptions = db.get_subscriptions()

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "stats": stats,
            "shops": shops,
            "plans": plans,
            "subscriptions": subscriptions
        }
    )

@router.get("/api/admin/stats")
async def get_stats(request: Request):
    return {"success": True, "stats": db.get_admin_dashboard_stats()}

@router.get("/api/admin/shops")
async def get_shops(request: Request):
    return {"success": True, "shops": db.get_all_shops()}

@router.post("/api/admin/shops/{shop_id}/subscription")
async def grant_subscription(shop_id: str, payload: dict = Body(...)):
    duration_days = int(payload.get("duration_days", 30))
    plan_name = payload.get("plan_name", f"{duration_days} Days Admin Extension")
    
    result = db.update_shop_subscription(shop_id, duration_days, plan_name)
    db.create_subscription_record({
        "shop_id": shop_id,
        "plan_id": "admin-grant",
        "plan_name": plan_name,
        "amount": 0.0,
        "payment_gateway": "admin_granted",
        "transaction_id": f"admin-{uuid.uuid4().hex[:8]}",
        "status": "success",
        "expires_at": result.get("plan_expires_at")
    })
    return {"success": True, "data": result}

@router.post("/api/admin/shops/{shop_id}/suspend")
async def suspend_shop(shop_id: str, payload: dict = Body(...)):
    suspend = bool(payload.get("suspend", True))
    db.toggle_shop_suspension(shop_id, suspend)
    return {"success": True, "suspended": suspend}

@router.get("/api/admin/plans")
async def list_plans():
    return {"success": True, "plans": db.get_plans()}

@router.post("/api/admin/plans")
async def create_or_update_plan(payload: dict = Body(...)):
    if not payload.get("name") or not payload.get("duration_days") or payload.get("price") is None:
        raise HTTPException(status_code=400, detail="Missing required fields: name, duration_days, price")
    db.save_plan(payload)
    return {"success": True, "message": "Plan saved successfully"}

@router.delete("/api/admin/plans/{plan_id}")
async def delete_plan(plan_id: str):
    db.delete_plan(plan_id)
    return {"success": True, "message": "Plan deleted"}

@router.post("/api/admin/shops/{shop_id}/reset-key")
async def reset_shop_key(shop_id: str):
    new_key = db.regenerate_shop_api_key(shop_id)
    return {"success": True, "new_api_key": new_key, "message": "API key regenerated & paired device reset successfully"}


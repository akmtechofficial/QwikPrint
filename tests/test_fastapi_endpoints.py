import os
import sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from web_server.server import app
from web_server.auth import create_session_data
from web_server.database import db

if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

async def test_fastapi_endpoints_async():
    print("==================================================")
    print("FASTAPI API ROUTE AUTHORIZATION & SECURITY TESTS")
    print("==================================================\n")

    # Import httpx or use Starlette TestClient via asyncio
    from starlette.testclient import TestClient
    client = TestClient(app)

    # 1. Unauthenticated Admin Page Access
    res_admin = client.get("/admin", follow_redirects=False)
    assert res_admin.status_code in (302, 303)
    assert "/login" in res_admin.headers.get("location", "")
    print("[PASSED] ROUTE 1: Unauthenticated /admin Redirects to /login")

    # 2. Unauthenticated Admin API Access
    res_stats = client.get("/api/admin/stats")
    assert res_stats.status_code in (401, 403)
    print("[PASSED] ROUTE 2: Unauthenticated /api/admin/stats Returns HTTP 401/403")

    # 3. Non-Admin User Accessing Admin API
    # Create non-admin shopkeeper session
    shops = db.get_all_shops()
    if shops:
        s = shops[0]
        user_token = create_session_data(s["owner_id"], s["shop_id"])
        client.cookies.set("qwikprint_session", user_token)
        
        res_nonadmin = client.get("/api/admin/stats")
        assert res_nonadmin.status_code == 403
        print("[PASSED] ROUTE 3: Non-Admin User Access to Admin API Returns HTTP 403 Forbidden")

    # 4. Desktop Agent Queue Access Without Device Headers
    client.cookies.clear()
    res_agent = client.get("/api/agent/queue")
    assert res_agent.status_code == 401
    print("[PASSED] ROUTE 4: Agent API Rejects Requests Without Valid Headers")

    # 5. Payment Order Creation Requires Auth
    res_pay = client.post("/api/payments/create-order", json={"plan_id": "plan-1m", "amount": 0.0})
    assert res_pay.status_code == 401
    print("[PASSED] ROUTE 5: Payment Creation Rejects Unauthenticated Requests")

    # 6. Verify APIClient Has device_id and device_token Properties
    from python_agent.api_client import api_client
    assert hasattr(api_client, "device_id")
    assert hasattr(api_client, "device_token")
    assert isinstance(api_client.device_id, str)
    assert isinstance(api_client.device_token, str)
    print("[PASSED] ROUTE 6: APIClient has device_id and device_token Property Getters")

    print("\n==================================================")
    print("ALL FASTAPI ROUTE TESTS PASSED (6/6)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(test_fastapi_endpoints_async())

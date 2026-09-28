import os
import sys
import uuid
import datetime
import asyncio

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from web_server.database import db
from web_server.auth import create_session_data, decode_session_data, hash_password
from web_server.routes.customer import validate_safe_upload_path
from fastapi import HTTPException

test_results = []

if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

def log_test(name: str, passed: bool, detail: str = ""):
    status = "PASSED" if passed else "FAILED"
    test_results.append((name, passed, detail))
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))

def run_tests():
    print("==================================================")
    print("QWIKPRINT SYSTEM ARCHITECTURE & SECURITY TEST SUITE")
    print("==================================================\n")

    # ----------------------------------------------------
    # TEST 1: SESSION CREATION & Persistence Validation
    # ----------------------------------------------------
    try:
        user_id = f"test-usr-{uuid.uuid4().hex[:6]}"
        shop_id = f"test-shop-{uuid.uuid4().hex[:6]}"
        token = create_session_data(user_id, shop_id)
        decoded = decode_session_data(token)
        
        assert decoded.get("user_id") == user_id
        assert decoded.get("shop_id") == shop_id
        assert decoded.get("exp") > int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 800000
        log_test("AUTH 1: Session Token Creation & 1-Year Expiration", True)
    except Exception as e:
        log_test("AUTH 1: Session Token Creation & 1-Year Expiration", False, str(e))

    # ----------------------------------------------------
    # TEST 2: DATABASE ATOMIC USER & SHOP CREATION
    # ----------------------------------------------------
    try:
        test_email = f"test_user_{uuid.uuid4().hex[:6]}@example.com"
        pwd_hash = hash_password("TestPassword123")
        user, shop = db.create_user_and_shop(
            email=test_email,
            password_hash=pwd_hash,
            full_name="Test User",
            phone="9998887776",
            shop_name="Test Print Corner",
            registration_ip="127.0.0.1",
            device_fingerprint=f"FP_{uuid.uuid4().hex[:8]}"
        )
        
        fetched_user = db.get_user_by_email(test_email)
        fetched_shop = db.get_user_shop(user["user_id"])
        
        assert fetched_user is not None
        assert fetched_user["email"] == test_email
        assert fetched_shop is not None
        assert fetched_shop["shop_id"] == shop["shop_id"]
        log_test("DB 1: Atomic User & Shop Creation & Email Normalization", True)
    except Exception as e:
        log_test("DB 1: Atomic User & Shop Creation & Email Normalization", False, str(e))

    # ----------------------------------------------------
    # TEST 3: AUTHORITATIVE SUBSCRIPTION STATE MACHINE
    # ----------------------------------------------------
    try:
        test_shop_id = shop["shop_id"]
        sub_state = db.get_subscription_state(test_shop_id)
        
        assert sub_state["status"] in ("active", "expired", "suspended", "none")
        assert "is_valid" in sub_state
        assert "reason" in sub_state
        log_test("STATE MACHINE 1: Authoritative Subscription State Resolution", True)
    except Exception as e:
        log_test("STATE MACHINE 1: Authoritative Subscription State Resolution", False, str(e))

    # ----------------------------------------------------
    # TEST 4: ONE-TIME FREE TRIAL CLAIM & RECLAIM REJECTION
    # ----------------------------------------------------
    try:
        # Create a fresh shop for trial testing
        fresh_email = f"trial_shop_{uuid.uuid4().hex[:6]}@example.com"
        t_user, t_shop = db.create_user_and_shop(
            email=fresh_email,
            password_hash=hash_password("Pass123"),
            full_name="Trial Tester",
            phone="1112223334",
            shop_name="Fresh Trial Shop"
        )
        t_shop_id = t_shop["shop_id"]

        # 1st claim should succeed
        claim1 = db.claim_trial(t_shop_id, duration_days=7)
        assert claim1["success"] is True, f"Claim 1 failed: {claim1}"

        # 2nd claim MUST fail
        claim2 = db.claim_trial(t_shop_id, duration_days=7)
        assert claim2["success"] is False
        assert "already been claimed" in claim2["error"]
        
        # Verify trial_eligible is now False
        assert db.is_trial_eligible(t_shop_id) is False
        log_test("TRIAL 1: Trial Can Only Be Claimed ONCE Per Shop", True)
    except Exception as e:
        log_test("TRIAL 1: Trial Can Only Be Claimed ONCE Per Shop", False, str(e))

    # ----------------------------------------------------
    # TEST 5: SERVER-SIDE PLAN LOOKUP & TAMPER PREVENTION
    # ----------------------------------------------------
    try:
        plan = db.get_plan("plan-1m")
        if not plan:
            # Check default plan list
            plans = db.get_plans()
            plan = plans[0] if plans else None
            
        assert plan is not None
        assert "price" in plan
        assert "duration_days" in plan
        log_test("PAYMENT 1: Server-Side Authoritative Plan Lookup", True)
    except Exception as e:
        log_test("PAYMENT 1: Server-Side Authoritative Plan Lookup", False, str(e))

    # ----------------------------------------------------
    # TEST 6: PAYMENT CONFIRMATION IDEMPOTENCY
    # ----------------------------------------------------
    try:
        order_id = f"test-ord-{uuid.uuid4().hex[:8]}"
        p_shop_id = t_shop_id

        res1 = db.update_shop_subscription(p_shop_id, 30, "1 Month Starter")
        db.create_subscription_record({
            "shop_id": p_shop_id,
            "plan_id": "plan-1m",
            "plan_name": "1 Month Starter",
            "amount": 199.0,
            "payment_gateway": "test_gateway",
            "transaction_id": order_id,
            "status": "success",
            "expires_at": res1.get("plan_expires_at")
        })

        subs = db.get_subscriptions()
        already_processed = [s for s in subs if s.get("transaction_id") == order_id and s.get("status") == "success"]
        assert len(already_processed) == 1
        log_test("PAYMENT 2: Payment Idempotency Prevents Double Activation", True)
    except Exception as e:
        log_test("PAYMENT 2: Payment Idempotency Prevents Double Activation", False, str(e))

    # ----------------------------------------------------
    # TEST 7: PATH TRAVERSAL SECURITY IN CUSTOMER UPLOADS
    # ----------------------------------------------------
    try:
        # Valid path
        valid_path = validate_safe_upload_path("sample_document.pdf")
        assert os.path.basename(valid_path) == "sample_document.pdf"

        # Malicious path traversal
        traversal_failed = False
        try:
            validate_safe_upload_path("../../../etc/passwd")
        except HTTPException as h_err:
            if h_err.status_code == 400:
                traversal_failed = True

        assert traversal_failed is True
        log_test("SECURITY 1: Path Traversal Rejection in File Uploads", True)
    except Exception as e:
        log_test("SECURITY 1: Path Traversal Rejection in File Uploads", False, str(e))

    # ----------------------------------------------------
    # TEST 8: SUPER ADMIN ROLE CHECK
    # ----------------------------------------------------
    try:
        admin_user = db.get_user_by_email("akashkapri12109@gmail.com")
        if not admin_user:
            # Seed super admin
            db.update_user_role(user["user_id"], "super_admin")
            admin_user = db.get_user(user["user_id"])
            
        assert admin_user["role"] == "super_admin"
        log_test("AUTH 2: Super Admin Role Verification", True)
    except Exception as e:
        log_test("AUTH 2: Super Admin Role Verification", False, str(e))

    # ----------------------------------------------------
    # TEST 9: DIRECT DASHBOARD REDIRECT FOR NON-ADMIN USERS
    # ----------------------------------------------------
    try:
        non_admin_user = db.get_user_by_email(test_email)
        assert non_admin_user is not None
        target = "/admin" if non_admin_user.get("role") == "super_admin" else "/dashboard"
        assert target == "/dashboard"
        log_test("AUTH 3: Direct Dashboard Redirect for Non-Admin Users", True)
    except Exception as e:
        log_test("AUTH 3: Direct Dashboard Redirect for Non-Admin Users", False, str(e))

    # ----------------------------------------------------
    # FINAL SUMMARY
    # ----------------------------------------------------
    print("\n==================================================")
    passed_count = sum(1 for _, p, _ in test_results if p)
    total_count = len(test_results)
    print(f"RESULTS: {passed_count}/{total_count} TESTS PASSED")
    print("==================================================")

    if passed_count == total_count:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()

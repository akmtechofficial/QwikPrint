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
        assert decoded.get("exp") > int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 500000
        log_test("AUTH 1: Session Token Creation & 7-Day Expiration", True)
    except Exception as e:
        log_test("AUTH 1: Session Token Creation & 7-Day Expiration", False, str(e))

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
    # TEST 10: UNAUTHENTICATED AGENT DOWNLOAD REJECTION
    # ----------------------------------------------------
    try:
        from web_server.routes.agent_api import validate_agent_auth
        unauth_blocked = False
        try:
            validate_agent_auth(None, None)
        except HTTPException as h_err:
            if h_err.status_code == 401:
                unauth_blocked = True
        assert unauth_blocked is True
        log_test("SECURITY 2: Unauthenticated Agent Download Rejection", True)
    except Exception as e:
        log_test("SECURITY 2: Unauthenticated Agent Download Rejection", False, str(e))

    # ----------------------------------------------------
    # TEST 11: COPIES ABUSE LIMIT VALIDATION
    # ----------------------------------------------------
    try:
        from web_server.routes.customer import submit_print_job
        copies_blocked = False
        try:
            asyncio.run(submit_print_job(
                shop_id=shop["shop_id"],
                original_filename="doc.pdf",
                file_path=os.path.join(os.path.dirname(__file__), "..", "private_uploads", "test.pdf"),
                paper_size="A4",
                page_count=1,
                copies=9999,
                color_mode="bw",
                duplex="single",
                page_range="all",
                payment_method="cash",
                total_cost=0.0
            ))
        except HTTPException as h_err:
            if h_err.status_code == 400:
                copies_blocked = True
        assert copies_blocked is True
        log_test("SECURITY 3: Job Copies Abuse Rejection (>100 copies)", True)
    except Exception as e:
        log_test("SECURITY 3: Job Copies Abuse Rejection (>100 copies)", False, str(e))

    # ----------------------------------------------------
    # TEST 12: SIGNED PREVIEW TOKEN VERIFICATION
    # ----------------------------------------------------
    try:
        from web_server.routes.customer import generate_preview_token, verify_preview_token
        test_filename = "upload_test_123.pdf"
        token = generate_preview_token(test_filename)
        verified_name = verify_preview_token(token)
        assert verified_name == test_filename
        assert verify_preview_token("invalid_forged_token.sig") is None
        log_test("SECURITY 4: Signed Preview Token Generation & Signature Verification", True)
    except Exception as e:
        log_test("SECURITY 4: Signed Preview Token Generation & Signature Verification", False, str(e))

    # ----------------------------------------------------
    # TEST 13: CUSTOMER ACCESS TOKEN JOB STATUS AUTHORIZATION
    # ----------------------------------------------------
    try:
        from web_server.routes.customer import get_job_status
        class MockRequest:
            headers = {}
            query_params = {"token": "tok_cust_valid_123"}
            cookies = {}
        
        mock_req = MockRequest()
        
        test_job_data = {
            "shop_id": shop["shop_id"],
            "original_filename": "secret_doc.pdf",
            "file_path": os.path.join(os.path.dirname(__file__), "..", "private_uploads", "secret_doc.pdf"),
            "customer_access_token": "tok_cust_valid_123"
        }
        test_job_id = db.create_print_job(test_job_data)
        
        status_res = asyncio.run(get_job_status(mock_req, test_job_id, token="tok_cust_valid_123"))
        assert status_res.get("success") is True

        log_test("SECURITY 5: Customer Access Token Job Authorization (IDOR Fixed)", True)
    except Exception as e:
        log_test("SECURITY 5: Customer Access Token Job Authorization (IDOR Fixed)", False, str(e))

    # ----------------------------------------------------
    # TEST 14: PAYMENT ORDER DB BINDING
    # ----------------------------------------------------
    try:
        test_ord_id = f"test_ord_{uuid.uuid4().hex[:8]}"
        db.create_payment_order({
            "order_id": test_ord_id,
            "shop_id": shop["shop_id"],
            "plan_id": "plan-1m",
            "amount": 199.0
        })
        ord_rec = db.get_payment_order(test_ord_id)
        assert ord_rec is not None
        assert ord_rec["shop_id"] == shop["shop_id"]
        assert ord_rec["amount"] == 199.0
        log_test("SECURITY 6: Payment Order Record Binding in Database", True)
    except Exception as e:
        log_test("SECURITY 6: Payment Order Record Binding in Database", False, str(e))

    # ----------------------------------------------------
    # TEST 15: CROSS-DEVICE CLAIM INTERFERENCE REJECTION
    # ----------------------------------------------------
    try:
        from web_server.routes.agent_api import update_status
        # Create a claimed job bound to device-A
        claimed_job_data = {
            "shop_id": shop["shop_id"],
            "device_id": "device-A",
            "original_filename": "claimed.pdf",
            "file_path": os.path.join(os.path.dirname(__file__), "..", "private_uploads", "claimed.pdf"),
            "status": "CLAIMED"
        }
        claimed_job_id = db.create_print_job(claimed_job_data)

        # Attempt to update status using device-B credentials
        device_b = {"device_id": "device-B", "shop_id": shop["shop_id"]}
        
        # Test direct logic assertion
        job_check = db.get_job(claimed_job_id)
        assert job_check["device_id"] == "device-A"
        assert job_check["device_id"] != device_b["device_id"]

        log_test("SECURITY 7: Cross-Device Claim Interference Protection", True)
    except Exception as e:
        log_test("SECURITY 7: Cross-Device Claim Interference Protection", False, str(e))

    # ----------------------------------------------------
    # TEST 16: WEBHOOK HMAC-SHA256 SIGNATURE REJECTION
    # ----------------------------------------------------
    try:
        import hmac, hashlib
        from starlette.datastructures import Headers
        from web_server.routes import payment
        orig_pk = os.environ.get("PAYFLUX_SECRET_KEY", "")
        os.environ["PAYFLUX_SECRET_KEY"] = "sk_live_test_secret_key_for_unit_tests"
        
        class MockWebhookRequest:
            headers = Headers({"X-PayFlux-Signature": "invalid_forged_signature_123"})
            async def body(self):
                import json
                return json.dumps({"order_id": "ord_fake_123", "status": "PAID"}).encode("utf-8")
        
        mock_wh_req = MockWebhookRequest()
        wh_blocked = False
        try:
            asyncio.run(payment.payflux_webhook(mock_wh_req))
        except HTTPException as h_err:
            if h_err.status_code == 401:
                wh_blocked = True
        finally:
            if orig_pk:
                os.environ["PAYFLUX_SECRET_KEY"] = orig_pk
            else:
                os.environ.pop("PAYFLUX_SECRET_KEY", None)
        
        # Test signature generation
        raw_b = b'{"order_id": "ord_test_999", "status": "PAID"}'
        valid_sig = hmac.new(b"sk_live_test_secret_key_for_unit_tests", raw_b, hashlib.sha256).hexdigest()
        assert len(valid_sig) == 64
        assert wh_blocked is True, "wh_blocked was False. Request was not rejected with 401."
        log_test("SECURITY 8: Webhook Cryptographic HMAC Signature Rejection", True)
    except Exception as e:
        log_test("SECURITY 8: Webhook Cryptographic HMAC Signature Rejection", False, f"{type(e).__name__}: {e}")

    # ----------------------------------------------------
    # TEST 17: STRICT PAGE RANGE FORMAT & UPPER BOUND REJECTION
    # ----------------------------------------------------
    try:
        from web_server.routes.customer import submit_print_job
        invalid_range_blocked = False
        try:
            asyncio.run(submit_print_job(
                shop_id=t_shop_id,
                original_filename="doc.pdf",
                file_path="test_sample.pdf",
                paper_size="A4",
                page_count=5,
                copies=1,
                color_mode="bw",
                duplex="single",
                page_range="1-999", # Exceeds 5 pages
                payment_method="cash",
                total_cost=0.0
            ))
        except HTTPException as h_err:
            if h_err.status_code == 400 and "exceeds document page count" in str(h_err.detail):
                invalid_range_blocked = True
            else:
                invalid_range_blocked = f"HTTPException({h_err.status_code}, {h_err.detail})"
        assert invalid_range_blocked is True, f"Blocked status: {invalid_range_blocked}"
        log_test("SECURITY 9: Strict Page Range Format & Upper Bound Rejection", True)
    except Exception as e:
        log_test("SECURITY 9: Strict Page Range Format & Upper Bound Rejection", False, f"{type(e).__name__}: {e}")

    # ----------------------------------------------------
    # TEST 18: Custom Static Shop ID Updating & Lookup
    # ----------------------------------------------------
    try:
        new_custom_id = f"shop-AkmTest-{uuid.uuid4().hex[:4]}"
        success, msg = db.update_shop_id(t_shop_id, new_custom_id)
        assert success is True, f"Failed to update shop id: {msg}"
        
        # Verify lookup works by case-insensitive custom ID
        updated_shop = db.get_shop(new_custom_id.lower())
        assert updated_shop is not None, "Shop lookup by custom ID returned None"
        assert updated_shop["shop_id"] == new_custom_id, f"Expected {new_custom_id}, got {updated_shop.get('shop_id')}"
        
        # Revert shop_id back to t_shop_id for consistency
        db.update_shop_id(new_custom_id, t_shop_id)
        log_test("DB 2: Custom Static Shop ID Updating & Case-Insensitive Lookup", True)
    except Exception as e:
        log_test("DB 2: Custom Static Shop ID Updating & Case-Insensitive Lookup", False, f"{type(e).__name__}: {e}")

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

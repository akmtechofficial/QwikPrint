import sys
import urllib.request
import urllib.error
import json

if sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

def run_live_server_tests():
    print("==================================================")
    print("LIVE FASTAPI SERVER HTTP SECURITY TESTS")
    print("==================================================\n")

    base_url = "http://127.0.0.1:8000"

    # 1. Health Check
    try:
        req = urllib.request.Request(f"{base_url}/health")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            assert resp.status == 200
            assert data["status"] == "ok"
            print("[PASSED] HTTP 1: GET /health Returns HTTP 200 OK")
    except Exception as e:
        print(f"[FAILED] HTTP 1: GET /health - {e}")

    # 2. Unauthenticated Admin API Request
    try:
        req = urllib.request.Request(f"{base_url}/api/admin/stats")
        with urllib.request.urlopen(req) as resp:
            print("[FAILED] HTTP 2: /api/admin/stats Allowed unauthenticated access!")
    except urllib.error.HTTPError as e:
        assert e.code in (401, 403)
        print(f"[PASSED] HTTP 2: GET /api/admin/stats Rejected with HTTP {e.code}")
    except Exception as e:
        print(f"[FAILED] HTTP 2: {e}")

    # 3. Agent API Without Device Headers
    try:
        req = urllib.request.Request(f"{base_url}/api/agent/queue")
        with urllib.request.urlopen(req) as resp:
            print("[FAILED] HTTP 3: /api/agent/queue Allowed unauthenticated access!")
    except urllib.error.HTTPError as e:
        assert e.code in (401, 403)
        print(f"[PASSED] HTTP 3: GET /api/agent/queue Rejected with HTTP {e.code}")
    except Exception as e:
        print(f"[FAILED] HTTP 3: {e}")

    # 4. Payment Creation Without Session
    try:
        req = urllib.request.Request(
            f"{base_url}/api/payments/create-order",
            data=json.dumps({"plan_id": "plan-1m"}).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            print("[FAILED] HTTP 4: /api/payments/create-order Allowed unauthenticated order!")
    except urllib.error.HTTPError as e:
        assert e.code in (401, 403)
        print(f"[PASSED] HTTP 4: POST /api/payments/create-order Rejected with HTTP {e.code}")
    except Exception as e:
        print(f"[FAILED] HTTP 4: {e}")

    print("\n==================================================")
    print("ALL LIVE SERVER HTTP SECURITY TESTS COMPLETED")
    print("==================================================")

if __name__ == "__main__":
    run_live_server_tests()

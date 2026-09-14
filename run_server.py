import os
import sys
import uvicorn

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    is_dev = "--dev" in sys.argv or "--reload" in sys.argv or os.getenv("QWIKPRINT_ENV", "").lower() in ("dev", "development")
    mode_str = "DEVELOPMENT (StatReload Active)" if is_dev else "PRODUCTION (StatReload Disabled)"

    print("==============================================================")
    print(f" [>] QWIKPRINT FASTAPI WEB SERVER - Mode: {mode_str}")
    print("==============================================================")
    print(" -> Shop Owner Dashboard     : http://localhost:8000/dashboard")
    print(" -> Register Shop            : http://localhost:8000/register")
    print(" -> Login                    : http://localhost:8000/login")
    print(" -> Dev mode flag            : --dev / --reload")
    print("==============================================================\n")
    
    uvicorn.run("web_server.server:app", host="0.0.0.0", port=8000, reload=is_dev)


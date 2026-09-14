import os
import sys
import uvicorn

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    print("==============================================================")
    print(" [>] STARTING QWIKPRINT 100% PURE PYTHON FASTAPI WEB SERVER   ")
    print("==============================================================")
    print(" -> Shop Owner Dashboard     : http://localhost:8000/dashboard")
    print(" -> Register Shop            : http://localhost:8000/register")
    print(" -> Login                    : http://localhost:8000/login")
    print("==============================================================\n")
    
    uvicorn.run("web_server.server:app", host="0.0.0.0", port=8000, reload=True)

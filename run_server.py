import os
import sys
import uvicorn

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    print("==============================================================")
    print(" 🚀 STARTING QWIKPRINT 100% PURE PYTHON FASTAPI WEB SERVER   ")
    print("==============================================================")
    print("👉 Customer Portal Endpoint : http://localhost:8000/s/SHOP_AKM_001")
    print("👉 Shop Owner Dashboard     : http://localhost:8000/dashboard")
    print("👉 Health Check Endpoint    : http://localhost:8000/health")
    print("==============================================================\n")
    
    uvicorn.run("web_server.server:app", host="0.0.0.0", port=8000, reload=True)

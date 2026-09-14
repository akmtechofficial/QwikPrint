import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web_server.routes.customer import router as customer_router
from web_server.routes.shop import router as shop_router
from web_server.routes.auth import router as auth_router
from web_server.routes.agent_api import router as agent_router

app = FastAPI(title="QwikPrint 100% Pure Python Print Server", version="1.0.0")

# Mount Static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Routers
app.include_router(customer_router)
app.include_router(shop_router)
app.include_router(auth_router)
app.include_router(agent_router)

@app.get("/health")
async def health():
    return {"status": "ok", "app": "QwikPrint Pure Python Engine"}

if __name__ == "__main__":
    uvicorn.run("web_server.server:app", host="0.0.0.0", port=8000, reload=True)

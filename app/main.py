"""
KLResolute WhatsApp SaaS MVP
FastAPI entry point
Skeleton only – no business logic
"""

from fastapi import FastAPI
from app.health import router as health_router

app = FastAPI(
    title="KLResolute WhatsApp SaaS MVP",
    version="0.1.0"
)

app.include_router(health_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "klresolute-whatsapp-mvp"}

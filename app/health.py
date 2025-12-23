"""
Health check endpoints
Used by Render + ops
"""

from fastapi import APIRouter
from app.db import test_db_connection

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check():
    return {"status": "healthy"}


@router.get("/db")
def db_health_check():
    try:
        test_db_connection()
        return {"database": "healthy"}
    except Exception as e:
        return {"database": "unhealthy", "error": str(e)}

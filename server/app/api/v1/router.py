from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, wards

api_router = APIRouter()

# Mount health check endpoint
api_router.include_router(health.router, tags=["System Health"])

# Mount Authentication & Authorization router
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Authorization"])

# Mount Ward Management router
api_router.include_router(wards.router, prefix="/wards", tags=["Ward Management"])


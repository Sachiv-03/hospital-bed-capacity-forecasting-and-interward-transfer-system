from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, hospitals, wards, beds, ingestion, capacity

api_router = APIRouter()

# System Health
api_router.include_router(health.router, tags=["System Health"])

# Authentication & Authorization
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Authorization"])

# Hospital Management
api_router.include_router(hospitals.router, prefix="/hospitals", tags=["Hospital Management"])

# Ward Management
api_router.include_router(wards.router, prefix="/wards", tags=["Ward Management"])

# Phase 6 — Bed Management
api_router.include_router(beds.router, prefix="/beds", tags=["Bed Management"])

# Phase 6 — Data Ingestion Pipeline
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["Data Ingestion"])

# Phase 6 — Capacity APIs (mounted at root /api/v1 so paths are /hospitals/{id}/capacity and /wards/{id}/capacity)
api_router.include_router(capacity.router, tags=["Capacity"])

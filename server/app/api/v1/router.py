from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, hospitals, wards, beds, ingestion, capacity, alerts, forecasting, transfers

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

# Stage 2 — Capacity Alerts
api_router.include_router(alerts.router, prefix="/alerts", tags=["Capacity Alerts"])

# Phase 6 — Capacity APIs
api_router.include_router(capacity.router, tags=["Capacity"])

# Stage 3 — Bed Capacity Forecasting (mounted at root for /wards/{id}/forecast and /hospitals/{id}/forecast, and at /forecasting)
api_router.include_router(forecasting.router, tags=["Bed Capacity Forecasting"])
api_router.include_router(forecasting.router, prefix="/forecasting", tags=["Bed Capacity Forecasting"])

# Stage 4 — Inter-Ward Transfer Decision Support System
api_router.include_router(transfers.router, prefix="/transfers", tags=["Inter-Ward Transfers"])





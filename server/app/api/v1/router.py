from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, hospitals, wards, beds, patients, admissions, occupancy, ingestion, capacity, alerts, forecasting, transfers

api_router = APIRouter()

# System Health
api_router.include_router(health.router, tags=["System Health"])

# Authentication & Authorization
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Authorization"])

# Hospital Management
api_router.include_router(hospitals.router, prefix="/hospitals", tags=["Hospital Management"])

# Ward Management
api_router.include_router(wards.router, prefix="/wards", tags=["Ward Management"])

# Bed Management
api_router.include_router(beds.router, prefix="/beds", tags=["Bed Management"])

# Phase 5 — Patient & Admission / Discharge Management
api_router.include_router(patients.router, prefix="/patients", tags=["Patient Management"])
api_router.include_router(admissions.router, prefix="/admissions", tags=["Admission / Discharge Management"])

# Phase 6 — Occupancy & Capacity Tracking
api_router.include_router(occupancy.router, prefix="/occupancy", tags=["Occupancy & Capacity Tracking"])

# Data Ingestion Pipeline
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["Data Ingestion"])

# Stage 2 — Capacity Alerts
api_router.include_router(alerts.router, prefix="/alerts", tags=["Capacity Alerts"])

# Capacity APIs
api_router.include_router(capacity.router, tags=["Capacity"])

# Stage 3 — Bed Capacity Forecasting
api_router.include_router(forecasting.router, tags=["Bed Capacity Forecasting"])
api_router.include_router(forecasting.router, prefix="/forecasting", tags=["Bed Capacity Forecasting"])

# Stage 4 — Inter-Ward Transfer Decision Support System
api_router.include_router(transfers.router, prefix="/transfers", tags=["Inter-Ward Transfers"])





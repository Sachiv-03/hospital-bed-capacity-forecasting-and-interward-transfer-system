from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.database import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "healthy"})
    database: str = Field(..., json_schema_extra={"example": "connected"})
    service: str = Field(..., json_schema_extra={"example": "Hospital Bed Capacity Forecasting API"})
    version: str = Field(..., json_schema_extra={"example": "1.0.0"})


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check Endpoint",
    description="Returns health status of API and verifies live Neon PostgreSQL database connectivity.",
    tags=["System Health"],
)
def get_health(response: Response, db: Session = Depends(get_db)):
    """
    Health monitoring endpoint that tests live database connectivity.
    """
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "service": "Hospital Bed Capacity Forecasting API",
            "version": "1.0.0",
        }
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "service": "Hospital Bed Capacity Forecasting API",
            "version": "1.0.0",
        }

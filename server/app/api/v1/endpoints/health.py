from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    service: str = Field(..., example="Hospital Bed Capacity Forecasting API")
    version: str = Field(..., example="1.0.0")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check Endpoint",
    description="Returns health status of the Hospital Bed Capacity Forecasting API.",
    tags=["System Health"],
)
def get_health() -> dict:
    """
    Health monitoring endpoint used by load balancers and container orchestrators.
    """
    return {
        "status": "healthy",
        "service": "Hospital Bed Capacity Forecasting API",
        "version": "1.0.0",
    }

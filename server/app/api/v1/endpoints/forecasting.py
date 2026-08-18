from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User, UserRole
from app.schemas.forecast import (
    WardForecastResponse,
    HospitalForecastResponse,
    ForecastHistoryResponse,
    ModelPerformanceResponse,
    ManualForecastGenerateResponse,
)
from app.services.forecasting.forecast_service import ForecastService

router = APIRouter()

ALL_ROLES = [
    UserRole.SUPER_ADMIN.value,
    UserRole.ADMIN.value,
    UserRole.DOCTOR.value,
    UserRole.NURSE.value,
    UserRole.RECEPTIONIST.value,
]
ADMIN_ROLES = [UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value]


@router.get(
    "/wards/{ward_id}/forecast",
    response_model=WardForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ward Bed Capacity Forecast",
    description="Generates or retrieves 1-day, 3-day, or 7-day predicted bed capacity, occupancy %, prediction bounds, and future risk classification for a ward.",
)
def get_ward_forecast(
    ward_id: int,
    horizon: int = Query(7, ge=1, le=30, description="Forecast horizon in days (1, 3, or 7)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    target_hospital_id = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    try:
        return ForecastService.get_ward_latest_forecast(
            db=db,
            ward_id=ward_id,
            hospital_id=target_hospital_id,
            horizon=horizon,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate ward forecast: {str(e)}")


@router.get(
    "/hospitals/{hospital_id}/forecast",
    response_model=HospitalForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Hospital-Level Capacity Forecast",
    description="Aggregates ward-level bed forecasts into a hospital-wide predicted occupancy timeline.",
)
def get_hospital_forecast(
    hospital_id: int,
    horizon: int = Query(7, ge=1, le=30, description="Forecast horizon in days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    # Multi-hospital security check
    if current_user.role != UserRole.SUPER_ADMIN.value and current_user.hospital_id != hospital_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to another hospital's forecast is forbidden")

    try:
        return ForecastService.get_hospital_forecast(
            db=db,
            hospital_id=hospital_id,
            horizon=horizon,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate hospital forecast: {str(e)}")


@router.get(
    "/wards/{ward_id}/forecast/history",
    response_model=ForecastHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Forecast History Runs",
    description="Returns previous forecast runs for evaluating past predictions vs actual outcomes.",
)
def get_forecast_history(
    ward_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    target_hospital_id = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    try:
        return ForecastService.get_forecast_history(
            db=db,
            ward_id=ward_id,
            hospital_id=target_hospital_id,
            page=page,
            limit=limit,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/performance",
    response_model=ModelPerformanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Model Performance & Comparison Metrics",
    description="Compares Baseline (Moving Average) vs Primary SARIMA model performance metrics (MAE, RMSE, MAPE) for a ward.",
)
def get_model_performance(
    ward_id: int = Query(..., description="Ward ID to evaluate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    target_hospital_id = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    try:
        return ForecastService.get_model_performance(
            db=db,
            ward_id=ward_id,
            hospital_id=target_hospital_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/generate",
    response_model=ManualForecastGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger Manual Forecast Generation",
    description="Protected admin endpoint to trigger immediate batch forecast generation and persistence across hospital wards.",
)
def generate_forecasts(
    hospital_id: Optional[int] = Query(None, description="Optional hospital ID filter (SUPER_ADMIN only)"),
    horizon: int = Query(7, ge=1, le=30, description="Forecast horizon in days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    if current_user.role == UserRole.SUPER_ADMIN.value:
        target_hospital_id = hospital_id
    else:
        target_hospital_id = current_user.hospital_id

    try:
        return ForecastService.generate_all_forecasts(
            db=db,
            hospital_id=target_hospital_id,
            horizon=horizon,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Manual forecast trigger failed: {str(e)}")

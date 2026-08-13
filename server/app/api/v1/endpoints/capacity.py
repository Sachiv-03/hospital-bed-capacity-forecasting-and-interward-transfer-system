"""
Capacity API — ward-level, hospital-level, snapshots, history, and daily summary endpoints.
"""
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.models.ward import Ward
from app.schemas.capacity import (
    HospitalCapacityResponse,
    WardCapacityResponse,
    OccupancySnapshotResponse,
    OccupancySnapshotListResponse,
    DailySummaryResponse,
    DataQualityReportResponse,
    ForecastingDatasetResponse,
    ManualSnapshotGenerateResponse,
)
from app.services.capacity_service import CapacityService
from app.services.snapshot_service import SnapshotService
from app.services.historical_service import HistoricalService

router = APIRouter()
ADMIN_ROLES = [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]


def _resolve_hospital_id(current_user: User, hospital_id: int) -> int:
    """Enforce hospital isolation — non-SUPER_ADMIN can only access their own hospital."""
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return hospital_id
    if current_user.hospital_id != hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this hospital's capacity data",
        )
    return hospital_id


@router.get(
    "/hospitals/{hospital_id}/capacity",
    response_model=HospitalCapacityResponse,
    summary="Get hospital-level capacity summary",
)
def get_hospital_capacity(
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _resolve_hospital_id(current_user, hospital_id)
    return CapacityService.get_hospital_capacity(db, hospital_id)


@router.get(
    "/wards/{ward_id}/capacity",
    response_model=WardCapacityResponse,
    summary="Get ward-level capacity",
)
def get_ward_capacity(
    ward_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role == UserRole.SUPER_ADMIN.value:
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
        requesting_hospital_id = ward.hospital_id
    else:
        requesting_hospital_id = current_user.hospital_id

    return CapacityService.get_ward_capacity(db, ward_id, requesting_hospital_id)


# ── Stage 2 Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/capacity/snapshots/generate",
    response_model=ManualSnapshotGenerateResponse,
    summary="[DEV/TEST] Manually trigger occupancy snapshot creation",
)
def generate_snapshots(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    result = SnapshotService.generate_snapshots_for_all_hospitals(db)
    return ManualSnapshotGenerateResponse(
        snapshots_created=result["snapshots_created"],
        hospitals_processed=result["hospitals_processed"],
        wards_processed=result["wards_processed"],
    )


@router.get(
    "/wards/{ward_id}/capacity/history",
    response_model=OccupancySnapshotListResponse,
    summary="Get ward historical capacity snapshots",
)
def get_ward_capacity_history(
    ward_id: int,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    target_hosp = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    snaps = HistoricalService.get_ward_snapshot_history(
        db, ward_id=ward_id, hospital_id=target_hosp, start_date=start_date, end_date=end_date, limit=limit
    )

    items = []
    for s in snaps:
        items.append(
            OccupancySnapshotResponse(
                id=s.id,
                hospital_id=s.hospital_id,
                ward_id=s.ward_id,
                ward_name=s.ward.name if s.ward else "",
                snapshot_time=s.snapshot_time.isoformat(),
                total_beds=s.total_beds,
                occupied_beds=s.occupied_beds,
                available_beds=s.available_beds,
                cleaning_beds=s.cleaning_beds,
                reserved_beds=s.reserved_beds,
                maintenance_beds=s.maintenance_beds,
                occupancy_percentage=s.occupancy_percentage,
            )
        )
    return OccupancySnapshotListResponse(items=items, total=len(items))


@router.get(
    "/hospitals/{hospital_id}/capacity/history",
    summary="Get aggregated hospital historical capacity snapshots",
)
def get_hospital_capacity_history(
    hospital_id: int,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _resolve_hospital_id(current_user, hospital_id)
    return HistoricalService.get_hospital_snapshot_history(
        db, hospital_id=hospital_id, start_date=start_date, end_date=end_date, limit=limit
    )


@router.get(
    "/wards/{ward_id}/daily-summary",
    response_model=List[DailySummaryResponse],
    summary="Get ward daily operational summary (occupancy & movements)",
)
def get_ward_daily_summary(
    ward_id: int,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    target_hosp = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    return HistoricalService.get_daily_summary(
        db, ward_id=ward_id, hospital_id=target_hosp, start_date=start_date, end_date=end_date
    )


@router.get(
    "/capacity/data-quality",
    response_model=DataQualityReportResponse,
    summary="Run data quality checks on historical capacity dataset",
)
def get_data_quality_report(
    hospital_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.SUPER_ADMIN.value:
        target_hosp = current_user.hospital_id
    else:
        target_hosp = hospital_id

    return HistoricalService.get_data_quality_report(db, hospital_id=target_hosp)


@router.get(
    "/capacity/forecasting-dataset",
    response_model=ForecastingDatasetResponse,
    summary="Get clean forecasting-ready historical time series dataset",
)
def get_forecasting_dataset(
    hospital_id: Optional[int] = Query(None),
    ward_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.SUPER_ADMIN.value:
        target_hosp = current_user.hospital_id
    else:
        target_hosp = hospital_id

    return HistoricalService.get_forecasting_dataset(
        db, hospital_id=target_hosp, ward_id=ward_id, start_date=start_date, end_date=end_date
    )

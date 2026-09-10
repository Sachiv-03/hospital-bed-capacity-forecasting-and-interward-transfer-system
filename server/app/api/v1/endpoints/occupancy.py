from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.capacity import (
    HospitalCapacityResponse,
    WardCapacityResponse,
    OccupancySummaryResponse,
    OccupancySnapshotListResponse,
    ManualSnapshotGenerateResponse,
)
from app.services.capacity_service import CapacityService
from app.services.snapshot_service import SnapshotService
from app.services.historical_service import HistoricalService

router = APIRouter()
ADMIN_ROLES = [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]


def resolve_hospital_id(current_user: User, requested_hospital_id: Optional[int] = None) -> int:
    if current_user.role == UserRole.SUPER_ADMIN.value:
        if requested_hospital_id is not None:
            return requested_hospital_id
        if current_user.hospital_id is not None:
            return current_user.hospital_id
        return 1
    if current_user.hospital_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not associated with any hospital")
    if requested_hospital_id is not None and requested_hospital_id != current_user.hospital_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-hospital access forbidden")
    return current_user.hospital_id


@router.get("/hospital", response_model=HospitalCapacityResponse, summary="Get current hospital capacity")
def get_hospital_occupancy(
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN override"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return CapacityService.get_hospital_capacity(db, hospital_id=resolved_hid)


@router.get("/summary", response_model=OccupancySummaryResponse, summary="Get operational command occupancy summary")
def get_occupancy_summary(
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN override"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return CapacityService.get_occupancy_summary(db, hospital_id=resolved_hid)


@router.get("/wards", response_model=List[WardCapacityResponse], summary="Get capacity across all wards in hospital")
def get_all_wards_occupancy(
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN override"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return CapacityService.get_all_ward_capacities(db, hospital_id=resolved_hid)


@router.get("/wards/{ward_id}", response_model=WardCapacityResponse, summary="Get specific ward capacity")
def get_single_ward_occupancy(
    ward_id: int,
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN override"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return CapacityService.get_ward_capacity(db, ward_id=ward_id, requesting_hospital_id=resolved_hid)


@router.get("/trends", summary="Get historical occupancy trends")
def get_occupancy_trends(
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN override"),
    ward_id: Optional[int] = Query(None, description="Optional ward filter"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    if ward_id:
        return HistoricalService.get_ward_snapshot_history(
            db, ward_id=ward_id, hospital_id=resolved_hid, start_date=start_date, end_date=end_date, limit=limit
        )
    return HistoricalService.get_hospital_snapshot_history(
        db, hospital_id=resolved_hid, start_date=start_date, end_date=end_date, limit=limit
    )


@router.post("/snapshots", response_model=ManualSnapshotGenerateResponse, summary="Trigger occupancy snapshot creation")
def generate_snapshots(
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN override"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    result = SnapshotService.generate_snapshots_for_hospital(db, hospital_id=resolved_hid)
    return ManualSnapshotGenerateResponse(
        snapshots_created=result.get("snapshots_created", 1),
        hospitals_processed=1,
        wards_processed=result.get("wards_processed", 1)
    )

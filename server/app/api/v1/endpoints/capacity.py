"""
Capacity API — ward-level and hospital-level occupancy endpoints.
All values are computed live from the beds table.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.capacity import HospitalCapacityResponse, WardCapacityResponse
from app.services.capacity_service import CapacityService
from fastapi import HTTPException, status

router = APIRouter()


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
    description=(
        "Returns total beds, occupied, available, cleaning, reserved, and maintenance counts "
        "plus an overall occupancy percentage and NORMAL/MODERATE/HIGH/CRITICAL status."
    ),
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
    description="Returns bed counts and occupancy percentage for a single ward.",
)
def get_ward_capacity(
    ward_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Determine requesting hospital_id — SUPER_ADMIN can access all wards
    if current_user.role == UserRole.SUPER_ADMIN.value:
        # Get ward's hospital_id to pass to the service
        from app.models.ward import Ward
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
        requesting_hospital_id = ward.hospital_id
    else:
        requesting_hospital_id = current_user.hospital_id

    return CapacityService.get_ward_capacity(db, ward_id, requesting_hospital_id)

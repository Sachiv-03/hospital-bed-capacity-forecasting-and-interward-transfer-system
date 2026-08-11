"""
Beds API — CRUD endpoints for managing individual beds.
Enforces hospital-level isolation on every operation.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.bed import BedCreate, BedListResponse, BedResponse, BedUpdate
from app.services.bed_service import BedService

router = APIRouter()

ADMIN_ROLES = [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]


def _resolve_hospital_id(current_user: User, requested_hospital_id: Optional[int] = None) -> int:
    """
    Return the effective hospital_id for the requesting user.
    SUPER_ADMIN may supply an explicit hospital_id; everyone else uses their own.
    """
    if current_user.role == UserRole.SUPER_ADMIN.value:
        if requested_hospital_id is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="SUPER_ADMIN must specify hospital_id")
        return requested_hospital_id
    return current_user.hospital_id


@router.get("", response_model=BedListResponse, summary="List beds (hospital-scoped)")
def list_beds(
    ward_id: Optional[int] = Query(None, description="Filter by ward"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by bed status"),
    bed_type: Optional[str] = Query(None, description="Filter by bed type"),
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only: specify hospital"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = _resolve_hospital_id(current_user, hospital_id)
    return BedService.get_beds(
        db,
        hospital_id=resolved_hid,
        ward_id=ward_id,
        status_filter=status_filter,
        bed_type_filter=bed_type,
        page=page,
        limit=limit,
    )


@router.post("", response_model=BedResponse, status_code=status.HTTP_201_CREATED, summary="Create a bed")
def create_bed(
    bed_in: BedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    resolved_hid = _resolve_hospital_id(current_user, bed_in.hospital_id)
    bed = BedService.create_bed(db, bed_in, resolved_hid)
    resp = BedResponse(
        id=bed.id,
        hospital_id=bed.hospital_id,
        ward_id=bed.ward_id,
        bed_number=bed.bed_number,
        status=bed.status,
        bed_type=bed.bed_type,
        created_at=bed.created_at,
        updated_at=bed.updated_at,
        ward_name=bed.ward.name if bed.ward else None,
        hospital_name=bed.hospital.name if bed.hospital else None,
    )
    return resp


@router.get("/{bed_id}", response_model=BedResponse, summary="Get bed details")
def get_bed(
    bed_id: int,
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = _resolve_hospital_id(current_user, hospital_id)
    bed = BedService.get_bed(db, bed_id, resolved_hid)
    return BedResponse(
        id=bed.id,
        hospital_id=bed.hospital_id,
        ward_id=bed.ward_id,
        bed_number=bed.bed_number,
        status=bed.status,
        bed_type=bed.bed_type,
        created_at=bed.created_at,
        updated_at=bed.updated_at,
        ward_name=bed.ward.name if bed.ward else None,
        hospital_name=bed.hospital.name if bed.hospital else None,
    )


@router.put("/{bed_id}", response_model=BedResponse, summary="Update a bed")
def update_bed(
    bed_id: int,
    bed_update: BedUpdate,
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    resolved_hid = _resolve_hospital_id(current_user, hospital_id)
    bed = BedService.update_bed(db, bed_id, bed_update, resolved_hid)
    return BedResponse(
        id=bed.id,
        hospital_id=bed.hospital_id,
        ward_id=bed.ward_id,
        bed_number=bed.bed_number,
        status=bed.status,
        bed_type=bed.bed_type,
        created_at=bed.created_at,
        updated_at=bed.updated_at,
        ward_name=bed.ward.name if bed.ward else None,
        hospital_name=bed.hospital.name if bed.hospital else None,
    )


@router.delete("/{bed_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a bed")
def delete_bed(
    bed_id: int,
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    resolved_hid = _resolve_hospital_id(current_user, hospital_id)
    BedService.delete_bed(db, bed_id, resolved_hid)

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User, UserRole
from app.schemas.hospital import (
    HospitalCreate,
    HospitalUpdate,
    HospitalResponse,
    HospitalListResponse,
    HospitalStatusEnum,
)
from app.services.hospital_service import HospitalService

router = APIRouter()

SUPER_ADMIN_ONLY = [UserRole.SUPER_ADMIN.value]
ALL_ROLES = [
    UserRole.SUPER_ADMIN.value,
    UserRole.ADMIN.value,
    UserRole.DOCTOR.value,
    UserRole.NURSE.value,
    UserRole.RECEPTIONIST.value,
]


@router.get(
    "",
    response_model=HospitalListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Hospitals",
    description="Returns a paginated list of hospitals. Requires SUPER_ADMIN role.",
)
def list_hospitals(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name, code, city, or state"),
    status: Optional[HospitalStatusEnum] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SUPER_ADMIN_ONLY)),
):
    status_str = status.value if status else None
    return HospitalService.get_hospitals(
        db=db,
        page=page,
        limit=limit,
        search=search,
        status_filter=status_str,
    )


@router.get(
    "/{hospital_id}",
    response_model=HospitalResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Hospital Details",
    description="Returns detailed information for a specific hospital.",
)
def get_hospital(
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    # Non-super admins can only view their own hospital details
    if current_user.role != UserRole.SUPER_ADMIN.value:
        if current_user.hospital_id != hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view details for your assigned hospital."
            )

    return HospitalService.get_hospital_by_id(db=db, hospital_id=hospital_id)


@router.post(
    "",
    response_model=HospitalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Hospital",
    description="Creates a new hospital facility. Requires SUPER_ADMIN role.",
)
def create_hospital(
    hospital_in: HospitalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SUPER_ADMIN_ONLY)),
):
    return HospitalService.create_hospital(db=db, hospital_in=hospital_in)


@router.put(
    "/{hospital_id}",
    response_model=HospitalResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Hospital",
    description="Updates existing hospital details. Requires SUPER_ADMIN role.",
)
def update_hospital(
    hospital_id: int,
    hospital_in: HospitalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SUPER_ADMIN_ONLY)),
):
    return HospitalService.update_hospital(db=db, hospital_id=hospital_id, hospital_in=hospital_in)


@router.delete(
    "/{hospital_id}",
    response_model=HospitalResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate Hospital",
    description="Safely deactivates a hospital facility by setting status to INACTIVE. Requires SUPER_ADMIN role.",
)
def deactivate_hospital(
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SUPER_ADMIN_ONLY)),
):
    return HospitalService.deactivate_hospital(db=db, hospital_id=hospital_id)

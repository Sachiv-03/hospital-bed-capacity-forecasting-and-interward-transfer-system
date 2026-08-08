from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User, UserRole
from app.schemas.ward import (
    WardCreate,
    WardUpdate,
    WardResponse,
    WardListResponse,
    WardStatisticsResponse,
    WardOccupancyResponse,
    WardStatusEnum,
    WardTypeEnum,
)
from app.services.ward_service import WardService

router = APIRouter()

# Role presets for cleaner dependencies
ALL_ROLES = [UserRole.ADMIN.value, UserRole.DOCTOR.value, UserRole.NURSE.value, UserRole.RECEPTIONIST.value]
ADMIN_ONLY = [UserRole.ADMIN.value]


@router.get(
    "/statistics",
    response_model=WardStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ward Statistics",
    description="Returns aggregate hospital ward capacity, total wards, and active/inactive counts.",
)
def get_ward_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    return WardService.get_ward_statistics(db)


@router.get(
    "",
    response_model=WardListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Wards",
    description="Returns a paginated list of hospital wards with search and filtering capabilities.",
)
def list_wards(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name, department, or description"),
    ward_type: Optional[WardTypeEnum] = Query(None, description="Filter by ward type"),
    department: Optional[str] = Query(None, description="Filter by department"),
    status: Optional[WardStatusEnum] = Query(None, description="Filter by ward status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    type_str = ward_type.value if ward_type else None
    status_str = status.value if status else None
    return WardService.get_wards(
        db=db,
        page=page,
        limit=limit,
        search=search,
        ward_type=type_str,
        department=department,
        status_filter=status_str,
    )


@router.get(
    "/{ward_id}",
    response_model=WardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ward Details",
    description="Returns detailed information for a specific ward by ID.",
)
def get_ward(
    ward_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    return WardService.get_ward_by_id(db=db, ward_id=ward_id)


@router.get(
    "/{ward_id}/occupancy",
    response_model=WardOccupancyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ward Occupancy",
    description="Returns ward occupancy and capacity data.",
)
def get_ward_occupancy(
    ward_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    return WardService.get_ward_occupancy(db=db, ward_id=ward_id)


@router.post(
    "",
    response_model=WardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Ward",
    description="Creates a new hospital ward. Requires ADMIN role.",
)
def create_ward(
    ward_in: WardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ONLY)),
):
    return WardService.create_ward(db=db, ward_in=ward_in)


@router.put(
    "/{ward_id}",
    response_model=WardResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Ward",
    description="Updates existing ward information. Requires ADMIN role.",
)
def update_ward(
    ward_id: int,
    ward_in: WardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ONLY)),
):
    return WardService.update_ward(db=db, ward_id=ward_id, ward_in=ward_in)


@router.delete(
    "/{ward_id}",
    response_model=WardResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate Ward",
    description="Safely deactivates a ward by setting status to INACTIVE. Requires ADMIN role.",
)
def deactivate_ward(
    ward_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ONLY)),
):
    return WardService.deactivate_ward(db=db, ward_id=ward_id)

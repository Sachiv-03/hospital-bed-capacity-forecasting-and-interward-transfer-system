from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.admission import (
    AdmissionCreate, DischargeCreate, AdmissionResponse, AdmissionListResponse
)
from app.schemas.bed import BedResponse
from app.services.admission_service import AdmissionService

router = APIRouter()

ALLOWED_ADMISSION_ROLES = [
    UserRole.SUPER_ADMIN.value,
    UserRole.ADMIN.value,
    UserRole.DOCTOR.value,
    UserRole.NURSE.value,
    UserRole.RECEPTIONIST.value,
]


def resolve_hospital_id(current_user: User, requested_hospital_id: Optional[int] = None) -> int:
    if current_user.role == UserRole.SUPER_ADMIN.value:
        if requested_hospital_id is not None:
            return requested_hospital_id
        if current_user.hospital_id is not None:
            return current_user.hospital_id
        return 1
    if current_user.hospital_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not associated with any hospital")
    return current_user.hospital_id


@router.post("", response_model=AdmissionResponse, status_code=status.HTTP_201_CREATED, summary="Admit a patient")
def admit_patient(
    admission_in: AdmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALLOWED_ADMISSION_ROLES)),
):
    resolved_hid = resolve_hospital_id(current_user, admission_in.hospital_id)
    return AdmissionService.admit_patient(
        db,
        admission_in=admission_in,
        hospital_id=resolved_hid,
        user_id=current_user.id
    )


@router.get("", response_model=AdmissionListResponse, summary="List admissions (hospital-scoped)")
def list_admissions(
    ward_id: Optional[int] = Query(None, description="Filter by ward ID"),
    patient_id: Optional[int] = Query(None, description="Filter by patient ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (ADMITTED/DISCHARGED)"),
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return AdmissionService.get_admissions(
        db,
        hospital_id=resolved_hid,
        ward_id=ward_id,
        patient_id=patient_id,
        status_filter=status_filter,
        page=page,
        limit=limit
    )


@router.get("/{admission_id}", response_model=AdmissionResponse, summary="Get admission details")
def get_admission(
    admission_id: int,
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return AdmissionService.get_admission_response(db, admission_id=admission_id, hospital_id=resolved_hid)


@router.post("/{admission_id}/discharge", response_model=AdmissionResponse, summary="Discharge a patient")
def discharge_patient(
    admission_id: int,
    discharge_in: DischargeCreate = DischargeCreate(),
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALLOWED_ADMISSION_ROLES)),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return AdmissionService.discharge_patient(
        db,
        admission_id=admission_id,
        discharge_in=discharge_in,
        hospital_id=resolved_hid,
        user_id=current_user.id
    )

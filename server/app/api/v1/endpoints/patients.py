from typing import Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.patient import (
    PatientCreate, PatientUpdate, PatientStatusUpdate, PatientResponse, PatientListResponse
)
from app.services.patient_service import PatientService

router = APIRouter()

ALLOWED_PATIENT_ROLES = [
    UserRole.SUPER_ADMIN.value,
    UserRole.ADMIN.value,
    UserRole.DOCTOR.value,
    UserRole.NURSE.value,
    UserRole.RECEPTIONIST.value,
]

ADMIN_ROLES = [
    UserRole.SUPER_ADMIN.value,
    UserRole.ADMIN.value,
    UserRole.RECEPTIONIST.value,
    UserRole.NURSE.value,
]


def resolve_hospital_id(current_user: User, requested_hospital_id: Optional[int] = None) -> int:
    if current_user.role == UserRole.SUPER_ADMIN.value:
        if requested_hospital_id is not None:
            return requested_hospital_id
        if current_user.hospital_id is not None:
            return current_user.hospital_id
        return 1  # Default to primary hospital for super admin
    if current_user.hospital_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not associated with any hospital")
    return current_user.hospital_id


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED, summary="Register a patient")
def create_patient(
    patient_in: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALLOWED_PATIENT_ROLES)),
):
    resolved_hid = resolve_hospital_id(current_user, patient_in.hospital_id)
    return PatientService.create_patient(db, patient_in, hospital_id=resolved_hid, user_id=current_user.id)


@router.get("", response_model=PatientListResponse, summary="List & search patients (hospital-scoped)")
def list_patients(
    search: Optional[str] = Query(None, description="Search by identifier, name, phone, or email"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (ACTIVE/INACTIVE)"),
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only: specify hospital"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return PatientService.get_patients(
        db,
        hospital_id=resolved_hid,
        search=search,
        status_filter=status_filter,
        page=page,
        limit=limit
    )


@router.get("/{patient_id}", response_model=PatientResponse, summary="Get patient details")
def get_patient(
    patient_id: int,
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return PatientService.get_patient_response(db, patient_id=patient_id, hospital_id=resolved_hid)


@router.put("/{patient_id}", response_model=PatientResponse, summary="Update patient information")
def update_patient(
    patient_id: int,
    patient_update: PatientUpdate,
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALLOWED_PATIENT_ROLES)),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return PatientService.update_patient(
        db,
        patient_id=patient_id,
        patient_update=patient_update,
        hospital_id=resolved_hid,
        user_id=current_user.id
    )


@router.patch("/{patient_id}/status", response_model=PatientResponse, summary="Update patient active status")
def update_patient_status(
    patient_id: int,
    status_update: PatientStatusUpdate,
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALLOWED_PATIENT_ROLES)),
):
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    return PatientService.update_patient(
        db,
        patient_id=patient_id,
        patient_update=PatientUpdate(status=status_update.status),
        hospital_id=resolved_hid,
        user_id=current_user.id
    )


@router.get("/{patient_id}/admissions", summary="Get patient admissions history")
def get_patient_admissions(
    patient_id: int,
    hospital_id: Optional[int] = Query(None, description="SUPER_ADMIN only"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.admission_service import AdmissionService
    resolved_hid = resolve_hospital_id(current_user, hospital_id)
    # Validate patient exists in hospital
    PatientService.get_patient(db, patient_id=patient_id, hospital_id=resolved_hid)
    return AdmissionService.get_admissions(
        db,
        hospital_id=resolved_hid,
        patient_id=patient_id
    )

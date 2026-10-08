import logging
from math import ceil
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload

from app.models.patient import Patient, PatientStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.hospital import Hospital
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse, PatientListResponse, CurrentAdmissionInfo
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class PatientService:

    @staticmethod
    def generate_patient_identifier(db: Session, hospital_id: int) -> str:
        """Generate a unique hospital-scoped patient identifier (e.g., HOSP001-P000001)."""
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        hosp_code = hospital.code if hospital and hospital.code else f"HOSP{hospital_id}"
        
        # Count existing patients in this hospital to construct sequential number
        total_count = db.query(Patient).filter(Patient.hospital_id == hospital_id).count()
        seq = total_count + 1
        
        identifier = f"{hosp_code}-P{seq:06d}"
        
        # Guard against collision if a custom identifier was previously created
        while db.query(Patient).filter(Patient.hospital_id == hospital_id, Patient.patient_identifier == identifier).first():
            seq += 1
            identifier = f"{hosp_code}-P{seq:06d}"
            
        return identifier

    @staticmethod
    def create_patient(db: Session, patient_in: PatientCreate, hospital_id: int, user_id: Optional[int] = None) -> PatientResponse:
        """Register a new patient scoped to the user's hospital."""
        target_hospital_id = patient_in.hospital_id if patient_in.hospital_id else hospital_id
        
        hospital = db.query(Hospital).filter(Hospital.id == target_hospital_id).first()
        if not hospital:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
        
        # Auto-generate identifier if not supplied
        identifier = patient_in.patient_identifier
        if not identifier or not identifier.strip():
            identifier = PatientService.generate_patient_identifier(db, target_hospital_id)
        else:
            identifier = identifier.strip()
            # Check unique constraint
            existing = db.query(Patient).filter(
                Patient.hospital_id == target_hospital_id,
                Patient.patient_identifier == identifier
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Patient identifier '{identifier}' already exists in this hospital"
                )

        patient = Patient(
            hospital_id=target_hospital_id,
            patient_identifier=identifier,
            first_name=patient_in.first_name.strip(),
            last_name=patient_in.last_name.strip(),
            date_of_birth=patient_in.date_of_birth,
            gender=patient_in.gender,
            phone=patient_in.phone,
            email=patient_in.email,
            address=patient_in.address,
            emergency_contact_name=patient_in.emergency_contact_name,
            emergency_contact_phone=patient_in.emergency_contact_phone,
            status=PatientStatus.ACTIVE.value,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        # Audit log
        AuditService.log_event(
            db=db,
            hospital_id=target_hospital_id,
            user_id=user_id,
            action="PATIENT_CREATED",
            resource_type="PATIENT",
            resource_id=str(patient.id),
            metadata={"patient_identifier": patient.patient_identifier, "name": f"{patient.first_name} {patient.last_name}"}
        )

        return PatientService.get_patient_response(db, patient.id, target_hospital_id)

    @staticmethod
    def get_patient(db: Session, patient_id: int, hospital_id: int) -> Patient:
        """Fetch raw Patient model ensuring hospital isolation."""
        patient = db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.hospital_id == hospital_id
        ).first()
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found in this hospital")
        return patient

    @staticmethod
    def get_patient_response(db: Session, patient_id: int, hospital_id: int) -> PatientResponse:
        """Fetch patient with response model including active admission status."""
        patient = PatientService.get_patient(db, patient_id, hospital_id)
        
        # Check active admission
        active_adm = db.query(Admission).filter(
            Admission.patient_id == patient.id,
            Admission.status == AdmissionStatus.ADMITTED.value
        ).first()

        current_adm_info = None
        if active_adm:
            current_adm_info = CurrentAdmissionInfo(
                admission_id=active_adm.id,
                admission_number=active_adm.admission_number,
                admission_date=active_adm.admission_date,
                ward_id=active_adm.ward_id,
                ward_name=active_adm.ward.name if active_adm.ward else "",
                bed_id=active_adm.bed_id,
                bed_number=active_adm.bed.bed_number if active_adm.bed else "",
                status=active_adm.status
            )

        return PatientResponse(
            id=patient.id,
            hospital_id=patient.hospital_id,
            patient_identifier=patient.patient_identifier,
            first_name=patient.first_name,
            last_name=patient.last_name,
            date_of_birth=patient.date_of_birth,
            gender=patient.gender,
            phone=patient.phone,
            email=patient.email,
            address=patient.address,
            emergency_contact_name=patient.emergency_contact_name,
            emergency_contact_phone=patient.emergency_contact_phone,
            status=patient.status,
            created_at=patient.created_at,
            updated_at=patient.updated_at,
            hospital_name=patient.hospital.name if patient.hospital else None,
            current_admission=current_adm_info
        )

    @staticmethod
    def get_patients(
        db: Session,
        hospital_id: int,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        limit: int = 50
    ) -> PatientListResponse:
        """List patients with search, status filtering, and hospital isolation."""
        query = db.query(Patient).filter(Patient.hospital_id == hospital_id)

        if status_filter:
            query = query.filter(Patient.status == status_filter)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Patient.patient_identifier.ilike(term),
                    Patient.first_name.ilike(term),
                    Patient.last_name.ilike(term),
                    (Patient.first_name + " " + Patient.last_name).ilike(term),
                    Patient.phone.ilike(term),
                    Patient.email.ilike(term)
                )
            )

        total = query.count()
        patients = query.order_by(Patient.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

        p_ids = [p.id for p in patients]
        admissions_map = {}
        if p_ids:
            active_adms = db.query(Admission).options(
                joinedload(Admission.ward),
                joinedload(Admission.bed)
            ).filter(
                Admission.patient_id.in_(p_ids),
                Admission.status == AdmissionStatus.ADMITTED.value
            ).all()
            for adm in active_adms:
                admissions_map[adm.patient_id] = adm

        hospital = db.query(Hospital.name).filter(Hospital.id == hospital_id).first()
        hosp_name = hospital[0] if hospital else None

        items = []
        for p in patients:
            active_adm = admissions_map.get(p.id)
            current_adm_info = None
            if active_adm:
                current_adm_info = CurrentAdmissionInfo(
                    admission_id=active_adm.id,
                    admission_number=active_adm.admission_number,
                    admission_date=active_adm.admission_date,
                    ward_id=active_adm.ward_id,
                    ward_name=active_adm.ward.name if active_adm.ward else "",
                    bed_id=active_adm.bed_id,
                    bed_number=active_adm.bed.bed_number if active_adm.bed else "",
                    status=active_adm.status
                )
            items.append(
                PatientResponse(
                    id=p.id,
                    hospital_id=p.hospital_id,
                    patient_identifier=p.patient_identifier,
                    first_name=p.first_name,
                    last_name=p.last_name,
                    date_of_birth=p.date_of_birth,
                    gender=p.gender,
                    phone=p.phone,
                    email=p.email,
                    address=p.address,
                    emergency_contact_name=p.emergency_contact_name,
                    emergency_contact_phone=p.emergency_contact_phone,
                    status=p.status,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                    hospital_name=hosp_name,
                    current_admission=current_adm_info
                )
            )

        return PatientListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=ceil(total / limit) if limit else 1
        )

    @staticmethod
    def update_patient(
        db: Session,
        patient_id: int,
        patient_update: PatientUpdate,
        hospital_id: int,
        user_id: Optional[int] = None
    ) -> PatientResponse:
        """Update patient information."""
        patient = PatientService.get_patient(db, patient_id, hospital_id)

        update_data = patient_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(patient, field) and value is not None:
                setattr(patient, field, value.value if hasattr(value, "value") else value)

        db.commit()
        db.refresh(patient)

        AuditService.log_event(
            db=db,
            hospital_id=hospital_id,
            user_id=user_id,
            action="PATIENT_UPDATED",
            resource_type="PATIENT",
            resource_id=str(patient.id),
            metadata={"updated_fields": list(update_data.keys())}
        )

        return PatientService.get_patient_response(db, patient.id, hospital_id)

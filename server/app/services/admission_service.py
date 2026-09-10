import logging
from datetime import datetime
from math import ceil
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.patient import Patient, PatientStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus
from app.models.ward import Ward
from app.models.hospital import Hospital
from app.models.occupancy_event import OccupancyEvent, EventType, EventSource
from app.schemas.admission import AdmissionCreate, DischargeCreate, AdmissionResponse, AdmissionListResponse, MinimalPatientInfo
from app.schemas.bed import BedResponse
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class AdmissionService:

    @staticmethod
    def generate_admission_number(db: Session, hospital_id: int) -> str:
        """Generate a unique admission number (e.g. ADM-2026-000001)."""
        year = datetime.utcnow().year
        count = db.query(Admission).filter(Admission.hospital_id == hospital_id).count()
        seq = count + 1
        
        adm_number = f"ADM-{year}-{seq:06d}"
        
        while db.query(Admission).filter(Admission.admission_number == adm_number).first():
            seq += 1
            adm_number = f"ADM-{year}-{seq:06d}"
            
        return adm_number

    @staticmethod
    def admit_patient(
        db: Session,
        admission_in: AdmissionCreate,
        hospital_id: int,
        user_id: Optional[int] = None
    ) -> AdmissionResponse:
        """
        Admit a patient into a bed transactionally.
        Validates ownership, patient active status, no existing admission, bed availability, and updates bed status to OCCUPIED.
        """
        target_hospital_id = admission_in.hospital_id if admission_in.hospital_id else hospital_id

        # 1. Validate Patient
        patient = db.query(Patient).filter(
            Patient.id == admission_in.patient_id,
            Patient.hospital_id == target_hospital_id
        ).first()
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found in this hospital")
        
        if patient.status != PatientStatus.ACTIVE.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patient account is inactive")

        # 2. Prevent duplicate active admissions
        existing_active = db.query(Admission).filter(
            Admission.patient_id == patient.id,
            Admission.status == AdmissionStatus.ADMITTED.value
        ).first()
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient already has an active admission ({existing_active.admission_number})"
            )

        # 3. Validate Ward
        ward = db.query(Ward).filter(
            Ward.id == admission_in.ward_id,
            Ward.hospital_id == target_hospital_id
        ).first()
        if not ward:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found in this hospital")

        # 4. Validate & Row-Lock Bed
        bed = db.query(Bed).filter(
            Bed.id == admission_in.bed_id,
            Bed.hospital_id == target_hospital_id,
            Bed.ward_id == admission_in.ward_id
        ).with_for_update().first()

        if not bed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bed not found in specified ward and hospital"
            )

        if bed.status != BedStatus.AVAILABLE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Selected bed '{bed.bed_number}' is not available (current status: {bed.status})"
            )

        # 5. Create Admission record
        adm_number = AdmissionService.generate_admission_number(db, target_hospital_id)
        now = datetime.utcnow()

        admission = Admission(
            hospital_id=target_hospital_id,
            patient_id=patient.id,
            ward_id=ward.id,
            bed_id=bed.id,
            admission_number=adm_number,
            admission_date=now,
            status=AdmissionStatus.ADMITTED.value,
            admission_reason=admission_in.admission_reason,
            created_by=user_id
        )
        db.add(admission)

        # 6. Update Bed Status
        bed.status = BedStatus.OCCUPIED.value

        # 7. Record Occupancy Event
        event_id = f"EVT-ADM-{adm_number}-{int(now.timestamp())}"
        occ_event = OccupancyEvent(
            hospital_id=target_hospital_id,
            ward_id=ward.id,
            bed_id=bed.id,
            event_type=EventType.ADMISSION.value,
            event_time=now,
            source=EventSource.MANUAL.value,
            event_id=event_id,
            processed=True
        )
        db.add(occ_event)

        # 8. Record Audit Log
        AuditService.log_event(
            db=db,
            hospital_id=target_hospital_id,
            user_id=user_id,
            action="ADMISSION_CREATED",
            resource_type="ADMISSION",
            resource_id=adm_number,
            metadata={
                "patient_id": patient.id,
                "patient_identifier": patient.patient_identifier,
                "ward_id": ward.id,
                "bed_id": bed.id,
                "bed_number": bed.bed_number
            }
        )

        db.commit()
        db.refresh(admission)

        return AdmissionService.get_admission_response(db, admission.id, target_hospital_id)

    @staticmethod
    def discharge_patient(
        db: Session,
        admission_id: int,
        discharge_in: DischargeCreate,
        hospital_id: int,
        user_id: Optional[int] = None
    ) -> AdmissionResponse:
        """
        Discharge a patient transactionally.
        Validates admission status, updates discharge date, releases bed to AVAILABLE, and records event/audit.
        """
        # 1. Fetch & Row-Lock Admission
        admission = db.query(Admission).filter(
            Admission.id == admission_id,
            Admission.hospital_id == hospital_id
        ).with_for_update().first()

        if not admission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found in this hospital")

        if admission.status != AdmissionStatus.ADMITTED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Admission is already in status '{admission.status}'"
            )

        discharge_time = discharge_in.discharge_date or datetime.utcnow()
        if discharge_time < admission.admission_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discharge timestamp cannot be earlier than admission timestamp"
            )

        admission.discharge_date = discharge_time
        admission.status = AdmissionStatus.DISCHARGED.value
        admission.discharged_by = user_id
        admission.discharge_notes = discharge_in.discharge_notes

        # 2. Fetch & Row-Lock Bed
        bed = db.query(Bed).filter(
            Bed.id == admission.bed_id,
            Bed.hospital_id == hospital_id
        ).with_for_update().first()

        if bed:
            bed.status = BedStatus.AVAILABLE.value

        # 3. Record Occupancy Event
        event_id = f"EVT-DIS-{admission.admission_number}-{int(discharge_time.timestamp())}"
        occ_event = OccupancyEvent(
            hospital_id=hospital_id,
            ward_id=admission.ward_id,
            bed_id=admission.bed_id,
            event_type=EventType.DISCHARGE.value,
            event_time=discharge_time,
            source=EventSource.MANUAL.value,
            event_id=event_id,
            processed=True
        )
        db.add(occ_event)

        # 4. Audit Log
        AuditService.log_event(
            db=db,
            hospital_id=hospital_id,
            user_id=user_id,
            action="PATIENT_DISCHARGED",
            resource_type="ADMISSION",
            resource_id=admission.admission_number,
            metadata={
                "patient_id": admission.patient_id,
                "bed_id": admission.bed_id,
                "discharge_date": discharge_time.isoformat()
            }
        )

        db.commit()
        db.refresh(admission)

        return AdmissionService.get_admission_response(db, admission.id, hospital_id)

    @staticmethod
    def get_admission_response(db: Session, admission_id: int, hospital_id: int) -> AdmissionResponse:
        admission = db.query(Admission).filter(
            Admission.id == admission_id,
            Admission.hospital_id == hospital_id
        ).first()

        if not admission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission record not found")

        # Calculate stay duration in hours
        end_time = admission.discharge_date or datetime.utcnow()
        duration_hours = round((end_time - admission.admission_date).total_seconds() / 3600.0, 2)

        patient_info = None
        if admission.patient:
            p = admission.patient
            patient_info = MinimalPatientInfo(
                id=p.id,
                patient_identifier=p.patient_identifier,
                first_name=p.first_name,
                last_name=p.last_name,
                date_of_birth=str(p.date_of_birth) if p.date_of_birth else None,
                gender=p.gender
            )

        return AdmissionResponse(
            id=admission.id,
            hospital_id=admission.hospital_id,
            patient_id=admission.patient_id,
            ward_id=admission.ward_id,
            bed_id=admission.bed_id,
            admission_number=admission.admission_number,
            admission_date=admission.admission_date,
            discharge_date=admission.discharge_date,
            status=admission.status,
            admission_reason=admission.admission_reason,
            discharge_notes=admission.discharge_notes,
            created_by=admission.created_by,
            discharged_by=admission.discharged_by,
            created_at=admission.created_at,
            updated_at=admission.updated_at,
            hospital_name=admission.hospital.name if admission.hospital else None,
            ward_name=admission.ward.name if admission.ward else None,
            bed_number=admission.bed.bed_number if admission.bed else None,
            patient=patient_info,
            duration_hours=duration_hours
        )

    @staticmethod
    def get_admissions(
        db: Session,
        hospital_id: int,
        ward_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        limit: int = 50
    ) -> AdmissionListResponse:
        """List admissions with pagination and hospital isolation."""
        query = db.query(Admission).filter(Admission.hospital_id == hospital_id)

        if ward_id:
            query = query.filter(Admission.ward_id == ward_id)

        if patient_id:
            query = query.filter(Admission.patient_id == patient_id)

        if status_filter:
            query = query.filter(Admission.status == status_filter)

        total = query.count()
        admissions = query.order_by(Admission.admission_date.desc()).offset((page - 1) * limit).limit(limit).all()

        items = [AdmissionService.get_admission_response(db, a.id, hospital_id) for a in admissions]

        return AdmissionListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=ceil(total / limit) if limit else 1
        )

    @staticmethod
    def get_available_beds_for_ward(db: Session, ward_id: int, hospital_id: int) -> List[BedResponse]:
        """Fetch available beds belonging to the specified ward and hospital."""
        ward = db.query(Ward).filter(Ward.id == ward_id, Ward.hospital_id == hospital_id).first()
        if not ward:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found in this hospital")

        beds = db.query(Bed).filter(
            Bed.ward_id == ward_id,
            Bed.hospital_id == hospital_id,
            Bed.status == BedStatus.AVAILABLE.value
        ).order_by(Bed.bed_number).all()

        items = []
        for bed in beds:
            items.append(
                BedResponse(
                    id=bed.id,
                    hospital_id=bed.hospital_id,
                    ward_id=bed.ward_id,
                    bed_number=bed.bed_number,
                    status=bed.status,
                    bed_type=bed.bed_type,
                    created_at=bed.created_at,
                    updated_at=bed.updated_at,
                    ward_name=ward.name,
                    hospital_name=ward.hospital.name if ward.hospital else None
                )
            )
        return items

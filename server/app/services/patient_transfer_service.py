from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.transfer import Transfer, TransferStatus
from app.models.patient import Patient
from app.models.admission import Admission, AdmissionStatus
from app.models.ward import Ward
from app.models.bed import Bed, BedStatus
from app.models.occupancy_event import OccupancyEvent, EventType, EventSource
from app.models.user import User
from app.services.audit_service import AuditService


class PatientTransferService:

    @staticmethod
    def _enrich_transfer_response(transfer: Transfer) -> Transfer:
        """Helper to attach human-readable metadata to Transfer instance for response schemas."""
        if transfer.patient:
            transfer.patient_name = f"{transfer.patient.first_name} {transfer.patient.last_name}"
            transfer.patient_identifier = transfer.patient.patient_identifier
        if transfer.source_ward:
            transfer.source_ward_name = transfer.source_ward.name
        if transfer.destination_ward:
            transfer.destination_ward_name = transfer.destination_ward.name
        if transfer.source_bed:
            transfer.source_bed_number = transfer.source_bed.bed_number
        if transfer.destination_bed:
            transfer.destination_bed_number = transfer.destination_bed.bed_number
        if transfer.requester:
            transfer.requested_by_name = transfer.requester.full_name
        if transfer.approver:
            transfer.approved_by_name = transfer.approver.full_name
        if transfer.rejecter:
            transfer.rejected_by_name = transfer.rejecter.full_name
        if transfer.completer:
            transfer.completed_by_name = transfer.completer.full_name
        return transfer

    @classmethod
    def create_transfer_request(
        cls,
        db: Session,
        hospital_id: int,
        user_id: int,
        patient_id: int,
        destination_ward_id: int,
        destination_bed_id: int,
        reason: Optional[str] = None
    ) -> Transfer:
        """Create a new inter-ward transfer request for an admitted patient."""

        # 1. Verify Patient belongs to the hospital
        patient = db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.hospital_id == hospital_id
        ).first()
        if not patient:
            raise ValueError(f"Patient with ID {patient_id} not found in hospital {hospital_id}.")

        # 2. Verify Active Admission
        admission = db.query(Admission).filter(
            Admission.patient_id == patient_id,
            Admission.hospital_id == hospital_id,
            Admission.status == AdmissionStatus.ADMITTED.value
        ).first()
        if not admission:
            raise ValueError(f"Patient '{patient.first_name} {patient.last_name}' does not have an active admission.")

        source_ward_id = admission.ward_id
        source_bed_id = admission.bed_id

        # 3. Check for existing pending transfer requests
        existing_pending = db.query(Transfer).filter(
            Transfer.patient_id == patient_id,
            Transfer.hospital_id == hospital_id,
            Transfer.status.in_([TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value])
        ).first()
        if existing_pending:
            raise ValueError(f"An active transfer request already exists for this patient (Transfer ID #{existing_pending.id}).")

        # 4. Validate Source and Destination Wards
        if source_ward_id == destination_ward_id:
            raise ValueError("Source and Destination wards cannot be the same.")

        dest_ward = db.query(Ward).filter(
            Ward.id == destination_ward_id,
            Ward.hospital_id == hospital_id
        ).first()
        if not dest_ward:
            raise ValueError(f"Destination ward ID {destination_ward_id} not found in this hospital.")

        # 5. Validate Destination Bed
        dest_bed = db.query(Bed).filter(
            Bed.id == destination_bed_id,
            Bed.ward_id == destination_ward_id,
            Bed.hospital_id == hospital_id
        ).first()
        if not dest_bed:
            raise ValueError(f"Destination bed ID {destination_bed_id} does not exist in ward '{dest_ward.name}'.")

        if dest_bed.status != BedStatus.AVAILABLE.value:
            raise ValueError(f"Destination bed '{dest_bed.bed_number}' is currently {dest_bed.status}, not AVAILABLE.")

        # 6. Instantiate Transfer
        transfer = Transfer(
            hospital_id=hospital_id,
            patient_id=patient_id,
            admission_id=admission.id,
            source_ward_id=source_ward_id,
            destination_ward_id=destination_ward_id,
            source_bed_id=source_bed_id,
            destination_bed_id=destination_bed_id,
            reason=reason,
            status=TransferStatus.REQUESTED.value,
            requested_by=user_id,
            requested_at=datetime.utcnow()
        )

        db.add(transfer)
        db.commit()
        db.refresh(transfer)

        AuditService.log_event(
            db,
            hospital_id=hospital_id,
            user_id=user_id,
            action="PATIENT_TRANSFER_REQUESTED",
            resource_type="PATIENT_TRANSFER",
            resource_id=str(transfer.id),
            metadata={
                "patient_id": patient_id,
                "source_ward_id": source_ward_id,
                "destination_ward_id": destination_ward_id,
                "destination_bed_id": destination_bed_id,
            }
        )


        return cls._enrich_transfer_response(transfer)

    @classmethod
    def approve_transfer_request(
        cls,
        db: Session,
        transfer_id: int,
        hospital_id: int,
        user_id: int,
        notes: Optional[str] = None
    ) -> Transfer:
        """Approve a requested inter-ward transfer after re-validating destination bed availability."""
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id,
            Transfer.hospital_id == hospital_id
        ).first()
        if not transfer:
            raise ValueError(f"Transfer request ID #{transfer_id} not found.")

        if transfer.status != TransferStatus.REQUESTED.value:
            raise ValueError(f"Transfer request is in '{transfer.status}' status and cannot be approved.")

        # Re-validate destination bed availability
        dest_bed = db.query(Bed).filter(Bed.id == transfer.destination_bed_id).first()
        if not dest_bed or dest_bed.status != BedStatus.AVAILABLE.value:
            raise ValueError(f"Destination bed '{dest_bed.bed_number if dest_bed else transfer.destination_bed_id}' is no longer AVAILABLE.")

        transfer.status = TransferStatus.APPROVED.value
        transfer.approved_by = user_id
        transfer.approved_at = datetime.utcnow()
        if notes:
            transfer.reason = (transfer.reason or "") + f" [Approval Note: {notes}]"

        db.commit()
        db.refresh(transfer)

        AuditService.log_event(
            db,
            hospital_id=hospital_id,
            user_id=user_id,
            action="PATIENT_TRANSFER_APPROVED",
            resource_type="PATIENT_TRANSFER",
            resource_id=str(transfer.id),
        )

        return cls._enrich_transfer_response(transfer)

    @classmethod
    def reject_transfer_request(
        cls,
        db: Session,
        transfer_id: int,
        hospital_id: int,
        user_id: int,
        rejection_reason: str
    ) -> Transfer:
        """Reject a requested inter-ward transfer with a required reason."""
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id,
            Transfer.hospital_id == hospital_id
        ).first()
        if not transfer:
            raise ValueError(f"Transfer request ID #{transfer_id} not found.")

        if transfer.status not in [TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value]:
            raise ValueError(f"Transfer request in status '{transfer.status}' cannot be rejected.")

        transfer.status = TransferStatus.REJECTED.value
        transfer.rejected_by = user_id
        transfer.rejected_at = datetime.utcnow()
        transfer.rejection_reason = rejection_reason

        db.commit()
        db.refresh(transfer)

        AuditService.log_event(
            db,
            hospital_id=hospital_id,
            user_id=user_id,
            action="PATIENT_TRANSFER_REJECTED",
            resource_type="PATIENT_TRANSFER",
            resource_id=str(transfer.id),
            metadata={"rejection_reason": rejection_reason}
        )


        return cls._enrich_transfer_response(transfer)

    @classmethod
    def cancel_transfer_request(
        cls,
        db: Session,
        transfer_id: int,
        hospital_id: int,
        user_id: int
    ) -> Transfer:
        """Cancel a pending transfer request."""
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id,
            Transfer.hospital_id == hospital_id
        ).first()
        if not transfer:
            raise ValueError(f"Transfer request ID #{transfer_id} not found.")

        if transfer.status not in [TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value]:
            raise ValueError(f"Transfer request in status '{transfer.status}' cannot be cancelled.")

        transfer.status = TransferStatus.CANCELLED.value
        db.commit()
        db.refresh(transfer)

        AuditService.log_event(
            db,
            hospital_id=hospital_id,
            user_id=user_id,
            action="PATIENT_TRANSFER_CANCELLED",
            resource_type="PATIENT_TRANSFER",
            resource_id=str(transfer.id)
        )

        return cls._enrich_transfer_response(transfer)

    @classmethod
    def complete_transfer_request(
        cls,
        db: Session,
        transfer_id: int,
        hospital_id: int,
        user_id: int
    ) -> Transfer:
        """
        Execute full atomic database transaction to complete inter-ward patient transfer:
        1. Verify transfer status = APPROVED (or REQUESTED)
        2. Verify destination bed is still AVAILABLE
        3. Verify source bed is occupied by patient's active admission
        4. Free source bed (status -> AVAILABLE)
        5. Occupy destination bed (status -> OCCUPIED)
        6. Move admission (ward_id, bed_id -> destination)
        7. Log OccupancyEvent (TRANSFER)
        8. Update transfer status -> COMPLETED with completed_at
        """
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id,
            Transfer.hospital_id == hospital_id
        ).first()
        if not transfer:
            raise ValueError(f"Transfer request ID #{transfer_id} not found.")

        if transfer.status not in [TransferStatus.APPROVED.value, TransferStatus.REQUESTED.value]:
            raise ValueError(f"Transfer request must be APPROVED or REQUESTED to be completed. Current status: '{transfer.status}'.")

        # 1. Fetch Source Bed & Destination Bed
        source_bed = db.query(Bed).filter(Bed.id == transfer.source_bed_id).with_for_update().first()
        dest_bed = db.query(Bed).filter(Bed.id == transfer.destination_bed_id).with_for_update().first()

        if not dest_bed or dest_bed.status != BedStatus.AVAILABLE.value:
            raise ValueError(f"Destination bed '{dest_bed.bed_number if dest_bed else transfer.destination_bed_id}' is no longer AVAILABLE.")

        # 2. Fetch Active Admission
        admission = db.query(Admission).filter(
            Admission.id == transfer.admission_id,
            Admission.status == AdmissionStatus.ADMITTED.value
        ).first()
        if not admission:
            raise ValueError("Patient no longer has an active admission.")

        try:
            # ATOMIC TRANSACTION EXECUTION
            # 3. Release Source Bed
            if source_bed:
                source_bed.status = BedStatus.AVAILABLE.value

            # 4. Occupy Destination Bed
            dest_bed.status = BedStatus.OCCUPIED.value

            # 5. Relocate Admission
            admission.ward_id = transfer.destination_ward_id
            admission.bed_id = transfer.destination_bed_id

            # 6. Log Occupancy Events (TRANSFER_OUT for source, TRANSFER_IN for destination)
            now = datetime.utcnow()
            ts = int(now.timestamp())
            
            if source_bed:
                event_out = OccupancyEvent(
                    hospital_id=hospital_id,
                    ward_id=transfer.source_ward_id,
                    bed_id=transfer.source_bed_id,
                    event_type=EventType.TRANSFER_OUT.value,
                    event_time=now,
                    source=EventSource.MANUAL.value,
                    event_id=f"evt_xfer_out_{transfer.id}_{ts}",
                    processed=True,
                )
                db.add(event_out)

            event_in = OccupancyEvent(
                hospital_id=hospital_id,
                ward_id=transfer.destination_ward_id,
                bed_id=transfer.destination_bed_id,
                event_type=EventType.TRANSFER_IN.value,
                event_time=now,
                source=EventSource.MANUAL.value,
                event_id=f"evt_xfer_in_{transfer.id}_{ts}",
                processed=True,
            )
            db.add(event_in)


            # 7. Update Transfer record
            transfer.status = TransferStatus.COMPLETED.value
            transfer.completed_by = user_id
            transfer.completed_at = datetime.utcnow()

            db.commit()
            db.refresh(transfer)

            AuditService.log_event(
                db,
                hospital_id=hospital_id,
                user_id=user_id,
                action="PATIENT_TRANSFER_COMPLETED",
                resource_type="PATIENT_TRANSFER",
                resource_id=str(transfer.id),
                metadata={
                    "patient_id": transfer.patient_id,
                    "from_ward_id": transfer.source_ward_id,
                    "to_ward_id": transfer.destination_ward_id,
                    "from_bed_id": transfer.source_bed_id,
                    "to_bed_id": transfer.destination_bed_id,
                }
            )


            return cls._enrich_transfer_response(transfer)

        except Exception as e:
            db.rollback()
            raise ValueError(f"Failed to complete transfer due to database transaction failure: {str(e)}")

    @classmethod
    def get_transfers(
        cls,
        db: Session,
        hospital_id: int,
        status_filter: Optional[str] = None,
        patient_id: Optional[int] = None,
        source_ward_id: Optional[int] = None,
        destination_ward_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Transfer], int]:
        """List transfers with optional filtering and pagination."""
        query = db.query(Transfer).filter(Transfer.hospital_id == hospital_id)

        if status_filter and status_filter.upper() != 'ALL':
            query = query.filter(Transfer.status == status_filter.upper())
        if patient_id:
            query = query.filter(Transfer.patient_id == patient_id)
        if source_ward_id:
            query = query.filter(Transfer.source_ward_id == source_ward_id)
        if destination_ward_id:
            query = query.filter(Transfer.destination_ward_id == destination_ward_id)

        total = query.count()
        transfers = query.order_by(Transfer.requested_at.desc()).offset(offset).limit(limit).all()

        for t in transfers:
            cls._enrich_transfer_response(t)

        return transfers, total

    @classmethod
    def get_transfer_by_id(cls, db: Session, transfer_id: int, hospital_id: int) -> Optional[Transfer]:
        """Fetch a single transfer by ID with hospital security enforcement."""
        transfer = db.query(Transfer).filter(
            Transfer.id == transfer_id,
            Transfer.hospital_id == hospital_id
        ).first()
        if transfer:
            cls._enrich_transfer_response(transfer)
        return transfer

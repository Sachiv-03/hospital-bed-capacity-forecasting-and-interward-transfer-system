"""
Event Processor — the heart of Phase 6 Stage 1.

Responsibilities:
  1. Validate hospital → ward → bed ownership (cross-tenant safety)
  2. Detect duplicate event_id (idempotency)
  3. Apply bed status transition rules
  4. Save OccupancyEvent record
  5. Run all above inside a single DB transaction

This service is intentionally source-agnostic: it does not care whether
the event came from the SIMULATOR, MANUAL, or a future real-hospital API.
"""
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bed import Bed, BedStatus
from app.models.hospital import Hospital
from app.models.occupancy_event import OccupancyEvent
from app.models.ward import Ward
from app.schemas.occupancy_event import OccupancyEventIngest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed bed status transitions per event type
# ---------------------------------------------------------------------------
TRANSITIONS: Dict[str, Dict[str, str]] = {
    "ADMISSION":       {"AVAILABLE": "OCCUPIED"},
    "DISCHARGE":       {"OCCUPIED": "AVAILABLE"},
    "TRANSFER_OUT":    {"OCCUPIED": "AVAILABLE"},
    "TRANSFER_IN":     {"AVAILABLE": "OCCUPIED"},
    "BED_CLEANING":    {"AVAILABLE": "CLEANING", "OCCUPIED": "CLEANING"},
    "BED_AVAILABLE":   {"CLEANING": "AVAILABLE", "RESERVED": "AVAILABLE", "MAINTENANCE": "AVAILABLE"},
    "BED_MAINTENANCE": {
        "AVAILABLE": "MAINTENANCE", "OCCUPIED": "MAINTENANCE",
        "CLEANING": "MAINTENANCE", "RESERVED": "MAINTENANCE",
    },
    "BED_RESERVED":    {"AVAILABLE": "RESERVED"},
    "BED_RELEASED":    {"RESERVED": "AVAILABLE"},
}

# Human-readable rejection messages
REJECTION_MESSAGES: Dict[str, str] = {
    "ADMISSION":    "Cannot admit into a bed that is not AVAILABLE (current status: {status})",
    "DISCHARGE":    "Cannot discharge from a bed that is not OCCUPIED (current status: {status})",
    "TRANSFER_OUT": "Cannot transfer out from a bed that is not OCCUPIED (current status: {status})",
    "TRANSFER_IN":  "Cannot transfer into a bed that is not AVAILABLE (current status: {status})",
    "BED_CLEANING": "Cannot start cleaning a bed with status {status}",
    "BED_AVAILABLE":"Cannot mark bed as AVAILABLE from status {status}",
    "BED_MAINTENANCE": "Cannot set bed to MAINTENANCE from status {status}",
    "BED_RESERVED": "Cannot reserve a bed with status {status}",
    "BED_RELEASED": "Cannot release a bed that is not RESERVED (current status: {status})",
}


class EventProcessor:

    @staticmethod
    def process_event(db: Session, event: OccupancyEventIngest) -> Dict[str, Any]:
        """
        Main entry point. Validates, processes, and persists a single event.
        Returns a result dict with status: 'success' | 'duplicate' | 'rejected'.
        All DB operations run inside one transaction; on any failure the session
        is rolled back by the get_db() FastAPI dependency.
        """
        logger.info(
            f"EVENT RECEIVED | event_id={event.event_id} type={event.event_type} "
            f"hospital_id={event.hospital_id} ward_id={event.ward_id} bed_id={event.bed_id}"
        )

        # ── 1. Duplicate check ───────────────────────────────────────────────
        existing = db.query(OccupancyEvent).filter(
            OccupancyEvent.event_id == event.event_id
        ).first()
        if existing:
            logger.warning(f"EVENT DUPLICATE DETECTED | event_id={event.event_id}")
            return {
                "status": "duplicate",
                "message": "Event has already been processed",
                "event_id": event.event_id,
            }

        # ── 2. Validate hospital ─────────────────────────────────────────────
        hospital = db.query(Hospital).filter(Hospital.id == event.hospital_id).first()
        if not hospital:
            logger.warning(f"EVENT REJECTED | event_id={event.event_id} reason=hospital_not_found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

        # ── 3. Validate ward ─────────────────────────────────────────────────
        ward = db.query(Ward).filter(Ward.id == event.ward_id).first()
        if not ward:
            logger.warning(f"EVENT REJECTED | event_id={event.event_id} reason=ward_not_found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
        if ward.hospital_id != event.hospital_id:
            logger.warning(
                f"EVENT REJECTED | event_id={event.event_id} "
                f"reason=cross_hospital_ward ward.hospital_id={ward.hospital_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ward does not belong to the specified hospital",
            )

        # ── 4. Validate bed ──────────────────────────────────────────────────
        bed = db.query(Bed).filter(Bed.id == event.bed_id).first()
        if not bed:
            logger.warning(f"EVENT REJECTED | event_id={event.event_id} reason=bed_not_found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")
        if bed.ward_id != event.ward_id:
            logger.warning(f"EVENT REJECTED | event_id={event.event_id} reason=cross_ward_bed")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bed does not belong to the specified ward",
            )
        if bed.hospital_id != event.hospital_id:
            logger.warning(f"EVENT REJECTED | event_id={event.event_id} reason=cross_hospital_bed")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bed does not belong to the specified hospital",
            )

        logger.info(f"EVENT VALIDATED | event_id={event.event_id}")

        # ── 5. Determine new bed status ──────────────────────────────────────
        event_type_str = event.event_type.value
        allowed_transitions = TRANSITIONS.get(event_type_str, {})
        current_status = bed.status

        if current_status not in allowed_transitions:
            msg_template = REJECTION_MESSAGES.get(event_type_str, "Invalid status transition")
            msg = msg_template.format(status=current_status)
            logger.warning(
                f"EVENT REJECTED | event_id={event.event_id} "
                f"type={event_type_str} current_status={current_status} reason=invalid_transition"
            )
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

        new_status = allowed_transitions[current_status]

        # ── 6. Update bed status ─────────────────────────────────────────────
        old_status = bed.status
        bed.status = new_status
        bed.updated_at = datetime.utcnow()

        # ── 7. Save event record ─────────────────────────────────────────────
        occupancy_event = OccupancyEvent(
            hospital_id=event.hospital_id,
            ward_id=event.ward_id,
            bed_id=event.bed_id,
            event_type=event_type_str,
            event_time=event.event_time,
            source=event.source.value,
            event_id=event.event_id,
            processed=True,
        )
        db.add(occupancy_event)

        # ── 8. Commit transaction ─────────────────────────────────────────────
        db.commit()
        db.refresh(bed)
        db.refresh(occupancy_event)

        logger.info(
            f"EVENT PROCESSED | event_id={event.event_id} type={event_type_str} "
            f"bed_id={bed.id} bed_number={bed.bed_number} "
            f"status_change={old_status} → {new_status}"
        )
        logger.info(f"BED UPDATED | bed_id={bed.id} new_status={new_status}")
        logger.info(f"EVENT SAVED  | occupancy_event_id={occupancy_event.id}")

        return {
            "status": "success",
            "event_id": event.event_id,
            "bed_id": bed.id,
            "bed_number": bed.bed_number,
            "event_type": event_type_str,
            "previous_status": old_status,
            "new_status": new_status,
            "ward_id": ward.id,
            "ward_name": ward.name,
            "hospital_id": hospital.id,
        }

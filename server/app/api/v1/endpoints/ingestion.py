"""
Ingestion API — receives hospital events from the simulator or any authorized source.
Also exposes event history (GET) and a dev-only simulate endpoint (POST /simulate).
"""
import logging
import random
import string
from datetime import datetime
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.services.synthea_import_service import SyntheaImportService

from app.api.deps import get_current_active_user, require_roles
from app.core.config import settings
from app.database.session import get_db
from app.models.bed import Bed, BedStatus
from app.models.occupancy_event import OccupancyEvent
from app.models.user import User, UserRole
from app.models.ward import Ward, WardStatus
from app.schemas.occupancy_event import (
    OccupancyEventIngest,
    OccupancyEventListResponse,
    OccupancyEventResponse,
    SimulateEventRequest,
)
from app.services.event_processor import TRANSITIONS, EventProcessor

logger = logging.getLogger(__name__)
router = APIRouter()

ADMIN_ROLES = [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]


def _resolve_hospital_id(current_user: User, requested_hospital_id: Optional[int] = None) -> Optional[int]:
    """None means SUPER_ADMIN with no filter (see all). Otherwise scoped to hospital."""
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return requested_hospital_id  # can be None (all hospitals) or a specific id
    return current_user.hospital_id


# ── POST /events ─────────────────────────────────────────────────────────────

@router.post(
    "/events",
    summary="Ingest a hospital event",
    description=(
        "Receive a hospital occupancy event (ADMISSION, DISCHARGE, BED_CLEANING, etc.), "
        "validate it, check for duplicates, update the bed status, and save the event log."
    ),
)
def ingest_event(
    event: OccupancyEventIngest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Any authenticated user can post events.
    Hospital-level isolation is enforced inside EventProcessor:
    non-SUPER_ADMIN users can only post events for their own hospital.
    """
    # Enforce non-super-admin hospital isolation at the routing layer too
    if current_user.role != UserRole.SUPER_ADMIN.value:
        if current_user.hospital_id != event.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only submit events for your own hospital",
            )

    result = EventProcessor.process_event(db, event)
    return result


# ── GET /events ──────────────────────────────────────────────────────────────

@router.get(
    "/events",
    response_model=OccupancyEventListResponse,
    summary="List occupancy events (paginated)",
)
def list_events(
    hospital_id: Optional[int] = Query(None, description="Filter by hospital (SUPER_ADMIN only)"),
    ward_id: Optional[int] = Query(None, description="Filter by ward"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    effective_hospital_id = _resolve_hospital_id(current_user, hospital_id)

    query = db.query(OccupancyEvent)

    if effective_hospital_id is not None:
        query = query.filter(OccupancyEvent.hospital_id == effective_hospital_id)
    if ward_id:
        query = query.filter(OccupancyEvent.ward_id == ward_id)
    if event_type:
        query = query.filter(OccupancyEvent.event_type == event_type.upper())
    if start_date:
        query = query.filter(OccupancyEvent.event_time >= start_date)
    if end_date:
        query = query.filter(OccupancyEvent.event_time <= end_date)

    total = query.count()
    events = (
        query.order_by(OccupancyEvent.event_time.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = []
    for ev in events:
        items.append(
            OccupancyEventResponse(
                id=ev.id,
                event_id=ev.event_id,
                hospital_id=ev.hospital_id,
                ward_id=ev.ward_id,
                bed_id=ev.bed_id,
                event_type=ev.event_type,
                event_time=ev.event_time,
                source=ev.source,
                processed=ev.processed,
                created_at=ev.created_at,
                ward_name=ev.ward.name if ev.ward else None,
                bed_number=ev.bed.bed_number if ev.bed else None,
            )
        )

    return OccupancyEventListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=ceil(total / limit) if limit else 1,
    )


# ── POST /simulate (DEV ONLY) ─────────────────────────────────────────────────

@router.post(
    "/simulate",
    summary="[DEV ONLY] Manually trigger a simulated event",
    description=(
        "Development-only endpoint. Selects an appropriate bed for the given event type "
        "and submits it to the ingestion pipeline. Requires SIMULATOR_ENABLED=true."
    ),
)
def simulate_event(
    request: SimulateEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    if not getattr(settings, "SIMULATOR_ENABLED", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulator is disabled. Set SIMULATOR_ENABLED=true in .env to enable.",
        )

    # Determine which statuses are valid source statuses for this event type
    allowed_source_statuses = list(TRANSITIONS.get(request.event_type.value, {}).keys())
    if not allowed_source_statuses:
        raise HTTPException(status_code=400, detail=f"Unknown event type: {request.event_type}")

    # Build query for eligible beds
    bed_query = (
        db.query(Bed)
        .filter(
            Bed.hospital_id == request.hospital_id,
            Bed.status.in_(allowed_source_statuses),
        )
    )
    if request.ward_id:
        bed_query = bed_query.filter(Bed.ward_id == request.ward_id)
    else:
        # Only pick beds from ACTIVE wards
        active_ward_ids = [
            w.id for w in db.query(Ward).filter(
                Ward.hospital_id == request.hospital_id,
                Ward.status == WardStatus.ACTIVE.value,
            ).all()
        ]
        bed_query = bed_query.filter(Bed.ward_id.in_(active_ward_ids))

    eligible_beds = bed_query.all()
    if not eligible_beds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No eligible beds found for event type '{request.event_type}' in hospital {request.hospital_id}",
        )

    bed = random.choice(eligible_beds)

    # Generate unique event_id
    suffix = "".join(random.choices(string.digits, k=6))
    date_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    event_id = f"MANUAL-{date_str}-{suffix}"

    event_payload = OccupancyEventIngest(
        event_id=event_id,
        hospital_id=request.hospital_id,
        ward_id=bed.ward_id,
        bed_id=bed.id,
        event_type=request.event_type,
        event_time=datetime.utcnow(),
        source="MANUAL",
    )

    result = EventProcessor.process_event(db, event_payload)
    return result


# ── POST /import/synthea ────────────────────────────────────────────────────

@router.post(
    "/import/synthea",
    summary="Ingest Synthea dataset into hospital capacity snapshots",
    description=(
        "Processes real-world Synthea EHR dataset (encounters & organizations) "
        "and generates continuous daily bed occupancy snapshots for forecasting."
    ),
)
def import_synthea(
    hospital_id: Optional[int] = Query(None, description="Target hospital ID (SUPER_ADMIN only, or leave empty to auto-configure)"),
    start_year: int = Query(2018, ge=1990, le=2025),
    end_year: int = Query(2020, ge=1990, le=2025),
    create_events: bool = Query(True, description="Whether to also log admission/discharge OccupancyEvents"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    target_id = _resolve_hospital_id(current_user, hospital_id)
    try:
        result = SyntheaImportService.import_encounters(
            db=db,
            target_hospital_id=target_id,
            start_year=start_year,
            end_year=end_year,
            create_occupancy_events=create_events,
        )
        return result
    except Exception as e:
        logger.error(f"Synthea import failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── POST /import/csv ────────────────────────────────────────────────────────

@router.post(
    "/import/csv",
    summary="Upload custom CSV time-series for bed occupancy snapshots",
    description="Upload a CSV with columns (date/snapshot_time, occupied_beds, total_beds) to feed forecasting.",
)
async def import_csv_snapshots(
    file: UploadFile = File(...),
    hospital_id: int = Form(...),
    ward_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    if current_user.role != UserRole.SUPER_ADMIN.value and current_user.hospital_id != hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only import snapshots for your assigned hospital",
        )

    try:
        content_bytes = await file.read()
        file_text = content_bytes.decode("utf-8")
        result = SyntheaImportService.import_custom_csv_snapshots(
            db=db,
            file_content=file_text,
            hospital_id=hospital_id,
            ward_id=ward_id,
        )
        return result
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file must be UTF-8 encoded")
    except Exception as e:
        logger.error(f"CSV import error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


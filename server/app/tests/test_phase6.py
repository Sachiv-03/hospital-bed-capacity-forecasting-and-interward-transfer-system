"""
Phase 6 Stage 1 — Test Suite
Tests: Bed model, event processing, idempotency, capacity, multi-hospital isolation,
transaction safety, and the ingestion API.
"""
import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.main import app
from app.api.deps import get_db
from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType
from app.models.occupancy_event import OccupancyEvent
from app.services.event_processor import EventProcessor
from app.services.capacity_service import CapacityService
from app.schemas.occupancy_event import OccupancyEventIngest, EventTypeEnum, EventSourceEnum

# ── In-memory SQLite for isolated tests ──────────────────────────────────────
SQLITE_URL = "sqlite:///./test_phase6.db"
engine_test = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_hospital(db, code_suffix="A") -> Hospital:
    h = Hospital(name=f"Test Hospital {code_suffix}", code=f"TEST{code_suffix}", status=HospitalStatus.ACTIVE.value)
    db.add(h)
    db.flush()
    return h


def make_ward(db, hospital: Hospital, ward_name="ICU") -> Ward:
    w = Ward(
        hospital_id=hospital.id,
        name=ward_name,
        ward_type=WardType.ICU.value,
        department="Critical Care",
        floor="Floor 2",
        capacity=20,
        status=WardStatus.ACTIVE.value,
    )
    db.add(w)
    db.flush()
    return w


def make_bed(db, hospital: Hospital, ward: Ward, number="ICU-01", status=BedStatus.AVAILABLE.value) -> Bed:
    bed = Bed(
        hospital_id=hospital.id,
        ward_id=ward.id,
        bed_number=number,
        bed_type=BedType.ICU.value,
        status=status,
    )
    db.add(bed)
    db.flush()
    return bed


def make_event_payload(hospital_id: int, ward_id: int, bed_id: int, event_type: str, event_id: str = None):
    return OccupancyEventIngest(
        event_id=event_id or f"TEST-{uuid.uuid4().hex[:12]}",
        hospital_id=hospital_id,
        ward_id=ward_id,
        bed_id=bed_id,
        event_type=EventTypeEnum(event_type),
        event_time=datetime.utcnow(),
        source=EventSourceEnum.SIMULATOR,
    )


# ── 1. MODEL TESTS ────────────────────────────────────────────────────────────

def test_bed_belongs_to_ward_and_hospital(db):
    h = make_hospital(db, "MODEL1")
    w = make_ward(db, h)
    bed = make_bed(db, h, w)
    db.commit()

    assert bed.hospital_id == h.id
    assert bed.ward_id == w.id
    assert bed.status == BedStatus.AVAILABLE.value


def test_bed_hospital_matches_ward_hospital(db):
    h = make_hospital(db, "MODEL2")
    w = make_ward(db, h)
    bed = make_bed(db, h, w)
    db.commit()

    assert bed.hospital_id == w.hospital_id, "Bed hospital must match ward hospital"


# ── 2. ADMISSION TESTS ────────────────────────────────────────────────────────

def test_admission_available_bed_becomes_occupied(db):
    h = make_hospital(db, "ADM1")
    w = make_ward(db, h)
    bed = make_bed(db, h, w, "ADM-01", BedStatus.AVAILABLE.value)
    db.commit()

    payload = make_event_payload(h.id, w.id, bed.id, "ADMISSION")
    result = EventProcessor.process_event(db, payload)

    assert result["status"] == "success"
    db.refresh(bed)
    assert bed.status == BedStatus.OCCUPIED.value


def test_admission_occupied_bed_rejected(db):
    from fastapi import HTTPException
    h = make_hospital(db, "ADM2")
    w = make_ward(db, h)
    bed = make_bed(db, h, w, "ADM-02", BedStatus.OCCUPIED.value)
    db.commit()

    payload = make_event_payload(h.id, w.id, bed.id, "ADMISSION")
    with pytest.raises(HTTPException) as exc_info:
        EventProcessor.process_event(db, payload)
    assert exc_info.value.status_code == 422


# ── 3. DISCHARGE TESTS ────────────────────────────────────────────────────────

def test_discharge_occupied_bed_becomes_available(db):
    h = make_hospital(db, "DIS1")
    w = make_ward(db, h)
    bed = make_bed(db, h, w, "DIS-01", BedStatus.OCCUPIED.value)
    db.commit()

    payload = make_event_payload(h.id, w.id, bed.id, "DISCHARGE")
    result = EventProcessor.process_event(db, payload)

    assert result["status"] == "success"
    db.refresh(bed)
    assert bed.status == BedStatus.AVAILABLE.value


def test_discharge_available_bed_rejected(db):
    from fastapi import HTTPException
    h = make_hospital(db, "DIS2")
    w = make_ward(db, h)
    bed = make_bed(db, h, w, "DIS-02", BedStatus.AVAILABLE.value)
    db.commit()

    payload = make_event_payload(h.id, w.id, bed.id, "DISCHARGE")
    with pytest.raises(HTTPException) as exc_info:
        EventProcessor.process_event(db, payload)
    assert exc_info.value.status_code == 422


# ── 4. MAINTENANCE TESTS ──────────────────────────────────────────────────────

def test_bed_maintenance_transition(db):
    h = make_hospital(db, "MAINT1")
    w = make_ward(db, h)
    bed = make_bed(db, h, w, "MAINT-01", BedStatus.AVAILABLE.value)
    db.commit()

    payload = make_event_payload(h.id, w.id, bed.id, "BED_MAINTENANCE")
    result = EventProcessor.process_event(db, payload)
    assert result["status"] == "success"
    db.refresh(bed)
    assert bed.status == BedStatus.MAINTENANCE.value


def test_maintenance_bed_not_counted_as_available(db):
    h = make_hospital(db, "MAINT2")
    w = make_ward(db, h)
    # 2 AVAILABLE, 1 MAINTENANCE
    make_bed(db, h, w, "MAINT-A1", BedStatus.AVAILABLE.value)
    make_bed(db, h, w, "MAINT-A2", BedStatus.AVAILABLE.value)
    make_bed(db, h, w, "MAINT-M1", BedStatus.MAINTENANCE.value)
    db.commit()

    cap = CapacityService.get_ward_capacity(db, w.id, h.id)
    assert cap.available_beds == 2
    assert cap.maintenance_beds == 1
    assert cap.total_beds == 3


# ── 5. DUPLICATE EVENT IDEMPOTENCY ───────────────────────────────────────────

def test_duplicate_event_is_rejected(db):
    h = make_hospital(db, "DUP1")
    w = make_ward(db, h)
    bed = make_bed(db, h, w, "DUP-01", BedStatus.AVAILABLE.value)
    db.commit()

    event_id = f"DUP-{uuid.uuid4().hex[:10]}"

    # First: should succeed
    payload1 = make_event_payload(h.id, w.id, bed.id, "ADMISSION", event_id)
    result1 = EventProcessor.process_event(db, payload1)
    assert result1["status"] == "success"

    # Second: same event_id → duplicate
    payload2 = make_event_payload(h.id, w.id, bed.id, "DISCHARGE", event_id)
    result2 = EventProcessor.process_event(db, payload2)
    assert result2["status"] == "duplicate"

    # Bed was only changed once (still OCCUPIED, not discharged)
    db.refresh(bed)
    assert bed.status == BedStatus.OCCUPIED.value


# ── 6. MULTI-HOSPITAL ISOLATION ───────────────────────────────────────────────

def test_cross_hospital_event_rejected(db):
    from fastapi import HTTPException
    h1 = make_hospital(db, "ISO1")
    h2 = make_hospital(db, "ISO2")
    w1 = make_ward(db, h1, "ICU-H1")
    w2 = make_ward(db, h2, "ICU-H2")
    bed2 = make_bed(db, h2, w2, "ISO-B1", BedStatus.AVAILABLE.value)
    db.commit()

    # hospital_id says h1 but ward belongs to h2 → should reject
    payload = make_event_payload(h1.id, w2.id, bed2.id, "ADMISSION")
    with pytest.raises(HTTPException) as exc_info:
        EventProcessor.process_event(db, payload)
    assert exc_info.value.status_code == 403


def test_cross_ward_bed_rejected(db):
    from fastapi import HTTPException
    h = make_hospital(db, "ISO3")
    w1 = make_ward(db, h, "Ward-A")
    w2 = make_ward(db, h, "Ward-B")
    bed_in_w2 = make_bed(db, h, w2, "ISO-X1", BedStatus.AVAILABLE.value)
    db.commit()

    # ward_id says w1 but bed belongs to w2 → should reject
    payload = make_event_payload(h.id, w1.id, bed_in_w2.id, "ADMISSION")
    with pytest.raises(HTTPException) as exc_info:
        EventProcessor.process_event(db, payload)
    assert exc_info.value.status_code == 403


# ── 7. CAPACITY CALCULATION ───────────────────────────────────────────────────

def test_ward_capacity_calculation(db):
    h = make_hospital(db, "CAP1")
    w = make_ward(db, h)
    make_bed(db, h, w, "CAP-01", BedStatus.OCCUPIED.value)
    make_bed(db, h, w, "CAP-02", BedStatus.OCCUPIED.value)
    make_bed(db, h, w, "CAP-03", BedStatus.AVAILABLE.value)
    make_bed(db, h, w, "CAP-04", BedStatus.CLEANING.value)
    db.commit()

    cap = CapacityService.get_ward_capacity(db, w.id, h.id)
    assert cap.total_beds == 4
    assert cap.occupied_beds == 2
    assert cap.available_beds == 1
    assert cap.cleaning_beds == 1
    assert cap.occupancy_percentage == 50.0


def test_hospital_capacity_aggregation(db):
    h = make_hospital(db, "CAP2")
    w1 = make_ward(db, h, "Ward-X")
    w2 = make_ward(db, h, "Ward-Y")
    make_bed(db, h, w1, "WX-01", BedStatus.OCCUPIED.value)
    make_bed(db, h, w1, "WX-02", BedStatus.AVAILABLE.value)
    make_bed(db, h, w2, "WY-01", BedStatus.OCCUPIED.value)
    make_bed(db, h, w2, "WY-02", BedStatus.OCCUPIED.value)
    db.commit()

    cap = CapacityService.get_hospital_capacity(db, h.id)
    assert cap.total_beds == 4
    assert cap.occupied_beds == 3
    assert cap.occupancy_percentage == 75.0


# ── 8. BED CLEANING & STATUS TRANSITIONS ─────────────────────────────────────

def test_bed_cleaning_then_available(db):
    h = make_hospital(db, "CLN1")
    w = make_ward(db, h)
    bed = make_bed(db, h, w, "CLN-01", BedStatus.AVAILABLE.value)
    db.commit()

    EventProcessor.process_event(db, make_event_payload(h.id, w.id, bed.id, "BED_CLEANING"))
    db.refresh(bed)
    assert bed.status == BedStatus.CLEANING.value

    EventProcessor.process_event(db, make_event_payload(h.id, w.id, bed.id, "BED_AVAILABLE"))
    db.refresh(bed)
    assert bed.status == BedStatus.AVAILABLE.value


def test_reserved_then_released(db):
    h = make_hospital(db, "RES1")
    w = make_ward(db, h)
    bed = make_bed(db, h, w, "RES-01", BedStatus.AVAILABLE.value)
    db.commit()

    EventProcessor.process_event(db, make_event_payload(h.id, w.id, bed.id, "BED_RESERVED"))
    db.refresh(bed)
    assert bed.status == BedStatus.RESERVED.value

    EventProcessor.process_event(db, make_event_payload(h.id, w.id, bed.id, "BED_RELEASED"))
    db.refresh(bed)
    assert bed.status == BedStatus.AVAILABLE.value

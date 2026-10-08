"""
Phase 8 — Comprehensive Test Suite
Validates historical daily data, deduplication, conflict detection,
missing date detection, dynamic capacity, SARIMA compatibility, and regression safety.
"""
import pytest
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.session import Base, get_db
from app.main import app
from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType
from app.models.user import User, UserRole
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.occupancy_event import OccupancyEvent
from app.core.security import get_password_hash, create_access_token
from app.services.forecasting.historical_validation_service import (
    HistoricalDataValidationService,
    ValidationStatus,
)
from app.services.forecasting.data_preparation import ForecastingDataPreparation
from app.services.forecasting.forecast_service import ForecastService
from app.services.forecasting.time_series_model import TimeSeriesForecaster
from app.services.historical_service import HistoricalService


@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(name="client")
def client_fixture(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def create_test_hospital(db: Session, code: str = "H1", name: str = "Metro Hospital") -> Hospital:
    h = Hospital(name=name, code=code, status=HospitalStatus.ACTIVE.value)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


def create_test_ward(db: Session, hospital_id: int, name: str = "ICU", capacity: int = 20) -> Ward:
    w = Ward(
        hospital_id=hospital_id,
        name=name,
        ward_type=WardType.ICU.value,
        department="Critical Care",
        floor="Floor 1",
        capacity=capacity,
        status=WardStatus.ACTIVE.value,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def create_auth_headers(db: Session, hospital_id: int, role: str = UserRole.ADMIN.value) -> dict:
    user = User(
        email=f"user_{role.lower()}_{hospital_id}@hospital.com",
        password_hash=get_password_hash("Secret123!"),
        full_name="Test Staff",
        role=role,
        hospital_id=hospital_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


# ── TEST 1: Valid daily occupancy data ──────────────────────────────────────────
def test_1_valid_daily_occupancy(db_session: Session):
    h = create_test_hospital(db_session, "H1")
    w = create_test_ward(db_session, h.id, "General", capacity=25)

    rec = {
        "hospital_id": h.id,
        "ward_id": w.id,
        "date": "2026-05-01",
        "occupied_beds": 18,
        "capacity": 25,
    }
    res = HistoricalDataValidationService.validate_daily_record(db_session, rec)
    assert res["is_valid"] is True
    assert res["status"] == ValidationStatus.VALID.value
    assert res["occupied_beds"] == 18.0
    assert res["capacity"] == 25.0
    assert res["available_beds"] == 7.0
    assert res["occupancy_rate"] == 72.0
    assert res["is_over_capacity"] is False


# ── TEST 2: Invalid date ───────────────────────────────────────────────────────
def test_2_invalid_date(db_session: Session):
    h = create_test_hospital(db_session, "H2")
    w = create_test_ward(db_session, h.id, "General", capacity=20)

    rec = {
        "hospital_id": h.id,
        "ward_id": w.id,
        "date": "invalid-date-format",
        "occupied_beds": 10,
        "capacity": 20,
    }
    res = HistoricalDataValidationService.validate_daily_record(db_session, rec)
    assert res["is_valid"] is False
    assert "error" in res


# ── TEST 3: Negative occupancy ────────────────────────────────────────────────
def test_3_negative_occupancy(db_session: Session):
    h = create_test_hospital(db_session, "H3")
    w = create_test_ward(db_session, h.id, "General", capacity=20)

    rec = {
        "hospital_id": h.id,
        "ward_id": w.id,
        "date": "2026-05-01",
        "occupied_beds": -5,
        "capacity": 20,
    }
    res = HistoricalDataValidationService.validate_daily_record(db_session, rec)
    assert res["is_valid"] is False
    assert res["status"] == ValidationStatus.INVALID_OCCUPANCY.value


# ── TEST 4: Invalid capacity ──────────────────────────────────────────────────
def test_4_invalid_capacity(db_session: Session):
    h = create_test_hospital(db_session, "H4")
    w = create_test_ward(db_session, h.id, "General", capacity=20)

    rec = {
        "hospital_id": h.id,
        "ward_id": w.id,
        "date": "2026-05-01",
        "occupied_beds": 5,
        "capacity": 0,
    }
    res = HistoricalDataValidationService.validate_daily_record(db_session, rec)
    assert res["is_valid"] is False
    assert res["status"] == ValidationStatus.INVALID_CAPACITY.value


# ── TEST 5: Occupancy greater than capacity ───────────────────────────────────
def test_5_occupancy_greater_than_capacity(db_session: Session):
    h = create_test_hospital(db_session, "H5")
    w = create_test_ward(db_session, h.id, "ICU", capacity=10)

    rec = {
        "hospital_id": h.id,
        "ward_id": w.id,
        "date": "2026-05-01",
        "occupied_beds": 14,
        "capacity": 10,
    }
    res = HistoricalDataValidationService.validate_daily_record(db_session, rec)
    assert res["is_valid"] is True
    assert res["status"] == ValidationStatus.CAPACITY_VIOLATION.value
    assert res["is_over_capacity"] is True
    assert res["available_beds"] == 0.0
    assert res["occupancy_rate"] == 140.0


# ── TEST 6: Unknown hospital ───────────────────────────────────────────────────
def test_6_unknown_hospital(db_session: Session):
    rec = {
        "hospital_id": 9999,
        "ward_id": 1,
        "date": "2026-05-01",
        "occupied_beds": 10,
        "capacity": 20,
    }
    res = HistoricalDataValidationService.validate_daily_record(db_session, rec)
    assert res["is_valid"] is False
    assert res["status"] == ValidationStatus.UNKNOWN_HOSPITAL.value


# ── TEST 7: Unknown ward ───────────────────────────────────────────────────────
def test_7_unknown_ward(db_session: Session):
    h = create_test_hospital(db_session, "H7")
    rec = {
        "hospital_id": h.id,
        "ward_id": 9999,
        "date": "2026-05-01",
        "occupied_beds": 10,
        "capacity": 20,
    }
    res = HistoricalDataValidationService.validate_daily_record(db_session, rec)
    assert res["is_valid"] is False
    assert res["status"] == ValidationStatus.UNKNOWN_WARD.value


# ── TEST 8: Ward belonging to another hospital ────────────────────────────────
def test_8_ward_belonging_to_another_hospital(db_session: Session):
    h1 = create_test_hospital(db_session, "H8A")
    h2 = create_test_hospital(db_session, "H8B")
    w2 = create_test_ward(db_session, h2.id, "WardB", capacity=15)

    rec = {
        "hospital_id": h1.id,  # Mismatched hospital
        "ward_id": w2.id,
        "date": "2026-05-01",
        "occupied_beds": 10,
        "capacity": 15,
    }
    res = HistoricalDataValidationService.validate_daily_record(db_session, rec)
    assert res["is_valid"] is False
    assert res["status"] == ValidationStatus.UNKNOWN_WARD.value


# ── TEST 9: Exact duplicate observation ────────────────────────────────────────
def test_9_exact_duplicate_observation(db_session: Session):
    h = create_test_hospital(db_session, "H9")
    w = create_test_ward(db_session, h.id, "Ward9", capacity=20)

    records = [
        {"hospital_id": h.id, "ward_id": w.id, "date": "2026-05-01", "occupied_beds": 12, "capacity": 20},
        {"hospital_id": h.id, "ward_id": w.id, "date": "2026-05-01", "occupied_beds": 12, "capacity": 20},
    ]
    proc = HistoricalDataValidationService.process_and_deduplicate_observations(db_session, records)
    assert proc["valid_count"] == 1
    assert proc["duplicate_count"] == 1
    assert proc["conflict_count"] == 0


# ── TEST 10: Conflicting observation for same hospital/ward/date ──────────────
def test_10_conflicting_observation(db_session: Session):
    h = create_test_hospital(db_session, "H10")
    w = create_test_ward(db_session, h.id, "Ward10", capacity=20)

    records = [
        {"hospital_id": h.id, "ward_id": w.id, "date": "2026-05-01", "occupied_beds": 10, "capacity": 20},
        {"hospital_id": h.id, "ward_id": w.id, "date": "2026-05-01", "occupied_beds": 18, "capacity": 20},
    ]
    proc = HistoricalDataValidationService.process_and_deduplicate_observations(db_session, records)
    assert proc["valid_count"] == 1
    assert proc["conflict_count"] == 1
    # Existing record was left unchanged at 10
    assert proc["valid_records"][0]["occupied_beds"] == 10.0


# ── TEST 11: Missing date detection ────────────────────────────────────────────
def test_11_missing_date_detection(db_session: Session):
    h = create_test_hospital(db_session, "H11")
    w = create_test_ward(db_session, h.id, "Ward11", capacity=20)

    # Insert snapshots skipping May 03
    dates_to_insert = ["2026-05-01", "2026-05-02", "2026-05-04", "2026-05-05"]
    for d_str in dates_to_insert:
        d_obj = datetime.strptime(d_str, "%Y-%m-%d")
        snap = OccupancySnapshot(
            hospital_id=h.id,
            ward_id=w.id,
            snapshot_time=d_obj,
            total_beds=20,
            occupied_beds=10,
            available_beds=10,
            occupancy_percentage=50.0,
            data_source="HOSPITAL_API",
        )
        db_session.add(snap)
    db_session.commit()

    prep = HistoricalDataValidationService.prepare_daily_time_series(db_session, h.id, w.id)
    assert prep["total_observations"] == 5
    assert prep["observed_count"] == 4
    assert prep["imputed_count"] == 1
    assert "2026-05-03" in prep["missing_dates"]

    # Verify imputed observation details
    imputed_items = [x for x in prep["clean_series"] if x["is_imputed"]]
    assert len(imputed_items) == 1
    assert imputed_items[0]["date_str"] == "2026-05-03"
    assert imputed_items[0]["imputation_method"] == "FORWARD_FILL"
    assert imputed_items[0]["occupied_beds"] == 10.0


# ── TEST 12: Chronological ordering ───────────────────────────────────────────
def test_12_chronological_ordering(db_session: Session):
    h = create_test_hospital(db_session, "H12")
    w = create_test_ward(db_session, h.id, "Ward12", capacity=20)

    # Insert out of order
    dates_shuffled = ["2026-05-05", "2026-05-01", "2026-05-04", "2026-05-02", "2026-05-03"]
    for d_str in dates_shuffled:
        snap = OccupancySnapshot(
            hospital_id=h.id,
            ward_id=w.id,
            snapshot_time=datetime.strptime(d_str, "%Y-%m-%d"),
            total_beds=20,
            occupied_beds=12,
            available_beds=8,
            occupancy_percentage=60.0,
        )
        db_session.add(snap)
    db_session.commit()

    prep = HistoricalDataValidationService.prepare_daily_time_series(db_session, h.id, w.id)
    assert prep["dates"] == sorted(dates_shuffled)


# ── TEST 13: Capacity changes over time ───────────────────────────────────────
def test_13_capacity_changes_over_time(db_session: Session):
    h = create_test_hospital(db_session, "H13")
    w = create_test_ward(db_session, h.id, "Ward13", capacity=30)  # Current ward capacity is 30

    # Earlier observation had total_beds = 20
    snap1 = OccupancySnapshot(
        hospital_id=h.id,
        ward_id=w.id,
        snapshot_time=datetime(2026, 1, 15, 23, 59),
        total_beds=20,
        occupied_beds=15,
        available_beds=5,
        occupancy_percentage=75.0,
    )
    # Later observation had total_beds = 25
    snap2 = OccupancySnapshot(
        hospital_id=h.id,
        ward_id=w.id,
        snapshot_time=datetime(2026, 2, 15, 23, 59),
        total_beds=25,
        occupied_beds=20,
        available_beds=5,
        occupancy_percentage=80.0,
    )
    db_session.add_all([snap1, snap2])
    db_session.commit()

    prep = HistoricalDataValidationService.prepare_daily_time_series(db_session, h.id, w.id)
    first_obs = prep["clean_series"][0]
    assert first_obs["capacity"] == 20.0  # Retained historical capacity, NOT overwritten with 30


# ── TEST 14: Insufficient historical data ──────────────────────────────────────
def test_14_insufficient_historical_data(db_session: Session):
    h = create_test_hospital(db_session, "H14")
    w = create_test_ward(db_session, h.id, "Ward14", capacity=10)

    # Only 3 daily observations (threshold is 7)
    for i in range(3):
        snap = OccupancySnapshot(
            hospital_id=h.id,
            ward_id=w.id,
            snapshot_time=datetime(2026, 5, 1 + i, 12, 0),
            total_beds=10,
            occupied_beds=5,
            available_beds=5,
            occupancy_percentage=50.0,
        )
        db_session.add(snap)
    db_session.commit()

    res = ForecastService.generate_ward_forecast(db_session, ward_id=w.id, hospital_id=h.id)
    assert res["status"] == "INSUFFICIENT_DATA"
    assert res["available_observations"] == 3
    assert res["required_observations"] == 7
    assert "Insufficient historical data" in res["message"]


# ── TEST 15: Daily frequency reaches SARIMA correctly ──────────────────────────
def test_15_daily_frequency_reaches_sarima(db_session: Session):
    history = [10.0 + (i % 3) for i in range(16)]  # 16 daily counts (>= 14)
    res = TimeSeriesForecaster.forecast_sarima(history, total_beds=20, horizon=7)
    assert res["status"] == "SUCCESS"
    assert res["model_name"] == "SARIMA"
    assert len(res["predictions"]) == 7
    assert "7" in res["seasonal_order"]  # Seasonal order (1, 0, 0, 7) weekly cycle


# ── TEST 16: Existing SARIMA forecast endpoint regression ──────────────────────
def test_16_sarima_forecast_endpoint_regression(client: TestClient, db_session: Session):
    h = create_test_hospital(db_session, "H16")
    w = create_test_ward(db_session, h.id, "Ward16", capacity=15)
    headers = create_auth_headers(db_session, h.id, UserRole.ADMIN.value)

    # Seed 15 daily snapshots for SARIMA
    for i in range(15):
        snap = OccupancySnapshot(
            hospital_id=h.id,
            ward_id=w.id,
            snapshot_time=datetime(2026, 6, 1 + i, 23, 59),
            total_beds=15,
            occupied_beds=8 + (i % 4),
            available_beds=7 - (i % 4),
            occupancy_percentage=round(((8 + (i % 4)) / 15) * 100, 2),
        )
        db_session.add(snap)
    db_session.commit()

    resp = client.get(f"/api/v1/forecasting/wards/{w.id}/forecast?horizon=7", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["model"] == "SARIMA"
    assert len(data["forecasts"]) == 7


# ── TEST 17: Existing occupancy API regression ─────────────────────────────────
def test_17_occupancy_api_regression(client: TestClient, db_session: Session):
    h = create_test_hospital(db_session, "H17")
    w = create_test_ward(db_session, h.id, "Ward17", capacity=10)
    bed = Bed(hospital_id=h.id, ward_id=w.id, bed_number="B17-01", status=BedStatus.AVAILABLE.value)
    db_session.add(bed)
    db_session.commit()

    headers = create_auth_headers(db_session, h.id, UserRole.ADMIN.value)

    resp_hosp = client.get(f"/api/v1/occupancy/hospital?hospital_id={h.id}", headers=headers)
    assert resp_hosp.status_code == 200
    assert resp_hosp.json()["hospital_id"] == h.id

    resp_wards = client.get(f"/api/v1/occupancy/wards?hospital_id={h.id}", headers=headers)
    assert resp_wards.status_code == 200
    assert len(resp_wards.json()) >= 1


# ── TEST 18: Existing hospital API ingestion regression ───────────────────────
def test_18_ingestion_api_regression(client: TestClient, db_session: Session):
    h = create_test_hospital(db_session, "H18")
    w = create_test_ward(db_session, h.id, "Ward18", capacity=10)
    bed = Bed(hospital_id=h.id, ward_id=w.id, bed_number="B18-01", status=BedStatus.AVAILABLE.value)
    db_session.add(bed)
    db_session.commit()

    headers = create_auth_headers(db_session, h.id, UserRole.ADMIN.value)

    payload = {
        "event_id": "TEST-INGEST-EV-01",
        "hospital_id": h.id,
        "ward_id": w.id,
        "bed_id": bed.id,
        "event_type": "ADMISSION",
        "event_time": datetime.utcnow().isoformat(),
        "source": "API",
    }
    resp = client.post("/api/v1/ingestion/events", json=payload, headers=headers)
    assert resp.status_code == 200
    db_session.refresh(bed)
    assert bed.status == BedStatus.OCCUPIED.value


# ── TEST 19: Existing inter-ward transfer regression ──────────────────────────
def test_19_inter_ward_transfer_regression(client: TestClient, db_session: Session):
    h = create_test_hospital(db_session, "H19")
    w1 = create_test_ward(db_session, h.id, "Ward19A", capacity=10)
    w2 = create_test_ward(db_session, h.id, "Ward19B", capacity=10)
    headers = create_auth_headers(db_session, h.id, UserRole.ADMIN.value)

    resp = client.get("/api/v1/transfers/rules", headers=headers)
    assert resp.status_code == 200


# ── TEST 20: Authentication and hospital isolation regression ─────────────────
def test_20_auth_and_hospital_isolation_regression(client: TestClient, db_session: Session):
    h1 = create_test_hospital(db_session, "H20A")
    h2 = create_test_hospital(db_session, "H20B")
    w2 = create_test_ward(db_session, h2.id, "Ward20B", capacity=10)

    # Headers for user belonging strictly to Hospital 1
    h1_headers = create_auth_headers(db_session, h1.id, UserRole.DOCTOR.value)

    # Attempting to access Hospital 2 ward forecast should be 403 Forbidden
    resp = client.get(f"/api/v1/forecasting/wards/{w2.id}/forecast", headers=h1_headers)
    assert resp.status_code == 403

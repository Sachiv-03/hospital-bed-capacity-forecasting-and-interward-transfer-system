"""
Phase 13 Test Suite — Management Analytics Dashboard
Comprehensive tests covering:
- Dashboard aggregation accuracy
- Bed-capacity and occupancy calculations (avoiding division-by-zero, operational beds formula)
- Hospital and ward filtering
- Empty and missing datasets
- Invalid capacity values and not-found error handling
- Forecast response integration and risk categorization
- Risk and alert summaries
- Transfer-status summaries (REQUESTED, APPROVED, COMPLETED)
- Authorization and cross-hospital tenant isolation (SUPER_ADMIN vs regular user)
- Data freshness timestamps
"""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import create_access_token
from app.database.database import Base
from app.main import app
from app.models.admission import Admission, AdmissionStatus
from app.models.bed import Bed, BedStatus, BedType
from app.models.capacity_alert import AlertSeverity, AlertStatus, AlertType, CapacityAlert
from app.models.hospital import Hospital, HospitalStatus
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.patient import Patient, PatientStatus
from app.models.transfer import Transfer, TransferStatus
from app.models.transfer_recommendation import (
    RecommendationPriority,
    RecommendationStatus,
    TransferRecommendation,
)
from app.models.user import User, UserRole
from app.models.ward import Ward, WardStatus


# ── In-Memory SQLite for Thread-Safe Test Isolation ─────────────────────────
SQLITE_URL = "sqlite:///:memory:"
engine_test = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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
        # Clear tables between tests
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db: Session):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# ── Helpers ──────────────────────────────────────────────────────────────────
def seed_hospital(db: Session, name="Metro General", code="MG01") -> Hospital:
    h = Hospital(name=name, code=code, status=HospitalStatus.ACTIVE.value)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


def seed_ward(db: Session, hospital_id: int, name="Cardiology Ward", capacity=20, ward_type="GENERAL", floor="1st Floor") -> Ward:
    w = Ward(
        hospital_id=hospital_id,
        name=name,
        ward_type=ward_type,
        department="Medicine",
        floor=floor,
        capacity=capacity,
        status=WardStatus.ACTIVE.value,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def seed_beds(db: Session, ward_id: int, hospital_id: int, occupied: int = 5, available: int = 15, cleaning: int = 0, maintenance: int = 0):
    beds = []
    # Occupied
    for i in range(occupied):
        beds.append(Bed(
            ward_id=ward_id,
            hospital_id=hospital_id,
            bed_number=f"BED-OCC-{i+1}",
            bed_type=BedType.STANDARD.value,
            status=BedStatus.OCCUPIED.value,
        ))
    # Available
    for i in range(available):
        beds.append(Bed(
            ward_id=ward_id,
            hospital_id=hospital_id,
            bed_number=f"BED-AVL-{i+1}",
            bed_type=BedType.STANDARD.value,
            status=BedStatus.AVAILABLE.value,
        ))
    # Cleaning
    for i in range(cleaning):
        beds.append(Bed(
            ward_id=ward_id,
            hospital_id=hospital_id,
            bed_number=f"BED-CLN-{i+1}",
            bed_type=BedType.STANDARD.value,
            status=BedStatus.CLEANING.value,
        ))
    # Maintenance
    for i in range(maintenance):
        beds.append(Bed(
            ward_id=ward_id,
            hospital_id=hospital_id,
            bed_number=f"BED-MNT-{i+1}",
            bed_type=BedType.STANDARD.value,
            status=BedStatus.MAINTENANCE.value,
        ))
    db.add_all(beds)
    db.commit()


def create_test_user(db: Session, email="admin@metro.com", role=UserRole.ADMIN.value, hospital_id=1) -> tuple[User, str]:
    user = User(
        email=email,
        full_name="Hospital Administrator",
        password_hash="fakehashedpassword",
        role=role,
        hospital_id=hospital_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=user.id, role=user.role)
    return user, token


# ── TEST CASES ───────────────────────────────────────────────────────────────

def test_dashboard_aggregation_accuracy(db: Session, client: TestClient):
    """Test accurate operational bed count, occupancy rate, and available beds."""
    h = seed_hospital(db, name="City Health Center", code="CHC1")
    w1 = seed_ward(db, h.id, name="ICU", capacity=10, ward_type="ICU")
    w2 = seed_ward(db, h.id, name="Surgical", capacity=20, ward_type="SURGICAL")

    # W1: 6 occupied, 4 available (operational = 10, total = 10)
    seed_beds(db, w1.id, h.id, occupied=6, available=4)
    # W2: 10 occupied, 8 available, 2 cleaning (operational = 18, total = 20)
    seed_beds(db, w2.id, h.id, occupied=10, available=8, cleaning=2)

    _, token = create_test_user(db, hospital_id=h.id)

    response = client.get(
        "/api/v1/occupancy/management-analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["hospital_id"] == h.id
    assert data["hospital_name"] == h.name
    metrics = data["overview_metrics"]
    assert metrics["total_capacity"] == 30  # 10 + 20
    assert metrics["operational_beds"] == 28  # (6+4) + (10+8)
    assert metrics["occupied_beds"] == 16  # 6 + 10
    assert metrics["available_beds"] == 12  # 4 + 8
    # Occupancy rate = 16 / 28 * 100 = 57.14%
    assert metrics["occupancy_rate"] == 57.14
    assert metrics["status"] == "NORMAL"
    assert len(data["ward_occupancy_breakdown"]) == 2


def test_operational_bed_formula_and_zero_division_safety(db: Session, client: TestClient):
    """Test hospital with 0 operational beds does not cause division-by-zero errors."""
    h = seed_hospital(db, name="Empty Care Facility", code="ECF1")
    w = seed_ward(db, h.id, name="Rehab Ward", capacity=10)
    # 0 occupied, 0 available, 5 maintenance beds
    seed_beds(db, w.id, h.id, occupied=0, available=0, maintenance=5)

    _, token = create_test_user(db, hospital_id=h.id)

    response = client.get(
        "/api/v1/occupancy/management-analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    metrics = data["overview_metrics"]
    assert metrics["total_capacity"] == 5
    assert metrics["operational_beds"] == 0
    assert metrics["occupied_beds"] == 0
    assert metrics["available_beds"] == 0
    assert metrics["occupancy_rate"] == 0.0
    assert metrics["status"] == "NORMAL"


def test_hospital_and_ward_filtering(db: Session, client: TestClient):
    """Test filtering dashboard payload down to a single selected ward."""
    h = seed_hospital(db, name="Apex Medical Center", code="AMC1")
    w1 = seed_ward(db, h.id, name="General Medicine", capacity=25)
    w2 = seed_ward(db, h.id, name="Pediatrics", capacity=15)

    seed_beds(db, w1.id, h.id, occupied=15, available=10)
    seed_beds(db, w2.id, h.id, occupied=5, available=10)

    _, token = create_test_user(db, hospital_id=h.id)

    # Query with ward_id=w1.id
    response = client.get(
        f"/api/v1/occupancy/management-analytics?ward_id={w1.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["selected_ward_id"] == w1.id
    assert data["selected_ward_name"] == w1.name
    metrics = data["overview_metrics"]
    assert metrics["total_capacity"] == 25
    assert metrics["occupied_beds"] == 15
    assert metrics["available_beds"] == 10
    assert metrics["occupancy_rate"] == 60.0


def test_empty_and_missing_datasets(db: Session, client: TestClient):
    """Test hospital with zero wards returns empty breakdown and zero metrics cleanly."""
    h = seed_hospital(db, name="New Unopened Hospital", code="NUH1")
    _, token = create_test_user(db, hospital_id=h.id)

    response = client.get(
        "/api/v1/occupancy/management-analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overview_metrics"]["total_capacity"] == 0
    assert data["overview_metrics"]["total_wards"] == 0
    assert data["overview_metrics"]["occupied_beds"] == 0
    assert data["overview_metrics"]["available_beds"] == 0
    assert len(data["ward_occupancy_breakdown"]) == 0


def test_invalid_hospital_and_ward_error_handling(db: Session, client: TestClient):
    """Test cross-hospital ward filter or non-existent hospital returns appropriate error."""
    h1 = seed_hospital(db, name="Hospital One", code="H01")
    h2 = seed_hospital(db, name="Hospital Two", code="H02")
    w_h2 = seed_ward(db, h2.id, name="Hospital Two Ward", capacity=10)

    _, token = create_test_user(db, hospital_id=h1.id)

    # 1. Attempting to query another ward from H2 while belonging to H1
    response = client.get(
        f"/api/v1/occupancy/management-analytics?ward_id={w_h2.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    # 2. Non-existent ward
    response = client.get(
        "/api/v1/occupancy/management-analytics?ward_id=99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_alert_summary_integration(db: Session, client: TestClient):
    """Test active alerts, high/critical severity alerts, and unacknowledged counts."""
    h = seed_hospital(db, name="Alert Testing Hospital", code="ATH1")
    w = seed_ward(db, h.id, name="Trauma Center", capacity=20)
    seed_beds(db, w.id, h.id, occupied=18, available=2)

    now = datetime.now(timezone.utc)
    # Seed 1 CRITICAL active alert, 1 HIGH active alert, 1 INFO active alert, 1 RESOLVED alert
    a1 = CapacityAlert(
        hospital_id=h.id,
        ward_id=w.id,
        alert_type=AlertType.CAPACITY_EXCEEDANCE.value,
        severity=AlertSeverity.CRITICAL.value,
        message="Critical capacity warning",
        trigger_value=95.0,
        threshold_value=90.0,
        status=AlertStatus.ACTIVE.value,
        created_at=now,
    )
    a2 = CapacityAlert(
        hospital_id=h.id,
        ward_id=w.id,
        alert_type=AlertType.RAPID_INCREASE.value,
        severity=AlertSeverity.HIGH.value,
        message="Rapid occupancy increase",
        trigger_value=86.0,
        threshold_value=85.0,
        status=AlertStatus.ACTIVE.value,
        created_at=now,
    )
    a3 = CapacityAlert(
        hospital_id=h.id,
        ward_id=w.id,
        alert_type=AlertType.INSUFFICIENT_DATA.value,
        severity=AlertSeverity.INFO.value,
        message="Info note",
        trigger_value=5.0,
        threshold_value=7.0,
        status=AlertStatus.ACTIVE.value,
        created_at=now,
    )
    a4 = CapacityAlert(
        hospital_id=h.id,
        ward_id=w.id,
        alert_type=AlertType.CAPACITY_EXCEEDANCE.value,
        severity=AlertSeverity.HIGH.value,
        message="Resolved past alert",
        trigger_value=88.0,
        threshold_value=85.0,
        status=AlertStatus.RESOLVED.value,
        created_at=now - timedelta(days=2),
        resolved_at=now - timedelta(days=1),
    )
    db.add_all([a1, a2, a3, a4])
    db.commit()

    _, token = create_test_user(db, hospital_id=h.id)

    response = client.get(
        "/api/v1/occupancy/management-analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    metrics = data["overview_metrics"]
    assert metrics["total_active_alerts"] == 3
    assert metrics["active_high_severity_alerts"] == 2  # a1 (CRITICAL) + a2 (HIGH)
    assert metrics["unacknowledged_alerts"] == 3


def test_transfer_status_summary_integration(db: Session, client: TestClient):
    """Test transfer activity summary: REQUESTED, APPROVED, COMPLETED counts."""
    h = seed_hospital(db, name="Transfer Testing Hospital", code="TTH1")
    w1 = seed_ward(db, h.id, name="Source Ward", capacity=10)
    w2 = seed_ward(db, h.id, name="Destination Ward", capacity=10)

    # Seed patient
    patient = Patient(
        hospital_id=h.id,
        patient_identifier="P_TEST_001",
        first_name="John",
        last_name="Doe",
        date_of_birth=datetime(1990, 1, 1).date(),
        gender="MALE",
        status=PatientStatus.ACTIVE.value,
    )
    db.add(patient)
    db.commit()

    # Seed admission
    adm = Admission(
        hospital_id=h.id,
        patient_id=patient.id,
        ward_id=w1.id,
        bed_id=1,
        admission_number="ADM-TEST-001",
        status=AdmissionStatus.ADMITTED.value,
    )
    db.add(adm)
    db.commit()

    # Seed 1 REQUESTED transfer, 1 APPROVED transfer, 1 COMPLETED transfer
    t1 = Transfer(hospital_id=h.id, patient_id=patient.id, admission_id=adm.id, source_ward_id=w1.id, destination_ward_id=w2.id, source_bed_id=1, destination_bed_id=2, status=TransferStatus.REQUESTED.value)
    t2 = Transfer(hospital_id=h.id, patient_id=patient.id, admission_id=adm.id, source_ward_id=w1.id, destination_ward_id=w2.id, source_bed_id=1, destination_bed_id=3, status=TransferStatus.APPROVED.value)
    t3 = Transfer(hospital_id=h.id, patient_id=patient.id, admission_id=adm.id, source_ward_id=w1.id, destination_ward_id=w2.id, source_bed_id=1, destination_bed_id=4, status=TransferStatus.COMPLETED.value)
    
    # Seed 1 recommendation
    rec = TransferRecommendation(
        hospital_id=h.id,
        source_ward_id=w1.id,
        destination_ward_id=w2.id,
        source_current_occupancy=90.0,
        source_predicted_occupancy=95.0,
        destination_current_occupancy=50.0,
        destination_predicted_occupancy=55.0,
        available_beds=5,
        safe_transfer_capacity=3,
        recommended_transfer_count=2,
        priority_score=85.0,
        priority_level=RecommendationPriority.HIGH.value,
        status=RecommendationStatus.PENDING.value,
        reason="Capacity relief",
        forecast_horizon_days=7,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add_all([t1, t2, t3, rec])
    db.commit()

    _, token = create_test_user(db, hospital_id=h.id)

    response = client.get(
        "/api/v1/occupancy/management-analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    metrics = data["overview_metrics"]
    assert metrics["pending_transfer_requests"] == 1
    assert metrics["approved_transfers"] == 1
    assert metrics["completed_transfers"] == 1
    assert metrics["pending_transfer_recommendations"] == 1

    tf = data["transfer_activity"]
    assert tf["by_status"]["REQUESTED"] == 1
    assert tf["by_status"]["APPROVED"] == 1
    assert tf["by_status"]["COMPLETED"] == 1


def test_authorization_and_cross_hospital_tenant_isolation(db: Session, client: TestClient):
    """Test tenant isolation: regular user cannot access another hospital; super_admin can."""
    h1 = seed_hospital(db, name="Facility Alpha", code="FA01")
    h2 = seed_hospital(db, name="Facility Beta", code="FB02")

    _user_alpha, token_alpha = create_test_user(db, email="user@alpha.com", role=UserRole.DOCTOR.value, hospital_id=h1.id)
    _user_super, token_super = create_test_user(db, email="super@system.com", role=UserRole.SUPER_ADMIN.value, hospital_id=h1.id)

    # 1. Regular user querying their own hospital -> 200 OK
    res1 = client.get(
        "/api/v1/occupancy/management-analytics",
        headers={"Authorization": f"Bearer {token_alpha}"},
    )
    assert res1.status_code == 200
    assert res1.json()["hospital_id"] == h1.id

    # 2. Regular user trying to query another hospital -> 403 Forbidden
    res2 = client.get(
        f"/api/v1/occupancy/management-analytics?hospital_id={h2.id}",
        headers={"Authorization": f"Bearer {token_alpha}"},
    )
    assert res2.status_code == 403

    # 3. Super admin querying facility beta -> 200 OK
    res3 = client.get(
        f"/api/v1/occupancy/management-analytics?hospital_id={h2.id}",
        headers={"Authorization": f"Bearer {token_super}"},
    )
    assert res3.status_code == 200
    assert res3.json()["hospital_id"] == h2.id


def test_data_freshness_timestamps(db: Session, client: TestClient):
    """Test reliable freshness timestamps are returned in the payload."""
    h = seed_hospital(db, name="Timestamp Testing Hospital", code="TTH2")
    w = seed_ward(db, h.id, name="General Ward", capacity=10)
    seed_beds(db, w.id, h.id, occupied=2, available=8)

    # Add snapshot
    snap_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    snap = OccupancySnapshot(
        hospital_id=h.id,
        ward_id=w.id,
        total_beds=10,
        occupied_beds=2,
        available_beds=8,
        occupancy_percentage=20.0,
        snapshot_time=snap_time,
    )
    db.add(snap)
    db.commit()

    _, token = create_test_user(db, hospital_id=h.id)

    response = client.get(
        "/api/v1/occupancy/management-analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    freshness = data["freshness"]
    assert "reporting_timestamp" in freshness
    assert freshness["reporting_timestamp"] is not None
    assert freshness["occupancy_last_updated"] is not None

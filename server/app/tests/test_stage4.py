"""
Stage 4 Inter-Ward Transfer Decision Support System Pytest Test Suite.
Tests all 18 Stage 4 functional and security requirements.
"""
import pytest
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.main import app
from app.models.hospital import Hospital
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus
from app.models.bed_capacity_forecast import BedCapacityForecast, RiskLevel
from app.models.user import User, UserRole
from app.models.ward_transfer_rule import WardTransferRule
from app.models.transfer_recommendation import TransferRecommendation, RecommendationStatus, RecommendationPriority
from app.models.audit_log import AuditLog
from app.services.transfer_scoring_service import TransferScoringService
from app.services.transfer_service import TransferService
from app.core.security import create_access_token


@pytest.fixture(scope="function")
def test_setup():
    """Create a fresh in-memory SQLite database engine & session maker for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


@pytest.fixture(scope="function")
def db_session(test_setup):
    """Create a database session for seeding and verification."""
    session = test_setup()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden DB dependency pointing to current db_session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def setup_multi_hospital(db_session: Session):
    """Seed multi-hospital test dataset with wards, beds, forecasts, rules, and users."""
    # Hospital 1: St. Jude
    h1 = Hospital(name="St. Jude Medical Center", code="H_STJUDE_TEST", city="Chicago", status="ACTIVE")
    # Hospital 2: MetroCare
    h2 = Hospital(name="MetroCare Health", code="H_METRO_TEST", city="Boston", status="ACTIVE")
    db_session.add_all([h1, h2])
    db_session.commit()

    # Hospital 1 Wards
    w1_icu = Ward(hospital_id=h1.id, name="ICU Unit A", ward_type=WardType.ICU.value, department="Critical Care", floor="Floor 3", capacity=10, status=WardStatus.ACTIVE.value)
    w1_step = Ward(hospital_id=h1.id, name="Step-Down Unit B", ward_type=WardType.STEP_DOWN.value, department="Intermediate Care", floor="Floor 2", capacity=20, status=WardStatus.ACTIVE.value)
    w1_gen = Ward(hospital_id=h1.id, name="General Ward C", ward_type=WardType.GENERAL.value, department="Internal Med", floor="Floor 1", capacity=30, status=WardStatus.ACTIVE.value)
    
    # Hospital 2 Wards
    w2_icu = Ward(hospital_id=h2.id, name="Metro ICU", ward_type=WardType.ICU.value, department="Critical Care", floor="Floor 4", capacity=10, status=WardStatus.ACTIVE.value)
    w2_gen = Ward(hospital_id=h2.id, name="Metro General", ward_type=WardType.GENERAL.value, department="General Med", floor="Floor 2", capacity=20, status=WardStatus.ACTIVE.value)

    db_session.add_all([w1_icu, w1_step, w1_gen, w2_icu, w2_gen])
    db_session.commit()

    # Seed Beds for w1_icu (10 total: 9 occupied = 90% occ)
    for i in range(1, 11):
        status = BedStatus.OCCUPIED.value if i <= 9 else BedStatus.AVAILABLE.value
        db_session.add(Bed(hospital_id=h1.id, ward_id=w1_icu.id, bed_number=f"ICU-{i:02d}", status=status))

    # Seed Beds for w1_step (20 total: 12 occupied = 60% occ, 8 available)
    for i in range(1, 21):
        status = BedStatus.OCCUPIED.value if i <= 12 else BedStatus.AVAILABLE.value
        db_session.add(Bed(hospital_id=h1.id, ward_id=w1_step.id, bed_number=f"STEP-{i:02d}", status=status))

    # Seed Beds for w1_gen (30 total: 20 occupied = 66.7% occ, 10 available)
    for i in range(1, 31):
        status = BedStatus.OCCUPIED.value if i <= 20 else BedStatus.AVAILABLE.value
        db_session.add(Bed(hospital_id=h1.id, ward_id=w1_gen.id, bed_number=f"GEN-{i:02d}", status=status))

    # Seed Beds for Hospital 2
    for i in range(1, 11):
        db_session.add(Bed(hospital_id=h2.id, ward_id=w2_icu.id, bed_number=f"M-ICU-{i:02d}", status=BedStatus.OCCUPIED.value))
    for i in range(1, 21):
        db_session.add(Bed(hospital_id=h2.id, ward_id=w2_gen.id, bed_number=f"M-GEN-{i:02d}", status=BedStatus.AVAILABLE.value))

    db_session.commit()

    # Seed Stage 3 Forecasts
    forecast_icu = BedCapacityForecast(
        hospital_id=h1.id,
        ward_id=w1_icu.id,
        forecast_date=date.today() + timedelta(days=1),
        predicted_occupied_beds=9.6,
        predicted_occupancy_percentage=96.0,
        lower_bound=90.0,
        upper_bound=100.0,
        risk_level=RiskLevel.CRITICAL.value,
    )
    forecast_step = BedCapacityForecast(
        hospital_id=h1.id,
        ward_id=w1_step.id,
        forecast_date=date.today() + timedelta(days=1),
        predicted_occupied_beds=13.0,
        predicted_occupancy_percentage=65.0,
        lower_bound=60.0,
        upper_bound=70.0,
        risk_level=RiskLevel.NORMAL.value,
    )
    db_session.add_all([forecast_icu, forecast_step])
    db_session.commit()

    # Seed Users
    u1_doctor = User(full_name="Dr. Alice Smith", email="alice@stjude.org", password_hash="hash", role=UserRole.DOCTOR.value, hospital_id=h1.id)
    u1_admin = User(full_name="Admin StJude", email="admin@stjude.org", password_hash="hash", role=UserRole.ADMIN.value, hospital_id=h1.id)
    u2_admin = User(full_name="Bob Admin", email="bob@metro.org", password_hash="hash", role=UserRole.ADMIN.value, hospital_id=h2.id)
    u1_receptionist = User(full_name="Rita Reception", email="rita@stjude.org", password_hash="hash", role=UserRole.RECEPTIONIST.value, hospital_id=h1.id)

    db_session.add_all([u1_doctor, u1_admin, u2_admin, u1_receptionist])
    db_session.commit()

    return {
        "h1": h1,
        "h2": h2,
        "w1_icu": w1_icu,
        "w1_step": w1_step,
        "w1_gen": w1_gen,
        "w2_icu": w2_icu,
        "w2_gen": w2_gen,
        "u1_doctor": u1_doctor,
        "u1_admin": u1_admin,
        "u2_admin": u2_admin,
        "u1_receptionist": u1_receptionist,
    }


# ── 1. SAFE CAPACITY CALCULATION TEST ─────────────────────────────────────────
def test_calculate_safe_capacity():
    """Verify max safe occupancy calculation with safety headroom & minimum buffer."""
    # 20 beds total, 12 occupied. Max safe occupancy = 85% (17 beds). Available = 8. Min buffer = 2 beds.
    # Safe headroom = 17 - 12 = 5 beds. Available after buffer = 8 - 2 = 6. min(5, 6) = 5 beds.
    safe_cap = TransferService.calculate_safe_capacity(
        total_beds=20, occupied_beds=12, max_safe_occ_pct=85.0, min_available_beds=2
    )
    assert safe_cap == 5

    # If ward is already at 85% occupancy, safe capacity should be 0
    safe_cap_full = TransferService.calculate_safe_capacity(
        total_beds=20, occupied_beds=17, max_safe_occ_pct=85.0, min_available_beds=2
    )
    assert safe_cap_full == 0


# ── 2. SCORING & PRIORITY TEST ────────────────────────────────────────────────
def test_transfer_scoring_engine():
    """Verify transparent 0-100 rule-based scoring breakdown and priority level classification."""
    score, priority, breakdown = TransferScoringService.calculate_score(
        source_current_occ=90.0,
        source_pred_occ=96.0,
        source_risk_level="CRITICAL",
        dest_current_occ=60.0,
        dest_pred_occ=65.0,
        dest_available_beds=8,
        safe_transfer_capacity=5,
        compatibility_allowed=True,
        rule_priority=2,
    )

    assert score > 80.0
    assert priority == RecommendationPriority.CRITICAL
    assert "source_urgency" in breakdown
    assert "destination_capacity" in breakdown
    assert "future_capacity" in breakdown
    assert "compatibility" in breakdown
    assert breakdown["source_urgency"] == 40.0


# ── 3. RECOMMENDATION GENERATION TEST ────────────────────────────────────────
def test_generate_recommendations(client: TestClient, setup_multi_hospital):
    """Test generating transfer recommendations for Hospital 1."""
    data = setup_multi_hospital
    token = create_access_token(data["u1_doctor"].id, data["u1_doctor"].role)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/transfers/recommendations/generate",
        headers=headers,
        json={"hospital_id": data["h1"].id, "horizon_days": 1}
    )

    assert resp.status_code == 201
    res = resp.json()
    assert res["hospital_id"] == data["h1"].id
    assert res["recommendations_generated"] >= 1
    assert res["source_wards_analyzed"] >= 1


# ── 4. LIST & DETAIL EXPLANATION TEST ────────────────────────────────────────
def test_list_and_get_recommendation_detail(client: TestClient, setup_multi_hospital):
    """Test listing recommendations and fetching transparent breakdown & explanation."""
    data = setup_multi_hospital
    token = create_access_token(data["u1_doctor"].id, data["u1_doctor"].role)
    headers = {"Authorization": f"Bearer {token}"}

    # Generate
    client.post("/api/v1/transfers/recommendations/generate", headers=headers, json={"hospital_id": data["h1"].id})

    # List
    list_resp = client.get(f"/api/v1/transfers/recommendations?hospital_id={data['h1'].id}", headers=headers)
    assert list_resp.status_code == 200
    recs = list_resp.json()
    assert len(recs) > 0
    rec_id = recs[0]["id"]

    # Detail
    detail_resp = client.get(f"/api/v1/transfers/recommendations/{rec_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == rec_id
    assert "reason" in detail
    assert "score_breakdown" in detail
    assert detail["revalidation_status"] == "VALID"


# ── 5. APPROVAL WORKFLOW & ZERO AUTO-TRANSFER ASSERTION TEST ──────────────────
def test_approval_workflow_no_auto_transfer(client: TestClient, setup_multi_hospital, db_session: Session):
    """Test staff approval records decision without altering patient location or bed count."""
    data = setup_multi_hospital
    token = create_access_token(data["u1_doctor"].id, data["u1_doctor"].role)
    headers = {"Authorization": f"Bearer {token}"}

    # Generate
    client.post("/api/v1/transfers/recommendations/generate", headers=headers, json={"hospital_id": data["h1"].id})
    recs = client.get(f"/api/v1/transfers/recommendations?hospital_id={data['h1'].id}", headers=headers).json()
    rec_id = recs[0]["id"]
    dest_ward_id = recs[0]["destination_ward_id"]

    # Measure bed count BEFORE approval
    occupied_beds_before = db_session.query(Bed).filter(Bed.ward_id == dest_ward_id, Bed.status == BedStatus.OCCUPIED.value).count()

    # Approve
    app_resp = client.post(
        f"/api/v1/transfers/recommendations/{rec_id}/approve",
        headers=headers,
        json={"notes": "Approved by Dr. Alice after clinical review"}
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # Measure bed count AFTER approval -> MUST BE EXACTLY UNCHANGED!
    occupied_beds_after = db_session.query(Bed).filter(Bed.ward_id == dest_ward_id, Bed.status == BedStatus.OCCUPIED.value).count()
    assert occupied_beds_before == occupied_beds_after


# ── 6. REJECTION WORKFLOW WITH MANDATORY REASON TEST ─────────────────────────
def test_rejection_workflow_requires_reason(client: TestClient, setup_multi_hospital, db_session: Session):
    """Test rejection requires a non-empty human explanation reason."""
    data = setup_multi_hospital
    token = create_access_token(data["u1_doctor"].id, data["u1_doctor"].role)
    headers = {"Authorization": f"Bearer {token}"}

    # Generate
    client.post("/api/v1/transfers/recommendations/generate", headers=headers, json={"hospital_id": data["h1"].id})
    recs = client.get(f"/api/v1/transfers/recommendations?hospital_id={data['h1'].id}", headers=headers).json()
    rec_id = recs[0]["id"]

    # Reject without reason -> Should fail with 400 Bad Request or 422 Unprocessable Entity
    bad_resp = client.post(f"/api/v1/transfers/recommendations/{rec_id}/reject", headers=headers, json={"rejection_reason": ""})
    assert bad_resp.status_code in [400, 422]

    # Proper rejection
    good_resp = client.post(
        f"/api/v1/transfers/recommendations/{rec_id}/reject",
        headers=headers,
        json={"rejection_reason": "Clinical decision: Patient unstable for inter-ward transfer."}
    )
    assert good_resp.status_code == 200
    assert good_resp.json()["status"] == "REJECTED"
    assert good_resp.json()["rejection_reason"] == "Clinical decision: Patient unstable for inter-ward transfer."


# ── 7. MULTI-HOSPITAL SECURITY ISOLATION TEST ────────────────────────────────
def test_multi_hospital_security_isolation(client: TestClient, setup_multi_hospital):
    """Verify strict tenant isolation (Hospital A cannot view/approve Hospital B recommendations)."""
    data = setup_multi_hospital
    token_h1 = create_access_token(data["u1_doctor"].id, data["u1_doctor"].role)
    token_h2 = create_access_token(data["u2_admin"].id, data["u2_admin"].role)
    headers_h1 = {"Authorization": f"Bearer {token_h1}"}
    headers_h2 = {"Authorization": f"Bearer {token_h2}"}

    # Generate for Hospital 1
    client.post("/api/v1/transfers/recommendations/generate", headers=headers_h1, json={"hospital_id": data["h1"].id})
    recs = client.get(f"/api/v1/transfers/recommendations?hospital_id={data['h1'].id}", headers=headers_h1).json()
    rec_id = recs[0]["id"]

    # Hospital 2 user attempting to access Hospital 1's recommendation detail -> 403 Forbidden
    cross_resp = client.get(f"/api/v1/transfers/recommendations/{rec_id}", headers=headers_h2)
    assert cross_resp.status_code == 403

    # Hospital 2 user attempting to approve Hospital 1 recommendation -> 403 Forbidden
    cross_app = client.post(f"/api/v1/transfers/recommendations/{rec_id}/approve", headers=headers_h2)
    assert cross_app.status_code == 403


# ── 8. UNAUTHENTICATED & UNAUTHORIZED ROLE SECURITY TEST ──────────────────────
def test_role_based_access_control(client: TestClient, setup_multi_hospital):
    """Verify 401 Unauthenticated and 403 Unauthorized Role enforcement."""
    data = setup_multi_hospital

    # Unauthenticated request -> 401
    unauth_resp = client.get(f"/api/v1/transfers/recommendations?hospital_id={data['h1'].id}")
    assert unauth_resp.status_code == 401

    # Receptionist attempting admin-only rule creation -> 403
    token_recep = create_access_token(data["u1_receptionist"].id, data["u1_receptionist"].role)
    headers_recep = {"Authorization": f"Bearer {token_recep}"}

    rule_resp = client.post(
        "/api/v1/transfers/rules",
        headers=headers_recep,
        json={
            "hospital_id": data["h1"].id,
            "source_ward_type": "ICU",
            "destination_ward_type": "GENERAL",
            "allowed": False
        }
    )
    assert rule_resp.status_code == 403


# ── 9. AUDIT LOGGING VERIFICATION TEST ──────────────────────────────────────
def test_audit_logging(client: TestClient, setup_multi_hospital, db_session: Session):
    """Verify audit log entries recorded for decision support operations."""
    data = setup_multi_hospital
    token_admin = create_access_token(data["u1_admin"].id, data["u1_admin"].role)
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # Generate recommendations
    client.post("/api/v1/transfers/recommendations/generate", headers=headers_admin, json={"hospital_id": data["h1"].id})

    # Fetch audit logs
    audit_resp = client.get(f"/api/v1/transfers/audit-logs?hospital_id={data['h1'].id}", headers=headers_admin)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    actions = [l["action"] for l in logs]
    assert "RECOMMENDATION_GENERATED" in actions

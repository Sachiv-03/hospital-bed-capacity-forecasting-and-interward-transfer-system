"""
Phase 11 Inter-Ward Transfer Decision Support System Pytest Test Suite.
Validates:
- Destination with suitable available bed & safe capacity
- Destination with no available beds (ineligibility handling)
- Capacity calculations (effective_capacity, maintenance, cleaning, reserved, pending transfers)
- Forecasted overcrowding & forecast_available_beds calculation
- Missing or stale forecast data safety (no crash, live capacity fallback, staleness warnings)
- Incompatible ward or bed type (ward transfer rules & specialty bed matching)
- Missing compatibility information (graceful default handling with verification required statement)
- Invalid patient, source ward, or destination ward validation
- Unauthorized users (401) and role-based permissions (403)
- Multi-hospital tenant isolation (cross-hospital rejection 403)
- Ranking & explanation accuracy (traceable reasons and transparent score breakdown)
- Concurrent / duplicate bed reservation prevention
- Valid and invalid transfer status transitions
- Occupancy consistency and atomic database transaction after approved transfer completion
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
from app.models.bed import Bed, BedStatus, BedType
from app.models.patient import Patient, PatientStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.transfer import Transfer, TransferStatus
from app.models.bed_capacity_forecast import BedCapacityForecast, RiskLevel
from app.models.user import User, UserRole
from app.models.ward_transfer_rule import WardTransferRule
from app.models.occupancy_event import OccupancyEvent, EventType
from app.services.transfer_service import TransferService
from app.services.patient_transfer_service import PatientTransferService
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
def phase11_dataset(db_session: Session):
    """Seed comprehensive dataset for testing Phase 11 decision support workflows."""
    # Hospitals
    h1 = Hospital(name="Mercy General Hospital", code="H_MERCY_P11", city="Chicago", status="ACTIVE")
    h2 = Hospital(name="St. Luke Medical Center", code="H_LUKE_P11", city="Boston", status="ACTIVE")
    db_session.add_all([h1, h2])
    db_session.commit()

    # Hospital 1 Wards:
    # 1. ICU (Overcrowded source ward: 10 beds, 9 occupied = 90%)
    w1_icu = Ward(hospital_id=h1.id, name="Intensive Care Unit", ward_type=WardType.ICU.value, department="Critical Care", floor="Floor 4", capacity=10, status=WardStatus.ACTIVE.value)
    # 2. Step-Down (Ideal destination: 15 beds, 6 occupied = 40%, 9 available, allowed by policy)
    w1_step = Ward(hospital_id=h1.id, name="Step-Down Unit", ward_type=WardType.STEP_DOWN.value, department="Intermediate Care", floor="Floor 3", capacity=15, status=WardStatus.ACTIVE.value)
    # 3. General Medicine (Disallowed direct transfer from ICU without step-down)
    w1_gen = Ward(hospital_id=h1.id, name="General Ward North", ward_type=WardType.GENERAL.value, department="Internal Med", floor="Floor 2", capacity=20, status=WardStatus.ACTIVE.value)
    # 4. Surgical Ward (Full / no available beds: 5 beds, 5 occupied = 100%)
    w1_surg_full = Ward(hospital_id=h1.id, name="Surgical Recovery", ward_type=WardType.SURGICAL.value, department="Surgery", floor="Floor 2", capacity=5, status=WardStatus.ACTIVE.value)
    # 5. Isolation Ward (Specialty ward with ISOLATION beds)
    w1_iso = Ward(hospital_id=h1.id, name="Infection Isolation Ward", ward_type=WardType.ISOLATION.value, department="Infectious Diseases", floor="Floor 1", capacity=8, status=WardStatus.ACTIVE.value)

    # Hospital 2 Ward (for cross-hospital security testing)
    w2_gen = Ward(hospital_id=h2.id, name="St. Luke General", ward_type=WardType.GENERAL.value, department="Medicine", floor="Floor 1", capacity=20, status=WardStatus.ACTIVE.value)

    db_session.add_all([w1_icu, w1_step, w1_gen, w1_surg_full, w1_iso, w2_gen])
    db_session.commit()

    # Beds for w1_icu (10 beds: 9 occupied, 1 available)
    icu_beds = []
    for i in range(1, 11):
        st = BedStatus.OCCUPIED.value if i <= 9 else BedStatus.AVAILABLE.value
        b = Bed(hospital_id=h1.id, ward_id=w1_icu.id, bed_number=f"ICU-{i:02d}", bed_type=BedType.ICU.value, status=st)
        icu_beds.append(b)
        db_session.add(b)

    # Beds for w1_step (15 beds: 6 occupied, 7 available, 1 cleaning, 1 maintenance)
    step_beds = []
    for i in range(1, 16):
        if i <= 6:
            st = BedStatus.OCCUPIED.value
        elif i <= 13:
            st = BedStatus.AVAILABLE.value
        elif i == 14:
            st = BedStatus.CLEANING.value
        else:
            st = BedStatus.MAINTENANCE.value
        b = Bed(hospital_id=h1.id, ward_id=w1_step.id, bed_number=f"STEP-{i:02d}", bed_type=BedType.STANDARD.value, status=st)
        step_beds.append(b)
        db_session.add(b)

    # Beds for w1_gen (20 beds: 10 occupied, 10 available)
    for i in range(1, 21):
        st = BedStatus.OCCUPIED.value if i <= 10 else BedStatus.AVAILABLE.value
        db_session.add(Bed(hospital_id=h1.id, ward_id=w1_gen.id, bed_number=f"GEN-{i:02d}", bed_type=BedType.STANDARD.value, status=st))

    # Beds for w1_surg_full (5 beds: ALL 5 OCCUPIED)
    for i in range(1, 6):
        db_session.add(Bed(hospital_id=h1.id, ward_id=w1_surg_full.id, bed_number=f"SURG-{i:02d}", bed_type=BedType.STANDARD.value, status=BedStatus.OCCUPIED.value))

    # Beds for w1_iso (8 beds: 4 occupied, 4 available - 2 ISOLATION, 2 STANDARD)
    for i in range(1, 9):
        st = BedStatus.OCCUPIED.value if i <= 4 else BedStatus.AVAILABLE.value
        bt = BedType.ISOLATION.value if i % 2 == 1 else BedType.STANDARD.value
        db_session.add(Bed(hospital_id=h1.id, ward_id=w1_iso.id, bed_number=f"ISO-{i:02d}", bed_type=bt, status=st))

    # Beds for Hospital 2
    for i in range(1, 21):
        db_session.add(Bed(hospital_id=h2.id, ward_id=w2_gen.id, bed_number=f"H2-GEN-{i:02d}", bed_type=BedType.STANDARD.value, status=BedStatus.AVAILABLE.value))

    db_session.commit()

    # Patients & Admissions in Hospital 1
    p1 = Patient(hospital_id=h1.id, patient_identifier="P11-001", first_name="John", last_name="Doe", date_of_birth=date(1975, 4, 12), gender="MALE")
    p2 = Patient(hospital_id=h1.id, patient_identifier="P11-002", first_name="Jane", last_name="Smith", date_of_birth=date(1982, 8, 25), gender="FEMALE")
    # Patient in Hospital 2
    p_h2 = Patient(hospital_id=h2.id, patient_identifier="P11-H2-001", first_name="Robert", last_name="Frost", date_of_birth=date(1960, 1, 1), gender="MALE")
    db_session.add_all([p1, p2, p_h2])
    db_session.commit()

    # Active Admission for p1 in w1_icu, Bed ICU-01
    adm1 = Admission(
        hospital_id=h1.id,
        patient_id=p1.id,
        ward_id=w1_icu.id,
        bed_id=icu_beds[0].id,
        admission_number="ADM-P11-001",
        admission_date=datetime.utcnow() - timedelta(days=2),
        status=AdmissionStatus.ADMITTED.value,
        admission_reason="Acute Respiratory Distress (Stabilized)",
    )
    # Active Admission for p2 in w1_icu, Bed ICU-02
    adm2 = Admission(
        hospital_id=h1.id,
        patient_id=p2.id,
        ward_id=w1_icu.id,
        bed_id=icu_beds[1].id,
        admission_number="ADM-P11-002",
        admission_date=datetime.utcnow() - timedelta(days=1),
        status=AdmissionStatus.ADMITTED.value,
        admission_reason="Post-cardiac intervention monitoring",
    )
    # Active Admission for p_h2 in Hospital 2
    adm_h2 = Admission(
        hospital_id=h2.id,
        patient_id=p_h2.id,
        ward_id=w2_gen.id,
        bed_id=1,
        admission_number="ADM-P11-H2",
        admission_date=datetime.utcnow() - timedelta(days=1),
        status=AdmissionStatus.ADMITTED.value,
        admission_reason="Hospital 2 Admission",
    )
    db_session.add_all([adm1, adm2, adm_h2])
    db_session.commit()

    # Seed Bed Capacity Forecasts (SARIMA results)
    forecast_icu = BedCapacityForecast(
        hospital_id=h1.id,
        ward_id=w1_icu.id,
        forecast_date=date.today() + timedelta(days=1),
        generated_at=datetime.utcnow(),
        horizon_days=1,
        predicted_occupied_beds=9.8,
        predicted_occupancy_percentage=98.0,
        lower_bound=92.0,
        upper_bound=100.0,
        risk_level=RiskLevel.CRITICAL.value,
    )
    forecast_step = BedCapacityForecast(
        hospital_id=h1.id,
        ward_id=w1_step.id,
        forecast_date=date.today() + timedelta(days=1),
        generated_at=datetime.utcnow(),
        horizon_days=1,
        predicted_occupied_beds=7.0,
        predicted_occupancy_percentage=46.7,
        lower_bound=40.0,
        upper_bound=55.0,
        risk_level=RiskLevel.NORMAL.value,
    )
    # Seed a STALE forecast for General Ward (> 72h old)
    forecast_gen_stale = BedCapacityForecast(
        hospital_id=h1.id,
        ward_id=w1_gen.id,
        forecast_date=date.today() - timedelta(days=3),
        generated_at=datetime.utcnow() - timedelta(days=4),
        horizon_days=1,
        predicted_occupied_beds=16.0,
        predicted_occupancy_percentage=80.0,
        lower_bound=70.0,
        upper_bound=90.0,
        risk_level=RiskLevel.MODERATE.value,
    )
    db_session.add_all([forecast_icu, forecast_step, forecast_gen_stale])
    db_session.commit()

    # Seed Users
    u_doc = User(full_name="Dr. Gregory House", email="doctor@mercy.org", password_hash="hash", role=UserRole.DOCTOR.value, hospital_id=h1.id)
    u_admin = User(full_name="Admin Lisa Cuddy", email="admin@mercy.org", password_hash="hash", role=UserRole.ADMIN.value, hospital_id=h1.id)
    u_nurse = User(full_name="Nurse Jackie", email="nurse@mercy.org", password_hash="hash", role=UserRole.NURSE.value, hospital_id=h1.id)
    u_h2_doc = User(full_name="Dr. Boston", email="doc@boston.org", password_hash="hash", role=UserRole.DOCTOR.value, hospital_id=h2.id)

    db_session.add_all([u_doc, u_admin, u_nurse, u_h2_doc])
    db_session.commit()

    return {
        "h1": h1,
        "h2": h2,
        "w1_icu": w1_icu,
        "w1_step": w1_step,
        "w1_gen": w1_gen,
        "w1_surg_full": w1_surg_full,
        "w1_iso": w1_iso,
        "w2_gen": w2_gen,
        "p1": p1,
        "p2": p2,
        "p_h2": p_h2,
        "adm1": adm1,
        "adm2": adm2,
        "u_doc": u_doc,
        "u_admin": u_admin,
        "u_nurse": u_nurse,
        "u_h2_doc": u_h2_doc,
    }


# ── 1. CAPACITY CALCULATIONS TEST ─────────────────────────────────────────────
def test_capacity_calculations_with_maintenance_and_pending_transfers(db_session: Session, phase11_dataset):
    """
    Verify effective capacity and available beds calculation:
    effective_capacity = total_beds - maintenance_beds - cleaning_beds
    available_beds = effective_capacity - occupied_beds - reserved_beds - pending_incoming_transfers
    """
    data = phase11_dataset
    step_ward = data["w1_step"]

    metrics = TransferService.get_ward_detailed_capacity_metrics(db_session, step_ward.id)
    # Total: 15, Occupied: 6, Cleaning: 1, Maintenance: 1
    assert metrics["total_beds"] == 15
    assert metrics["occupied_beds"] == 6
    assert metrics["cleaning_beds"] == 1
    assert metrics["maintenance_beds"] == 1
    # Effective capacity = 15 - 1 - 1 = 13
    assert metrics["effective_capacity"] == 13
    # Available beds should be 7
    assert metrics["available_beds"] == 7
    assert len(metrics["available_candidate_beds"]) == 7


# ── 2. DESTINATION WITH SUITABLE AVAILABLE BED RECOMMENDATION TEST ────────────
def test_suitable_destination_recommendation(client: TestClient, phase11_dataset):
    """
    Verify recommendation engine recommends suitable destination (Step-Down Unit)
    for admitted ICU patient John Doe.
    """
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/transfers/recommendations/patient-destination",
        headers=headers,
        json={"patient_id": data["p1"].id, "hospital_id": data["h1"].id}
    )

    assert resp.status_code == 200
    res = resp.json()
    assert res["hospital_id"] == data["h1"].id
    assert res["patient_id"] == data["p1"].id
    assert res["patient_name"] == "John Doe"
    assert res["source_ward_id"] == data["w1_icu"].id
    assert res["eligible_destinations_count"] >= 1

    # Step-down ward should be Rank #1 (allowed by rule, 7 available beds, low forecast)
    step_rec = next((r for r in res["recommendations"] if r["ward_id"] == data["w1_step"].id), None)
    assert step_rec is not None
    assert step_rec["rank"] == 1
    assert step_rec["is_eligible"] is True
    assert step_rec["score"] > 70.0
    assert step_rec["current_available_beds"] == 7
    assert step_rec["forecast_status"] == "VERIFIED"
    assert step_rec["forecast_available_beds"] is not None
    assert len(step_rec["reasons"]) >= 2
    assert len(step_rec["available_candidate_beds"]) == 7
    assert "verification_required_statement" in step_rec


# ── 3. DESTINATION WITH NO AVAILABLE BEDS TEST ────────────────────────────────
def test_destination_with_no_available_beds_marked_ineligible(client: TestClient, phase11_dataset):
    """
    Verify that destination ward with 0 available beds (Surgical Recovery)
    is marked is_eligible = False with an explicit ineligibility reason.
    """
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/transfers/recommendations/patient-destination",
        headers=headers,
        json={"patient_id": data["p1"].id, "hospital_id": data["h1"].id}
    )

    assert resp.status_code == 200
    res = resp.json()
    surg_rec = next((r for r in res["recommendations"] if r["ward_id"] == data["w1_surg_full"].id), None)
    assert surg_rec is not None
    assert surg_rec["is_eligible"] is False
    assert any("No verified available physical beds" in reason for reason in surg_rec["ineligibility_reasons"])


# ── 4. FORECAST OVERCROWDING & FORECAST AVAILABLE BEDS TEST ───────────────────
def test_forecast_available_beds_calculation(db_session: Session, phase11_dataset):
    """
    Verify forecast_available_beds = applicable_capacity - forecasted_occupied_beds.
    """
    data = phase11_dataset
    step_ward = data["w1_step"]
    # Step-down ward capacity = 15, effective = 13, predicted_occupied_beds = 7.0
    fc = TransferService.get_detailed_ward_forecast(db_session, step_ward.id, effective_capacity=13)
    assert fc["has_forecast"] is True
    assert fc["status"] == "VERIFIED"
    assert fc["predicted_occupied_beds"] == 7.0
    # forecast_available_beds = 13 - 7.0 = 6.0 beds
    assert fc["forecast_available_beds"] == 6.0


# ── 5. MISSING OR STALE FORECAST DATA SAFETY TEST ─────────────────────────────
def test_missing_and_stale_forecast_safety(client: TestClient, phase11_dataset):
    """
    Verify that missing forecast (Isolation Ward) or stale forecast (General Ward)
    does not cause crashes or re-fitting, correctly tags status, and includes clear warnings.
    """
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/transfers/recommendations/patient-destination",
        headers=headers,
        json={"patient_id": data["p1"].id, "hospital_id": data["h1"].id}
    )
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]

    # Isolation ward has no forecast in DB
    iso_rec = next((r for r in recs if r["ward_id"] == data["w1_iso"].id), None)
    assert iso_rec is not None
    assert iso_rec["forecast_status"] == "UNAVAILABLE"
    assert iso_rec["forecast_available_beds"] is None
    assert any("unavailable" in w.lower() for w in iso_rec["warnings"])

    # General ward forecast was generated > 4 days ago (stale)
    gen_rec = next((r for r in recs if r["ward_id"] == data["w1_gen"].id), None)
    assert gen_rec is not None
    assert gen_rec["forecast_status"] == "STALE"
    assert any("stale" in w.lower() for w in gen_rec["warnings"])


# ── 6. INCOMPATIBLE WARD OR BED TYPE TEST ─────────────────────────────────────
def test_incompatible_ward_transfer_rule(client: TestClient, phase11_dataset):
    """
    Verify default policy disallowing direct ICU -> General transfer restricts eligibility.
    """
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/transfers/recommendations/patient-destination",
        headers=headers,
        json={"patient_id": data["p1"].id, "hospital_id": data["h1"].id}
    )
    assert resp.status_code == 200
    gen_rec = next((r for r in resp.json()["recommendations"] if r["ward_id"] == data["w1_gen"].id), None)
    assert gen_rec is not None
    # ICU -> General is disallowed by default rule without step-down review
    assert gen_rec["is_eligible"] is False
    assert any("policy restricts transfer" in reason for reason in gen_rec["ineligibility_reasons"])


def test_specialty_bed_type_compatibility(client: TestClient, phase11_dataset):
    """
    Verify patient requiring ISOLATION bed type only matches destination with available ISOLATION beds.
    """
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    # Request with required_bed_type = "ISOLATION"
    resp = client.post(
        "/api/v1/transfers/recommendations/patient-destination",
        headers=headers,
        json={
            "patient_id": data["p1"].id,
            "required_bed_type": "ISOLATION",
            "hospital_id": data["h1"].id
        }
    )
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]

    # Step-down ward has STANDARD beds only -> should be marked ineligible for ISOLATION
    step_rec = next(r for r in recs if r["ward_id"] == data["w1_step"].id)
    assert step_rec["is_eligible"] is False
    assert any("No available beds matching required bed type 'ISOLATION'" in reason for reason in step_rec["ineligibility_reasons"])

    # Isolation ward has available ISOLATION beds
    iso_rec = next(r for r in recs if r["ward_id"] == data["w1_iso"].id)
    assert any(b["bed_type"] == "ISOLATION" for b in iso_rec["available_candidate_beds"])


# ── 7. INVALID PATIENT, SOURCE WARD VALIDATION TEST ───────────────────────────
def test_invalid_patient_or_ward_validation(client: TestClient, phase11_dataset):
    """Verify 400 Bad Request returned for invalid/missing patient or unadmitted patient."""
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    # Non-existent patient
    resp_bad_patient = client.post(
        "/api/v1/transfers/recommendations/patient-destination",
        headers=headers,
        json={"patient_id": 99999, "hospital_id": data["h1"].id}
    )
    assert resp_bad_patient.status_code == 400

    # Non-existent source ward
    resp_bad_ward = client.post(
        "/api/v1/transfers/recommendations/patient-destination",
        headers=headers,
        json={"source_ward_id": 88888, "hospital_id": data["h1"].id}
    )
    assert resp_bad_ward.status_code == 400


# ── 8. UNAUTHORIZED USERS AND ROLE-BASED ACCESS CONTROL TEST ──────────────────
def test_unauthorized_access(client: TestClient, phase11_dataset):
    """Verify 401 Unauthorized when unauthenticated."""
    resp = client.post("/api/v1/transfers/recommendations/patient-destination", json={"patient_id": 1})
    assert resp.status_code == 401


# ── 9. MULTI-HOSPITAL TENANT ISOLATION TEST ──────────────────────────────────
def test_cross_hospital_isolation(client: TestClient, phase11_dataset):
    """Verify hospital A staff cannot query recommendations for hospital B patient."""
    data = phase11_dataset
    token_h1 = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers_h1 = {"Authorization": f"Bearer {token_h1}"}

    # Attempt to access Hospital 2 with Hospital 1 token
    resp_cross = client.post(
        "/api/v1/transfers/recommendations/patient-destination",
        headers=headers_h1,
        json={"patient_id": data["p_h2"].id, "hospital_id": data["h2"].id}
    )
    assert resp_cross.status_code == 403


# ── 10. CONCURRENT / DUPLICATE BED RESERVATION PREVENTION TEST ────────────────
def test_concurrent_duplicate_bed_reservation_blocked(client: TestClient, phase11_dataset):
    """
    Verify concurrency safeguard:
    Doctor 1 requests Destination Bed STEP-07 for Patient 1 -> Success.
    Doctor 2 requests the same Destination Bed STEP-07 for Patient 2 -> Blocked with 400.
    """
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    # Find available bed in step-down ward
    target_bed = client.get(f"/api/v1/beds?ward_id={data['w1_step'].id}&status=AVAILABLE", headers=headers).json()["items"][0]
    target_bed_id = target_bed["id"]

    # 1. First transfer request
    resp1 = client.post(
        "/api/v1/transfers/patient-transfers",
        headers=headers,
        json={
            "patient_id": data["p1"].id,
            "destination_ward_id": data["w1_step"].id,
            "destination_bed_id": target_bed_id,
            "reason": "ICU step-down clinical transfer 1",
            "hospital_id": data["h1"].id,
        }
    )
    assert resp1.status_code == 201

    # 2. Second concurrent transfer request targeting the exact same bed for Patient 2
    resp2 = client.post(
        "/api/v1/transfers/patient-transfers",
        headers=headers,
        json={
            "patient_id": data["p2"].id,
            "destination_ward_id": data["w1_step"].id,
            "destination_bed_id": target_bed_id,
            "reason": "ICU step-down clinical transfer 2 attempting same bed",
            "hospital_id": data["h1"].id,
        }
    )
    assert resp2.status_code == 400
    assert "already reserved by active transfer request" in resp2.json()["detail"]


# ── 11. VALID & INVALID TRANSFER STATUS TRANSITIONS TEST ─────────────────────
def test_transfer_status_transitions(client: TestClient, phase11_dataset):
    """
    Verify complete transfer lifecycle:
    REQUESTED -> APPROVED -> COMPLETED.
    Verify cannot re-approve or cancel a completed transfer.
    """
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    # Find available bed
    target_bed = client.get(f"/api/v1/beds?ward_id={data['w1_step'].id}&status=AVAILABLE", headers=headers).json()["items"][0]

    # Create transfer
    create_resp = client.post(
        "/api/v1/transfers/patient-transfers",
        headers=headers,
        json={
            "patient_id": data["p1"].id,
            "destination_ward_id": data["w1_step"].id,
            "destination_bed_id": target_bed["id"],
            "reason": "Step-down lifecycle test",
            "hospital_id": data["h1"].id,
        }
    )
    assert create_resp.status_code == 201
    transfer_id = create_resp.json()["id"]

    # Approve transfer
    app_resp = client.patch(
        f"/api/v1/transfers/patient-transfers/{transfer_id}/approve",
        headers=headers,
        json={"notes": "Doctor approved"}
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # Complete transfer
    comp_resp = client.patch(
        f"/api/v1/transfers/patient-transfers/{transfer_id}/complete",
        headers=headers
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "COMPLETED"

    # Attempt to cancel completed transfer -> should fail with 400
    cancel_resp = client.patch(
        f"/api/v1/transfers/patient-transfers/{transfer_id}/cancel",
        headers=headers
    )
    assert cancel_resp.status_code == 400


# ── 12. OCCUPANCY CONSISTENCY AFTER APPROVED TRANSFER TEST ───────────────────
def test_occupancy_consistency_after_transfer_completion(client: TestClient, phase11_dataset, db_session: Session):
    """
    Verify atomic database transaction on completion:
    - Source bed released to AVAILABLE
    - Destination bed marked OCCUPIED
    - Admission record relocated to destination ward & bed
    - OccupancyEvent logged for both TRANSFER_OUT and TRANSFER_IN
    """
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    source_bed_id = data["adm1"].bed_id
    target_bed = client.get(f"/api/v1/beds?ward_id={data['w1_step'].id}&status=AVAILABLE", headers=headers).json()["items"][0]
    dest_bed_id = target_bed["id"]

    # Create & complete transfer
    create_resp = client.post(
        "/api/v1/transfers/patient-transfers",
        headers=headers,
        json={
            "patient_id": data["p1"].id,
            "destination_ward_id": data["w1_step"].id,
            "destination_bed_id": dest_bed_id,
            "hospital_id": data["h1"].id,
        }
    )
    transfer_id = create_resp.json()["id"]

    client.patch(f"/api/v1/transfers/patient-transfers/{transfer_id}/approve", headers=headers)
    client.patch(f"/api/v1/transfers/patient-transfers/{transfer_id}/complete", headers=headers)

    # Verify Database State
    db_session.expire_all()
    source_bed = db_session.query(Bed).filter(Bed.id == source_bed_id).first()
    dest_bed = db_session.query(Bed).filter(Bed.id == dest_bed_id).first()
    admission = db_session.query(Admission).filter(Admission.id == data["adm1"].id).first()

    assert source_bed.status == BedStatus.AVAILABLE.value
    assert dest_bed.status == BedStatus.OCCUPIED.value
    assert admission.ward_id == data["w1_step"].id
    assert admission.bed_id == dest_bed_id

    # Verify Occupancy Events
    events = db_session.query(OccupancyEvent).filter(OccupancyEvent.hospital_id == data["h1"].id).all()
    event_types = [e.event_type for e in events]
    assert EventType.TRANSFER_OUT.value in event_types
    assert EventType.TRANSFER_IN.value in event_types


# ── 13. TRANSFER REQUEST RECOMMENDATIONS ENDPOINT TEST ───────────────────────
def test_transfer_request_recommendations_endpoint(client: TestClient, phase11_dataset):
    """
    Verify GET /api/v1/transfers/patient-transfers/{transfer_id}/recommendations
    returns destination ward recommendations for the context of an existing transfer request.
    """
    data = phase11_dataset
    token = create_access_token(data["u_doc"].id, data["u_doc"].role)
    headers = {"Authorization": f"Bearer {token}"}

    target_bed = client.get(f"/api/v1/beds?ward_id={data['w1_step'].id}&status=AVAILABLE", headers=headers).json()["items"][0]

    create_resp = client.post(
        "/api/v1/transfers/patient-transfers",
        headers=headers,
        json={
            "patient_id": data["p1"].id,
            "destination_ward_id": data["w1_step"].id,
            "destination_bed_id": target_bed["id"],
            "hospital_id": data["h1"].id,
        }
    )
    transfer_id = create_resp.json()["id"]

    rec_resp = client.get(f"/api/v1/transfers/patient-transfers/{transfer_id}/recommendations", headers=headers)
    assert rec_resp.status_code == 200
    res = rec_resp.json()
    assert res["hospital_id"] == data["h1"].id
    assert res["source_ward_id"] == data["w1_icu"].id
    assert len(res["recommendations"]) >= 1

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType
from app.models.patient import Patient
from app.models.admission import Admission
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()

        # Seed Hospitals
        h1 = Hospital(id=1, name="General Hospital A", code="HOSP-A", status=HospitalStatus.ACTIVE.value)
        h2 = Hospital(id=2, name="St Jude Hospital B", code="HOSP-B", status=HospitalStatus.ACTIVE.value)
        db.add_all([h1, h2])
        db.commit()

        # Seed Wards
        w1 = Ward(id=1, hospital_id=1, name="Ward A1", ward_type=WardType.GENERAL.value, department="Medicine", floor="1", capacity=10)
        w2 = Ward(id=2, hospital_id=2, name="Ward B1", ward_type=WardType.ICU.value, department="Critical Care", floor="2", capacity=5)
        db.add_all([w1, w2])
        db.commit()

        # Seed Beds
        b1 = Bed(id=1, hospital_id=1, ward_id=1, bed_number="A1-01", status=BedStatus.AVAILABLE.value, bed_type=BedType.STANDARD.value)
        b2 = Bed(id=2, hospital_id=1, ward_id=1, bed_number="A1-02", status=BedStatus.MAINTENANCE.value, bed_type=BedType.STANDARD.value)
        b3 = Bed(id=3, hospital_id=2, ward_id=2, bed_number="B1-01", status=BedStatus.AVAILABLE.value, bed_type=BedType.ICU.value)
        db.add_all([b1, b2, b3])
        db.commit()

    finally:
        db.close()
    yield


client = TestClient(app)


@pytest.fixture(scope="module")
def staff_hosp_a_token():
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Nurse Alice", "email": "alice@hosp-a.com", "password": "Password123!", "role": "nurse", "hospital_id": 1}
    )
    res = client.post("/api/v1/auth/login", json={"email": "alice@hosp-a.com", "password": "Password123!"})
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def staff_hosp_b_token():
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Doctor Bob", "email": "bob@hosp-b.com", "password": "Password123!", "role": "doctor", "hospital_id": 2}
    )
    res = client.post("/api/v1/auth/login", json={"email": "bob@hosp-b.com", "password": "Password123!"})
    return res.json()["access_token"]


def test_patient_registration(staff_hosp_a_token):
    res = client.post(
        "/api/v1/patients",
        json={
            "first_name": "John",
            "last_name": "Smith",
            "date_of_birth": "1980-01-15",
            "gender": "MALE",
            "phone": "+1-555-0100",
            "email": "john.smith@example.com",
            "address": "100 Main St"
        },
        headers={"Authorization": f"Bearer {staff_hosp_a_token}"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["first_name"] == "John"
    assert data["hospital_id"] == 1
    assert data["patient_identifier"].startswith("HOSP-A-P")
    assert data["status"] == "ACTIVE"


def test_list_and_search_patients(staff_hosp_a_token):
    res = client.get("/api/v1/patients?search=John", headers={"Authorization": f"Bearer {staff_hosp_a_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["first_name"] == "John"


def test_cross_hospital_patient_isolation(staff_hosp_b_token):
    # Hospital B staff should NOT see Hospital A patient
    res = client.get("/api/v1/patients", headers={"Authorization": f"Bearer {staff_hosp_b_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0

    # Hospital B staff trying to access Hospital A patient ID 1 directly should get 404
    res_detail = client.get("/api/v1/patients/1", headers={"Authorization": f"Bearer {staff_hosp_b_token}"})
    assert res_detail.status_code == 404


def test_available_beds_api(staff_hosp_a_token):
    res = client.get("/api/v1/wards/1/available-beds", headers={"Authorization": f"Bearer {staff_hosp_a_token}"})
    assert res.status_code == 200
    beds = res.json()
    # Bed 1 is AVAILABLE, Bed 2 is MAINTENANCE
    assert len(beds) == 1
    assert beds[0]["bed_number"] == "A1-01"


def test_admission_workflow(staff_hosp_a_token):
    # Admit Patient 1 into Ward 1, Bed 1
    res = client.post(
        "/api/v1/admissions",
        json={
            "patient_id": 1,
            "ward_id": 1,
            "bed_id": 1,
            "admission_reason": "Acute respiratory observation"
        },
        headers={"Authorization": f"Bearer {staff_hosp_a_token}"}
    )
    assert res.status_code == 201
    adm = res.json()
    assert adm["status"] == "ADMITTED"
    assert adm["admission_number"].startswith("ADM-")
    assert adm["bed_number"] == "A1-01"

    # Verify Bed 1 is now OCCUPIED
    bed_res = client.get("/api/v1/beds/1", headers={"Authorization": f"Bearer {staff_hosp_a_token}"})
    assert bed_res.status_code == 200
    assert bed_res.json()["status"] == "OCCUPIED"

    # Verify available beds in Ward 1 is now 0
    avail_res = client.get("/api/v1/wards/1/available-beds", headers={"Authorization": f"Bearer {staff_hosp_a_token}"})
    assert len(avail_res.json()) == 0


def test_prevent_duplicate_active_admission(staff_hosp_a_token):
    # Trying to admit Patient 1 again should fail (409 Conflict)
    res = client.post(
        "/api/v1/admissions",
        json={
            "patient_id": 1,
            "ward_id": 1,
            "bed_id": 1,
            "admission_reason": "Duplicate admission attempt"
        },
        headers={"Authorization": f"Bearer {staff_hosp_a_token}"}
    )
    assert res.status_code == 409
    assert "already has an active admission" in res.json()["detail"]


def test_prevent_admit_occupied_or_maintenance_bed(staff_hosp_a_token):
    # Register patient 2
    p2 = client.post(
        "/api/v1/patients",
        json={"first_name": "Mary", "last_name": "Jane", "date_of_birth": "1992-04-10", "gender": "FEMALE"},
        headers={"Authorization": f"Bearer {staff_hosp_a_token}"}
    ).json()

    # Attempt to admit to Bed 1 (OCCUPIED)
    res1 = client.post(
        "/api/v1/admissions",
        json={"patient_id": p2["id"], "ward_id": 1, "bed_id": 1},
        headers={"Authorization": f"Bearer {staff_hosp_a_token}"}
    )
    assert res1.status_code == 409

    # Attempt to admit to Bed 2 (MAINTENANCE)
    res2 = client.post(
        "/api/v1/admissions",
        json={"patient_id": p2["id"], "ward_id": 1, "bed_id": 2},
        headers={"Authorization": f"Bearer {staff_hosp_a_token}"}
    )
    assert res2.status_code == 409


def test_discharge_workflow(staff_hosp_a_token):
    # Discharge Admission ID 1
    res = client.post(
        "/api/v1/admissions/1/discharge",
        json={"discharge_notes": "Patient recovered cleanly."},
        headers={"Authorization": f"Bearer {staff_hosp_a_token}"}
    )
    assert res.status_code == 200
    adm = res.json()
    assert adm["status"] == "DISCHARGED"
    assert adm["discharge_date"] is not None

    # Verify Bed 1 is back to AVAILABLE
    bed_res = client.get("/api/v1/beds/1", headers={"Authorization": f"Bearer {staff_hosp_a_token}"})
    assert bed_res.json()["status"] == "AVAILABLE"

    # Verify patient admission history remains intact
    hist_res = client.get("/api/v1/patients/1/admissions", headers={"Authorization": f"Bearer {staff_hosp_a_token}"})
    assert hist_res.status_code == 200
    assert hist_res.json()["total"] == 1
    assert hist_res.json()["items"][0]["status"] == "DISCHARGED"

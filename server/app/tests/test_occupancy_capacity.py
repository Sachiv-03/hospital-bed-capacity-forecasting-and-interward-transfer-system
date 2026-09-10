import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType
from app.main import app
from app.schemas.capacity import get_capacity_status, CapacityStatusEnum

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

        # Hosp A & Hosp B
        h1 = Hospital(id=1, name="Hospital A", code="HOSP-A", status=HospitalStatus.ACTIVE.value)
        h2 = Hospital(id=2, name="Hospital B", code="HOSP-B", status=HospitalStatus.ACTIVE.value)
        db.add_all([h1, h2])
        db.commit()

        # Ward A in Hosp A
        ward_a = Ward(id=1, hospital_id=1, name="ICU A", ward_type=WardType.ICU.value, department="Critical Care", floor="3", capacity=10, status=WardStatus.ACTIVE.value)
        # Ward B in Hosp B
        ward_b = Ward(id=2, hospital_id=2, name="ICU B", ward_type=WardType.ICU.value, department="Critical Care", floor="2", capacity=5, status=WardStatus.ACTIVE.value)
        db.add_all([ward_a, ward_b])
        db.commit()

        # Beds in Ward A (Total 10: 4 OCCUPIED, 4 AVAILABLE, 1 MAINTENANCE, 1 INACTIVE)
        for i in range(1, 5):
            b = Bed(ward_id=1, hospital_id=1, bed_number=f"ICU-A-0{i}", bed_type=BedType.ICU.value, status=BedStatus.OCCUPIED.value)
            db.add(b)
        for i in range(5, 9):
            b = Bed(ward_id=1, hospital_id=1, bed_number=f"ICU-A-0{i}", bed_type=BedType.ICU.value, status=BedStatus.AVAILABLE.value)
            db.add(b)
        db.add(Bed(ward_id=1, hospital_id=1, bed_number="ICU-A-09", bed_type=BedType.ICU.value, status=BedStatus.MAINTENANCE.value))
        db.add(Bed(ward_id=1, hospital_id=1, bed_number="ICU-A-10", bed_type=BedType.ICU.value, status="INACTIVE"))
        db.commit()
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(scope="module")
def staff_hosp_a_headers():
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Doctor Alice", "email": "alice@hosp-a.com", "password": "Password123!", "role": "doctor", "hospital_id": 1}
    )
    res = client.post("/api/v1/auth/login", json={"email": "alice@hosp-a.com", "password": "Password123!"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_hosp_a_headers():
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Admin Alex", "email": "admin@hosp-a.com", "password": "Password123!", "role": "admin", "hospital_id": 1}
    )
    res = client.post("/api/v1/auth/login", json={"email": "admin@hosp-a.com", "password": "Password123!"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def staff_hosp_b_headers():
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Doctor Bob", "email": "bob@hosp-b.com", "password": "Password123!", "role": "doctor", "hospital_id": 2}
    )
    res = client.post("/api/v1/auth/login", json={"email": "bob@hosp-b.com", "password": "Password123!"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_capacity_status_thresholds():
    """Verify threshold classification function."""
    assert get_capacity_status(0.0) == CapacityStatusEnum.NORMAL
    assert get_capacity_status(69.9) == CapacityStatusEnum.NORMAL
    assert get_capacity_status(70.0) == CapacityStatusEnum.WARNING
    assert get_capacity_status(84.9) == CapacityStatusEnum.WARNING
    assert get_capacity_status(85.0) == CapacityStatusEnum.HIGH
    assert get_capacity_status(94.9) == CapacityStatusEnum.HIGH
    assert get_capacity_status(95.0) == CapacityStatusEnum.CRITICAL
    assert get_capacity_status(100.0) == CapacityStatusEnum.CRITICAL


def test_occupancy_formulas_and_endpoints(staff_hosp_a_headers):
    """Test operational beds formula (Occupied + Available) and capacity endpoints."""
    # GET /api/v1/occupancy/hospital
    res = client.get("/api/v1/occupancy/hospital", headers=staff_hosp_a_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_beds"] == 10
    # Operational = 4 Occupied + 4 Available = 8
    assert data["operational_beds"] == 8
    assert data["occupied_beds"] == 4
    assert data["available_beds"] == 4
    assert data["maintenance_beds"] == 1
    assert data["inactive_beds"] == 1
    # Occupancy = 4 / 8 * 100 = 50.0%
    assert data["occupancy_percentage"] == 50.0
    # Available capacity = 4 / 8 * 100 = 50.0%
    assert data["available_capacity_percentage"] == 50.0
    assert data["status"] == "NORMAL"


def test_occupancy_summary_endpoint(staff_hosp_a_headers):
    """Test complete command summary endpoint."""
    res = client.get("/api/v1/occupancy/summary", headers=staff_hosp_a_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["hospital_id"] == 1
    assert data["total_beds"] == 10
    assert data["operational_beds"] == 8
    assert data["occupancy_percentage"] == 50.0
    assert data["capacity_status"] == "NORMAL"


def test_snapshot_creation_and_trends(admin_hosp_a_headers):
    """Test POST /api/v1/occupancy/snapshots and GET /api/v1/occupancy/trends."""
    # Create snapshot
    res = client.post("/api/v1/occupancy/snapshots", headers=admin_hosp_a_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["snapshots_created"] >= 1

    # Fetch trends
    res_trends = client.get("/api/v1/occupancy/trends", headers=admin_hosp_a_headers)
    assert res_trends.status_code == 200


def test_multi_hospital_occupancy_isolation(staff_hosp_b_headers):
    """Ensure Hospital B staff cannot request Hospital A occupancy data."""
    res = client.get("/api/v1/occupancy/hospital?hospital_id=1", headers=staff_hosp_b_headers)
    assert res.status_code == 403

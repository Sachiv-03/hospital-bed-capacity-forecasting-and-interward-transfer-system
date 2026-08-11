import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.models.hospital import Hospital, HospitalStatus
from app.main import app

# In-memory SQLite with StaticPool for thread-safe test isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()

        # Seed default initial hospital facility for ward tests
        h1 = Hospital(name="Apollo Medical Center", code="H001", city="Metropolis", status=HospitalStatus.ACTIVE.value)
        db.add(h1)
        db.commit()
    finally:
        db.close()
    yield


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(scope="module")
def admin_token():
    # Register admin user
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Admin User",
            "email": "admin.wardtest@hospital.com",
            "password": "AdminPassword123!",
            "role": "admin",
        },
    )
    # Login admin
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.wardtest@hospital.com", "password": "AdminPassword123!"},
    )
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def doctor_token():
    # Register doctor user
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Dr. Doctor User",
            "email": "doctor.wardtest@hospital.com",
            "password": "DoctorPassword123!",
            "role": "doctor",
        },
    )
    # Login doctor
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "doctor.wardtest@hospital.com", "password": "DoctorPassword123!"},
    )
    return res.json()["access_token"]


def test_create_ward_admin(admin_token):
    res = client.post(
        "/api/v1/wards",
        json={
            "name": "Cardiac Care Unit 1",
            "ward_type": "ICU",
            "department": "Cardiology",
            "floor": "Floor 3",
            "capacity": 20,
            "description": "High dependence cardiac monitoring ward.",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Cardiac Care Unit 1"
    assert data["capacity"] == 20
    assert data["status"] == "ACTIVE"
    assert "id" in data


def test_create_ward_invalid_capacity(admin_token):
    res = client.post(
        "/api/v1/wards",
        json={
            "name": "Invalid Capacity Ward",
            "ward_type": "GENERAL",
            "department": "General",
            "floor": "Floor 1",
            "capacity": 0,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 422


def test_create_ward_forbidden_for_doctor(doctor_token):
    res = client.post(
        "/api/v1/wards",
        json={
            "name": "Doctor Created Ward",
            "ward_type": "GENERAL",
            "department": "General",
            "floor": "Floor 1",
            "capacity": 10,
        },
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert res.status_code == 403


def test_get_ward_by_id(doctor_token):
    res = client.get("/api/v1/wards/1", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 1
    assert data["name"] == "Cardiac Care Unit 1"


def test_get_ward_not_found(doctor_token):
    res = client.get("/api/v1/wards/9999", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res.status_code == 404


def test_list_and_search_wards(doctor_token):
    res = client.get(
        "/api/v1/wards?search=Cardiac&ward_type=ICU",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert data["items"][0]["name"] == "Cardiac Care Unit 1"


def test_update_ward_admin(admin_token):
    res = client.put(
        "/api/v1/wards/1",
        json={
            "capacity": 25,
            "description": "Updated cardiac monitoring description.",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["capacity"] == 25
    assert data["description"] == "Updated cardiac monitoring description."


def test_deactivate_ward_admin(admin_token, doctor_token):
    # Deactivate ward
    res = client.delete("/api/v1/wards/1", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "INACTIVE"

    # Verify doctor can still view ward details with INACTIVE status
    view_res = client.get("/api/v1/wards/1", headers={"Authorization": f"Bearer {doctor_token}"})
    assert view_res.status_code == 200
    assert view_res.json()["status"] == "INACTIVE"


def test_get_ward_statistics(doctor_token):
    res = client.get("/api/v1/wards/statistics", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "total_wards" in data
    assert "active_wards" in data
    assert "inactive_wards" in data
    assert "total_capacity" in data

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.main import app
from app.models.hospital import Hospital, HospitalStatus
from app.models.user import User, UserRole
from app.models.ward import Ward

# In-memory SQLite with StaticPool for thread-safe test isolation
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


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()

        # Seed two distinct hospital facilities
        h1 = Hospital(name="Apollo Medical Center", code="H001", city="Metropolis", status=HospitalStatus.ACTIVE.value)
        h2 = Hospital(name="City General Hospital", code="H002", city="Gotham", status=HospitalStatus.ACTIVE.value)
        db.add_all([h1, h2])
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(scope="module")
def super_admin_token():
    # Register Super Admin
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Super Admin System",
            "email": "superadmin@system.com",
            "password": "SuperPassword123!",
            "role": "super_admin",
        },
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@system.com", "password": "SuperPassword123!"},
    )
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def hospital_a_admin_token():
    # Register Admin for Hospital 1 (Apollo)
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Apollo Admin",
            "email": "admin@apollo.com",
            "password": "ApolloPassword123!",
            "role": "admin",
            "hospital_id": 1,
        },
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@apollo.com", "password": "ApolloPassword123!"},
    )
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def hospital_b_admin_token():
    # Register Admin for Hospital 2 (City General)
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "City General Admin",
            "email": "admin@citygeneral.com",
            "password": "CityPassword123!",
            "role": "admin",
            "hospital_id": 2,
        },
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@citygeneral.com", "password": "CityPassword123!"},
    )
    return res.json()["access_token"]


def test_create_wards_for_different_hospitals(hospital_a_admin_token, hospital_b_admin_token):
    # Hospital A Admin creates Ward A
    res_a = client.post(
        "/api/v1/wards",
        json={
            "name": "Apollo ICU",
            "ward_type": "ICU",
            "department": "Critical Care",
            "floor": "Floor 2",
            "capacity": 20,
            "description": "Apollo Intensive Care Unit",
        },
        headers={"Authorization": f"Bearer {hospital_a_admin_token}"},
    )
    assert res_a.status_code == 201
    ward_a = res_a.json()
    assert ward_a["hospital_id"] == 1
    assert ward_a["name"] == "Apollo ICU"

    # Hospital B Admin creates Ward B
    res_b = client.post(
        "/api/v1/wards",
        json={
            "name": "City General ICU",
            "ward_type": "ICU",
            "department": "Emergency Care",
            "floor": "Floor 1",
            "capacity": 15,
            "description": "City General Intensive Care Unit",
        },
        headers={"Authorization": f"Bearer {hospital_b_admin_token}"},
    )
    assert res_b.status_code == 201
    ward_b = res_b.json()
    assert ward_b["hospital_id"] == 2
    assert ward_b["name"] == "City General ICU"


def test_tenant_data_isolation_list(hospital_a_admin_token, hospital_b_admin_token):
    # Hospital A user requests list of wards
    res_a = client.get("/api/v1/wards", headers={"Authorization": f"Bearer {hospital_a_admin_token}"})
    assert res_a.status_code == 200
    data_a = res_a.json()
    ward_names_a = [w["name"] for w in data_a["items"]]
    assert "Apollo ICU" in ward_names_a
    assert "City General ICU" not in ward_names_a

    # Hospital B user requests list of wards
    res_b = client.get("/api/v1/wards", headers={"Authorization": f"Bearer {hospital_b_admin_token}"})
    assert res_b.status_code == 200
    data_b = res_b.json()
    ward_names_b = [w["name"] for w in data_b["items"]]
    assert "City General ICU" in ward_names_b
    assert "Apollo ICU" not in ward_names_b


def test_cross_tenant_access_forbidden(hospital_a_admin_token, hospital_b_admin_token):
    # Get Ward B's ID first using Hospital B token
    res_b_list = client.get("/api/v1/wards", headers={"Authorization": f"Bearer {hospital_b_admin_token}"})
    ward_b_id = res_b_list.json()["items"][0]["id"]

    # Hospital A user attempts to view Hospital B's ward directly by ID
    res_get = client.get(f"/api/v1/wards/{ward_b_id}", headers={"Authorization": f"Bearer {hospital_a_admin_token}"})
    assert res_get.status_code == 404

    # Hospital A user attempts to update Hospital B's ward
    res_put = client.put(
        f"/api/v1/wards/{ward_b_id}",
        json={"capacity": 99},
        headers={"Authorization": f"Bearer {hospital_a_admin_token}"},
    )
    assert res_put.status_code == 404

    # Hospital A user attempts to deactivate Hospital B's ward
    res_del = client.delete(f"/api/v1/wards/{ward_b_id}", headers={"Authorization": f"Bearer {hospital_a_admin_token}"})
    assert res_del.status_code == 404


def test_super_admin_multihospital_access(super_admin_token):
    # Super Admin can view all wards across hospitals
    res_all = client.get("/api/v1/wards", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert res_all.status_code == 200
    all_names = [w["name"] for w in res_all.json()["items"]]
    assert "Apollo ICU" in all_names
    assert "City General ICU" in all_names

    # Super Admin can filter by hospital_id
    res_h1 = client.get("/api/v1/wards?hospital_id=1", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert res_h1.status_code == 200
    h1_names = [w["name"] for w in res_h1.json()["items"]]
    assert "Apollo ICU" in h1_names
    assert "City General ICU" not in h1_names


def test_hospital_management_api(super_admin_token, hospital_a_admin_token):
    # List hospitals (SUPER_ADMIN only)
    res_super = client.get("/api/v1/hospitals", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert res_super.status_code == 200
    assert len(res_super.json()["items"]) >= 2

    # Normal ADMIN cannot list all hospitals
    res_admin = client.get("/api/v1/hospitals", headers={"Authorization": f"Bearer {hospital_a_admin_token}"})
    assert res_admin.status_code == 403

    # Create new hospital with Super Admin
    res_create = client.post(
        "/api/v1/hospitals",
        json={
            "name": "St. Jude Memorial Hospital",
            "code": "H003",
            "city": "Chicago",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res_create.status_code == 201
    assert res_create.json()["code"] == "H003"

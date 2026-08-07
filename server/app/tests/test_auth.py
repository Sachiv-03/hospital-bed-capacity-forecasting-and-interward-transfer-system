import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base, get_db
from app.main import app

# In-memory SQLite for isolated test suite
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_user_registration():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Dr. Alex Rivera",
            "email": "alex.rivera@hospital.com",
            "password": "SecurePassword123!",
            "role": "doctor",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alex.rivera@hospital.com"
    assert data["role"] == "doctor"
    assert "id" in data


def test_duplicate_user_registration():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Dr. Alex Duplicate",
            "email": "alex.rivera@hospital.com",
            "password": "SecurePassword123!",
            "role": "doctor",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_user_login_success():
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "alex.rivera@hospital.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_user_login_invalid_password():
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "alex.rivera@hospital.com",
            "password": "WrongPassword!",
        },
    )
    assert response.status_code == 401


def test_get_current_user_profile():
    # Login to get token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "alex.rivera@hospital.com",
            "password": "SecurePassword123!",
        },
    )
    token = login_resp.json()["access_token"]

    # Fetch profile
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["email"] == "alex.rivera@hospital.com"
    assert data["role"] == "doctor"


def test_token_refresh():
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "alex.rivera@hospital.com",
            "password": "SecurePassword123!",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data

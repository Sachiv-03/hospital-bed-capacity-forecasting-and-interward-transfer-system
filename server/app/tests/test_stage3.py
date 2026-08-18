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
from app.models.bed import Bed, BedStatus
from app.models.user import User, UserRole
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.bed_capacity_forecast import BedCapacityForecast, RiskLevel
from app.services.forecasting.data_preparation import ForecastingDataPreparation
from app.services.forecasting.baseline_model import BaselineForecaster
from app.services.forecasting.time_series_model import TimeSeriesForecaster
from app.services.forecasting.evaluation import ModelEvaluator
from app.services.forecasting.forecast_service import ForecastService
from app.core.security import get_password_hash


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


def test_data_preparation_and_split(db_session: Session):
    h = Hospital(name="Apollo", code="H_APOLLO", city="City", status="ACTIVE")
    db_session.add(h)
    db_session.commit()

    w = Ward(hospital_id=h.id, name="ICU", ward_type="ICU", department="CC", floor="F1", capacity=10, status="ACTIVE")
    db_session.add(w)
    db_session.commit()

    # Seed 10 daily snapshots
    start_d = date(2026, 8, 1)
    for i in range(10):
        d_time = datetime(2026, 8, 1 + i, 12, 0, 0)
        snap = OccupancySnapshot(
            hospital_id=h.id,
            ward_id=w.id,
            snapshot_time=d_time,
            total_beds=10,
            occupied_beds=5 + (i % 3),
            available_beds=5 - (i % 3),
            occupancy_percentage=(5 + (i % 3)) * 10.0,
        )
        db_session.add(snap)
    db_session.commit()

    prep = ForecastingDataPreparation.prepare_ward_series(db_session, ward_id=w.id, hospital_id=h.id)
    assert prep["total_observations"] == 10
    assert len(prep["occupied_beds"]) == 10

    # Chronological split test (no random shuffling)
    tr_d, tr_v, te_d, te_v = ForecastingDataPreparation.train_test_split(prep["dates"], prep["occupied_beds"], train_ratio=0.7)
    assert len(tr_v) + len(te_v) == 10
    assert len(tr_v) >= 7
    assert len(te_v) >= 1


def test_baseline_and_time_series_models():
    history = [5.0, 6.0, 7.0, 6.0, 5.0, 7.0, 8.0, 7.0, 6.0, 7.0]

    # Baseline Model Test
    naive_pred = BaselineForecaster.naive_forecast(history, horizon=7)
    assert len(naive_pred) == 7
    assert naive_pred[0] == 7.0

    ma_pred = BaselineForecaster.moving_average_forecast(history, horizon=7, window=7)
    assert len(ma_pred) == 7

    # Metrics Test
    mae = ModelEvaluator.calculate_mae([7.0, 7.0], [6.0, 8.0])
    assert mae == 1.0

    rmse = ModelEvaluator.calculate_rmse([7.0, 7.0], [6.0, 8.0])
    assert rmse == 1.0

    # Primary SARIMA Model Test
    ts_res = TimeSeriesForecaster.forecast_sarima(history=history, total_beds=10, horizon=7)
    assert ts_res["status"] == "SUCCESS"
    assert len(ts_res["predictions"]) == 7
    for p in ts_res["predictions"]:
        assert 0.0 <= p <= 10.0


def test_insufficient_data_handling(db_session: Session):
    h = Hospital(name="City Gen", code="H_CITY", city="City", status="ACTIVE")
    db_session.add(h)
    db_session.commit()

    w = Ward(hospital_id=h.id, name="General", ward_type="GENERAL", department="Med", floor="F1", capacity=10, status="ACTIVE")
    db_session.add(w)
    db_session.commit()

    # Seed only 3 days (less than 7 minimum required)
    for i in range(3):
        snap = OccupancySnapshot(
            hospital_id=h.id,
            ward_id=w.id,
            snapshot_time=datetime(2026, 8, 1 + i, 12, 0, 0),
            total_beds=10,
            occupied_beds=4,
            available_beds=6,
            occupancy_percentage=40.0,
        )
        db_session.add(snap)
    db_session.commit()

    res = ForecastService.generate_ward_forecast(db_session, ward_id=w.id, hospital_id=h.id, horizon=7, save_to_db=False)
    assert res["status"] == "INSUFFICIENT_DATA"
    assert res["available_observations"] == 3
    assert res["required_observations"] == 7


def test_forecast_api_and_tenant_isolation(client: TestClient, db_session: Session):
    h1 = Hospital(name="Hospital Alpha", code="H_ALPHA", city="City A", status="ACTIVE")
    h2 = Hospital(name="Hospital Beta", code="H_BETA", city="City B", status="ACTIVE")
    db_session.add_all([h1, h2])
    db_session.commit()

    w1 = Ward(hospital_id=h1.id, name="ICU A", ward_type="ICU", department="CC", floor="F1", capacity=10, status="ACTIVE")
    w2 = Ward(hospital_id=h2.id, name="ICU B", ward_type="ICU", department="CC", floor="F1", capacity=10, status="ACTIVE")
    db_session.add_all([w1, w2])
    db_session.commit()

    # Seed history for w1
    for i in range(10):
        db_session.add(OccupancySnapshot(
            hospital_id=h1.id, ward_id=w1.id,
            snapshot_time=datetime(2026, 8, 1 + i, 12, 0, 0),
            total_beds=10, occupied_beds=8, available_beds=2, occupancy_percentage=80.0
        ))
    db_session.commit()

    # Create users
    pwd = get_password_hash("Password123!")
    u1 = User(full_name="User Alpha", email="alpha@hospital.com", password_hash=pwd, role="admin", hospital_id=h1.id)
    u2 = User(full_name="User Beta", email="beta@hospital.com", password_hash=pwd, role="admin", hospital_id=h2.id)
    db_session.add_all([u1, u2])
    db_session.commit()

    # Login
    r1 = client.post("/api/v1/auth/login", json={"email": "alpha@hospital.com", "password": "Password123!"})
    tok1 = r1.json()["access_token"]

    r2 = client.post("/api/v1/auth/login", json={"email": "beta@hospital.com", "password": "Password123!"})
    tok2 = r2.json()["access_token"]

    # Hospital 1 user accesses Ward 1 forecast (Allowed 200 OK)
    resp_w1 = client.get(f"/api/v1/wards/{w1.id}/forecast", headers={"Authorization": f"Bearer {tok1}"})
    assert resp_w1.status_code == 200
    assert resp_w1.json()["ward_id"] == w1.id

    # Hospital 1 user attempts to access Ward 2 forecast (Rejected 403 Forbidden)
    resp_w2_cross = client.get(f"/api/v1/wards/{w2.id}/forecast", headers={"Authorization": f"Bearer {tok1}"})
    assert resp_w2_cross.status_code == 403

    # Hospital 1 user attempts to access Hospital 2 forecast (Rejected 403 Forbidden)
    resp_h2_cross = client.get(f"/api/v1/hospitals/{h2.id}/forecast", headers={"Authorization": f"Bearer {tok1}"})
    assert resp_h2_cross.status_code == 403

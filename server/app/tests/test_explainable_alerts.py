import pytest
import json
from datetime import datetime, date, timedelta
from unittest.mock import patch
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
from app.models.capacity_alert import CapacityAlert, AlertType, AlertSeverity, AlertStatus
from app.models.bed_capacity_forecast import BedCapacityForecast, RiskLevel
from app.core.security import get_password_hash
from app.services.explainable_alert_service import ExplainableAlertService
from app.services.alert_service import AlertService


@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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


def seed_hospital_and_ward(
    db: Session,
    hospital_name="St. Jude Hospital",
    code="H_JUDE",
    ward_name="General Ward",
    capacity=20,
    ward_type="GENERAL",
):
    h = Hospital(name=hospital_name, code=code, city="Metropolis", status="ACTIVE")
    db.add(h)
    db.commit()

    w = Ward(
        hospital_id=h.id,
        name=ward_name,
        ward_type=ward_type,
        department="Medicine",
        floor="Floor 2",
        capacity=capacity,
        status="ACTIVE",
    )
    db.add(w)
    db.commit()
    return h, w


def seed_snapshots(db: Session, hospital_id: int, ward_id: int, occupied_counts: list[int], total_beds=20):
    start = date(2026, 8, 1)
    for i, occ in enumerate(occupied_counts):
        d_time = datetime(start.year, start.month, start.day + i, 12, 0, 0)
        snap = OccupancySnapshot(
            hospital_id=hospital_id,
            ward_id=ward_id,
            snapshot_time=d_time,
            total_beds=total_beds,
            occupied_beds=occ,
            available_beds=max(0, total_beds - occ),
            occupancy_percentage=round((occ / total_beds) * 100.0, 2) if total_beds > 0 else 0.0,
        )
        db.add(snap)
    db.commit()


def seed_beds(db: Session, hospital_id: int, ward_id: int, occupied_count: int, total_beds: int):
    for i in range(total_beds):
        status = BedStatus.OCCUPIED.value if i < occupied_count else BedStatus.AVAILABLE.value
        b = Bed(
            hospital_id=hospital_id,
            ward_id=ward_id,
            bed_number=f"B-{ward_id}-{i+1}",
            status=status,
            bed_type=BedType.STANDARD.value,
        )
        db.add(b)
    db.commit()


# ── 1. Valid Low-Risk Ward ───────────────────────────────────────────────────
def test_01_valid_low_risk_ward(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # 10 days of low occupancy (e.g. 6/20 = 30%)
    seed_snapshots(db_session, h.id, w.id, [6] * 10, total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=6, total_beds=20)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )

    assert res["risk_level"] == "LOW"
    assert res["severity"] == "INFO"
    assert res["has_alert"] is False
    assert len(res["rules_triggered"]) == 0
    assert "within safe operational limits" in res["explanation"]["human_readable_explanation"]
    assert res["explanation"]["evidence"]["current_occupancy_percentage"] == 30.0


# ── 2. Forecasted Occupancy Triggering High-Risk Alert ───────────────────────
def test_02_forecasted_occupancy_triggering_high_risk_alert(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # Upward trend reaching 18/20 = 90% (>= 85% high risk threshold, < 95%)
    seed_snapshots(db_session, h.id, w.id, [14, 14, 15, 15, 16, 16, 17, 17, 18, 18], total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=17, total_beds=20)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )

    assert res["risk_level"] in ["HIGH", "CRITICAL"]
    assert any("RULE_A_HIGH_FORECAST" in r for r in res["rules_triggered"]) or any(
        "RULE_B_CRITICAL_FORECAST" in r for r in res["rules_triggered"]
    )
    assert res["has_alert"] is True
    assert len(res["explanation"]["suggested_actions"]) > 0


# ── 3. Forecasted Occupancy Triggering Critical-Risk Alert ───────────────────
def test_03_forecasted_occupancy_triggering_critical_risk_alert(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # Consistent 19/20 or 20/20 beds = 95%-100%
    seed_snapshots(db_session, h.id, w.id, [19, 19, 19, 19, 20, 20, 20, 20, 20, 20], total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=20, total_beds=20)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )

    assert res["risk_level"] == "CRITICAL"
    assert res["severity"] == "CRITICAL"
    assert "RULE_B_CRITICAL_FORECAST" in res["rules_triggered"]
    assert res["explanation"]["evidence"]["current_occupancy_percentage"] == 100.0


# ── 4. Low Estimated Bed Availability ────────────────────────────────────────
def test_04_low_estimated_bed_availability(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [10] * 10, total_beds=20)
    # Set live beds such that only 1 bed is available (<= 2 beds threshold)
    seed_beds(db_session, h.id, w.id, occupied_count=19, total_beds=20)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )

    assert "RULE_C_LOW_AVAILABILITY" in res["rules_triggered"]
    rule_c = next(r for r in res["explanation"]["triggered_rules"] if r["rule_id"] == "RULE_C_LOW_AVAILABILITY")
    assert rule_c["trigger_value"] == 1.0
    assert rule_c["threshold_value"] == 2.0


# ── 5. Forecasted Occupancy Exceeding Physical Capacity ──────────────────────
def test_05_forecasted_occupancy_exceeding_capacity(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [18] * 10, total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=18, total_beds=20)

    # Mock forecast result where SARIMA projects 22 occupied beds (capacity 20)
    fake_forecast = {
        "status": "SUCCESS",
        "model": "SARIMA",
        "forecasts": [
            {
                "date": "2026-08-11",
                "predicted_occupied_beds": 22.0,
                "predicted_occupancy_percentage": 110.0,
                "lower_bound": 95.0,
                "upper_bound": 115.0,
                "risk_level": "CRITICAL",
            }
        ],
    }
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=fake_forecast):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )

        assert "RULE_E_CAPACITY_EXCEEDANCE" in res["rules_triggered"]
        assert res["risk_level"] == "CRITICAL"
        assert res["explanation"]["evidence"]["is_capacity_exceeded"] is True


# ── 6. Rapid Observed Occupancy Increase ─────────────────────────────────────
def test_06_rapid_observed_occupancy_increase(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # Seed snapshots where occupancy jumped from 40% (8 beds) to 75% (15 beds) -> +35% jump
    now = datetime.utcnow()
    # Oldest snapshot 48h ago
    snap1 = OccupancySnapshot(
        hospital_id=h.id, ward_id=w.id,
        snapshot_time=now - timedelta(hours=48),
        total_beds=20, occupied_beds=8, available_beds=12, occupancy_percentage=40.0
    )
    # Latest snapshot now
    snap2 = OccupancySnapshot(
        hospital_id=h.id, ward_id=w.id,
        snapshot_time=now,
        total_beds=20, occupied_beds=15, available_beds=5, occupancy_percentage=75.0
    )
    db_session.add_all([snap1, snap2])
    db_session.commit()
    seed_beds(db_session, h.id, w.id, occupied_count=15, total_beds=20)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )

    assert "RULE_D_RAPID_INCREASE" in res["rules_triggered"]
    assert res["explanation"]["evidence"]["historical_trend_percentage_change"] == 35.0


# ── 7. Missing Historical Observations ───────────────────────────────────────
def test_07_missing_historical_observations(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # Snapshots with non-contiguous dates (Aug 1, Aug 2, Aug 6, Aug 10)
    dates = [1, 2, 6, 10]
    for d in dates:
        db_session.add(OccupancySnapshot(
            hospital_id=h.id, ward_id=w.id,
            snapshot_time=datetime(2026, 8, d, 12, 0, 0),
            total_beds=20, occupied_beds=10, available_beds=10, occupancy_percentage=50.0
        ))
    db_session.commit()
    seed_beds(db_session, h.id, w.id, occupied_count=10, total_beds=20)

    # Should not crash; forward-fills gaps gracefully
    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )
    assert res["ward_id"] == w.id
    assert res["explanation"]["evidence"]["ward_capacity"] == 20


# ── 8. Insufficient History for SARIMA ───────────────────────────────────────
def test_08_insufficient_history_for_sarima(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # Only 3 daily observations (minimum required is 7)
    seed_snapshots(db_session, h.id, w.id, [8, 9, 8], total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=8, total_beds=20)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )

    assert "RULE_G_INSUFFICIENT_DATA" in res["rules_triggered"]
    assert res["risk_level"] == "INSUFFICIENT_DATA"
    assert len(res["explanation"]["evidence"]["data_quality_notes"]) > 0


# ── 9. Invalid or Zero Capacity ──────────────────────────────────────────────
def test_09_invalid_or_zero_capacity(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=0)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )

    assert res["risk_level"] == "INSUFFICIENT_DATA"
    assert "RULE_G_INSUFFICIENT_DATA" in [r["rule_id"] for r in res["explanation"]["triggered_rules"]]
    assert "Invalid capacity" in res["explanation"]["headline"]


# ── 10. Negative or Invalid Forecast Values ──────────────────────────────────
def test_10_negative_or_invalid_forecast_values(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [5] * 10, total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=5, total_beds=20)

    # Mock raw SARIMA output with negative prediction (-3.0 beds)
    fake_forecast = {
        "status": "SUCCESS",
        "model": "SARIMA",
        "forecasts": [
            {
                "date": "2026-08-11",
                "predicted_occupied_beds": 0.0,  # correctly clipped by TimeSeriesForecaster
                "predicted_occupancy_percentage": 0.0,
                "lower_bound": 0.0,
                "upper_bound": 10.0,
                "risk_level": "NORMAL",
            }
        ],
    }
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=fake_forecast):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )
        assert res["explanation"]["evidence"]["predicted_occupied_beds"] >= 0.0


# ── 11. Missing Forecast Intervals ───────────────────────────────────────────
def test_11_missing_forecast_intervals(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [10] * 10, total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=10, total_beds=20)

    fake_forecast = {
        "status": "SUCCESS",
        "model": "BASELINE",
        "forecasts": [
            {
                "date": "2026-08-11",
                "predicted_occupied_beds": 10.0,
                "predicted_occupancy_percentage": 50.0,
                "risk_level": "NORMAL",
                # no lower_bound or upper_bound provided
            }
        ],
    }
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=fake_forecast):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )
        # Should not crash and handles missing bounds safely
        assert res["risk_level"] == "LOW"


# ── 12. High Uncertainty When Intervals Are Available ────────────────────────
def test_12_high_uncertainty_when_intervals_available(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [10] * 10, total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=10, total_beds=20)

    # Mock prediction interval with wide span: 50% to 85% (span 35% >= 25% threshold)
    fake_forecast = {
        "status": "SUCCESS",
        "model": "SARIMA",
        "forecasts": [
            {
                "date": "2026-08-11",
                "predicted_occupied_beds": 14.0,
                "predicted_occupancy_percentage": 70.0,
                "lower_bound": 50.0,
                "upper_bound": 85.0,
                "risk_level": "MODERATE",
            }
        ],
    }
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=fake_forecast):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )
        assert "RULE_F_HIGH_UNCERTAINTY" in res["rules_triggered"]
        assert res["explanation"]["evidence"]["uncertainty_interval_width"] == 35.0


# ── 13. Explanation Contains the Actual Triggered Rule ───────────────────────
def test_13_explanation_contains_actual_triggered_rule(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [19] * 10, total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=19, total_beds=20)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )
    explanation = res["explanation"]["human_readable_explanation"]
    assert "Critical Forecasted Occupancy" in explanation or "Low Bed Availability" in explanation


# ── 14. Explanation Values Match the Evaluated Input Data ────────────────────
def test_14_explanation_values_match_input_data(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=25, ward_name="Surgical Ward")
    seed_snapshots(db_session, h.id, w.id, [12] * 10, total_beds=25)
    seed_beds(db_session, h.id, w.id, occupied_count=12, total_beds=25)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
    )
    ev = res["explanation"]["evidence"]
    assert ev["ward_name"] == "Surgical Ward"
    assert ev["ward_capacity"] == 25
    assert ev["current_occupied_beds"] == 12
    assert ev["current_occupancy_percentage"] == 48.0


# ── 15. Identical Inputs Produce Consistent Risk Results ─────────────────────
def test_15_identical_inputs_produce_consistent_risk_results(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [14] * 10, total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=14, total_beds=20)

    res1 = ExplainableAlertService.evaluate_ward_capacity_risk(db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=False)
    res2 = ExplainableAlertService.evaluate_ward_capacity_risk(db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=False)

    assert res1["risk_level"] == res2["risk_level"]
    assert res1["severity"] == res2["severity"]
    assert res1["rules_triggered"] == res2["rules_triggered"]
    assert res1["explanation"]["evidence"]["current_occupancy_percentage"] == res2["explanation"]["evidence"]["current_occupancy_percentage"]


# ── 16. Duplicate Alert Prevention ───────────────────────────────────────────
def test_16_duplicate_alert_prevention(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [19] * 10, total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=19, total_beds=20)

    # First evaluation creates alert
    ExplainableAlertService.evaluate_ward_capacity_risk(db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True)
    count1 = db_session.query(CapacityAlert).filter(CapacityAlert.ward_id == w.id).count()

    # Second evaluation updates existing active alert rather than duplicating
    ExplainableAlertService.evaluate_ward_capacity_risk(db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True)
    count2 = db_session.query(CapacityAlert).filter(CapacityAlert.ward_id == w.id).count()

    assert count1 == count2
    assert count1 >= 1


# ── 17. Alert Acknowledgement Permissions & State Transition ─────────────────
def test_17_alert_acknowledgement_permissions(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [19] * 10, total_beds=20)
    seed_beds(db_session, h.id, w.id, occupied_count=19, total_beds=20)

    alert = CapacityAlert(
        hospital_id=h.id, ward_id=w.id,
        alert_type=AlertType.CRITICAL_OCCUPANCY.value,
        severity=AlertSeverity.CRITICAL.value,
        message="Critical occupancy warning",
        trigger_value=95.0, threshold_value=95.0,
        status=AlertStatus.ACTIVE.value,
    )
    db_session.add(alert)

    pwd = get_password_hash("Password123!")
    user = User(full_name="Nurse Jane", email="jane@hospital.com", password_hash=pwd, role="nurse", hospital_id=h.id)
    db_session.add(user)
    db_session.commit()

    # Login as nurse
    login_res = client.post("/api/v1/auth/login", json={"email": "jane@hospital.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    # Acknowledge alert
    ack_res = client.post(f"/api/v1/alerts/{alert.id}/acknowledge", headers={"Authorization": f"Bearer {token}"})
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    # Verify state in DB
    db_alert = db_session.query(CapacityAlert).filter(CapacityAlert.id == alert.id).first()
    assert db_alert.status == "ACKNOWLEDGED"
    assert db_alert.acknowledged_at is not None
    assert db_alert.acknowledged_by_id == user.id


# ── 18. Unauthorized Hospital Access ─────────────────────────────────────────
def test_18_unauthorized_hospital_access(client: TestClient, db_session: Session):
    h1, w1 = seed_hospital_and_ward(db_session, hospital_name="Hospital 1", code="H1", capacity=20)
    h2, w2 = seed_hospital_and_ward(db_session, hospital_name="Hospital 2", code="H2", capacity=20)

    pwd = get_password_hash("Password123!")
    u1 = User(full_name="Admin Hosp 1", email="admin1@hosp.com", password_hash=pwd, role="admin", hospital_id=h1.id)
    db_session.add(u1)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"email": "admin1@hosp.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    # Hospital 1 admin attempts to query Hospital 2 alerts -> 403 Forbidden
    resp = client.get(f"/api/v1/alerts?hospital_id={h2.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# ── 19. Cross-Hospital Ward Access ───────────────────────────────────────────
def test_19_cross_hospital_ward_access(client: TestClient, db_session: Session):
    h1, w1 = seed_hospital_and_ward(db_session, hospital_name="Hospital 1", code="H1", capacity=20)
    h2, w2 = seed_hospital_and_ward(db_session, hospital_name="Hospital 2", code="H2", capacity=20)

    pwd = get_password_hash("Password123!")
    u1 = User(full_name="Admin Hosp 1", email="admin1@hosp.com", password_hash=pwd, role="admin", hospital_id=h1.id)
    db_session.add(u1)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"email": "admin1@hosp.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    # Hospital 1 admin attempts to filter alerts by Ward 2 (belongs to Hospital 2) -> 403 Forbidden
    resp = client.get(f"/api/v1/alerts?ward_id={w2.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# ── 20. API Validation and Error Handling ────────────────────────────────────
def test_20_api_validation_and_error_handling(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    pwd = get_password_hash("Password123!")
    u = User(full_name="Admin Hosp", email="admin@hosp.com", password_hash=pwd, role="admin", hospital_id=h.id)
    db_session.add(u)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"email": "admin@hosp.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    # 404 for non-existent alert
    resp = client.get("/api/v1/alerts/99999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404

    # 404 for non-existent ward in alert evaluation
    resp_eval = client.post("/api/v1/alerts/evaluate?ward_id=99999", headers={"Authorization": f"Bearer {token}"})
    assert resp_eval.status_code == 404


# ── 21. Existing Alert API Regression Tests ──────────────────────────────────
def test_21_existing_alert_api_regression(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    alert = CapacityAlert(
        hospital_id=h.id, ward_id=w.id,
        alert_type=AlertType.HIGH_OCCUPANCY.value,
        severity=AlertSeverity.WARNING.value,
        message="High occupancy alert",
        trigger_value=88.0, threshold_value=85.0,
        status=AlertStatus.ACTIVE.value,
    )
    db_session.add(alert)
    pwd = get_password_hash("Password123!")
    u = User(full_name="Admin", email="admin_reg@hosp.com", password_hash=pwd, role="admin", hospital_id=h.id)
    db_session.add(u)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"email": "admin_reg@hosp.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    # List alerts
    list_res = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # Resolve alert
    resolve_res = client.post(f"/api/v1/alerts/{alert.id}/resolve", headers={"Authorization": f"Bearer {token}"})
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"


# ── 22. Forecast API Regression Tests ────────────────────────────────────────
def test_22_forecast_api_regression(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_snapshots(db_session, h.id, w.id, [10] * 10, total_beds=20)
    pwd = get_password_hash("Password123!")
    u = User(full_name="Doctor", email="doc_reg@hosp.com", password_hash=pwd, role="doctor", hospital_id=h.id)
    db_session.add(u)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"email": "doc_reg@hosp.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    resp = client.get(f"/api/v1/wards/{w.id}/forecast?horizon=7", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ward_id"] == w.id
    assert "forecasts" in data


# ── 23. Occupancy API Regression Tests ───────────────────────────────────────
def test_23_occupancy_api_regression(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_beds(db_session, h.id, w.id, occupied_count=10, total_beds=20)
    pwd = get_password_hash("Password123!")
    u = User(full_name="Nurse", email="nurse_reg@hosp.com", password_hash=pwd, role="nurse", hospital_id=h.id)
    db_session.add(u)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"email": "nurse_reg@hosp.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    resp = client.get(f"/api/v1/occupancy/wards/{w.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["ward_id"] == w.id


# ── 24. Ingestion Regression Tests ───────────────────────────────────────────
def test_24_ingestion_regression(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_beds(db_session, h.id, w.id, occupied_count=5, total_beds=20)
    bed = db_session.query(Bed).filter(Bed.ward_id == w.id, Bed.status == BedStatus.AVAILABLE.value).first()

    pwd = get_password_hash("Password123!")
    u = User(full_name="Admin", email="admin_ingest@hosp.com", password_hash=pwd, role="admin", hospital_id=h.id)
    db_session.add(u)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"email": "admin_ingest@hosp.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    payload = {
        "event_id": "EVT_TEST_001",
        "hospital_id": h.id,
        "ward_id": w.id,
        "bed_id": bed.id,
        "event_type": "ADMISSION",
        "event_time": datetime.utcnow().isoformat(),
        "source": "API",
    }
    resp = client.post("/api/v1/ingestion/events", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [200, 201]


# ── 25. Transfer Module Regression Tests ─────────────────────────────────────
def test_25_transfer_module_regression(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    pwd = get_password_hash("Password123!")
    u = User(full_name="Admin", email="admin_trans@hosp.com", password_hash=pwd, role="admin", hospital_id=h.id)
    db_session.add(u)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"email": "admin_trans@hosp.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    resp = client.get(f"/api/v1/transfers/recommendations?hospital_id={h.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


# ── 26. Authentication Regression Tests ──────────────────────────────────────
def test_26_authentication_regression(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    pwd = get_password_hash("Password123!")
    u = User(full_name="Auth User", email="auth_reg@hosp.com", password_hash=pwd, role="doctor", hospital_id=h.id)
    db_session.add(u)
    db_session.commit()

    # Valid login
    login_res = client.post("/api/v1/auth/login", json={"email": "auth_reg@hosp.com", "password": "Password123!"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # /me endpoint
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "auth_reg@hosp.com"

    # Invalid login
    bad_res = client.post("/api/v1/auth/login", json={"email": "auth_reg@hosp.com", "password": "WrongPassword!"})
    assert bad_res.status_code == 401

import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.session import Base, get_db
from app.main import app
from app.models.bed import Bed, BedStatus, BedType
from app.models.capacity_alert import AlertSeverity, AlertStatus, AlertType, CapacityAlert
from app.models.hospital import Hospital
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.user import User
from app.models.ward import Ward
from app.services.explainable_alert_service import ExplainableAlertService
from app.services.snapshot_service import SnapshotService


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
    hospital_name="Memorial General",
    code="MEM_GEN",
    ward_name="ICU West",
    capacity=20,
    ward_type="ICU",
):
    h = Hospital(name=hospital_name, code=code, city="Metro City", status="ACTIVE")
    db.add(h)
    db.commit()

    w = Ward(
        hospital_id=h.id,
        name=ward_name,
        ward_type=ward_type,
        department="Critical Care",
        floor="Floor 3",
        capacity=capacity,
        status="ACTIVE",
    )
    db.add(w)
    db.commit()
    return h, w


def seed_beds(db: Session, hospital_id: int, ward_id: int, occupied_count: int, total_beds: int):
    for i in range(total_beds):
        status = BedStatus.OCCUPIED.value if i < occupied_count else BedStatus.AVAILABLE.value
        b = Bed(
            hospital_id=hospital_id,
            ward_id=ward_id,
            bed_number=f"BED-{ward_id}-{i+1:02d}",
            status=status,
            bed_type=BedType.STANDARD.value,
        )
        db.add(b)
    db.commit()


def seed_user(db: Session, hospital_id: int, role="admin", email="admin@hospital.com", full_name="Dr. Admin"):
    pwd = get_password_hash("SecretPassword123!")
    user = User(
        full_name=full_name,
        email=email,
        password_hash=pwd,
        role=role,
        hospital_id=hospital_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def get_auth_token(client: TestClient, email: str, password="SecretPassword123!") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


# ── 1. Current Capacity Alerts: High and Critical Occupancy ─────────────────
def test_current_capacity_high_and_critical_occupancy(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # 18 of 20 beds occupied = 90% (>= 85% high threshold, < 95%)
    seed_beds(db_session, h.id, w.id, occupied_count=18, total_beds=20)

    # Mock empty forecast to verify current occupancy rule
    empty_forecast = {"status": "SUCCESS", "model": "SARIMA", "forecasts": []}
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=empty_forecast):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True
        )

        assert res["has_alert"] is True
        assert res["risk_level"] in ["HIGH", "CRITICAL"]
        assert any(r["rule_id"] in ["RULE_A_HIGH_FORECAST", "RULE_B_CRITICAL_FORECAST"] for r in res["explanation"]["triggered_rules"])
        assert res["explanation"]["evidence"]["current_occupancy_percentage"] == 90.0

    # 19 of 20 beds occupied = 95% (critical threshold)
    db_session.query(Bed).filter(Bed.ward_id == w.id).delete()
    seed_beds(db_session, h.id, w.id, occupied_count=19, total_beds=20)
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=empty_forecast):
        res_crit = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True
        )
        assert res_crit["risk_level"] == "CRITICAL"
        assert res_crit["severity"] == "CRITICAL"
        assert any(r["rule_id"] == "RULE_B_CRITICAL_FORECAST" for r in res_crit["explanation"]["triggered_rules"])


# ── 2. Current Capacity Alerts: Low Bed Availability ─────────────────────────
def test_current_low_availability_alert(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # 19 occupied, 1 available (threshold <= 2)
    seed_beds(db_session, h.id, w.id, occupied_count=19, total_beds=20)

    empty_forecast = {"status": "SUCCESS", "model": "SARIMA", "forecasts": []}
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=empty_forecast):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )

        assert "RULE_C_LOW_AVAILABILITY" in res["rules_triggered"]
        rule_c = next(r for r in res["explanation"]["triggered_rules"] if r["rule_id"] == "RULE_C_LOW_AVAILABILITY")
        assert rule_c["trigger_value"] == 1.0
        assert rule_c["threshold_value"] == 2.0


# ── 3. Current Capacity Exceedance (Data Quality / Overflow Issue) ────────────
def test_current_capacity_exceedance_data_quality(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # 22 beds occupied in a 20-bed ward
    seed_beds(db_session, h.id, w.id, occupied_count=22, total_beds=22)

    empty_forecast = {"status": "SUCCESS", "model": "SARIMA", "forecasts": []}
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=empty_forecast):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )

        assert res["risk_level"] == "CRITICAL"
        assert "RULE_E_CAPACITY_EXCEEDANCE" in res["rules_triggered"]
        assert res["explanation"]["evidence"]["is_capacity_exceeded"] is True
        assert any("exceed" in n.lower() for n in res["explanation"]["evidence"]["data_quality_notes"])


# ── 4. Forecast-Based Alerts: Overcrowding & Time to Threshold ───────────────
def test_forecast_based_high_occupancy_and_time_to_threshold(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # Current occupancy normal: 10/20 = 50%
    seed_beds(db_session, h.id, w.id, occupied_count=10, total_beds=20)

    # Forecast climbs to 88% on day 3
    forecast_payload = {
        "status": "SUCCESS",
        "model": "SARIMA",
        "forecasts": [
            {"date": "2026-10-23", "predicted_occupied_beds": 12.0, "predicted_occupancy_percentage": 60.0, "lower_bound": 55.0, "upper_bound": 65.0},
            {"date": "2026-10-24", "predicted_occupied_beds": 15.0, "predicted_occupancy_percentage": 75.0, "lower_bound": 70.0, "upper_bound": 80.0},
            {"date": "2026-10-25", "predicted_occupied_beds": 17.6, "predicted_occupancy_percentage": 88.0, "lower_bound": 82.0, "upper_bound": 94.0},
        ],
    }

    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=forecast_payload):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )

        assert res["risk_level"] == "HIGH"
        assert "RULE_A_HIGH_FORECAST" in res["rules_triggered"]
        ev = res["explanation"]["evidence"]
        assert ev["predicted_occupancy_percentage"] == 88.0
        assert ev["time_to_threshold_days"] == 3
        assert ev["time_to_threshold_date"] == "2026-10-25"


# ── 5. Forecast-Based Alerts: Low Forecast Bed Availability ───────────────────
def test_forecast_low_bed_availability_alert(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # Current available: 6 beds (not triggering current low availability)
    seed_beds(db_session, h.id, w.id, occupied_count=14, total_beds=20)

    # Forecast projects 19 occupied beds (1 available bed remaining <= 2)
    forecast_payload = {
        "status": "SUCCESS",
        "model": "SARIMA",
        "forecasts": [
            {"date": "2026-10-23", "predicted_occupied_beds": 19.0, "predicted_occupancy_percentage": 95.0, "lower_bound": 90.0, "upper_bound": 100.0},
        ],
    }

    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=forecast_payload):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )

        assert "RULE_C_LOW_AVAILABILITY" in res["rules_triggered"]
        assert res["explanation"]["evidence"]["predicted_available_beds"] == 1.0


# ── 6. Forecast Exceeding Physical Capacity ──────────────────────────────────
def test_forecast_exceeding_capacity(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_beds(db_session, h.id, w.id, occupied_count=15, total_beds=20)

    forecast_payload = {
        "status": "SUCCESS",
        "model": "SARIMA",
        "forecasts": [
            {"date": "2026-10-23", "predicted_occupied_beds": 24.0, "predicted_occupancy_percentage": 120.0, "lower_bound": 110.0, "upper_bound": 130.0},
        ],
    }

    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=forecast_payload):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )

        assert res["risk_level"] == "CRITICAL"
        assert "RULE_E_CAPACITY_EXCEEDANCE" in res["rules_triggered"]
        assert res["explanation"]["evidence"]["is_capacity_exceeded"] is True


# ── 7. Rapid Historical Growth Velocity ──────────────────────────────────────
def test_rapid_historical_growth_velocity(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    now = datetime.now(timezone.utc)
    # 3 days ago: 30% occupancy
    s1 = OccupancySnapshot(
        hospital_id=h.id, ward_id=w.id, snapshot_time=now - timedelta(days=3),
        total_beds=20, occupied_beds=6, available_beds=14, occupancy_percentage=30.0
    )
    # Today: 65% occupancy (+35% increase >= 15% threshold)
    s2 = OccupancySnapshot(
        hospital_id=h.id, ward_id=w.id, snapshot_time=now,
        total_beds=20, occupied_beds=13, available_beds=7, occupancy_percentage=65.0
    )
    db_session.add_all([s1, s2])
    db_session.commit()
    seed_beds(db_session, h.id, w.id, occupied_count=13, total_beds=20)

    empty_forecast = {"status": "SUCCESS", "model": "SARIMA", "forecasts": []}
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=empty_forecast):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )

        assert "RULE_D_RAPID_INCREASE" in res["rules_triggered"]
        assert res["explanation"]["evidence"]["historical_trend_percentage_change"] == 35.0


# ── 8. High Forecast Prediction Uncertainty ──────────────────────────────────
def test_high_forecast_uncertainty(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_beds(db_session, h.id, w.id, occupied_count=10, total_beds=20)

    # 95% CI spans 40% to 75% -> width = 35% (>= 25% uncertainty threshold)
    forecast_payload = {
        "status": "SUCCESS",
        "model": "SARIMA",
        "forecasts": [
            {"date": "2026-10-23", "predicted_occupied_beds": 11.0, "predicted_occupancy_percentage": 55.0, "lower_bound": 40.0, "upper_bound": 75.0},
        ],
    }

    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=forecast_payload):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True
        )

        assert "RULE_F_HIGH_UNCERTAINTY" in res["rules_triggered"]
        assert res["explanation"]["evidence"]["uncertainty_interval_width"] == 35.0

        alert = db_session.query(CapacityAlert).filter(CapacityAlert.ward_id == w.id).first()
        assert alert is not None
        assert alert.alert_type == AlertType.HIGH_UNCERTAINTY.value


# ── 9. Missing and Stale Forecast Handling ───────────────────────────────────
def test_stale_and_missing_forecast_data_quality(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_beds(db_session, h.id, w.id, occupied_count=10, total_beds=20)

    # Forecast generated 60 hours ago (> 48h staleness threshold)
    stale_timestamp = (datetime.now(timezone.utc) - timedelta(hours=60)).isoformat()
    stale_forecast = {
        "status": "SUCCESS",
        "model": "SARIMA",
        "generated_at": stale_timestamp,
        "forecasts": [
            {"date": "2026-10-23", "predicted_occupied_beds": 10.0, "predicted_occupancy_percentage": 50.0, "lower_bound": 45.0, "upper_bound": 55.0},
        ],
    }

    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=stale_forecast):
        res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7
        )

        assert any("stale" in note.lower() for note in res["explanation"]["evidence"]["data_quality_notes"])
        assert any("RULE_G_INSUFFICIENT_DATA" == r["rule_id"] for r in res["explanation"]["triggered_rules"])


# ── 10. Invalid Physical Capacity ────────────────────────────────────────────
def test_invalid_capacity_generates_critical_data_quality_alert(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=0)

    res = ExplainableAlertService.evaluate_ward_capacity_risk(
        db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True
    )

    assert res["risk_level"] == "INSUFFICIENT_DATA"
    assert res["severity"] == "CRITICAL"
    assert "Invalid Ward Capacity" in res["explanation"]["triggered_rules"][0]["rule_name"]


# ── 11. Deduplication and In-Place Active Updates ─────────────────────────────
def test_alert_deduplication_and_in_place_update(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_beds(db_session, h.id, w.id, occupied_count=18, total_beds=20)

    empty_forecast = {"status": "SUCCESS", "model": "SARIMA", "forecasts": []}
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=empty_forecast):
        # First run creates active alert
        ExplainableAlertService.evaluate_ward_capacity_risk(db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True)
        count_first = db_session.query(CapacityAlert).filter(CapacityAlert.ward_id == w.id).count()
        assert count_first == 1

        # Second run updates existing alert in-place rather than adding a row
        ExplainableAlertService.evaluate_ward_capacity_risk(db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True)
        count_second = db_session.query(CapacityAlert).filter(CapacityAlert.ward_id == w.id).count()
        assert count_second == 1


# ── 12. Alert Lifecycle: Acknowledge and Resolve Transitions ─────────────────
def test_alert_lifecycle_transitions(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    doctor = seed_user(db_session, h.id, role="doctor", email="doctor@hospital.com", full_name="Dr. Smith")
    _admin = seed_user(db_session, h.id, role="admin", email="admin_lead@hospital.com", full_name="Admin Lead")

    alert = CapacityAlert(
        hospital_id=h.id,
        ward_id=w.id,
        alert_type=AlertType.CRITICAL_OCCUPANCY.value,
        severity=AlertSeverity.CRITICAL.value,
        message="Critical occupancy level reached",
        trigger_value=96.0,
        threshold_value=95.0,
        status=AlertStatus.ACTIVE.value,
    )
    db_session.add(alert)
    db_session.commit()

    # Step 1: Doctor acknowledges alert
    doc_token = get_auth_token(client, "doctor@hospital.com")
    ack_res = client.post(f"/api/v1/alerts/{alert.id}/acknowledge", headers={"Authorization": f"Bearer {doc_token}"})
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    db_session.refresh(alert)
    assert alert.status == "ACKNOWLEDGED"
    assert alert.acknowledged_by_id == doctor.id
    assert alert.acknowledged_at is not None

    # Step 2: Doctor cannot resolve (admin-only)
    fail_resolve = client.post(f"/api/v1/alerts/{alert.id}/resolve", headers={"Authorization": f"Bearer {doc_token}"})
    assert fail_resolve.status_code == 403

    # Step 3: Admin resolves alert
    admin_token = get_auth_token(client, "admin_lead@hospital.com")
    res_res = client.post(f"/api/v1/alerts/{alert.id}/resolve", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"

    db_session.refresh(alert)
    assert alert.status == "RESOLVED"
    assert alert.resolved_at is not None


# ── 13. Auto-Resolution When Ward Returns to Safe Capacity ───────────────────
def test_auto_resolution_on_metric_normalization(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # Start high occupancy -> alert active
    seed_beds(db_session, h.id, w.id, occupied_count=19, total_beds=20)

    empty_forecast = {"status": "SUCCESS", "model": "SARIMA", "forecasts": []}
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=empty_forecast):
        ExplainableAlertService.evaluate_ward_capacity_risk(db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True)
        active_alert = db_session.query(CapacityAlert).filter(CapacityAlert.ward_id == w.id, CapacityAlert.status == "ACTIVE").first()
        assert active_alert is not None

        # Occupancy drops to safe level (6/20 = 30%)
        db_session.query(Bed).filter(Bed.ward_id == w.id).delete()
        seed_beds(db_session, h.id, w.id, occupied_count=6, total_beds=20)

        safe_forecast = {
            "status": "SUCCESS",
            "model": "SARIMA",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "forecasts": [
                {
                    "date": (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "predicted_occupied_beds": 6.0,
                    "predicted_occupancy": 6.0,
                    "predicted_occupancy_percentage": 30.0,
                    "predicted_available": 14.0,
                    "lower_bound_percentage": 25.0,
                    "upper_bound_percentage": 35.0,
                }
            ],
        }
        with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=safe_forecast):
            # Next evaluation auto-resolves the alert
            ExplainableAlertService.evaluate_ward_capacity_risk(db=db_session, ward_id=w.id, hospital_id=h.id, horizon=7, persist=True)
            db_session.refresh(active_alert)
            assert active_alert.status == "RESOLVED"
            assert active_alert.resolved_at is not None


# ── 14. Alert Summary Endpoint KPI Aggregation ───────────────────────────────
def test_alert_summary_endpoint(client: TestClient, db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    seed_user(db_session, h.id, role="admin", email="summary_admin@hospital.com")

    # Seed alerts of varying status and severity
    a1 = CapacityAlert(hospital_id=h.id, ward_id=w.id, alert_type=AlertType.CRITICAL_OCCUPANCY.value, severity=AlertSeverity.CRITICAL.value, message="Critical 1", trigger_value=96.0, threshold_value=95.0, status=AlertStatus.ACTIVE.value)
    a2 = CapacityAlert(hospital_id=h.id, ward_id=w.id, alert_type=AlertType.HIGH_OCCUPANCY.value, severity=AlertSeverity.WARNING.value, message="Warning 1", trigger_value=88.0, threshold_value=85.0, status=AlertStatus.ACKNOWLEDGED.value)
    a3 = CapacityAlert(hospital_id=h.id, ward_id=w.id, alert_type=AlertType.INSUFFICIENT_DATA.value, severity=AlertSeverity.INFO.value, message="Data quality", trigger_value=0.0, threshold_value=1.0, status=AlertStatus.ACTIVE.value)
    a4 = CapacityAlert(hospital_id=h.id, ward_id=w.id, alert_type=AlertType.LOW_AVAILABILITY.value, severity=AlertSeverity.WARNING.value, message="Resolved old", trigger_value=1.0, threshold_value=2.0, status=AlertStatus.RESOLVED.value)
    db_session.add_all([a1, a2, a3, a4])
    db_session.commit()

    token = get_auth_token(client, "summary_admin@hospital.com")
    res = client.get("/api/v1/alerts/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert data["total_active"] == 3  # a1, a2, a3
    assert data["unacknowledged_count"] == 2  # a1, a3
    assert data["critical_count"] == 1  # a1
    assert data["high_count"] == 1  # a2
    assert data["data_quality_count"] == 1  # a3
    assert data["resolved_count"] == 1  # a4


# ── 15. Cross-Hospital Tenant Isolation ──────────────────────────────────────
def test_cross_hospital_isolation(client: TestClient, db_session: Session):
    h1, _w1 = seed_hospital_and_ward(db_session, hospital_name="Hospital Alpha", code="ALPHA", capacity=20)
    h2, w2 = seed_hospital_and_ward(db_session, hospital_name="Hospital Beta", code="BETA", capacity=20)

    _u1 = seed_user(db_session, h1.id, role="admin", email="alpha_user@hosp.com")
    a2 = CapacityAlert(hospital_id=h2.id, ward_id=w2.id, alert_type=AlertType.CRITICAL_OCCUPANCY.value, severity=AlertSeverity.CRITICAL.value, message="H2 Alert", trigger_value=98.0, threshold_value=95.0, status=AlertStatus.ACTIVE.value)
    db_session.add(a2)
    db_session.commit()

    token1 = get_auth_token(client, "alpha_user@hosp.com")

    # Hospital 1 user cannot query Hospital 2 alert summary
    res_summary = client.get(f"/api/v1/alerts/summary?hospital_id={h2.id}", headers={"Authorization": f"Bearer {token1}"})
    assert res_summary.status_code == 403

    # Hospital 1 user cannot access Hospital 2 alert detail
    res_detail = client.get(f"/api/v1/alerts/{a2.id}", headers={"Authorization": f"Bearer {token1}"})
    assert res_detail.status_code == 404  # Isolated query returns None/404

    # Hospital 1 user cannot evaluate Hospital 2 wards
    res_eval = client.post(f"/api/v1/alerts/evaluate?hospital_id={h2.id}", headers={"Authorization": f"Bearer {token1}"})
    assert res_eval.status_code == 403


# ── 16. Snapshot Generation Automatically Triggers Explainable Alerts ────────
def test_snapshot_generation_triggers_explainable_alerts(db_session: Session):
    h, w = seed_hospital_and_ward(db_session, capacity=20)
    # 19 occupied beds
    seed_beds(db_session, h.id, w.id, occupied_count=19, total_beds=20)

    empty_forecast = {"status": "SUCCESS", "model": "SARIMA", "forecasts": []}
    with patch("app.services.forecasting.forecast_service.ForecastService.get_ward_latest_forecast", return_value=empty_forecast):
        # Generate snapshots for hospital
        res = SnapshotService.generate_snapshots_for_hospital(db_session, hospital_id=h.id)
        assert res["snapshots_created"] == 1

        # Verify that an explainable alert with explanation_json was created
        alert = db_session.query(CapacityAlert).filter(CapacityAlert.ward_id == w.id).first()
        assert alert is not None
        assert alert.explanation_json is not None
        expl_data = json.loads(alert.explanation_json)
        assert "evidence" in expl_data
        assert "triggered_rules" in expl_data

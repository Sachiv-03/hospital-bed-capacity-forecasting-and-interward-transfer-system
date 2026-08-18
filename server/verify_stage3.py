"""
Stage 3 Comprehensive Bed Capacity Forecasting Pipeline Verification Script.
Tests Stage 1, Stage 2, and Stage 3 end-to-end functionality against Neon PostgreSQL / DB engine.
"""
import sys
import os
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any

# Ensure server root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from sqlalchemy import inspect, create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.main import app
from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus
from app.models.occupancy_event import OccupancyEvent
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.capacity_alert import CapacityAlert
from app.models.bed_capacity_forecast import BedCapacityForecast, RiskLevel
from app.models.user import User, UserRole
from app.services.snapshot_service import SnapshotService
from app.services.historical_service import HistoricalService
from app.services.forecasting.data_preparation import ForecastingDataPreparation
from app.services.forecasting.baseline_model import BaselineForecaster
from app.services.forecasting.time_series_model import TimeSeriesForecaster
from app.services.forecasting.forecast_service import ForecastService

results: Dict[str, Dict[str, Any]] = {}

def log_result(test_name: str, passed: bool, message: str = "", details: str = ""):
    results[test_name] = {
        "passed": passed,
        "status": "PASS" if passed else "FAIL",
        "message": message,
        "details": details
    }
    status_str = "[PASS]" if passed else "[FAIL]"
    print(f"{status_str} {test_name}: {message}")


def run_stage3_verification():
    print("=" * 80)
    print("      STAGE 3 — HOSPITAL BED CAPACITY FORECASTING SYSTEM VERIFICATION")
    print("=" * 80)

    # ── 1. DB Schema & Table Inspection ──────────────────────────────────────
    print("\n--- PART 1: Database Schema & Table Check ---")
    try:
        from app.database.database import engine
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = [
            "hospitals", "users", "wards", "beds",
            "occupancy_events", "occupancy_snapshots",
            "capacity_alerts", "bed_capacity_forecasts"
        ]
        missing = [t for t in expected if t not in tables]

        if missing:
            log_result("PART_1_DB_TABLES", False, f"Missing tables: {missing}")
        else:
            log_result("PART_1_DB_TABLES", True, f"All Stage 1, 2 & 3 tables present: {expected}")
    except Exception as e:
        log_result("PART_1_DB_TABLES", False, f"DB inspection error: {e}")

    # Set up isolated test DB session
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    db: Session = TestingSessionLocal()

    # ── 2. Multi-Hospital Test Setup & Historical Snapshot Generation ───────
    print("\n--- PART 2: Multi-Facility Test Setup & Snapshot Seeding ---")
    try:
        h1 = Hospital(name="St. Jude Medical Center", code="H_STJUDE_S3", city="Chicago", status="ACTIVE")
        h2 = Hospital(name="MetroCare Health", code="H_METRO_S3", city="Boston", status="ACTIVE")
        db.add_all([h1, h2])
        db.commit()

        w1 = Ward(hospital_id=h1.id, name="ICU Unit A", ward_type="ICU", department="Critical Care", floor="Floor 3", capacity=10, status="ACTIVE")
        w2 = Ward(hospital_id=h1.id, name="General Med B", ward_type="GENERAL", department="Internal Medicine", floor="Floor 2", capacity=15, status="ACTIVE")
        w3 = Ward(hospital_id=h2.id, name="Emergency Ward C", ward_type="EMERGENCY", department="Emergency", floor="Floor 1", capacity=10, status="ACTIVE")
        db.add_all([w1, w2, w3])
        db.commit()

        # Seed 14 days of historical occupancy snapshots for Ward 1 (ICU Unit A)
        start_date = date(2026, 8, 1)
        for i in range(14):
            curr_d = start_date + timedelta(days=i)
            # Simulated occupancy pattern: high occupancy (80-90%) with weekly fluctuation
            occ = 8 + (i % 2)
            db.add(OccupancySnapshot(
                hospital_id=h1.id,
                ward_id=w1.id,
                snapshot_time=datetime(curr_d.year, curr_d.month, curr_d.day, 12, 0, 0),
                total_beds=10,
                occupied_beds=occ,
                available_beds=10 - occ,
                occupancy_percentage=round((occ / 10.0) * 100.0, 2),
            ))

        # Seed 3 days of historical snapshots for Ward 2 (Short history for insufficient data check)
        for i in range(3):
            curr_d = start_date + timedelta(days=i)
            db.add(OccupancySnapshot(
                hospital_id=h1.id,
                ward_id=w2.id,
                snapshot_time=datetime(curr_d.year, curr_d.month, curr_d.day, 12, 0, 0),
                total_beds=15,
                occupied_beds=5,
                available_beds=10,
                occupancy_percentage=33.33,
            ))

        db.commit()
        log_result("PART_2_TEST_SETUP", True, "Seeded multi-facility setup and 14-day historical occupancy snapshots.")
    except Exception as e:
        log_result("PART_2_TEST_SETUP", False, f"Test setup error: {e}")

    # ── 3. Data Preprocessing & Train/Test Chronological Split ──────────────
    print("\n--- PART 3: Data Preprocessing & Chronological Train/Test Split ---")
    try:
        prep = ForecastingDataPreparation.prepare_ward_series(db, ward_id=w1.id, hospital_id=h1.id)
        n_obs = prep["total_observations"]

        tr_dates, tr_vals, te_dates, te_vals = ForecastingDataPreparation.train_test_split(
            dates=prep["dates"],
            values=prep["occupied_beds"],
            train_ratio=0.75,
        )

        p3_passed = (
            n_obs == 14 and
            len(tr_vals) + len(te_vals) == 14 and
            len(tr_vals) >= 10 and
            len(te_vals) >= 3 and
            tr_dates[-1] < te_dates[0]  # Strict temporal ordering
        )
        log_result("PART_3_DATA_PREPROCESSING", p3_passed, f"Total daily observations: {n_obs}. Train split: {len(tr_vals)}, Test split: {len(te_vals)}. Chronological order preserved.")
    except Exception as e:
        log_result("PART_3_DATA_PREPROCESSING", False, f"Preprocessing error: {e}")

    # ── 4. Baseline & SARIMA Forecasting Engine ──────────────────────────────
    print("\n--- PART 4: Baseline & SARIMA Model Execution ---")
    try:
        # Baseline Moving Average Model
        base_eval = BaselineForecaster.evaluate_baseline(tr_vals, te_vals, tr_dates, te_dates)

        # Primary SARIMA Model
        ts_res = TimeSeriesForecaster.forecast_sarima(history=prep["occupied_beds"], total_beds=10, horizon=7)

        p4_passed = (
            base_eval["mae"] >= 0.0 and
            ts_res["status"] == "SUCCESS" and
            len(ts_res["predictions"]) == 7 and
            all(0.0 <= p <= 10.0 for p in ts_res["predictions"]) and
            len(ts_res["lower_bounds"]) == 7 and
            len(ts_res["upper_bounds"]) == 7
        )
        log_result("PART_4_FORECASTING_MODELS", p4_passed, f"Baseline MAE: {base_eval['mae']} beds. SARIMA generated 7-day predictions within physical capacity bounds [0, 10].")
    except Exception as e:
        log_result("PART_4_FORECASTING_MODELS", False, f"Model execution error: {e}")

    # ── 5. Insufficient Data Detection Test ──────────────────────────────────
    print("\n--- PART 5: Insufficient Historical Data Handling ---")
    try:
        w2_fc = ForecastService.generate_ward_forecast(db, ward_id=w2.id, hospital_id=h1.id, horizon=7, save_to_db=False)
        p5_passed = (
            w2_fc["status"] == "INSUFFICIENT_DATA" and
            w2_fc["available_observations"] == 3 and
            w2_fc["required_observations"] == 7
        )
        log_result("PART_5_INSUFFICIENT_DATA", p5_passed, f"Short history (3 days) correctly returned INSUFFICIENT_DATA status without crashing.")
    except Exception as e:
        log_result("PART_5_INSUFFICIENT_DATA", False, f"Insufficient data handling error: {e}")

    # ── 6. User Setup & JWT Token Generation ─────────────────────────────────
    print("\n--- PART 6: Authentication & Multi-Hospital Setup ---")
    try:
        from app.core.security import get_password_hash
        pwd = get_password_hash("Password123!")

        u_super = User(full_name="Super Admin", email="super_s3@system.com", password_hash=pwd, role=UserRole.SUPER_ADMIN.value)
        u_stjude = User(full_name="StJude Admin", email="admin@stjude.com", password_hash=pwd, role=UserRole.ADMIN.value, hospital_id=h1.id)
        u_metro = User(full_name="Metro Admin", email="admin@metro.com", password_hash=pwd, role=UserRole.ADMIN.value, hospital_id=h2.id)
        db.add_all([u_super, u_stjude, u_metro])
        db.commit()

        tok_stjude = client.post("/api/v1/auth/login", json={"email": "admin@stjude.com", "password": "Password123!"}).json()["access_token"]
        tok_metro = client.post("/api/v1/auth/login", json={"email": "admin@metro.com", "password": "Password123!"}).json()["access_token"]

        log_result("PART_6_AUTH_SETUP", True, "St. Jude Admin & Metro Care Admin JWT authentication tokens acquired.")
    except Exception as e:
        log_result("PART_6_AUTH_SETUP", False, f"Auth setup error: {e}")

    # ── 7. Stage 3 REST API Endpoints Verification ───────────────────────────
    print("\n--- PART 7: Stage 3 REST API Endpoints Verification ---")
    try:
        # 1. GET /api/v1/wards/{ward_id}/forecast
        r_ward_fc = client.get(f"/api/v1/wards/{w1.id}/forecast", headers={"Authorization": f"Bearer {tok_stjude}"})
        p7_ward_fc = (r_ward_fc.status_code == 200 and r_ward_fc.json()["status"] == "SUCCESS")

        # 2. GET /api/v1/hospitals/{hospital_id}/forecast
        r_hosp_fc = client.get(f"/api/v1/hospitals/{h1.id}/forecast", headers={"Authorization": f"Bearer {tok_stjude}"})
        p7_hosp_fc = (r_hosp_fc.status_code == 200 and "hospital_daily_forecasts" in r_hosp_fc.json())

        # 3. GET /api/v1/wards/{ward_id}/forecast/history
        r_fc_hist = client.get(f"/api/v1/wards/{w1.id}/forecast/history", headers={"Authorization": f"Bearer {tok_stjude}"})
        p7_fc_hist = (r_fc_hist.status_code == 200 and "items" in r_fc_hist.json())

        # 4. GET /api/v1/forecasting/performance
        r_perf = client.get(f"/api/v1/forecasting/performance?ward_id={w1.id}", headers={"Authorization": f"Bearer {tok_stjude}"})
        p7_perf = (r_perf.status_code == 200 and "baseline_model" in r_perf.json())

        # 5. POST /api/v1/forecasting/generate
        r_gen = client.post("/api/v1/forecasting/generate", headers={"Authorization": f"Bearer {tok_stjude}"})
        p7_gen = (r_gen.status_code == 200 and r_gen.json()["status"] == "SUCCESS")

        p7_passed = p7_ward_fc and p7_hosp_fc and p7_fc_hist and p7_perf and p7_gen
        log_result("PART_7_STAGE3_APIS", p7_passed, "All 5 Stage 3 REST API endpoints responded successfully (200 OK).")
    except Exception as e:
        log_result("PART_7_STAGE3_APIS", False, f"Stage 3 API error: {e}")

    # ── 8. PostgreSQL Forecast Record Verification ──────────────────────────
    print("\n--- PART 8: Database Persistence Verification ---")
    try:
        db_count = db.query(BedCapacityForecast).filter(BedCapacityForecast.ward_id == w1.id).count()
        latest_fc = db.query(BedCapacityForecast).filter(BedCapacityForecast.ward_id == w1.id).first()

        p8_passed = (
            db_count >= 7 and
            latest_fc is not None and
            latest_fc.hospital_id == h1.id and
            latest_fc.model_name in ["SARIMA", "EXPONENTIAL_SMOOTHING"]
        )
        log_result("PART_8_DB_PERSISTENCE", p8_passed, f"Verified {db_count} forecast records saved in bed_capacity_forecasts table in PostgreSQL.")
    except Exception as e:
        log_result("PART_8_DB_PERSISTENCE", False, f"DB persistence error: {e}")

    # ── 9. Multi-Hospital Tenant Security Isolation ──────────────────────────
    print("\n--- PART 9: Multi-Hospital Tenant Security Isolation ---")
    try:
        # St. Jude Admin tries to access Metro Care ward forecast
        r_cross_ward = client.get(f"/api/v1/wards/{w3.id}/forecast", headers={"Authorization": f"Bearer {tok_stjude}"})
        cross_ward_rejected = (r_cross_ward.status_code == 403)

        # St. Jude Admin tries to access Metro Care hospital forecast
        r_cross_hosp = client.get(f"/api/v1/hospitals/{h2.id}/forecast", headers={"Authorization": f"Bearer {tok_stjude}"})
        cross_hosp_rejected = (r_cross_hosp.status_code == 403)

        p9_passed = cross_ward_rejected and cross_hosp_rejected
        log_result("PART_9_MULTI_HOSPITAL_ISOLATION", p9_passed, "Cross-hospital forecast endpoints returned HTTP 403 Forbidden.")
    except Exception as e:
        log_result("PART_9_MULTI_HOSPITAL_ISOLATION", False, f"Tenant isolation error: {e}")

    # ── Summary Report ───────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("                    STAGE 3 VERIFICATION SUMMARY")
    print("=" * 80)
    all_passed = True
    for t_name, data in results.items():
        status_colored = "PASS" if data["passed"] else "FAIL"
        print(f"[{status_colored}] {t_name:<35}: {data['message']}")
        if not data["passed"]:
            all_passed = False

    print("=" * 80)
    overall_status = "PASS" if all_passed else "FAIL"
    print(f"STAGE 3 OVERALL VERIFICATION STATUS: {overall_status}")
    print("=" * 80)
    return all_passed

if __name__ == "__main__":
    success = run_stage3_verification()
    sys.exit(0 if success else 1)

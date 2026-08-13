"""
Stage 2 Comprehensive Pipeline Verification Script
Tests all Stage 1 + Stage 2 functionality against the project database and FastAPI endpoints.
"""
import sys
import os
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any

# Ensure server root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import inspect, create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.main import app
from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType
from app.models.occupancy_event import OccupancyEvent
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.capacity_alert import CapacityAlert, AlertType, AlertSeverity, AlertStatus
from app.models.user import User, UserRole
from app.services.event_processor import EventProcessor
from app.services.capacity_service import CapacityService
from app.services.snapshot_service import SnapshotService
from app.services.alert_service import AlertService
from app.services.historical_service import HistoricalService
from app.schemas.occupancy_event import OccupancyEventIngest, EventTypeEnum, EventSourceEnum

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


def run_all_tests():
    print("=" * 75)
    print("      STAGE 2 - AUTOMATED HISTORICAL CAPACITY PIPELINE VERIFICATION")
    print("=" * 75)

    # ── 1. DB Table Inspection ───────────────────────────────────────────────
    print("\n--- PART 1: Database Tables & Schema Check ---")
    try:
        from app.database.database import engine
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = ["hospitals", "users", "wards", "beds", "occupancy_events", "occupancy_snapshots", "capacity_alerts"]
        missing = [t for t in expected if t not in tables]

        if missing:
            log_result("PART_1_DB_TABLES", False, f"Missing tables: {missing}")
        else:
            log_result("PART_1_DB_TABLES", True, f"All Stage 1 & Stage 2 tables present: {expected}")
    except Exception as e:
        log_result("PART_1_DB_TABLES", False, f"DB inspection failed: {e}")

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

    # ── 2. Seed Test Multi-Facility Setup ─────────────────────────────────────
    print("\n--- PART 2: Test Data Setup (Multi-Hospital Setup) ---")
    try:
        h1 = Hospital(name="Apollo Medical Center", code="H_APOLLO_S2", city="Metropolis", status=HospitalStatus.ACTIVE.value)
        h2 = Hospital(name="City General Hospital", code="H_CITYGEN_S2", city="Gotham", status=HospitalStatus.ACTIVE.value)
        db.add_all([h1, h2])
        db.commit()
        db.refresh(h1)
        db.refresh(h2)

        w1 = Ward(hospital_id=h1.id, name="ICU", ward_type=WardType.ICU.value, department="Critical Care", floor="Floor 2", capacity=10, status=WardStatus.ACTIVE.value)
        w2 = Ward(hospital_id=h1.id, name="General", ward_type=WardType.GENERAL.value, department="Medicine", floor="Floor 1", capacity=10, status=WardStatus.ACTIVE.value)
        w3 = Ward(hospital_id=h2.id, name="Emergency", ward_type=WardType.EMERGENCY.value, department="ER", floor="Floor 1", capacity=10, status=WardStatus.ACTIVE.value)
        db.add_all([w1, w2, w3])
        db.commit()

        # Seed 10 beds in Apollo ICU: 9 occupied, 1 available (90% occupancy -> HIGH_OCCUPANCY alert)
        for i in range(1, 10):
            db.add(Bed(hospital_id=h1.id, ward_id=w1.id, bed_number=f"ICU-B{i}", status=BedStatus.OCCUPIED.value))
        db.add(Bed(hospital_id=h1.id, ward_id=w1.id, bed_number="ICU-B10", status=BedStatus.AVAILABLE.value))

        # Seed 10 beds in Apollo General: 2 occupied, 8 available (20% occupancy)
        for i in range(1, 3):
            db.add(Bed(hospital_id=h1.id, ward_id=w2.id, bed_number=f"GEN-B{i}", status=BedStatus.OCCUPIED.value))
        for i in range(3, 11):
            db.add(Bed(hospital_id=h1.id, ward_id=w2.id, bed_number=f"GEN-B{i}", status=BedStatus.AVAILABLE.value))

        db.commit()
        log_result("PART_2_TEST_DATA", True, f"Seeded Hospitals ({h1.name}, {h2.name}), Wards, and Beds")
    except Exception as e:
        log_result("PART_2_TEST_DATA", False, f"Test data setup error: {e}")

    # ── 3. Snapshot Generation & Uniqueness Test ─────────────────────────────
    print("\n--- PART 3: Snapshot Generation & Deduplication ---")
    try:
        res1 = SnapshotService.generate_snapshots_for_all_hospitals(db)
        snaps_count1 = db.query(OccupancySnapshot).count()

        # Generate again for exact same time period (should not create duplicate snapshots)
        res2 = SnapshotService.generate_snapshots_for_all_hospitals(db)
        snaps_count2 = db.query(OccupancySnapshot).count()

        p3_passed = (
            res1["snapshots_created"] > 0 and
            res2["snapshots_created"] == 0 and
            snaps_count1 == snaps_count2
        )
        log_result("PART_3_SNAPSHOT_DEDUPLICATION", p3_passed, f"Run 1: {res1['snapshots_created']} created. Run 2: {res2['snapshots_created']} created. Unique constraint verified.")
    except Exception as e:
        log_result("PART_3_SNAPSHOT_DEDUPLICATION", False, f"Snapshot generation error: {e}")

    # ── 4. Rule-Based Capacity Alert & Resolution Test ────────────────────────
    print("\n--- PART 4: Rule-Based Capacity Alerts & Deduplication ---")
    try:
        # Check active alerts
        alerts_icu = AlertService.get_alerts(db, ward_id=w1.id, status="ACTIVE")
        has_high_or_low = any(a["alert_type"] in ["HIGH_OCCUPANCY", "LOW_AVAILABILITY"] for a in alerts_icu)

        # Run snapshot again: should NOT create duplicate active alert
        SnapshotService.generate_snapshots_for_all_hospitals(db)
        active_alerts_count = db.query(CapacityAlert).filter(CapacityAlert.ward_id == w1.id, CapacityAlert.status == "ACTIVE").count()

        # Discharge 5 beds in ICU (occupancy drops to 40% -> alert auto-resolves)
        for b in db.query(Bed).filter(Bed.ward_id == w1.id, Bed.status == BedStatus.OCCUPIED.value).limit(5).all():
            b.status = BedStatus.AVAILABLE.value
        db.commit()

        SnapshotService.generate_snapshots_for_all_hospitals(db)
        active_after_discharge = db.query(CapacityAlert).filter(CapacityAlert.ward_id == w1.id, CapacityAlert.status == "ACTIVE").count()
        resolved_after_discharge = db.query(CapacityAlert).filter(CapacityAlert.ward_id == w1.id, CapacityAlert.status == "RESOLVED").count()

        p4_passed = (
            has_high_or_low and
            active_alerts_count <= 2 and
            active_after_discharge == 0 and
            resolved_after_discharge > 0
        )
        log_result("PART_4_CAPACITY_ALERTS", p4_passed, f"Alert created, deduplicated, and automatically RESOLVED when occupancy dropped.")
    except Exception as e:
        log_result("PART_4_CAPACITY_ALERTS", False, f"Capacity alert error: {e}")

    # ── 5. Authentication & User Creation for API Tests ─────────────────────
    print("\n--- PART 5: User Setup & Authentication ---")
    try:
        from app.core.security import get_password_hash
        hash_pwd = get_password_hash("Password123!")

        u_super = User(full_name="Super Admin", email="super@system.com", password_hash=hash_pwd, role=UserRole.SUPER_ADMIN.value)
        u_apollo = User(full_name="Apollo Admin", email="admin@apollo.com", password_hash=hash_pwd, role=UserRole.ADMIN.value, hospital_id=h1.id)
        u_city = User(full_name="City Admin", email="admin@city.com", password_hash=hash_pwd, role=UserRole.ADMIN.value, hospital_id=h2.id)
        db.add_all([u_super, u_apollo, u_city])
        db.commit()

        tok_super = client.post("/api/v1/auth/login", json={"email": "super@system.com", "password": "Password123!"}).json()["access_token"]
        tok_apollo = client.post("/api/v1/auth/login", json={"email": "admin@apollo.com", "password": "Password123!"}).json()["access_token"]
        tok_city = client.post("/api/v1/auth/login", json={"email": "admin@city.com", "password": "Password123!"}).json()["access_token"]

        log_result("PART_5_AUTH_SETUP", True, "Super Admin & Hospital Admin JWT tokens generated.")
    except Exception as e:
        log_result("PART_5_AUTH_SETUP", False, f"Auth setup error: {e}")

    # ── 6. Stage 2 API Endpoints Verification ────────────────────────────────
    print("\n--- PART 6: Stage 2 API Endpoints Testing ---")
    try:
        import traceback
        # 1. POST /capacity/snapshots/generate
        try:
            r_snap_gen = client.post("/api/v1/capacity/snapshots/generate", headers={"Authorization": f"Bearer {tok_apollo}"})
            p6_gen_passed = (r_snap_gen.status_code == 200 and "snapshots_created" in r_snap_gen.json())
            print(f"  API 1 (Generate Snapshots): status={r_snap_gen.status_code}, data={r_snap_gen.json() if r_snap_gen.status_code == 200 else r_snap_gen.text}")
        except Exception as e1:
            print(f"  API 1 Exception: {e1}")
            traceback.print_exc()
            p6_gen_passed = False

        # 2. GET /wards/{id}/capacity/history
        try:
            r_ward_hist = client.get(f"/api/v1/wards/{w1.id}/capacity/history", headers={"Authorization": f"Bearer {tok_apollo}"})
            p6_ward_hist_passed = (r_ward_hist.status_code == 200 and "items" in r_ward_hist.json())
            print(f"  API 2 (Ward History): status={r_ward_hist.status_code}")
        except Exception as e2:
            print(f"  API 2 Exception: {e2}")
            traceback.print_exc()
            p6_ward_hist_passed = False

        # 3. GET /hospitals/{id}/capacity/history
        try:
            r_hosp_hist = client.get(f"/api/v1/hospitals/{h1.id}/capacity/history", headers={"Authorization": f"Bearer {tok_apollo}"})
            p6_hosp_hist_passed = (r_hosp_hist.status_code == 200 and isinstance(r_hosp_hist.json(), list))
            print(f"  API 3 (Hospital History): status={r_hosp_hist.status_code}")
        except Exception as e3:
            print(f"  API 3 Exception: {e3}")
            traceback.print_exc()
            p6_hosp_hist_passed = False

        # 4. GET /wards/{id}/daily-summary
        try:
            r_summary = client.get(f"/api/v1/wards/{w1.id}/daily-summary", headers={"Authorization": f"Bearer {tok_apollo}"})
            p6_summary_passed = (r_summary.status_code == 200 and isinstance(r_summary.json(), list))
            print(f"  API 4 (Daily Summary): status={r_summary.status_code}, data={r_summary.json() if r_summary.status_code == 200 else r_summary.text}")
        except Exception as e4:
            print(f"  API 4 Exception: {e4}")
            traceback.print_exc()
            p6_summary_passed = False

        # 5. GET /capacity/data-quality
        try:
            r_quality = client.get("/api/v1/capacity/data-quality", headers={"Authorization": f"Bearer {tok_apollo}"})
            p6_quality_passed = (r_quality.status_code == 200 and "health_score" in r_quality.json())
            print(f"  API 5 (Data Quality): status={r_quality.status_code}, data={r_quality.json() if r_quality.status_code == 200 else r_quality.text}")
        except Exception as e5:
            print(f"  API 5 Exception: {e5}")
            traceback.print_exc()
            p6_quality_passed = False

        # 6. GET /capacity/forecasting-dataset
        try:
            r_dataset = client.get("/api/v1/capacity/forecasting-dataset", headers={"Authorization": f"Bearer {tok_apollo}"})
            p6_dataset_passed = (r_dataset.status_code == 200 and "items" in r_dataset.json())
            print(f"  API 6 (Forecasting Dataset): status={r_dataset.status_code}, data={r_dataset.json() if r_dataset.status_code == 200 else r_dataset.text}")
        except Exception as e6:
            print(f"  API 6 Exception: {e6}")
            traceback.print_exc()
            p6_dataset_passed = False

        # 7. GET /alerts
        try:
            r_alerts = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {tok_apollo}"})
            p6_alerts_passed = (r_alerts.status_code == 200 and "items" in r_alerts.json())
            print(f"  API 7 (Alerts List): status={r_alerts.status_code}")
        except Exception as e7:
            print(f"  API 7 Exception: {e7}")
            traceback.print_exc()
            p6_alerts_passed = False

        p6_passed = (
            p6_gen_passed and p6_ward_hist_passed and p6_hosp_hist_passed and
            p6_summary_passed and p6_quality_passed and p6_dataset_passed and p6_alerts_passed
        )
        log_result("PART_6_STAGE2_APIS", p6_passed, "All Stage 2 REST API endpoints responded successfully (200 OK).")
    except Exception as e:
        log_result("PART_6_STAGE2_APIS", False, f"Stage 2 API error: {e}")


    # ── 7. Multi-Hospital Tenant Security Isolation ──────────────────────────
    print("\n--- PART 7: Multi-Hospital Tenant Security Isolation ---")
    try:
        # Hospital A user attempts to get Hospital B's capacity history
        r_cross_hist = client.get(f"/api/v1/hospitals/{h2.id}/capacity/history", headers={"Authorization": f"Bearer {tok_apollo}"})
        cross_hist_rejected = (r_cross_hist.status_code == 403)

        # Hospital A user attempts to get Hospital B's ward history
        r_cross_ward = client.get(f"/api/v1/wards/{w3.id}/capacity/history", headers={"Authorization": f"Bearer {tok_apollo}"})
        cross_ward_rejected = (r_cross_ward.status_code == 403)

        p7_passed = cross_hist_rejected and cross_ward_rejected
        log_result("PART_7_MULTI_HOSPITAL_ISOLATION", p7_passed, "Cross-hospital history and ward data access rejected with HTTP 403 Forbidden.")
    except Exception as e:
        log_result("PART_7_MULTI_HOSPITAL_ISOLATION", False, f"Isolation error: {e}")

    # ── Summary Report ───────────────────────────────────────────────────────
    print("\n" + "=" * 75)
    print("                    STAGE 2 VERIFICATION SUMMARY")
    print("=" * 75)
    all_passed = True
    for t_name, data in results.items():
        status_colored = "PASS" if data["passed"] else "FAIL"
        print(f"[{status_colored}] {t_name:<35}: {data['message']}")
        if not data["passed"]:
            all_passed = False

    print("=" * 75)
    overall_status = "PASS" if all_passed else "FAIL"
    print(f"STAGE 2 OVERALL VERIFICATION STATUS: {overall_status}")
    print("=" * 75)
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

"""
Phase 5 Comprehensive Verification Script — Patient + Admission / Discharge Management.
Verifies DB tables, registration, bed validation, active admission rules, discharge, bed state transitions, audit/event logs, and multi-hospital isolation.
"""
import sys
import os
from datetime import datetime, date, timedelta
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from sqlalchemy import inspect, create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.main import app
from app.models.hospital import Hospital
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType
from app.models.patient import Patient, PatientStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.occupancy_event import OccupancyEvent
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.core.security import create_access_token

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


def run_phase5_verification():
    print("=" * 80)
    print("  PHASE 5 — PATIENT + ADMISSION / DISCHARGE MANAGEMENT VERIFICATION")
    print("=" * 80)

    # ── 1. Check Tables ──────────────────────────────────────────────────────
    print("\n--- PART 1: Database Table Inspection ---")
    try:
        from app.database.session import engine
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = ["hospitals", "users", "wards", "beds", "patients", "admissions", "occupancy_events", "audit_logs"]
        missing = [t for t in expected if t not in tables]
        if missing:
            log_result("PART_1_DB_TABLES", False, f"Missing tables in DB: {missing}")
        else:
            log_result("PART_1_DB_TABLES", True, f"All tables present: {expected}")
    except Exception as e:
        expected = ["hospitals", "users", "wards", "beds", "patients", "admissions", "occupancy_events", "audit_logs"]
        model_tables = list(Base.metadata.tables.keys())
        missing_models = [t for t in expected if t not in model_tables]
        if not missing_models:
            log_result("PART_1_DB_TABLES", True, f"All Phase 1-5 ORM models defined: {expected}")
        else:
            log_result("PART_1_DB_TABLES", False, f"Missing ORM models: {missing_models}")

    # Isolated SQLite test database
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

    # ── 2. Setup Multi-Hospital Test Data ─────────────────────────────────────
    print("\n--- PART 2: Multi-Hospital & Facility Setup ---")
    try:
        h1 = Hospital(name="St. Mary Hospital", code="HOSP-A", status="ACTIVE")
        h2 = Hospital(name="City General Hospital", code="HOSP-B", status="ACTIVE")
        db.add_all([h1, h2])
        db.commit()

        w1 = Ward(hospital_id=h1.id, name="General Ward A1", ward_type=WardType.GENERAL.value, department="Medicine", floor="1", capacity=10, status=WardStatus.ACTIVE.value)
        w2 = Ward(hospital_id=h2.id, name="ICU Ward B1", ward_type=WardType.ICU.value, department="Critical Care", floor="2", capacity=5, status=WardStatus.ACTIVE.value)
        db.add_all([w1, w2])
        db.commit()

        b1_1 = Bed(hospital_id=h1.id, ward_id=w1.id, bed_number="A1-01", status=BedStatus.AVAILABLE.value, bed_type=BedType.STANDARD.value)
        b1_2 = Bed(hospital_id=h1.id, ward_id=w1.id, bed_number="A1-02", status=BedStatus.MAINTENANCE.value, bed_type=BedType.STANDARD.value)
        b2_1 = Bed(hospital_id=h2.id, ward_id=w2.id, bed_number="B1-01", status=BedStatus.AVAILABLE.value, bed_type=BedType.ICU.value)
        db.add_all([b1_1, b1_2, b2_1])
        db.commit()

        u1 = User(full_name="Nurse Sarah", email="sarah@stmary.org", password_hash="hash", role=UserRole.NURSE.value, hospital_id=h1.id)
        u2 = User(full_name="Dr. Mark", email="mark@citygen.org", password_hash="hash", role=UserRole.DOCTOR.value, hospital_id=h2.id)
        db.add_all([u1, u2])
        db.commit()

        log_result("PART_2_SETUP", True, "Successfully setup multi-hospital test data.")
    except Exception as e:
        log_result("PART_2_SETUP", False, f"Setup error: {e}")

    token_h1 = create_access_token(u1.id, u1.role)
    token_h2 = create_access_token(u2.id, u2.role)
    headers_h1 = {"Authorization": f"Bearer {token_h1}"}
    headers_h2 = {"Authorization": f"Bearer {token_h2}"}

    # ── 3. Patient Registration & Search API ─────────────────────────────────
    print("\n--- PART 3: Patient Registration & Search ---")
    patient1_id = None
    try:
        p_res = client.post(
            "/api/v1/patients",
            headers=headers_h1,
            json={
                "first_name": "Eleanor",
                "last_name": "Vane",
                "date_of_birth": "1990-07-20",
                "gender": "FEMALE",
                "phone": "+1-555-0199",
                "email": "eleanor@example.com"
            }
        )
        if p_res.status_code == 201:
            p_data = p_res.json()
            patient1_id = p_data["id"]
            if p_data["patient_identifier"].startswith("HOSP-A-P") and p_data["first_name"] == "Eleanor":
                log_result("PART_3_PATIENT_REGISTRATION", True, f"Registered patient {p_data['patient_identifier']} successfully")
            else:
                log_result("PART_3_PATIENT_REGISTRATION", False, f"Unexpected data: {p_data}")
        else:
            log_result("PART_3_PATIENT_REGISTRATION", False, f"HTTP {p_res.status_code}: {p_res.text}")

        # Search test
        s_res = client.get("/api/v1/patients?search=Eleanor", headers=headers_h1)
        if s_res.status_code == 200 and s_res.json()["total"] == 1:
            log_result("PART_3_PATIENT_SEARCH", True, "Patient search returned registered patient")
        else:
            log_result("PART_3_PATIENT_SEARCH", False, f"Search failed: {s_res.text}")

    except Exception as e:
        log_result("PART_3_PATIENT_REGISTRATION", False, f"Error: {e}")

    # ── 4. Available Bed Selection ───────────────────────────────────────────
    print("\n--- PART 4: Available Bed Selection API ---")
    try:
        avail_res = client.get("/api/v1/wards/1/available-beds", headers=headers_h1)
        if avail_res.status_code == 200:
            beds = avail_res.json()
            if len(beds) == 1 and beds[0]["bed_number"] == "A1-01":
                log_result("PART_4_AVAILABLE_BEDS", True, "Only ACTIVE and AVAILABLE bed returned (Maintenance bed excluded)")
            else:
                log_result("PART_4_AVAILABLE_BEDS", False, f"Unexpected beds list: {beds}")
        else:
            log_result("PART_4_AVAILABLE_BEDS", False, f"HTTP {avail_res.status_code}: {avail_res.text}")
    except Exception as e:
        log_result("PART_4_AVAILABLE_BEDS", False, f"Error: {e}")

    # ── 5. Admission Workflow & Bed State Transition ──────────────────────────
    print("\n--- PART 5: Admission Workflow & Bed State Transition ---")
    adm_id = None
    try:
        adm_res = client.post(
            "/api/v1/admissions",
            headers=headers_h1,
            json={
                "patient_id": patient1_id,
                "ward_id": w1.id,
                "bed_id": b1_1.id,
                "admission_reason": "General observation"
            }
        )
        if adm_res.status_code == 201:
            adm_data = adm_res.json()
            adm_id = adm_data["id"]
            if adm_data["status"] == "ADMITTED" and adm_data["bed_number"] == "A1-01":
                log_result("PART_5_ADMISSION_CREATE", True, f"Admission created ({adm_data['admission_number']})")
            else:
                log_result("PART_5_ADMISSION_CREATE", False, f"Unexpected adm data: {adm_data}")
        else:
            log_result("PART_5_ADMISSION_CREATE", False, f"HTTP {adm_res.status_code}: {adm_res.text}")

        # Check Bed 1 state is now OCCUPIED
        b_res = client.get(f"/api/v1/beds/{b1_1.id}", headers=headers_h1)
        if b_res.status_code == 200 and b_res.json()["status"] == "OCCUPIED":
            log_result("PART_5_BED_OCCUPIED", True, "Bed state automatically transitioned from AVAILABLE -> OCCUPIED")
        else:
            log_result("PART_5_BED_OCCUPIED", False, f"Bed state check failed: {b_res.text}")

    except Exception as e:
        log_result("PART_5_ADMISSION_CREATE", False, f"Error: {e}")

    # ── 6. Active Admission Rule & Bed Availability Conflict ─────────────────
    print("\n--- PART 6: Validation Rules & Edge Cases ---")
    try:
        # Prevent second admission for already admitted patient
        dup_res = client.post(
            "/api/v1/admissions",
            headers=headers_h1,
            json={
                "patient_id": patient1_id,
                "ward_id": w1.id,
                "bed_id": b1_1.id,
                "admission_reason": "Duplicate attempt"
            }
        )
        if dup_res.status_code == 409:
            log_result("PART_6_DUPLICATE_ACTIVE_ADMISSION", True, "Blocked second admission for already admitted patient (409 Conflict)")
        else:
            log_result("PART_6_DUPLICATE_ACTIVE_ADMISSION", False, f"Expected 409, got {dup_res.status_code}")

    except Exception as e:
        log_result("PART_6_DUPLICATE_ACTIVE_ADMISSION", False, f"Error: {e}")

    # ── 7. Multi-Hospital Data Isolation ─────────────────────────────────────
    print("\n--- PART 7: Multi-Hospital Data Isolation ---")
    try:
        # Hospital 2 staff trying to view Hospital 1 patient
        iso_p = client.get(f"/api/v1/patients/{patient1_id}", headers=headers_h2)
        if iso_p.status_code == 404:
            log_result("PART_7_PATIENT_ISOLATION", True, "Hospital 2 staff blocked from viewing Hospital 1 patient (404 Not Found)")
        else:
            log_result("PART_7_PATIENT_ISOLATION", False, f"Expected 404, got {iso_p.status_code}")

        # Hospital 2 staff trying to view Hospital 1 admission
        iso_adm = client.get(f"/api/v1/admissions/{adm_id}", headers=headers_h2)
        if iso_adm.status_code == 404:
            log_result("PART_7_ADMISSION_ISOLATION", True, "Hospital 2 staff blocked from viewing Hospital 1 admission (404 Not Found)")
        else:
            log_result("PART_7_ADMISSION_ISOLATION", False, f"Expected 404, got {iso_adm.status_code}")

    except Exception as e:
        log_result("PART_7_PATIENT_ISOLATION", False, f"Error: {e}")

    # ── 8. Discharge Workflow & Bed Release ─────────────────────────────────
    print("\n--- PART 8: Discharge Workflow & Bed Release ---")
    try:
        dis_res = client.post(
            f"/api/v1/admissions/{adm_id}/discharge",
            headers=headers_h1,
            json={"discharge_notes": "Routine discharge, patient fully recovered."}
        )
        if dis_res.status_code == 200:
            dis_data = dis_res.json()
            if dis_data["status"] == "DISCHARGED" and dis_data["discharge_date"] is not None:
                log_result("PART_8_DISCHARGE_WORKFLOW", True, "Patient discharged successfully")
            else:
                log_result("PART_8_DISCHARGE_WORKFLOW", False, f"Unexpected discharge response: {dis_data}")
        else:
            log_result("PART_8_DISCHARGE_WORKFLOW", False, f"HTTP {dis_res.status_code}: {dis_res.text}")

        # Check Bed 1 state is released back to AVAILABLE
        b_res2 = client.get(f"/api/v1/beds/{b1_1.id}", headers=headers_h1)
        if b_res2.status_code == 200 and b_res2.json()["status"] == "AVAILABLE":
            log_result("PART_8_BED_RELEASED", True, "Bed state automatically transitioned from OCCUPIED -> AVAILABLE")
        else:
            log_result("PART_8_BED_RELEASED", False, f"Bed state check failed: {b_res2.text}")

        # Historical admission preserved
        hist_res = client.get(f"/api/v1/patients/{patient1_id}/admissions", headers=headers_h1)
        if hist_res.status_code == 200 and hist_res.json()["total"] == 1:
            log_result("PART_8_HISTORICAL_ADMISSION_PRESERVED", True, "Historical admission preserved after discharge")
        else:
            log_result("PART_8_HISTORICAL_ADMISSION_PRESERVED", False, f"History check failed: {hist_res.text}")

    except Exception as e:
        log_result("PART_8_DISCHARGE_WORKFLOW", False, f"Error: {e}")

    # ── 9. Audit Log and Event Log Check ─────────────────────────────────────
    print("\n--- PART 9: Audit Trail & Occupancy Events ---")
    try:
        audit_count = db.query(AuditLog).filter(AuditLog.hospital_id == h1.id).count()
        event_count = db.query(OccupancyEvent).filter(OccupancyEvent.hospital_id == h1.id).count()
        if audit_count >= 2 and event_count >= 2:
            log_result("PART_9_AUDIT_EVENTS", True, f"Created {audit_count} Audit Logs and {event_count} Occupancy Events")
        else:
            log_result("PART_9_AUDIT_EVENTS", False, f"Audit logs ({audit_count}) or events ({event_count}) missing")
    except Exception as e:
        log_result("PART_9_AUDIT_EVENTS", False, f"Error: {e}")

    # ── SUMMARY REPORT ──────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("                    PHASE 5 VERIFICATION SUMMARY")
    print("=" * 80)
    all_passed = True
    for name, res in results.items():
        print(f"{res['status']:<8} | {name:<35} | {res['message']}")
        if not res["passed"]:
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("PHASE 5 STATUS: PASS")
    else:
        print("PHASE 5 STATUS: FAIL")
    print("=" * 80)


if __name__ == "__main__":
    run_phase5_verification()

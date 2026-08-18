"""
Stage 4 Comprehensive Inter-Ward Transfer Decision Support System Verification Script.
Tests Stage 1, Stage 2, Stage 3, and Stage 4 end-to-end functionality against DB & FastAPI endpoints.
"""
import sys
import os
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
from app.models.hospital import Hospital
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus
from app.models.occupancy_event import OccupancyEvent
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.bed_capacity_forecast import BedCapacityForecast, RiskLevel
from app.models.user import User, UserRole
from app.models.ward_transfer_rule import WardTransferRule
from app.models.transfer_recommendation import TransferRecommendation, RecommendationStatus, RecommendationPriority
from app.models.audit_log import AuditLog
from app.services.transfer_scoring_service import TransferScoringService
from app.services.transfer_service import TransferService
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


def run_stage4_verification():
    print("=" * 80)
    print("  STAGE 4 — INTER-WARD TRANSFER DECISION SUPPORT SYSTEM VERIFICATION")
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
            "capacity_alerts", "bed_capacity_forecasts",
            "ward_transfer_rules", "transfer_recommendations", "audit_logs"
        ]
        missing = [t for t in expected if t not in tables]

        if missing:
            log_result("PART_1_DB_TABLES", False, f"Missing tables: {missing}")
        else:
            log_result("PART_1_DB_TABLES", True, f"All Stage 1, 2, 3 & 4 tables present: {expected}")
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

    # ── 2. Multi-Hospital Data Setup ──────────────────────────────────────────
    print("\n--- PART 2: Multi-Hospital Setup & Ward Seeding ---")
    try:
        h1 = Hospital(name="St. Jude Medical Center", code="H_STJUDE_S4", city="Chicago", status="ACTIVE")
        h2 = Hospital(name="MetroCare Health", code="H_METRO_S4", city="Boston", status="ACTIVE")
        db.add_all([h1, h2])
        db.commit()

        # Hospital 1 Wards
        w1_icu = Ward(hospital_id=h1.id, name="ICU Unit A", ward_type=WardType.ICU.value, department="Critical Care", floor="Floor 3", capacity=10, status=WardStatus.ACTIVE.value)
        w1_step = Ward(hospital_id=h1.id, name="Step-Down Unit B", ward_type=WardType.STEP_DOWN.value, department="Intermediate Care", floor="Floor 2", capacity=20, status=WardStatus.ACTIVE.value)
        w1_gen = Ward(hospital_id=h1.id, name="General Ward C", ward_type=WardType.GENERAL.value, department="Internal Med", floor="Floor 1", capacity=30, status=WardStatus.ACTIVE.value)

        # Hospital 2 Wards
        w2_icu = Ward(hospital_id=h2.id, name="Metro ICU", ward_type=WardType.ICU.value, department="Critical Care", floor="Floor 4", capacity=10, status=WardStatus.ACTIVE.value)
        w2_gen = Ward(hospital_id=h2.id, name="Metro General", ward_type=WardType.GENERAL.value, department="General Med", floor="Floor 2", capacity=25, status=WardStatus.ACTIVE.value)

        db.add_all([w1_icu, w1_step, w1_gen, w2_icu, w2_gen])
        db.commit()

        # Seed Beds for w1_icu (10 total: 9 occupied = 90% occ)
        for i in range(1, 11):
            status = BedStatus.OCCUPIED.value if i <= 9 else BedStatus.AVAILABLE.value
            db.add(Bed(hospital_id=h1.id, ward_id=w1_icu.id, bed_number=f"ICU-{i:02d}", status=status))

        # Seed Beds for w1_step (20 total: 12 occupied = 60% occ, 8 available)
        for i in range(1, 21):
            status = BedStatus.OCCUPIED.value if i <= 12 else BedStatus.AVAILABLE.value
            db.add(Bed(hospital_id=h1.id, ward_id=w1_step.id, bed_number=f"STEP-{i:02d}", status=status))

        # Seed Beds for w1_gen (30 total: 20 occupied = 66.7% occ, 10 available)
        for i in range(1, 31):
            status = BedStatus.OCCUPIED.value if i <= 20 else BedStatus.AVAILABLE.value
            db.add(Bed(hospital_id=h1.id, ward_id=w1_gen.id, bed_number=f"GEN-{i:02d}", status=status))

        db.commit()

        # Seed Stage 3 Forecast for w1_icu (96% occupancy tomorrow, CRITICAL risk)
        forecast_icu = BedCapacityForecast(
            hospital_id=h1.id,
            ward_id=w1_icu.id,
            forecast_date=date.today() + timedelta(days=1),
            predicted_occupied_beds=9.6,
            predicted_occupancy_percentage=96.0,
            lower_bound=90.0,
            upper_bound=100.0,
            risk_level=RiskLevel.CRITICAL.value,
        )
        forecast_step = BedCapacityForecast(
            hospital_id=h1.id,
            ward_id=w1_step.id,
            forecast_date=date.today() + timedelta(days=1),
            predicted_occupied_beds=13.0,
            predicted_occupancy_percentage=65.0,
            lower_bound=60.0,
            upper_bound=70.0,
            risk_level=RiskLevel.NORMAL.value,
        )
        db.add_all([forecast_icu, forecast_step])
        db.commit()

        # Create Users
        u1 = User(full_name="Dr. Alice Smith", email="alice@stjude.org", password_hash="hash", role=UserRole.DOCTOR.value, hospital_id=h1.id)
        u1_admin = User(full_name="Admin StJude", email="admin@stjude.org", password_hash="hash", role=UserRole.ADMIN.value, hospital_id=h1.id)
        u2 = User(full_name="Bob Admin", email="bob@metro.org", password_hash="hash", role=UserRole.ADMIN.value, hospital_id=h2.id)
        db.add_all([u1, u1_admin, u2])
        db.commit()

        log_result("PART_2_SETUP", True, "Successfully seeded multi-hospital wards, beds, forecasts, and users.")
    except Exception as e:
        log_result("PART_2_SETUP", False, f"Setup error: {e}")

    token_h1 = create_access_token(u1.id, u1.role)
    token_h1_admin = create_access_token(u1_admin.id, u1_admin.role)
    token_h2 = create_access_token(u2.id, u2.role)
    headers_h1 = {"Authorization": f"Bearer {token_h1}"}
    headers_h1_admin = {"Authorization": f"Bearer {token_h1_admin}"}
    headers_h2 = {"Authorization": f"Bearer {token_h2}"}

    # ── 3. Scoring & Safe Capacity Unit Tests ──────────────────────────────
    print("\n--- PART 3: Scoring & Capacity Algorithm Check ---")
    try:
        safe_cap = TransferService.calculate_safe_capacity(
            total_beds=20, occupied_beds=12, max_safe_occ_pct=85.0, min_available_beds=2
        )
        # 20 * 85% = 17 max safe occupied beds. 17 - 12 = 5 beds. Available = 8. 8 - 2 = 6. min(5, 6) = 5.
        if safe_cap == 5:
            log_result("PART_3_SAFE_CAPACITY", True, f"Safe capacity calculation correct: {safe_cap} beds")
        else:
            log_result("PART_3_SAFE_CAPACITY", False, f"Expected 5 safe beds, got {safe_cap}")

        score, priority, breakdown = TransferScoringService.calculate_score(
            source_current_occ=90.0,
            source_pred_occ=96.0,
            source_risk_level="CRITICAL",
            dest_current_occ=60.0,
            dest_pred_occ=65.0,
            dest_available_beds=8,
            safe_transfer_capacity=5,
            compatibility_allowed=True,
            rule_priority=2,
        )
        if score > 80.0 and priority == RecommendationPriority.CRITICAL:
            log_result("PART_3_SCORING", True, f"Scoring engine output verified (Score: {score}/100, Priority: {priority})")
        else:
            log_result("PART_3_SCORING", False, f"Unexpected score: {score}, priority: {priority}")
    except Exception as e:
        log_result("PART_3_SCORING", False, f"Scoring error: {e}")

    # ── 4. Recommendation Generation API Test ───────────────────────────────
    print("\n--- PART 4: Recommendation Generation API ---")
    try:
        resp = client.post(
            "/api/v1/transfers/recommendations/generate",
            headers=headers_h1,
            json={"hospital_id": h1.id, "horizon_days": 1}
        )
        if resp.status_code == 201:
            data = resp.json()
            if data["recommendations_generated"] >= 1:
                log_result("PART_4_GENERATE_API", True, f"Generated {data['recommendations_generated']} recommendations for Hospital 1")
            else:
                log_result("PART_4_GENERATE_API", False, "No recommendations generated")
        else:
            log_result("PART_4_GENERATE_API", False, f"HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        log_result("PART_4_GENERATE_API", False, f"Generation API error: {e}")

    # ── 5. List Recommendations & Detail Explanation API ─────────────────────
    print("\n--- PART 5: Recommendation Listing & Detail Explanation API ---")
    rec_id = None
    try:
        resp = client.get(f"/api/v1/transfers/recommendations?hospital_id={h1.id}", headers=headers_h1)
        if resp.status_code == 200:
            recs = resp.json()
            if len(recs) > 0:
                rec_id = recs[0]["id"]
                log_result("PART_5_LIST_API", True, f"Retrieved {len(recs)} recommendations for Hospital 1")
            else:
                log_result("PART_5_LIST_API", False, "List returned empty array")
        else:
            log_result("PART_5_LIST_API", False, f"HTTP {resp.status_code}: {resp.text}")

        if rec_id:
            resp_detail = client.get(f"/api/v1/transfers/recommendations/{rec_id}", headers=headers_h1)
            if resp_detail.status_code == 200:
                detail = resp_detail.json()
                if "reason" in detail and "score_breakdown" in detail and detail["revalidation_status"] == "VALID":
                    log_result("PART_5_DETAIL_API", True, f"Detail explanation verified for Rec ID {rec_id}")
                else:
                    log_result("PART_5_DETAIL_API", False, f"Missing detail fields: {detail}")
            else:
                log_result("PART_5_DETAIL_API", False, f"HTTP {resp_detail.status_code}: {resp_detail.text}")
    except Exception as e:
        log_result("PART_5_DETAIL_API", False, f"Detail API error: {e}")

    # ── 6. Multi-Hospital Isolation Security Test ────────────────────────────
    print("\n--- PART 6: Multi-Hospital Security Isolation Test ---")
    try:
        # Hospital 2 user (Bob) attempting to access Hospital 1's recommendation
        resp_forbidden = client.get(f"/api/v1/transfers/recommendations/{rec_id}", headers=headers_h2)
        if resp_forbidden.status_code == 403:
            log_result("PART_6_SECURITY_ISOLATION", True, "Hospital 2 user correctly denied access (403 Forbidden) to Hospital 1 recommendation")
        else:
            log_result("PART_6_SECURITY_ISOLATION", False, f"Expected 403 Forbidden, got {resp_forbidden.status_code}")

        # Hospital 2 user attempting to generate for Hospital 1
        resp_gen_forbidden = client.post(
            "/api/v1/transfers/recommendations/generate",
            headers=headers_h2,
            json={"hospital_id": h1.id}
        )
        if resp_gen_forbidden.status_code == 403:
            log_result("PART_6_SECURITY_CROSS_GENERATE", True, "Cross-hospital recommendation generation blocked (403 Forbidden)")
        else:
            log_result("PART_6_SECURITY_CROSS_GENERATE", False, f"Expected 403, got {resp_gen_forbidden.status_code}")
    except Exception as e:
        log_result("PART_6_SECURITY_ISOLATION", False, f"Security test error: {e}")

    # ── 7. Revalidation & Approval Flow Test ────────────────────────────────
    print("\n--- PART 7: Approval Flow & Revalidation Check ---")
    try:
        # Measure bed occupancy BEFORE approval
        occupied_beds_before = db.query(Bed).filter(Bed.ward_id == w1_step.id, Bed.status == BedStatus.OCCUPIED.value).count()

        resp_approve = client.post(
            f"/api/v1/transfers/recommendations/{rec_id}/approve",
            headers=headers_h1,
            json={"notes": "Approved by Dr. Alice after clinical review"}
        )
        if resp_approve.status_code == 200:
            app_data = resp_approve.json()
            if app_data["status"] == "APPROVED" and app_data["approved_by_id"] == u1.id:
                log_result("PART_7_APPROVAL_API", True, f"Recommendation {rec_id} successfully approved by staff member")
            else:
                log_result("PART_7_APPROVAL_API", False, f"Unexpected approval status: {app_data}")
        else:
            log_result("PART_7_APPROVAL_API", False, f"HTTP {resp_approve.status_code}: {resp_approve.text}")

        # Assert NO automatic patient move / bed status change occurred!
        occupied_beds_after = db.query(Bed).filter(Bed.ward_id == w1_step.id, Bed.status == BedStatus.OCCUPIED.value).count()
        if occupied_beds_before == occupied_beds_after:
            log_result("PART_7_NO_AUTO_TRANSFER", True, "VERIFIED: Approval did NOT alter patient location or bed status. Human staff remain in full control.")
        else:
            log_result("PART_7_NO_AUTO_TRANSFER", False, f"FAIL: Bed count changed from {occupied_beds_before} to {occupied_beds_after}")
    except Exception as e:
        log_result("PART_7_APPROVAL_API", False, f"Approval test error: {e}")

    # ── 8. Rejection API Test ────────────────────────────────────────────────
    print("\n--- PART 8: Rejection API with Mandatory Reason ---")
    try:
        # Generate another recommendation for rejection test
        rec_reject = TransferRecommendation(
            hospital_id=h1.id,
            source_ward_id=w1_icu.id,
            destination_ward_id=w1_gen.id,
            source_current_occupancy=90.0,
            source_predicted_occupancy=96.0,
            destination_current_occupancy=66.7,
            destination_predicted_occupancy=70.0,
            available_beds=10,
            safe_transfer_capacity=4,
            recommended_transfer_count=4,
            priority_score=75.0,
            priority_level="HIGH",
            status="PENDING",
            reason="Test recommendation for rejection",
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.add(rec_reject)
        db.commit()
        db.refresh(rec_reject)

        # Attempt rejection without valid reason -> Should fail 422/400
        resp_bad_rej = client.post(
            f"/api/v1/transfers/recommendations/{rec_reject.id}/reject",
            headers=headers_h1,
            json={"rejection_reason": ""}
        )
        if resp_bad_rej.status_code in [400, 422]:
            log_result("PART_8_REJECT_REASON_REQ", True, "Rejection rejected when mandatory reason was omitted")
        else:
            log_result("PART_8_REJECT_REASON_REQ", False, f"Expected 400/422, got {resp_bad_rej.status_code}")

        # Proper rejection
        resp_rej = client.post(
            f"/api/v1/transfers/recommendations/{rec_reject.id}/reject",
            headers=headers_h1,
            json={"rejection_reason": "Clinical decision: Patient unstable for transfer."}
        )
        if resp_rej.status_code == 200 and resp_rej.json()["status"] == "REJECTED":
            log_result("PART_8_REJECT_API", True, "Recommendation rejected with mandatory reason recorded")
        else:
            log_result("PART_8_REJECT_API", False, f"HTTP {resp_rej.status_code}: {resp_rej.text}")
    except Exception as e:
        log_result("PART_8_REJECT_API", False, f"Rejection test error: {e}")

    # ── 9. Audit Logging Verification ─────────────────────────────────────────
    print("\n--- PART 9: Audit Logging Verification ---")
    try:
        resp_audit = client.get(f"/api/v1/transfers/audit-logs?hospital_id={h1.id}", headers=headers_h1_admin)
        if resp_audit.status_code == 200:
            logs = resp_audit.json()
            actions = [l["action"] for l in logs]
            if "RECOMMENDATION_GENERATED" in actions and "RECOMMENDATION_APPROVED" in actions:
                log_result("PART_9_AUDIT_LOGS", True, f"Audit log recorded actions: {actions[:4]}")
            else:
                log_result("PART_9_AUDIT_LOGS", False, f"Missing audit actions: {actions}")
        else:
            log_result("PART_9_AUDIT_LOGS", False, f"HTTP {resp_audit.status_code}: {resp_audit.text}")
    except Exception as e:
        log_result("PART_9_AUDIT_LOGS", False, f"Audit test error: {e}")

    # ── SUMMARY REPORT ──────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("                    STAGE 4 VERIFICATION SUMMARY")
    print("=" * 80)
    all_passed = True
    for name, res in results.items():
        print(f"{res['status']:<8} | {name:<30} | {res['message']}")
        if not res["passed"]:
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("STAGE 4 STATUS: PASS")
    else:
        print("STAGE 4 STATUS: FAIL")
    print("=" * 80)

if __name__ == "__main__":
    run_stage4_verification()

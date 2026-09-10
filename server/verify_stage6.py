import sys
import json
from datetime import datetime, date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.database.session import SessionLocal, engine, Base
from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType
from app.models.user import User, UserRole
from app.models.patient import Patient, PatientStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.occupancy_event import OccupancyEvent
from app.models.audit_log import AuditLog
from app.services.patient_service import PatientService
from app.services.admission_service import AdmissionService
from app.services.capacity_service import CapacityService
from app.services.snapshot_service import SnapshotService
from app.schemas.patient import PatientCreate
from app.schemas.admission import AdmissionCreate, DischargeCreate
from app.schemas.capacity import get_capacity_status, CapacityStatusEnum
from app.main import app

def log_test(name: str, passed: bool, detail: str = ""):
    status_str = "[PASS]" if passed else "[FAIL]"
    print(f"{status_str} {name}: {detail}")
    return passed

def run_verification():
    print("=" * 80)
    print("  PHASE 6 — OCCUPANCY & CAPACITY TRACKING VERIFICATION")
    print("=" * 80)

    db = SessionLocal()
    client = TestClient(app)
    results = {}

    try:
        # PART 1: Database Table Inspection
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        required_tables = ["hospitals", "wards", "beds", "patients", "admissions", "occupancy_snapshots", "occupancy_events", "audit_logs"]
        missing = [t for t in required_tables if t not in table_names]
        results["PART_1_DB_TABLES"] = log_test(
            "PART_1_DB_TABLES",
            len(missing) == 0,
            f"All tables present: {required_tables}" if len(missing) == 0 else f"Missing tables: {missing}"
        )

        # PART 2: Clean Setup for Test Hospitals
        db.query(AuditLog).delete()
        db.query(OccupancyEvent).delete()
        db.query(OccupancySnapshot).delete()
        db.query(Admission).delete()
        db.query(Patient).delete()
        db.query(Bed).delete()
        db.query(Ward).delete()
        db.query(User).filter(User.email.like("%@v6test.com")).delete()
        db.query(Hospital).filter(Hospital.code.like("HOSP-V6-%")).delete()
        db.commit()

        hosp1 = Hospital(name="Phase 6 Hospital 1", code="HOSP-V6-1", status=HospitalStatus.ACTIVE.value)
        hosp2 = Hospital(name="Phase 6 Hospital 2", code="HOSP-V6-2", status=HospitalStatus.ACTIVE.value)
        db.add_all([hosp1, hosp2])
        db.commit()

        # Create Ward with 10 total beds (4 OCCUPIED, 4 AVAILABLE, 1 MAINTENANCE, 1 INACTIVE)
        ward1 = Ward(hospital_id=hosp1.id, name="ICU Unit 1", ward_type=WardType.ICU.value, department="Critical Care", floor="1", capacity=10, status=WardStatus.ACTIVE.value)
        ward2 = Ward(hospital_id=hosp2.id, name="General Ward 2", ward_type=WardType.GENERAL.value, department="General Medicine", floor="2", capacity=5, status=WardStatus.ACTIVE.value)
        db.add_all([ward1, ward2])
        db.commit()

        for i in range(1, 5):
            db.add(Bed(ward_id=ward1.id, hospital_id=hosp1.id, bed_number=f"ICU-10{i}", bed_type=BedType.ICU.value, status=BedStatus.OCCUPIED.value))
        for i in range(5, 9):
            db.add(Bed(ward_id=ward1.id, hospital_id=hosp1.id, bed_number=f"ICU-10{i}", bed_type=BedType.ICU.value, status=BedStatus.AVAILABLE.value))
        db.add(Bed(ward_id=ward1.id, hospital_id=hosp1.id, bed_number="ICU-109", bed_type=BedType.ICU.value, status=BedStatus.MAINTENANCE.value))
        db.add(Bed(ward_id=ward1.id, hospital_id=hosp1.id, bed_number="ICU-110", bed_type=BedType.ICU.value, status="INACTIVE"))

        for i in range(1, 4):
            db.add(Bed(ward_id=ward2.id, hospital_id=hosp2.id, bed_number=f"GEN-20{i}", bed_type=BedType.STANDARD.value, status=BedStatus.AVAILABLE.value))
        db.commit()

        # Register users via auth endpoint
        client.post("/api/v1/auth/register", json={"full_name": "Dr. Staff A", "email": "doc_a@v6test.com", "password": "Password123!", "role": "doctor", "hospital_id": hosp1.id})
        client.post("/api/v1/auth/register", json={"full_name": "Dr. Staff B", "email": "doc_b@v6test.com", "password": "Password123!", "role": "doctor", "hospital_id": hosp2.id})
        client.post("/api/v1/auth/register", json={"full_name": "Admin V6", "email": "admin@v6test.com", "password": "Password123!", "role": "admin", "hospital_id": hosp1.id})

        res_login1 = client.post("/api/v1/auth/login", json={"email": "doc_a@v6test.com", "password": "Password123!"})
        res_login2 = client.post("/api/v1/auth/login", json={"email": "doc_b@v6test.com", "password": "Password123!"})
        res_login_admin = client.post("/api/v1/auth/login", json={"email": "admin@v6test.com", "password": "Password123!"})

        headers1 = {"Authorization": f"Bearer {res_login1.json()['access_token']}"}
        headers2 = {"Authorization": f"Bearer {res_login2.json()['access_token']}"}
        headers_admin = {"Authorization": f"Bearer {res_login_admin.json()['access_token']}"}

        user1 = db.query(User).filter(User.email == "doc_a@v6test.com").first()

        results["PART_2_SETUP"] = log_test("PART_2_SETUP", True, "Multi-hospital test fixture seeded")

        # PART 3: Operational Beds & Occupancy Formula Verification
        cap1 = CapacityService.get_hospital_capacity(db, hosp1.id)
        # Total = 10, Operational = 8 (4 occupied + 4 available), Occupancy % = 4 / 8 * 100 = 50.0%
        valid_formula = (
            cap1.total_beds == 10 and
            cap1.operational_beds == 8 and
            cap1.occupied_beds == 4 and
            cap1.available_beds == 4 and
            cap1.maintenance_beds == 1 and
            cap1.inactive_beds == 1 and
            cap1.occupancy_percentage == 50.0 and
            cap1.available_capacity_percentage == 50.0 and
            cap1.status == "NORMAL"
        )
        results["PART_3_FORMULA_CHECK"] = log_test(
            "PART_3_FORMULA_CHECK",
            valid_formula,
            f"Operational Beds={cap1.operational_beds}, Occupancy={cap1.occupancy_percentage}%, AvailCap={cap1.available_capacity_percentage}%"
        )

        # PART 4: Threshold Logic Verification
        t_norm = get_capacity_status(65.0) == CapacityStatusEnum.NORMAL
        t_warn = get_capacity_status(75.0) == CapacityStatusEnum.WARNING
        t_high = get_capacity_status(88.0) == CapacityStatusEnum.HIGH
        t_crit = get_capacity_status(96.0) == CapacityStatusEnum.CRITICAL
        results["PART_4_THRESHOLDS"] = log_test("PART_4_THRESHOLDS", t_norm and t_warn and t_high and t_crit, "NORMAL <70%, WARNING 70-85%, HIGH 85-95%, CRITICAL >=95%")

        # PART 5: Admission Real-Time Occupancy Change
        patient = PatientService.create_patient(
            db,
            patient_in=PatientCreate(
                first_name="Test", last_name="Admission", date_of_birth=date(1985, 5, 20),
                gender="MALE", phone="+1-555-9999"
            ),
            hospital_id=hosp1.id,
            user_id=user1.id
        )

        bed_to_admit = db.query(Bed).filter(Bed.bed_number == "ICU-105").first()
        adm = AdmissionService.admit_patient(
            db,
            admission_in=AdmissionCreate(
                patient_id=patient.id, ward_id=ward1.id, bed_id=bed_to_admit.id,
                admission_reason="V6 Verification Stay", hospital_id=hosp1.id
            ),
            hospital_id=hosp1.id,
            user_id=user1.id
        )

        cap1_after_adm = CapacityService.get_hospital_capacity(db, hosp1.id)
        # Now: 5 occupied, 3 available. Operational = 8. Occupancy = 5 / 8 * 100 = 62.5%
        adm_occupancy_passed = (
            cap1_after_adm.occupied_beds == 5 and
            cap1_after_adm.available_beds == 3 and
            cap1_after_adm.occupancy_percentage == 62.5 and
            cap1_after_adm.active_admissions == 1
        )
        results["PART_5_ADMISSION_OCCUPANCY"] = log_test(
            "PART_5_ADMISSION_OCCUPANCY",
            adm_occupancy_passed,
            f"Occupied increased 4->5, Occupancy % increased 50%->{cap1_after_adm.occupancy_percentage}%"
        )

        # PART 6: Discharge Real-Time Occupancy Change
        discharged_adm = AdmissionService.discharge_patient(
            db,
            admission_id=adm.id,
            discharge_in=DischargeCreate(discharge_notes="Recovered"),
            hospital_id=hosp1.id,
            user_id=user1.id
        )

        cap1_after_dis = CapacityService.get_hospital_capacity(db, hosp1.id)
        # Now: 4 occupied, 4 available. Occupancy = 50.0%
        dis_occupancy_passed = (
            cap1_after_dis.occupied_beds == 4 and
            cap1_after_dis.available_beds == 4 and
            cap1_after_dis.occupancy_percentage == 50.0 and
            cap1_after_dis.discharges_today == 1
        )
        results["PART_6_DISCHARGE_OCCUPANCY"] = log_test(
            "PART_6_DISCHARGE_OCCUPANCY",
            dis_occupancy_passed,
            f"Occupied decreased 5->4, Occupancy % decreased 62.5%->{cap1_after_dis.occupancy_percentage}%"
        )

        # PART 7: Occupancy Snapshots API Verification
        res_snap = client.post("/api/v1/occupancy/snapshots", headers=headers_admin)
        snap_passed = res_snap.status_code == 200 and res_snap.json().get("snapshots_created") >= 1
        results["PART_7_SNAPSHOT_API"] = log_test("PART_7_SNAPSHOT_API", snap_passed, f"Snapshot creation response: {res_snap.json()}")

        # PART 8: Historical Trend API Verification
        res_trend = client.get("/api/v1/occupancy/trends", headers=headers1)
        trend_passed = res_trend.status_code == 200
        results["PART_8_TREND_API"] = log_test("PART_8_TREND_API", trend_passed, "Historical trend snapshots fetched successfully")

        # PART 9: Multi-Hospital Occupancy Data Isolation
        res_iso = client.get(f"/api/v1/occupancy/hospital?hospital_id={hosp1.id}", headers=headers2)
        iso_passed = res_iso.status_code == 403
        results["PART_9_TENANT_ISOLATION"] = log_test("PART_9_TENANT_ISOLATION", iso_passed, f"Hospital 2 user blocked from viewing Hospital 1 capacity (HTTP {res_iso.status_code})")

    finally:
        db.close()

    print("=" * 80)
    print("                    PHASE 6 VERIFICATION SUMMARY")
    print("=" * 80)
    all_pass = True
    for key, passed in results.items():
        status_str = "PASS" if passed else "FAIL"
        print(f"{status_str:<8} | {key}")
        if not passed:
            all_pass = False
    print("=" * 80)
    if all_pass:
        print("PHASE 6 STATUS: PASS")
    else:
        print("PHASE 6 STATUS: INCOMPLETE")
    print("=" * 80)
    return all_pass

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)

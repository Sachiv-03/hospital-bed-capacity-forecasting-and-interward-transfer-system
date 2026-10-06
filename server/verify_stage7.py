import sys
import os
from datetime import datetime, date

# Append app root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database.session import SessionLocal, engine
from app.models.hospital import Hospital, HospitalStatus
from app.models.user import User, UserRole
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType
from app.models.patient import Patient, PatientStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.transfer import Transfer, TransferStatus
from app.services.patient_transfer_service import PatientTransferService


def run_stage7_verification():
    print("=" * 70)
    print("STAGE 7 VERIFICATION: PATIENT INTER-WARD TRANSFERS & ATOMIC TRANSACTIONS")
    print("=" * 70)

    db: Session = SessionLocal()

    try:
        # 1. Setup Test Hospital
        hospital = db.query(Hospital).filter(Hospital.code == "STAGE7_TEST").first()
        if not hospital:
            hospital = Hospital(
                name="Stage 7 Memorial Hospital",
                code="STAGE7_TEST",
                status=HospitalStatus.ACTIVE.value,
            )
            db.add(hospital)
            db.commit()
            db.refresh(hospital)
        print(f"[1] Test Hospital ready: ID={hospital.id} ({hospital.name})")

        # 2. Setup Test User
        user = db.query(User).filter(User.email == "doctor.stage7@hospital.org").first()
        if not user:
            user = User(
                full_name="Dr. Stage 7 Test",
                email="doctor.stage7@hospital.org",
                password_hash="hashed_pw",
                role=UserRole.DOCTOR.value,
                hospital_id=hospital.id,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        print(f"[2] Test Doctor User ready: ID={user.id}")

        # 3. Setup Wards (Ward A: ICU, Ward B: Step-Down General)
        ward_a = db.query(Ward).filter(Ward.hospital_id == hospital.id, Ward.name == "Ward A (ICU)").first()
        if not ward_a:
            ward_a = Ward(
                hospital_id=hospital.id,
                name="Ward A (ICU)",
                ward_type=WardType.ICU.value,
                department="Critical Care",
                floor="3",
                capacity=10,
                status=WardStatus.ACTIVE.value,
            )
            db.add(ward_a)
            db.commit()
            db.refresh(ward_a)

        ward_b = db.query(Ward).filter(Ward.hospital_id == hospital.id, Ward.name == "Ward B (General)").first()
        if not ward_b:
            ward_b = Ward(
                hospital_id=hospital.id,
                name="Ward B (General)",
                ward_type=WardType.GENERAL.value,
                department="General Medicine",
                floor="2",
                capacity=10,
                status=WardStatus.ACTIVE.value,
            )
            db.add(ward_b)
            db.commit()
            db.refresh(ward_b)

        print(f"[3] Test Wards ready: Ward A ID={ward_a.id}, Ward B ID={ward_b.id}")

        # 4. Setup Beds
        # Bed A-10 (Source, currently OCCUPIED)
        bed_a = db.query(Bed).filter(Bed.ward_id == ward_a.id, Bed.bed_number == "A-10").first()
        if not bed_a:
            bed_a = Bed(
                hospital_id=hospital.id,
                ward_id=ward_a.id,
                bed_number="A-10",
                status=BedStatus.OCCUPIED.value,
                bed_type=BedType.ICU.value,
            )
            db.add(bed_a)
            db.commit()
            db.refresh(bed_a)
        else:
            bed_a.status = BedStatus.OCCUPIED.value
            db.commit()

        # Bed B-05 (Destination, currently AVAILABLE)
        bed_b = db.query(Bed).filter(Bed.ward_id == ward_b.id, Bed.bed_number == "B-05").first()
        if not bed_b:
            bed_b = Bed(
                hospital_id=hospital.id,
                ward_id=ward_b.id,
                bed_number="B-05",
                status=BedStatus.AVAILABLE.value,
                bed_type=BedType.STANDARD.value,
            )
            db.add(bed_b)
            db.commit()
            db.refresh(bed_b)
        else:
            bed_b.status = BedStatus.AVAILABLE.value
            db.commit()

        print(f"[4] Source Bed A-10 status: {bed_a.status} | Destination Bed B-05 status: {bed_b.status}")

        # 5. Setup Patient & Active Admission
        patient = db.query(Patient).filter(Patient.hospital_id == hospital.id, Patient.patient_identifier == "P-STAGE7-001").first()
        if not patient:
            patient = Patient(
                hospital_id=hospital.id,
                patient_identifier="P-STAGE7-001",
                first_name="Jane",
                last_name="Doe",
                date_of_birth=date(1985, 5, 20),
                gender="FEMALE",
                status=PatientStatus.ACTIVE.value,
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)

        # Clear existing active admissions for clean test
        db.query(Admission).filter(Admission.patient_id == patient.id).delete()
        db.commit()

        admission = Admission(
            hospital_id=hospital.id,
            patient_id=patient.id,
            ward_id=ward_a.id,
            bed_id=bed_a.id,
            admission_number="ADM-S7-999",
            admission_date=datetime.utcnow(),
            status=AdmissionStatus.ADMITTED.value,
            admission_reason="Severe Respiratory Distress",
            created_by=user.id,
        )
        db.add(admission)
        db.commit()
        db.refresh(admission)

        print(f"[5] Patient '{patient.first_name} {patient.last_name}' admitted to Ward A ({ward_a.name}), Bed A-10 ({bed_a.bed_number})")

        # 6. TEST STEP: Create Transfer Request
        print("\n--- STEP A: Creating Inter-Ward Transfer Request ---")
        transfer = PatientTransferService.create_transfer_request(
            db=db,
            hospital_id=hospital.id,
            user_id=user.id,
            patient_id=patient.id,
            destination_ward_id=ward_b.id,
            destination_bed_id=bed_b.id,
            reason="Patient stabilized; step-down to General Ward B",
        )
        print(f"[SUCCESS] Transfer Request created! ID={transfer.id}, Status='{transfer.status}'")
        assert transfer.status == TransferStatus.REQUESTED.value
        assert transfer.source_ward_id == ward_a.id
        assert transfer.destination_ward_id == ward_b.id

        # 7. TEST STEP: Approve Transfer Request
        print("\n--- STEP B: Approving Transfer Request ---")
        approved_transfer = PatientTransferService.approve_transfer_request(
            db=db,
            transfer_id=transfer.id,
            hospital_id=hospital.id,
            user_id=user.id,
            notes="Doctor approval confirmed",
        )
        print(f"[SUCCESS] Transfer approved! Status='{approved_transfer.status}'")
        assert approved_transfer.status == TransferStatus.APPROVED.value

        # 8. TEST STEP: Complete Transfer Request (Atomic Transaction)
        print("\n--- STEP C: Completing Transfer & Executing Bed Relocation ---")
        completed_transfer = PatientTransferService.complete_transfer_request(
            db=db,
            transfer_id=transfer.id,
            hospital_id=hospital.id,
            user_id=user.id,
        )
        print(f"[SUCCESS] Transfer completed! Status='{completed_transfer.status}', Completed At={completed_transfer.completed_at}")

        # 9. VERIFY DATABASE CHANGES
        db.refresh(bed_a)
        db.refresh(bed_b)
        db.refresh(admission)

        print("\n--- DATABASE VERIFICATION RESULTS ---")
        print(f"Source Bed A-10 Status: {bed_a.status} (Expected: AVAILABLE)")
        print(f"Destination Bed B-05 Status: {bed_b.status} (Expected: OCCUPIED)")
        print(f"Patient Active Admission Ward ID: {admission.ward_id} (Expected: {ward_b.id})")
        print(f"Patient Active Admission Bed ID: {admission.bed_id} (Expected: {bed_b.id})")

        assert bed_a.status == BedStatus.AVAILABLE.value, "Source bed must be AVAILABLE after completion!"
        assert bed_b.status == BedStatus.OCCUPIED.value, "Destination bed must be OCCUPIED after completion!"
        assert admission.ward_id == ward_b.id, "Admission ward_id must be updated to Destination Ward!"
        assert admission.bed_id == bed_b.id, "Admission bed_id must be updated to Destination Bed!"

        print("\n[SUCCESS] ALL PHASE 7 VERIFICATION CHECKS PASSED SUCCESSFULLY!")

    except Exception as e:
        print(f"\n[FAIL] VERIFICATION FAILED: {str(e)}")

        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_stage7_verification()

"""
Seed Data — creates realistic test hospitals, wards, and beds in Neon PostgreSQL.

This script is safe to run multiple times. It skips entities that already exist.
Run once after applying the Alembic migration.

Usage (from the server/ directory):
    python -m simulator.seed_data
"""
import sys
import os

# Allow running from server/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database import SessionLocal
from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType


# ── Seed Configuration ───────────────────────────────────────────────────────

SEED_HOSPITALS = [
    {"name": "Apollo Medical Center", "code": "AMC001", "city": "Chennai", "state": "Tamil Nadu", "country": "India"},
    {"name": "City General Hospital", "code": "CGH002", "city": "Mumbai", "state": "Maharashtra", "country": "India"},
]

SEED_WARDS = {
    "AMC001": [
        {"name": "ICU", "ward_type": WardType.ICU.value, "department": "Critical Care", "floor": "Floor 2", "capacity": 20},
        {"name": "General Ward A", "ward_type": WardType.GENERAL.value, "department": "General Medicine", "floor": "Floor 1", "capacity": 40},
        {"name": "Emergency", "ward_type": WardType.EMERGENCY.value, "department": "Emergency Medicine", "floor": "Ground Floor", "capacity": 15},
        {"name": "Pediatric Ward", "ward_type": WardType.PEDIATRIC.value, "department": "Pediatrics", "floor": "Floor 3", "capacity": 25},
    ],
    "CGH002": [
        {"name": "ICU", "ward_type": WardType.ICU.value, "department": "Critical Care", "floor": "Floor 3", "capacity": 30},
        {"name": "Surgical Ward", "ward_type": WardType.SURGICAL.value, "department": "Surgery", "floor": "Floor 2", "capacity": 35},
        {"name": "Maternity Ward", "ward_type": WardType.MATERNITY.value, "department": "Obstetrics", "floor": "Floor 4", "capacity": 20},
    ],
}

# Beds per ward with a mix of statuses for a realistic demo
WARD_BED_CONFIG = {
    # (count, bed_type, prefix)
    ("ICU", "AMC001"):         (20, BedType.ICU.value, "ICU"),
    ("General Ward A", "AMC001"): (40, BedType.STANDARD.value, "GWA"),
    ("Emergency", "AMC001"):   (15, BedType.EMERGENCY.value, "EM"),
    ("Pediatric Ward", "AMC001"): (25, BedType.STANDARD.value, "PED"),
    ("ICU", "CGH002"):         (30, BedType.ICU.value, "ICU"),
    ("Surgical Ward", "CGH002"): (35, BedType.STANDARD.value, "SUR"),
    ("Maternity Ward", "CGH002"): (20, BedType.STANDARD.value, "MAT"),
}

# Realistic status distribution: ~60% OCCUPIED, ~30% AVAILABLE, rest mixed
STATUS_PATTERN = [
    BedStatus.OCCUPIED.value,
    BedStatus.OCCUPIED.value,
    BedStatus.OCCUPIED.value,
    BedStatus.AVAILABLE.value,
    BedStatus.AVAILABLE.value,
    BedStatus.OCCUPIED.value,
    BedStatus.OCCUPIED.value,
    BedStatus.CLEANING.value,
    BedStatus.AVAILABLE.value,
    BedStatus.OCCUPIED.value,
]


def seed():
    db = SessionLocal()
    try:
        print("=" * 60)
        print("HOSPITAL SIMULATOR — SEED DATA")
        print("=" * 60)

        for h_data in SEED_HOSPITALS:
            hospital = db.query(Hospital).filter(Hospital.code == h_data["code"]).first()
            if not hospital:
                hospital = Hospital(
                    name=h_data["name"],
                    code=h_data["code"],
                    city=h_data.get("city"),
                    state=h_data.get("state"),
                    country=h_data.get("country"),
                    status=HospitalStatus.ACTIVE.value,
                )
                db.add(hospital)
                db.flush()  # get id before commit
                print(f"  [+] Hospital created: {hospital.name} (id={hospital.id})")
            else:
                print(f"  [=] Hospital exists:  {hospital.name} (id={hospital.id})")

            wards_config = SEED_WARDS.get(h_data["code"], [])
            for w_data in wards_config:
                ward = db.query(Ward).filter(
                    Ward.hospital_id == hospital.id,
                    Ward.name == w_data["name"],
                ).first()
                if not ward:
                    ward = Ward(
                        hospital_id=hospital.id,
                        name=w_data["name"],
                        ward_type=w_data["ward_type"],
                        department=w_data["department"],
                        floor=w_data["floor"],
                        capacity=w_data["capacity"],
                        status=WardStatus.ACTIVE.value,
                    )
                    db.add(ward)
                    db.flush()
                    print(f"      [+] Ward created: {ward.name} (id={ward.id})")
                else:
                    print(f"      [=] Ward exists:  {ward.name} (id={ward.id})")

                # Seed beds
                key = (ward.name, h_data["code"])
                if key in WARD_BED_CONFIG:
                    count, bed_type, prefix = WARD_BED_CONFIG[key]
                    created = 0
                    for i in range(1, count + 1):
                        bed_number = f"{prefix}-{str(i).zfill(2)}"
                        existing_bed = db.query(Bed).filter(
                            Bed.ward_id == ward.id,
                            Bed.bed_number == bed_number,
                        ).first()
                        if not existing_bed:
                            # Cycle through realistic status pattern
                            bed_status = STATUS_PATTERN[(i - 1) % len(STATUS_PATTERN)]
                            bed = Bed(
                                hospital_id=hospital.id,
                                ward_id=ward.id,
                                bed_number=bed_number,
                                bed_type=bed_type,
                                status=bed_status,
                            )
                            db.add(bed)
                            created += 1
                    if created:
                        print(f"          [+] {created} beds created in {ward.name}")
                    else:
                        print(f"          [=] Beds already exist in {ward.name}")

        db.commit()
        print()
        print("Seed data applied successfully.")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"ERROR during seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

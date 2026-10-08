"""
Synthea & CSV Dataset Import Service
Ingests real-world synthetic healthcare datasets (Synthea encounters, organizations)
and custom CSV time-series into the hospital bed capacity forecasting system.

Features:
1. Synthea Organizations -> Hospitals & Wards mapping
2. Synthea Inpatient & Emergency Encounters -> Continuous daily OccupancySnapshots
3. Synthea Admission/Discharge Events -> OccupancyEvent logs
4. Custom CSV time-series import -> OccupancySnapshots
5. Separation of real vs simulated data via data_source='SYNTHEA'
6. High-performance batch/bulk processing with in-memory caching
"""
import os
import re
import csv
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus
from app.models.patient import Patient, PatientStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.occupancy_event import OccupancyEvent, EventType, EventSource

logger = logging.getLogger(__name__)

DEFAULT_DATASET_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../datasets/synthea")
)


class SyntheaImportService:

    @staticmethod
    def ensure_hospital_wards_and_beds(db: Session, hospital: Hospital) -> Dict[str, Ward]:
        """
        Ensures a hospital has the core clinical wards and operational beds needed
        for bed capacity tracking, transfers, and forecasting.
        Returns a dict mapping ward category ('EMERGENCY', 'GENERAL', 'ICU') to Ward model.
        """
        wards_map: Dict[str, Ward] = {}

        ward_definitions = [
            {
                "key": "EMERGENCY",
                "name": f"{hospital.name} Emergency Unit",
                "ward_type": WardType.EMERGENCY.value,
                "department": "Emergency Medicine",
                "floor": "Ground",
                "capacity": 20,
                "external_ward_id": f"EXT-W-{hospital.id}-EMERGENCY",
            },
            {
                "key": "GENERAL",
                "name": f"{hospital.name} Inpatient Ward",
                "ward_type": WardType.GENERAL.value,
                "department": "Internal Medicine",
                "floor": "Floor 1",
                "capacity": 30,
                "external_ward_id": f"EXT-W-{hospital.id}-GENERAL",
            },
            {
                "key": "ICU",
                "name": f"{hospital.name} Intensive Care Unit",
                "ward_type": WardType.ICU.value,
                "department": "Critical Care",
                "floor": "Floor 2",
                "capacity": 12,
                "external_ward_id": f"EXT-W-{hospital.id}-ICU",
            },
        ]

        for w_def in ward_definitions:
            ward = db.query(Ward).filter(
                Ward.hospital_id == hospital.id,
                Ward.ward_type == w_def["ward_type"]
            ).first()

            if not ward:
                ward = Ward(
                    hospital_id=hospital.id,
                    name=w_def["name"],
                    ward_type=w_def["ward_type"],
                    department=w_def["department"],
                    floor=w_def["floor"],
                    capacity=w_def["capacity"],
                    external_ward_id=w_def["external_ward_id"],
                    status=WardStatus.ACTIVE.value,
                )
                db.add(ward)
                db.flush()

            # Ensure beds exist for this ward matching its capacity
            existing_beds = db.query(Bed).filter(Bed.ward_id == ward.id).count()
            if existing_beds < ward.capacity:
                beds_to_create = []
                for b_num in range(existing_beds + 1, ward.capacity + 1):
                    bed_code = f"W{ward.id}-B{b_num:02d}"
                    beds_to_create.append(
                        Bed(
                            hospital_id=hospital.id,
                            ward_id=ward.id,
                            bed_number=bed_code,
                            status=BedStatus.AVAILABLE.value,
                        )
                    )
                db.bulk_save_objects(beds_to_create)
                db.flush()

            wards_map[w_def["key"]] = ward

        db.commit()
        return wards_map

    @classmethod
    def import_organizations(
        cls,
        db: Session,
        csv_path: Optional[str] = None,
        limit: int = 5,
    ) -> List[Hospital]:
        """
        Parses Synthea organizations.csv and creates or links Hospital records.
        """
        path = csv_path or os.path.join(DEFAULT_DATASET_DIR, "organizations.csv")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Organizations CSV not found at: {path}")

        hospitals: List[Hospital] = []

        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                if count >= limit:
                    break

                org_id = row.get("Id", "").strip()
                name = row.get("NAME", "").strip().title()
                if not org_id or not name:
                    continue

                hospital = db.query(Hospital).filter(
                    (Hospital.external_hospital_id == org_id) | (Hospital.name == name)
                ).first()

                if not hospital:
                    code_prefix = "".join(filter(str.isalnum, name))[:4].upper()
                    unique_code = f"SYN-{code_prefix}-{org_id[:4].upper()}"

                    while db.query(Hospital).filter(Hospital.code == unique_code).first():
                        unique_code = f"SYN-{code_prefix}-{os.urandom(2).hex().upper()}"

                    hospital = Hospital(
                        name=name,
                        code=unique_code,
                        external_hospital_id=org_id,
                        address=row.get("ADDRESS", "").strip().title(),
                        city=row.get("CITY", "").strip().title(),
                        state=row.get("STATE", "MA").strip().upper(),
                        country="USA",
                        status=HospitalStatus.ACTIVE.value,
                    )
                    db.add(hospital)
                    db.flush()

                cls.ensure_hospital_wards_and_beds(db, hospital)
                hospitals.append(hospital)
                count += 1

        db.commit()
        return hospitals

    @classmethod
    def import_encounters(
        cls,
        db: Session,
        encounters_csv_path: Optional[str] = None,
        target_hospital_id: Optional[int] = None,
        start_year: int = 2018,
        end_year: int = 2020,
        create_occupancy_events: bool = True,
    ) -> Dict[str, Any]:
        """
        Parses Synthea encounters.csv, filters for inpatient/emergency encounters,
        and computes daily bed occupancy snapshots for the target hospital(s).
        """
        path = encounters_csv_path or os.path.join(DEFAULT_DATASET_DIR, "encounters.csv")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Encounters CSV not found at: {path}")

        # Resolve target hospital
        if target_hospital_id is not None:
            hospital = db.query(Hospital).filter(Hospital.id == target_hospital_id).first()
            if not hospital:
                raise ValueError(f"Target hospital {target_hospital_id} not found")
            target_hospitals = [hospital]
        else:
            target_hospitals = db.query(Hospital).filter(Hospital.external_hospital_id.isnot(None)).all()
            if not target_hospitals:
                target_hospitals = cls.import_organizations(db, limit=3)

        primary_hospital = target_hospitals[0]
        primary_wards = cls.ensure_hospital_wards_and_beds(db, primary_hospital)

        logger.info(
            f"Importing Synthea encounters into hospital {primary_hospital.name} (ID: {primary_hospital.id})"
        )

        # Cache beds per ward in memory to avoid repeated queries in loop
        ward_bed_ids: Dict[int, Optional[int]] = {}
        for w in primary_wards.values():
            bed_obj = db.query(Bed.id).filter(Bed.ward_id == w.id).first()
            ward_bed_ids[w.id] = bed_obj[0] if bed_obj else None

        # Preload existing event IDs globally for deduplication in memory
        existing_event_ids: Set[str] = set(
            row[0] for row in db.query(OccupancyEvent.event_id).all()
        )

        # Daily census tracking: (ward_id, date) -> count
        daily_active: Dict[Tuple[int, date], int] = {}
        daily_admissions: Dict[Tuple[int, date], int] = {}
        daily_discharges: Dict[Tuple[int, date], int] = {}

        encounters_processed = 0
        events_created = 0
        min_encounter_date = date.max
        max_encounter_date = date.min

        events_to_insert: List[OccupancyEvent] = []

        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                e_class = (row.get("ENCOUNTERCLASS") or "").strip().lower()
                if e_class not in ("inpatient", "emergency"):
                    continue

                st_str = (row.get("START") or "").strip()
                sp_str = (row.get("STOP") or "").strip()
                if not st_str:
                    continue

                try:
                    start_dt = datetime.fromisoformat(st_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    stop_dt = (
                        datetime.fromisoformat(sp_str.replace("Z", "+00:00")).replace(tzinfo=None)
                        if sp_str
                        else start_dt + timedelta(days=1)
                    )
                except Exception:
                    continue

                start_d = start_dt.date()
                stop_d = stop_dt.date()

                if start_d.year < start_year or start_d.year > end_year:
                    continue

                desc = (row.get("DESCRIPTION") or "").lower()
                reason = (row.get("REASONDESCRIPTION") or "").lower()
                combined_text = f"{desc} {reason}"

                if e_class == "emergency":
                    assigned_ward = primary_wards["EMERGENCY"]
                elif any(k in combined_text for k in ["cardiac", "infarction", "respiratory failure", "icu", "critical", "stroke", "arrest"]):
                    assigned_ward = primary_wards["ICU"]
                else:
                    assigned_ward = primary_wards["GENERAL"]

                encounters_processed += 1
                min_encounter_date = min(min_encounter_date, start_d)
                max_encounter_date = max(max_encounter_date, stop_d)

                daily_admissions[(assigned_ward.id, start_d)] = daily_admissions.get((assigned_ward.id, start_d), 0) + 1
                daily_discharges[(assigned_ward.id, stop_d)] = daily_discharges.get((assigned_ward.id, stop_d), 0) + 1

                curr_d = start_d
                while curr_d <= stop_d:
                    key = (assigned_ward.id, curr_d)
                    daily_active[key] = daily_active.get(key, 0) + 1
                    curr_d += timedelta(days=1)

                if create_occupancy_events:
                    enc_id = row.get("Id", "")[:18]
                    bed_id = ward_bed_ids.get(assigned_ward.id)

                    adm_event_id = f"SYN-H{primary_hospital.id}-ADM-{enc_id}"
                    if adm_event_id not in existing_event_ids:
                        events_to_insert.append(
                            OccupancyEvent(
                                event_id=adm_event_id,
                                hospital_id=primary_hospital.id,
                                ward_id=assigned_ward.id,
                                bed_id=bed_id,
                                event_type=EventType.ADMISSION.value,
                                event_time=start_dt,
                                source=EventSource.API.value,
                            )
                        )
                        existing_event_ids.add(adm_event_id)
                        events_created += 1

                    dis_event_id = f"SYN-H{primary_hospital.id}-DIS-{enc_id}"
                    if dis_event_id not in existing_event_ids:
                        events_to_insert.append(
                            OccupancyEvent(
                                event_id=dis_event_id,
                                hospital_id=primary_hospital.id,
                                ward_id=assigned_ward.id,
                                bed_id=bed_id,
                                event_type=EventType.DISCHARGE.value,
                                event_time=stop_dt,
                                source=EventSource.API.value,
                            )
                        )
                        existing_event_ids.add(dis_event_id)
                        events_created += 1

        if events_to_insert:
            db.bulk_save_objects(events_to_insert)
            db.flush()

        # Preload existing snapshots for this hospital into memory map
        existing_snaps: Dict[Tuple[int, datetime], OccupancySnapshot] = {}
        for snap in db.query(OccupancySnapshot).filter(
            OccupancySnapshot.hospital_id == primary_hospital.id
        ).all():
            existing_snaps[(snap.ward_id, snap.snapshot_time)] = snap

        snapshots_created = 0
        snapshots_updated = 0
        new_snaps_to_insert: List[OccupancySnapshot] = []

        if min_encounter_date <= max_encounter_date:
            for ward_key, ward in primary_wards.items():
                curr_date = min_encounter_date
                while curr_date <= max_encounter_date:
                    active_count = daily_active.get((ward.id, curr_date), 0)
                    total_cap = ward.capacity or 20
                    occupied = min(active_count, total_cap)
                    available = max(0, total_cap - occupied)
                    occ_pct = round((occupied / total_cap) * 100.0, 2)
                    snap_time = datetime.combine(curr_date, datetime.min.time()) + timedelta(hours=23, minutes=59)

                    existing = existing_snaps.get((ward.id, snap_time))
                    if existing:
                        existing.total_beds = total_cap
                        existing.occupied_beds = occupied
                        existing.available_beds = available
                        existing.occupancy_percentage = occ_pct
                        existing.data_source = "SYNTHEA"
                        snapshots_updated += 1
                    else:
                        new_snap = OccupancySnapshot(
                            hospital_id=primary_hospital.id,
                            ward_id=ward.id,
                            snapshot_time=snap_time,
                            total_beds=total_cap,
                            occupied_beds=occupied,
                            available_beds=available,
                            cleaning_beds=0,
                            reserved_beds=0,
                            maintenance_beds=0,
                            occupancy_percentage=occ_pct,
                            data_source="SYNTHEA",
                        )
                        new_snaps_to_insert.append(new_snap)
                        existing_snaps[(ward.id, snap_time)] = new_snap
                        snapshots_created += 1

                    curr_date += timedelta(days=1)

        if new_snaps_to_insert:
            db.bulk_save_objects(new_snaps_to_insert)
            db.flush()

        db.commit()

        return {
            "status": "SUCCESS",
            "hospital_id": primary_hospital.id,
            "hospital_name": primary_hospital.name,
            "encounters_processed": encounters_processed,
            "date_range": {
                "start": min_encounter_date.isoformat() if min_encounter_date != date.max else None,
                "end": max_encounter_date.isoformat() if max_encounter_date != date.min else None,
            },
            "snapshots_created": snapshots_created,
            "snapshots_updated": snapshots_updated,
            "events_created": events_created,
            "data_source": "SYNTHEA",
            "wards_configured": [
                {"id": w.id, "name": w.name, "capacity": w.capacity, "type": w.ward_type}
                for w in primary_wards.values()
            ],
        }

    @classmethod
    def import_custom_csv_snapshots(
        cls,
        db: Session,
        file_content: str,
        hospital_id: int,
        ward_id: int,
    ) -> Dict[str, Any]:
        """
        Parses a custom CSV string containing daily bed occupancy snapshots.
        """
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise ValueError(f"Hospital {hospital_id} not found")

        ward = db.query(Ward).filter(Ward.id == ward_id, Ward.hospital_id == hospital_id).first()
        if not ward:
            raise ValueError(f"Ward {ward_id} not found for hospital {hospital_id}")

        lines = file_content.strip().splitlines()
        reader = csv.DictReader(lines)

        created_count = 0
        updated_count = 0
        new_snaps: List[OccupancySnapshot] = []

        existing_snaps = {
            s.snapshot_time: s
            for s in db.query(OccupancySnapshot).filter(
                OccupancySnapshot.hospital_id == hospital_id,
                OccupancySnapshot.ward_id == ward_id,
            ).all()
        }

        for row in reader:
            normalized = {k.lower().strip().replace(" ", "_"): v.strip() for k, v in row.items() if k}

            date_val = normalized.get("date") or normalized.get("snapshot_time") or normalized.get("timestamp")
            if not date_val:
                continue

            try:
                if "T" in date_val:
                    snap_time = datetime.fromisoformat(date_val.replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    d_obj = datetime.strptime(date_val[:10], "%Y-%m-%d").date()
                    snap_time = datetime.combine(d_obj, datetime.min.time()) + timedelta(hours=23, minutes=59)
            except Exception:
                continue

            occ_str = normalized.get("occupied_beds") or normalized.get("occupied") or "0"
            tot_str = normalized.get("total_beds") or normalized.get("total") or str(ward.capacity)

            try:
                occupied = max(0, int(float(occ_str)))
                total = max(1, int(float(tot_str)))
            except ValueError:
                continue

            available = max(0, total - occupied)
            occ_pct = round((occupied / total) * 100.0, 2)

            existing = existing_snaps.get(snap_time)
            if existing:
                existing.total_beds = total
                existing.occupied_beds = occupied
                existing.available_beds = available
                existing.occupancy_percentage = occ_pct
                existing.data_source = "CSV_IMPORT"
                updated_count += 1
            else:
                snap = OccupancySnapshot(
                    hospital_id=hospital_id,
                    ward_id=ward_id,
                    snapshot_time=snap_time,
                    total_beds=total,
                    occupied_beds=occupied,
                    available_beds=available,
                    occupancy_percentage=occ_pct,
                    data_source="CSV_IMPORT",
                )
                new_snaps.append(snap)
                created_count += 1

        if new_snaps:
            db.bulk_save_objects(new_snaps)

        db.commit()

        return {
            "status": "SUCCESS",
            "hospital_id": hospital_id,
            "ward_id": ward_id,
            "created": created_count,
            "updated": updated_count,
            "data_source": "CSV_IMPORT",
        }

    @classmethod
    def import_patients(
        cls,
        db: Session,
        target_hospital_id: int,
        csv_path: Optional[str] = None,
        limit: int = 50,
        create_sample_admissions: bool = True,
    ) -> Dict[str, Any]:
        """
        Ingests real Synthea patients from patients.csv into the specified hospital.
        Optionally creates active admissions in available beds to populate the clinical registry.
        """
        path = csv_path or os.path.join(DEFAULT_DATASET_DIR, "patients.csv")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Patients CSV not found at: {path}")

        hospital = db.query(Hospital).filter(Hospital.id == target_hospital_id).first()
        if not hospital:
            raise ValueError(f"Hospital with ID {target_hospital_id} does not exist.")

        created_patients: List[Patient] = []
        admissions_created = 0

        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                if count >= limit:
                    break

                raw_id = row.get("Id", "").strip()
                raw_first = row.get("FIRST", "").strip()
                raw_last = row.get("LAST", "").strip()
                birthdate_str = row.get("BIRTHDATE", "").strip()

                if not raw_id or not raw_first or not raw_last or not birthdate_str:
                    continue

                clean_first = re.sub(r"\d+", "", raw_first).strip()
                clean_last = re.sub(r"\d+", "", raw_last).strip()
                clean_ident = f"SYN-{raw_id[:8].upper()}"

                existing = db.query(Patient).filter(
                    Patient.hospital_id == target_hospital_id,
                    (Patient.patient_identifier == clean_ident) | (Patient.patient_identifier == raw_id)
                ).first()

                if not existing:
                    try:
                        dob = datetime.strptime(birthdate_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue

                    gender_code = row.get("GENDER", "OTHER").upper()
                    gender = "MALE" if gender_code == "M" else ("FEMALE" if gender_code == "F" else "OTHER")

                    address_parts = [
                        row.get("ADDRESS", "").strip(),
                        row.get("CITY", "").strip(),
                        row.get("STATE", "").strip(),
                        row.get("ZIP", "").strip(),
                    ]
                    clean_address = ", ".join(p for p in address_parts if p)

                    patient = Patient(
                        hospital_id=target_hospital_id,
                        patient_identifier=clean_ident,
                        first_name=clean_first or raw_first,
                        last_name=clean_last or raw_last,
                        date_of_birth=dob,
                        gender=gender,
                        phone=f"555-01{count:02d}",
                        email=f"{clean_first.lower().replace(' ', '')}.{clean_last.lower()}@example.org",
                        address=clean_address or "Boston, Massachusetts",
                        emergency_contact_name=f"Contact for {clean_first}",
                        emergency_contact_phone=f"555-99{count:02d}",
                        status=PatientStatus.ACTIVE.value,
                    )
                    db.add(patient)
                    db.flush()
                    created_patients.append(patient)
                    count += 1

        db.commit()

        if create_sample_admissions:
            available_beds = db.query(Bed).filter(
                Bed.hospital_id == target_hospital_id,
                Bed.status == BedStatus.AVAILABLE.value
            ).limit(8).all()

            patients_for_admission = db.query(Patient).filter(
                Patient.hospital_id == target_hospital_id
            ).limit(len(available_beds)).all()

            for idx, (p, bed) in enumerate(zip(patients_for_admission, available_beds)):
                active_adm = db.query(Admission).filter(
                    Admission.patient_id == p.id,
                    Admission.status == AdmissionStatus.ADMITTED.value
                ).first()

                if not active_adm:
                    adm = Admission(
                        hospital_id=target_hospital_id,
                        patient_id=p.id,
                        ward_id=bed.ward_id,
                        bed_id=bed.id,
                        admission_number=f"ADM-SYN-{datetime.utcnow().strftime('%Y%m%d')}-{bed.id:03d}",
                        admission_date=datetime.utcnow() - timedelta(days=idx + 1),
                        status=AdmissionStatus.ADMITTED.value,
                        admission_reason="Inpatient medical evaluation and capacity telemetry observation",
                    )
                    db.add(adm)
                    bed.status = BedStatus.OCCUPIED.value
                    admissions_created += 1

            db.commit()

        return {
            "status": "SUCCESS",
            "hospital_id": target_hospital_id,
            "patients_created": len(created_patients),
            "admissions_created": admissions_created,
        }

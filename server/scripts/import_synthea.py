"""
Synthea Dataset Ingestion CLI Runner
Usage:
    python scripts/import_synthea.py [--hospital-id 1] [--start-year 2018] [--end-year 2020]
"""
import sys
import os
import argparse

# Ensure server module is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.session import SessionLocal
from app.models.hospital import Hospital
from app.services.synthea_import_service import SyntheaImportService


def main():
    parser = argparse.ArgumentParser(description="Ingest Synthea dataset into Hospital Bed Capacity system")
    parser.add_argument("--hospital-id", type=int, default=None, help="Target hospital ID to assign encounters to (default: auto-create/use Synthea hospitals)")
    parser.add_argument("--limit-orgs", type=int, default=3, help="Max Synthea organizations to import as hospitals")
    parser.add_argument("--start-year", type=int, default=2018, help="Start year for encounter filtering")
    parser.add_argument("--end-year", type=int, default=2020, help="End year for encounter filtering")

    parser.add_argument("--import-patients", action="store_true", default=True, help="Import Synthea patients from patients.csv")
    parser.add_argument("--limit-patients", type=int, default=50, help="Max Synthea patients to import")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("=" * 60)
        print("Hospital Bed Capacity Forecasting — Synthea Dataset Ingestion")
        print("=" * 60)

        # 1. Organizations & Wards
        print(f"\n[1/3] Checking Synthea Organizations & Wards (limit={args.limit_orgs})...")
        hospitals = SyntheaImportService.import_organizations(db, limit=args.limit_orgs)
        for h in hospitals:
            print(f"  * Hospital: {h.name} (ID: {h.id}, Code: {h.code}, ExtID: {h.external_hospital_id})")

        # Target Hospital setup
        target_id = args.hospital_id or (hospitals[0].id if hospitals else None)
        target_hospital = db.query(Hospital).filter(Hospital.id == target_id).first()
        if target_hospital:
            print(f"  * Ensuring wards and beds exist for Target Hospital: {target_hospital.name} (ID: {target_hospital.id})...")
            SyntheaImportService.ensure_hospital_wards_and_beds(db, target_hospital)

        # 2. Encounters & Daily Snapshots
        print(f"\n[2/3] Ingesting Inpatient & Emergency Encounters into Hospital ID {target_id}...")
        print(f"  * Year filter: {args.start_year} to {args.end_year}")

        result = SyntheaImportService.import_encounters(
            db=db,
            target_hospital_id=target_id,
            start_year=args.start_year,
            end_year=args.end_year,
            create_occupancy_events=True,
        )

        # 3. Patients & Sample Admissions
        patient_res = None
        if args.import_patients and target_id:
            print(f"\n[3/3] Ingesting Synthea Patients into Hospital ID {target_id} (limit={args.limit_patients})...")
            patient_res = SyntheaImportService.import_patients(
                db=db,
                target_hospital_id=target_id,
                limit=args.limit_patients,
                create_sample_admissions=True,
            )

        print("\n" + "=" * 60)
        print("INGESTION SUMMARY:")
        print("=" * 60)
        print(f"  Target Hospital:      {result['hospital_name']} (ID: {result['hospital_id']})")
        print(f"  Encounters Ingested:  {result['encounters_processed']}")
        print(f"  Date Range:           {result['date_range']['start']} to {result['date_range']['end']}")
        print(f"  Snapshots Created:    {result['snapshots_created']}")
        print(f"  Snapshots Updated:    {result['snapshots_updated']}")
        print(f"  Events Logged:        {result['events_created']}")
        if patient_res:
            print(f"  Patients Ingested:    {patient_res['patients_created']}")
            print(f"  Active Admissions:    {patient_res['admissions_created']}")
        print(f"  Data Source Tag:      {result['data_source']}")
        print("  Configured Wards:")
        for w in result["wards_configured"]:
            print(f"    - Ward {w['id']} ({w['name']}): Type={w['type']}, Capacity={w['capacity']}")
        print("=" * 60)
        print("Ingestion completed successfully! Historical data is ready for forecasting.")

    except Exception as e:
        print(f"\nERROR during ingestion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

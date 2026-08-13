import logging
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.models.bed import Bed, BedStatus
from app.models.hospital import Hospital, HospitalStatus
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.ward import Ward, WardStatus
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)


class SnapshotService:

    @staticmethod
    def generate_snapshots_for_all_hospitals(db: Session) -> Dict[str, Any]:
        """
        Calculates live bed statuses for all active wards across active hospitals
        and records time-series OccupancySnapshot entries.
        Enforces snapshot uniqueness per (hospital_id, ward_id, snapshot_time).
        Triggers rule-based capacity alert evaluations.
        """
        # Round snapshot time to nearest minute to prevent accidental high-frequency duplicate timestamps
        now = datetime.utcnow()
        snapshot_time = datetime(now.year, now.month, now.day, now.hour, now.minute)

        active_hospitals = db.query(Hospital).filter(Hospital.status == HospitalStatus.ACTIVE.value).all()
        snapshots_created = 0
        wards_processed = 0

        for hosp in active_hospitals:
            active_wards = db.query(Ward).filter(
                Ward.hospital_id == hosp.id,
                Ward.status == WardStatus.ACTIVE.value,
            ).all()

            for ward in active_wards:
                wards_processed += 1

                # Calculate live counts directly from Bed records
                bed_query = db.query(Bed).filter(Bed.ward_id == ward.id)
                beds = bed_query.all()

                total_beds = len(beds)
                occupied_beds = sum(1 for b in beds if b.status == BedStatus.OCCUPIED.value)
                available_beds = sum(1 for b in beds if b.status == BedStatus.AVAILABLE.value)
                cleaning_beds = sum(1 for b in beds if b.status == BedStatus.CLEANING.value)
                reserved_beds = sum(1 for b in beds if b.status == BedStatus.RESERVED.value)
                maintenance_beds = sum(1 for b in beds if b.status == BedStatus.MAINTENANCE.value)

                occupancy_pct = (occupied_beds / total_beds * 100.0) if total_beds > 0 else 0.0
                occupancy_pct = round(occupancy_pct, 2)

                # Check if snapshot already exists for this exact minute (uniqueness rule)
                existing = db.query(OccupancySnapshot).filter(
                    OccupancySnapshot.hospital_id == hosp.id,
                    OccupancySnapshot.ward_id == ward.id,
                    OccupancySnapshot.snapshot_time == snapshot_time,
                ).first()

                if not existing:
                    snapshot = OccupancySnapshot(
                        hospital_id=hosp.id,
                        ward_id=ward.id,
                        snapshot_time=snapshot_time,
                        total_beds=total_beds,
                        occupied_beds=occupied_beds,
                        available_beds=available_beds,
                        cleaning_beds=cleaning_beds,
                        reserved_beds=reserved_beds,
                        maintenance_beds=maintenance_beds,
                        occupancy_percentage=occupancy_pct,
                    )
                    db.add(snapshot)
                    snapshots_created += 1

                # Evaluate capacity alerts
                try:
                    AlertService.evaluate_ward_alerts(
                        db=db,
                        hospital_id=hosp.id,
                        ward_id=ward.id,
                        ward_name=ward.name,
                        occupied_beds=occupied_beds,
                        total_beds=total_beds,
                        available_beds=available_beds,
                        occupancy_percentage=occupancy_pct,
                    )
                except Exception as ex:
                    logger.error(f"Alert evaluation error for ward {ward.id}: {ex}")

        db.commit()

        logger.info(
            f"SNAPSHOT GENERATION COMPLETE | created={snapshots_created} "
            f"wards={wards_processed} hospitals={len(active_hospitals)}"
        )

        return {
            "snapshots_created": snapshots_created,
            "hospitals_processed": len(active_hospitals),
            "wards_processed": wards_processed,
            "snapshot_time": snapshot_time.isoformat(),
        }

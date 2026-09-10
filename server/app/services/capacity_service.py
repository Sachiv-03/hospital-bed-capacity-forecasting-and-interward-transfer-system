import logging
from datetime import datetime, date
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func, Date, cast
from sqlalchemy.orm import Session

from app.models.bed import Bed, BedStatus
from app.models.hospital import Hospital
from app.models.ward import Ward, WardStatus
from app.models.admission import Admission, AdmissionStatus
from app.schemas.capacity import (
    HospitalCapacityResponse, WardCapacityResponse, OccupancySummaryResponse, get_capacity_status
)

logger = logging.getLogger(__name__)


class CapacityService:

    @staticmethod
    def _count_beds_by_status(db: Session, ward_id: int) -> dict:
        """Return a dict of {status: count} for all beds in a ward."""
        rows = (
            db.query(Bed.status, func.count(Bed.id))
            .filter(Bed.ward_id == ward_id)
            .group_by(Bed.status)
            .all()
        )
        counts = {
            BedStatus.AVAILABLE.value: 0,
            BedStatus.OCCUPIED.value: 0,
            BedStatus.CLEANING.value: 0,
            BedStatus.MAINTENANCE.value: 0,
            BedStatus.RESERVED.value: 0,
            "INACTIVE": 0,
        }
        for stat, cnt in rows:
            counts[stat] = cnt
        return counts

    @staticmethod
    def get_ward_capacity(db: Session, ward_id: int, requesting_hospital_id: int) -> WardCapacityResponse:
        """Return real-time capacity for a single ward. Enforces hospital ownership."""
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
        if ward.hospital_id != requesting_hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this ward",
            )

        counts = CapacityService._count_beds_by_status(db, ward_id)
        total = sum(counts.values())
        occupied = counts.get(BedStatus.OCCUPIED.value, 0)
        available = counts.get(BedStatus.AVAILABLE.value, 0)
        
        # Operational Beds = Available + Occupied (excludes Maintenance, Cleaning, Reserved, Inactive)
        operational = occupied + available
        
        occupancy_pct = round((occupied / operational * 100), 2) if operational > 0 else 0.0
        avail_cap_pct = round((available / operational * 100), 2) if operational > 0 else 0.0

        return WardCapacityResponse(
            ward_id=ward.id,
            ward_name=ward.name,
            ward_type=ward.ward_type,
            hospital_id=ward.hospital_id,
            total_beds=total,
            operational_beds=operational,
            occupied_beds=occupied,
            available_beds=available,
            cleaning_beds=counts.get(BedStatus.CLEANING.value, 0),
            reserved_beds=counts.get(BedStatus.RESERVED.value, 0),
            maintenance_beds=counts.get(BedStatus.MAINTENANCE.value, 0),
            inactive_beds=counts.get("INACTIVE", 0),
            occupancy_percentage=occupancy_pct,
            available_capacity_percentage=avail_cap_pct,
            status=get_capacity_status(occupancy_pct),
        )

    @staticmethod
    def get_all_ward_capacities(db: Session, hospital_id: int) -> List[WardCapacityResponse]:
        """Return capacity for every active ward in a hospital."""
        wards = (
            db.query(Ward)
            .filter(Ward.hospital_id == hospital_id, Ward.status == WardStatus.ACTIVE.value)
            .order_by(Ward.name)
            .all()
        )
        results = []
        for ward in wards:
            counts = CapacityService._count_beds_by_status(db, ward.id)
            total = sum(counts.values())
            occupied = counts.get(BedStatus.OCCUPIED.value, 0)
            available = counts.get(BedStatus.AVAILABLE.value, 0)
            operational = occupied + available
            
            occupancy_pct = round((occupied / operational * 100), 2) if operational > 0 else 0.0
            avail_cap_pct = round((available / operational * 100), 2) if operational > 0 else 0.0

            results.append(
                WardCapacityResponse(
                    ward_id=ward.id,
                    ward_name=ward.name,
                    ward_type=ward.ward_type,
                    hospital_id=ward.hospital_id,
                    total_beds=total,
                    operational_beds=operational,
                    occupied_beds=occupied,
                    available_beds=available,
                    cleaning_beds=counts.get(BedStatus.CLEANING.value, 0),
                    reserved_beds=counts.get(BedStatus.RESERVED.value, 0),
                    maintenance_beds=counts.get(BedStatus.MAINTENANCE.value, 0),
                    inactive_beds=counts.get("INACTIVE", 0),
                    occupancy_percentage=occupancy_pct,
                    available_capacity_percentage=avail_cap_pct,
                    status=get_capacity_status(occupancy_pct),
                )
            )
        return results

    @staticmethod
    def get_hospital_capacity(db: Session, hospital_id: int) -> HospitalCapacityResponse:
        """Return aggregated capacity for an entire hospital."""
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

        ward_capacities = CapacityService.get_all_ward_capacities(db, hospital_id)

        total_wards = len(ward_capacities)
        total_beds = sum(w.total_beds for w in ward_capacities)
        operational_beds = sum(w.operational_beds for w in ward_capacities)
        occupied_beds = sum(w.occupied_beds for w in ward_capacities)
        available_beds = sum(w.available_beds for w in ward_capacities)
        cleaning_beds = sum(w.cleaning_beds for w in ward_capacities)
        reserved_beds = sum(w.reserved_beds for w in ward_capacities)
        maintenance_beds = sum(w.maintenance_beds for w in ward_capacities)
        inactive_beds = sum(w.inactive_beds for w in ward_capacities)

        occupancy_pct = round((occupied_beds / operational_beds * 100), 2) if operational_beds > 0 else 0.0
        avail_cap_pct = round((available_beds / operational_beds * 100), 2) if operational_beds > 0 else 0.0

        # Calculate live stay movements from Phase 5 admissions table
        today_date = date.today()

        active_admissions = db.query(Admission).filter(
            Admission.hospital_id == hospital_id,
            Admission.status == AdmissionStatus.ADMITTED.value
        ).count()

        admissions_today = db.query(Admission).filter(
            Admission.hospital_id == hospital_id,
            cast(Admission.admission_date, Date) == today_date
        ).count()

        discharges_today = db.query(Admission).filter(
            Admission.hospital_id == hospital_id,
            cast(Admission.discharge_date, Date) == today_date
        ).count()

        return HospitalCapacityResponse(
            hospital_id=hospital.id,
            hospital_name=hospital.name,
            total_wards=total_wards,
            total_beds=total_beds,
            operational_beds=operational_beds,
            occupied_beds=occupied_beds,
            available_beds=available_beds,
            cleaning_beds=cleaning_beds,
            reserved_beds=reserved_beds,
            maintenance_beds=maintenance_beds,
            inactive_beds=inactive_beds,
            occupancy_percentage=occupancy_pct,
            available_capacity_percentage=avail_cap_pct,
            status=get_capacity_status(occupancy_pct),
            active_admissions=active_admissions,
            admissions_today=admissions_today,
            discharges_today=discharges_today,
            ward_capacities=[w.model_dump() for w in ward_capacities],
        )

    @staticmethod
    def get_occupancy_summary(db: Session, hospital_id: int) -> OccupancySummaryResponse:
        """Return complete command summary for hospital capacity & stay movements."""
        cap = CapacityService.get_hospital_capacity(db, hospital_id)
        return OccupancySummaryResponse(
            hospital_id=cap.hospital_id,
            hospital_name=cap.hospital_name,
            total_beds=cap.total_beds,
            operational_beds=cap.operational_beds,
            occupied_beds=cap.occupied_beds,
            available_beds=cap.available_beds,
            maintenance_beds=cap.maintenance_beds,
            inactive_beds=cap.inactive_beds,
            occupancy_percentage=cap.occupancy_percentage,
            available_capacity_percentage=cap.available_capacity_percentage,
            capacity_status=cap.status,
            active_admissions=cap.active_admissions,
            admissions_today=cap.admissions_today,
            discharges_today=cap.discharges_today,
            timestamp=datetime.utcnow().isoformat()
        )

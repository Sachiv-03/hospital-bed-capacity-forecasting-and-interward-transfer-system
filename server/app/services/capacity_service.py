"""
Capacity Service — calculate real-time ward and hospital bed occupancy.

All values are computed live from the `beds` table. Nothing is hard-coded.
"""
import logging
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bed import Bed, BedStatus
from app.models.hospital import Hospital
from app.models.ward import Ward, WardStatus
from app.schemas.capacity import HospitalCapacityResponse, WardCapacityResponse, get_capacity_status

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
        occupied = counts[BedStatus.OCCUPIED.value]
        pct = round((occupied / total * 100), 2) if total > 0 else 0.0

        return WardCapacityResponse(
            ward_id=ward.id,
            ward_name=ward.name,
            hospital_id=ward.hospital_id,
            total_beds=total,
            occupied_beds=occupied,
            available_beds=counts[BedStatus.AVAILABLE.value],
            cleaning_beds=counts[BedStatus.CLEANING.value],
            reserved_beds=counts[BedStatus.RESERVED.value],
            maintenance_beds=counts[BedStatus.MAINTENANCE.value],
            occupancy_percentage=pct,
            status=get_capacity_status(pct),
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
            occupied = counts[BedStatus.OCCUPIED.value]
            pct = round((occupied / total * 100), 2) if total > 0 else 0.0
            results.append(
                WardCapacityResponse(
                    ward_id=ward.id,
                    ward_name=ward.name,
                    hospital_id=ward.hospital_id,
                    total_beds=total,
                    occupied_beds=occupied,
                    available_beds=counts[BedStatus.AVAILABLE.value],
                    cleaning_beds=counts[BedStatus.CLEANING.value],
                    reserved_beds=counts[BedStatus.RESERVED.value],
                    maintenance_beds=counts[BedStatus.MAINTENANCE.value],
                    occupancy_percentage=pct,
                    status=get_capacity_status(pct),
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
        occupied_beds = sum(w.occupied_beds for w in ward_capacities)
        available_beds = sum(w.available_beds for w in ward_capacities)
        cleaning_beds = sum(w.cleaning_beds for w in ward_capacities)
        reserved_beds = sum(w.reserved_beds for w in ward_capacities)
        maintenance_beds = sum(w.maintenance_beds for w in ward_capacities)
        pct = round((occupied_beds / total_beds * 100), 2) if total_beds > 0 else 0.0

        return HospitalCapacityResponse(
            hospital_id=hospital.id,
            hospital_name=hospital.name,
            total_wards=total_wards,
            total_beds=total_beds,
            occupied_beds=occupied_beds,
            available_beds=available_beds,
            cleaning_beds=cleaning_beds,
            reserved_beds=reserved_beds,
            maintenance_beds=maintenance_beds,
            occupancy_percentage=pct,
            status=get_capacity_status(pct),
            ward_capacities=[w.model_dump() for w in ward_capacities],
        )

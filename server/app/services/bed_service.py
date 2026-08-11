"""
Bed Service — CRUD operations for the beds table.
Enforces hospital ↔ ward ↔ bed ownership at every operation.
"""
import logging
from math import ceil
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bed import Bed, BedStatus, BedType
from app.models.ward import Ward
from app.schemas.bed import BedCreate, BedUpdate, BedResponse, BedListResponse

logger = logging.getLogger(__name__)


class BedService:

    @staticmethod
    def _get_ward_or_404(db: Session, ward_id: int, hospital_id: int) -> Ward:
        """Fetch a ward and verify it belongs to the given hospital."""
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
        if ward.hospital_id != hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ward does not belong to the specified hospital",
            )
        return ward

    @staticmethod
    def get_bed(db: Session, bed_id: int, hospital_id: int) -> Bed:
        bed = db.query(Bed).filter(Bed.id == bed_id, Bed.hospital_id == hospital_id).first()
        if not bed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed not found")
        return bed

    @staticmethod
    def get_beds(
        db: Session,
        hospital_id: int,
        ward_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        bed_type_filter: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> BedListResponse:
        query = db.query(Bed).filter(Bed.hospital_id == hospital_id)
        if ward_id:
            query = query.filter(Bed.ward_id == ward_id)
        if status_filter:
            query = query.filter(Bed.status == status_filter)
        if bed_type_filter:
            query = query.filter(Bed.bed_type == bed_type_filter)

        total = query.count()
        beds = query.order_by(Bed.ward_id, Bed.bed_number).offset((page - 1) * limit).limit(limit).all()

        items = []
        for bed in beds:
            ward = bed.ward
            hospital = bed.hospital
            resp = BedResponse(
                id=bed.id,
                hospital_id=bed.hospital_id,
                ward_id=bed.ward_id,
                bed_number=bed.bed_number,
                status=bed.status,
                bed_type=bed.bed_type,
                created_at=bed.created_at,
                updated_at=bed.updated_at,
                ward_name=ward.name if ward else None,
                hospital_name=hospital.name if hospital else None,
            )
            items.append(resp)

        return BedListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=ceil(total / limit) if limit else 1,
        )

    @staticmethod
    def create_bed(db: Session, bed_in: BedCreate, resolved_hospital_id: int) -> Bed:
        """Create a bed. Validates ward ↔ hospital ownership."""
        BedService._get_ward_or_404(db, bed_in.ward_id, resolved_hospital_id)

        # Check for duplicate bed_number within the same ward
        existing = db.query(Bed).filter(
            Bed.ward_id == bed_in.ward_id,
            Bed.bed_number == bed_in.bed_number,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bed number '{bed_in.bed_number}' already exists in this ward",
            )

        bed = Bed(
            hospital_id=resolved_hospital_id,
            ward_id=bed_in.ward_id,
            bed_number=bed_in.bed_number,
            bed_type=bed_in.bed_type.value,
            status=bed_in.status.value,
        )
        db.add(bed)
        db.commit()
        db.refresh(bed)
        logger.info(f"BED CREATED: bed_id={bed.id} ward_id={bed.ward_id} hospital_id={bed.hospital_id}")
        return bed

    @staticmethod
    def update_bed(db: Session, bed_id: int, bed_update: BedUpdate, hospital_id: int) -> Bed:
        bed = BedService.get_bed(db, bed_id, hospital_id)
        update_data = bed_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(bed, field) and value is not None:
                setattr(bed, field, value.value if hasattr(value, "value") else value)
        db.commit()
        db.refresh(bed)
        return bed

    @staticmethod
    def delete_bed(db: Session, bed_id: int, hospital_id: int) -> None:
        bed = BedService.get_bed(db, bed_id, hospital_id)
        db.delete(bed)
        db.commit()

    @staticmethod
    def seed_beds(
        db: Session,
        ward: Ward,
        count: int,
        bed_type: str = BedType.STANDARD.value,
        prefix: Optional[str] = None,
    ) -> List[Bed]:
        """Create `count` beds for a ward (for seeding/testing)."""
        if prefix is None:
            prefix = ward.ward_type[:3].upper()
        beds = []
        for i in range(1, count + 1):
            bed_number = f"{prefix}-{str(i).zfill(2)}"
            existing = db.query(Bed).filter(
                Bed.ward_id == ward.id, Bed.bed_number == bed_number
            ).first()
            if existing:
                beds.append(existing)
                continue
            bed = Bed(
                hospital_id=ward.hospital_id,
                ward_id=ward.id,
                bed_number=bed_number,
                bed_type=bed_type,
                status=BedStatus.AVAILABLE.value,
            )
            db.add(bed)
            beds.append(bed)
        db.commit()
        return beds

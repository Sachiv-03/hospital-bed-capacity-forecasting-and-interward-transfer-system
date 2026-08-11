from typing import Dict, Any, Optional
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardStatus
from app.schemas.hospital import HospitalCreate, HospitalUpdate, HospitalStatusEnum


class HospitalService:
    @staticmethod
    def get_hospitals(
        db: Session,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch paginated list of hospitals with optional search and status filtering.
        """
        query = db.query(Hospital)

        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Hospital.name.ilike(pattern),
                    Hospital.code.ilike(pattern),
                    Hospital.city.ilike(pattern),
                    Hospital.state.ilike(pattern),
                )
            )

        if status_filter:
            query = query.filter(Hospital.status == status_filter)

        total = query.count()
        pages = max(1, (total + limit - 1) // limit) if total > 0 else 1
        offset = (page - 1) * limit

        hospitals = query.order_by(Hospital.id.asc()).offset(offset).limit(limit).all()

        items = []
        for h in hospitals:
            ward_count = db.query(Ward).filter(Ward.hospital_id == h.id).count()
            capacity_sum = db.query(func.sum(Ward.capacity)).filter(
                Ward.hospital_id == h.id,
                Ward.status == WardStatus.ACTIVE.value
            ).scalar()
            items.append({
                "id": h.id,
                "name": h.name,
                "code": h.code,
                "address": h.address,
                "city": h.city,
                "state": h.state,
                "country": h.country,
                "status": h.status,
                "created_at": h.created_at,
                "updated_at": h.updated_at,
                "ward_count": ward_count,
                "total_capacity": int(capacity_sum) if capacity_sum else 0,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
        }

    @staticmethod
    def get_hospital_by_id(db: Session, hospital_id: int) -> Dict[str, Any]:
        """
        Retrieve single hospital by ID with computed metrics or raise 404.
        """
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hospital with ID {hospital_id} not found."
            )

        ward_count = db.query(Ward).filter(Ward.hospital_id == hospital.id).count()
        capacity_sum = db.query(func.sum(Ward.capacity)).filter(
            Ward.hospital_id == hospital.id,
            Ward.status == WardStatus.ACTIVE.value
        ).scalar()

        return {
            "id": hospital.id,
            "name": hospital.name,
            "code": hospital.code,
            "address": hospital.address,
            "city": hospital.city,
            "state": hospital.state,
            "country": hospital.country,
            "status": hospital.status,
            "created_at": hospital.created_at,
            "updated_at": hospital.updated_at,
            "ward_count": ward_count,
            "total_capacity": int(capacity_sum) if capacity_sum else 0,
        }

    @staticmethod
    def create_hospital(db: Session, hospital_in: HospitalCreate) -> Dict[str, Any]:
        """
        Create a new hospital with unique code verification.
        """
        existing = db.query(Hospital).filter(
            func.lower(Hospital.code) == hospital_in.code.strip().lower()
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A hospital with code '{hospital_in.code}' already exists."
            )

        hospital = Hospital(
            name=hospital_in.name.strip(),
            code=hospital_in.code.strip().upper(),
            address=hospital_in.address.strip() if hospital_in.address else None,
            city=hospital_in.city.strip() if hospital_in.city else None,
            state=hospital_in.state.strip() if hospital_in.state else None,
            country=hospital_in.country.strip() if hospital_in.country else None,
            status=HospitalStatus.ACTIVE.value,
        )

        db.add(hospital)
        db.commit()
        db.refresh(hospital)

        return HospitalService.get_hospital_by_id(db, hospital.id)

    @staticmethod
    def update_hospital(db: Session, hospital_id: int, hospital_in: HospitalUpdate) -> Dict[str, Any]:
        """
        Update existing hospital metadata or status.
        """
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hospital with ID {hospital_id} not found."
            )

        update_data = hospital_in.model_dump(exclude_unset=True)

        if "code" in update_data and update_data["code"]:
            new_code = update_data["code"].strip().upper()
            if new_code != hospital.code:
                conflict = db.query(Hospital).filter(
                    Hospital.id != hospital_id,
                    func.lower(Hospital.code) == new_code.lower()
                ).first()
                if conflict:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Another hospital with code '{new_code}' already exists."
                    )
                hospital.code = new_code

        for field, value in update_data.items():
            if field == "code":
                continue
            if value is not None:
                if field == "status" and isinstance(value, HospitalStatusEnum):
                    value = value.value
                elif isinstance(value, str):
                    value = value.strip()
                setattr(hospital, field, value)

        db.commit()
        db.refresh(hospital)
        return HospitalService.get_hospital_by_id(db, hospital_id)

    @staticmethod
    def deactivate_hospital(db: Session, hospital_id: int) -> Dict[str, Any]:
        """
        Soft-deactivate hospital by setting status = INACTIVE.
        Preserves all historical wards and associated data.
        """
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hospital with ID {hospital_id} not found."
            )

        hospital.status = HospitalStatus.INACTIVE.value
        db.commit()
        db.refresh(hospital)
        return HospitalService.get_hospital_by_id(db, hospital_id)

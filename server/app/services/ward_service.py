from typing import Dict, Any, Optional
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.hospital import Hospital
from app.models.ward import Ward, WardStatus, WardType
from app.schemas.ward import WardCreate, WardUpdate, WardStatusEnum, WardTypeEnum


class WardService:
    @staticmethod
    def format_ward_response(db: Session, ward: Ward) -> Dict[str, Any]:
        """
        Formats ward ORM object into response dictionary with hospital_name attached.
        """
        hospital_name = None
        if ward.hospital_id:
            h = db.query(Hospital).filter(Hospital.id == ward.hospital_id).first()
            if h:
                hospital_name = h.name

        return {
            "id": ward.id,
            "hospital_id": ward.hospital_id,
            "hospital_name": hospital_name,
            "name": ward.name,
            "ward_type": ward.ward_type,
            "department": ward.department,
            "floor": ward.floor,
            "capacity": ward.capacity,
            "description": ward.description,
            "status": ward.status,
            "created_at": ward.created_at,
            "updated_at": ward.updated_at,
        }

    @staticmethod
    def get_wards(
        db: Session,
        hospital_id: Optional[int] = None,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        ward_type: Optional[str] = None,
        department: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch paginated list of wards scoped by hospital_id with optional search and filtering.
        """
        query = db.query(Ward)

        if hospital_id is not None:
            query = query.filter(Ward.hospital_id == hospital_id)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Ward.name.ilike(search_pattern),
                    Ward.department.ilike(search_pattern),
                    Ward.description.ilike(search_pattern),
                )
            )

        if ward_type:
            query = query.filter(Ward.ward_type == ward_type)

        if department:
            query = query.filter(Ward.department.ilike(f"%{department.strip()}%"))

        if status_filter:
            query = query.filter(Ward.status == status_filter)

        total = query.count()
        pages = max(1, (total + limit - 1) // limit) if total > 0 else 1
        offset = (page - 1) * limit

        wards = query.order_by(Ward.id.desc()).offset(offset).limit(limit).all()

        items = [WardService.format_ward_response(db, w) for w in wards]

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
        }

    @staticmethod
    def get_ward_by_id(db: Session, ward_id: int, hospital_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve single ward by ID and verify hospital_id access restriction.
        """
        query = db.query(Ward).filter(Ward.id == ward_id)
        if hospital_id is not None:
            query = query.filter(Ward.hospital_id == hospital_id)

        ward = query.first()
        if not ward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ward with ID {ward_id} not found."
            )
        return WardService.format_ward_response(db, ward)

    @staticmethod
    def create_ward(db: Session, ward_in: WardCreate, target_hospital_id: int) -> Dict[str, Any]:
        """
        Create new ward record within the target hospital. Enforces per-hospital ward name uniqueness.
        """
        # Validate target hospital exists
        hospital = db.query(Hospital).filter(Hospital.id == target_hospital_id).first()
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hospital with ID {target_hospital_id} does not exist."
            )

        # Check duplicate ward name within the SAME hospital
        existing_ward = db.query(Ward).filter(
            Ward.hospital_id == target_hospital_id,
            func.lower(Ward.name) == ward_in.name.strip().lower(),
        ).first()

        if existing_ward:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A ward named '{ward_in.name}' already exists in hospital '{hospital.name}'."
            )

        floor_str = str(ward_in.floor)
        ward = Ward(
            hospital_id=target_hospital_id,
            name=ward_in.name.strip(),
            ward_type=ward_in.ward_type.value if isinstance(ward_in.ward_type, WardTypeEnum) else str(ward_in.ward_type),
            department=ward_in.department.strip(),
            floor=floor_str,
            capacity=ward_in.capacity,
            description=ward_in.description.strip() if ward_in.description else None,
            status=WardStatus.ACTIVE.value,
        )

        db.add(ward)
        db.commit()
        db.refresh(ward)
        return WardService.format_ward_response(db, ward)

    @staticmethod
    def update_ward(db: Session, ward_id: int, ward_in: WardUpdate, hospital_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Update existing ward details while ensuring tenant isolation.
        """
        query = db.query(Ward).filter(Ward.id == ward_id)
        if hospital_id is not None:
            query = query.filter(Ward.hospital_id == hospital_id)

        ward = query.first()
        if not ward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ward with ID {ward_id} not found."
            )

        update_data = ward_in.model_dump(exclude_unset=True)

        new_name = update_data.get("name", ward.name)
        if new_name != ward.name:
            conflict = db.query(Ward).filter(
                Ward.id != ward_id,
                Ward.hospital_id == ward.hospital_id,
                func.lower(Ward.name) == new_name.strip().lower(),
            ).first()
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Another ward named '{new_name}' already exists in this hospital."
                )

        for field, value in update_data.items():
            if value is not None:
                if field == "ward_type" and isinstance(value, WardTypeEnum):
                    value = value.value
                elif field == "status" and isinstance(value, WardStatusEnum):
                    value = value.value
                elif field == "floor":
                    value = str(value)
                elif isinstance(value, str):
                    value = value.strip()
                setattr(ward, field, value)

        db.commit()
        db.refresh(ward)
        return WardService.format_ward_response(db, ward)

    @staticmethod
    def deactivate_ward(db: Session, ward_id: int, hospital_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Safely deactivate ward by setting status = INACTIVE (soft delete).
        """
        query = db.query(Ward).filter(Ward.id == ward_id)
        if hospital_id is not None:
            query = query.filter(Ward.hospital_id == hospital_id)

        ward = query.first()
        if not ward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ward with ID {ward_id} not found."
            )

        ward.status = WardStatus.INACTIVE.value
        db.commit()
        db.refresh(ward)
        return WardService.format_ward_response(db, ward)

    @staticmethod
    def get_ward_statistics(db: Session, hospital_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate database aggregate statistics for hospital wards scoped to hospital_id.
        """
        query = db.query(Ward)
        if hospital_id is not None:
            query = query.filter(Ward.hospital_id == hospital_id)

        total_wards = query.count()
        active_wards = query.filter(Ward.status == WardStatus.ACTIVE.value).count()
        inactive_wards = query.filter(Ward.status == WardStatus.INACTIVE.value).count()
        
        # Calculate total capacity across active wards
        cap_query = db.query(func.sum(Ward.capacity)).filter(Ward.status == WardStatus.ACTIVE.value)
        if hospital_id is not None:
            cap_query = cap_query.filter(Ward.hospital_id == hospital_id)

        sum_capacity = cap_query.scalar()
        total_capacity = int(sum_capacity) if sum_capacity else 0

        total_beds = 0
        occupied_beds = 0
        available_beds = total_capacity
        occupancy_rate = 0.0

        return {
            "total_wards": total_wards,
            "active_wards": active_wards,
            "inactive_wards": inactive_wards,
            "total_capacity": total_capacity,
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "available_beds": available_beds,
            "occupancy_rate": occupancy_rate,
        }

    @staticmethod
    def get_ward_occupancy(db: Session, ward_id: int, hospital_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get occupancy metrics for specific ward.
        """
        ward_data = WardService.get_ward_by_id(db, ward_id, hospital_id=hospital_id)
        return {
            "ward_id": ward_data["id"],
            "ward_name": ward_data["name"],
            "capacity": ward_data["capacity"],
            "occupied_beds": 0,
            "available_beds": ward_data["capacity"],
            "occupancy_rate": 0.0,
            "message": "Detailed bed occupancy tracking will be enabled in Phase 4 Bed Management.",
        }

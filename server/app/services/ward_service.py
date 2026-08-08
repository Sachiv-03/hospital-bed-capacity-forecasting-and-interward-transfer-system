from typing import Dict, Any, Optional
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.ward import Ward, WardStatus, WardType
from app.schemas.ward import WardCreate, WardUpdate, WardStatusEnum, WardTypeEnum


class WardService:
    @staticmethod
    def get_wards(
        db: Session,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        ward_type: Optional[str] = None,
        department: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch paginated list of wards with optional search and filtering.
        """
        query = db.query(Ward)

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

        items = query.order_by(Ward.id.desc()).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
        }

    @staticmethod
    def get_ward_by_id(db: Session, ward_id: int) -> Ward:
        """
        Retrieve single ward by ID or raise 404 exception.
        """
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ward with ID {ward_id} not found."
            )
        return ward

    @staticmethod
    def create_ward(db: Session, ward_in: WardCreate) -> Ward:
        """
        Create new ward record after checking for duplicate names in the same department.
        """
        # Check duplicate ward name in same department
        existing_ward = db.query(Ward).filter(
            func.lower(Ward.name) == ward_in.name.strip().lower(),
            func.lower(Ward.department) == ward_in.department.strip().lower(),
        ).first()

        if existing_ward:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A ward named '{ward_in.name}' already exists in department '{ward_in.department}'."
            )

        floor_str = str(ward_in.floor)
        ward = Ward(
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
        return ward

    @staticmethod
    def update_ward(db: Session, ward_id: int, ward_in: WardUpdate) -> Ward:
        """
        Update existing ward details.
        """
        ward = WardService.get_ward_by_id(db, ward_id)

        update_data = ward_in.model_dump(exclude_unset=True)

        # Check duplicate name conflict if name or department updated
        new_name = update_data.get("name", ward.name)
        new_dept = update_data.get("department", ward.department)

        if (new_name != ward.name or new_dept != ward.department):
            existing_conflict = db.query(Ward).filter(
                Ward.id != ward_id,
                func.lower(Ward.name) == new_name.strip().lower(),
                func.lower(Ward.department) == new_dept.strip().lower(),
            ).first()
            if existing_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Another ward named '{new_name}' already exists in department '{new_dept}'."
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
        return ward

    @staticmethod
    def deactivate_ward(db: Session, ward_id: int) -> Ward:
        """
        Safely deactivate ward by setting status = INACTIVE (soft delete).
        """
        ward = WardService.get_ward_by_id(db, ward_id)
        ward.status = WardStatus.INACTIVE.value
        db.commit()
        db.refresh(ward)
        return ward

    @staticmethod
    def get_ward_statistics(db: Session) -> Dict[str, Any]:
        """
        Calculate database aggregate statistics for hospital wards.
        """
        total_wards = db.query(Ward).count()
        active_wards = db.query(Ward).filter(Ward.status == WardStatus.ACTIVE.value).count()
        inactive_wards = db.query(Ward).filter(Ward.status == WardStatus.INACTIVE.value).count()
        
        # Calculate total capacity across active wards
        sum_capacity = db.query(func.sum(Ward.capacity)).filter(Ward.status == WardStatus.ACTIVE.value).scalar()
        total_capacity = int(sum_capacity) if sum_capacity else 0

        # Phase 3 temporary placeholders until Phase 4 Bed Management is implemented
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
    def get_ward_occupancy(db: Session, ward_id: int) -> Dict[str, Any]:
        """
        Get occupancy metrics for specific ward.
        """
        ward = WardService.get_ward_by_id(db, ward_id)
        return {
            "ward_id": ward.id,
            "ward_name": ward.name,
            "capacity": ward.capacity,
            "occupied_beds": 0,
            "available_beds": ward.capacity,
            "occupancy_rate": 0.0,
            "message": "Detailed bed occupancy tracking will be enabled in Phase 4 Bed Management.",
        }

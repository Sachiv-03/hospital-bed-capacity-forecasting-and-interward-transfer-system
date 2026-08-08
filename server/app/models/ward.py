import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database.session import Base


class WardStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class WardType(str, enum.Enum):
    GENERAL = "GENERAL"
    ICU = "ICU"
    EMERGENCY = "EMERGENCY"
    PEDIATRIC = "PEDIATRIC"
    MATERNITY = "MATERNITY"
    SURGICAL = "SURGICAL"
    ISOLATION = "ISOLATION"
    OTHER = "OTHER"


class Ward(Base):
    __tablename__ = "wards"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    ward_type = Column(String(50), nullable=False, default=WardType.GENERAL.value, index=True)
    department = Column(String(255), nullable=False, index=True)
    floor = Column(String(50), nullable=False)
    capacity = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=WardStatus.ACTIVE.value, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Ward id={self.id} name='{self.name}' type='{self.ward_type}' status='{self.status}'>"

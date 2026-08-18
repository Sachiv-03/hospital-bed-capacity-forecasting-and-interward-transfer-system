import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.session import Base


class WardStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class WardType(str, enum.Enum):
    GENERAL = "GENERAL"
    ICU = "ICU"
    STEP_DOWN = "STEP_DOWN"
    EMERGENCY = "EMERGENCY"
    PEDIATRIC = "PEDIATRIC"
    MATERNITY = "MATERNITY"
    SURGICAL = "SURGICAL"
    ISOLATION = "ISOLATION"
    OTHER = "OTHER"


class Ward(Base):
    __tablename__ = "wards"
    __table_args__ = (
        UniqueConstraint('hospital_id', 'name', name='uq_ward_hospital_name'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    ward_type = Column(String(50), nullable=False, default=WardType.GENERAL.value, index=True)
    department = Column(String(255), nullable=False, index=True)
    floor = Column(String(50), nullable=False)
    capacity = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=WardStatus.ACTIVE.value, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    hospital = relationship("Hospital", back_populates="wards")
    beds = relationship("Bed", back_populates="ward", cascade="all, delete-orphan")
    occupancy_events = relationship("OccupancyEvent", back_populates="ward", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Ward id={self.id} hospital_id={self.hospital_id} name='{self.name}' type='{self.ward_type}' status='{self.status}'>"

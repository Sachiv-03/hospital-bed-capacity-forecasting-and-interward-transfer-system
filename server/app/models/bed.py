import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.session import Base


class BedStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    CLEANING = "CLEANING"
    MAINTENANCE = "MAINTENANCE"
    RESERVED = "RESERVED"


class BedType(str, enum.Enum):
    STANDARD = "STANDARD"
    ICU = "ICU"
    ISOLATION = "ISOLATION"
    EMERGENCY = "EMERGENCY"


class Bed(Base):
    __tablename__ = "beds"
    __table_args__ = (
        UniqueConstraint("ward_id", "bed_number", name="uq_bed_ward_number"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    bed_number = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default=BedStatus.AVAILABLE.value, index=True)
    bed_type = Column(String(50), nullable=False, default=BedType.STANDARD.value, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    hospital = relationship("Hospital", back_populates="beds")
    ward = relationship("Ward", back_populates="beds")
    occupancy_events = relationship("OccupancyEvent", back_populates="bed", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Bed id={self.id} hospital_id={self.hospital_id} ward_id={self.ward_id} bed_number='{self.bed_number}' status='{self.status}'>"

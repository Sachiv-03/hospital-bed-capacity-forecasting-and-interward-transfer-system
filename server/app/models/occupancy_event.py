import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database.session import Base


class EventType(str, enum.Enum):
    ADMISSION = "ADMISSION"
    DISCHARGE = "DISCHARGE"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    BED_AVAILABLE = "BED_AVAILABLE"
    BED_CLEANING = "BED_CLEANING"
    BED_MAINTENANCE = "BED_MAINTENANCE"
    BED_RESERVED = "BED_RESERVED"
    BED_RELEASED = "BED_RELEASED"


class EventSource(str, enum.Enum):
    SIMULATOR = "SIMULATOR"
    MANUAL = "MANUAL"
    API = "API"


class OccupancyEvent(Base):
    __tablename__ = "occupancy_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    bed_id = Column(Integer, ForeignKey("beds.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    event_time = Column(DateTime, nullable=False, index=True)
    source = Column(String(50), nullable=False, default=EventSource.SIMULATOR.value, index=True)
    # Idempotency key — unique event identifier from the source system
    event_id = Column(String(100), nullable=False, unique=True, index=True)
    processed = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    hospital = relationship("Hospital", back_populates="occupancy_events")
    ward = relationship("Ward", back_populates="occupancy_events")
    bed = relationship("Bed", back_populates="occupancy_events")

    def __repr__(self):
        return (
            f"<OccupancyEvent id={self.id} event_id='{self.event_id}' "
            f"type='{self.event_type}' bed_id={self.bed_id} source='{self.source}'>"
        )

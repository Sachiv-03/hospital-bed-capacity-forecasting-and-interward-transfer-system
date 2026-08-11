import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base


class HospitalStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True, index=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default=HospitalStatus.ACTIVE.value, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="hospital", cascade="all, delete-orphan")
    wards = relationship("Ward", back_populates="hospital", cascade="all, delete-orphan")
    beds = relationship("Bed", back_populates="hospital", cascade="all, delete-orphan")
    occupancy_events = relationship("OccupancyEvent", back_populates="hospital", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Hospital id={self.id} code='{self.code}' name='{self.name}' status='{self.status}'>"

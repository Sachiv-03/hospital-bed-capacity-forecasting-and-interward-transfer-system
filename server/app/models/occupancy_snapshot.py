from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.session import Base


class OccupancySnapshot(Base):
    __tablename__ = "occupancy_snapshots"
    __table_args__ = (
        UniqueConstraint('hospital_id', 'ward_id', 'snapshot_time', name='uq_hospital_ward_snapshot_time'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_time = Column(DateTime, nullable=False, index=True)
    total_beds = Column(Integer, nullable=False, default=0)
    occupied_beds = Column(Integer, nullable=False, default=0)
    available_beds = Column(Integer, nullable=False, default=0)
    cleaning_beds = Column(Integer, nullable=False, default=0)
    reserved_beds = Column(Integer, nullable=False, default=0)
    maintenance_beds = Column(Integer, nullable=False, default=0)
    occupancy_percentage = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    hospital = relationship("Hospital")
    ward = relationship("Ward")

    def __repr__(self):
        return (
            f"<OccupancySnapshot id={self.id} ward_id={self.ward_id} "
            f"time='{self.snapshot_time}' occupancy={self.occupancy_percentage}%>"
        )

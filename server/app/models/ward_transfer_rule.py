from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base


class WardTransferRule(Base):
    __tablename__ = "ward_transfer_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Can target specific wards or ward types
    source_ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=True, index=True)
    destination_ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=True, index=True)
    source_ward_type = Column(String(50), nullable=True, index=True)
    destination_ward_type = Column(String(50), nullable=True, index=True)
    
    allowed = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=1)
    minimum_available_beds = Column(Integer, nullable=False, default=2)
    maximum_destination_occupancy = Column(Float, nullable=False, default=85.0)
    reason = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    hospital = relationship("Hospital")
    source_ward = relationship("Ward", foreign_keys=[source_ward_id])
    destination_ward = relationship("Ward", foreign_keys=[destination_ward_id])

    def __repr__(self):
        return (
            f"<WardTransferRule id={self.id} hospital_id={self.hospital_id} "
            f"src={self.source_ward_id or self.source_ward_type} -> "
            f"dst={self.destination_ward_id or self.destination_ward_type} allowed={self.allowed}>"
        )

import enum
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database.session import Base


class RecommendationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    STALE = "STALE"


class RecommendationPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransferRecommendation(Base):
    __tablename__ = "transfer_recommendations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    source_ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    destination_ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    
    recommended_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    source_current_occupancy = Column(Float, nullable=False)
    source_predicted_occupancy = Column(Float, nullable=False)
    destination_current_occupancy = Column(Float, nullable=False)
    destination_predicted_occupancy = Column(Float, nullable=False)
    
    available_beds = Column(Integer, nullable=False)
    safe_transfer_capacity = Column(Integer, nullable=False)
    recommended_transfer_count = Column(Integer, nullable=False)
    
    priority_score = Column(Float, nullable=False, index=True)
    priority_level = Column(String(20), nullable=False, default=RecommendationPriority.MEDIUM.value, index=True)
    status = Column(String(20), nullable=False, default=RecommendationStatus.PENDING.value, index=True)
    
    reason = Column(Text, nullable=False)
    warnings = Column(JSON, nullable=True)
    score_breakdown = Column(JSON, nullable=True)
    
    forecast_horizon_days = Column(Integer, nullable=False, default=1)
    forecast_confidence_lower = Column(Float, nullable=True)
    forecast_confidence_upper = Column(Float, nullable=True)
    
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    rejected_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    hospital = relationship("Hospital")
    source_ward = relationship("Ward", foreign_keys=[source_ward_id])
    destination_ward = relationship("Ward", foreign_keys=[destination_ward_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    rejected_by = relationship("User", foreign_keys=[rejected_by_id])

    def __repr__(self):
        return (
            f"<TransferRecommendation id={self.id} hospital_id={self.hospital_id} "
            f"source_ward_id={self.source_ward_id} -> dest_ward_id={self.destination_ward_id} "
            f"score={self.priority_score} priority={self.priority_level} status={self.status}>"
        )

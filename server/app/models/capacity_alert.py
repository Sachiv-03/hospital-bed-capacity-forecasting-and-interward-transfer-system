import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base


class AlertType(str, enum.Enum):
    HIGH_OCCUPANCY = "HIGH_OCCUPANCY"
    CRITICAL_OCCUPANCY = "CRITICAL_OCCUPANCY"
    LOW_AVAILABILITY = "LOW_AVAILABILITY"
    FORECAST_HIGH_OCCUPANCY = "FORECAST_HIGH_OCCUPANCY"
    FORECAST_CRITICAL_OCCUPANCY = "FORECAST_CRITICAL_OCCUPANCY"
    CAPACITY_EXCEEDANCE = "CAPACITY_EXCEEDANCE"
    RAPID_INCREASE = "RAPID_INCREASE"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class CapacityAlert(Base):
    __tablename__ = "capacity_alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(50), nullable=False, index=True)
    message = Column(Text, nullable=False)
    trigger_value = Column(Float, nullable=False)
    threshold_value = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default=AlertStatus.ACTIVE.value, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    explanation_json = Column(Text, nullable=True)

    hospital = relationship("Hospital")
    ward = relationship("Ward")
    acknowledged_by = relationship("User", foreign_keys=[acknowledged_by_id])

    def __repr__(self):
        return (
            f"<CapacityAlert id={self.id} ward_id={self.ward_id} "
            f"type='{self.alert_type}' severity='{self.severity}' status='{self.status}'>"
        )

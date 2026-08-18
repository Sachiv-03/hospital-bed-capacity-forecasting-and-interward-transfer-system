import enum
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base


class RiskLevel(str, enum.Enum):
    NORMAL = "NORMAL"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BedCapacityForecast(Base):
    __tablename__ = "bed_capacity_forecasts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    forecast_date = Column(Date, nullable=False, index=True)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    horizon_days = Column(Integer, nullable=False, default=7)
    predicted_occupied_beds = Column(Float, nullable=False)
    predicted_occupancy_percentage = Column(Float, nullable=False)
    lower_bound = Column(Float, nullable=True)
    upper_bound = Column(Float, nullable=True)
    risk_level = Column(String(20), nullable=False, default=RiskLevel.NORMAL.value, index=True)
    model_name = Column(String(50), nullable=False, default="SARIMA")
    model_version = Column(String(20), nullable=False, default="1.0")
    training_data_start = Column(Date, nullable=True)
    training_data_end = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    hospital = relationship("Hospital")
    ward = relationship("Ward")

    def __repr__(self):
        return (
            f"<BedCapacityForecast id={self.id} ward_id={self.ward_id} "
            f"date='{self.forecast_date}' predicted_occ={self.predicted_occupancy_percentage}% risk='{self.risk_level}'>"
        )

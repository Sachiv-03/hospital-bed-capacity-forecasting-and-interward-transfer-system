import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.session import Base


class AdmissionStatus(str, enum.Enum):
    ADMITTED = "ADMITTED"
    DISCHARGED = "DISCHARGED"
    CANCELLED = "CANCELLED"


class Admission(Base):
    __tablename__ = "admissions"
    __table_args__ = (
        UniqueConstraint("admission_number", name="uq_admission_number"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    bed_id = Column(Integer, ForeignKey("beds.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_number = Column(String(100), nullable=False, index=True)
    admission_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    discharge_date = Column(DateTime, nullable=True, index=True)
    status = Column(String(50), nullable=False, default=AdmissionStatus.ADMITTED.value, index=True)
    admission_reason = Column(Text, nullable=True)
    discharge_notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    discharged_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    hospital = relationship("Hospital", back_populates="admissions")
    patient = relationship("Patient", back_populates="admissions")
    ward = relationship("Ward")
    bed = relationship("Bed")
    creator = relationship("User", foreign_keys=[created_by])
    discharger = relationship("User", foreign_keys=[discharged_by])

    def __repr__(self):
        return f"<Admission id={self.id} admission_number='{self.admission_number}' patient_id={self.patient_id} bed_id={self.bed_id} status='{self.status}'>"

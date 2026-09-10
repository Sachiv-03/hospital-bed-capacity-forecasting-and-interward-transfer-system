from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class AdmissionStatusEnum(str, Enum):
    ADMITTED = "ADMITTED"
    DISCHARGED = "DISCHARGED"
    CANCELLED = "CANCELLED"


class AdmissionCreate(BaseModel):
    patient_id: int = Field(..., description="ID of patient to admit")
    ward_id: int = Field(..., description="Target ward ID")
    bed_id: int = Field(..., description="Target available bed ID")
    admission_reason: Optional[str] = Field(None, max_length=1000, description="Brief operational reason for admission")
    hospital_id: Optional[int] = Field(None, description="Hospital ID (super_admin override)")


class DischargeCreate(BaseModel):
    discharge_date: Optional[datetime] = Field(None, description="Discharge timestamp (defaults to current UTC time)")
    discharge_notes: Optional[str] = Field(None, max_length=1000, description="Minimal operational discharge notes")


class MinimalPatientInfo(BaseModel):
    id: int
    patient_identifier: str
    first_name: str
    last_name: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AdmissionResponse(BaseModel):
    id: int
    hospital_id: int
    patient_id: int
    ward_id: int
    bed_id: int
    admission_number: str
    admission_date: datetime
    discharge_date: Optional[datetime] = None
    status: AdmissionStatusEnum
    admission_reason: Optional[str] = None
    discharge_notes: Optional[str] = None
    created_by: Optional[int] = None
    discharged_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # Expanded metadata
    hospital_name: Optional[str] = None
    ward_name: Optional[str] = None
    bed_number: Optional[str] = None
    patient: Optional[MinimalPatientInfo] = None
    duration_hours: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class AdmissionListResponse(BaseModel):
    items: List[AdmissionResponse]
    total: int
    page: int
    limit: int
    pages: int

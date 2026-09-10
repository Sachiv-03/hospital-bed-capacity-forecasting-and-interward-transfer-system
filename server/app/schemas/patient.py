from enum import Enum
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class PatientStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100, examples=["John"])
    last_name: str = Field(..., min_length=1, max_length=100, examples=["Doe"])
    date_of_birth: date = Field(..., examples=["1985-05-15"])
    gender: str = Field(default="OTHER", examples=["MALE", "FEMALE", "OTHER"])
    phone: Optional[str] = Field(None, max_length=50, examples=["+1-555-0192"])
    email: Optional[EmailStr] = Field(None, examples=["john.doe@example.com"])
    address: Optional[str] = Field(None, examples=["123 Main St, Springfield"])
    emergency_contact_name: Optional[str] = Field(None, max_length=255, examples=["Jane Doe"])
    emergency_contact_phone: Optional[str] = Field(None, max_length=50, examples=["+1-555-0193"])


class PatientCreate(PatientBase):
    patient_identifier: Optional[str] = Field(None, max_length=100, description="Optional custom patient identifier; if omitted, system auto-generates HOSP-scoped identifier")
    hospital_id: Optional[int] = Field(None, description="Target hospital id (super admin only, otherwise current user hospital)")


class PatientUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    status: Optional[PatientStatusEnum] = None


class PatientStatusUpdate(BaseModel):
    status: PatientStatusEnum


class CurrentAdmissionInfo(BaseModel):
    admission_id: int
    admission_number: str
    admission_date: datetime
    ward_id: int
    ward_name: str
    bed_id: int
    bed_number: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class PatientResponse(PatientBase):
    id: int
    hospital_id: int
    patient_identifier: str
    status: PatientStatusEnum
    created_at: datetime
    updated_at: datetime
    hospital_name: Optional[str] = None
    current_admission: Optional[CurrentAdmissionInfo] = None

    model_config = ConfigDict(from_attributes=True)


class PatientListResponse(BaseModel):
    items: List[PatientResponse]
    total: int
    page: int
    limit: int
    pages: int

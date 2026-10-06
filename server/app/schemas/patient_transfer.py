from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class TransferStatusEnum(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TransferCreate(BaseModel):
    patient_id: int = Field(..., description="ID of active admitted patient to transfer")
    destination_ward_id: int = Field(..., description="ID of destination ward")
    destination_bed_id: int = Field(..., description="ID of destination available bed")
    reason: Optional[str] = Field(None, max_length=1000, description="Reason for inter-ward transfer")
    hospital_id: Optional[int] = Field(None, description="Hospital ID (optional, enforced by JWT auth)")


class TransferApproveRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=1000, description="Optional approval notes")


class TransferRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, max_length=1000, description="Mandatory reason for rejecting transfer")


class TransferResponse(BaseModel):
    id: int
    hospital_id: int
    patient_id: int
    admission_id: int
    source_ward_id: int
    destination_ward_id: int
    source_bed_id: int
    destination_bed_id: int
    reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    status: str
    requested_by: Optional[int] = None
    approved_by: Optional[int] = None
    rejected_by: Optional[int] = None
    completed_by: Optional[int] = None
    requested_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Extended human-readable attributes for UI display
    patient_name: Optional[str] = None
    patient_identifier: Optional[str] = None
    source_ward_name: Optional[str] = None
    destination_ward_name: Optional[str] = None
    source_bed_number: Optional[str] = None
    destination_bed_number: Optional[str] = None
    requested_by_name: Optional[str] = None
    approved_by_name: Optional[str] = None
    rejected_by_name: Optional[str] = None
    completed_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TransferListResponse(BaseModel):
    items: List[TransferResponse]
    total: int
    page: int
    limit: int
    pages: int

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TransferStatusEnum(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TransferCreate(BaseModel):
    patient_id: int = Field(
        ..., description="ID of active admitted patient to transfer"
    )
    destination_ward_id: int = Field(..., description="ID of destination ward")
    destination_bed_id: int = Field(..., description="ID of destination available bed")
    reason: str | None = Field(
        None, max_length=1000, description="Reason for inter-ward transfer"
    )
    hospital_id: int | None = Field(
        None, description="Hospital ID (optional, enforced by JWT auth)"
    )


class TransferApproveRequest(BaseModel):
    notes: str | None = Field(
        None, max_length=1000, description="Optional approval notes"
    )


class TransferRejectRequest(BaseModel):
    rejection_reason: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Mandatory reason for rejecting transfer",
    )


class TransferResponse(BaseModel):
    id: int
    hospital_id: int
    patient_id: int
    admission_id: int
    source_ward_id: int
    destination_ward_id: int
    source_bed_id: int
    destination_bed_id: int
    reason: str | None = None
    rejection_reason: str | None = None
    status: str
    requested_by: int | None = None
    approved_by: int | None = None
    rejected_by: int | None = None
    completed_by: int | None = None
    requested_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Extended human-readable attributes for UI display
    hospital_name: str | None = None
    patient_name: str | None = None
    patient_identifier: str | None = None
    source_ward_name: str | None = None
    destination_ward_name: str | None = None
    source_bed_number: str | None = None
    destination_bed_number: str | None = None
    requested_by_name: str | None = None
    approved_by_name: str | None = None
    rejected_by_name: str | None = None
    completed_by_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TransferListResponse(BaseModel):
    items: list[TransferResponse]
    total: int
    page: int
    limit: int
    pages: int

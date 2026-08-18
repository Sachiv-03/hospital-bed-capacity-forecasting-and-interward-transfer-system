from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TransferRuleBase(BaseModel):
    source_ward_id: Optional[int] = None
    destination_ward_id: Optional[int] = None
    source_ward_type: Optional[str] = None
    destination_ward_type: Optional[str] = None
    allowed: bool = True
    priority: int = Field(default=1, ge=1, le=10)
    minimum_available_beds: int = Field(default=2, ge=0)
    maximum_destination_occupancy: float = Field(default=85.0, ge=0.0, le=100.0)
    reason: Optional[str] = None
    active: bool = True


class TransferRuleCreate(TransferRuleBase):
    hospital_id: Optional[int] = None


class TransferRuleUpdate(BaseModel):
    allowed: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    minimum_available_beds: Optional[int] = Field(None, ge=0)
    maximum_destination_occupancy: Optional[float] = Field(None, ge=0.0, le=100.0)
    reason: Optional[str] = None
    active: Optional[bool] = None


class TransferRuleResponse(TransferRuleBase):
    id: int
    hospital_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

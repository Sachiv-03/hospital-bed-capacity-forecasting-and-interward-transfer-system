from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CapacityAlertResponse(BaseModel):
    id: int
    hospital_id: int
    ward_id: int
    ward_name: Optional[str] = None
    hospital_name: Optional[str] = None
    alert_type: str
    severity: str
    message: str
    trigger_value: float
    threshold_value: float
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CapacityAlertListResponse(BaseModel):
    items: List[CapacityAlertResponse]
    total: int

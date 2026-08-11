from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class EventTypeEnum(str, Enum):
    ADMISSION = "ADMISSION"
    DISCHARGE = "DISCHARGE"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    BED_AVAILABLE = "BED_AVAILABLE"
    BED_CLEANING = "BED_CLEANING"
    BED_MAINTENANCE = "BED_MAINTENANCE"
    BED_RESERVED = "BED_RESERVED"
    BED_RELEASED = "BED_RELEASED"


class EventSourceEnum(str, Enum):
    SIMULATOR = "SIMULATOR"
    MANUAL = "MANUAL"
    API = "API"


class OccupancyEventIngest(BaseModel):
    """Incoming event payload from simulator or external source."""
    event_id: str = Field(
        ...,
        min_length=5,
        max_length=100,
        description="Unique event identifier for idempotency (e.g. SIM-20260811-000001)",
        examples=["SIM-20260811-000001"],
    )
    hospital_id: int = Field(..., description="Hospital this event belongs to", examples=[1])
    ward_id: int = Field(..., description="Ward this event targets", examples=[5])
    bed_id: int = Field(..., description="Bed this event targets", examples=[103])
    event_type: EventTypeEnum = Field(..., examples=["ADMISSION"])
    event_time: datetime = Field(..., description="When the event occurred", examples=["2026-08-11T20:30:00"])
    source: EventSourceEnum = Field(default=EventSourceEnum.SIMULATOR)


class OccupancyEventResponse(BaseModel):
    id: int
    event_id: str
    hospital_id: int
    ward_id: int
    bed_id: int
    event_type: str
    event_time: datetime
    source: str
    processed: bool
    created_at: datetime
    # Enriched fields joined from related tables
    ward_name: Optional[str] = None
    bed_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OccupancyEventListResponse(BaseModel):
    items: List[OccupancyEventResponse]
    total: int
    page: int
    limit: int
    pages: int


class SimulateEventRequest(BaseModel):
    """Dev-only: trigger a simulated event, backend picks an appropriate bed."""
    hospital_id: int = Field(..., examples=[1])
    ward_id: Optional[int] = Field(None, description="Optional specific ward, random if omitted", examples=[5])
    event_type: EventTypeEnum = Field(..., examples=["ADMISSION"])

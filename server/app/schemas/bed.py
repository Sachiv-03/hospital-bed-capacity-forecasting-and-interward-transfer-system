from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class BedStatusEnum(str, Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    CLEANING = "CLEANING"
    MAINTENANCE = "MAINTENANCE"
    RESERVED = "RESERVED"


class BedTypeEnum(str, Enum):
    STANDARD = "STANDARD"
    ICU = "ICU"
    ISOLATION = "ISOLATION"
    EMERGENCY = "EMERGENCY"


class BedBase(BaseModel):
    bed_number: str = Field(..., min_length=1, max_length=50, examples=["ICU-01"])
    bed_type: BedTypeEnum = Field(default=BedTypeEnum.STANDARD, examples=["STANDARD"])
    status: BedStatusEnum = Field(default=BedStatusEnum.AVAILABLE, examples=["AVAILABLE"])


class BedCreate(BedBase):
    ward_id: int = Field(..., description="Ward this bed belongs to")
    hospital_id: Optional[int] = Field(None, description="Hospital (inferred from ward for normal users)")


class BedUpdate(BaseModel):
    bed_number: Optional[str] = Field(None, min_length=1, max_length=50)
    bed_type: Optional[BedTypeEnum] = None
    status: Optional[BedStatusEnum] = None


class BedResponse(BedBase):
    id: int
    hospital_id: int
    ward_id: int
    ward_name: Optional[str] = None
    hospital_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BedListResponse(BaseModel):
    items: List[BedResponse]
    total: int
    page: int
    limit: int
    pages: int

from enum import Enum
from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


class WardStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class WardTypeEnum(str, Enum):
    GENERAL = "GENERAL"
    ICU = "ICU"
    EMERGENCY = "EMERGENCY"
    PEDIATRIC = "PEDIATRIC"
    MATERNITY = "MATERNITY"
    SURGICAL = "SURGICAL"
    ISOLATION = "ISOLATION"
    OTHER = "OTHER"


class WardBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, json_schema_extra={"example": "Cardiology ICU A"})
    ward_type: WardTypeEnum = Field(default=WardTypeEnum.GENERAL, json_schema_extra={"example": "ICU"})
    department: str = Field(..., min_length=1, max_length=255, json_schema_extra={"example": "Cardiology"})
    floor: Union[str, int] = Field(..., json_schema_extra={"example": "Floor 2"})
    capacity: int = Field(..., gt=0, json_schema_extra={"example": 25}, description="Capacity must be a positive integer")
    description: Optional[str] = Field(None, json_schema_extra={"example": "Specialized intensive care unit for cardiac monitoring."})

    @field_validator("floor", mode="before")
    @classmethod
    def convert_floor_to_str(cls, v):
        if isinstance(v, int):
            return f"Floor {v}"
        return str(v)


class WardCreate(WardBase):
    hospital_id: Optional[int] = Field(None, description="Optional target hospital_id (SUPER_ADMIN only)")


class WardUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    ward_type: Optional[WardTypeEnum] = None
    department: Optional[str] = Field(None, min_length=1, max_length=255)
    floor: Optional[Union[str, int]] = Field(None)
    capacity: Optional[int] = Field(None, gt=0)
    description: Optional[str] = None
    status: Optional[WardStatusEnum] = None

    @field_validator("floor", mode="before")
    @classmethod
    def convert_floor_to_str(cls, v):
        if v is not None:
            if isinstance(v, int):
                return f"Floor {v}"
            return str(v)
        return v


class WardResponse(WardBase):
    id: int
    hospital_id: int
    hospital_name: Optional[str] = None
    floor: str
    status: WardStatusEnum
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WardListResponse(BaseModel):
    items: List[WardResponse]
    total: int
    page: int
    limit: int
    pages: int


class WardStatisticsResponse(BaseModel):
    total_wards: int
    active_wards: int
    inactive_wards: int
    total_capacity: int
    total_beds: int = 0
    occupied_beds: int = 0
    available_beds: int
    occupancy_rate: float = 0.0


class WardOccupancyResponse(BaseModel):
    ward_id: int
    ward_name: str
    capacity: int
    occupied_beds: int = 0
    available_beds: int
    occupancy_rate: float = 0.0
    message: str = "Detailed bed occupancy tracking will be enabled in Phase 4 Bed Management."

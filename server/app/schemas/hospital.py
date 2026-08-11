from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class HospitalStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class HospitalBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, json_schema_extra={"example": "Apollo Medical Center"})
    code: str = Field(..., min_length=2, max_length=50, json_schema_extra={"example": "H001"})
    address: Optional[str] = Field(None, json_schema_extra={"example": "123 Healthcare Boulevard"})
    city: Optional[str] = Field(None, max_length=100, json_schema_extra={"example": "Metropolis"})
    state: Optional[str] = Field(None, max_length=100, json_schema_extra={"example": "New York"})
    country: Optional[str] = Field(None, max_length=100, json_schema_extra={"example": "USA"})


class HospitalCreate(HospitalBase):
    pass


class HospitalUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    status: Optional[HospitalStatusEnum] = None


class HospitalResponse(HospitalBase):
    id: int
    status: HospitalStatusEnum
    created_at: datetime
    updated_at: datetime
    ward_count: int = 0
    total_capacity: int = 0

    model_config = ConfigDict(from_attributes=True)


class HospitalListResponse(BaseModel):
    items: List[HospitalResponse]
    total: int
    page: int
    limit: int
    pages: int

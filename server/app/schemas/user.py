from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRoleEnum(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    RECEPTIONIST = "receptionist"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255, json_schema_extra={"example": "Dr. Sarah Jenkins"})
    role: UserRoleEnum = Field(default=UserRoleEnum.DOCTOR, json_schema_extra={"example": "doctor"})


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100, json_schema_extra={"example": "SecureP@ss123"})
    hospital_id: Optional[int] = Field(None, description="ID of assigned hospital (optional for super_admin, defaults to 1 if not specified)")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., json_schema_extra={"example": "doctor@hospital.com"})
    password: str = Field(..., json_schema_extra={"example": "SecureP@ss123"})


class UserResponse(UserBase):
    id: int
    hospital_id: Optional[int] = None
    hospital_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

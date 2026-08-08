from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRoleEnum(str, Enum):
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


class UserLogin(BaseModel):
    email: EmailStr = Field(..., json_schema_extra={"example": "doctor@hospital.com"})
    password: str = Field(..., json_schema_extra={"example": "SecureP@ss123"})


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

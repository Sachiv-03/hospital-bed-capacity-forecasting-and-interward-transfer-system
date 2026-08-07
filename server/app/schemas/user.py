from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRoleEnum(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    RECEPTIONIST = "receptionist"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255, example="Dr. Sarah Jenkins")
    role: UserRoleEnum = Field(default=UserRoleEnum.DOCTOR, example="doctor")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100, example="SecureP@ss123")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., example="doctor@hospital.com")
    password: str = Field(..., example="SecureP@ss123")


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

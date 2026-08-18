from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    hospital_id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    timestamp: datetime
    metadata_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

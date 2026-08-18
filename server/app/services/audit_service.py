from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        hospital_id: int,
        action: str,
        resource_type: str,
        user_id: Optional[int] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Record a structured audit log event."""
        log_entry = AuditLog(
            hospital_id=hospital_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=datetime.utcnow(),
            metadata_json=metadata or {}
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.capacity_alert import CapacityAlertListResponse, CapacityAlertResponse
from app.services.alert_service import AlertService

router = APIRouter()
ADMIN_ROLES = [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]


@router.get(
    "",
    response_model=CapacityAlertListResponse,
    summary="List rule-based capacity alerts",
    description="Returns active and resolved capacity alerts with hospital-level tenant isolation.",
)
def list_alerts(
    hospital_id: Optional[int] = Query(None, description="Filter by hospital (SUPER_ADMIN only)"),
    ward_id: Optional[int] = Query(None, description="Filter by ward"),
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE / RESOLVED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (INFO / WARNING / CRITICAL)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role == UserRole.SUPER_ADMIN.value:
        target_hospital_id = hospital_id
    else:
        target_hospital_id = current_user.hospital_id

    alerts = AlertService.get_alerts(
        db=db,
        hospital_id=target_hospital_id,
        ward_id=ward_id,
        status=status,
        severity=severity,
    )

    items = [CapacityAlertResponse(**a) for a in alerts]
    return CapacityAlertListResponse(items=items, total=len(items))


@router.post(
    "/{alert_id}/resolve",
    response_model=CapacityAlertResponse,
    summary="Manually resolve a capacity alert",
)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES)),
):
    target_hospital_id = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    resolved = AlertService.resolve_alert(db=db, alert_id=alert_id, hospital_id=target_hospital_id)

    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found or access forbidden",
        )

    return CapacityAlertResponse.from_orm(resolved)

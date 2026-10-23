from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.models.ward import Ward
from app.schemas.capacity_alert import (
    CapacityAlertListResponse,
    CapacityAlertResponse,
    CapacityAlertDetailResponse,
    CapacityAlertSummaryResponse,
    AlertEvaluationResponse,
)
from app.services.alert_service import AlertService
from app.services.explainable_alert_service import ExplainableAlertService

router = APIRouter()
ADMIN_ROLES = [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]
ALL_ROLES = [
    UserRole.SUPER_ADMIN.value,
    UserRole.ADMIN.value,
    UserRole.DOCTOR.value,
    UserRole.NURSE.value,
    UserRole.RECEPTIONIST.value,
]


@router.get(
    "",
    response_model=CapacityAlertListResponse,
    summary="List rule-based and explainable capacity alerts",
    description="Returns active, acknowledged, and resolved capacity alerts with hospital-level tenant isolation.",
)
def list_alerts(
    hospital_id: Optional[int] = Query(None, description="Filter by hospital (SUPER_ADMIN only)"),
    ward_id: Optional[int] = Query(None, description="Filter by ward"),
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE / ACKNOWLEDGED / RESOLVED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (INFO / WARNING / HIGH / CRITICAL)"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role == UserRole.SUPER_ADMIN.value:
        target_hospital_id = hospital_id
    else:
        if hospital_id is not None and hospital_id != current_user.hospital_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Access to another hospital's alerts is forbidden",
            )
        target_hospital_id = current_user.hospital_id

    # Cross-hospital ward access validation
    if ward_id is not None:
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Ward not found")
        if target_hospital_id is not None and ward.hospital_id != target_hospital_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Cross-hospital ward access is forbidden",
            )

    alerts = AlertService.get_alerts(
        db=db,
        hospital_id=target_hospital_id,
        ward_id=ward_id,
        status=status,
        severity=severity,
        alert_type=alert_type,
    )

    items = [CapacityAlertResponse(**a) for a in alerts]
    return CapacityAlertListResponse(items=items, total=len(items))


@router.get(
    "/summary",
    response_model=CapacityAlertSummaryResponse,
    summary="Get aggregated counts and summary metrics for capacity alerts",
    description="Returns total active, critical, high, unacknowledged, and data-quality alert counts with hospital isolation.",
)
def get_alert_summary(
    hospital_id: Optional[int] = Query(None, description="Filter by hospital (SUPER_ADMIN only)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role == UserRole.SUPER_ADMIN.value:
        target_hospital_id = hospital_id
    else:
        if hospital_id is not None and hospital_id != current_user.hospital_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Access to another hospital's alert summary is forbidden",
            )
        target_hospital_id = current_user.hospital_id

    summary = AlertService.get_alert_summary(db=db, hospital_id=target_hospital_id)
    return CapacityAlertSummaryResponse(**summary)


@router.get(
    "/{alert_id}",
    response_model=CapacityAlertDetailResponse,
    summary="Get detailed explainable alert with evidence and triggered rules",
)
def get_alert_detail(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    target_hospital_id = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    alert = AlertService.get_alert_by_id(db=db, alert_id=alert_id, hospital_id=target_hospital_id)

    if not alert:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Alert not found or access forbidden",
        )

    return CapacityAlertDetailResponse(**alert)


@router.get(
    "/{alert_id}/explanation",
    response_model=CapacityAlertDetailResponse,
    summary="Get explainable AI details and evidence for a specific alert",
)
def get_alert_explanation(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    target_hospital_id = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    alert = AlertService.get_alert_by_id(db=db, alert_id=alert_id, hospital_id=target_hospital_id)

    if not alert:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Alert not found or access forbidden",
        )

    return CapacityAlertDetailResponse(**alert)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=CapacityAlertResponse,
    summary="Acknowledge a capacity alert",
    description="Marks an alert as acknowledged by authorized hospital staff.",
)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    target_hospital_id = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    acknowledged = AlertService.acknowledge_alert(
        db=db,
        alert_id=alert_id,
        user_id=current_user.id,
        hospital_id=target_hospital_id,
    )

    if not acknowledged:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Alert not found or access forbidden",
        )

    return CapacityAlertResponse(**acknowledged)


@router.post(
    "/{alert_id}/resolve",
    response_model=CapacityAlertResponse,
    summary="Manually resolve a capacity alert",
)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    target_hospital_id = None if current_user.role == UserRole.SUPER_ADMIN.value else current_user.hospital_id
    resolved = AlertService.resolve_alert(db=db, alert_id=alert_id, hospital_id=target_hospital_id)

    if not resolved:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Alert not found or access forbidden",
        )

    alert_dict = AlertService.get_alert_by_id(db=db, alert_id=alert_id, hospital_id=target_hospital_id)
    if alert_dict:
        return CapacityAlertResponse(**alert_dict)
    return CapacityAlertResponse.from_orm(resolved)


@router.post(
    "/evaluate",
    response_model=AlertEvaluationResponse,
    summary="Trigger Explainable Risk Evaluation",
    description="Evaluates explainable risk signals across wards using actual observed and forecasted data.",
)
def evaluate_alerts(
    hospital_id: Optional[int] = Query(None, description="Optional hospital ID filter (SUPER_ADMIN only)"),
    ward_id: Optional[int] = Query(None, description="Optional single ward ID to evaluate"),
    horizon: int = Query(7, ge=1, le=30, description="Forecast horizon in days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
):
    if current_user.role == UserRole.SUPER_ADMIN.value:
        target_hospital_id = hospital_id
    else:
        if hospital_id is not None and hospital_id != current_user.hospital_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Access to another hospital's risk evaluation is forbidden",
            )
        target_hospital_id = current_user.hospital_id

    if ward_id is not None:
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Ward not found")
        if target_hospital_id is not None and ward.hospital_id != target_hospital_id:
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Cross-hospital ward access is forbidden")

        eval_res = ExplainableAlertService.evaluate_ward_capacity_risk(
            db=db,
            ward_id=ward.id,
            hospital_id=ward.hospital_id,
            horizon=horizon,
            persist=True,
        )

        return AlertEvaluationResponse(
            status="SUCCESS",
            hospital_id=ward.hospital_id,
            wards_evaluated=1,
            alerts_count=1 if eval_res.get("has_alert") else 0,
            evaluated_at=eval_res["explanation"]["evidence"]["evaluated_at"],
            results=[eval_res],
        )

    res = ExplainableAlertService.evaluate_all_hospital_wards(
        db=db,
        hospital_id=target_hospital_id,
        horizon=horizon,
    )
    return AlertEvaluationResponse(**res)

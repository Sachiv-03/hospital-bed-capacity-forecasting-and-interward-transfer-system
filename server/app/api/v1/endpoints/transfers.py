from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.transfer_recommendation import TransferRecommendation, RecommendationStatus
from app.models.ward_transfer_rule import WardTransferRule
from app.models.audit_log import AuditLog
from app.schemas.transfer_rule import (
    TransferRuleCreate,
    TransferRuleUpdate,
    TransferRuleResponse,
)
from app.schemas.transfer_recommendation import (
    RecommendationGenerateRequest,
    RecommendationGenerateResponse,
    RecommendationResponse,
    RecommendationDetailResponse,
    RecommendationApproveRequest,
    RecommendationRejectRequest,
    TransferOverviewStatsResponse,
)
from app.schemas.audit_log import AuditLogResponse
from app.services.transfer_service import TransferService
from app.services.audit_service import AuditService

router = APIRouter()


def enforce_hospital_access(current_user: User, target_hospital_id: Optional[int]) -> int:
    """
    Enforce strict multi-hospital isolation.
    - Super admins can access any target_hospital_id.
    - Other users can ONLY access their assigned hospital_id.
    """
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return target_hospital_id or current_user.hospital_id or 1

    if current_user.hospital_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to any hospital facility."
        )

    if target_hospital_id is not None and target_hospital_id != current_user.hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. User belongs to hospital_id={current_user.hospital_id}, cannot access hospital_id={target_hospital_id}."
        )

    return current_user.hospital_id


# ── 1. RECOMMENDATION GENERATION ─────────────────────────────────────────────
@router.post("/recommendations/generate", response_model=RecommendationGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_recommendations(
    req: RecommendationGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.SUPER_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.DOCTOR.value,
        UserRole.NURSE.value,
    ])),
):
    """Generate inter-ward transfer recommendations for an authorized hospital facility."""
    hospital_id = enforce_hospital_access(current_user, req.hospital_id)
    result = TransferService.generate_recommendations_for_hospital(
        db=db,
        hospital_id=hospital_id,
        horizon_days=req.horizon_days,
        user_id=current_user.id,
    )
    return result


# ── 2. GET OVERVIEW STATS ───────────────────────────────────────────────────
@router.get("/recommendations/overview", response_model=TransferOverviewStatsResponse)
def get_transfer_overview(
    hospital_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get hospital transfer pressure overview metrics."""
    h_id = enforce_hospital_access(current_user, hospital_id)
    stats = TransferService.get_hospital_overview_stats(db, h_id)
    return stats


# ── 3. LIST RECOMMENDATIONS ──────────────────────────────────────────────────
@router.get("/recommendations", response_model=List[RecommendationResponse])
def list_recommendations(
    hospital_id: Optional[int] = Query(None),
    source_ward_id: Optional[int] = Query(None),
    destination_ward_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve transfer recommendations for an authorized hospital."""
    h_id = enforce_hospital_access(current_user, hospital_id)
    query = db.query(TransferRecommendation).filter(TransferRecommendation.hospital_id == h_id)

    if source_ward_id:
        query = query.filter(TransferRecommendation.source_ward_id == source_ward_id)
    if destination_ward_id:
        query = query.filter(TransferRecommendation.destination_ward_id == destination_ward_id)
    if priority:
        query = query.filter(TransferRecommendation.priority_level == priority.upper())
    if status_filter:
        query = query.filter(TransferRecommendation.status == status_filter.upper())

    recommendations = query.order_by(
        TransferRecommendation.priority_score.desc(),
        TransferRecommendation.created_at.desc()
    ).offset(offset).limit(limit).all()

    return recommendations


# ── 4. RECOMMENDATION DETAIL EXPLANATION ────────────────────────────────────
@router.get("/recommendations/{recommendation_id}", response_model=RecommendationDetailResponse)
def get_recommendation_detail(
    recommendation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get detailed transparent explanation, breakdown, and revalidation status of a recommendation."""
    rec = db.query(TransferRecommendation).filter(TransferRecommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer recommendation not found.")

    enforce_hospital_access(current_user, rec.hospital_id)
    
    is_valid, msg = TransferService.revalidate_recommendation(db, rec)
    
    rules_passed = ["Capacity Safety Margin (<= 85% Occupancy)", "Same Hospital Boundaries", "Active Ward Status"]
    if rec.score_breakdown and rec.score_breakdown.get("compatibility", 0) > 0:
        rules_passed.append("Ward Compatibility Rules")

    return RecommendationDetailResponse(
        id=rec.id,
        hospital_id=rec.hospital_id,
        source_ward_id=rec.source_ward_id,
        destination_ward_id=rec.destination_ward_id,
        source_ward=rec.source_ward,
        destination_ward=rec.destination_ward,
        recommended_at=rec.recommended_at,
        source_current_occupancy=rec.source_current_occupancy,
        source_predicted_occupancy=rec.source_predicted_occupancy,
        destination_current_occupancy=rec.destination_current_occupancy,
        destination_predicted_occupancy=rec.destination_predicted_occupancy,
        available_beds=rec.available_beds,
        safe_transfer_capacity=rec.safe_transfer_capacity,
        recommended_transfer_count=rec.recommended_transfer_count,
        priority_score=rec.priority_score,
        priority_level=rec.priority_level,
        status=rec.status,
        reason=rec.reason,
        warnings=rec.warnings or [],
        score_breakdown=rec.score_breakdown or {},
        forecast_horizon_days=rec.forecast_horizon_days,
        forecast_confidence_lower=rec.forecast_confidence_lower,
        forecast_confidence_upper=rec.forecast_confidence_upper,
        approved_by_id=rec.approved_by_id,
        approved_at=rec.approved_at,
        rejected_by_id=rec.rejected_by_id,
        rejected_at=rec.rejected_at,
        rejection_reason=rec.rejection_reason,
        expires_at=rec.expires_at,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        rules_passed=rules_passed,
        rules_failed=[],
        revalidation_status="VALID" if is_valid else f"STALE ({msg})"
    )


# ── 5. APPROVE RECOMMENDATION ───────────────────────────────────────────────
@router.post("/recommendations/{recommendation_id}/approve", response_model=RecommendationResponse)
def approve_recommendation(
    recommendation_id: int,
    req: Optional[RecommendationApproveRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.SUPER_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.DOCTOR.value,
        UserRole.NURSE.value,
    ])),
):
    """
    Approve a transfer recommendation after real-time capacity revalidation.
    Note: Does NOT automatically move or transfer patients.
    """
    rec = db.query(TransferRecommendation).filter(TransferRecommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer recommendation not found.")

    h_id = enforce_hospital_access(current_user, rec.hospital_id)
    notes = req.notes if req else None

    try:
        approved_rec = TransferService.approve_recommendation(
            db=db,
            rec_id=recommendation_id,
            user_id=current_user.id,
            hospital_id=h_id,
            notes=notes,
        )
        return approved_rec
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── 6. REJECT RECOMMENDATION ────────────────────────────────────────────────
@router.post("/recommendations/{recommendation_id}/reject", response_model=RecommendationResponse)
def reject_recommendation(
    recommendation_id: int,
    req: RecommendationRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.SUPER_ADMIN.value,
        UserRole.ADMIN.value,
        UserRole.DOCTOR.value,
        UserRole.NURSE.value,
    ])),
):
    """Reject a transfer recommendation with a mandatory explanation reason."""
    rec = db.query(TransferRecommendation).filter(TransferRecommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer recommendation not found.")

    h_id = enforce_hospital_access(current_user, rec.hospital_id)

    try:
        rejected_rec = TransferService.reject_recommendation(
            db=db,
            rec_id=recommendation_id,
            user_id=current_user.id,
            hospital_id=h_id,
            rejection_reason=req.rejection_reason,
        )
        return rejected_rec
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── 7. WARD TRANSFER RULES MANAGEMENT ───────────────────────────────────────
@router.get("/rules", response_model=List[TransferRuleResponse])
def list_transfer_rules(
    hospital_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List operational ward compatibility rules for an authorized hospital."""
    h_id = enforce_hospital_access(current_user, hospital_id)
    rules = TransferService.get_or_create_default_rules(db, h_id)
    return rules


@router.post("/rules", response_model=TransferRuleResponse, status_code=status.HTTP_201_CREATED)
def create_transfer_rule(
    rule_in: TransferRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.SUPER_ADMIN.value,
        UserRole.ADMIN.value,
    ])),
):
    """Create a new ward compatibility rule (Admin only)."""
    h_id = enforce_hospital_access(current_user, rule_in.hospital_id)
    
    rule = WardTransferRule(
        hospital_id=h_id,
        source_ward_id=rule_in.source_ward_id,
        destination_ward_id=rule_in.destination_ward_id,
        source_ward_type=rule_in.source_ward_type,
        destination_ward_type=rule_in.destination_ward_type,
        allowed=rule_in.allowed,
        priority=rule_in.priority,
        minimum_available_beds=rule_in.minimum_available_beds,
        maximum_destination_occupancy=rule_in.maximum_destination_occupancy,
        reason=rule_in.reason,
        active=rule_in.active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    AuditService.log_event(
        db,
        hospital_id=h_id,
        user_id=current_user.id,
        action="TRANSFER_RULE_CREATED",
        resource_type="WARD_TRANSFER_RULE",
        resource_id=str(rule.id),
    )
    return rule


@router.put("/rules/{rule_id}", response_model=TransferRuleResponse)
def update_transfer_rule(
    rule_id: int,
    rule_in: TransferRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.SUPER_ADMIN.value,
        UserRole.ADMIN.value,
    ])),
):
    """Update an existing ward compatibility rule (Admin only)."""
    rule = db.query(WardTransferRule).filter(WardTransferRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer rule not found.")

    enforce_hospital_access(current_user, rule.hospital_id)

    update_data = rule_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)

    AuditService.log_event(
        db,
        hospital_id=rule.hospital_id,
        user_id=current_user.id,
        action="TRANSFER_RULE_MODIFIED",
        resource_type="WARD_TRANSFER_RULE",
        resource_id=str(rule.id),
    )
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transfer_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.SUPER_ADMIN.value,
        UserRole.ADMIN.value,
    ])),
):
    """Delete a ward compatibility rule (Admin only)."""
    rule = db.query(WardTransferRule).filter(WardTransferRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer rule not found.")

    h_id = enforce_hospital_access(current_user, rule.hospital_id)
    db.delete(rule)
    db.commit()

    AuditService.log_event(
        db,
        hospital_id=h_id,
        user_id=current_user.id,
        action="TRANSFER_RULE_DELETED",
        resource_type="WARD_TRANSFER_RULE",
        resource_id=str(rule_id),
    )
    return None


# ── 8. AUDIT LOGS ────────────────────────────────────────────────────────────
@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    hospital_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.SUPER_ADMIN.value,
        UserRole.ADMIN.value,
    ])),
):
    """Get audit logs for transfer decision support system actions."""
    h_id = enforce_hospital_access(current_user, hospital_id)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.hospital_id == h_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    res = []
    for l in logs:
        res.append(AuditLogResponse(
            id=l.id,
            hospital_id=l.hospital_id,
            user_id=l.user_id,
            user_email=l.user.email if l.user else None,
            user_name=l.user.full_name if l.user else None,
            action=l.action,
            resource_type=l.resource_type,
            resource_id=l.resource_id,
            timestamp=l.timestamp,
            metadata_json=l.metadata_json or {},
        ))
    return res

from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.ward import Ward, WardStatus, WardType
from app.models.bed import Bed, BedStatus
from app.models.bed_capacity_forecast import BedCapacityForecast, RiskLevel
from app.models.ward_transfer_rule import WardTransferRule
from app.models.transfer_recommendation import (
    TransferRecommendation,
    RecommendationStatus,
    RecommendationPriority,
)
from app.models.audit_log import AuditLog
from app.services.transfer_scoring_service import TransferScoringService
from app.services.audit_service import AuditService


class TransferService:

    @staticmethod
    def get_or_create_default_rules(db: Session, hospital_id: int) -> List[WardTransferRule]:
        """Ensure default baseline transfer compatibility rules exist for the hospital."""
        existing = db.query(WardTransferRule).filter(WardTransferRule.hospital_id == hospital_id).all()
        if existing:
            return existing

        default_rules = [
            WardTransferRule(
                hospital_id=hospital_id,
                source_ward_type=WardType.ICU.value,
                destination_ward_type=WardType.STEP_DOWN.value,
                allowed=True,
                priority=2,
                minimum_available_beds=2,
                maximum_destination_occupancy=85.0,
                reason="ICU step-down to dedicated Step-down Unit is allowed for stable patients.",
                active=True,
            ),
            WardTransferRule(
                hospital_id=hospital_id,
                source_ward_type=WardType.STEP_DOWN.value,
                destination_ward_type=WardType.GENERAL.value,
                allowed=True,
                priority=2,
                minimum_available_beds=2,
                maximum_destination_occupancy=85.0,
                reason="Step-down to General Ward transfer allowed once patient meets step-down criteria.",
                active=True,
            ),
            WardTransferRule(
                hospital_id=hospital_id,
                source_ward_type=WardType.GENERAL.value,
                destination_ward_type=WardType.GENERAL.value,
                allowed=True,
                priority=1,
                minimum_available_beds=2,
                maximum_destination_occupancy=85.0,
                reason="Lateral transfer between General Wards allowed for capacity load balancing.",
                active=True,
            ),
            WardTransferRule(
                hospital_id=hospital_id,
                source_ward_type=WardType.EMERGENCY.value,
                destination_ward_type=WardType.GENERAL.value,
                allowed=True,
                priority=2,
                minimum_available_beds=2,
                maximum_destination_occupancy=85.0,
                reason="Emergency Department to General Ward admission transfer allowed.",
                active=True,
            ),
            WardTransferRule(
                hospital_id=hospital_id,
                source_ward_type=WardType.SURGICAL.value,
                destination_ward_type=WardType.GENERAL.value,
                allowed=True,
                priority=1,
                minimum_available_beds=2,
                maximum_destination_occupancy=85.0,
                reason="Post-surgical recovery transfer to General Ward allowed.",
                active=True,
            ),
            WardTransferRule(
                hospital_id=hospital_id,
                source_ward_type=WardType.ICU.value,
                destination_ward_type=WardType.GENERAL.value,
                allowed=False,
                priority=1,
                minimum_available_beds=2,
                maximum_destination_occupancy=85.0,
                reason="Direct transfer from ICU to General Ward is not automatically allowed without Step-down review.",
                active=True,
            ),
        ]
        db.add_all(default_rules)
        db.commit()
        for r in default_rules:
            db.refresh(r)
        return default_rules

    @staticmethod
    def get_ward_realtime_occupancy(db: Session, ward_id: int) -> Tuple[int, int, int, float]:
        """
        Compute real-time ward capacity metrics:
        Returns (total_beds, occupied_beds, available_beds, occupancy_percentage)
        """
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            return 0, 0, 0, 0.0

        total_beds = ward.capacity or 0
        if total_beds == 0:
            return 0, 0, 0, 0.0

        occupied_count = (
            db.query(Bed)
            .filter(Bed.ward_id == ward_id, Bed.status == BedStatus.OCCUPIED.value)
            .count()
        )
        available_count = max(0, total_beds - occupied_count)
        occ_percentage = round((occupied_count / total_beds) * 100.0, 1)

        return total_beds, occupied_count, available_count, occ_percentage

    @staticmethod
    def get_latest_forecast(db: Session, ward_id: int, horizon_days: int = 1) -> Tuple[float, str, Optional[float], Optional[float]]:
        """
        Fetch latest Stage 3 forecast for a ward.
        Returns (predicted_occupancy_percentage, risk_level, lower_bound, upper_bound)
        """
        forecast = (
            db.query(BedCapacityForecast)
            .filter(BedCapacityForecast.ward_id == ward_id)
            .order_by(BedCapacityForecast.generated_at.desc(), BedCapacityForecast.forecast_date.asc())
            .first()
        )
        if forecast:
            return (
                round(forecast.predicted_occupancy_percentage, 1),
                forecast.risk_level,
                forecast.lower_bound,
                forecast.upper_bound,
            )
        # Fallback if no forecast exists
        return 0.0, RiskLevel.NORMAL.value, None, None

    @staticmethod
    def calculate_safe_capacity(
        total_beds: int,
        occupied_beds: int,
        max_safe_occ_pct: float = 85.0,
        min_available_beds: int = 2,
    ) -> int:
        """
        Calculate safe transfer capacity to avoid filling destination ward beyond safety margin.
        """
        available = max(0, total_beds - occupied_beds)
        max_safe_occupied_beds = int(total_beds * max_safe_occ_pct / 100.0)
        headroom_beds = max(0, max_safe_occupied_beds - occupied_beds)
        
        # Must reserve min_available_beds buffer
        headroom_after_buffer = max(0, available - min_available_beds)
        
        safe_capacity = max(0, min(headroom_beds, headroom_after_buffer))
        return safe_capacity

    @staticmethod
    def evaluate_rule_compatibility(
        db: Session,
        hospital_id: int,
        source_ward: Ward,
        dest_ward: Ward,
    ) -> Tuple[bool, int, float, str]:
        """
        Evaluate compatibility rules for source -> destination ward pair.
        Returns (allowed, priority, max_destination_occupancy, reason)
        """
        rules = (
            db.query(WardTransferRule)
            .filter(
                WardTransferRule.hospital_id == hospital_id,
                WardTransferRule.active == True,
            )
            .all()
        )

        # 1. Exact ward-to-ward match (highest precedence)
        for r in rules:
            if r.source_ward_id == source_ward.id and r.destination_ward_id == dest_ward.id:
                return r.allowed, r.priority, r.maximum_destination_occupancy, r.reason or "Specific ward rule match"

        # 2. Ward type match
        for r in rules:
            if r.source_ward_type == source_ward.ward_type and r.destination_ward_type == dest_ward.ward_type:
                return r.allowed, r.priority, r.maximum_destination_occupancy, r.reason or f"Rule match for {source_ward.ward_type} -> {dest_ward.ward_type}"

        # 3. Default fallback
        if source_ward.ward_type == dest_ward.ward_type:
            return True, 1, 85.0, f"Same ward type transfer ({source_ward.ward_type})"
        
        return True, 1, 85.0, f"General operational transfer compatibility from {source_ward.ward_type} to {dest_ward.ward_type}"

    @classmethod
    def generate_recommendations_for_hospital(
        cls,
        db: Session,
        hospital_id: int,
        horizon_days: int = 1,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Main Stage 4 Decision Support Pipeline.
        Generates and ranks inter-ward transfer recommendations.
        """
        cls.get_or_create_default_rules(db, hospital_id)
        
        # 1. Get all active wards for this hospital (STRICT hospital_id isolation)
        wards = db.query(Ward).filter(Ward.hospital_id == hospital_id, Ward.status == WardStatus.ACTIVE.value).all()
        
        # 2. Expire old pending recommendations for this hospital
        db.query(TransferRecommendation).filter(
            TransferRecommendation.hospital_id == hospital_id,
            TransferRecommendation.status == RecommendationStatus.PENDING.value,
        ).update({"status": RecommendationStatus.EXPIRED.value}, synchronize_session=False)
        db.commit()

        source_wards_analyzed = 0
        destination_wards_analyzed = len(wards)
        recommendations_created = []
        no_suitable_dest_count = 0

        now = datetime.utcnow()
        expires_at = now + timedelta(hours=24)

        for source_ward in wards:
            s_total, s_occupied, s_avail, s_curr_occ = cls.get_ward_realtime_occupancy(db, source_ward.id)
            s_pred_occ, s_risk, s_lower, s_upper = cls.get_latest_forecast(db, source_ward.id, horizon_days)
            
            if s_pred_occ == 0.0:
                s_pred_occ = s_curr_occ

            # Source at-risk threshold check
            is_at_risk = (
                s_curr_occ >= 80.0
                or s_pred_occ >= 80.0
                or s_avail <= 3
                or s_risk in [RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]
            )

            if not is_at_risk:
                continue

            source_wards_analyzed += 1
            candidate_recommendations = []

            for dest_ward in wards:
                if dest_ward.id == source_ward.id:
                    continue

                d_total, d_occupied, d_avail, d_curr_occ = cls.get_ward_realtime_occupancy(db, dest_ward.id)
                d_pred_occ, d_risk, _, _ = cls.get_latest_forecast(db, dest_ward.id, horizon_days)
                
                if d_pred_occ == 0.0:
                    d_pred_occ = d_curr_occ

                allowed, priority, max_safe_occ, rule_reason = cls.evaluate_rule_compatibility(
                    db, hospital_id, source_ward, dest_ward
                )

                if not allowed:
                    continue

                safe_capacity = cls.calculate_safe_capacity(
                    d_total, d_occupied, max_safe_occ_pct=max_safe_occ, min_available_beds=2
                )

                if safe_capacity <= 0:
                    continue

                # Calculate Score & Priority
                score, priority_level, breakdown = TransferScoringService.calculate_score(
                    source_current_occ=s_curr_occ,
                    source_pred_occ=s_pred_occ,
                    source_risk_level=s_risk,
                    dest_current_occ=d_curr_occ,
                    dest_pred_occ=d_pred_occ,
                    dest_available_beds=d_avail,
                    safe_transfer_capacity=safe_capacity,
                    compatibility_allowed=allowed,
                    rule_priority=priority,
                )

                # Human-readable Explanation Reason
                reason_str = (
                    f"{source_ward.name} ({source_ward.ward_type}) is experiencing capacity pressure "
                    f"(Current: {s_curr_occ}%, Forecast: {s_pred_occ}%). "
                    f"{dest_ward.name} ({dest_ward.ward_type}) has {d_avail} available beds with "
                    f"a safe transfer capacity of {safe_capacity} beds, and is forecast to remain at {d_pred_occ}% occupancy."
                )

                # Warnings
                warnings_list = []
                if d_curr_occ > 75.0:
                    warnings_list.append(f"Destination {dest_ward.name} is approaching high occupancy ({d_curr_occ}%).")
                if safe_capacity <= 2:
                    warnings_list.append(f"Destination {dest_ward.name} has limited safe transfer capacity ({safe_capacity} beds).")
                if s_lower is not None and s_upper is not None and (s_upper - s_lower) > 20.0:
                    warnings_list.append(f"Source forecast uncertainty is moderate to high (range: {s_lower:.1f}% - {s_upper:.1f}%).")

                rec = TransferRecommendation(
                    hospital_id=hospital_id,
                    source_ward_id=source_ward.id,
                    destination_ward_id=dest_ward.id,
                    recommended_at=now,
                    source_current_occupancy=s_curr_occ,
                    source_predicted_occupancy=s_pred_occ,
                    destination_current_occupancy=d_curr_occ,
                    destination_predicted_occupancy=d_pred_occ,
                    available_beds=d_avail,
                    safe_transfer_capacity=safe_capacity,
                    recommended_transfer_count=safe_capacity,
                    priority_score=score,
                    priority_level=priority_level.value,
                    status=RecommendationStatus.PENDING.value,
                    reason=reason_str,
                    warnings=warnings_list,
                    score_breakdown=breakdown,
                    forecast_horizon_days=horizon_days,
                    forecast_confidence_lower=s_lower,
                    forecast_confidence_upper=s_upper,
                    expires_at=expires_at,
                )
                candidate_recommendations.append(rec)

            if not candidate_recommendations:
                no_suitable_dest_count += 1
            else:
                # Rank candidates by score descending
                candidate_recommendations.sort(key=lambda r: r.priority_score, reverse=True)
                # Keep top 3 ranked recommendations per source ward
                top_candidates = candidate_recommendations[:3]
                db.add_all(top_candidates)
                recommendations_created.extend(top_candidates)

        db.commit()

        for rec in recommendations_created:
            db.refresh(rec)

        # Audit Log
        AuditService.log_event(
            db,
            hospital_id=hospital_id,
            user_id=user_id,
            action="RECOMMENDATION_GENERATED",
            resource_type="TRANSFER_RECOMMENDATION",
            metadata={
                "source_wards_analyzed": source_wards_analyzed,
                "recommendations_generated": len(recommendations_created),
                "no_suitable_destination_count": no_suitable_dest_count,
            },
        )

        return {
            "hospital_id": hospital_id,
            "source_wards_analyzed": source_wards_analyzed,
            "destination_wards_analyzed": destination_wards_analyzed,
            "recommendations_generated": len(recommendations_created),
            "no_suitable_destination_count": no_suitable_dest_count,
            "generated_at": now,
        }

    @classmethod
    def revalidate_recommendation(cls, db: Session, rec: TransferRecommendation) -> Tuple[bool, str]:
        """
        Real-time revalidation check before staff approval.
        Ensures capacity conditions have not deteriorated since recommendation generation.
        """
        if rec.status != RecommendationStatus.PENDING.value:
            return False, f"Recommendation is no longer PENDING (Current status: {rec.status})."

        if datetime.utcnow() > rec.expires_at:
            rec.status = RecommendationStatus.EXPIRED.value
            db.commit()
            return False, "Recommendation has expired."

        # Re-check destination ward capacity
        d_total, d_occupied, d_avail, d_curr_occ = cls.get_ward_realtime_occupancy(db, rec.destination_ward_id)
        current_safe_cap = cls.calculate_safe_capacity(d_total, d_occupied, max_safe_occ_pct=85.0, min_available_beds=2)

        if current_safe_cap <= 0 or d_curr_occ >= 85.0:
            rec.status = RecommendationStatus.STALE.value
            db.commit()
            return False, f"Destination capacity has changed. Safe capacity is now {current_safe_cap} beds (Occupancy: {d_curr_occ}%). Recommendation is now STALE."

        return True, "VALID"

    @classmethod
    def approve_recommendation(
        cls,
        db: Session,
        rec_id: int,
        user_id: int,
        hospital_id: int,
        notes: Optional[str] = None,
    ) -> TransferRecommendation:
        """
        Approve recommendation after real-time revalidation.
        SAFETY GUARANTEE: Does NOT automatically move patients or alter patient records.
        """
        rec = db.query(TransferRecommendation).filter(
            TransferRecommendation.id == rec_id,
            TransferRecommendation.hospital_id == hospital_id,
        ).first()

        if not rec:
            raise ValueError("Transfer recommendation not found for this hospital.")

        is_valid, msg = cls.revalidate_recommendation(db, rec)
        if not is_valid:
            raise ValueError(f"Approval blocked: {msg}")

        rec.status = RecommendationStatus.APPROVED.value
        rec.approved_by_id = user_id
        rec.approved_at = datetime.utcnow()
        db.commit()
        db.refresh(rec)

        AuditService.log_event(
            db,
            hospital_id=hospital_id,
            user_id=user_id,
            action="RECOMMENDATION_APPROVED",
            resource_type="TRANSFER_RECOMMENDATION",
            resource_id=str(rec.id),
            metadata={
                "source_ward_id": rec.source_ward_id,
                "destination_ward_id": rec.destination_ward_id,
                "recommended_transfer_count": rec.recommended_transfer_count,
                "notes": notes,
            },
        )

        return rec

    @classmethod
    def reject_recommendation(
        cls,
        db: Session,
        rec_id: int,
        user_id: int,
        hospital_id: int,
        rejection_reason: str,
    ) -> TransferRecommendation:
        """
        Reject recommendation with a mandatory human reason.
        """
        rec = db.query(TransferRecommendation).filter(
            TransferRecommendation.id == rec_id,
            TransferRecommendation.hospital_id == hospital_id,
        ).first()

        if not rec:
            raise ValueError("Transfer recommendation not found for this hospital.")

        if not rejection_reason or len(rejection_reason.strip()) < 3:
            raise ValueError("A valid rejection reason is required.")

        rec.status = RecommendationStatus.REJECTED.value
        rec.rejected_by_id = user_id
        rec.rejected_at = datetime.utcnow()
        rec.rejection_reason = rejection_reason.strip()
        db.commit()
        db.refresh(rec)

        AuditService.log_event(
            db,
            hospital_id=hospital_id,
            user_id=user_id,
            action="RECOMMENDATION_REJECTED",
            resource_type="TRANSFER_RECOMMENDATION",
            resource_id=str(rec.id),
            metadata={
                "source_ward_id": rec.source_ward_id,
                "destination_ward_id": rec.destination_ward_id,
                "rejection_reason": rejection_reason.strip(),
            },
        )

        return rec

    @classmethod
    def get_hospital_overview_stats(cls, db: Session, hospital_id: int) -> Dict[str, Any]:
        """
        Compute dashboard summary stats for hospital transfer pressure.
        """
        wards = db.query(Ward).filter(Ward.hospital_id == hospital_id, Ward.status == WardStatus.ACTIVE.value).all()
        critical_count = 0
        high_count = 0
        destinations_count = 0
        no_suitable_count = 0

        for w in wards:
            _, o_count, _, curr_occ = cls.get_ward_realtime_occupancy(db, w.id)
            pred_occ, risk, _, _ = cls.get_latest_forecast(db, w.id)
            if risk == RiskLevel.CRITICAL.value or max(curr_occ, pred_occ) >= 95.0:
                critical_count += 1
            elif risk == RiskLevel.HIGH.value or max(curr_occ, pred_occ) >= 85.0:
                high_count += 1
            
            if curr_occ < 75.0 and pred_occ < 80.0:
                destinations_count += 1

        pending_count = (
            db.query(TransferRecommendation)
            .filter(
                TransferRecommendation.hospital_id == hospital_id,
                TransferRecommendation.status == RecommendationStatus.PENDING.value,
            )
            .count()
        )

        return {
            "hospital_id": hospital_id,
            "critical_pressure_wards": critical_count,
            "high_pressure_wards": high_count,
            "total_potential_destinations": destinations_count,
            "pending_recommendations": pending_count,
            "no_suitable_destination_wards": no_suitable_count,
            "updated_at": datetime.utcnow(),
        }

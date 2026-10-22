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
from app.models.patient import Patient
from app.models.admission import Admission, AdmissionStatus
from app.models.transfer import Transfer, TransferStatus
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
    def get_ward_detailed_capacity_metrics(db: Session, ward_id: int) -> Dict[str, Any]:
        """
        Compute real-time ward capacity and bed availability:
        effective_capacity = total_capacity - maintenance_beds - cleaning_beds
        available_beds = max(0, min(available_beds_count - pending_transfers, effective_capacity - occupied_beds - reserved_beds - pending_transfers))
        Accounts for cleaning, maintenance, reserved beds, and pending transfers.
        """
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            return {
                "ward_id": ward_id,
                "total_beds": 0,
                "effective_capacity": 0,
                "occupied_beds": 0,
                "available_beds": 0,
                "cleaning_beds": 0,
                "maintenance_beds": 0,
                "reserved_beds": 0,
                "pending_incoming_transfers": 0,
                "occupancy_percentage": 0.0,
                "available_candidate_beds": [],
            }

        total_beds = ward.capacity or 0
        beds = db.query(Bed).filter(Bed.ward_id == ward_id).all()

        counts = {
            BedStatus.AVAILABLE.value: 0,
            BedStatus.OCCUPIED.value: 0,
            BedStatus.CLEANING.value: 0,
            BedStatus.MAINTENANCE.value: 0,
            BedStatus.RESERVED.value: 0,
        }
        for b in beds:
            if b.status in counts:
                counts[b.status] += 1

        occupied_count = counts[BedStatus.OCCUPIED.value]
        cleaning_count = counts[BedStatus.CLEANING.value]
        maintenance_count = counts[BedStatus.MAINTENANCE.value]
        reserved_count = counts[BedStatus.RESERVED.value]

        # Pending transfers targeting this ward (REQUESTED or APPROVED)
        pending_transfers = db.query(Transfer).filter(
            Transfer.destination_ward_id == ward_id,
            Transfer.status.in_([TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value]),
        ).all()
        pending_incoming = len(pending_transfers)
        reserved_bed_ids = {t.destination_bed_id for t in pending_transfers if t.destination_bed_id}

        # Effective capacity = total beds minus maintenance & cleaning
        effective_capacity = max(0, total_beds - maintenance_count - cleaning_count)

        # Candidate beds: status is AVAILABLE and not targeted by a pending transfer
        candidate_beds = [b for b in beds if b.status == BedStatus.AVAILABLE.value and b.id not in reserved_bed_ids]

        # Available beds calculation
        calculated_available = max(0, effective_capacity - occupied_count - reserved_count - pending_incoming)
        actual_available = len(candidate_beds)
        final_available_beds = min(calculated_available, actual_available) if actual_available > 0 else calculated_available

        occ_percentage = round((occupied_count / total_beds) * 100.0, 1) if total_beds > 0 else 0.0

        return {
            "ward_id": ward_id,
            "ward": ward,
            "total_beds": total_beds,
            "effective_capacity": effective_capacity,
            "occupied_beds": occupied_count,
            "available_beds": final_available_beds,
            "cleaning_beds": cleaning_count,
            "maintenance_beds": maintenance_count,
            "reserved_beds": reserved_count,
            "pending_incoming_transfers": pending_incoming,
            "occupancy_percentage": occ_percentage,
            "available_candidate_beds": candidate_beds,
        }

    @classmethod
    def get_ward_realtime_occupancy(cls, db: Session, ward_id: int) -> Tuple[int, int, int, float]:
        """
        Compute real-time ward capacity metrics:
        Returns (total_beds, occupied_beds, available_beds, occupancy_percentage)
        """
        metrics = cls.get_ward_detailed_capacity_metrics(db, ward_id)
        return metrics["total_beds"], metrics["occupied_beds"], metrics["available_beds"], metrics["occupancy_percentage"]

    @staticmethod
    def get_detailed_ward_forecast(db: Session, ward_id: int, horizon_days: int = 1, effective_capacity: int = 0) -> Dict[str, Any]:
        """
        Fetch latest SARIMA forecast for a ward without re-fitting.
        Calculates forecast_available_beds = applicable_capacity - forecasted_occupied_beds
        and identifies staleness or missing forecast data.
        """
        forecast = (
            db.query(BedCapacityForecast)
            .filter(BedCapacityForecast.ward_id == ward_id)
            .order_by(BedCapacityForecast.generated_at.desc(), BedCapacityForecast.forecast_date.asc())
            .first()
        )
        if not forecast:
            return {
                "has_forecast": False,
                "status": "UNAVAILABLE",
                "predicted_occupancy_percentage": None,
                "predicted_occupied_beds": None,
                "forecast_available_beds": None,
                "lower_bound": None,
                "upper_bound": None,
                "risk_level": RiskLevel.NORMAL.value,
                "forecast_date": None,
                "generated_at": None,
                "warnings": ["Forecast data unavailable for this ward; recommendations based on live verified capacity only."],
            }

        # Check staleness: older than 48 hours
        is_stale = False
        warnings = []
        if forecast.generated_at and forecast.generated_at < datetime.utcnow() - timedelta(hours=48):
            is_stale = True
            warnings.append(f"Forecast generated on {forecast.generated_at.strftime('%Y-%m-%d')} (>48h ago) may be stale; staff re-verification required.")

        pred_occ_pct = round(forecast.predicted_occupancy_percentage, 1)
        pred_occ_beds = round(forecast.predicted_occupied_beds, 1)

        applicable_capacity = effective_capacity if effective_capacity > 0 else (forecast.ward.capacity if forecast.ward else 0)
        forecast_avail_beds = max(0.0, round(applicable_capacity - pred_occ_beds, 1)) if applicable_capacity > 0 else 0.0

        return {
            "has_forecast": True,
            "status": "STALE" if is_stale else "VERIFIED",
            "predicted_occupancy_percentage": pred_occ_pct,
            "predicted_occupied_beds": pred_occ_beds,
            "forecast_available_beds": forecast_avail_beds,
            "lower_bound": forecast.lower_bound,
            "upper_bound": forecast.upper_bound,
            "risk_level": forecast.risk_level,
            "forecast_date": forecast.forecast_date.isoformat() if hasattr(forecast.forecast_date, "isoformat") else str(forecast.forecast_date),
            "generated_at": forecast.generated_at,
            "warnings": warnings,
        }

    @classmethod
    def get_latest_forecast(cls, db: Session, ward_id: int, horizon_days: int = 1) -> Tuple[float, str, Optional[float], Optional[float]]:
        """
        Fetch latest Stage 3 forecast for a ward.
        Returns (predicted_occupancy_percentage, risk_level, lower_bound, upper_bound)
        """
        fc = cls.get_detailed_ward_forecast(db, ward_id, horizon_days)
        if fc["has_forecast"]:
            return (
                fc["predicted_occupancy_percentage"] or 0.0,
                fc["risk_level"],
                fc["lower_bound"],
                fc["upper_bound"],
            )
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
                warnings_list.append("Staffing ratio and equipment constraints are not recorded in system; authorized staff clinical verification required.")

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

    @classmethod
    def recommend_destinations_for_patient(
        cls,
        db: Session,
        hospital_id: int,
        patient_id: Optional[int] = None,
        transfer_id: Optional[int] = None,
        admission_id: Optional[int] = None,
        source_ward_id: Optional[int] = None,
        required_bed_type: Optional[str] = None,
        horizon_days: int = 1,
    ) -> Dict[str, Any]:
        """
        Phase 11: Patient-Centric Inter-Ward Transfer Recommendation Engine.
        Analyzes current live capacity, existing forecasts, patient category/bed type compatibility,
        and ward compatibility rules to recommend and rank suitable destination wards.
        Human-in-the-loop decision support: Does not automatically execute transfers.
        """
        cls.get_or_create_default_rules(db, hospital_id)

        patient_name = None
        patient_identifier = None

        # 1. Resolve Patient & Source Ward Context
        if transfer_id:
            transfer = db.query(Transfer).filter(
                Transfer.id == transfer_id,
                Transfer.hospital_id == hospital_id,
            ).first()
            if not transfer:
                raise ValueError(f"Transfer request #{transfer_id} not found in this hospital.")
            source_ward_id = transfer.source_ward_id
            patient_id = transfer.patient_id
            if transfer.patient:
                patient_name = f"{transfer.patient.first_name} {transfer.patient.last_name}"
                patient_identifier = transfer.patient.patient_identifier

        elif patient_id:
            patient = db.query(Patient).filter(
                Patient.id == patient_id,
                Patient.hospital_id == hospital_id,
            ).first()
            if not patient:
                raise ValueError(f"Patient ID #{patient_id} not found in this hospital.")
            patient_name = f"{patient.first_name} {patient.last_name}"
            patient_identifier = patient.patient_identifier

            active_admission = db.query(Admission).filter(
                Admission.patient_id == patient_id,
                Admission.hospital_id == hospital_id,
                Admission.status == AdmissionStatus.ADMITTED.value,
            ).first()
            if not active_admission:
                raise ValueError(f"Patient '{patient_name}' does not have an active admission in this hospital.")
            source_ward_id = active_admission.ward_id

        elif admission_id:
            adm = db.query(Admission).filter(
                Admission.id == admission_id,
                Admission.hospital_id == hospital_id,
            ).first()
            if not adm:
                raise ValueError(f"Admission #{admission_id} not found in this hospital.")
            source_ward_id = adm.ward_id
            patient_id = adm.patient_id
            if adm.patient:
                patient_name = f"{adm.patient.first_name} {adm.patient.last_name}"
                patient_identifier = adm.patient.patient_identifier

        elif source_ward_id:
            src = db.query(Ward).filter(
                Ward.id == source_ward_id,
                Ward.hospital_id == hospital_id,
            ).first()
            if not src:
                raise ValueError(f"Source ward ID #{source_ward_id} not found in this hospital.")

        else:
            raise ValueError("A patient_id, transfer_id, or source_ward_id must be provided.")

        source_ward = db.query(Ward).filter(
            Ward.id == source_ward_id,
            Ward.hospital_id == hospital_id,
        ).first()
        if not source_ward:
            raise ValueError(f"Source ward ID #{source_ward_id} not found in this hospital.")

        # Source ward live metrics & forecast
        s_metrics = cls.get_ward_detailed_capacity_metrics(db, source_ward_id)
        s_forecast = cls.get_detailed_ward_forecast(db, source_ward_id, horizon_days, s_metrics["effective_capacity"])
        s_curr_occ = s_metrics["occupancy_percentage"]
        s_pred_occ = s_forecast["predicted_occupancy_percentage"] if s_forecast["has_forecast"] else s_curr_occ
        s_risk = s_forecast["risk_level"] if s_forecast["has_forecast"] else RiskLevel.NORMAL.value

        # 2. Query all candidate active wards in the same hospital (excluding source ward)
        candidate_wards = db.query(Ward).filter(
            Ward.hospital_id == hospital_id,
            Ward.status == WardStatus.ACTIVE.value,
            Ward.id != source_ward_id,
        ).order_by(Ward.name).all()

        evaluated_destinations = []

        for dest_ward in candidate_wards:
            d_metrics = cls.get_ward_detailed_capacity_metrics(db, dest_ward.id)
            d_total = d_metrics["total_beds"]
            d_avail = d_metrics["available_beds"]
            d_curr_occ = d_metrics["occupancy_percentage"]
            d_effective_cap = d_metrics["effective_capacity"]
            candidate_beds = d_metrics["available_candidate_beds"]

            # Forecast for destination ward
            d_forecast = cls.get_detailed_ward_forecast(db, dest_ward.id, horizon_days, d_effective_cap)
            d_pred_occ = d_forecast["predicted_occupancy_percentage"] if d_forecast["has_forecast"] else d_curr_occ

            # Compatibility rule
            allowed, priority, max_safe_occ, rule_reason = cls.evaluate_rule_compatibility(
                db, hospital_id, source_ward, dest_ward
            )

            # Bed-type compatibility check
            if required_bed_type:
                type_matching_beds = [b for b in candidate_beds if b.bed_type == required_bed_type]
            else:
                type_matching_beds = candidate_beds

            # Calculate safe capacity
            safe_capacity = cls.calculate_safe_capacity(
                d_total, d_metrics["occupied_beds"], max_safe_occ_pct=max_safe_occ, min_available_beds=1
            )

            # Determine eligibility
            ineligibility_reasons = []
            warnings = list(d_forecast.get("warnings", []))
            reasons = []

            if d_total <= 0:
                ineligibility_reasons.append("Ward capacity is 0 or unconfigured.")
            if d_avail <= 0 or len(candidate_beds) == 0:
                ineligibility_reasons.append("No verified available physical beds currently in ward.")
            if not allowed:
                ineligibility_reasons.append(f"Ward transfer policy restricts transfer: {rule_reason}")
            if safe_capacity <= 0 or d_curr_occ >= max_safe_occ:
                ineligibility_reasons.append(f"Ward is at or above safety occupancy threshold ({d_curr_occ}% current, {max_safe_occ}% maximum safe).")
            if required_bed_type and len(type_matching_beds) == 0:
                ineligibility_reasons.append(f"No available beds matching required bed type '{required_bed_type}' (Available of other types: {len(candidate_beds)}).")
            if d_forecast.get("predicted_occupancy_percentage") is not None and d_forecast["predicted_occupancy_percentage"] >= 90.0:
                warnings.append(f"Destination forecast predicts high pressure ({d_forecast['predicted_occupancy_percentage']}%).")

            is_eligible = len(ineligibility_reasons) == 0

            # Transparent Scoring
            if not is_eligible:
                score = 0.0
                priority_level = "LOW"
                breakdown = {
                    "source_urgency": 0.0,
                    "destination_capacity": 0.0,
                    "future_capacity": 0.0,
                    "compatibility": 0.0,
                    "max_possible": 100.0,
                }
            else:
                score, priority_enum, breakdown = TransferScoringService.calculate_score(
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
                priority_level = priority_enum.value

                # Construct Explainability Reasons
                reasons.append(f"Capacity available: {d_avail} verified bed(s) available with safe headroom for {safe_capacity} transfer(s) below {max_safe_occ}% safety limit.")
                if d_forecast["has_forecast"]:
                    reasons.append(f"Forecast occupancy: Destination projected to remain at {d_pred_occ}% on target date (~{d_forecast['forecast_available_beds']} beds available).")
                else:
                    reasons.append("Live bed capacity verified; forecast data unavailable.")
                reasons.append(f"Compatibility match: {rule_reason}")
                if required_bed_type and len(type_matching_beds) > 0:
                    reasons.append(f"Specialty match: {len(type_matching_beds)} verified available bed(s) matching '{required_bed_type}'.")

            # Standard constraints & warnings
            warnings.append("Staffing ratio and specialty equipment constraints are not recorded in system; authorized staff physical verification is required.")
            if d_metrics["pending_incoming_transfers"] > 0:
                warnings.append(f"{d_metrics['pending_incoming_transfers']} other transfer request(s) are currently pending for this destination ward.")
            if d_metrics["cleaning_beds"] > 0 or d_metrics["maintenance_beds"] > 0:
                warnings.append(f"{d_metrics['cleaning_beds']} bed(s) in cleaning, {d_metrics['maintenance_beds']} bed(s) under maintenance.")

            available_beds_list = [
                {
                    "id": b.id,
                    "bed_number": b.bed_number,
                    "bed_type": b.bed_type,
                    "status": b.status,
                }
                for b in (type_matching_beds if required_bed_type else candidate_beds)[:15]
            ]

            dest_rec = {
                "ward_id": dest_ward.id,
                "ward_name": dest_ward.name,
                "ward_type": dest_ward.ward_type,
                "department": dest_ward.department,
                "floor": dest_ward.floor,
                "capacity": d_total,
                "current_occupied_beds": d_metrics["occupied_beds"],
                "current_available_beds": d_avail,
                "current_occupancy_percentage": d_curr_occ,
                "cleaning_beds": d_metrics["cleaning_beds"],
                "maintenance_beds": d_metrics["maintenance_beds"],
                "reserved_beds": d_metrics["reserved_beds"],
                "pending_incoming_transfers": d_metrics["pending_incoming_transfers"],
                "effective_capacity": d_effective_cap,
                "safe_transfer_capacity": safe_capacity,
                "forecasted_occupied_beds": d_forecast["predicted_occupied_beds"],
                "forecasted_occupancy_percentage": d_forecast["predicted_occupancy_percentage"],
                "forecast_available_beds": d_forecast["forecast_available_beds"],
                "forecast_target_date": d_forecast["forecast_date"],
                "forecast_risk_level": d_forecast["risk_level"],
                "forecast_status": d_forecast["status"],
                "is_eligible": is_eligible,
                "ineligibility_reasons": ineligibility_reasons,
                "score": score,
                "rank": 0,
                "priority_level": priority_level,
                "reasons": reasons,
                "warnings": warnings,
                "score_breakdown": breakdown,
                "compatibility_allowed": allowed,
                "compatibility_rule": rule_reason,
                "available_candidate_beds": available_beds_list,
                "verification_required_statement": "Staff must physically verify bed readiness and clinically approve the transfer. Decision support only.",
            }
            evaluated_destinations.append(dest_rec)

        # 3. Rank Candidates: Eligible first (by score DESC, then available_beds DESC), followed by Ineligible
        eligible_candidates = [r for r in evaluated_destinations if r["is_eligible"]]
        ineligible_candidates = [r for r in evaluated_destinations if not r["is_eligible"]]

        eligible_candidates.sort(key=lambda r: (r["score"], r["current_available_beds"]), reverse=True)
        ineligible_candidates.sort(key=lambda r: r["current_available_beds"], reverse=True)

        for i, r in enumerate(eligible_candidates):
            r["rank"] = i + 1

        for i, r in enumerate(ineligible_candidates):
            r["rank"] = len(eligible_candidates) + i + 1

        all_recommendations = eligible_candidates + ineligible_candidates

        return {
            "hospital_id": hospital_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "patient_identifier": patient_identifier,
            "source_ward_id": source_ward_id,
            "source_ward_name": source_ward.name,
            "source_ward_type": source_ward.ward_type,
            "source_current_occupancy": s_curr_occ,
            "source_predicted_occupancy": s_pred_occ,
            "required_bed_type": required_bed_type,
            "evaluated_at": datetime.utcnow(),
            "total_destination_wards_evaluated": len(candidate_wards),
            "eligible_destinations_count": len(eligible_candidates),
            "recommendations": all_recommendations,
            "verification_required_statement": "Staff must physically verify bed readiness and clinically approve the transfer. Decision support only.",
        }

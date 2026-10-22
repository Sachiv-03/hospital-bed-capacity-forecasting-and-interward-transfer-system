import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.capacity_alert import CapacityAlert, AlertType, AlertSeverity, AlertStatus
from app.models.hospital import Hospital
from app.models.ward import Ward

logger = logging.getLogger(__name__)


class AlertService:

    @staticmethod
    def evaluate_ward_alerts(
        db: Session,
        hospital_id: int,
        ward_id: int,
        ward_name: str,
        occupied_beds: int,
        total_beds: int,
        available_beds: int,
        occupancy_percentage: float,
    ) -> List[CapacityAlert]:
        """
        Evaluates rule-based alerts for a single ward.
        Enforces deduplication: if an active alert for the type exists, it is updated rather than duplicated.
        Resolves active alerts when metrics fall back below thresholds.
        """
        created_or_updated = []

        # ── 1. Critical Occupancy Check (>= 95%) ──────────────────────────────
        critical_active = db.query(CapacityAlert).filter(
            CapacityAlert.ward_id == ward_id,
            CapacityAlert.alert_type == AlertType.CRITICAL_OCCUPANCY.value,
            CapacityAlert.status == AlertStatus.ACTIVE.value,
        ).first()

        if occupancy_percentage >= settings.ALERT_CRITICAL_THRESHOLD:
            msg = (
                f"Critical occupancy level of {occupancy_percentage:.1f}% reached in {ward_name}. "
                f"{occupied_beds}/{total_beds} beds occupied."
            )
            if not critical_active:
                alert = CapacityAlert(
                    hospital_id=hospital_id,
                    ward_id=ward_id,
                    alert_type=AlertType.CRITICAL_OCCUPANCY.value,
                    severity=AlertSeverity.CRITICAL.value,
                    message=msg,
                    trigger_value=occupancy_percentage,
                    threshold_value=settings.ALERT_CRITICAL_THRESHOLD,
                    status=AlertStatus.ACTIVE.value,
                )
                db.add(alert)
                created_or_updated.append(alert)
                logger.warning(f"ALERT CREATED | {ward_name} CRITICAL_OCCUPANCY ({occupancy_percentage:.1f}%)")
            else:
                critical_active.trigger_value = occupancy_percentage
                critical_active.message = msg
                created_or_updated.append(critical_active)
        else:
            if critical_active:
                critical_active.status = AlertStatus.RESOLVED.value
                critical_active.resolved_at = datetime.utcnow()
                logger.info(f"ALERT RESOLVED | {ward_name} CRITICAL_OCCUPANCY resolved")

        # ── 2. High Occupancy Check (85% <= occupancy < 95%) ──────────────────
        high_active = db.query(CapacityAlert).filter(
            CapacityAlert.ward_id == ward_id,
            CapacityAlert.alert_type == AlertType.HIGH_OCCUPANCY.value,
            CapacityAlert.status == AlertStatus.ACTIVE.value,
        ).first()

        if settings.ALERT_HIGH_THRESHOLD <= occupancy_percentage < settings.ALERT_CRITICAL_THRESHOLD:
            msg = (
                f"High occupancy warning of {occupancy_percentage:.1f}% in {ward_name}. "
                f"{occupied_beds}/{total_beds} beds occupied."
            )
            if not high_active:
                alert = CapacityAlert(
                    hospital_id=hospital_id,
                    ward_id=ward_id,
                    alert_type=AlertType.HIGH_OCCUPANCY.value,
                    severity=AlertSeverity.WARNING.value,
                    message=msg,
                    trigger_value=occupancy_percentage,
                    threshold_value=settings.ALERT_HIGH_THRESHOLD,
                    status=AlertStatus.ACTIVE.value,
                )
                db.add(alert)
                created_or_updated.append(alert)
                logger.warning(f"ALERT CREATED | {ward_name} HIGH_OCCUPANCY ({occupancy_percentage:.1f}%)")
            else:
                high_active.trigger_value = occupancy_percentage
                high_active.message = msg
                created_or_updated.append(high_active)
        else:
            if high_active:
                high_active.status = AlertStatus.RESOLVED.value
                high_active.resolved_at = datetime.utcnow()
                logger.info(f"ALERT RESOLVED | {ward_name} HIGH_OCCUPANCY resolved")

        # ── 3. Low Availability Check (available_beds <= 2) ──────────────────
        low_avail_active = db.query(CapacityAlert).filter(
            CapacityAlert.ward_id == ward_id,
            CapacityAlert.alert_type == AlertType.LOW_AVAILABILITY.value,
            CapacityAlert.status == AlertStatus.ACTIVE.value,
        ).first()

        low_threshold = getattr(settings, "ALERT_LOW_AVAILABILITY_THRESHOLD", 2)
        if available_beds <= low_threshold and total_beds > 0:
            msg = (
                f"Low bed availability in {ward_name}: only {available_beds} bed(s) available."
            )
            if not low_avail_active:
                alert = CapacityAlert(
                    hospital_id=hospital_id,
                    ward_id=ward_id,
                    alert_type=AlertType.LOW_AVAILABILITY.value,
                    severity=AlertSeverity.WARNING.value,
                    message=msg,
                    trigger_value=float(available_beds),
                    threshold_value=float(low_threshold),
                    status=AlertStatus.ACTIVE.value,
                )
                db.add(alert)
                created_or_updated.append(alert)
                logger.warning(f"ALERT CREATED | {ward_name} LOW_AVAILABILITY ({available_beds} left)")
            else:
                low_avail_active.trigger_value = float(available_beds)
                low_avail_active.message = msg
                created_or_updated.append(low_avail_active)
        else:
            if low_avail_active:
                low_avail_active.status = AlertStatus.RESOLVED.value
                low_avail_active.resolved_at = datetime.utcnow()
                logger.info(f"ALERT RESOLVED | {ward_name} LOW_AVAILABILITY resolved")

        db.commit()
        return created_or_updated

    @staticmethod
    def _format_alert_dict(a: CapacityAlert) -> Dict[str, Any]:
        import json
        explanation_data = None
        if getattr(a, "explanation_json", None):
            try:
                explanation_data = json.loads(a.explanation_json)
            except Exception:
                explanation_data = None

        return {
            "id": a.id,
            "hospital_id": a.hospital_id,
            "ward_id": a.ward_id,
            "ward_name": a.ward.name if a.ward else "",
            "hospital_name": a.hospital.name if a.hospital else "",
            "alert_type": a.alert_type,
            "severity": a.severity,
            "message": a.message,
            "trigger_value": a.trigger_value,
            "threshold_value": a.threshold_value,
            "status": a.status,
            "created_at": a.created_at,
            "resolved_at": a.resolved_at,
            "acknowledged_at": getattr(a, "acknowledged_at", None),
            "acknowledged_by_id": getattr(a, "acknowledged_by_id", None),
            "acknowledged_by_name": a.acknowledged_by.full_name if getattr(a, "acknowledged_by", None) else None,
            "explanation": explanation_data,
        }

    @staticmethod
    def get_alerts(
        db: Session,
        hospital_id: Optional[int] = None,
        ward_id: Optional[int] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = db.query(CapacityAlert)

        if hospital_id is not None:
            query = query.filter(CapacityAlert.hospital_id == hospital_id)
        if ward_id is not None:
            query = query.filter(CapacityAlert.ward_id == ward_id)
        if status:
            query = query.filter(CapacityAlert.status == status.upper())
        if severity:
            query = query.filter(CapacityAlert.severity == severity.upper())
        if alert_type:
            query = query.filter(CapacityAlert.alert_type == alert_type.upper())

        alerts = query.order_by(CapacityAlert.created_at.desc()).all()
        return [AlertService._format_alert_dict(a) for a in alerts]

    @staticmethod
    def get_alert_summary(db: Session, hospital_id: Optional[int] = None) -> Dict[str, int]:
        """
        Returns aggregated counts and summary metrics for capacity alerts.
        """
        query = db.query(CapacityAlert)
        if hospital_id is not None:
            query = query.filter(CapacityAlert.hospital_id == hospital_id)

        all_alerts = query.all()

        active_alerts = [a for a in all_alerts if a.status in [AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value]]
        unacknowledged = [a for a in all_alerts if a.status == AlertStatus.ACTIVE.value]
        critical_alerts = [a for a in active_alerts if a.severity == AlertSeverity.CRITICAL.value]
        high_alerts = [a for a in active_alerts if a.severity in [AlertSeverity.HIGH.value, AlertSeverity.WARNING.value]]
        moderate_alerts = [a for a in active_alerts if a.severity == AlertSeverity.INFO.value]
        data_quality_alerts = [
            a for a in active_alerts
            if a.alert_type in [AlertType.INSUFFICIENT_DATA.value, AlertType.HIGH_UNCERTAINTY.value]
        ]
        resolved_alerts = [a for a in all_alerts if a.status == AlertStatus.RESOLVED.value]

        return {
            "total_active": len(active_alerts),
            "critical_count": len(critical_alerts),
            "high_count": len(high_alerts),
            "moderate_count": len(moderate_alerts),
            "unacknowledged_count": len(unacknowledged),
            "data_quality_count": len(data_quality_alerts),
            "resolved_count": len(resolved_alerts),
        }

    @staticmethod
    def get_alert_by_id(
        db: Session,
        alert_id: int,
        hospital_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        query = db.query(CapacityAlert).filter(CapacityAlert.id == alert_id)
        if hospital_id is not None:
            query = query.filter(CapacityAlert.hospital_id == hospital_id)

        alert = query.first()
        if not alert:
            return None
        return AlertService._format_alert_dict(alert)

    @staticmethod
    def acknowledge_alert(
        db: Session,
        alert_id: int,
        user_id: int,
        hospital_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        query = db.query(CapacityAlert).filter(CapacityAlert.id == alert_id)
        if hospital_id is not None:
            query = query.filter(CapacityAlert.hospital_id == hospital_id)

        alert = query.first()
        if not alert:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by_id = user_id
        db.commit()
        db.refresh(alert)
        return AlertService._format_alert_dict(alert)

    @staticmethod
    def resolve_alert(db: Session, alert_id: int, hospital_id: Optional[int] = None) -> Optional[CapacityAlert]:
        query = db.query(CapacityAlert).filter(CapacityAlert.id == alert_id)
        if hospital_id is not None:
            query = query.filter(CapacityAlert.hospital_id == hospital_id)

        alert = query.first()
        if not alert:
            return None

        alert.status = AlertStatus.RESOLVED.value
        alert.resolved_at = datetime.utcnow()
        db.commit()
        db.refresh(alert)
        return alert

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bed import Bed, BedStatus
from app.models.capacity_alert import AlertSeverity, AlertStatus, AlertType, CapacityAlert
from app.models.hospital import Hospital
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.ward import Ward
from app.services.forecasting.forecast_service import ForecastService

logger = logging.getLogger(__name__)


class ExplainableAlertService:
    """
    Deterministic Explainable Decision-Support Engine for Hospital Bed Capacity Forecasting.

    Evaluates actual historical occupancy, physical capacity, live bed counts, and existing
    SARIMA time-series forecasts to produce explainable alerts with structured evidence,
    traceable triggered rules, and practical non-clinical administrative suggestions.

    Rules Evaluated:
    - RULE_A_HIGH_FORECAST: Predicted occupancy >= ALERT_HIGH_THRESHOLD (default 85%).
    - RULE_B_CRITICAL_FORECAST: Predicted occupancy >= ALERT_CRITICAL_THRESHOLD (default 95%).
    - RULE_C_LOW_AVAILABILITY: Estimated available beds <= ALERT_LOW_AVAILABILITY_THRESHOLD (default 2).
    - RULE_D_RAPID_INCREASE: Observed historical occupancy increased by >= ALERT_RAPID_INCREASE_THRESHOLD (default 15%).
    - RULE_E_CAPACITY_EXCEEDANCE: Predicted occupied beds exceed physical ward capacity.
    - RULE_F_HIGH_UNCERTAINTY: Prediction interval width >= ALERT_UNCERTAINTY_THRESHOLD (default 25%).
    - RULE_G_INSUFFICIENT_DATA: Insufficient history (< 7 days), invalid/zero capacity, or model failure.
    """

    @classmethod
    def evaluate_ward_capacity_risk(
        cls,
        db: Session,
        ward_id: int,
        hospital_id: Optional[int] = None,
        horizon: int = 7,
        persist: bool = True,
    ) -> dict[str, Any]:
        """
        Evaluates explainable risk signals for a single ward using actual data.
        Returns a complete structured explanation payload and optionally persists/updates alerts.
        """
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise ValueError(f"Ward with ID {ward_id} not found")

        # Multi-hospital tenant isolation check
        if hospital_id is not None and ward.hospital_id != hospital_id:
            raise PermissionError(f"Access forbidden to ward {ward_id} for hospital {hospital_id}")

        hospital = db.query(Hospital).filter(Hospital.id == ward.hospital_id).first()
        hospital_name = hospital.name if hospital else f"Hospital #{ward.hospital_id}"

        now = datetime.now(timezone.utc)
        triggered_rules: list[dict[str, Any]] = []
        data_quality_notes: list[str] = []

        # ── 1. Capacity Validation ───────────────────────────────────────────
        capacity = ward.capacity
        if capacity is None or capacity <= 0:
            data_quality_notes.append("Invalid or non-positive physical capacity configured for ward.")
            rule_g = {
                "rule_id": "RULE_G_INSUFFICIENT_DATA",
                "rule_name": "Invalid Ward Capacity",
                "severity": "CRITICAL",
                "condition_met": f"Ward physical capacity is {capacity} (must be > 0)",
                "trigger_value": float(capacity or 0),
                "threshold_value": 1.0,
                "description": "Physical bed capacity is missing or zero, preventing valid occupancy calculation.",
            }
            triggered_rules.append(rule_g)

            evidence = {
                "hospital_id": ward.hospital_id,
                "hospital_name": hospital_name,
                "ward_id": ward.id,
                "ward_name": ward.name,
                "ward_type": ward.ward_type,
                "ward_capacity": capacity or 0,
                "current_occupied_beds": 0,
                "current_available_beds": 0,
                "current_occupancy_percentage": 0.0,
                "forecast_target_date": None,
                "forecast_horizon_days": horizon,
                "predicted_occupied_beds": None,
                "predicted_occupancy_percentage": None,
                "predicted_available_beds": None,
                "lower_bound_percentage": None,
                "upper_bound_percentage": None,
                "uncertainty_interval_width": None,
                "historical_trend_percentage_change": None,
                "historical_trend_days": None,
                "time_to_threshold_days": None,
                "time_to_threshold_date": None,
                "is_capacity_exceeded": False,
                "data_quality_notes": data_quality_notes,
                "model_used": "NONE",
                "evaluated_at": now.isoformat(),
            }

            explanation_payload = {
                "headline": f"Data Quality Alert: Invalid capacity in {ward.name}",
                "human_readable_explanation": (
                    f"Ward '{ward.name}' has an unconfigured or non-positive bed capacity ({capacity}). "
                    f"The system cannot calculate valid occupancy rates or future risk."
                ),
                "suggested_actions": [
                    "Verify and update ward capacity in the hospital ward administration settings.",
                    "Audit physical bed inventory for this ward before using automated capacity alerts.",
                ],
                "triggered_rules": triggered_rules,
                "evidence": evidence,
            }

            if persist:
                cls._persist_alert(
                    db=db,
                    hospital_id=ward.hospital_id,
                    ward_id=ward.id,
                    alert_type=AlertType.INSUFFICIENT_DATA.value,
                    severity=AlertSeverity.CRITICAL.value,
                    message=explanation_payload["human_readable_explanation"],
                    trigger_value=0.0,
                    threshold_value=1.0,
                    explanation_payload=explanation_payload,
                )

            return {
                "ward_id": ward.id,
                "ward_name": ward.name,
                "hospital_id": ward.hospital_id,
                "risk_level": "INSUFFICIENT_DATA",
                "severity": "CRITICAL",
                "explanation": explanation_payload,
            }

        # ── 2. Live Occupancy State ──────────────────────────────────────────
        live_beds = db.query(Bed).filter(Bed.ward_id == ward.id).all()
        current_occupied = sum(1 for b in live_beds if b.status == BedStatus.OCCUPIED.value)
        current_available = sum(1 for b in live_beds if b.status == BedStatus.AVAILABLE.value) if live_beds else (capacity - current_occupied)
        current_occupancy_pct = round((current_occupied / capacity) * 100.0, 2)

        # ── 2b. Current Capacity Exceedance Check ────────────────────────────
        is_capacity_exceeded = False
        if 0 < capacity < current_occupied:
            is_capacity_exceeded = True
            triggered_rules.append({
                "rule_id": "RULE_E_CAPACITY_EXCEEDANCE",
                "rule_name": "Current Capacity Exceedance",
                "severity": AlertSeverity.CRITICAL.value,
                "condition_met": (
                    f"Current occupied beds ({current_occupied}) exceed physical capacity ({capacity})"
                ),
                "trigger_value": float(current_occupied),
                "threshold_value": float(capacity),
                "description": "Active occupied bed count exceeds recorded operational ward capacity, indicating potential bed-state discrepancies or severe overcrowding.",
            })
            data_quality_notes.append(
                f"Live occupied beds ({current_occupied}) exceed physical ward capacity ({capacity})."
            )

        # ── 3. Historical Trend Evaluation ───────────────────────────────────
        trend_days = settings.ALERT_RAPID_INCREASE_DAYS
        trend_change_pct: Optional[float] = None

        snapshots = (
            db.query(OccupancySnapshot)
            .filter(
                OccupancySnapshot.hospital_id == ward.hospital_id,
                OccupancySnapshot.ward_id == ward.id,
            )
            .order_by(OccupancySnapshot.snapshot_time.desc())
            .limit(trend_days * 24)
            .all()
        )

        if len(snapshots) >= 2:
            latest_snap_pct = float(snapshots[0].occupancy_percentage)
            oldest_snap_pct = float(snapshots[-1].occupancy_percentage)
            trend_change_pct = round(latest_snap_pct - oldest_snap_pct, 2)

            if trend_change_pct >= settings.ALERT_RAPID_INCREASE_THRESHOLD:
                triggered_rules.append({
                    "rule_id": "RULE_D_RAPID_INCREASE",
                    "rule_name": "Rapid Historical Occupancy Growth",
                    "severity": AlertSeverity.WARNING.value,
                    "condition_met": (
                        f"Observed occupancy grew by {trend_change_pct:+.1f}% points over recent window "
                        f"(threshold: >= +{settings.ALERT_RAPID_INCREASE_THRESHOLD:.1f}%)"
                    ),
                    "trigger_value": trend_change_pct,
                    "threshold_value": settings.ALERT_RAPID_INCREASE_THRESHOLD,
                    "description": "Ward occupancy velocity indicates rapid admission inflow or slowing discharges.",
                })

        # ── 4. Forecast Retrieval & Analysis ─────────────────────────────────
        forecast_result = ForecastService.get_ward_latest_forecast(
            db=db,
            ward_id=ward.id,
            hospital_id=ward.hospital_id,
            horizon=horizon,
        )

        forecast_status = forecast_result.get("status", "SUCCESS")
        model_name = forecast_result.get("model", "SARIMA")
        forecast_items = forecast_result.get("forecasts", [])

        predicted_occupied: Optional[float] = None
        predicted_occupancy_pct: Optional[float] = None
        predicted_available: Optional[float] = None
        target_date_str: Optional[str] = None
        lower_bound_pct: Optional[float] = None
        upper_bound_pct: Optional[float] = None
        uncertainty_width: Optional[float] = None
        time_to_threshold_days: Optional[int] = None
        time_to_threshold_date: Optional[str] = None

        if forecast_status == "INSUFFICIENT_DATA":
            avail_obs = forecast_result.get("available_observations", 0)
            req_obs = forecast_result.get("required_observations", settings.FORECAST_MIN_OBSERVATIONS)
            data_quality_notes.append(
                f"Insufficient historical observations: {avail_obs} available, {req_obs} required. "
                "Time-series forecast cannot be generated with statistical confidence."
            )
            triggered_rules.append({
                "rule_id": "RULE_G_INSUFFICIENT_DATA",
                "rule_name": "Insufficient Historical Observations",
                "severity": AlertSeverity.INFO.value,
                "condition_met": f"Available daily observations: {avail_obs}/{req_obs}",
                "trigger_value": float(avail_obs),
                "threshold_value": float(req_obs),
                "description": "Insufficient history to reliably fit SARIMA time-series model.",
            })

        elif forecast_items:
            # Analyze peak future pressure across the horizon
            peak_item = max(forecast_items, key=lambda x: x["predicted_occupancy_percentage"])
            predicted_occupied = float(peak_item.get("predicted_occupied_beds", peak_item.get("predicted_occupancy", 0.0)))
            predicted_occupancy_pct = float(peak_item.get("predicted_occupancy_percentage", 0.0))
            predicted_available = round(max(0.0, capacity - predicted_occupied), 1)
            target_date_str = peak_item.get("date")

            lower_bound_pct = float(peak_item.get("lower_bound", predicted_occupancy_pct))
            upper_bound_pct = float(peak_item.get("upper_bound", predicted_occupancy_pct))
            uncertainty_width = round(max(0.0, upper_bound_pct - lower_bound_pct), 2)

            # Check capacity exceedance
            if predicted_occupied > capacity:
                is_capacity_exceeded = True
                if not any(r["rule_id"] == "RULE_E_CAPACITY_EXCEEDANCE" for r in triggered_rules):
                    triggered_rules.append({
                        "rule_id": "RULE_E_CAPACITY_EXCEEDANCE",
                        "rule_name": "Physical Capacity Exceedance",
                        "severity": AlertSeverity.CRITICAL.value,
                        "condition_met": (
                            f"Forecasted beds ({predicted_occupied:.1f}) exceed physical capacity ({capacity})"
                        ),
                        "trigger_value": round(predicted_occupied, 1),
                        "threshold_value": float(capacity),
                        "description": "SARIMA model projects bed demand surpassing total operational beds.",
                    })

            # Check critical forecasted occupancy
            if predicted_occupancy_pct >= settings.ALERT_CRITICAL_THRESHOLD:
                triggered_rules.append({
                    "rule_id": "RULE_B_CRITICAL_FORECAST",
                    "rule_name": "Critical Forecasted Occupancy",
                    "severity": AlertSeverity.CRITICAL.value,
                    "condition_met": (
                        f"Predicted peak occupancy of {predicted_occupancy_pct:.1f}% meets critical threshold "
                        f"(threshold: >= {settings.ALERT_CRITICAL_THRESHOLD:.1f}%)"
                    ),
                    "trigger_value": predicted_occupancy_pct,
                    "threshold_value": settings.ALERT_CRITICAL_THRESHOLD,
                    "description": "Ward is projected to enter critical capacity deficit.",
                })
            # Check high forecasted occupancy
            elif predicted_occupancy_pct >= settings.ALERT_HIGH_THRESHOLD:
                triggered_rules.append({
                    "rule_id": "RULE_A_HIGH_FORECAST",
                    "rule_name": "High Forecasted Occupancy",
                    "severity": AlertSeverity.WARNING.value,
                    "condition_met": (
                        f"Predicted peak occupancy of {predicted_occupancy_pct:.1f}% exceeds warning threshold "
                        f"(threshold: >= {settings.ALERT_HIGH_THRESHOLD:.1f}%)"
                    ),
                    "trigger_value": predicted_occupancy_pct,
                    "threshold_value": settings.ALERT_HIGH_THRESHOLD,
                    "description": "Ward is projected to experience severe bed pressure requiring administrative review.",
                })

            # Check forecast uncertainty
            if uncertainty_width >= settings.ALERT_UNCERTAINTY_THRESHOLD:
                triggered_rules.append({
                    "rule_id": "RULE_F_HIGH_UNCERTAINTY",
                    "rule_name": "High Forecast Uncertainty",
                    "severity": AlertSeverity.INFO.value,
                    "condition_met": (
                        f"95% prediction interval span is {uncertainty_width:.1f}% "
                        f"(threshold: >= {settings.ALERT_UNCERTAINTY_THRESHOLD:.1f}%)"
                    ),
                    "trigger_value": uncertainty_width,
                    "threshold_value": settings.ALERT_UNCERTAINTY_THRESHOLD,
                    "description": "Wide prediction interval reflects high variance; forecast should be treated cautiously.",
                })

            # Chronological scan to find time until threshold is reached
            for idx, item in enumerate(forecast_items):
                if item["predicted_occupancy_percentage"] >= settings.ALERT_HIGH_THRESHOLD:
                    time_to_threshold_days = idx + 1
                    time_to_threshold_date = item["date"]
                    break

            # Check forecast staleness (> 48 hours)
            gen_at = forecast_result.get("generated_at")
            if gen_at:
                try:
                    dt_gen = datetime.fromisoformat(gen_at) if isinstance(gen_at, str) else gen_at
                    if dt_gen.tzinfo is None:
                        dt_gen = dt_gen.replace(tzinfo=timezone.utc)
                    age_hours = (now - dt_gen).total_seconds() / 3600.0
                    if age_hours > 48.0:
                        data_quality_notes.append(f"Forecast projection is {age_hours:.1f} hours old (> 48h staleness threshold).")
                        if not any(r["rule_id"] == "RULE_G_INSUFFICIENT_DATA" for r in triggered_rules):
                            triggered_rules.append({
                                "rule_id": "RULE_G_INSUFFICIENT_DATA",
                                "rule_name": "Stale Forecast Projection",
                                "severity": AlertSeverity.INFO.value,
                                "condition_met": f"Forecast timestamp is {age_hours:.1f} hours old (threshold: > 48.0h)",
                                "trigger_value": round(age_hours, 1),
                                "threshold_value": 48.0,
                                "description": "Forecast has not been refreshed within 48 hours; on-demand model re-run recommended.",
                            })
                except ValueError:
                    logger.debug("Could not parse forecast generated_at timestamp; skipping staleness check.")

        elif not forecast_items and forecast_status != "INSUFFICIENT_DATA":
            data_quality_notes.append("No forward forecast projections available for this ward horizon.")
            if not any(r["rule_id"] == "RULE_G_INSUFFICIENT_DATA" for r in triggered_rules):
                triggered_rules.append({
                    "rule_id": "RULE_G_INSUFFICIENT_DATA",
                    "rule_name": "Missing Forecast Projection",
                    "severity": AlertSeverity.INFO.value,
                    "condition_met": "Forward forecast projection is unavailable",
                    "trigger_value": 0.0,
                    "threshold_value": 1.0,
                    "description": "Forward capacity forecast is unavailable; relying on real-time bed occupancy records.",
                })

        # ── 4b. Current Occupancy Threshold Check (if not already triggered by forecast) ──
        if current_occupancy_pct >= settings.ALERT_CRITICAL_THRESHOLD and not any(r["rule_id"] == "RULE_B_CRITICAL_FORECAST" for r in triggered_rules):
            triggered_rules.append({
                "rule_id": "RULE_B_CRITICAL_FORECAST",
                "rule_name": "Critical Occupancy Level",
                "severity": AlertSeverity.CRITICAL.value,
                "condition_met": (
                    f"Current observed occupancy of {current_occupancy_pct:.1f}% meets critical threshold "
                    f"(threshold: >= {settings.ALERT_CRITICAL_THRESHOLD:.1f}%)"
                ),
                "trigger_value": current_occupancy_pct,
                "threshold_value": settings.ALERT_CRITICAL_THRESHOLD,
                "description": "Ward is currently operating at or above critical capacity limit.",
            })
        elif current_occupancy_pct >= settings.ALERT_HIGH_THRESHOLD and not any(r["rule_id"] in ["RULE_A_HIGH_FORECAST", "RULE_B_CRITICAL_FORECAST"] for r in triggered_rules):
            triggered_rules.append({
                "rule_id": "RULE_A_HIGH_FORECAST",
                "rule_name": "High Occupancy Warning",
                "severity": AlertSeverity.WARNING.value,
                "condition_met": (
                    f"Current observed occupancy of {current_occupancy_pct:.1f}% meets high-risk warning threshold "
                    f"(threshold: >= {settings.ALERT_HIGH_THRESHOLD:.1f}%)"
                ),
                "trigger_value": current_occupancy_pct,
                "threshold_value": settings.ALERT_HIGH_THRESHOLD,
                "description": "Ward is currently experiencing high bed pressure requiring administrative review.",
            })

        # ── 5. Current & Forecasted Availability Check ───────────────────────
        low_threshold = getattr(settings, "ALERT_LOW_AVAILABILITY_THRESHOLD", 2)
        if current_available <= low_threshold and capacity > 0:
            triggered_rules.append({
                "rule_id": "RULE_C_LOW_AVAILABILITY",
                "rule_name": "Low Bed Availability",
                "severity": AlertSeverity.WARNING.value,
                "condition_met": f"Current available beds: {current_available} (threshold: <= {low_threshold})",
                "trigger_value": float(current_available),
                "threshold_value": float(low_threshold),
                "description": "Current free bed count is at or below operational reserve safety threshold.",
            })
        elif predicted_available is not None and predicted_available <= low_threshold and capacity > 0:
            triggered_rules.append({
                "rule_id": "RULE_C_LOW_AVAILABILITY",
                "rule_name": "Forecast Low Bed Availability",
                "severity": AlertSeverity.WARNING.value,
                "condition_met": f"Forecasted available beds: {predicted_available:.0f} (threshold: <= {low_threshold})",
                "trigger_value": float(predicted_available),
                "threshold_value": float(low_threshold),
                "description": "Projected free bed count falls to or below operational reserve safety threshold.",
            })

        # ── 6. Severity & Risk Level Assignment ──────────────────────────────
        rule_ids = {r["rule_id"] for r in triggered_rules}
        if "RULE_G_INSUFFICIENT_DATA" in rule_ids and not any(
            r in rule_ids for r in ["RULE_B_CRITICAL_FORECAST", "RULE_A_HIGH_FORECAST", "RULE_E_CAPACITY_EXCEEDANCE"]
        ):
            risk_level = "INSUFFICIENT_DATA"
            severity = AlertSeverity.INFO.value
        elif "RULE_E_CAPACITY_EXCEEDANCE" in rule_ids or "RULE_B_CRITICAL_FORECAST" in rule_ids:
            risk_level = "CRITICAL"
            severity = AlertSeverity.CRITICAL.value
        elif "RULE_A_HIGH_FORECAST" in rule_ids:
            risk_level = "HIGH"
            severity = AlertSeverity.WARNING.value
        elif "RULE_C_LOW_AVAILABILITY" in rule_ids or "RULE_D_RAPID_INCREASE" in rule_ids:
            risk_level = "MODERATE"
            severity = AlertSeverity.WARNING.value
        elif "RULE_F_HIGH_UNCERTAINTY" in rule_ids:
            risk_level = "MODERATE"
            severity = AlertSeverity.INFO.value
        else:
            risk_level = "LOW"
            severity = AlertSeverity.INFO.value

        # ── 7. Evidence Payload ──────────────────────────────────────────────
        evidence = {
            "hospital_id": ward.hospital_id,
            "hospital_name": hospital_name,
            "ward_id": ward.id,
            "ward_name": ward.name,
            "ward_type": ward.ward_type,
            "ward_capacity": capacity,
            "current_occupied_beds": current_occupied,
            "current_available_beds": current_available,
            "current_occupancy_percentage": current_occupancy_pct,
            "forecast_target_date": target_date_str,
            "forecast_horizon_days": horizon,
            "predicted_occupied_beds": predicted_occupied,
            "predicted_occupancy_percentage": predicted_occupancy_pct,
            "predicted_available_beds": predicted_available,
            "lower_bound_percentage": lower_bound_pct,
            "upper_bound_percentage": upper_bound_pct,
            "uncertainty_interval_width": uncertainty_width,
            "historical_trend_percentage_change": trend_change_pct,
            "historical_trend_days": trend_days,
            "time_to_threshold_days": time_to_threshold_days,
            "time_to_threshold_date": time_to_threshold_date,
            "is_capacity_exceeded": is_capacity_exceeded,
            "data_quality_notes": data_quality_notes,
            "model_used": model_name,
            "evaluated_at": now,
        }

        # ── 8. Dynamic Human-Readable Explanation ────────────────────────────
        explanation_text = cls._generate_human_readable_explanation(
            ward_name=ward.name,
            capacity=capacity,
            current_occupied=current_occupied,
            current_pct=current_occupancy_pct,
            predicted_occupied=predicted_occupied,
            predicted_pct=predicted_occupancy_pct,
            predicted_avail=predicted_available,
            target_date=target_date_str,
            triggered_rules=triggered_rules,
            uncertainty_width=uncertainty_width,
            lower_bound_pct=lower_bound_pct,
            upper_bound_pct=upper_bound_pct,
            trend_change_pct=trend_change_pct,
            trend_days=trend_days,
            time_to_threshold_days=time_to_threshold_days,
            time_to_threshold_date=time_to_threshold_date,
            data_quality_notes=data_quality_notes,
        )

        suggested_actions = cls._generate_suggested_actions(
            triggered_rules=triggered_rules,
            ward_name=ward.name,
            target_date=target_date_str,
            current_available=current_available,
            predicted_available=predicted_available,
        )

        headline = cls._generate_headline(ward.name, risk_level, triggered_rules)

        explanation_payload = {
            "headline": headline,
            "human_readable_explanation": explanation_text,
            "suggested_actions": suggested_actions,
            "triggered_rules": triggered_rules,
            "evidence": evidence,
        }

        # ── 9. Persistence & Deduplication ───────────────────────────────────
        alerts_saved = 0
        if persist:
            alerts_saved = cls._sync_alerts(
                db=db,
                hospital_id=ward.hospital_id,
                ward_id=ward.id,
                ward_name=ward.name,
                risk_level=risk_level,
                severity=severity,
                triggered_rules=triggered_rules,
                explanation_payload=explanation_payload,
                current_pct=current_occupancy_pct,
                predicted_pct=predicted_occupancy_pct,
            )

        return {
            "ward_id": ward.id,
            "ward_name": ward.name,
            "hospital_id": ward.hospital_id,
            "risk_level": risk_level,
            "severity": severity,
            "alerts_created_or_updated": alerts_saved,
            "rules_triggered": [r["rule_id"] for r in triggered_rules],
            "has_alert": len(triggered_rules) > 0,
            "explanation": explanation_payload,
        }

    @classmethod
    def _generate_headline(cls, ward_name: str, risk_level: str, triggered_rules: list[dict[str, Any]]) -> str:
        if not triggered_rules:
            return f"Normal Capacity: {ward_name} operating within safe thresholds"
        rule_ids = {r["rule_id"] for r in triggered_rules}
        if "RULE_E_CAPACITY_EXCEEDANCE" in rule_ids:
            return f"Critical Exceedance Risk: {ward_name} projected to exceed 100% capacity"
        if "RULE_B_CRITICAL_FORECAST" in rule_ids:
            return f"Critical Capacity Pressure: {ward_name} forecast reaches critical limit"
        if "RULE_A_HIGH_FORECAST" in rule_ids:
            return f"High Capacity Warning: {ward_name} forecast approaches high risk threshold"
        if "RULE_C_LOW_AVAILABILITY" in rule_ids:
            return f"Low Bed Availability Warning: {ward_name} has critically few free beds"
        if "RULE_D_RAPID_INCREASE" in rule_ids:
            return f"Rapid Occupancy Surge: {ward_name} admissions accelerating"
        if "RULE_G_INSUFFICIENT_DATA" in rule_ids:
            return f"Data Quality Notice: Insufficient observations for {ward_name}"
        return f"{risk_level} Capacity Alert for {ward_name}"

    @classmethod
    def _generate_human_readable_explanation(
        cls,
        ward_name: str,
        capacity: int,
        current_occupied: int,
        current_pct: float,
        predicted_occupied: float | None,
        predicted_pct: float | None,
        predicted_avail: float | None,
        target_date: str | None,
        triggered_rules: list[dict[str, Any]],
        uncertainty_width: float | None,
        lower_bound_pct: float | None,
        upper_bound_pct: float | None,
        trend_change_pct: float | None,
        trend_days: int,
        time_to_threshold_days: int | None,
        time_to_threshold_date: str | None,
        data_quality_notes: list[str],
    ) -> str:
        """
        Dynamically generates explainable prose strictly derived from observed metrics and forecasts.
        Never fabricates trends or claims causation.
        """
        parts = []

        # Current status
        parts.append(
            f"{ward_name} has a physical capacity of {capacity} beds and currently has "
            f"{current_occupied} occupied beds ({current_pct:.1f}% occupancy)."
        )

        # Forecast findings
        if predicted_occupied is not None and predicted_pct is not None and target_date:
            avail_str = f"approximately {predicted_avail:.0f} available bed(s)" if predicted_avail is not None else "minimal availability"
            parts.append(
                f"The existing SARIMA time-series forecast projects {predicted_occupied:.1f} occupied beds "
                f"on {target_date}, corresponding to {predicted_pct:.1f}% occupancy with {avail_str} remaining."
            )

            if lower_bound_pct is not None and upper_bound_pct is not None:
                parts.append(
                    f"The 95% forecast prediction interval spans {lower_bound_pct:.1f}% to {upper_bound_pct:.1f}% "
                    f"(uncertainty span: {uncertainty_width:.1f}%)."
                )

        # Time until threshold
        if time_to_threshold_days and time_to_threshold_date:
            parts.append(
                f"The capacity threshold is projected to be crossed in {time_to_threshold_days} day(s) "
                f"(projected threshold date: {time_to_threshold_date})."
            )

        # Trend findings
        if trend_change_pct is not None:
            direction = "increased" if trend_change_pct > 0 else "decreased"
            parts.append(
                f"Over the last {trend_days} days of valid observations, occupancy has {direction} "
                f"by {abs(trend_change_pct):.1f}% points."
            )

        # Rules context
        if triggered_rules:
            rule_summaries = [f"{r['rule_name']} ({r['condition_met']})" for r in triggered_rules]
            parts.append(f"Triggered risk rules: {'; '.join(rule_summaries)}.")
        else:
            parts.append("All observed and forecasted metrics are within safe operational limits.")

        # Limitations / Safeguards
        if data_quality_notes:
            parts.append(f"Data-quality considerations: {' '.join(data_quality_notes)}")

        parts.append(
            "Note: This alert provides deterministic operational decision support based on statistical forecasting; "
            "it does not prove causation and should be verified with ward staff."
        )

        return " ".join(parts)

    @classmethod
    def _generate_suggested_actions(
        cls,
        triggered_rules: list[dict[str, Any]],
        ward_name: str,
        target_date: str | None,
        current_available: int,
        predicted_available: float | None,
    ) -> list[str]:
        """
        Generates practical, non-clinical administrative suggestions appropriate to the triggered rules.
        """
        rule_ids = {r["rule_id"] for r in triggered_rules}
        actions: list[str] = []

        if "RULE_E_CAPACITY_EXCEEDANCE" in rule_ids:
            actions.append(f"Notify hospital bed command and authorized administrator of possible overcapacity in {ward_name}.")
            actions.append("Review hospital-level contingency bed opening and surge capacity protocols.")
            actions.append("Evaluate suitable alternative destination wards with available operational capacity.")

        if "RULE_B_CRITICAL_FORECAST" in rule_ids or "RULE_A_HIGH_FORECAST" in rule_ids:
            date_clause = f" for {target_date}" if target_date else ""
            actions.append(f"Review scheduled admissions and planned discharges{date_clause}.")
            actions.append(f"Verify ward nursing and support staffing levels for {ward_name}{date_clause}.")
            actions.append("Audit pending discharge clearances with clinical care teams.")

        if "RULE_C_LOW_AVAILABILITY" in rule_ids:
            actions.append(f"Confirm actual physical bed availability directly with {ward_name} charge nurse ({current_available} beds currently indicated).")
            actions.append("Expedite room cleaning and turnover for recently vacated beds.")

        if "RULE_D_RAPID_INCREASE" in rule_ids:
            actions.append("Investigate emergency department intake volume and acute admission flow into this ward.")
            actions.append("Check whether incoming patient transfers from other wards can be re-routed.")

        if "RULE_F_HIGH_UNCERTAINTY" in rule_ids:
            actions.append("Treat the prediction cautiously due to high historical variance.")
            actions.append("Verify recent occupancy data before committing major administrative resource adjustments.")

        if "RULE_G_INSUFFICIENT_DATA" in rule_ids:
            actions.append("Inspect automated data ingestion logs and verify that daily occupancy snapshots are recording properly.")
            actions.append("Wait for at least 7 days of validated observations before relying on automated forecasts.")

        if not actions:
            actions.append("No immediate intervention needed; continue standard routine ward occupancy monitoring.")

        return actions

    @classmethod
    def _persist_alert(
        cls,
        db: Session,
        hospital_id: int,
        ward_id: int,
        alert_type: str,
        severity: str,
        message: str,
        trigger_value: float,
        threshold_value: float,
        explanation_payload: dict[str, Any],
    ) -> CapacityAlert:
        """
        Persists or updates an alert with strict deduplication.
        """
        existing = db.query(CapacityAlert).filter(
            CapacityAlert.hospital_id == hospital_id,
            CapacityAlert.ward_id == ward_id,
            CapacityAlert.alert_type == alert_type,
            CapacityAlert.status.in_([AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value]),
        ).first()

        expl_json = json.dumps(explanation_payload, default=str)

        if existing:
            existing.trigger_value = trigger_value
            existing.threshold_value = threshold_value
            existing.message = message
            existing.severity = severity
            existing.explanation_json = expl_json
            db.commit()
            return existing

        alert = CapacityAlert(
            hospital_id=hospital_id,
            ward_id=ward_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            trigger_value=trigger_value,
            threshold_value=threshold_value,
            status=AlertStatus.ACTIVE.value,
            explanation_json=expl_json,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    @classmethod
    def _sync_alerts(
        cls,
        db: Session,
        hospital_id: int,
        ward_id: int,
        ward_name: str,
        risk_level: str,
        severity: str,
        triggered_rules: list[dict[str, Any]],
        explanation_payload: dict[str, Any],
        current_pct: float,
        predicted_pct: float | None,
    ) -> int:
        """
        Synchronizes database alert state with current risk evaluation.
        Updates active alerts, creates new alerts, and resolves alerts whose conditions have cleared.
        """
        rule_ids = {r["rule_id"] for r in triggered_rules}
        alerts_saved = 0

        # Mapping rule to primary AlertType
        primary_alert_type = None
        trigger_val = current_pct
        threshold_val = settings.ALERT_HIGH_THRESHOLD

        if "RULE_E_CAPACITY_EXCEEDANCE" in rule_ids:
            primary_alert_type = AlertType.CAPACITY_EXCEEDANCE.value
            trigger_val = predicted_pct or current_pct
            threshold_val = 100.0
        elif "RULE_B_CRITICAL_FORECAST" in rule_ids:
            primary_alert_type = AlertType.FORECAST_CRITICAL_OCCUPANCY.value
            trigger_val = predicted_pct or current_pct
            threshold_val = settings.ALERT_CRITICAL_THRESHOLD
        elif "RULE_A_HIGH_FORECAST" in rule_ids:
            primary_alert_type = AlertType.FORECAST_HIGH_OCCUPANCY.value
            trigger_val = predicted_pct or current_pct
            threshold_val = settings.ALERT_HIGH_THRESHOLD
        elif "RULE_C_LOW_AVAILABILITY" in rule_ids:
            primary_alert_type = AlertType.LOW_AVAILABILITY.value
            low_r = next(r for r in triggered_rules if r["rule_id"] == "RULE_C_LOW_AVAILABILITY")
            trigger_val = low_r["trigger_value"]
            threshold_val = low_r["threshold_value"]
        elif "RULE_D_RAPID_INCREASE" in rule_ids:
            primary_alert_type = AlertType.RAPID_INCREASE.value
            rap_r = next(r for r in triggered_rules if r["rule_id"] == "RULE_D_RAPID_INCREASE")
            trigger_val = rap_r["trigger_value"]
            threshold_val = rap_r["threshold_value"]
        elif "RULE_F_HIGH_UNCERTAINTY" in rule_ids:
            primary_alert_type = AlertType.HIGH_UNCERTAINTY.value
            unc_r = next(r for r in triggered_rules if r["rule_id"] == "RULE_F_HIGH_UNCERTAINTY")
            trigger_val = unc_r["trigger_value"]
            threshold_val = unc_r["threshold_value"]
        elif "RULE_G_INSUFFICIENT_DATA" in rule_ids:
            primary_alert_type = AlertType.INSUFFICIENT_DATA.value
            trigger_val = 0.0
            threshold_val = float(settings.FORECAST_MIN_OBSERVATIONS)

        if primary_alert_type:
            cls._persist_alert(
                db=db,
                hospital_id=hospital_id,
                ward_id=ward_id,
                alert_type=primary_alert_type,
                severity=severity,
                message=explanation_payload["human_readable_explanation"],
                trigger_value=trigger_val,
                threshold_value=threshold_val,
                explanation_payload=explanation_payload,
            )
            alerts_saved += 1

            # Auto-resolve any previous active/acknowledged alerts of a different type for this ward
            other_active = db.query(CapacityAlert).filter(
                CapacityAlert.hospital_id == hospital_id,
                CapacityAlert.ward_id == ward_id,
                CapacityAlert.alert_type != primary_alert_type,
                CapacityAlert.status.in_([AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value]),
            ).all()
            for oa in other_active:
                oa.status = AlertStatus.RESOLVED.value
                oa.resolved_at = datetime.now(timezone.utc)
            if other_active:
                db.commit()
        else:
            # If no capacity risk rules triggered, auto-resolve any active/acknowledged capacity alerts for this ward
            active_alerts = db.query(CapacityAlert).filter(
                CapacityAlert.hospital_id == hospital_id,
                CapacityAlert.ward_id == ward_id,
                CapacityAlert.status.in_([AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value]),
            ).all()

            for a in active_alerts:
                a.status = AlertStatus.RESOLVED.value
                a.resolved_at = datetime.now(timezone.utc)
            if active_alerts:
                db.commit()

        return alerts_saved

    @classmethod
    def acknowledge_alert(
        cls,
        db: Session,
        alert_id: int,
        user_id: int,
        hospital_id: int | None = None,
    ) -> CapacityAlert | None:
        """
        Marks an active alert as ACKNOWLEDGED by an authorized user.
        """
        query = db.query(CapacityAlert).filter(CapacityAlert.id == alert_id)
        if hospital_id is not None:
            query = query.filter(CapacityAlert.hospital_id == hospital_id)

        alert = query.first()
        if not alert:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by_id = user_id
        db.commit()
        db.refresh(alert)
        return alert

    @classmethod
    def evaluate_all_hospital_wards(
        cls,
        db: Session,
        hospital_id: Optional[int] = None,
        horizon: int = 7,
    ) -> dict[str, Any]:
        """
        Batch-evaluates explainable capacity risks for all active wards across hospitals.
        """
        query = db.query(Ward).filter(Ward.status == "ACTIVE")
        if hospital_id is not None:
            query = query.filter(Ward.hospital_id == hospital_id)

        wards = query.all()
        results = []
        alerts_count = 0

        for w in wards:
            try:
                res = cls.evaluate_ward_capacity_risk(
                    db=db,
                    ward_id=w.id,
                    hospital_id=w.hospital_id,
                    horizon=horizon,
                    persist=True,
                )
                if res.get("has_alert"):
                    alerts_count += res.get("alerts_created_or_updated", 1)
                results.append(res)
            except Exception as e:
                logger.error(f"Error evaluating risk for ward {w.id}: {e}")
                results.append({
                    "ward_id": w.id,
                    "ward_name": w.name,
                    "risk_level": "ERROR",
                    "error": str(e),
                    "has_alert": False,
                })

        return {
            "status": "SUCCESS",
            "hospital_id": hospital_id,
            "wards_evaluated": len(wards),
            "alerts_count": alerts_count,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
        }

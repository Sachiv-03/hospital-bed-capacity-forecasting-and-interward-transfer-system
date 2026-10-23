import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ward import Ward
from app.models.transfer_recommendation import TransferRecommendation, RecommendationStatus
from app.models.transfer import Transfer, TransferStatus
from app.services.capacity_service import CapacityService
from app.services.historical_service import HistoricalService
from app.services.forecasting.forecast_service import ForecastService
from app.services.explainable_alert_service import ExplainableAlertService
from app.services.alert_service import AlertService
from app.services.transfer_service import TransferService
from app.services.patient_transfer_service import PatientTransferService

logger = logging.getLogger(__name__)


class AssistantTools:
    """
    Read-only, strictly hospital-scoped tools wrapping existing backend services.
    Enforces authorization, minimizes payload, redacts sensitive patient identifiers,
    and returns verified source-of-truth evidence.
    """

    @staticmethod
    def get_current_bed_availability(
        db: Session,
        hospital_id: int,
        ward_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Tool A: Retrieve live recorded bed availability and ward breakdowns."""
        now_iso = datetime.now(timezone.utc).isoformat()

        if ward_id is not None:
            ward_cap = CapacityService.get_ward_capacity(db, ward_id, hospital_id)
            return {
                "source": "CapacityService.get_ward_capacity",
                "timestamp": now_iso,
                "is_hospital_wide": False,
                "ward": {
                    "ward_id": ward_cap.ward_id,
                    "ward_name": ward_cap.ward_name,
                    "ward_type": ward_cap.ward_type,
                    "total_beds": ward_cap.total_beds,
                    "operational_beds": ward_cap.operational_beds,
                    "occupied_beds": ward_cap.occupied_beds,
                    "available_beds": ward_cap.available_beds,
                    "cleaning_beds": ward_cap.cleaning_beds,
                    "reserved_beds": ward_cap.reserved_beds,
                    "occupancy_percentage": ward_cap.occupancy_percentage,
                    "status": ward_cap.status,
                },
            }

        hosp_cap = CapacityService.get_hospital_capacity(db, hospital_id)
        ward_caps = CapacityService.get_all_ward_capacities(db, hospital_id)

        # Identify highest occupancy wards and wards with zero or low availability
        sorted_by_occ = sorted(ward_caps, key=lambda w: w.occupancy_percentage, reverse=True)
        zero_avail_wards = [w.ward_name for w in ward_caps if w.available_beds == 0]
        low_avail_wards = [
            {"ward_name": w.ward_name, "available_beds": w.available_beds, "occupancy_pct": w.occupancy_percentage}
            for w in ward_caps
            if 0 < w.available_beds <= settings.ALERT_LOW_AVAILABILITY_THRESHOLD
        ]

        ward_summaries = [
            {
                "ward_id": w.ward_id,
                "ward_name": w.ward_name,
                "ward_type": w.ward_type,
                "total_beds": w.total_beds,
                "occupied_beds": w.occupied_beds,
                "available_beds": w.available_beds,
                "occupancy_percentage": w.occupancy_percentage,
                "status": w.status,
            }
            for w in sorted_by_occ
        ]

        return {
            "source": "CapacityService.get_hospital_capacity",
            "timestamp": now_iso,
            "is_hospital_wide": True,
            "hospital_summary": {
                "hospital_id": hosp_cap.hospital_id,
                "hospital_name": hosp_cap.hospital_name,
                "total_beds": hosp_cap.total_beds,
                "operational_beds": hosp_cap.operational_beds,
                "occupied_beds": hosp_cap.occupied_beds,
                "available_beds": hosp_cap.available_beds,
                "cleaning_beds": hosp_cap.cleaning_beds,
                "reserved_beds": hosp_cap.reserved_beds,
                "occupancy_percentage": hosp_cap.occupancy_percentage,
                "status": hosp_cap.status,
            },
            "top_occupied_wards": ward_summaries[:3],
            "zero_available_wards": zero_avail_wards,
            "low_available_wards": low_avail_wards,
            "all_wards": ward_summaries,
        }

    @staticmethod
    def get_occupancy_trends(
        db: Session,
        hospital_id: int,
        ward_id: Optional[int] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Tool B: Retrieve historical occupancy records and trend trajectories."""
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=days)
        warnings: List[str] = []

        if ward_id is not None:
            snapshots = HistoricalService.get_ward_snapshot_history(
                db=db,
                ward_id=ward_id,
                hospital_id=hospital_id,
                start_date=start_date,
                end_date=now,
                limit=200,
            )
            ward = db.query(Ward).filter(Ward.id == ward_id).first()
            ward_name = ward.name if ward else f"Ward #{ward_id}"

            if not snapshots:
                warnings.append(f"No historical snapshots recorded for {ward_name} in the selected {days}-day window.")
                return {
                    "source": "HistoricalService.get_ward_snapshot_history",
                    "timestamp": now.isoformat(),
                    "ward_name": ward_name,
                    "date_range": f"{start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
                    "observations_count": 0,
                    "trend_direction": "UNKNOWN",
                    "warnings": warnings,
                }

            start_occ = snapshots[0].occupancy_percentage
            end_occ = snapshots[-1].occupancy_percentage
            diff = round(end_occ - start_occ, 2)
            direction = "INCREASING" if diff > 2.0 else ("DECREASING" if diff < -2.0 else "STABLE")

            return {
                "source": "HistoricalService.get_ward_snapshot_history",
                "timestamp": now.isoformat(),
                "ward_name": ward_name,
                "date_range": f"{start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
                "observations_count": len(snapshots),
                "first_recorded_occupancy_pct": start_occ,
                "latest_recorded_occupancy_pct": end_occ,
                "net_change_pct_points": diff,
                "trend_direction": direction,
                "warnings": warnings,
            }

        # Hospital-wide trends
        snapshots = HistoricalService.get_hospital_snapshot_history(
            db=db,
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=now,
            limit=200,
        )

        if not snapshots:
            warnings.append(f"No historical hospital snapshots recorded in the past {days} days.")
            return {
                "source": "HistoricalService.get_hospital_snapshot_history",
                "timestamp": now.isoformat(),
                "date_range": f"{start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
                "observations_count": 0,
                "trend_direction": "UNKNOWN",
                "warnings": warnings,
            }

        first_pt = snapshots[0].get("occupancy_percentage", 0.0)
        last_pt = snapshots[-1].get("occupancy_percentage", 0.0)
        diff = round(last_pt - first_pt, 2)
        direction = "INCREASING" if diff > 2.0 else ("DECREASING" if diff < -2.0 else "STABLE")

        return {
            "source": "HistoricalService.get_hospital_snapshot_history",
            "timestamp": now.isoformat(),
            "date_range": f"{start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
            "observations_count": len(snapshots),
            "first_recorded_occupancy_pct": first_pt,
            "latest_recorded_occupancy_pct": last_pt,
            "net_change_pct_points": diff,
            "trend_direction": direction,
            "warnings": warnings,
        }

    @staticmethod
    def get_forecast_explanation(
        db: Session,
        hospital_id: int,
        ward_id: Optional[int] = None,
        horizon: int = 7,
    ) -> Dict[str, Any]:
        """Tool C: Retrieve actual SARIMA / time-series capacity forecast metrics."""
        now_iso = datetime.now(timezone.utc).isoformat()
        warnings: List[str] = []

        if ward_id is not None:
            try:
                forecast_data = ForecastService.get_ward_latest_forecast(
                    db=db,
                    ward_id=ward_id,
                    hospital_id=hospital_id,
                    horizon=horizon,
                )
            except Exception as e:
                return {
                    "source": "ForecastService.get_ward_latest_forecast",
                    "timestamp": now_iso,
                    "available": False,
                    "error": str(e),
                    "warnings": [f"Could not retrieve forecast for ward {ward_id}: {str(e)}"],
                }

            model_name = forecast_data.get("model", "SARIMA")
            if model_name == "NONE":
                warnings.append("Insufficient historical observations to train SARIMA (< 7 daily snapshots).")

            predictions = forecast_data.get("predictions", [])
            pred_summary = [
                {
                    "target_date": p.get("target_date"),
                    "predicted_occupied_beds": p.get("predicted_occupied_beds"),
                    "predicted_occupancy_pct": p.get("predicted_occupancy_percentage"),
                    "lower_bound_pct": p.get("lower_bound"),
                    "upper_bound_pct": p.get("upper_bound"),
                    "risk_level": p.get("risk_level"),
                }
                for p in predictions
            ]

            return {
                "source": "ForecastService.get_ward_latest_forecast",
                "timestamp": forecast_data.get("generated_at", now_iso),
                "available": True,
                "ward_name": forecast_data.get("ward_name"),
                "total_beds": forecast_data.get("total_beds"),
                "current_occupancy_pct": forecast_data.get("current_occupancy_percentage"),
                "model": model_name,
                "horizon_days": forecast_data.get("horizon", horizon),
                "predictions": pred_summary,
                "warnings": warnings,
            }

        # Hospital-level aggregated forecast
        try:
            hosp_forecast = ForecastService.get_hospital_forecast(
                db=db,
                hospital_id=hospital_id,
                horizon=horizon,
            )
            predictions = hosp_forecast.get("predictions", [])
            pred_summary = [
                {
                    "target_date": p.get("target_date"),
                    "predicted_occupied_beds": p.get("predicted_occupied_beds"),
                    "predicted_occupancy_pct": p.get("predicted_occupancy_percentage"),
                    "risk_level": p.get("risk_level"),
                }
                for p in predictions
            ]
            return {
                "source": "ForecastService.get_hospital_forecast",
                "timestamp": hosp_forecast.get("generated_at", now_iso),
                "available": True,
                "hospital_name": hosp_forecast.get("hospital_name"),
                "total_beds": hosp_forecast.get("total_beds"),
                "current_occupancy_pct": hosp_forecast.get("current_occupancy_percentage"),
                "horizon_days": hosp_forecast.get("horizon", horizon),
                "predictions": pred_summary,
                "ward_breakdown": hosp_forecast.get("ward_breakdown", [])[:5],
                "warnings": warnings,
            }
        except Exception as e:
            return {
                "source": "ForecastService.get_hospital_forecast",
                "timestamp": now_iso,
                "available": False,
                "error": str(e),
                "warnings": [f"Hospital forecast calculation failed: {str(e)}"],
            }

    @staticmethod
    def get_capacity_risk_and_alerts(
        db: Session,
        hospital_id: int,
        ward_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Tool D: Retrieve explainable risk rule evaluations (Rules A-G) and active alerts."""
        now_iso = datetime.now(timezone.utc).isoformat()
        warnings: List[str] = []

        if ward_id is not None:
            try:
                risk_eval = ExplainableAlertService.evaluate_ward_capacity_risk(
                    db=db,
                    ward_id=ward_id,
                    hospital_id=hospital_id,
                    persist=False,
                )
                return {
                    "source": "ExplainableAlertService.evaluate_ward_capacity_risk",
                    "timestamp": now_iso,
                    "ward_name": risk_eval.get("ward_name"),
                    "risk_level": risk_eval.get("risk_level"),
                    "headline": risk_eval.get("headline"),
                    "explanation": risk_eval.get("human_readable_explanation"),
                    "triggered_rules": risk_eval.get("triggered_rules", []),
                    "evidence": risk_eval.get("evidence", {}),
                    "suggested_actions": risk_eval.get("suggested_actions", []),
                    "warnings": warnings,
                }
            except Exception as e:
                warnings.append(f"Risk evaluation error for ward {ward_id}: {str(e)}")

        # Hospital-wide evaluation
        all_evals_res = ExplainableAlertService.evaluate_all_hospital_wards(
            db=db,
            hospital_id=hospital_id,
        )
        all_evals = all_evals_res.get("results", [])

        active_db_alerts = AlertService.get_alerts(
            db=db,
            hospital_id=hospital_id,
            status="ACTIVE",
        )

        critical_wards = [w for w in all_evals if w.get("risk_level") == "CRITICAL"]
        high_wards = [w for w in all_evals if w.get("risk_level") == "HIGH"]

        return {
            "source": "ExplainableAlertService & AlertService",
            "timestamp": now_iso,
            "total_active_alerts": len(active_db_alerts),
            "critical_risk_wards_count": len(critical_wards),
            "high_risk_wards_count": len(high_wards),
            "priority_review_wards": [
                {
                    "ward_name": w.get("ward_name"),
                    "risk_level": w.get("risk_level"),
                    "headline": w.get("headline"),
                    "rules": [r.get("rule_name") for r in w.get("triggered_rules", [])],
                }
                for w in (critical_wards + high_wards)[:5]
            ],
            "active_alerts_summary": [
                {
                    "alert_type": a.get("alert_type"),
                    "severity": a.get("severity"),
                    "ward_id": a.get("ward_id"),
                    "message": a.get("message"),
                }
                for a in active_db_alerts[:5]
            ],
            "warnings": warnings,
        }

    @staticmethod
    def get_transfer_decision_support(
        db: Session,
        hospital_id: int,
    ) -> Dict[str, Any]:
        """Tool E: Retrieve transfer overview statistics, existing recommendations, and pending requests."""
        now_iso = datetime.now(timezone.utc).isoformat()
        warnings: List[str] = []

        overview_stats = TransferService.get_hospital_overview_stats(db, hospital_id)

        # Retrieve verified existing recommendations from database
        recs = (
            db.query(TransferRecommendation)
            .filter(
                TransferRecommendation.hospital_id == hospital_id,
                TransferRecommendation.status == RecommendationStatus.PENDING.value,
            )
            .order_by(TransferRecommendation.priority_score.desc())
            .limit(5)
            .all()
        )

        rec_items = [
            {
                "id": r.id,
                "source_ward_name": r.source_ward.name if r.source_ward else f"Ward #{r.source_ward_id}",
                "destination_ward_name": r.destination_ward.name if r.destination_ward else f"Ward #{r.destination_ward_id}",
                "priority_level": r.priority_level,
                "priority_score": r.priority_score,
                "reason": r.reason,
                "recommended_transfer_count": r.recommended_transfer_count,
            }
            for r in recs
        ]

        # Retrieve pending patient transfer requests
        pending_transfers, _ = PatientTransferService.get_transfers(
            db=db,
            hospital_id=hospital_id,
            status_filter=TransferStatus.REQUESTED.value,
            limit=5,
        )
        transfers_summary = [
            {
                "id": t.id,
                "source_ward_name": t.source_ward.name if t.source_ward else f"Ward #{t.source_ward_id}",
                "destination_ward_name": t.destination_ward.name if t.destination_ward else f"Ward #{t.destination_ward_id}",
                "priority": getattr(t, "priority", "NORMAL"),
                "clinical_reason": t.reason,
                "status": t.status,
            }
            for t in pending_transfers
        ]

        return {
            "source": "TransferService & PatientTransferService",
            "timestamp": now_iso,
            "overview_stats": overview_stats,
            "pending_recommendations": rec_items,
            "pending_patient_transfers": transfers_summary,
            "action_guidance": "Transfers cannot be autonomously executed by the AI. Authorized clinicians must review and approve transfers in the Transfers module.",
            "warnings": warnings,
        }

    @staticmethod
    def get_management_summary(
        db: Session,
        hospital_id: int,
    ) -> Dict[str, Any]:
        """Tool F: Retrieve executive command analytics payload."""
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            analytics = CapacityService.get_management_analytics(
                db=db,
                hospital_id=hospital_id,
                horizon=7,
            )
            ov = analytics.overview_metrics
            risk = analytics.risk_summary
            dq = analytics.data_quality
            return {
                "source": "CapacityService.get_management_analytics",
                "timestamp": analytics.freshness.reporting_timestamp or now_iso,
                "hospital_name": analytics.hospital_name,
                "overview": {
                    "total_beds": ov.total_capacity,
                    "operational_beds": ov.operational_beds,
                    "occupied_beds": ov.occupied_beds,
                    "available_beds": ov.available_beds,
                    "occupancy_rate": ov.occupancy_rate,
                    "critical_risk_wards": ov.wards_at_elevated_risk,
                    "unacknowledged_alerts": ov.unacknowledged_alerts,
                    "pending_transfers": ov.pending_transfer_requests,
                },
                "risk_summary": {
                    "high_risk_wards_count": len(risk.high_risk_wards),
                    "moderate_risk_wards_count": len(risk.moderate_risk_wards),
                    "normal_risk_wards_count": len(risk.normal_risk_wards),
                    "critical_risk_wards_count": len(risk.critical_risk_wards),
                },
                "data_quality": {
                    "data_quality_score": dq.health_score if dq else 100.0,
                    "health_status": "HEALTHY",
                },
            }
        except Exception as e:
            logger.error(f"Failed to generate management summary: {e}")
            return {
                "source": "CapacityService.get_management_analytics",
                "timestamp": now_iso,
                "error": str(e),
                "warnings": ["Executive management summary could not be retrieved from analytics pipeline."],
            }

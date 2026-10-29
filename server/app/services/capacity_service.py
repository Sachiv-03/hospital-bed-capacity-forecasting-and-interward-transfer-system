from datetime import date, datetime, timezone
import logging
from fastapi import HTTPException, status
from sqlalchemy import func, Date, cast
from sqlalchemy.orm import Session

from app.models.bed import Bed, BedStatus
from app.models.hospital import Hospital
from app.models.ward import Ward, WardStatus
from app.models.admission import Admission, AdmissionStatus
from app.models.capacity_alert import CapacityAlert, AlertSeverity, AlertStatus
from app.models.transfer import Transfer, TransferStatus
from app.models.transfer_recommendation import TransferRecommendation, RecommendationStatus
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.bed_capacity_forecast import BedCapacityForecast
from app.schemas.capacity import (
    HospitalCapacityResponse,
    WardCapacityResponse,
    OccupancySummaryResponse,
    get_capacity_status,
    ManagementAnalyticsResponse,
    ManagementFreshness,
    ManagementOverviewMetrics,
    ManagementWardRiskItem,
    ManagementRiskSummary,
    WardTransferCountItem,
    ManagementTransferActivity,
    ManagementDataQualitySummary,
)

logger = logging.getLogger(__name__)


class CapacityService:

    @staticmethod
    def _count_beds_by_status(db: Session, ward_id: int) -> dict:
        """Return a dict of {status: count} for all beds in a ward."""
        rows = (
            db.query(Bed.status, func.count(Bed.id))
            .filter(Bed.ward_id == ward_id)
            .group_by(Bed.status)
            .all()
        )
        counts = {
            BedStatus.AVAILABLE.value: 0,
            BedStatus.OCCUPIED.value: 0,
            BedStatus.CLEANING.value: 0,
            BedStatus.MAINTENANCE.value: 0,
            BedStatus.RESERVED.value: 0,
            "INACTIVE": 0,
        }
        for stat, cnt in rows:
            counts[stat] = cnt
        return counts

    @staticmethod
    def get_ward_capacity(db: Session, ward_id: int, requesting_hospital_id: int) -> WardCapacityResponse:
        """Return real-time capacity for a single ward. Enforces hospital ownership."""
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
        if ward.hospital_id != requesting_hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this ward",
            )

        counts = CapacityService._count_beds_by_status(db, ward_id)
        total = sum(counts.values())
        occupied = counts.get(BedStatus.OCCUPIED.value, 0)
        available = counts.get(BedStatus.AVAILABLE.value, 0)
        
        # Operational Beds = Available + Occupied (excludes Maintenance, Cleaning, Reserved, Inactive)
        operational = occupied + available
        
        occupancy_pct = round((occupied / operational * 100), 2) if operational > 0 else 0.0
        avail_cap_pct = round((available / operational * 100), 2) if operational > 0 else 0.0

        return WardCapacityResponse(
            ward_id=ward.id,
            ward_name=ward.name,
            ward_type=ward.ward_type,
            hospital_id=ward.hospital_id,
            total_beds=total,
            operational_beds=operational,
            occupied_beds=occupied,
            available_beds=available,
            cleaning_beds=counts.get(BedStatus.CLEANING.value, 0),
            reserved_beds=counts.get(BedStatus.RESERVED.value, 0),
            maintenance_beds=counts.get(BedStatus.MAINTENANCE.value, 0),
            inactive_beds=counts.get("INACTIVE", 0),
            occupancy_percentage=occupancy_pct,
            available_capacity_percentage=avail_cap_pct,
            status=get_capacity_status(occupancy_pct),
        )

    @staticmethod
    def get_all_ward_capacities(
        db: Session, hospital_id: int
    ) -> list[WardCapacityResponse]:
        """Return capacity for every active ward in a hospital (batch-optimized)."""
        wards = (
            db.query(Ward)
            .filter(
                Ward.hospital_id == hospital_id,
                Ward.status == WardStatus.ACTIVE.value,
            )
            .order_by(Ward.name)
            .all()
        )
        if not wards:
            return []

        # Batch query all bed counts for this hospital in one round-trip
        bed_rows = (
            db.query(Bed.ward_id, Bed.status, func.count(Bed.id))
            .filter(Bed.hospital_id == hospital_id)
            .group_by(Bed.ward_id, Bed.status)
            .all()
        )
        counts_by_ward: dict[int, dict[str, int]] = {}
        for w_id, stat, cnt in bed_rows:
            if w_id not in counts_by_ward:
                counts_by_ward[w_id] = {
                    BedStatus.AVAILABLE.value: 0,
                    BedStatus.OCCUPIED.value: 0,
                    BedStatus.CLEANING.value: 0,
                    BedStatus.MAINTENANCE.value: 0,
                    BedStatus.RESERVED.value: 0,
                    "INACTIVE": 0,
                }
            counts_by_ward[w_id][stat] = cnt

        default_counts = {
            BedStatus.AVAILABLE.value: 0,
            BedStatus.OCCUPIED.value: 0,
            BedStatus.CLEANING.value: 0,
            BedStatus.MAINTENANCE.value: 0,
            BedStatus.RESERVED.value: 0,
            "INACTIVE": 0,
        }

        results = []
        for ward in wards:
            counts = counts_by_ward.get(ward.id, default_counts)
            total = sum(counts.values())
            occupied = counts.get(BedStatus.OCCUPIED.value, 0)
            available = counts.get(BedStatus.AVAILABLE.value, 0)
            operational = occupied + available

            occupancy_pct = (
                round((occupied / operational * 100), 2) if operational > 0 else 0.0
            )
            avail_cap_pct = (
                round((available / operational * 100), 2) if operational > 0 else 0.0
            )

            results.append(
                WardCapacityResponse(
                    ward_id=ward.id,
                    ward_name=ward.name,
                    ward_type=ward.ward_type,
                    hospital_id=ward.hospital_id,
                    total_beds=total,
                    operational_beds=operational,
                    occupied_beds=occupied,
                    available_beds=available,
                    cleaning_beds=counts.get(BedStatus.CLEANING.value, 0),
                    reserved_beds=counts.get(BedStatus.RESERVED.value, 0),
                    maintenance_beds=counts.get(BedStatus.MAINTENANCE.value, 0),
                    inactive_beds=counts.get("INACTIVE", 0),
                    occupancy_percentage=occupancy_pct,
                    available_capacity_percentage=avail_cap_pct,
                    status=get_capacity_status(occupancy_pct),
                )
            )
        return results

    @staticmethod
    def get_hospital_capacity(db: Session, hospital_id: int) -> HospitalCapacityResponse:
        """Return aggregated capacity for an entire hospital."""
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

        ward_capacities = CapacityService.get_all_ward_capacities(db, hospital_id)

        total_wards = len(ward_capacities)
        total_beds = sum(w.total_beds for w in ward_capacities)
        operational_beds = sum(w.operational_beds for w in ward_capacities)
        occupied_beds = sum(w.occupied_beds for w in ward_capacities)
        available_beds = sum(w.available_beds for w in ward_capacities)
        cleaning_beds = sum(w.cleaning_beds for w in ward_capacities)
        reserved_beds = sum(w.reserved_beds for w in ward_capacities)
        maintenance_beds = sum(w.maintenance_beds for w in ward_capacities)
        inactive_beds = sum(w.inactive_beds for w in ward_capacities)

        occupancy_pct = round((occupied_beds / operational_beds * 100), 2) if operational_beds > 0 else 0.0
        avail_cap_pct = round((available_beds / operational_beds * 100), 2) if operational_beds > 0 else 0.0

        # Calculate live stay movements from Phase 5 admissions table
        today_date = date.today()

        active_admissions = db.query(Admission).filter(
            Admission.hospital_id == hospital_id,
            Admission.status == AdmissionStatus.ADMITTED.value
        ).count()

        admissions_today = db.query(Admission).filter(
            Admission.hospital_id == hospital_id,
            cast(Admission.admission_date, Date) == today_date
        ).count()

        discharges_today = db.query(Admission).filter(
            Admission.hospital_id == hospital_id,
            cast(Admission.discharge_date, Date) == today_date
        ).count()

        return HospitalCapacityResponse(
            hospital_id=hospital.id,
            hospital_name=hospital.name,
            total_wards=total_wards,
            total_beds=total_beds,
            operational_beds=operational_beds,
            occupied_beds=occupied_beds,
            available_beds=available_beds,
            cleaning_beds=cleaning_beds,
            reserved_beds=reserved_beds,
            maintenance_beds=maintenance_beds,
            inactive_beds=inactive_beds,
            occupancy_percentage=occupancy_pct,
            available_capacity_percentage=avail_cap_pct,
            status=get_capacity_status(occupancy_pct),
            active_admissions=active_admissions,
            admissions_today=admissions_today,
            discharges_today=discharges_today,
            ward_capacities=[w.model_dump() for w in ward_capacities],
        )

    @staticmethod
    def get_occupancy_summary(db: Session, hospital_id: int) -> OccupancySummaryResponse:
        """Return complete command summary for hospital capacity & stay movements."""
        cap = CapacityService.get_hospital_capacity(db, hospital_id)
        return OccupancySummaryResponse(
            hospital_id=cap.hospital_id,
            hospital_name=cap.hospital_name,
            total_beds=cap.total_beds,
            operational_beds=cap.operational_beds,
            occupied_beds=cap.occupied_beds,
            available_beds=cap.available_beds,
            maintenance_beds=cap.maintenance_beds,
            inactive_beds=cap.inactive_beds,
            occupancy_percentage=cap.occupancy_percentage,
            available_capacity_percentage=cap.available_capacity_percentage,
            capacity_status=cap.status,
            active_admissions=cap.active_admissions,
            admissions_today=cap.admissions_today,
            discharges_today=cap.discharges_today,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    @staticmethod
    def get_management_analytics(
        db: Session,
        hospital_id: int,
        ward_id: int | None = None,
        horizon: int = 7,
    ) -> ManagementAnalyticsResponse:
        """
        Phase 13: Management Analytics Dashboard aggregation.
        Aggregates verified live occupancy, SARIMA forecasts, capacity-risk classifications,
        alerts, inter-ward transfer activity, and data quality into an authorized report.
        """
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

        selected_ward = None
        if ward_id is not None:
            selected_ward = db.query(Ward).filter(Ward.id == ward_id).first()
            if not selected_ward:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
            if selected_ward.hospital_id != hospital_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ward does not belong to requested hospital")

        # 1. Ward capacities
        all_ward_caps = CapacityService.get_all_ward_capacities(db, hospital_id)
        if selected_ward:
            target_caps = [w for w in all_ward_caps if w.ward_id == selected_ward.id]
        else:
            target_caps = all_ward_caps

        total_capacity = sum(w.total_beds for w in target_caps)
        operational_beds = sum(w.operational_beds for w in target_caps)
        occupied_beds = sum(w.occupied_beds for w in target_caps)
        available_beds = sum(w.available_beds for w in target_caps)
        occupancy_rate = round((occupied_beds / operational_beds * 100), 2) if operational_beds > 0 else 0.0
        cap_status = get_capacity_status(occupancy_rate)

        # 2. Alerts Summary
        alert_query = db.query(CapacityAlert).filter(CapacityAlert.hospital_id == hospital_id)
        if selected_ward:
            alert_query = alert_query.filter(CapacityAlert.ward_id == selected_ward.id)

        all_alerts = alert_query.all()
        active_alerts = [a for a in all_alerts if a.status in (AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value)]
        high_critical_alerts = [
            a for a in active_alerts
            if a.severity in (AlertSeverity.HIGH.value, AlertSeverity.CRITICAL.value)
        ]
        unacknowledged_alerts = [a for a in active_alerts if a.status == AlertStatus.ACTIVE.value or a.acknowledged_at is None]

        # 3. Inter-Ward Transfers Activity
        transfer_query = db.query(Transfer).filter(Transfer.hospital_id == hospital_id)
        if selected_ward:
            transfer_query = transfer_query.filter(
                (Transfer.source_ward_id == selected_ward.id) | (Transfer.destination_ward_id == selected_ward.id)
            )
        transfers = transfer_query.all()

        by_status = {
            TransferStatus.REQUESTED.value: 0,
            TransferStatus.APPROVED.value: 0,
            TransferStatus.REJECTED.value: 0,
            TransferStatus.COMPLETED.value: 0,
            TransferStatus.CANCELLED.value: 0,
        }
        for t in transfers:
            if t.status in by_status:
                by_status[t.status] += 1
            else:
                by_status[t.status] = 1

        # Recommendations pending
        rec_query = db.query(TransferRecommendation).filter(
            TransferRecommendation.hospital_id == hospital_id,
            TransferRecommendation.status == RecommendationStatus.PENDING.value
        )
        if selected_ward:
            rec_query = rec_query.filter(
                (TransferRecommendation.source_ward_id == selected_ward.id) | (TransferRecommendation.destination_ward_id == selected_ward.id)
            )
        pending_recs = rec_query.count()

        # Transfers count by ward
        ward_transfer_pressure = []
        for w in (all_ward_caps if not selected_ward else target_caps):
            out_cnt = sum(1 for t in transfers if t.source_ward_id == w.ward_id and t.status in (TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value, TransferStatus.COMPLETED.value))
            in_cnt = sum(1 for t in transfers if t.destination_ward_id == w.ward_id and t.status in (TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value, TransferStatus.COMPLETED.value))
            ward_transfer_pressure.append(WardTransferCountItem(
                ward_id=w.ward_id,
                ward_name=w.ward_name,
                transfers_out_count=out_cnt,
                transfers_in_count=in_cnt,
            ))

        # 4. Forecast & Risk Categorization
        critical_risk_wards = []
        high_risk_wards = []
        moderate_risk_wards = []
        normal_risk_wards = []
        unreliable_wards = []

        try:
            from app.services.forecasting.forecast_service import ForecastService
            hospital_forecast = ForecastService.get_hospital_forecast(db, hospital_id=hospital_id, horizon=horizon)
            ward_summaries = (
                hospital_forecast.get("ward_summaries", [])
                if isinstance(hospital_forecast, dict)
                else getattr(hospital_forecast, "ward_summaries", [])
            )
            ward_forecast_map = {
                (ws.get("ward_id") if isinstance(ws, dict) else ws.ward_id): ws
                for ws in ward_summaries
            }
        except Exception as exc:
            logger.warning("Forecast retrieval notice for management analytics: %s", exc)
            ward_forecast_map = {}

        for w in (all_ward_caps if not selected_ward else target_caps):
            wf = ward_forecast_map.get(w.ward_id)
            if wf:
                predicted_peak = float(
                    wf.get("max_7day_occupancy_percentage", w.occupancy_percentage)
                    if isinstance(wf, dict)
                    else getattr(wf, "max_7day_occupancy_percentage", w.occupancy_percentage)
                )
                risk_lvl = str(
                    wf.get("max_risk_level", w.status)
                    if isinstance(wf, dict)
                    else getattr(wf, "max_risk_level", w.status)
                )
                item = ManagementWardRiskItem(
                    ward_id=w.ward_id,
                    ward_name=w.ward_name,
                    ward_type=w.ward_type,
                    total_beds=w.total_beds,
                    current_occupancy_percentage=w.occupancy_percentage,
                    predicted_peak_occupancy_percentage=predicted_peak,
                    risk_level=risk_lvl,
                )
                if risk_lvl == "CRITICAL" or predicted_peak >= 95.0:
                    critical_risk_wards.append(item)
                elif risk_lvl == "HIGH" or predicted_peak >= 85.0:
                    high_risk_wards.append(item)
                elif risk_lvl == "MODERATE" or predicted_peak >= 70.0:
                    moderate_risk_wards.append(item)
                else:
                    normal_risk_wards.append(item)
            else:
                item = ManagementWardRiskItem(
                    ward_id=w.ward_id,
                    ward_name=w.ward_name,
                    ward_type=w.ward_type,
                    total_beds=w.total_beds,
                    current_occupancy_percentage=w.occupancy_percentage,
                    predicted_peak_occupancy_percentage=w.occupancy_percentage,
                    risk_level=w.status,
                    data_quality_warning="No forecast run available for this horizon",
                )
                if w.status == "CRITICAL":
                    critical_risk_wards.append(item)
                elif w.status in ("HIGH", "WARNING"):
                    high_risk_wards.append(item)
                else:
                    normal_risk_wards.append(item)

        wards_at_elevated_risk = len(critical_risk_wards) + len(high_risk_wards)

        # 5. Freshness Timestamps
        latest_snap = db.query(OccupancySnapshot).filter(OccupancySnapshot.hospital_id == hospital_id).order_by(OccupancySnapshot.snapshot_time.desc()).first()
        latest_fc = db.query(BedCapacityForecast).filter(BedCapacityForecast.hospital_id == hospital_id).order_by(BedCapacityForecast.generated_at.desc()).first()
        latest_al = db.query(CapacityAlert).filter(CapacityAlert.hospital_id == hospital_id).order_by(CapacityAlert.created_at.desc()).first()

        now_utc = datetime.now(timezone.utc)
        freshness = ManagementFreshness(
            occupancy_last_updated=latest_snap.snapshot_time.isoformat() if latest_snap else (now_utc.isoformat() if all_ward_caps else None),
            forecast_last_updated=latest_fc.generated_at.isoformat() if latest_fc and latest_fc.generated_at else None,
            alerts_last_evaluated=latest_al.created_at.isoformat() if latest_al and latest_al.created_at else None,
            reporting_timestamp=now_utc.isoformat(),
        )

        # 6. Data Quality
        try:
            from app.services.historical_service import HistoricalService
            dq = HistoricalService.get_data_quality_report(db, hospital_id=hospital_id)
            data_quality_summary = ManagementDataQualitySummary(
                total_observations=dq.get("total_observations") or dq.get("total_snapshots", 0),
                health_score=float(dq.get("health_score", 100.0)),
                data_frequency=dq.get("data_frequency", "DAILY"),
                earliest_observation_date=dq.get("earliest_observation_date"),
                latest_observation_date=dq.get("latest_observation_date"),
                missing_dates=dq.get("missing_dates", 0),
            )
        except Exception as exc:
            logger.warning("Data quality summary retrieval notice: %s", exc)
            data_quality_summary = ManagementDataQualitySummary()

        overview_metrics = ManagementOverviewMetrics(
            total_capacity=total_capacity,
            operational_beds=operational_beds,
            occupied_beds=occupied_beds,
            available_beds=available_beds,
            occupancy_rate=occupancy_rate,
            status=cap_status,
            active_high_severity_alerts=len(high_critical_alerts),
            total_active_alerts=len(active_alerts),
            unacknowledged_alerts=len(unacknowledged_alerts),
            wards_at_elevated_risk=wards_at_elevated_risk,
            total_wards=len(all_ward_caps),
            pending_transfer_requests=by_status.get(TransferStatus.REQUESTED.value, 0),
            pending_transfer_recommendations=pending_recs,
            approved_transfers=by_status.get(TransferStatus.APPROVED.value, 0),
            completed_transfers=by_status.get(TransferStatus.COMPLETED.value, 0),
        )

        return ManagementAnalyticsResponse(
            hospital_id=hospital.id,
            hospital_name=hospital.name,
            selected_ward_id=selected_ward.id if selected_ward else None,
            selected_ward_name=selected_ward.name if selected_ward else None,
            selected_horizon=horizon,
            freshness=freshness,
            overview_metrics=overview_metrics,
            ward_occupancy_breakdown=all_ward_caps,
            risk_summary=ManagementRiskSummary(
                critical_risk_wards=critical_risk_wards,
                high_risk_wards=high_risk_wards,
                moderate_risk_wards=moderate_risk_wards,
                normal_risk_wards=normal_risk_wards,
                unreliable_or_missing_data_wards=unreliable_wards,
            ),
            transfer_activity=ManagementTransferActivity(
                by_status=by_status,
                ward_transfer_pressure=ward_transfer_pressure,
                pending_requests_count=by_status.get(TransferStatus.REQUESTED.value, 0),
                pending_recommendations_count=pending_recs,
            ),
            data_quality=data_quality_summary,
        )


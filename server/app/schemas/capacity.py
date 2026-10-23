from typing import List, Optional
from pydantic import BaseModel, Field


class CapacityStatusEnum:
    """Occupancy thresholds — easy to adjust later."""
    NORMAL = "NORMAL"        # < 70%
    WARNING = "WARNING"      # 70 – 84.99% (or MODERATE)
    HIGH = "HIGH"            # 85 – 94.99%
    CRITICAL = "CRITICAL"    # >= 95%


def get_capacity_status(occupancy_pct: float) -> str:
    """Return a textual occupancy status label from a percentage (0-100)."""
    if occupancy_pct >= 95:
        return CapacityStatusEnum.CRITICAL
    if occupancy_pct >= 85:
        return CapacityStatusEnum.HIGH
    if occupancy_pct >= 70:
        return CapacityStatusEnum.WARNING
    return CapacityStatusEnum.NORMAL


class WardCapacityResponse(BaseModel):
    ward_id: int
    ward_name: str
    ward_type: str = ""
    hospital_id: int
    total_beds: int = Field(default=0, description="Total beds in the ward")
    operational_beds: int = Field(default=0, description="Operational beds (Occupied + Available)")
    occupied_beds: int = Field(default=0)
    available_beds: int = Field(default=0)
    cleaning_beds: int = Field(default=0)
    reserved_beds: int = Field(default=0)
    maintenance_beds: int = Field(default=0)
    inactive_beds: int = Field(default=0)
    occupancy_percentage: float = Field(default=0.0)
    available_capacity_percentage: float = Field(default=0.0)
    status: str = Field(default="NORMAL", description="NORMAL | WARNING | HIGH | CRITICAL")


class HospitalCapacityResponse(BaseModel):
    hospital_id: int
    hospital_name: str
    total_wards: int = Field(default=0)
    total_beds: int = Field(default=0)
    operational_beds: int = Field(default=0, description="Operational beds (Occupied + Available)")
    occupied_beds: int = Field(default=0)
    available_beds: int = Field(default=0)
    cleaning_beds: int = Field(default=0)
    reserved_beds: int = Field(default=0)
    maintenance_beds: int = Field(default=0)
    inactive_beds: int = Field(default=0)
    occupancy_percentage: float = Field(default=0.0)
    available_capacity_percentage: float = Field(default=0.0)
    status: str = Field(default="NORMAL", description="NORMAL | WARNING | HIGH | CRITICAL")
    active_admissions: int = Field(default=0)
    admissions_today: int = Field(default=0)
    discharges_today: int = Field(default=0)
    ward_capacities: List[dict] = Field(default_factory=list, description="Per-ward breakdown")


class OccupancySummaryResponse(BaseModel):
    hospital_id: int
    hospital_name: str
    total_beds: int
    operational_beds: int
    occupied_beds: int
    available_beds: int
    maintenance_beds: int
    inactive_beds: int
    occupancy_percentage: float
    available_capacity_percentage: float
    capacity_status: str
    active_admissions: int
    admissions_today: int
    discharges_today: int
    timestamp: str


class OccupancySnapshotResponse(BaseModel):
    id: int
    hospital_id: int
    ward_id: int
    ward_name: str = ""
    snapshot_time: str
    total_beds: int
    occupied_beds: int
    available_beds: int
    cleaning_beds: int
    reserved_beds: int
    maintenance_beds: int
    occupancy_percentage: float


class OccupancySnapshotListResponse(BaseModel):
    items: List[OccupancySnapshotResponse]
    total: int
    page: int = 1
    limit: int = 50


class DailySummaryResponse(BaseModel):
    date: str
    hospital_id: int
    ward_id: int
    ward_name: str = ""
    average_occupancy: float
    maximum_occupancy: float
    minimum_occupancy: float
    admissions: int
    discharges: int
    transfers_in: int
    transfers_out: int


class DataQualityReportResponse(BaseModel):
    total_snapshots: int
    invalid_snapshots: int
    duplicate_snapshots: int
    invalid_events: int
    missing_data_count: int
    last_successful_snapshot: Optional[str] = None
    health_score: float = 100.0
    # Phase 8 Daily Historical Validation Metrics
    total_observations: Optional[int] = None
    valid_observations: Optional[int] = None
    duplicate_observations: Optional[int] = None
    missing_dates: Optional[int] = None
    invalid_observations: Optional[int] = None
    conflicting_observations: Optional[int] = 0
    number_of_hospitals: Optional[int] = None
    number_of_wards: Optional[int] = None
    earliest_observation_date: Optional[str] = None
    latest_observation_date: Optional[str] = None
    data_frequency: Optional[str] = "DAILY"


class ForecastingDatasetItem(BaseModel):
    date: str
    hospital_id: int
    ward_id: int
    ward_name: str
    total_beds: int
    occupied_beds: int
    available_beds: int
    occupancy_percentage: float
    admissions: int
    discharges: int
    transfers_in: int
    transfers_out: int
    day_of_week: int


class ForecastingDatasetResponse(BaseModel):
    items: List[ForecastingDatasetItem]
    total_records: int
    start_date: str
    end_date: str
    missing_periods_reported: int


class ManualSnapshotGenerateResponse(BaseModel):
    snapshots_created: int
    hospitals_processed: int
    wards_processed: int


# ── Phase 13 Management Analytics Dashboard Schemas ──────────────────────────

class ManagementFreshness(BaseModel):
    occupancy_last_updated: Optional[str] = None
    forecast_last_updated: Optional[str] = None
    alerts_last_evaluated: Optional[str] = None
    reporting_timestamp: str


class ManagementOverviewMetrics(BaseModel):
    total_capacity: int = Field(default=0, description="Total physical bed capacity")
    operational_beds: int = Field(default=0, description="Operational capacity (occupied + available)")
    occupied_beds: int = Field(default=0, description="Currently occupied beds")
    available_beds: int = Field(default=0, description="Currently available beds")
    occupancy_rate: float = Field(default=0.0, description="Current occupancy percentage")
    status: str = Field(default="NORMAL", description="Capacity status: NORMAL | WARNING | HIGH | CRITICAL")
    active_high_severity_alerts: int = Field(default=0, description="Count of active HIGH and CRITICAL alerts")
    total_active_alerts: int = Field(default=0, description="Total active alerts count")
    unacknowledged_alerts: int = Field(default=0, description="Unacknowledged alerts count")
    wards_at_elevated_risk: int = Field(default=0, description="Count of wards at HIGH or CRITICAL predicted risk")
    total_wards: int = Field(default=0, description="Total active wards")
    pending_transfer_requests: int = Field(default=0, description="Pending patient transfer requests (REQUESTED)")
    pending_transfer_recommendations: int = Field(default=0, description="Pending transfer recommendations")
    approved_transfers: int = Field(default=0, description="Approved transfers")
    completed_transfers: int = Field(default=0, description="Completed transfers")


class ManagementWardRiskItem(BaseModel):
    ward_id: int
    ward_name: str
    ward_type: str = ""
    total_beds: int = 0
    current_occupancy_percentage: float = 0.0
    predicted_peak_occupancy_percentage: float = 0.0
    risk_level: str = "NORMAL"
    threshold_crossing_date: Optional[str] = None
    days_to_threshold: Optional[int] = None
    data_quality_warning: Optional[str] = None


class ManagementRiskSummary(BaseModel):
    critical_risk_wards: List[ManagementWardRiskItem] = Field(default_factory=list)
    high_risk_wards: List[ManagementWardRiskItem] = Field(default_factory=list)
    moderate_risk_wards: List[ManagementWardRiskItem] = Field(default_factory=list)
    normal_risk_wards: List[ManagementWardRiskItem] = Field(default_factory=list)
    unreliable_or_missing_data_wards: List[ManagementWardRiskItem] = Field(default_factory=list)


class WardTransferCountItem(BaseModel):
    ward_id: int
    ward_name: str
    transfers_out_count: int = 0
    transfers_in_count: int = 0


class ManagementTransferActivity(BaseModel):
    by_status: dict = Field(default_factory=dict, description="Counts by TransferStatus")
    ward_transfer_pressure: List[WardTransferCountItem] = Field(default_factory=list)
    pending_requests_count: int = 0
    pending_recommendations_count: int = 0


class ManagementDataQualitySummary(BaseModel):
    total_observations: Optional[int] = 0
    health_score: Optional[float] = 100.0
    data_frequency: Optional[str] = "DAILY"
    earliest_observation_date: Optional[str] = None
    latest_observation_date: Optional[str] = None
    missing_dates: Optional[int] = 0


class ManagementAnalyticsResponse(BaseModel):
    hospital_id: int
    hospital_name: str
    selected_ward_id: Optional[int] = None
    selected_ward_name: Optional[str] = None
    selected_horizon: int = 7
    freshness: ManagementFreshness
    overview_metrics: ManagementOverviewMetrics
    ward_occupancy_breakdown: List[WardCapacityResponse] = Field(default_factory=list)
    risk_summary: ManagementRiskSummary
    transfer_activity: ManagementTransferActivity
    data_quality: ManagementDataQualitySummary


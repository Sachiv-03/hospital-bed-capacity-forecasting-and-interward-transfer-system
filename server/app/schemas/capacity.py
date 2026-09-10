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

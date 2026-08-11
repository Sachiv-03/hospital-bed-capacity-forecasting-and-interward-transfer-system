from pydantic import BaseModel, Field


class CapacityStatusEnum:
    """Occupancy thresholds — easy to adjust later."""
    NORMAL = "NORMAL"        # < 70%
    MODERATE = "MODERATE"    # 70 – 84.99%
    HIGH = "HIGH"            # 85 – 94.99%
    CRITICAL = "CRITICAL"    # >= 95%


def get_capacity_status(occupancy_pct: float) -> str:
    """Return a textual occupancy status label from a percentage (0-100)."""
    if occupancy_pct >= 95:
        return CapacityStatusEnum.CRITICAL
    if occupancy_pct >= 85:
        return CapacityStatusEnum.HIGH
    if occupancy_pct >= 70:
        return CapacityStatusEnum.MODERATE
    return CapacityStatusEnum.NORMAL


class WardCapacityResponse(BaseModel):
    ward_id: int
    ward_name: str
    hospital_id: int
    total_beds: int = Field(default=0, description="Total beds in the ward")
    occupied_beds: int = Field(default=0)
    available_beds: int = Field(default=0)
    cleaning_beds: int = Field(default=0)
    reserved_beds: int = Field(default=0)
    maintenance_beds: int = Field(default=0)
    occupancy_percentage: float = Field(default=0.0)
    status: str = Field(default="NORMAL", description="NORMAL | MODERATE | HIGH | CRITICAL")


class HospitalCapacityResponse(BaseModel):
    hospital_id: int
    hospital_name: str
    total_wards: int = Field(default=0)
    total_beds: int = Field(default=0)
    occupied_beds: int = Field(default=0)
    available_beds: int = Field(default=0)
    cleaning_beds: int = Field(default=0)
    reserved_beds: int = Field(default=0)
    maintenance_beds: int = Field(default=0)
    occupancy_percentage: float = Field(default=0.0)
    status: str = Field(default="NORMAL", description="NORMAL | MODERATE | HIGH | CRITICAL")
    ward_capacities: list = Field(default_factory=list, description="Per-ward breakdown")

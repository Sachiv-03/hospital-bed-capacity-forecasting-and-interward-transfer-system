from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.transfer_recommendation import RecommendationStatus, RecommendationPriority


class RecommendationGenerateRequest(BaseModel):
    hospital_id: Optional[int] = None
    horizon_days: int = Field(default=1, ge=1, le=7)
    force_refresh: bool = False


class RecommendationGenerateResponse(BaseModel):
    hospital_id: int
    source_wards_analyzed: int
    destination_wards_analyzed: int
    recommendations_generated: int
    no_suitable_destination_count: int
    generated_at: datetime


class WardMinimalInfo(BaseModel):
    id: int
    name: str
    ward_type: str
    department: str
    capacity: int

    class Config:
        from_attributes = True


class RecommendationResponse(BaseModel):
    id: int
    hospital_id: int
    source_ward_id: int
    destination_ward_id: int
    source_ward: Optional[WardMinimalInfo] = None
    destination_ward: Optional[WardMinimalInfo] = None
    
    recommended_at: datetime
    source_current_occupancy: float
    source_predicted_occupancy: float
    destination_current_occupancy: float
    destination_predicted_occupancy: float
    
    available_beds: int
    safe_transfer_capacity: int
    recommended_transfer_count: int
    
    priority_score: float
    priority_level: RecommendationPriority
    status: RecommendationStatus
    
    reason: str
    warnings: Optional[List[str]] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    
    forecast_horizon_days: int
    forecast_confidence_lower: Optional[float] = None
    forecast_confidence_upper: Optional[float] = None
    
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    rejected_by_id: Optional[int] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecommendationDetailResponse(RecommendationResponse):
    rules_passed: List[str] = []
    rules_failed: List[str] = []
    revalidation_status: str = "VALID"


class RecommendationApproveRequest(BaseModel):
    notes: Optional[str] = None


class RecommendationRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, description="Mandatory reason for rejecting recommendation")


class TransferOverviewStatsResponse(BaseModel):
    hospital_id: int
    critical_pressure_wards: int
    high_pressure_wards: int
    total_potential_destinations: int
    pending_recommendations: int
    no_suitable_destination_wards: int
    updated_at: datetime


class AvailableBedSummary(BaseModel):
    id: int
    bed_number: str
    bed_type: str
    status: str

    class Config:
        from_attributes = True


class PatientDestinationRecommendationRequest(BaseModel):
    patient_id: Optional[int] = Field(None, description="ID of admitted patient to transfer")
    transfer_id: Optional[int] = Field(None, description="Existing transfer request ID to evaluate")
    admission_id: Optional[int] = Field(None, description="Active admission ID")
    source_ward_id: Optional[int] = Field(None, description="Source ward ID (inferred if patient_id provided)")
    required_bed_type: Optional[str] = Field(None, description="Required bed type compatibility (STANDARD, ICU, ISOLATION, EMERGENCY)")
    horizon_days: int = Field(default=1, ge=1, le=7)
    hospital_id: Optional[int] = Field(None, description="Hospital ID (enforced by JWT)")


class DestinationWardRecommendation(BaseModel):
    ward_id: int
    ward_name: str
    ward_type: str
    department: str
    floor: str
    capacity: int

    current_occupied_beds: int
    current_available_beds: int
    current_occupancy_percentage: float

    cleaning_beds: int = 0
    maintenance_beds: int = 0
    reserved_beds: int = 0
    pending_incoming_transfers: int = 0

    effective_capacity: int
    safe_transfer_capacity: int

    forecasted_occupied_beds: Optional[float] = None
    forecasted_occupancy_percentage: Optional[float] = None
    forecast_available_beds: Optional[float] = None
    forecast_target_date: Optional[str] = None
    forecast_risk_level: Optional[str] = None
    forecast_status: str = "VERIFIED"  # "VERIFIED", "UNAVAILABLE", "STALE"

    is_eligible: bool = True
    ineligibility_reasons: List[str] = []

    score: float
    rank: int
    priority_level: str
    reasons: List[str] = []
    warnings: List[str] = []
    score_breakdown: Dict[str, Any] = {}

    compatibility_allowed: bool = True
    compatibility_rule: Optional[str] = None
    available_candidate_beds: List[AvailableBedSummary] = []
    verification_required_statement: str = "Staff must physically verify bed readiness and clinically approve the transfer. Decision support only."


class PatientDestinationRecommendationResponse(BaseModel):
    hospital_id: int
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    patient_identifier: Optional[str] = None
    source_ward_id: int
    source_ward_name: str
    source_ward_type: str
    source_current_occupancy: float
    source_predicted_occupancy: Optional[float] = None
    required_bed_type: Optional[str] = None
    evaluated_at: datetime
    total_destination_wards_evaluated: int
    eligible_destinations_count: int
    recommendations: List[DestinationWardRecommendation]
    verification_required_statement: str = "Staff must physically verify bed readiness and clinically approve the transfer. Decision support only."


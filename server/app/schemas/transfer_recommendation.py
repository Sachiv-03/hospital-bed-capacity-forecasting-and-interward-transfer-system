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

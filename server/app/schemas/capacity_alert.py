from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TriggeredRuleSchema(BaseModel):
    rule_id: str = Field(..., description="Unique rule code (e.g. RULE_A_HIGH_FORECAST)")
    rule_name: str = Field(..., description="Human-readable rule name")
    severity: str = Field(..., description="Rule-specific severity (INFO, WARNING, HIGH, CRITICAL, INSUFFICIENT_DATA)")
    condition_met: str = Field(..., description="Condition statement that evaluated to true")
    trigger_value: float = Field(..., description="Observed or predicted value triggering the rule")
    threshold_value: float = Field(..., description="Configured threshold evaluated against")
    description: str = Field(..., description="Contextual explanation of what the rule indicates")


class ExplainableEvidenceSchema(BaseModel):
    hospital_id: int
    hospital_name: str
    ward_id: int
    ward_name: str
    ward_type: str
    ward_capacity: int
    current_occupied_beds: int
    current_available_beds: int
    current_occupancy_percentage: float
    forecast_target_date: str | None = None
    forecast_horizon_days: int = 7
    predicted_occupied_beds: float | None = None
    predicted_occupancy_percentage: float | None = None
    predicted_available_beds: float | None = None
    lower_bound_percentage: float | None = None
    upper_bound_percentage: float | None = None
    uncertainty_interval_width: float | None = None
    historical_trend_percentage_change: float | None = None
    historical_trend_days: int | None = None
    time_to_threshold_days: int | None = None
    time_to_threshold_date: str | None = None
    is_capacity_exceeded: bool = False
    data_quality_notes: list[str] = Field(default_factory=list)
    model_used: str = "SARIMA"
    evaluated_at: datetime


class CapacityAlertExplanationSchema(BaseModel):
    headline: str
    human_readable_explanation: str
    suggested_actions: list[str] = Field(default_factory=list)
    triggered_rules: list[TriggeredRuleSchema] = Field(default_factory=list)
    evidence: ExplainableEvidenceSchema


class CapacityAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hospital_id: int
    ward_id: int
    ward_name: str | None = None
    hospital_name: str | None = None
    alert_type: str
    severity: str
    message: str
    trigger_value: float
    threshold_value: float
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by_id: int | None = None
    acknowledged_by_name: str | None = None
    explanation: CapacityAlertExplanationSchema | None = None


class CapacityAlertListResponse(BaseModel):
    items: list[CapacityAlertResponse]
    total: int


class CapacityAlertDetailResponse(CapacityAlertResponse):
    pass


class AlertEvaluationResultItem(BaseModel):
    ward_id: int
    ward_name: str
    risk_level: str
    alerts_created_or_updated: int
    rules_triggered: list[str]
    has_alert: bool
    explanation: CapacityAlertExplanationSchema | None = None


class AlertEvaluationResponse(BaseModel):
    status: str
    hospital_id: int | None = None
    wards_evaluated: int
    alerts_count: int
    evaluated_at: datetime
    results: list[AlertEvaluationResultItem]


class CapacityAlertSummaryResponse(BaseModel):
    total_active: int
    critical_count: int
    high_count: int
    moderate_count: int
    unacknowledged_count: int
    data_quality_count: int
    resolved_count: int

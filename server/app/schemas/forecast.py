from typing import List, Optional
from pydantic import BaseModel, Field


class ForecastStatusEnum:
    SUCCESS = "SUCCESS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MODEL_ERROR = "MODEL_ERROR"


class ForecastItem(BaseModel):
    date: str = Field(description="Forecast date in ISO format YYYY-MM-DD")
    predicted_occupied_beds: float = Field(description="Predicted occupied bed count")
    predicted_occupancy_percentage: float = Field(description="Predicted occupancy percentage (0-100%)")
    lower_bound: Optional[float] = Field(None, description="Lower prediction bound percentage")
    upper_bound: Optional[float] = Field(None, description="Upper prediction bound percentage")
    lower_bound_beds: Optional[float] = Field(None, description="Lower prediction bound in beds")
    upper_bound_beds: Optional[float] = Field(None, description="Upper prediction bound in beds")
    risk_level: str = Field(default="NORMAL", description="Risk level: NORMAL | MODERATE | HIGH | CRITICAL")


class WardForecastResponse(BaseModel):
    ward_id: int
    ward_name: str
    hospital_id: int
    total_beds: int = 0
    current_occupied_beds: int = 0
    current_occupancy_percentage: float = 0.0
    horizon: int = 7
    model: str = "SARIMA"
    model_version: str = "1.0"
    generated_at: str
    status: str = "SUCCESS"
    message: Optional[str] = None
    required_observations: Optional[int] = None
    available_observations: Optional[int] = None
    forecasts: List[ForecastItem] = []
    max_predicted_occupancy: float = 0.0
    max_predicted_date: Optional[str] = None
    max_risk_level: str = "NORMAL"


class HospitalWardForecastSummary(BaseModel):
    ward_id: int
    ward_name: str
    total_beds: int
    current_occupancy_percentage: float
    tomorrow_occupancy_percentage: float
    max_7day_occupancy_percentage: float
    max_risk_level: str


class HospitalDailyForecast(BaseModel):
    date: str
    total_beds: int
    predicted_occupied_beds: float
    predicted_occupancy_percentage: float
    risk_level: str


class HospitalForecastResponse(BaseModel):
    hospital_id: int
    hospital_name: str
    total_beds: int = 0
    horizon: int = 7
    generated_at: str
    hospital_daily_forecasts: List[HospitalDailyForecast] = []
    ward_summaries: List[HospitalWardForecastSummary] = []


class ForecastHistoryItem(BaseModel):
    id: int
    hospital_id: int
    ward_id: int
    forecast_date: str
    generated_at: str
    horizon_days: int
    predicted_occupied_beds: float
    predicted_occupancy_percentage: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    risk_level: str
    model_name: str
    model_version: str


class ForecastHistoryResponse(BaseModel):
    items: List[ForecastHistoryItem]
    total: int
    page: int = 1
    limit: int = 50


class ModelPerformanceMetricItem(BaseModel):
    model_name: str
    model_version: str
    mae: float = Field(description="Mean Absolute Error in beds")
    rmse: float = Field(description="Root Mean Squared Error in beds")
    mape: Optional[float] = Field(None, description="Mean Absolute Percentage Error (%)")
    training_period_start: Optional[str] = None
    training_period_end: Optional[str] = None
    testing_period_start: Optional[str] = None
    testing_period_end: Optional[str] = None
    is_best_model: bool = False


class ModelPerformanceResponse(BaseModel):
    hospital_id: int
    ward_id: int
    ward_name: str
    evaluated_at: str
    baseline_model: ModelPerformanceMetricItem
    primary_model: ModelPerformanceMetricItem
    recommended_model: str


class ManualForecastGenerateResponse(BaseModel):
    status: str = "SUCCESS"
    hospitals_processed: int
    wards_processed: int
    forecasts_generated: int
    models_failed: int
    insufficient_data_count: int
    details: List[dict] = []

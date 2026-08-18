"""
Stage 3 Hospital Bed Capacity Forecasting Package.
Modular engine providing data preprocessing, baseline models, SARIMA time-series models,
model evaluation, risk classification, and DB persistence services.
"""
from app.services.forecasting.forecast_service import ForecastService

__all__ = ["ForecastService"]

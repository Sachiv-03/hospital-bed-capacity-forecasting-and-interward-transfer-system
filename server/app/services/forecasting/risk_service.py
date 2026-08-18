from app.core.config import settings
from app.models.bed_capacity_forecast import RiskLevel


class ForecastRiskService:
    """
    Classifies predicted occupancy percentage into future risk levels:
    - NORMAL: < 70%
    - MODERATE: 70% - 84.99%
    - HIGH: 85% - 94.99%
    - CRITICAL: >= 95%
    Uses configurable thresholds from settings.
    """

    @staticmethod
    def classify_risk(predicted_occupancy_percentage: float) -> str:
        pct = float(predicted_occupancy_percentage)
        if pct >= settings.FORECAST_HIGH_THRESHOLD:  # default 95.0
            return RiskLevel.CRITICAL.value
        if pct >= settings.FORECAST_MODERATE_THRESHOLD:  # default 85.0
            return RiskLevel.HIGH.value
        if pct >= settings.FORECAST_NORMAL_THRESHOLD:  # default 70.0
            return RiskLevel.MODERATE.value
        return RiskLevel.NORMAL.value

    @staticmethod
    def get_max_risk_level(risk_levels: list[str]) -> str:
        priority = {
            RiskLevel.CRITICAL.value: 4,
            RiskLevel.HIGH.value: 3,
            RiskLevel.MODERATE.value: 2,
            RiskLevel.NORMAL.value: 1,
        }
        max_level = RiskLevel.NORMAL.value
        max_val = 0
        for r in risk_levels:
            val = priority.get(r, 1)
            if val > max_val:
                max_val = val
                max_level = r
        return max_level

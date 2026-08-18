import logging
import math
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class TimeSeriesForecaster:
    """
    Primary Time-Series Forecasting Model (SARIMA / Exponential Smoothing).
    Features:
    - Uses statsmodels SARIMAX (order=(1,1,1), seasonal_order=(1,0,0,7)) when enough observations exist.
    - Robust fallback to Exponential Smoothing / Holt's linear trend model when data size is small.
    - Generates 1-day, 3-day, 7-day point predictions and 95% confidence intervals (lower/upper bounds).
    - Applies physical domain constraints: 0 <= predicted_occupied_beds <= total_beds.
    """

    @staticmethod
    def forecast_sarima(
        history: List[float],
        total_beds: int,
        horizon: int = 7,
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Fits SARIMA model on historical occupied beds series.
        Returns point predictions, lower bounds, upper bounds, and model metadata.
        """
        if not history:
            return TimeSeriesForecaster._fallback_forecast(history, total_beds, horizon)

        try:
            import numpy as np
            import pandas as pd
            from statsmodels.tsa.statespace.sarimax import SARIMAX

            series = pd.Series(history, dtype=float)

            # Heuristic parameter selection based on historical observations length
            n = len(series)
            if n >= 14:
                order = (1, 1, 1)
                seasonal_order = (1, 0, 0, 7)
            elif n >= 7:
                order = (1, 1, 0)
                seasonal_order = (0, 0, 0, 0)
            else:
                order = (1, 0, 0)
                seasonal_order = (0, 0, 0, 0)

            model = SARIMAX(
                series,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            res = model.fit(disp=False, maxiter=100)

            forecast_res = res.get_forecast(steps=horizon)
            mean_pred = forecast_res.predicted_mean.values
            conf_int = forecast_res.conf_int(alpha=1.0 - confidence_level).values

            point_preds = []
            lower_bounds = []
            upper_bounds = []

            for i in range(horizon):
                p = float(mean_pred[i]) if i < len(mean_pred) else float(history[-1])
                l = float(conf_int[i, 0]) if i < len(conf_int) else p * 0.9
                u = float(conf_int[i, 1]) if i < len(conf_int) else p * 1.1

                # Physical capacity constraints clipping
                p_clipped = max(0.0, min(p, float(total_beds)))
                l_clipped = max(0.0, min(l, float(total_beds)))
                u_clipped = max(0.0, min(u, float(total_beds)))

                # Ensure lower <= point <= upper
                l_final = min(l_clipped, p_clipped)
                u_final = max(u_clipped, p_clipped)

                point_preds.append(round(p_clipped, 2))
                lower_bounds.append(round(l_final, 2))
                upper_bounds.append(round(u_final, 2))

            return {
                "model_name": "SARIMA",
                "model_version": "1.0",
                "predictions": point_preds,
                "lower_bounds": lower_bounds,
                "upper_bounds": upper_bounds,
                "order": str(order),
                "seasonal_order": str(seasonal_order),
                "status": "SUCCESS",
            }

        except Exception as e:
            logger.warning(f"SARIMA fitting notice/fallback: {e}")
            return TimeSeriesForecaster._fallback_forecast(history, total_beds, horizon)

    @staticmethod
    def _fallback_forecast(
        history: List[float],
        total_beds: int,
        horizon: int = 7,
    ) -> Dict[str, Any]:
        """
        Holt-Winters / Exponential Smoothing fallback for short history or convergence edge cases.
        """
        if not history:
            mean_val = 0.0
        else:
            # Holt's double exponential smoothing or weighted mean
            alpha = 0.4
            mean_val = history[0]
            for v in history[1:]:
                mean_val = alpha * v + (1 - alpha) * mean_val

        last_val = history[-1] if history else mean_val
        trend = (last_val - history[0]) / len(history) if len(history) > 1 else 0.0
        trend = max(-0.5, min(trend, 0.5))  # damped trend

        point_preds = []
        lower_bounds = []
        upper_bounds = []

        std_dev = 1.5
        if len(history) > 2:
            avg = sum(history) / len(history)
            variance = sum((x - avg) ** 2 for x in history) / len(history)
            std_dev = max(0.5, math.sqrt(variance))

        for i in range(1, horizon + 1):
            p = last_val + (trend * i * 0.5)
            l = p - (1.96 * std_dev * math.sqrt(i * 0.5))
            u = p + (1.96 * std_dev * math.sqrt(i * 0.5))

            p_clipped = max(0.0, min(p, float(total_beds)))
            l_clipped = max(0.0, min(l, p_clipped))
            u_clipped = max(p_clipped, min(u, float(total_beds)))

            point_preds.append(round(p_clipped, 2))
            lower_bounds.append(round(l_clipped, 2))
            upper_bounds.append(round(u_clipped, 2))

        return {
            "model_name": "EXPONENTIAL_SMOOTHING",
            "model_version": "1.0",
            "predictions": point_preds,
            "lower_bounds": lower_bounds,
            "upper_bounds": upper_bounds,
            "status": "SUCCESS",
        }

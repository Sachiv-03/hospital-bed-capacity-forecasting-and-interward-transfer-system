from typing import List, Dict, Any, Tuple
from app.services.forecasting.evaluation import ModelEvaluator


class BaselineForecaster:
    """
    Simple Baseline Forecasting Models:
    1. Naive Forecast: prediction = last observed value
    2. Moving Average: prediction = rolling mean of recent K observations (default K=3 or K=7)
    Used to establish performance benchmark for time-series models.
    """

    @staticmethod
    def naive_forecast(history: List[float], horizon: int = 7) -> List[float]:
        if not history:
            return [0.0] * horizon
        last_val = history[-1]
        return [float(last_val)] * horizon

    @staticmethod
    def moving_average_forecast(history: List[float], horizon: int = 7, window: int = 7) -> List[float]:
        if not history:
            return [0.0] * horizon
        k = min(window, len(history))
        avg_val = sum(history[-k:]) / k
        return [float(avg_val)] * horizon

    @classmethod
    def evaluate_baseline(
        cls,
        train_vals: List[float],
        test_vals: List[float],
        train_dates: List[str],
        test_dates: List[str],
        window: int = 7,
    ) -> Dict[str, Any]:
        """
        Fits baseline moving average on train_vals and predicts over len(test_vals).
        Compares with actual test_vals to compute MAE, RMSE, MAPE.
        """
        if not test_vals:
            # If no test split available, evaluate baseline on last portion of train
            horizon = min(7, len(train_vals))
            test_vals = train_vals[-horizon:]
            history = train_vals[:-horizon] if len(train_vals) > horizon else train_vals
        else:
            history = train_vals

        horizon = len(test_vals)
        pred = cls.moving_average_forecast(history, horizon=horizon, window=window)

        t_start = train_dates[0] if train_dates else None
        t_end = train_dates[-1] if train_dates else None
        eval_start = test_dates[0] if test_dates else None
        eval_end = test_dates[-1] if test_dates else None

        metrics = ModelEvaluator.evaluate_model(
            actual=test_vals,
            predicted=pred,
            model_name="MOVING_AVERAGE_BASELINE",
            model_version="1.0",
            training_start=t_start,
            training_end=t_end,
            testing_start=eval_start,
            testing_end=eval_end,
        )
        metrics["predictions"] = pred
        return metrics

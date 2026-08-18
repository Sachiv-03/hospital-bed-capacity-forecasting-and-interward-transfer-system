import math
from typing import List, Dict, Any, Optional


class ModelEvaluator:
    """
    Computes time-series forecasting accuracy metrics:
    - MAE (Mean Absolute Error) in bed count
    - RMSE (Root Mean Squared Error) in bed count
    - MAPE (Mean Absolute Percentage Error) handling zero actual values safely
    """

    @staticmethod
    def calculate_mae(actual: List[float], predicted: List[float]) -> float:
        if not actual or len(actual) != len(predicted):
            return 0.0
        n = len(actual)
        mae = sum(abs(a - p) for a, p in zip(actual, predicted)) / n
        return round(float(mae), 4)

    @staticmethod
    def calculate_rmse(actual: List[float], predicted: List[float]) -> float:
        if not actual or len(actual) != len(predicted):
            return 0.0
        n = len(actual)
        mse = sum((a - p) ** 2 for a, p in zip(actual, predicted)) / n
        return round(float(math.sqrt(mse)), 4)

    @staticmethod
    def calculate_mape(actual: List[float], predicted: List[float]) -> Optional[float]:
        """
        Calculates MAPE safely. If actual values contain zeros or near-zero numbers,
        avoids division by zero by using standard epsilon or returning None.
        """
        if not actual or len(actual) != len(predicted):
            return None

        valid_pairs = [(a, p) for a, p in zip(actual, predicted) if abs(a) > 1e-5]
        if not valid_pairs:
            return None

        mape = (sum(abs((a - p) / a) for a, p in valid_pairs) / len(valid_pairs)) * 100.0
        return round(float(mape), 2)

    @classmethod
    def evaluate_model(
        cls,
        actual: List[float],
        predicted: List[float],
        model_name: str,
        model_version: str = "1.0",
        training_start: Optional[str] = None,
        training_end: Optional[str] = None,
        testing_start: Optional[str] = None,
        testing_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        mae = cls.calculate_mae(actual, predicted)
        rmse = cls.calculate_rmse(actual, predicted)
        mape = cls.calculate_mape(actual, predicted)

        return {
            "model_name": model_name,
            "model_version": model_version,
            "mae": mae,
            "rmse": rmse,
            "mape": mape,
            "training_period_start": training_start,
            "training_period_end": training_end,
            "testing_period_start": testing_start,
            "testing_period_end": testing_end,
            "is_best_model": False,
        }

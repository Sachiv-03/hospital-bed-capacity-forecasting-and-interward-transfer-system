import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from app.core.config import settings
from app.models.hospital import Hospital
from app.models.ward import Ward
from app.models.bed import Bed
from app.models.bed_capacity_forecast import BedCapacityForecast, RiskLevel
from app.services.forecasting.data_preparation import ForecastingDataPreparation
from app.services.forecasting.baseline_model import BaselineForecaster
from app.services.forecasting.time_series_model import TimeSeriesForecaster
from app.services.forecasting.evaluation import ModelEvaluator
from app.services.forecasting.risk_service import ForecastRiskService

logger = logging.getLogger(__name__)


class ForecastService:

    @classmethod
    def generate_ward_forecast(
        cls,
        db: Session,
        ward_id: int,
        hospital_id: Optional[int] = None,
        horizon: int = 7,
        save_to_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Orchestrates full forecasting pipeline for a single ward:
        1. Preprocess & validate historical data
        2. Check adequacy threshold
        3. Train & evaluate Baseline vs SARIMA
        4. Generate N-day forecast with confidence intervals
        5. Classify future capacity risk
        6. Persist to PostgreSQL if save_to_db is True
        """
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise ValueError(f"Ward with ID {ward_id} not found")

        # Multi-hospital tenant isolation check
        if hospital_id is not None and ward.hospital_id != hospital_id:
            raise PermissionError(f"Access to ward {ward_id} forecast is forbidden for hospital {hospital_id}")

        prep_data = ForecastingDataPreparation.prepare_ward_series(
            db=db,
            ward_id=ward_id,
            hospital_id=hospital_id,
        )

        total_obs = prep_data["total_observations"]
        total_beds = prep_data["total_beds"] or 1
        history = prep_data["occupied_beds"]
        dates = prep_data["dates"]

        # Current live occupancy state
        curr_occupied = db.query(Bed).filter(Bed.ward_id == ward_id, Bed.status == "OCCUPIED").count()
        curr_total = db.query(Bed).filter(Bed.ward_id == ward_id).count() or total_beds
        curr_pct = round((curr_occupied / curr_total) * 100.0, 2)

        min_obs_required = settings.FORECAST_MIN_OBSERVATIONS  # Default 7

        # Check for insufficient data
        if total_obs < min_obs_required:
            logger.info(f"INSUFFICIENT_DATA for ward {ward_id}: {total_obs}/{min_obs_required} observations")
            return {
                "ward_id": ward_id,
                "ward_name": ward.name,
                "hospital_id": ward.hospital_id,
                "total_beds": curr_total,
                "current_occupied_beds": curr_occupied,
                "current_occupancy_percentage": curr_pct,
                "horizon": horizon,
                "model": "NONE",
                "model_version": "1.0",
                "generated_at": datetime.utcnow().isoformat(),
                "status": "INSUFFICIENT_DATA",
                "message": f"Insufficient historical data for reliable forecasting. Required: {min_obs_required} days, Available: {total_obs} days.",
                "required_observations": min_obs_required,
                "available_observations": total_obs,
                "forecasts": [],
                "max_predicted_occupancy": 0.0,
                "max_predicted_date": None,
                "max_risk_level": "NORMAL",
            }

        # Train/Test Chronological Split for evaluation
        train_dates, train_vals, test_dates, test_vals = ForecastingDataPreparation.train_test_split(
            dates=dates,
            values=history,
            train_ratio=0.75,
        )

        # Baseline evaluation
        baseline_eval = BaselineForecaster.evaluate_baseline(
            train_vals=train_vals,
            test_vals=test_vals,
            train_dates=train_dates,
            test_dates=test_dates,
        )

        # Primary SARIMA forecasting
        ts_result = TimeSeriesForecaster.forecast_sarima(
            history=history,
            total_beds=curr_total,
            horizon=horizon,
        )

        predictions = ts_result["predictions"]
        lower_bounds = ts_result.get("lower_bounds", predictions)
        upper_bounds = ts_result.get("upper_bounds", predictions)
        model_name = ts_result["model_name"]
        model_version = ts_result["model_version"]

        gen_time = datetime.utcnow()
        start_date = dates[0] if dates else date.today().isoformat()
        last_hist_date = dates[-1] if dates else date.today().isoformat()
        last_d_obj = datetime.strptime(last_hist_date[:10], "%Y-%m-%d").date()

        forecast_items = []
        max_pct = 0.0
        max_date_str = None
        risk_levels = []

        db_records = []

        for i in range(horizon):
            f_date = last_d_obj + timedelta(days=i + 1)
            f_date_str = f_date.isoformat()

            pred_beds = predictions[i] if i < len(predictions) else predictions[-1]
            l_beds = lower_bounds[i] if i < len(lower_bounds) else pred_beds
            u_beds = upper_bounds[i] if i < len(upper_bounds) else pred_beds

            pred_pct = round((pred_beds / curr_total) * 100.0, 2) if curr_total > 0 else 0.0
            l_pct = round((l_beds / curr_total) * 100.0, 2) if curr_total > 0 else 0.0
            u_pct = round((u_beds / curr_total) * 100.0, 2) if curr_total > 0 else 0.0

            # Clip percentages to [0, 100]
            pred_pct = max(0.0, min(100.0, pred_pct))
            l_pct = max(0.0, min(100.0, l_pct))
            u_pct = max(100.0, max(l_pct, u_pct)) if u_pct > 100.0 else max(l_pct, u_pct)

            risk = ForecastRiskService.classify_risk(pred_pct)
            risk_levels.append(risk)

            if pred_pct > max_pct:
                max_pct = pred_pct
                max_date_str = f_date_str

            item = {
                "date": f_date_str,
                "predicted_occupied_beds": round(pred_beds, 1),
                "predicted_occupancy_percentage": pred_pct,
                "lower_bound": l_pct,
                "upper_bound": u_pct,
                "lower_bound_beds": round(l_beds, 1),
                "upper_bound_beds": round(u_beds, 1),
                "risk_level": risk,
            }
            forecast_items.append(item)

            if save_to_db:
                db_record = BedCapacityForecast(
                    hospital_id=ward.hospital_id,
                    ward_id=ward_id,
                    forecast_date=f_date,
                    generated_at=gen_time,
                    horizon_days=horizon,
                    predicted_occupied_beds=round(pred_beds, 1),
                    predicted_occupancy_percentage=pred_pct,
                    lower_bound=l_pct,
                    upper_bound=u_pct,
                    risk_level=risk,
                    model_name=model_name,
                    model_version=model_version,
                    training_data_start=datetime.strptime(start_date[:10], "%Y-%m-%d").date(),
                    training_data_end=last_d_obj,
                )
                db_records.append(db_record)

        if save_to_db and db_records:
            try:
                db.add_all(db_records)
                db.commit()
                logger.info(f"FORECAST_SAVED: {len(db_records)} records saved for ward {ward_id}")
            except Exception as e:
                db.rollback()
                logger.error(f"FORECAST_SAVE_ERROR for ward {ward_id}: {e}")

        max_risk = ForecastRiskService.get_max_risk_level(risk_levels)

        return {
            "ward_id": ward_id,
            "ward_name": ward.name,
            "hospital_id": ward.hospital_id,
            "total_beds": curr_total,
            "current_occupied_beds": curr_occupied,
            "current_occupancy_percentage": curr_pct,
            "horizon": horizon,
            "model": model_name,
            "model_version": model_version,
            "generated_at": gen_time.isoformat(),
            "status": "SUCCESS",
            "message": "Forecast generated successfully",
            "forecasts": forecast_items,
            "max_predicted_occupancy": max_pct,
            "max_predicted_date": max_date_str,
            "max_risk_level": max_risk,
        }

    @classmethod
    def get_ward_latest_forecast(
        cls,
        db: Session,
        ward_id: int,
        hospital_id: Optional[int] = None,
        horizon: int = 7,
    ) -> Dict[str, Any]:
        """
        Retrieves the latest generated forecast for a ward from DB, or generates one if missing.
        """
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise ValueError("Ward not found")

        if hospital_id is not None and ward.hospital_id != hospital_id:
            raise PermissionError("Access forbidden to this ward forecast")

        # Find latest generated_at timestamp for ward
        latest_stamp = (
            db.query(BedCapacityForecast.generated_at)
            .filter(BedCapacityForecast.ward_id == ward_id)
            .order_by(desc(BedCapacityForecast.generated_at))
            .first()
        )

        if not latest_stamp:
            # Generate fresh forecast
            return cls.generate_ward_forecast(db=db, ward_id=ward_id, hospital_id=hospital_id, horizon=horizon, save_to_db=True)

        gen_time = latest_stamp[0]
        records = (
            db.query(BedCapacityForecast)
            .filter(BedCapacityForecast.ward_id == ward_id, BedCapacityForecast.generated_at == gen_time)
            .order_by(BedCapacityForecast.forecast_date.asc())
            .limit(horizon)
            .all()
        )

        if not records:
            return cls.generate_ward_forecast(db=db, ward_id=ward_id, hospital_id=hospital_id, horizon=horizon, save_to_db=True)

        curr_occupied = db.query(Bed).filter(Bed.ward_id == ward_id, Bed.status == "OCCUPIED").count()
        curr_total = db.query(Bed).filter(Bed.ward_id == ward_id).count() or ward.capacity
        curr_pct = round((curr_occupied / curr_total) * 100.0, 2)

        forecast_items = []
        max_pct = 0.0
        max_date_str = None
        risk_levels = []

        for r in records:
            d_str = r.forecast_date.isoformat()
            pct = float(r.predicted_occupancy_percentage)
            risk_levels.append(r.risk_level)

            if pct > max_pct:
                max_pct = pct
                max_date_str = d_str

            forecast_items.append({
                "date": d_str,
                "predicted_occupied_beds": float(r.predicted_occupied_beds),
                "predicted_occupancy_percentage": pct,
                "lower_bound": float(r.lower_bound) if r.lower_bound is not None else pct,
                "upper_bound": float(r.upper_bound) if r.upper_bound is not None else pct,
                "lower_bound_beds": float(r.predicted_occupied_beds),
                "upper_bound_beds": float(r.predicted_occupied_beds),
                "risk_level": r.risk_level,
            })

        max_risk = ForecastRiskService.get_max_risk_level(risk_levels)

        return {
            "ward_id": ward_id,
            "ward_name": ward.name,
            "hospital_id": ward.hospital_id,
            "total_beds": curr_total,
            "current_occupied_beds": curr_occupied,
            "current_occupancy_percentage": curr_pct,
            "horizon": len(forecast_items),
            "model": records[0].model_name,
            "model_version": records[0].model_version,
            "generated_at": gen_time.isoformat(),
            "status": "SUCCESS",
            "forecasts": forecast_items,
            "max_predicted_occupancy": max_pct,
            "max_predicted_date": max_date_str,
            "max_risk_level": max_risk,
        }

    @classmethod
    def get_hospital_forecast(
        cls,
        db: Session,
        hospital_id: int,
        horizon: int = 7,
    ) -> Dict[str, Any]:
        """
        Aggregates ward-level forecasts into a weighted hospital-level forecast.
        Formula: total predicted occupied beds across all wards / total hospital beds * 100.
        """
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise ValueError(f"Hospital {hospital_id} not found")

        wards = db.query(Ward).filter(Ward.hospital_id == hospital_id, Ward.status == "ACTIVE").all()
        if not wards:
            return {
                "hospital_id": hospital_id,
                "hospital_name": hospital.name,
                "total_beds": 0,
                "horizon": horizon,
                "generated_at": datetime.utcnow().isoformat(),
                "hospital_daily_forecasts": [],
                "ward_summaries": [],
            }

        ward_forecasts = []
        ward_summaries = []

        total_hosp_beds = db.query(Bed).filter(Bed.hospital_id == hospital_id).count()
        if total_hosp_beds == 0:
            total_hosp_beds = sum(w.capacity for w in wards) or 1

        daily_beds_sum: Dict[str, float] = {}

        for w in wards:
            w_fc = cls.get_ward_latest_forecast(db=db, ward_id=w.id, hospital_id=hospital_id, horizon=horizon)
            ward_forecasts.append(w_fc)

            w_curr_pct = w_fc.get("current_occupancy_percentage", 0.0)
            f_list = w_fc.get("forecasts", [])

            tomorrow_pct = f_list[0]["predicted_occupancy_percentage"] if len(f_list) > 0 else w_curr_pct
            max_7d_pct = w_fc.get("max_predicted_occupancy", w_curr_pct)
            risk = w_fc.get("max_risk_level", "NORMAL")

            ward_summaries.append({
                "ward_id": w.id,
                "ward_name": w.name,
                "total_beds": w.capacity,
                "current_occupancy_percentage": w_curr_pct,
                "tomorrow_occupancy_percentage": tomorrow_pct,
                "max_7day_occupancy_percentage": max_7d_pct,
                "max_risk_level": risk,
            })

            for f_item in f_list:
                d = f_item["date"]
                p_beds = f_item["predicted_occupied_beds"]
                daily_beds_sum[d] = daily_beds_sum.get(d, 0.0) + p_beds

        hospital_daily = []
        for d in sorted(daily_beds_sum.keys()):
            tot_p_beds = daily_beds_sum[d]
            hosp_pct = round((tot_p_beds / total_hosp_beds) * 100.0, 2)
            hosp_risk = ForecastRiskService.classify_risk(hosp_pct)

            hospital_daily.append({
                "date": d,
                "total_beds": total_hosp_beds,
                "predicted_occupied_beds": round(tot_p_beds, 1),
                "predicted_occupancy_percentage": hosp_pct,
                "risk_level": hosp_risk,
            })

        gen_time = datetime.utcnow().isoformat()
        if ward_forecasts and ward_forecasts[0].get("generated_at"):
            gen_time = ward_forecasts[0]["generated_at"]

        return {
            "hospital_id": hospital_id,
            "hospital_name": hospital.name,
            "total_beds": total_hosp_beds,
            "horizon": horizon,
            "generated_at": gen_time,
            "hospital_daily_forecasts": hospital_daily,
            "ward_summaries": ward_summaries,
        }

    @classmethod
    def get_forecast_history(
        cls,
        db: Session,
        ward_id: int,
        hospital_id: Optional[int] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Retrieves historical forecast runs for a ward.
        """
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise ValueError("Ward not found")

        if hospital_id is not None and ward.hospital_id != hospital_id:
            raise PermissionError("Access forbidden to ward forecast history")

        query = db.query(BedCapacityForecast).filter(BedCapacityForecast.ward_id == ward_id)
        total = query.count()

        offset = (page - 1) * limit
        records = query.order_by(desc(BedCapacityForecast.generated_at), BedCapacityForecast.forecast_date.asc()).offset(offset).limit(limit).all()

        items = []
        for r in records:
            items.append({
                "id": r.id,
                "hospital_id": r.hospital_id,
                "ward_id": r.ward_id,
                "forecast_date": r.forecast_date.isoformat(),
                "generated_at": r.generated_at.isoformat(),
                "horizon_days": r.horizon_days,
                "predicted_occupied_beds": float(r.predicted_occupied_beds),
                "predicted_occupancy_percentage": float(r.predicted_occupancy_percentage),
                "lower_bound": float(r.lower_bound) if r.lower_bound is not None else None,
                "upper_bound": float(r.upper_bound) if r.upper_bound is not None else None,
                "risk_level": r.risk_level,
                "model_name": r.model_name,
                "model_version": r.model_version,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
        }

    @classmethod
    def get_model_performance(
        cls,
        db: Session,
        ward_id: int,
        hospital_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates and compares Baseline vs Primary SARIMA model performance metrics.
        """
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise ValueError("Ward not found")

        if hospital_id is not None and ward.hospital_id != hospital_id:
            raise PermissionError("Access forbidden to model performance metrics")

        prep_data = ForecastingDataPreparation.prepare_ward_series(db=db, ward_id=ward_id, hospital_id=hospital_id)
        history = prep_data["occupied_beds"]
        dates = prep_data["dates"]

        train_dates, train_vals, test_dates, test_vals = ForecastingDataPreparation.train_test_split(dates, history, train_ratio=0.75)

        # Baseline evaluation
        base_eval = BaselineForecaster.evaluate_baseline(train_vals, test_vals, train_dates, test_dates)

        # Primary model evaluation
        if test_vals and train_vals:
            ts_res = TimeSeriesForecaster.forecast_sarima(history=train_vals, total_beds=ward.capacity, horizon=len(test_vals))
            pred_vals = ts_res["predictions"]
            prim_eval = ModelEvaluator.evaluate_model(
                actual=test_vals,
                predicted=pred_vals,
                model_name=ts_res["model_name"],
                model_version=ts_res["model_version"],
                training_start=train_dates[0] if train_dates else None,
                training_end=train_dates[-1] if train_dates else None,
                testing_start=test_dates[0] if test_dates else None,
                testing_end=test_dates[-1] if test_dates else None,
            )
        else:
            prim_eval = {
                "model_name": "SARIMA",
                "model_version": "1.0",
                "mae": base_eval["mae"],
                "rmse": base_eval["rmse"],
                "mape": base_eval["mape"],
                "training_period_start": None,
                "training_period_end": None,
                "testing_period_start": None,
                "testing_period_end": None,
            }

        rec_model = "SARIMA" if prim_eval["mae"] <= base_eval["mae"] else "MOVING_AVERAGE_BASELINE"
        base_eval["is_best_model"] = (rec_model == "MOVING_AVERAGE_BASELINE")
        prim_eval["is_best_model"] = (rec_model == "SARIMA")

        return {
            "hospital_id": ward.hospital_id,
            "ward_id": ward_id,
            "ward_name": ward.name,
            "evaluated_at": datetime.utcnow().isoformat(),
            "baseline_model": base_eval,
            "primary_model": prim_eval,
            "recommended_model": rec_model,
        }

    @classmethod
    def generate_all_forecasts(
        cls,
        db: Session,
        hospital_id: Optional[int] = None,
        horizon: int = 7,
    ) -> Dict[str, Any]:
        """
        Admin/Trigger endpoint to process and generate forecasts for all wards across hospitals.
        """
        query = db.query(Ward).filter(Ward.status == "ACTIVE")
        if hospital_id is not None:
            query = query.filter(Ward.hospital_id == hospital_id)

        wards = query.all()
        hospitals_seen = set()

        forecasts_gen = 0
        models_failed = 0
        insufficient_data_cnt = 0
        details = []

        for w in wards:
            hospitals_seen.add(w.hospital_id)
            try:
                res = cls.generate_ward_forecast(db=db, ward_id=w.id, hospital_id=w.hospital_id, horizon=horizon, save_to_db=True)
                if res["status"] == "INSUFFICIENT_DATA":
                    insufficient_data_cnt += 1
                else:
                    forecasts_gen += len(res.get("forecasts", []))
                details.append({"ward_id": w.id, "ward_name": w.name, "status": res["status"]})
            except Exception as e:
                models_failed += 1
                logger.error(f"Failed to generate forecast for ward {w.id}: {e}")
                details.append({"ward_id": w.id, "ward_name": w.name, "status": "FAILED", "error": str(e)})

        return {
            "status": "SUCCESS",
            "hospitals_processed": len(hospitals_seen),
            "wards_processed": len(wards),
            "forecasts_generated": forecasts_gen,
            "models_failed": models_failed,
            "insufficient_data_count": insufficient_data_cnt,
            "details": details,
        }

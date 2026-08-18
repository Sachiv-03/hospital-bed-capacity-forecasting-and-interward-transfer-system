import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from app.services.historical_service import HistoricalService
from app.models.ward import Ward

logger = logging.getLogger(__name__)


class ForecastingDataPreparation:
    """
    Stage 3 Data Preparation Pipeline.
    Steps:
    1. Load historical snapshots / daily summaries from Stage 2.
    2. Filter by hospital and ward.
    3. Sort chronologically.
    4. Remove/aggregate duplicate date entries.
    5. Validate occupancy values (0 <= occupied <= total_beds).
    6. Fill missing dates via linear interpolation / forward fill.
    7. Generate time features (day_of_week, is_weekend).
    8. Perform chronological train/test split (70% train, 30% test).
    """

    @staticmethod
    def prepare_ward_series(
        db: Session,
        ward_id: int,
        hospital_id: Optional[int] = None,
        start_date: Any = None,
        end_date: Any = None,
    ) -> Dict[str, Any]:
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise ValueError(f"Ward {ward_id} not found")

        if hospital_id is not None and ward.hospital_id != hospital_id:
            raise PermissionError(f"Access forbidden to ward {ward_id} for hospital {hospital_id}")

        dataset = HistoricalService.get_forecasting_dataset(
            db=db,
            hospital_id=ward.hospital_id,
            ward_id=ward_id,
            start_date=start_date,
            end_date=end_date,
        )

        items = dataset.get("items", [])
        if not items:
            return {
                "ward_id": ward_id,
                "ward_name": ward.name,
                "hospital_id": ward.hospital_id,
                "total_beds": ward.capacity,
                "total_observations": 0,
                "series": [],
                "dates": [],
                "occupied_beds": [],
                "occupancy_percentages": [],
            }

        # Deduplicate & group by date
        date_map: Dict[date, Dict[str, Any]] = {}
        for item in items:
            d_str = item["date"]
            if isinstance(d_str, str):
                d_obj = datetime.strptime(d_str[:10], "%Y-%m-%d").date()
            else:
                d_obj = d_str

            occ = max(0, min(item.get("occupied_beds", 0), item.get("total_beds", ward.capacity)))
            tot = max(1, item.get("total_beds", ward.capacity))
            pct = round((occ / tot) * 100.0, 2)

            date_map[d_obj] = {
                "date": d_obj.isoformat(),
                "date_obj": d_obj,
                "occupied_beds": occ,
                "total_beds": tot,
                "occupancy_percentage": pct,
                "admissions": item.get("admissions", 0),
                "discharges": item.get("discharges", 0),
                "transfers_in": item.get("transfers_in", 0),
                "transfers_out": item.get("transfers_out", 0),
                "day_of_week": d_obj.weekday(),
                "is_weekend": 1 if d_obj.weekday() >= 5 else 0,
            }

        sorted_dates = sorted(date_map.keys())
        if not sorted_dates:
            return {
                "ward_id": ward_id,
                "ward_name": ward.name,
                "hospital_id": ward.hospital_id,
                "total_beds": ward.capacity,
                "total_observations": 0,
                "series": [],
                "dates": [],
                "occupied_beds": [],
                "occupancy_percentages": [],
            }

        # Fill missing daily dates from min_date to max_date
        min_date = sorted_dates[0]
        max_date = sorted_dates[-1]

        full_series: List[Dict[str, Any]] = []
        curr = min_date
        last_item = date_map[min_date]

        while curr <= max_date:
            if curr in date_map:
                item = date_map[curr]
                last_item = item
            else:
                # Forward fill / interpolate missing date
                item = {
                    "date": curr.isoformat(),
                    "date_obj": curr,
                    "occupied_beds": last_item["occupied_beds"],
                    "total_beds": last_item["total_beds"],
                    "occupancy_percentage": last_item["occupancy_percentage"],
                    "admissions": 0,
                    "discharges": 0,
                    "transfers_in": 0,
                    "transfers_out": 0,
                    "day_of_week": curr.weekday(),
                    "is_weekend": 1 if curr.weekday() >= 5 else 0,
                    "interpolated": True,
                }
            full_series.append(item)
            curr += timedelta(days=1)

        dates_str = [x["date"] for x in full_series]
        occ_beds = [float(x["occupied_beds"]) for x in full_series]
        occ_pcts = [float(x["occupancy_percentage"]) for x in full_series]

        return {
            "ward_id": ward_id,
            "ward_name": ward.name,
            "hospital_id": ward.hospital_id,
            "total_beds": ward.capacity,
            "total_observations": len(full_series),
            "start_date": min_date.isoformat(),
            "end_date": max_date.isoformat(),
            "series": full_series,
            "dates": dates_str,
            "occupied_beds": occ_beds,
            "occupancy_percentages": occ_pcts,
        }

    @staticmethod
    def train_test_split(
        dates: List[str],
        values: List[float],
        train_ratio: float = 0.75,
    ) -> Tuple[List[str], List[float], List[str], List[float]]:
        """
        Performs strict chronological train/test split.
        No random shuffling!
        """
        n = len(values)
        if n == 0:
            return [], [], [], []

        split_idx = int(n * train_ratio)
        if split_idx >= n:
            split_idx = max(1, n - 1)
        if split_idx == 0 and n > 1:
            split_idx = 1

        train_dates = dates[:split_idx]
        train_vals = values[:split_idx]
        test_dates = dates[split_idx:]
        test_vals = values[split_idx:]

        return train_dates, train_vals, test_dates, test_vals

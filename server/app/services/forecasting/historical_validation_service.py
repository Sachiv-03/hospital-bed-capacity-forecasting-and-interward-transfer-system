"""
Phase 8 — Historical Daily Occupancy Validation and Preparation Service

Provides robust data quality validation, duplicate classification, missing-date
detection, and clean daily time-series preparation for SARIMA forecasting.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import cast, Date

from app.models.hospital import Hospital, HospitalStatus
from app.models.ward import Ward, WardStatus
from app.models.occupancy_snapshot import OccupancySnapshot

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    VALID = "VALID"
    DUPLICATE = "DUPLICATE"
    MISSING_DATE = "MISSING_DATE"
    INVALID_OCCUPANCY = "INVALID_OCCUPANCY"
    INVALID_CAPACITY = "INVALID_CAPACITY"
    UNKNOWN_HOSPITAL = "UNKNOWN_HOSPITAL"
    UNKNOWN_WARD = "UNKNOWN_WARD"
    CAPACITY_VIOLATION = "CAPACITY_VIOLATION"
    CONFLICTING_RECORD = "CONFLICTING_RECORD"


def parse_observation_date(val: Any) -> Tuple[Optional[date], Optional[str]]:
    """
    Parses an observation date into a standard python date object.
    Returns (date_obj, error_message).
    """
    if val is None:
        return None, "Observation date is missing or null"

    if isinstance(val, date) and not isinstance(val, datetime):
        return val, None

    if isinstance(val, datetime):
        return val.date(), None

    if isinstance(val, str):
        val_clean = val.strip()
        if not val_clean:
            return None, "Observation date is empty"

        # Try ISO format
        try:
            return datetime.fromisoformat(val_clean.replace("Z", "+00:00")).date(), None
        except Exception:
            pass

        # Try YYYY-MM-DD
        try:
            return datetime.strptime(val_clean[:10], "%Y-%m-%d").date(), None
        except Exception:
            pass

        return None, f"Observation date '{val}' is malformed or invalid"

    return None, f"Unsupported date type: {type(val).__name__}"


class HistoricalDataValidationService:
    """
    Validates, deduplicates, and prepares daily historical occupancy datasets.
    """

    @staticmethod
    def validate_daily_record(
        db: Session,
        record: Dict[str, Any],
        hospitals_cache: Optional[Dict[int, Hospital]] = None,
        wards_cache: Optional[Dict[int, Ward]] = None,
    ) -> Dict[str, Any]:
        """
        Validates a single daily occupancy observation record against core hospital domain rules.
        """
        hospital_id = record.get("hospital_id")
        ward_id = record.get("ward_id")
        raw_date = record.get("date") or record.get("observation_date") or record.get("snapshot_time")
        occupied_beds = record.get("occupied_beds")
        capacity = record["capacity"] if "capacity" in record else record.get("total_beds")
        data_source = record.get("data_source", "HOSPITAL_API")

        # 1. Date validation
        obs_date, date_err = parse_observation_date(raw_date)
        if date_err or obs_date is None:
            return {
                "status": ValidationStatus.MISSING_DATE.value if not raw_date else "INVALID_DATE",
                "is_valid": False,
                "error": date_err,
                "record": record,
            }

        # 2. Hospital exists
        if hospital_id is None:
            return {
                "status": ValidationStatus.UNKNOWN_HOSPITAL.value,
                "is_valid": False,
                "error": "Hospital ID is required",
                "record": record,
            }

        hospital = (
            hospitals_cache.get(hospital_id)
            if hospitals_cache is not None
            else db.query(Hospital).filter(Hospital.id == hospital_id).first()
        )
        if not hospital:
            return {
                "status": ValidationStatus.UNKNOWN_HOSPITAL.value,
                "is_valid": False,
                "error": f"Hospital ID {hospital_id} does not exist",
                "record": record,
            }

        # 3. Ward exists
        if ward_id is None:
            return {
                "status": ValidationStatus.UNKNOWN_WARD.value,
                "is_valid": False,
                "error": "Ward ID is required",
                "record": record,
            }

        ward = (
            wards_cache.get(ward_id)
            if wards_cache is not None
            else db.query(Ward).filter(Ward.id == ward_id).first()
        )
        if not ward:
            return {
                "status": ValidationStatus.UNKNOWN_WARD.value,
                "is_valid": False,
                "error": f"Ward ID {ward_id} does not exist",
                "record": record,
            }

        # 4. Ward belongs to correct hospital
        if ward.hospital_id != hospital_id:
            return {
                "status": ValidationStatus.UNKNOWN_WARD.value,
                "is_valid": False,
                "error": f"Ward ID {ward_id} belongs to hospital {ward.hospital_id}, not {hospital_id}",
                "record": record,
            }

        # 5. Occupied beds numeric and non-negative
        if occupied_beds is None:
            return {
                "status": ValidationStatus.INVALID_OCCUPANCY.value,
                "is_valid": False,
                "error": "Occupied beds count is missing",
                "record": record,
            }

        try:
            occ_num = float(occupied_beds)
            if occ_num < 0:
                return {
                    "status": ValidationStatus.INVALID_OCCUPANCY.value,
                    "is_valid": False,
                    "error": f"Occupied beds cannot be negative: {occ_num}",
                    "record": record,
                }
        except (ValueError, TypeError):
            return {
                "status": ValidationStatus.INVALID_OCCUPANCY.value,
                "is_valid": False,
                "error": f"Occupied beds count is not numeric: {occupied_beds}",
                "record": record,
            }

        # 6. Capacity numeric and > 0
        if capacity is None:
            cap_num = float(ward.capacity) if ward.capacity else 1.0
        else:
            try:
                cap_num = float(capacity)
                if cap_num <= 0:
                    return {
                        "status": ValidationStatus.INVALID_CAPACITY.value,
                        "is_valid": False,
                        "error": f"Capacity must be strictly greater than zero: {cap_num}",
                        "record": record,
                    }
            except (ValueError, TypeError):
                return {
                    "status": ValidationStatus.INVALID_CAPACITY.value,
                    "is_valid": False,
                    "error": f"Capacity is not numeric: {capacity}",
                    "record": record,
                }

        # 7. Occupied beds vs Capacity
        is_over_capacity = occ_num > cap_num
        validation_status = (
            ValidationStatus.CAPACITY_VIOLATION.value
            if is_over_capacity
            else ValidationStatus.VALID.value
        )

        available_beds = max(0.0, cap_num - occ_num)
        occupancy_rate = round((occ_num / cap_num) * 100.0, 2)

        return {
            "status": validation_status,
            "is_valid": True,  # Record itself is structurally valid and accepted into dataset
            "hospital_id": hospital_id,
            "ward_id": ward_id,
            "date": obs_date,
            "date_str": obs_date.isoformat(),
            "occupied_beds": occ_num,
            "capacity": cap_num,
            "available_beds": available_beds,
            "occupancy_rate": occupancy_rate,
            "is_over_capacity": is_over_capacity,
            "data_source": data_source,
            "record": record,
        }

    @classmethod
    def process_and_deduplicate_observations(
        cls,
        db: Session,
        raw_records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Validates a collection of daily records, applies idempotent deduplication
        and conflict detection without silently overwriting conflicting records.
        """
        valid_records: Dict[Tuple[int, int, date], Dict[str, Any]] = {}
        exact_duplicates: List[Dict[str, Any]] = []
        conflicting_records: List[Dict[str, Any]] = []
        invalid_records: List[Dict[str, Any]] = []

        # Cache hospitals and wards to avoid repeated DB lookups
        hospitals_cache = {h.id: h for h in db.query(Hospital).all()}
        wards_cache = {w.id: w for w in db.query(Ward).all()}

        for raw_item in raw_records:
            val_res = cls.validate_daily_record(
                db=db,
                record=raw_item,
                hospitals_cache=hospitals_cache,
                wards_cache=wards_cache,
            )

            if not val_res["is_valid"]:
                invalid_records.append(val_res)
                continue

            key = (val_res["hospital_id"], val_res["ward_id"], val_res["date"])

            if key in valid_records:
                existing = valid_records[key]
                # Compare occupancy and capacity
                if (
                    abs(existing["occupied_beds"] - val_res["occupied_beds"]) < 1e-4
                    and abs(existing["capacity"] - val_res["capacity"]) < 1e-4
                ):
                    # Exact duplicate -> idempotent ignore
                    exact_duplicates.append({
                        "key": (key[0], key[1], key[2].isoformat()),
                        "status": ValidationStatus.DUPLICATE.value,
                        "record": raw_item,
                    })
                else:
                    # Conflicting duplicate -> do NOT overwrite existing record, report conflict
                    conflicting_records.append({
                        "key": (key[0], key[1], key[2].isoformat()),
                        "status": ValidationStatus.CONFLICTING_RECORD.value,
                        "existing_occupied": existing["occupied_beds"],
                        "existing_capacity": existing["capacity"],
                        "conflicting_occupied": val_res["occupied_beds"],
                        "conflicting_capacity": val_res["capacity"],
                        "record": raw_item,
                    })
            else:
                valid_records[key] = val_res

        return {
            "valid_records": list(valid_records.values()),
            "exact_duplicates": exact_duplicates,
            "conflicting_records": conflicting_records,
            "invalid_records": invalid_records,
            "total_processed": len(raw_records),
            "valid_count": len(valid_records),
            "duplicate_count": len(exact_duplicates),
            "conflict_count": len(conflicting_records),
            "invalid_count": len(invalid_records),
        }

    @classmethod
    def prepare_daily_time_series(
        cls,
        db: Session,
        hospital_id: int,
        ward_id: int,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Extracts, validates, detects missing dates, and prepares a clean,
        chronological daily series for a specific ward.
        """
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise ValueError(f"Ward {ward_id} not found")

        if ward.hospital_id != hospital_id:
            raise PermissionError(f"Ward {ward_id} does not belong to hospital {hospital_id}")

        st_d, _ = parse_observation_date(start_date)
        end_d, _ = parse_observation_date(end_date)

        # Query database snapshots
        query = db.query(OccupancySnapshot).filter(
            OccupancySnapshot.hospital_id == hospital_id,
            OccupancySnapshot.ward_id == ward_id,
        )

        if st_d:
            query = query.filter(cast(OccupancySnapshot.snapshot_time, Date) >= st_d)
        if end_d:
            query = query.filter(cast(OccupancySnapshot.snapshot_time, Date) <= end_d)

        snapshots = query.order_by(OccupancySnapshot.snapshot_time.asc()).all()

        if not snapshots:
            return {
                "hospital_id": hospital_id,
                "ward_id": ward_id,
                "ward_name": ward.name,
                "total_observations": 0,
                "clean_series": [],
                "dates": [],
                "occupied_beds": [],
                "capacities": [],
                "missing_dates": [],
                "imputed_count": 0,
                "start_date": None,
                "end_date": None,
                "data_frequency": "DAILY",
            }

        # Group by date to handle possible multiple snapshots on same date
        daily_map: Dict[date, List[OccupancySnapshot]] = {}
        for s in snapshots:
            d = s.snapshot_time.date()
            if d not in daily_map:
                daily_map[d] = []
            daily_map[d].append(s)

        sorted_observed_dates = sorted(daily_map.keys())
        min_date = sorted_observed_dates[0]
        max_date = sorted_observed_dates[-1]

        # Collapse each observed date using validated domain rules
        observed_day_records: Dict[date, Dict[str, Any]] = {}
        for d in sorted_observed_dates:
            snaps = daily_map[d]
            latest_snap = snaps[-1]

            # Use latest snapshot's total_beds (preserves historical capacity)
            hist_capacity = float(latest_snap.total_beds if latest_snap.total_beds > 0 else (ward.capacity or 1))
            hist_occupied = float(latest_snap.occupied_beds)

            # Available beds and occupancy rate
            avail = max(0.0, hist_capacity - hist_occupied)
            occ_pct = round((hist_occupied / hist_capacity) * 100.0, 2)

            observed_day_records[d] = {
                "date": d,
                "date_str": d.isoformat(),
                "hospital_id": hospital_id,
                "ward_id": ward_id,
                "occupied_beds": hist_occupied,
                "capacity": hist_capacity,
                "available_beds": avail,
                "occupancy_percentage": occ_pct,
                "is_imputed": False,
                "imputation_method": "NONE",
                "data_source": latest_snap.data_source or "HOSPITAL_API",
                "day_of_week": d.weekday(),
                "is_weekend": 1 if d.weekday() >= 5 else 0,
            }

        # Chronological series assembly & Missing Date Detection
        clean_series: List[Dict[str, Any]] = []
        missing_dates: List[str] = []
        imputed_count = 0

        curr_d = min_date
        last_observed = observed_day_records[min_date]

        while curr_d <= max_date:
            if curr_d in observed_day_records:
                item = observed_day_records[curr_d]
                last_observed = item
                clean_series.append(item)
            else:
                # Missing date detected!
                missing_dates.append(curr_d.isoformat())
                imputed_count += 1

                # Forward-fill from preceding observation (prevents future leakage)
                imputed_item = {
                    "date": curr_d,
                    "date_str": curr_d.isoformat(),
                    "hospital_id": hospital_id,
                    "ward_id": ward_id,
                    "occupied_beds": last_observed["occupied_beds"],
                    "capacity": last_observed["capacity"],  # Preserves prevailing historical capacity
                    "available_beds": last_observed["available_beds"],
                    "occupancy_percentage": last_observed["occupancy_percentage"],
                    "is_imputed": True,
                    "imputation_method": "FORWARD_FILL",
                    "data_source": last_observed["data_source"],
                    "day_of_week": curr_d.weekday(),
                    "is_weekend": 1 if curr_d.weekday() >= 5 else 0,
                }
                clean_series.append(imputed_item)

            curr_d += timedelta(days=1)

        dates_list = [x["date_str"] for x in clean_series]
        occupied_list = [x["occupied_beds"] for x in clean_series]
        capacities_list = [x["capacity"] for x in clean_series]

        return {
            "hospital_id": hospital_id,
            "ward_id": ward_id,
            "ward_name": ward.name,
            "total_observations": len(clean_series),
            "observed_count": len(observed_day_records),
            "clean_series": clean_series,
            "dates": dates_list,
            "occupied_beds": occupied_list,
            "capacities": capacities_list,
            "missing_dates": missing_dates,
            "imputed_count": imputed_count,
            "start_date": min_date.isoformat(),
            "end_date": max_date.isoformat(),
            "data_frequency": "DAILY",
        }

    @classmethod
    def get_comprehensive_quality_report(
        cls,
        db: Session,
        hospital_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generates an extensive data quality report across hospitals/wards,
        including missing date counts, date ranges, and frequency metadata.
        """
        # Base query for snapshots
        snap_query = db.query(OccupancySnapshot)
        if hospital_id is not None:
            snap_query = snap_query.filter(OccupancySnapshot.hospital_id == hospital_id)

        all_snaps = snap_query.order_by(OccupancySnapshot.snapshot_time.asc()).all()
        total_snaps = len(all_snaps)

        if total_snaps == 0:
            return {
                "total_observations": 0,
                "valid_observations": 0,
                "duplicate_observations": 0,
                "missing_dates": 0,
                "invalid_observations": 0,
                "conflicting_observations": 0,
                "number_of_hospitals": 1 if hospital_id else db.query(Hospital).count(),
                "number_of_wards": db.query(Ward).filter(Ward.hospital_id == hospital_id).count() if hospital_id else db.query(Ward).count(),
                "earliest_observation_date": None,
                "latest_observation_date": None,
                "data_frequency": "DAILY",
                "missing_date_list": [],
                "health_score": 100.0,
                "last_successful_snapshot": None,
            }

        # Track hospitals and wards
        seen_hospitals = set()
        seen_wards = set()
        earliest_date = date.max
        latest_date = date.min

        # Group by (hospital, ward, date)
        ward_day_snaps: Dict[Tuple[int, int], Set[date]] = {}
        invalid_obs_count = 0
        duplicate_obs_count = 0

        for s in all_snaps:
            seen_hospitals.add(s.hospital_id)
            seen_wards.add(s.ward_id)
            d = s.snapshot_time.date()
            earliest_date = min(earliest_date, d)
            latest_date = max(latest_date, d)

            # Check validity
            if s.occupied_beds < 0 or s.total_beds <= 0:
                invalid_obs_count += 1

            key = (s.hospital_id, s.ward_id)
            if key not in ward_day_snaps:
                ward_day_snaps[key] = set()

            if d in ward_day_snaps[key]:
                duplicate_obs_count += 1
            else:
                ward_day_snaps[key].add(d)

        # Detect missing dates per ward across their range
        all_missing_dates: List[str] = []
        for (h_id, w_id), observed_dates in ward_day_snaps.items():
            if not observed_dates:
                continue
            w_min = min(observed_dates)
            w_max = max(observed_dates)
            curr = w_min
            while curr <= w_max:
                if curr not in observed_dates:
                    all_missing_dates.append(f"H{h_id}-W{w_id}:{curr.isoformat()}")
                curr += timedelta(days=1)

        valid_obs_count = max(0, total_snaps - invalid_obs_count - duplicate_obs_count)

        last_snap = all_snaps[-1] if all_snaps else None
        last_snap_str = last_snap.snapshot_time.isoformat() if last_snap else None

        flaws = invalid_obs_count + duplicate_obs_count + len(all_missing_dates)
        health_score = max(0.0, round(100.0 - (flaws / total_snaps * 100.0), 2)) if total_snaps > 0 else 100.0

        return {
            "total_observations": total_snaps,
            "valid_observations": valid_obs_count,
            "duplicate_observations": duplicate_obs_count,
            "missing_dates": len(all_missing_dates),
            "invalid_observations": invalid_obs_count,
            "conflicting_observations": 0,
            "number_of_hospitals": len(seen_hospitals),
            "number_of_wards": len(seen_wards),
            "earliest_observation_date": earliest_date.isoformat() if earliest_date != date.max else None,
            "latest_observation_date": latest_date.isoformat() if latest_date != date.min else None,
            "data_frequency": "DAILY",
            "missing_date_list": all_missing_dates[:50],  # sample preview
            "health_score": health_score,
            "last_successful_snapshot": last_snap_str,
        }

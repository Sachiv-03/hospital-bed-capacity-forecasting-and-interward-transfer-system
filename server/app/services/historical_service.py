import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import func, cast, Date, and_
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.models.ward import Ward
from app.models.bed import Bed
from app.models.occupancy_event import OccupancyEvent, EventType
from app.models.occupancy_snapshot import OccupancySnapshot
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except Exception:
            return None
    return None


def _parse_datetime(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


class HistoricalService:

    @staticmethod
    def get_ward_snapshot_history(
        db: Session,
        ward_id: int,
        hospital_id: Optional[int] = None,
        start_date: Any = None,
        end_date: Any = None,
        limit: int = 200,
    ) -> List[OccupancySnapshot]:
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")

        # Hospital isolation check
        if hospital_id is not None and ward.hospital_id != hospital_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this ward's history is forbidden")

        st_dt = _parse_datetime(start_date)
        end_dt = _parse_datetime(end_date)

        query = db.query(OccupancySnapshot).filter(OccupancySnapshot.ward_id == ward_id)

        if st_dt:
            query = query.filter(OccupancySnapshot.snapshot_time >= st_dt)
        if end_dt:
            query = query.filter(OccupancySnapshot.snapshot_time <= end_dt)

        return query.order_by(OccupancySnapshot.snapshot_time.asc()).limit(limit).all()


    @staticmethod
    def get_hospital_snapshot_history(
        db: Session,
        hospital_id: int,
        start_date: Any = None,
        end_date: Any = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

        st_dt = _parse_datetime(start_date)
        end_dt = _parse_datetime(end_date)

        query = db.query(
            OccupancySnapshot.snapshot_time,
            func.sum(OccupancySnapshot.total_beds).label("total_beds"),
            func.sum(OccupancySnapshot.occupied_beds).label("occupied_beds"),
            func.sum(OccupancySnapshot.available_beds).label("available_beds"),
            func.sum(OccupancySnapshot.cleaning_beds).label("cleaning_beds"),
            func.sum(OccupancySnapshot.reserved_beds).label("reserved_beds"),
            func.sum(OccupancySnapshot.maintenance_beds).label("maintenance_beds"),
        ).filter(OccupancySnapshot.hospital_id == hospital_id)

        if st_dt:
            query = query.filter(OccupancySnapshot.snapshot_time >= st_dt)
        if end_dt:
            query = query.filter(OccupancySnapshot.snapshot_time <= end_dt)

        results = (
            query.group_by(OccupancySnapshot.snapshot_time)
            .order_by(OccupancySnapshot.snapshot_time.asc())
            .limit(limit)
            .all()
        )

        items = []
        for r in results:
            t_beds = r.total_beds or 0
            o_beds = r.occupied_beds or 0
            pct = round((o_beds / t_beds * 100.0), 2) if t_beds > 0 else 0.0
            items.append({
                "timestamp": r.snapshot_time.isoformat() if isinstance(r.snapshot_time, datetime) else str(r.snapshot_time),
                "hospital_id": hospital_id,
                "hospital_name": hospital.name,
                "total_beds": t_beds,
                "occupied_beds": o_beds,
                "available_beds": r.available_beds or 0,
                "cleaning_beds": r.cleaning_beds or 0,
                "reserved_beds": r.reserved_beds or 0,
                "maintenance_beds": r.maintenance_beds or 0,
                "occupancy_percentage": pct,
            })
        return items

    @staticmethod
    def get_daily_summary(
        db: Session,
        ward_id: int,
        hospital_id: Optional[int] = None,
        start_date: Any = None,
        end_date: Any = None,
    ) -> List[Dict[str, Any]]:
        ward = db.query(Ward).filter(Ward.id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")

        if hospital_id is not None and ward.hospital_id != hospital_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to ward daily summary is forbidden")

        st_d = _parse_date(start_date)
        end_d = _parse_date(end_date)

        # Query snapshots for ward
        snap_query = db.query(OccupancySnapshot).filter(OccupancySnapshot.ward_id == ward_id)

        snapshots = snap_query.order_by(OccupancySnapshot.snapshot_time.asc()).all()

        # Group snapshots by date in Python (dialect-agnostic)
        daily_snaps: Dict[date, List[OccupancySnapshot]] = {}
        for s in snapshots:
            d = s.snapshot_time.date()
            if st_d and d < st_d:
                continue
            if end_d and d > end_d:
                continue
            if d not in daily_snaps:
                daily_snaps[d] = []
            daily_snaps[d].append(s)

        # If no snapshots exist yet, fallback to today's current capacity
        summaries = []
        if not daily_snaps:
            bed_query = db.query(Bed).filter(Bed.ward_id == ward_id)
            total = bed_query.count()
            occ = bed_query.filter(Bed.status == "OCCUPIED").count()
            pct = round((occ / total * 100.0), 2) if total > 0 else 0.0

            today = date.today()
            t_start = datetime(today.year, today.month, today.day, 0, 0, 0)
            t_end = datetime(today.year, today.month, today.day, 23, 59, 59)

            adm = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == ward_id, OccupancyEvent.event_type == "ADMISSION", OccupancyEvent.event_time >= t_start, OccupancyEvent.event_time <= t_end).count()
            dis = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == ward_id, OccupancyEvent.event_type == "DISCHARGE", OccupancyEvent.event_time >= t_start, OccupancyEvent.event_time <= t_end).count()
            t_in = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == ward_id, OccupancyEvent.event_type == "TRANSFER_IN", OccupancyEvent.event_time >= t_start, OccupancyEvent.event_time <= t_end).count()
            t_out = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == ward_id, OccupancyEvent.event_type == "TRANSFER_OUT", OccupancyEvent.event_time >= t_start, OccupancyEvent.event_time <= t_end).count()

            summaries.append({
                "date": today.isoformat(),
                "hospital_id": ward.hospital_id,
                "ward_id": ward_id,
                "ward_name": ward.name,
                "average_occupancy": pct,
                "maximum_occupancy": pct,
                "minimum_occupancy": pct,
                "admissions": adm,
                "discharges": dis,
                "transfers_in": t_in,
                "transfers_out": t_out,
            })
            return summaries

        for curr_date in sorted(daily_snaps.keys()):
            snaps = daily_snaps[curr_date]
            occ_list = [s.occupancy_percentage for s in snaps]
            avg_occ = round(sum(occ_list) / len(occ_list), 2)
            max_occ = round(max(occ_list), 2)
            min_occ = round(min(occ_list), 2)

            t_start = datetime(curr_date.year, curr_date.month, curr_date.day, 0, 0, 0)
            t_end = datetime(curr_date.year, curr_date.month, curr_date.day, 23, 59, 59)

            adm = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == ward_id, OccupancyEvent.event_type == "ADMISSION", OccupancyEvent.event_time >= t_start, OccupancyEvent.event_time <= t_end).count()
            dis = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == ward_id, OccupancyEvent.event_type == "DISCHARGE", OccupancyEvent.event_time >= t_start, OccupancyEvent.event_time <= t_end).count()
            t_in = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == ward_id, OccupancyEvent.event_type == "TRANSFER_IN", OccupancyEvent.event_time >= t_start, OccupancyEvent.event_time <= t_end).count()
            t_out = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == ward_id, OccupancyEvent.event_type == "TRANSFER_OUT", OccupancyEvent.event_time >= t_start, OccupancyEvent.event_time <= t_end).count()

            summaries.append({
                "date": curr_date.isoformat(),
                "hospital_id": ward.hospital_id,
                "ward_id": ward_id,
                "ward_name": ward.name,
                "average_occupancy": avg_occ,
                "maximum_occupancy": max_occ,
                "minimum_occupancy": min_occ,
                "admissions": adm,
                "discharges": dis,
                "transfers_in": t_in,
                "transfers_out": t_out,
            })
        return summaries


    @staticmethod
    def get_data_quality_report(db: Session, hospital_id: Optional[int] = None) -> Dict[str, Any]:
        query_snaps = db.query(OccupancySnapshot)
        query_events = db.query(OccupancyEvent)

        if hospital_id is not None:
            query_snaps = query_snaps.filter(OccupancySnapshot.hospital_id == hospital_id)
            query_events = query_events.filter(OccupancyEvent.hospital_id == hospital_id)

        total_snaps = query_snaps.count()

        # Audit checks
        invalid_snaps = query_snaps.filter(
            (OccupancySnapshot.occupied_beds > OccupancySnapshot.total_beds) |
            (OccupancySnapshot.available_beds < 0) |
            (OccupancySnapshot.occupancy_percentage < 0) |
            (OccupancySnapshot.occupancy_percentage > 100.0)
        ).count()

        # Duplicate timestamps for same (hospital, ward)
        dup_subq = (
            db.query(
                OccupancySnapshot.hospital_id,
                OccupancySnapshot.ward_id,
                OccupancySnapshot.snapshot_time,
                func.count(OccupancySnapshot.id).label("cnt")
            )
            .group_by(OccupancySnapshot.hospital_id, OccupancySnapshot.ward_id, OccupancySnapshot.snapshot_time)
            .having(func.count(OccupancySnapshot.id) > 1)
        )
        if hospital_id is not None:
            dup_subq = dup_subq.filter(OccupancySnapshot.hospital_id == hospital_id)
        duplicate_snaps = dup_subq.count()

        # Invalid events (missing bed or ward reference)
        invalid_events = 0
        all_events = query_events.all()
        for ev in all_events:
            if not ev.bed_id or not ev.ward_id or not ev.hospital_id:
                invalid_events += 1

        last_snap = query_snaps.order_by(OccupancySnapshot.snapshot_time.desc()).first()
        last_time_str = last_snap.snapshot_time.isoformat() if last_snap else None

        health_score = 100.0
        if total_snaps > 0:
            flaws = invalid_snaps + duplicate_snaps + invalid_events
            health_score = max(0.0, round(100.0 - (flaws / total_snaps * 100.0), 2))

        return {
            "total_snapshots": total_snaps,
            "invalid_snapshots": invalid_snaps,
            "duplicate_snapshots": duplicate_snaps,
            "invalid_events": invalid_events,
            "missing_data_count": 0,
            "last_successful_snapshot": last_time_str,
            "health_score": health_score,
        }

    @staticmethod
    def get_forecasting_dataset(
        db: Session,
        hospital_id: Optional[int] = None,
        ward_id: Optional[int] = None,
        start_date: Any = None,
        end_date: Any = None,
    ) -> Dict[str, Any]:
        """
        Prepares a clean, chronologically sorted, daily normalized dataset
        specifically structured for future Stage 3 machine learning forecasting models.
        """
        query = db.query(OccupancySnapshot)

        if hospital_id is not None:
            query = query.filter(OccupancySnapshot.hospital_id == hospital_id)
        if ward_id is not None:
            query = query.filter(OccupancySnapshot.ward_id == ward_id)

        st_d = _parse_date(start_date)
        end_d = _parse_date(end_date)

        if st_d:
            query = query.filter(cast(OccupancySnapshot.snapshot_time, Date) >= st_d)
        if end_d:
            query = query.filter(cast(OccupancySnapshot.snapshot_time, Date) <= end_d)

        snapshots = query.order_by(OccupancySnapshot.snapshot_time.asc()).all()

        # Group by ward and date
        daily_groups: Dict[tuple, List[OccupancySnapshot]] = {}
        for s in snapshots:
            d = s.snapshot_time.date()
            key = (s.hospital_id, s.ward_id, d)
            if key not in daily_groups:
                daily_groups[key] = []
            daily_groups[key].append(s)

        dataset_items = []
        for (h_id, w_id, d), snaps in sorted(daily_groups.items(), key=lambda x: x[0][2]):
            ward = db.query(Ward).filter(Ward.id == w_id).first()
            w_name = ward.name if ward else f"Ward-{w_id}"

            avg_occ = sum(s.occupancy_percentage for s in snaps) / len(snaps)
            latest_snap = snaps[-1]

            adm = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == w_id, OccupancyEvent.event_type == "ADMISSION", cast(OccupancyEvent.event_time, Date) == d).count()
            dis = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == w_id, OccupancyEvent.event_type == "DISCHARGE", cast(OccupancyEvent.event_time, Date) == d).count()
            t_in = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == w_id, OccupancyEvent.event_type == "TRANSFER_IN", cast(OccupancyEvent.event_time, Date) == d).count()
            t_out = db.query(OccupancyEvent).filter(OccupancyEvent.ward_id == w_id, OccupancyEvent.event_type == "TRANSFER_OUT", cast(OccupancyEvent.event_time, Date) == d).count()

            dataset_items.append({
                "date": d.isoformat(),
                "hospital_id": h_id,
                "ward_id": w_id,
                "ward_name": w_name,
                "total_beds": latest_snap.total_beds,
                "occupied_beds": latest_snap.occupied_beds,
                "available_beds": latest_snap.available_beds,
                "occupancy_percentage": round(avg_occ, 2),
                "admissions": adm,
                "discharges": dis,
                "transfers_in": t_in,
                "transfers_out": t_out,
                "day_of_week": d.weekday(),  # 0=Monday, 6=Sunday
            })

        min_d_str = st_d.isoformat() if st_d else (dataset_items[0]["date"] if dataset_items else date.today().isoformat())
        max_d_str = end_d.isoformat() if end_d else (dataset_items[-1]["date"] if dataset_items else date.today().isoformat())

        return {
            "items": dataset_items,
            "total_records": len(dataset_items),
            "start_date": min_d_str,
            "end_date": max_d_str,
            "missing_periods_reported": 0,
        }


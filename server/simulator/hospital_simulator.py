"""
Hospital Simulator — generates fictional hospital occupancy events and sends them
to the FastAPI ingestion pipeline.

This simulator has two modes:
  MODE 1 — MANUAL:    Call generate_single_event() to fire one event.
  MODE 2 — AUTOMATIC: Call run_automatic() to loop at SIMULATOR_INTERVAL_SECONDS.

Configuration (server/.env):
  SIMULATOR_ENABLED=true
  SIMULATOR_INTERVAL_SECONDS=10
  SIMULATOR_HOSPITAL_ID=1

Usage (from server/ directory):
  python -m simulator.hospital_simulator            # automatic loop
  python -m simulator.hospital_simulator --once     # single event
  python -m simulator.hospital_simulator --seed     # seed data then exit
"""
import argparse
import logging
import random
import string
import sys
import os
import time
from datetime import datetime

import requests

# Allow running from server/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.database.database import SessionLocal
from app.models.bed import Bed, BedStatus
from app.models.ward import Ward, WardStatus

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIMULATOR] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("simulator")

# ── Constants ─────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000/api/v1"
INGESTION_URL = f"{API_BASE}/ingestion/events"

# Maps current bed status → what events could realistically happen next
STATUS_TO_EVENTS = {
    BedStatus.AVAILABLE.value:    ["ADMISSION", "BED_CLEANING", "BED_MAINTENANCE", "BED_RESERVED"],
    BedStatus.OCCUPIED.value:     ["DISCHARGE", "TRANSFER_OUT", "BED_CLEANING"],
    BedStatus.CLEANING.value:     ["BED_AVAILABLE"],
    BedStatus.MAINTENANCE.value:  ["BED_AVAILABLE"],
    BedStatus.RESERVED.value:     ["BED_RELEASED", "TRANSFER_IN"],
}

# Weights: make common events more likely
EVENT_WEIGHTS = {
    "ADMISSION":    10,
    "DISCHARGE":    8,
    "TRANSFER_OUT": 3,
    "TRANSFER_IN":  3,
    "BED_CLEANING": 4,
    "BED_AVAILABLE": 4,
    "BED_MAINTENANCE": 1,
    "BED_RESERVED": 2,
    "BED_RELEASED": 2,
}

_event_counter = 0


def _generate_event_id() -> str:
    global _event_counter
    _event_counter += 1
    date_str = datetime.utcnow().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.digits, k=4))
    return f"SIM-{date_str}-{str(_event_counter).zfill(6)}-{suffix}"


def _get_eligible_beds(db, hospital_id: int):
    """Fetch all beds from active wards for the configured hospital."""
    active_ward_ids = [
        w.id for w in db.query(Ward).filter(
            Ward.hospital_id == hospital_id,
            Ward.status == WardStatus.ACTIVE.value,
        ).all()
    ]
    if not active_ward_ids:
        logger.warning(f"No active wards found for hospital_id={hospital_id}")
        return []
    return db.query(Bed).filter(Bed.ward_id.in_(active_ward_ids)).all()


def _pick_event_for_bed(bed: Bed) -> str:
    """Choose a realistic next event for a bed based on its current status."""
    possible = STATUS_TO_EVENTS.get(bed.status, [])
    if not possible:
        return None
    weights = [EVENT_WEIGHTS.get(e, 1) for e in possible]
    return random.choices(possible, weights=weights, k=1)[0]


def _get_auth_token() -> str:
    """
    Returns a JWT token for the simulator.
    The simulator uses a local service account (admin) for authentication.
    Set SIMULATOR_EMAIL and SIMULATOR_PASSWORD in .env, or use the defaults.
    """
    email = os.getenv("SIMULATOR_EMAIL", "simulator@system.local")
    password = os.getenv("SIMULATOR_PASSWORD", "SimulatorPass123!")
    try:
        resp = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": email, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token", "")
        else:
            logger.error(f"Auth failed: {resp.status_code} — {resp.text}")
            return ""
    except Exception as e:
        logger.error(f"Auth request error: {e}")
        return ""


def generate_single_event(hospital_id: int, token: str) -> dict:
    """
    Pick a random eligible bed, choose a realistic event, send it to the API.
    Returns the API response dict.
    """
    db = SessionLocal()
    try:
        beds = _get_eligible_beds(db, hospital_id)
        if not beds:
            logger.warning("No beds found — has the seed data been applied?")
            return {"status": "no_beds"}

        # Pick a random bed
        bed = random.choice(beds)
        event_type = _pick_event_for_bed(bed)
        if not event_type:
            logger.warning(f"No valid event for bed {bed.bed_number} status={bed.status}")
            return {"status": "skipped"}

        event_id = _generate_event_id()
        payload = {
            "event_id": event_id,
            "hospital_id": hospital_id,
            "ward_id": bed.ward_id,
            "bed_id": bed.id,
            "event_type": event_type,
            "event_time": datetime.utcnow().isoformat(),
            "source": "SIMULATOR",
        }

        logger.info(
            f"GENERATING EVENT | event_id={event_id} "
            f"type={event_type} bed={bed.bed_number} "
            f"ward_id={bed.ward_id} current_status={bed.status}"
        )

    finally:
        db.close()

    # POST the event to the ingestion API
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.post(INGESTION_URL, json=payload, headers=headers, timeout=10)
        result = resp.json()
        if resp.status_code == 200:
            status = result.get("status", "unknown")
            if status == "success":
                logger.info(
                    f"EVENT ACCEPTED  | event_id={event_id} "
                    f"bed={result.get('bed_number')} "
                    f"{result.get('previous_status')} → {result.get('new_status')}"
                )
            elif status == "duplicate":
                logger.warning(f"EVENT DUPLICATE | event_id={event_id}")
            return result
        else:
            logger.error(f"EVENT REJECTED  | event_id={event_id} HTTP={resp.status_code} detail={resp.text}")
            return {"status": "error", "detail": resp.text}
    except Exception as e:
        logger.error(f"Request error for event_id={event_id}: {e}")
        return {"status": "error", "detail": str(e)}


def run_automatic():
    """
    Automatic mode — generate events at SIMULATOR_INTERVAL_SECONDS intervals.
    Runs until the process is stopped (Ctrl+C).
    Refreshes the auth token every 20 minutes.
    """
    if not settings.SIMULATOR_ENABLED:
        logger.error("SIMULATOR_ENABLED=false. Set SIMULATOR_ENABLED=true in .env to run.")
        sys.exit(1)

    hospital_id = settings.SIMULATOR_HOSPITAL_ID
    interval = settings.SIMULATOR_INTERVAL_SECONDS

    logger.info("=" * 60)
    logger.info("HOSPITAL SIMULATOR — AUTOMATIC MODE")
    logger.info(f"  Hospital ID : {hospital_id}")
    logger.info(f"  Interval    : {interval}s")
    logger.info(f"  Target API  : {INGESTION_URL}")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to stop.")

    token = _get_auth_token()
    if not token:
        logger.error("Could not obtain auth token. Is the backend running and a simulator user created?")
        logger.error("Create a user: POST /api/v1/auth/register with email=simulator@system.local")
        sys.exit(1)

    last_token_refresh = time.time()
    TOKEN_REFRESH_INTERVAL = 1200  # 20 minutes

    try:
        while True:
            # Refresh token periodically
            if time.time() - last_token_refresh > TOKEN_REFRESH_INTERVAL:
                token = _get_auth_token()
                last_token_refresh = time.time()

            generate_single_event(hospital_id, token)
            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Simulator stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hospital Bed Capacity Simulator")
    parser.add_argument("--once", action="store_true", help="Generate a single event and exit")
    parser.add_argument("--seed", action="store_true", help="Run seed data and exit")
    args = parser.parse_args()

    if args.seed:
        from simulator.seed_data import seed
        seed()
        sys.exit(0)

    if args.once:
        token = _get_auth_token()
        if not token:
            logger.error("Could not get auth token. Is FastAPI running?")
            sys.exit(1)
        result = generate_single_event(settings.SIMULATOR_HOSPITAL_ID, token)
        print(result)
        sys.exit(0)

    run_automatic()

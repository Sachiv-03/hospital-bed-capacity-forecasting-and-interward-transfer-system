import logging
import threading
import time
from typing import Optional

from app.core.config import settings
from app.database.session import SessionLocal
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)


class SnapshotScheduler:
    _instance: Optional["SnapshotScheduler"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @classmethod
    def get_instance(cls) -> "SnapshotScheduler":
        with cls._lock:
            if cls._instance is None:
                cls._instance = SnapshotScheduler()
            return cls._instance

    def _run_loop(self):
        logger.info(
            f"SNAPSHOT SCHEDULER STARTED | Interval={settings.SNAPSHOT_INTERVAL_SECONDS}s "
            f"Enabled={settings.SNAPSHOT_ENABLED}"
        )
        last_forecast_time = 0.0
        while not self._stop_event.is_set():
            now = time.time()
            if settings.SNAPSHOT_ENABLED:
                db = SessionLocal()
                try:
                    SnapshotService.generate_snapshots_for_all_hospitals(db)
                except Exception as e:
                    logger.error(f"Snapshot scheduler execution error: {e}")
                finally:
                    db.close()

            # Run forecasting periodic job
            if settings.FORECAST_ENABLED and (now - last_forecast_time >= settings.FORECAST_INTERVAL_SECONDS):
                db = SessionLocal()
                try:
                    from app.services.forecasting.forecast_service import ForecastService
                    ForecastService.generate_all_forecasts(db=db, horizon=7)
                    last_forecast_time = now
                    logger.info("FORECAST SCHEDULER: Successfully generated 7-day capacity forecasts.")
                except Exception as e:
                    logger.error(f"Forecast scheduler execution error: {e}")
                finally:
                    db.close()

            # Wait for interval or stop event
            self._stop_event.wait(timeout=settings.SNAPSHOT_INTERVAL_SECONDS)


        logger.info("SNAPSHOT SCHEDULER STOPPED cleanly.")

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("Scheduler already running — skipping duplicate start.")
                return

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SnapshotSchedulerThread")
            self._thread.start()

    def stop(self):
        with self._lock:
            if self._thread is not None:
                self._stop_event.set()
                self._thread.join(timeout=5.0)
                self._thread = None


scheduler = SnapshotScheduler.get_instance()

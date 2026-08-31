import logging
import signal
import sys
import time

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.database import SessionLocal
from app.services.job_scheduler import JobScheduler

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("app.scheduler")

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info(f"Received signal {signum}. Initiating graceful scheduler shutdown...")
    running = False


def run_scheduler_loop(scan_interval_seconds: float = 60.0):
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(f"Job Scheduler process started. Scanning every {scan_interval_seconds}s...")
    scheduler = JobScheduler(worker_id="standalone-scheduler")

    while running:
        db = SessionLocal()
        try:
            results = scheduler.trigger_periodic_scans(db)
            logger.info(f"Triggered periodic scan batch: {results}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Scheduler loop encountered an error: {e}")
        finally:
            db.close()

        # Sleep in small increments to respond quickly to shutdown signals
        sleep_elapsed = 0.0
        while running and sleep_elapsed < scan_interval_seconds:
            time.sleep(0.5)
            sleep_elapsed += 0.5

    logger.info("Scheduler process terminated gracefully.")


if __name__ == "__main__":
    scan_sec = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    run_scheduler_loop(scan_interval_seconds=scan_sec)

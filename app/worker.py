import logging
import signal
import sys
import time

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.database import SessionLocal
from app.domain.jobs.job_scheduler import JobScheduler
from app.domain.jobs.outbox_service import OutboxService

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("app.worker")

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info(f"Received signal {signum}. Initiating graceful worker shutdown...")
    running = False


def run_worker_loop(poll_interval_seconds: float = 2.0, batch_size: int = 10):
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(f"Background Job Worker started. Polling every {poll_interval_seconds}s (batch: {batch_size})...")
    scheduler = JobScheduler(worker_id="standalone-worker")

    while running:
        db = SessionLocal()
        try:
            processed = scheduler.run_worker_batch(db, limit=batch_size)
            if processed > 0:
                logger.info(f"Processed {processed} background job(s).")

            outbox_svc = OutboxService(db)
            outbox_count = outbox_svc.process_outbox_batch(limit=batch_size)
            if outbox_count > 0:
                logger.info(f"Dispatched {outbox_count} outbox event(s).")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Worker loop encountered an error: {e}")
        finally:
            db.close()

        # Update heartbeat file for container healthcheck
        try:
            import json
            import os
            import tempfile
            from datetime import UTC, datetime
            from pathlib import Path

            hb_path = Path(tempfile.gettempdir()) / "lcc_worker_heartbeat.json"
            hb_path.write_text(
                json.dumps({
                    "status": "HEALTHY",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "pid": os.getpid(),
                })
            )
        except Exception:  # noqa: BLE001
            pass

        # Sleep in small increments to respond quickly to shutdown signals
        sleep_elapsed = 0.0
        while running and sleep_elapsed < poll_interval_seconds:
            time.sleep(0.2)
            sleep_elapsed += 0.2

    logger.info("Worker process terminated gracefully.")


if __name__ == "__main__":
    poll_sec = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    run_worker_loop(poll_interval_seconds=poll_sec)

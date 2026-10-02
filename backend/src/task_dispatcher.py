"""Dispatch tracked scrape jobs to Celery, with a local-thread fallback."""

from __future__ import annotations

import threading

from config.settings import SCRAPING_LOG_DIR
from src.database import SessionLocal
from src.job_runner import run_scrape_job
from src.job_service import mark_job_failed
from utils.logger import get_logger

logger = get_logger(__name__, SCRAPING_LOG_DIR)


def dispatch_scrape_job(job_id: str, *, trigger_source: str = "manual") -> dict:
    try:
        from src.celery_worker import scrape_new_ads_task

        async_result = scrape_new_ads_task.apply_async(
            kwargs={"job_id": job_id, "trigger_source": trigger_source}
        )
        return {
            "worker": "celery",
            "task_id": async_result.id,
        }
    except Exception as exc:
        logger.warning(
            "Could not enqueue scrape job via Celery, falling back to local thread: %s",
            exc,
        )

        def _target() -> None:
            try:
                run_scrape_job(job_id, trigger_source=trigger_source, worker_type="thread")
            except Exception:
                pass

        try:
            thread = threading.Thread(target=_target, daemon=True)
            thread.start()
            return {
                "worker": "thread",
                "task_id": None,
            }
        except Exception as thread_exc:
            db = SessionLocal()
            try:
                mark_job_failed(
                    db,
                    job_id,
                    error_message=f"Could not dispatch scrape job: {thread_exc}",
                )
            finally:
                db.close()
            raise

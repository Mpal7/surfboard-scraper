"""Manual refresh orchestration: cooldown, job creation and dispatch."""

from __future__ import annotations

import os
import time

from config.settings import COOLDOWN_FILE, REFRESH_COOLDOWN_SECONDS
from src.job_service import create_job, get_job
from src.task_dispatcher import dispatch_scrape_job


def get_last_refresh_time() -> float:
    if not os.path.exists(COOLDOWN_FILE):
        return 0
    with open(COOLDOWN_FILE, "r", encoding="utf-8") as file_handle:
        try:
            return float(file_handle.read().strip())
        except (ValueError, TypeError):
            return 0


def set_last_refresh_time(timestamp: float) -> None:
    with open(COOLDOWN_FILE, "w", encoding="utf-8") as file_handle:
        file_handle.write(str(timestamp))


def refresh_allowed(now: float | None = None) -> tuple[bool, float]:
    current_time = now if now is not None else time.time()
    last_refresh_time = get_last_refresh_time()
    remaining = REFRESH_COOLDOWN_SECONDS - (current_time - last_refresh_time)
    return remaining <= 0, max(0.0, remaining)


def schedule_manual_refresh(db, *, now: float | None = None) -> dict:
    current_time = now if now is not None else time.time()
    allowed, remaining = refresh_allowed(now=current_time)
    if not allowed:
        return {
            "scheduled": False,
            "retry_after_seconds": int(remaining),
            "message": f"Refresh allowed only every {REFRESH_COOLDOWN_SECONDS // 60} minutes.",
        }

    set_last_refresh_time(current_time)
    job = create_job(db, job_type="scrape", trigger_source="manual")
    dispatch = dispatch_scrape_job(job.id, trigger_source="manual")
    refreshed_job = get_job(db, job.id)
    return {
        "scheduled": True,
        "message": "Refresh scheduled.",
        "job_id": job.id,
        "status": refreshed_job.status if refreshed_job else "queued",
        "worker": dispatch["worker"],
        "task_id": dispatch["task_id"],
        "status_url": f"/jobs/{job.id}",
    }

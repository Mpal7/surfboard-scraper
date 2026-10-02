"""Job lifecycle persistence for tracked background runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config.settings import JOB_RESULT_PREVIEW_LIMIT
from src.models import JobRun


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_job(
    db: Session,
    *,
    job_type: str,
    trigger_source: str,
    status: str = "queued",
) -> JobRun:
    job = JobRun(
        job_type=job_type,
        trigger_source=trigger_source,
        status=status,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> JobRun | None:
    return db.query(JobRun).filter(JobRun.id == job_id).first()


def list_jobs(db: Session, *, job_type: str | None = None, limit: int = 20) -> list[JobRun]:
    query = db.query(JobRun)
    if job_type:
        query = query.filter(JobRun.job_type == job_type)
    return query.order_by(JobRun.created_at.desc()).limit(limit).all()


def mark_job_running(
    db: Session,
    job_id: str,
    *,
    worker_type: str,
    celery_task_id: str | None = None,
) -> JobRun | None:
    job = get_job(db, job_id)
    if not job:
        return None
    job.status = "running"
    job.worker_type = worker_type
    if celery_task_id:
        job.celery_task_id = celery_task_id
    job.started_at = utcnow()
    db.commit()
    db.refresh(job)
    return job


def mark_job_completed(db: Session, job_id: str, *, result_payload: dict) -> JobRun | None:
    job = get_job(db, job_id)
    if not job:
        return None
    job.status = "completed"
    job.finished_at = utcnow()
    job.result_json = json.dumps(trim_result_payload(result_payload))
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job


def mark_job_failed(
    db: Session,
    job_id: str,
    *,
    error_message: str,
    result_payload: dict | None = None,
) -> JobRun | None:
    job = get_job(db, job_id)
    if not job:
        return None
    job.status = "failed"
    job.finished_at = utcnow()
    job.error_message = error_message
    if result_payload is not None:
        job.result_json = json.dumps(trim_result_payload(result_payload))
    db.commit()
    db.refresh(job)
    return job


def trim_result_payload(payload: dict) -> dict:
    trimmed = dict(payload)
    added_links = trimmed.get("added_links") or []
    if len(added_links) > JOB_RESULT_PREVIEW_LIMIT:
        trimmed["added_links"] = added_links[:JOB_RESULT_PREVIEW_LIMIT]
        trimmed["added_links_truncated"] = len(added_links) - JOB_RESULT_PREVIEW_LIMIT
    return trimmed

"""Execute tracked jobs against a fresh database session.

Importable from Celery tasks and the local thread fallback. The web app is
imported lazily so a worker process can send post-refresh emails without a
module-level import cycle.
"""

from __future__ import annotations

import scripts.check_ads as check_ads
import src.scraper as scraper
from config.settings import SCRAPING_LOG_DIR
from src.database import SessionLocal
from src.job_service import mark_job_completed, mark_job_failed, mark_job_running
from utils.logger import get_logger

logger = get_logger(__name__, SCRAPING_LOG_DIR)


def _auto_send_after_refresh(db) -> dict | None:
    """Send notification emails when auto-send is enabled.

    Returns ``{"email_sent": [...], "email_failed": [...]}`` or ``None`` when
    auto-send is off. Imported lazily to avoid a cycle with the web app.
    """
    from src.main import _send_to_recipient, get_auto_send_after_refresh, get_recipients

    if not get_auto_send_after_refresh():
        return None

    recipients = [r for r in get_recipients() if r.get("auto_send", True)]
    sent: list[dict] = []
    failed: list[dict] = []
    for recipient in recipients:
        result = _send_to_recipient(recipient, db)
        if result["status"] == "sent":
            sent.append({"email": result["email"], "ads_count": result["ads_count"]})
        else:
            failed.append({"email": result["email"], "error": result.get("error", "Unknown error")})
    return {"email_sent": sent, "email_failed": failed}


def run_scrape_job(
    job_id: str | None = None,
    *,
    trigger_source: str = "manual",
    worker_type: str = "celery",
) -> dict:
    db = SessionLocal()
    try:
        if job_id:
            mark_job_running(db, job_id, worker_type=worker_type)

        ads_added = scraper.scrape_and_store(db)
        payload = {
            "new_ads_added": len(ads_added),
            "added_links": [getattr(ad, "link", None) for ad in ads_added],
        }
        email_outcome = _auto_send_after_refresh(db)
        if email_outcome is not None:
            payload.update(email_outcome)

        if job_id:
            mark_job_completed(db, job_id, result_payload=payload)
        return payload
    except Exception as exc:
        logger.error("Scrape job failed: %s", exc)
        if job_id:
            mark_job_failed(db, job_id, error_message=str(exc))
        raise
    finally:
        db.close()


def run_check_ads_job(
    job_id: str | None = None,
    *,
    trigger_source: str = "schedule",
    worker_type: str = "celery",
) -> dict:
    db = SessionLocal()
    try:
        if job_id:
            mark_job_running(db, job_id, worker_type=worker_type)

        check_ads.check_ad_status(db)
        payload = {"checked": True}

        if job_id:
            mark_job_completed(db, job_id, result_payload=payload)
        return payload
    except Exception as exc:
        logger.error("Check-ads job failed: %s", exc)
        if job_id:
            mark_job_failed(db, job_id, error_message=str(exc))
        raise
    finally:
        db.close()

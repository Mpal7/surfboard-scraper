from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.job_service import (
    create_job,
    get_job,
    list_jobs,
    mark_job_completed,
    mark_job_failed,
    mark_job_running,
    trim_result_payload,
)


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_and_get_job():
    db = _session()

    job = create_job(db, job_type="scrape", trigger_source="manual")

    assert job.id
    assert job.status == "queued"
    assert get_job(db, job.id).id == job.id


def test_mark_job_lifecycle_records_result():
    db = _session()
    job = create_job(db, job_type="scrape", trigger_source="manual")

    mark_job_running(db, job.id, worker_type="thread")
    assert get_job(db, job.id).status == "running"
    assert get_job(db, job.id).worker_type == "thread"

    mark_job_completed(db, job.id, result_payload={"new_ads_added": 2, "added_links": ["a", "b"]})
    stored = get_job(db, job.id)
    assert stored.status == "completed"
    assert stored.finished_at is not None
    assert stored.result_payload()["new_ads_added"] == 2


def test_mark_job_failed_records_error():
    db = _session()
    job = create_job(db, job_type="scrape", trigger_source="schedule")

    mark_job_failed(db, job.id, error_message="boom")

    stored = get_job(db, job.id)
    assert stored.status == "failed"
    assert stored.error_message == "boom"


def test_list_jobs_filters_by_type():
    db = _session()
    create_job(db, job_type="scrape", trigger_source="manual")
    create_job(db, job_type="check_ads", trigger_source="schedule")

    assert len(list_jobs(db)) == 2
    scrape_jobs = list_jobs(db, job_type="scrape")
    assert len(scrape_jobs) == 1
    assert scrape_jobs[0].job_type == "scrape"


def test_trim_result_payload_caps_added_links():
    payload = {"added_links": [f"link-{i}" for i in range(60)]}

    trimmed = trim_result_payload(payload)

    assert len(trimmed["added_links"]) == 50
    assert trimmed["added_links_truncated"] == 10

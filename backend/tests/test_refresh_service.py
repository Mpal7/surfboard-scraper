from unittest.mock import MagicMock

from src.models import JobRun
from src import refresh_service


def make_job(job_id: str, status: str = "queued") -> JobRun:
    return JobRun(id=job_id, job_type="scrape", trigger_source="manual", status=status)


def test_schedule_manual_refresh_enqueues_async_job(mocker):
    mock_db = MagicMock()
    created_job = make_job("job-123", status="queued")

    mocker.patch("src.refresh_service.refresh_allowed", return_value=(True, 0))
    set_last_refresh_time = mocker.patch("src.refresh_service.set_last_refresh_time")
    create_job = mocker.patch("src.refresh_service.create_job", return_value=created_job)
    dispatch_scrape_job = mocker.patch(
        "src.refresh_service.dispatch_scrape_job",
        return_value={"worker": "thread", "task_id": None},
    )
    mocker.patch("src.refresh_service.get_job", return_value=created_job)

    result = refresh_service.schedule_manual_refresh(mock_db, now=123.0)

    assert result == {
        "scheduled": True,
        "message": "Refresh scheduled.",
        "job_id": "job-123",
        "status": "queued",
        "worker": "thread",
        "task_id": None,
        "status_url": "/jobs/job-123",
    }
    create_job.assert_called_once_with(mock_db, job_type="scrape", trigger_source="manual")
    dispatch_scrape_job.assert_called_once_with("job-123", trigger_source="manual")
    set_last_refresh_time.assert_called_once_with(123.0)


def test_schedule_manual_refresh_respects_cooldown(mocker):
    mock_db = MagicMock()
    mocker.patch("src.refresh_service.refresh_allowed", return_value=(False, 17))
    set_last_refresh_time = mocker.patch("src.refresh_service.set_last_refresh_time")
    create_job = mocker.patch("src.refresh_service.create_job")

    result = refresh_service.schedule_manual_refresh(mock_db, now=123.0)

    assert result == {
        "scheduled": False,
        "retry_after_seconds": 17,
        "message": "Refresh allowed only every 1 minutes.",
    }
    set_last_refresh_time.assert_not_called()
    create_job.assert_not_called()


def test_refresh_allowed_uses_cooldown_file_values(mocker):
    mocker.patch("src.refresh_service.get_last_refresh_time", return_value=100.0)

    allowed, remaining = refresh_service.refresh_allowed(now=120.0)

    assert allowed is False
    assert remaining == 40.0

from unittest.mock import MagicMock

import pytest

from src import job_runner


def test_run_scrape_job_marks_completed_and_reports_ads(mocker):
    mock_db = MagicMock()
    mocker.patch("src.job_runner.SessionLocal", return_value=mock_db)
    running = mocker.patch("src.job_runner.mark_job_running")
    completed = mocker.patch("src.job_runner.mark_job_completed")
    mocker.patch(
        "src.job_runner.scraper.scrape_and_store",
        return_value=[MagicMock(link="https://example.com/a")],
    )
    mocker.patch(
        "src.job_runner._auto_send_after_refresh",
        return_value={"email_sent": [], "email_failed": []},
    )

    payload = job_runner.run_scrape_job("job-1", worker_type="thread")

    assert payload["new_ads_added"] == 1
    assert payload["added_links"] == ["https://example.com/a"]
    running.assert_called_once()
    completed.assert_called_once()
    assert completed.call_args.args[0] is mock_db
    assert completed.call_args.args[1] == "job-1"
    mock_db.close.assert_called_once()


def test_run_scrape_job_marks_failed_on_error(mocker):
    mock_db = MagicMock()
    mocker.patch("src.job_runner.SessionLocal", return_value=mock_db)
    mocker.patch("src.job_runner.mark_job_running")
    failed = mocker.patch("src.job_runner.mark_job_failed")
    mocker.patch(
        "src.job_runner.scraper.scrape_and_store",
        side_effect=RuntimeError("boom"),
    )
    mocker.patch("src.job_runner._auto_send_after_refresh")

    with pytest.raises(RuntimeError):
        job_runner.run_scrape_job("job-1")

    failed.assert_called_once()
    assert failed.call_args.kwargs["error_message"] == "boom"
    mock_db.close.assert_called_once()

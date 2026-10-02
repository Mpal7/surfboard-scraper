from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.auth import write_auth_config
from src.database import get_db
from src.main import app
from src.models import JobRun


def _auth_headers(client) -> dict:
    token = client.post(
        "/auth/login", json={"username": "admin", "password": "correct password"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _prepare_auth(monkeypatch, tmp_path):
    auth_file = tmp_path / "auth.json"
    write_auth_config("admin", "correct password", auth_file)
    monkeypatch.setattr("src.auth.AUTH_CONFIG_FILE", auth_file)


def test_refresh_endpoint_returns_202_with_job(mocker, monkeypatch, tmp_path):
    _prepare_auth(monkeypatch, tmp_path)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    mocker.patch(
        "src.main.schedule_manual_refresh",
        return_value={
            "scheduled": True,
            "message": "Refresh scheduled.",
            "job_id": "job-1",
            "status": "queued",
            "worker": "thread",
            "task_id": None,
            "status_url": "/jobs/job-1",
        },
    )

    try:
        client = TestClient(app)
        response = client.post("/refresh", headers=_auth_headers(client))

        assert response.status_code == 202
        assert response.json()["job_id"] == "job-1"
        assert response.json()["status_url"] == "/jobs/job-1"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_refresh_endpoint_returns_429_during_cooldown(mocker, monkeypatch, tmp_path):
    _prepare_auth(monkeypatch, tmp_path)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    mocker.patch(
        "src.main.schedule_manual_refresh",
        return_value={
            "scheduled": False,
            "retry_after_seconds": 17,
            "message": "Refresh allowed only every 1 minutes.",
        },
    )

    try:
        client = TestClient(app)
        response = client.post("/refresh", headers=_auth_headers(client))

        assert response.status_code == 429
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_get_job_endpoint_returns_404_when_missing(mocker, monkeypatch, tmp_path):
    _prepare_auth(monkeypatch, tmp_path)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    mocker.patch("src.main.get_job", return_value=None)

    try:
        client = TestClient(app)
        response = client.get("/jobs/missing", headers=_auth_headers(client))

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_get_job_endpoint_returns_job_payload(mocker, monkeypatch, tmp_path):
    _prepare_auth(monkeypatch, tmp_path)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    job = JobRun(id="job-1", job_type="scrape", trigger_source="manual", status="completed")
    mocker.patch("src.main.get_job", return_value=job)

    try:
        client = TestClient(app)
        response = client.get("/jobs/job-1", headers=_auth_headers(client))

        assert response.status_code == 200
        assert response.json()["id"] == "job-1"
        assert response.json()["status"] == "completed"
    finally:
        app.dependency_overrides.pop(get_db, None)

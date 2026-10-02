from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.auth import write_auth_config
from src.database import get_db
from src.main import app


def test_send_email_endpoint_requires_auth_and_dispatches_recipient(mocker, monkeypatch, tmp_path):
    auth_file = tmp_path / "auth.json"
    write_auth_config("admin", "correct password", auth_file)
    monkeypatch.setattr("src.auth.AUTH_CONFIG_FILE", auth_file)

    recipients = [{"email": "recipient@example.com", "filters": {}}]
    mocker.patch("src.main.get_recipients", return_value=recipients)
    send_recipient = mocker.patch(
        "src.main._send_to_recipient",
        return_value={"email": "recipient@example.com", "ads_count": 1, "status": "sent"},
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()

    try:
        client = TestClient(app)
        assert client.post("/send_email").status_code == 401

        token = client.post(
            "/auth/login", json={"username": "admin", "password": "correct password"}
        ).json()["access_token"]
        response = client.post(
            "/send_email?emails=recipient%40example.com",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "sent": [{"email": "recipient@example.com", "ads_count": 1}],
            "failed": [],
        }
        send_recipient.assert_called_once_with(recipients[0], mocker.ANY)
    finally:
        app.dependency_overrides.pop(get_db, None)

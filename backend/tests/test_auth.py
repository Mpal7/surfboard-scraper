from fastapi.testclient import TestClient

from src.auth import hash_password, verify_password
from src.main import app


def test_password_hash_verifies_only_original_password():
    encoded = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_login_issues_token_and_protected_routes_require_it(monkeypatch, tmp_path):
    auth_file = tmp_path / "auth.json"
    from src.auth import write_auth_config

    write_auth_config("admin", "correct password", auth_file)
    monkeypatch.setattr("src.auth.AUTH_CONFIG_FILE", auth_file)

    client = TestClient(app)

    assert client.get("/ads").status_code == 401
    assert client.post(
        "/auth/login", json={"username": "admin", "password": "wrong password"}
    ).status_code == 401

    response = client.post(
        "/auth/login", json={"username": "admin", "password": "correct password"}
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json() == {
        "username": "admin"
    }
    assert token.count(".") == 1

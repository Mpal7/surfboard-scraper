import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import (
    ADMIN_PASSWORD_HASH,
    ADMIN_USERNAME,
    AUTH_CONFIG_FILE,
    AUTH_SECRET,
    AUTH_TOKEN_TTL_SECONDS,
)

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 310_000
bearer_scheme = HTTPBearer(auto_error=False)


class AuthConfigurationError(RuntimeError):
    pass


def _encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decoded(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${_encoded(salt)}${_encoded(digest)}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, encoded_salt, encoded_digest = encoded_hash.split("$")
        if algorithm != PASSWORD_ALGORITHM:
            return False
        salt = _decoded(encoded_salt)
        expected = _decoded(encoded_digest)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _load_auth_config() -> dict[str, str]:
    env_config = {
        "username": ADMIN_USERNAME,
        "password_hash": ADMIN_PASSWORD_HASH,
        "auth_secret": AUTH_SECRET,
    }
    if all(env_config.values()):
        return env_config

    try:
        with Path(AUTH_CONFIG_FILE).open("r", encoding="utf-8") as auth_file:
            config = json.load(auth_file)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise AuthConfigurationError(
            "Authentication is not configured. Run scripts/generate_admin_credentials.py "
            "or set the ADMIN_USERNAME, ADMIN_PASSWORD_HASH, and AUTH_SECRET environment variables."
        ) from error

    if not all(config.get(key) for key in env_config):
        raise AuthConfigurationError("Authentication configuration is incomplete.")
    return {key: str(config[key]) for key in env_config}


def write_auth_config(username: str, password: str, destination: Path = AUTH_CONFIG_FILE) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "username": username,
        "password_hash": hash_password(password),
        "auth_secret": secrets.token_urlsafe(32),
    }
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as auth_file:
        json.dump(config, auth_file, indent=2)
        auth_file.write("\n")
    temporary.replace(destination)


def create_access_token(username: str) -> str:
    config = _load_auth_config()
    now = int(time.time())
    payload = {"sub": username, "iat": now, "exp": now + AUTH_TOKEN_TTL_SECONDS}
    encoded_payload = _encoded(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        config["auth_secret"].encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_encoded(signature)}"


def authenticate_admin(username: str, password: str) -> bool:
    try:
        config = _load_auth_config()
    except AuthConfigurationError:
        return False
    return hmac.compare_digest(username, config["username"]) and verify_password(
        password, config["password_hash"]
    )


def get_authenticated_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        config = _load_auth_config()
        encoded_payload, encoded_signature = credentials.credentials.split(".")
        expected_signature = hmac.new(
            config["auth_secret"].encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_decoded(encoded_signature), expected_signature):
            raise ValueError("Invalid signature")
        payload = json.loads(_decoded(encoded_payload))
        if payload.get("sub") != config["username"] or int(payload["exp"]) <= int(time.time()):
            raise ValueError("Expired token")
        return str(payload["sub"])
    except (
        AuthConfigurationError,
        binascii.Error,
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(admin: str = Depends(get_authenticated_admin)) -> str:
    return admin

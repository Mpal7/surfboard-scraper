import json
import logging
from pathlib import Path
from typing import Optional

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

EMAIL_CONFIG_PATH = DATA_DIR / "email_config.json"

DEFAULT_FILTER = {
    "brand": None,
    "min_price": None,
    "max_price": None,
    "min_length_inches": None,
    "max_length_inches": None,
    "min_width": None,
    "max_width": None,
    "min_thickness": None,
    "max_thickness": None,
    "min_liters": None,
    "max_liters": None,
}

DEFAULT_CONFIG = {
    "auto_send_after_refresh": True,
    "recipients": [],
}


def load_config() -> dict:
    if not EMAIL_CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()
    try:
        with open(EMAIL_CONFIG_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load email config: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    with open(EMAIL_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_recipients() -> list[dict]:
    return load_config().get("recipients", [])


def get_recipient(email: str) -> Optional[dict]:
    for r in get_recipients():
        if r["email"].lower() == email.lower():
            return r
    return None


def add_recipient(recipient: dict) -> dict:
    config = load_config()
    existing = get_recipient(recipient["email"])
    if existing:
        raise ValueError(f"Recipient {recipient['email']} already exists")
    config["recipients"].append(recipient)
    save_config(config)
    return recipient


def update_recipient(email: str, updates: dict) -> dict:
    config = load_config()
    for i, r in enumerate(config["recipients"]):
        if r["email"].lower() == email.lower():
            for key, value in updates.items():
                if key != "email":
                    r[key] = value
            config["recipients"][i] = r
            save_config(config)
            return r
    raise ValueError(f"Recipient {email} not found")


def delete_recipient(email: str) -> bool:
    config = load_config()
    original_len = len(config["recipients"])
    config["recipients"] = [
        r for r in config["recipients"] if r["email"].lower() != email.lower()
    ]
    if len(config["recipients"]) == original_len:
        raise ValueError(f"Recipient {email} not found")
    save_config(config)
    return True


def get_auto_send_after_refresh() -> bool:
    return load_config().get("auto_send_after_refresh", True)


def set_auto_send_after_refresh(enabled: bool) -> None:
    config = load_config()
    config["auto_send_after_refresh"] = enabled
    save_config(config)

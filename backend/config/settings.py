from __future__ import annotations

import os
from pathlib import Path
import random
from typing import Iterable

import httpx

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Storage / persistence
DATABASE_PATH = DATA_DIR / "ads.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

# Task queue
REDIS_URL = "redis://localhost:6379/0"

# env
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# API refresh throttling
COOLDOWN_FILE = DATA_DIR / "last_refresh.txt"
REFRESH_COOLDOWN_SECONDS = 1 * 60

# Logging
SCRAPING_LOG_DIR = BASE_DIR / "logs"
MAINTENANCE_LOG_DIR = BASE_DIR / "logs"

# HTTP behaviour
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    # Drop 'br' to avoid brotli-encoded responses when brotli decoder is unavailable.
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
    "Referer": "https://www.subito.it/",
    "Sec-Ch-Ua": '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.183 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.160 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/120.0.0.0 Safari/537.36",
]

SEC_CH_UA_POOL = [
    '"Not.A/Brand";v="8", "Chromium";v="122", "Google Chrome";v="122"',
    '"Chromium";v="121", "Not.A/Brand";v="8", "Microsoft Edge";v="121"',
    '"Not?A_Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
]

ACCEPT_LANGUAGE_POOL = [
    "it-IT,it;q=0.9,en-US;q=0.7,en;q=0.6",
    "en-GB,en;q=0.9,it-IT;q=0.8,it;q=0.7",
    "it-IT,it;q=0.9,en;q=0.8",
]

REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=30.0)


def choose(seq: Iterable[str]) -> str:
    return random.choice(list(seq))


def build_headers(referrer: str | None = None) -> dict[str, str]:
    """Assemble per-request headers with light randomisation."""
    headers = DEFAULT_HEADERS.copy()
    ua_choice = choose(USER_AGENT_POOL)
    headers["User-Agent"] = ua_choice
    headers["Sec-Ch-Ua"] = choose(SEC_CH_UA_POOL)
    headers["Accept-Language"] = choose(ACCEPT_LANGUAGE_POOL)
    headers["Referer"] = referrer or DEFAULT_HEADERS["Referer"]
    headers["Cache-Control"] = "max-age=0"
    headers["Pragma"] = "no-cache"
    headers["Dnt"] = "1"

    if "Macintosh" in ua_choice:
        headers["Sec-Ch-Ua-Platform"] = '"macOS"'
    elif "Linux" in ua_choice:
        headers["Sec-Ch-Ua-Platform"] = '"Linux"'
    else:
        headers["Sec-Ch-Ua-Platform"] = '"Windows"'

    return headers


SEARCH_CITIES = [
    ("roma", "lazio"),
    ("milano", "lombardia"),
    ("genova", "liguria"),
    ("savona", "liguria"),
    ("imperia", "liguria"),
    ("la-spezia", "liguria"),
    ("livorno", "toscana"),
    ("lucca", "toscana"),
    ("grosseto", "toscana"),
    ("pisa", "toscana"),
    ("rimini", "emilia-romagna"),
    ("forli-cesena", "emilia-romagna"),
    ("ravenna", "emilia-romagna"),
    ("venezia", "veneto"),
    ("ancona", "marche"),
    ("pesaro-urbino", "marche"),
    ("cagliari", "sardegna"),
    ("sassari", "sardegna"),
    ("palermo", "sicilia"),
    ("catania", "sicilia"),
    ("lecce", "puglia"),
    ("bari", "puglia"),
    ("reggio-calabria", "calabria"),
    ("napoli", "campania"),
    ("salerno", "campania"),
    ("padova", "veneto"),
]

SEARCH_TERMS = ["tavola+da+surf", "surfboard"]

SEARCH_CONFIGS = [
    (city, region, term)
    for city, region in SEARCH_CITIES
    for term in SEARCH_TERMS
]

ALLOWED_CATEGORY_IDS = {"20"}

DEFAULT_IMAGE_RULE = "gallery-desktop-1x-auto"
DETAIL_IMAGE_RULE = "fullscreen-1x-auto"

EXCLUDED_TERMS = [
    "kite",
    "wind",
    "surfskate",
    "foil",
    "sup",
    "surfsup",
    "skate",
    "wake",
    "sacca",
    "cover",
    "mutina",
    "muta",
    "Jetsurf",
    "kitesurf",
    "kitesurfing",
    "windsurf",
    "windsurfing",
    "surfskate",
    "surfskating",
    "wakeboard",
    "wakeboarding",
    "paddle",
    "paddleboard",
    "paddleboarding",
    "stand up paddle",
    "/kitesurf",
    "surfista",
    "kiteloose",
    "borsa",
    "air4",
    "air",
    "pinna",
    "pinne",
    "body",
]

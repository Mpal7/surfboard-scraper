from __future__ import annotations

import os
from pathlib import Path
import random
from typing import Iterable

import httpx
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Load local development secrets before reading any environment-backed setting.
# Explicitly exported process variables remain authoritative (`override=False`).
load_dotenv(BASE_DIR / ".env")

AUTH_CONFIG_FILE = DATA_DIR / "auth.json"
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "28800"))

# Storage / persistence
DATABASE_PATH = DATA_DIR / "ads.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

# Task queue
REDIS_URL = "redis://localhost:6379/0"

# env
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
AUTH_SECRET = os.getenv("AUTH_SECRET", "")

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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
]

SEC_CH_UA_POOL = [
    '"Not/A.Brand";v="99", "Chromium";v="152", "Google Chrome";v="152"',
    '"Not.A/Brand";v="99", "Chromium";v="151", "Google Chrome";v="151"',
    '"Not/A.Brand";v="99", "Chromium";v="152", "Microsoft Edge";v="152"',
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
    ("venezia", "veneto"),
    ("padova", "veneto"),
]

FOIL_SEARCH_TERMS = ["foil", "wingfoil"]
KITE_SEARCH_TERMS = ["kitesurf", "kiteboard", "kite+surf", "parakite", "parawing", "lowwing"]
SEARCH_TERMS = ["tavola+da+surf", "surfboard", *FOIL_SEARCH_TERMS, *KITE_SEARCH_TERMS]

SEARCH_CONFIGS = [
    (city, region, term)
    for city, region in SEARCH_CITIES
    for term in SEARCH_TERMS
]

ALLOWED_CATEGORY_IDS = {"20"}

# Product vocabulary used to distinguish actual foil/kite equipment from
# nearby marketplace accessories such as wetsuits, harnesses, and bags.
FOIL_ITEM_TERMS = [
    "foil",
    "hydrofoil",
    "wingfoil",
    "wing foil",
    "windfoil",
    "efoil",
    "e-foil",
    "foilboard",
    "foil board",
    "front wing",
    "frontwing",
    "rear wing",
    "tail wing",
    "ala anteriore",
    "ala front",
    "ala posteriore",
    "stabilizzatore",
    "stabilizer",
    "fusoliera",
    "piantone",
    "mast",
    "tavola foil",
    "tavola wing",
    "set foil",
    "kit foil",
    "vela wing",
    "ala wing",
]

FOIL_PRODUCT_TERMS = [
    "curve",
    "allvator",
    "sabfoil",
    "kraken",
    "phantom",
    "carve",
    "whizz",
    "thunder",
    "blade",
    "jet",
    "supercruiser",
    "sky",
    "skybrid",
    "beluga",
    "zuma",
    "hipe",
    "seek",
    "manticore",
    "strike",
    "slick",
    "unit",
    "droid",
    "neutra",
]

KITE_ITEM_TERMS = [
    "kite",
    "kitesurf",
    "kite surf",
    "kiteboard",
    "kite board",
    "tavola kite",
    "tavola da kite",
    "tavola kitesurf",
    "tavola da kitesurf",
    "twintip",
    "twin tip",
    "ala kite",
    "vela kite",
    "kite vela",
    "surfino",
    "set kite",
    "kit kite",
    "attrezzatura kite",
    "attrezzatura kitesurf",
    "parawing",
    "lowwing",
    "harness",
    "trapezio",
]

KITE_PRODUCT_TERMS = [
    "bandit",
    "rebel",
    "switchblade",
    "pivot",
    "orbit",
    "neo",
    "evo",
    "enduro",
    "moto",
    "vision",
    "passion",
    "religion",
    "gonzales",
    "prime",
    "monarch",
    "jaime",
    "mitu",
    "placebo",
    "maquina",
    "waroo",
    "ultimate",
    "twintip",
]

KITE_HARNESS_TERMS = [
    "harness",
    "waist harness",
    "seat harness",
    "trapezio",
    "imbrago",
    "imbracatura",
]

EQUIPMENT_ACCESSORY_TERMS = [
    "muta",
    "trapezio",
    "harness",
    "barra",
    "sacca",
    "borsa",
    "cover",
    "custodia",
    "pompa",
    "leash",
    "strap",
    "straps",
    "footstrap",
    "maniglia",
    "attacco",
    "attacchi",
    "viti",
    "dadi",
    "sensore",
    "giubbotto",
    "giubbino",
]

DEFAULT_IMAGE_RULE = "gallery-desktop-1x-auto"
DETAIL_IMAGE_RULE = "fullscreen-1x-auto"

# Board types that disqualify an ad from being stored at all. These are
# whole-category exclusions (snowboard, windsurf, SUP, paddle, skate, wake,
# bodyboard): the user does not want any of these scraped.
SKIP_ADS_TERMS = [
    "snowboard",
    "snowboarding",
    "windsurf",
    "windsurfing",
    "sup",
    "surfsup",
    "stand up paddle",
    "paddle",
    "paddleboard",
    "paddleboarding",
    "skateboard",
    "skateboarding",
    "surfskate",
    "surfskating",
    "waveboard",
    "wakeboard",
    "wakeboarding",
    "bodyboard",
    "bodyboarding",
    "jetsurf",
    "efoil",
    "e-foil",
    "hydrofoil",
    "hydro foil",
]

# Secondary terms that hide a stored ad from the UI (primary filter is SKIP_ADS_TERMS).
# These are accessories / passing mentions (e.g. "con sacca inclusa") that should
# not hard-skip a real surfboard listing.
EXCLUDED_TERMS = [
    "sacca",
    "borsa",
    "cover",
    "mutina",
    "muta",
    "surfista",
    "air4",
    "air",
    "pinna",
    "pinne",
    "body",
]

import logging
import random
import time

import httpx
from httpx import URL
from sqlalchemy.orm import Session

from config.settings import MAINTENANCE_LOG_DIR, REQUEST_TIMEOUT, build_headers
from src.database import SessionLocal
from src.models import Ad
from utils.logger import get_logger

logger = get_logger(__name__, MAINTENANCE_LOG_DIR)

MISSING_ANNOUNCEMENT_PHRASES = [
    "questo annuncio non esiste più",
    "questo annuncio non esiste piu",
]


def _is_homepage(url: URL | str) -> bool:
    """Return True if the given URL points to Subito's homepage."""
    try:
        target = URL(url) if not isinstance(url, URL) else url
    except Exception:
        return False

    if target.host != "www.subito.it":
        return False

    # Normalize path and ignore query params/fragments.
    path = target.path.rstrip("/")
    return path == "" or path == "/"


def response_indicates_removed(response: httpx.Response) -> bool:
    """Return True when the upstream response points to a removed listing."""
    if response.status_code in (404, 410):
        return True

    # Subito frequently responds with 403 for removed ads; check body to be sure.
    if response.status_code == 403:
        body = (response.text or "").lower()
        return any(phrase in body for phrase in MISSING_ANNOUNCEMENT_PHRASES)

    if response.is_redirect:
        target = response.headers.get("location", "")
        if _is_homepage(target):
            return True

    # Some stacks follow redirects automatically; check the final URL as well.
    if _is_homepage(response.url):
        return True

    body = (response.text or "").lower()
    return any(phrase in body for phrase in MISSING_ANNOUNCEMENT_PHRASES)


def check_ad_status(db: Session):
    """
    Iterates through active ads and checks if their links are still valid.
    Updates the is_active flag to False for dead links.
    """
    ads_to_check = db.query(Ad).filter(Ad.is_active == True).all()
    if not ads_to_check:
        logger.info("No active ads to check. Exiting.")
        return

    logger.info(f"Starting check for {len(ads_to_check)} active ads.")
    deactivated_count = 0

    # Use HTTP/2 and randomized headers to look more like a browser and reduce 403s.
    with httpx.Client(
        http2=True,
        headers=build_headers(),
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT,
    ) as client:
        for ad in ads_to_check:
            try:
                headers = build_headers(referrer=ad.link)
                response = client.get(ad.link, headers=headers)

                if response_indicates_removed(response):
                    logger.warning(
                        f"Ad ID {ad.id} considered gone (status {response.status_code}). Deactivating: {ad.link}"
                    )
                    ad.is_active = False
                    deactivated_count += 1
                else:
                    logger.info(f"Ad ID {ad.id} is still ACTIVE ({response.status_code}).")

            except httpx.RequestError as e:
                logger.error(f"Network error checking Ad ID {ad.id}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred for Ad ID {ad.id}: {e}")

            time.sleep(random.uniform(10, 20))  # Polite delay between requests

    if deactivated_count > 0:
        db.commit()
        logger.info(f"Committed changes to the database. Deactivated {deactivated_count} ads.")
    else:
        logger.info("No ads were deactivated in this run.")


if __name__ == "__main__":
    logger.info("--- Starting Ad Status Check Script ---")
    # This script needs its own database session since it's not part of the FastAPI app
    db = SessionLocal()
    try:
        check_ad_status(db)
    finally:
        db.close()
    logger.info("--- Ad Status Check Script Finished ---")
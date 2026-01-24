"""Utility script to backfill or normalise image URLs for previously scraped ads."""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import or_

from database import SessionLocal
from models import Ad
from scraper import (
    DEFAULT_IMAGE_RULE,
    REQUEST_TIMEOUT,
    _build_image_url,
    _ensure_image_url,
    build_headers,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Update stored ad images with working URLs.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most this many ads (default: no limit).",
    )
    parser.add_argument(
        "--force-fetch",
        action="store_true",
        help="Fetch every detail page even if an image URL already looks valid.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without committing changes to the database.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.5,
        help="Base delay (in seconds) between network requests when fetching detail pages.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args(argv)


def fetch_detail_page(client: httpx.Client, url: str, base_delay: float, max_attempts: int = 3) -> str | None:
    """Fetch an ad detail page with basic retry logic."""
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.get(url, headers=build_headers(referrer="https://www.subito.it/"))
        except httpx.RequestError as exc:
            logging.warning("Network error for %s: %s", url, exc)
        else:
            if response.status_code == 200:
                return response.text
            if response.status_code in (403, 429, 503):
                wait = max(base_delay, 0.5) * attempt + random.uniform(0, base_delay)
                logging.warning(
                    "Status %s for %s (attempt %d/%d). Cooling down for %.1fs before retrying.",
                    response.status_code,
                    url,
                    attempt,
                    max_attempts,
                    wait,
                )
                client.cookies.clear()
                time.sleep(wait)
                continue
            logging.error("Unexpected status %s for %s; aborting fetch.", response.status_code, url)
            return None
        wait = max(base_delay, 0.5) * attempt + random.uniform(0, base_delay)
        time.sleep(wait)
    logging.error("Exceeded retry attempts while fetching %s", url)
    return None


def update_image_for_ad(ad: Ad, client: httpx.Client, base_delay: float, force_fetch: bool) -> tuple[str | None, str, bool, str | None]:
    """Resolve a working image URL for a single ad."""
    original = ad.image_url or ""

    if original and not force_fetch:
        normalised = _build_image_url(original, DEFAULT_IMAGE_RULE)
        if normalised and normalised != original:
            return normalised, "normalised existing URL", False, None
        if normalised:
            return None, "image already contained a rule parameter", False, None

    should_fetch = force_fetch or not original
    if should_fetch:
        html = fetch_detail_page(client, ad.link, base_delay)
        if not html:
            return None, "unable to fetch detail page", True, "detail fetch failed"
        soup = BeautifulSoup(html, "html.parser")
        seed = None if force_fetch else _build_image_url(original, DEFAULT_IMAGE_RULE) if original else None
        refreshed = _ensure_image_url(seed, soup)
        if refreshed and refreshed != original:
            return refreshed, "retrieved image from detail page metadata", True, None
        return None, "no image found on detail page", True, None

    return None, "no change needed", False, None


def select_ads(session, force_fetch: bool):
    query = session.query(Ad).order_by(Ad.timestamp.asc())
    if not force_fetch:
        query = query.filter(or_(Ad.image_url == None, ~Ad.image_url.contains("rule=")))  # noqa: E711
    return query


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    session = SessionLocal()
    updated = 0
    unchanged = 0
    failures = 0
    processed = 0

    try:
        query = select_ads(session, args.force_fetch)
        with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
            for ad in query:
                if args.limit is not None and processed >= args.limit:
                    break

                processed += 1
                new_url, note, fetched, error = update_image_for_ad(ad, client, args.sleep, args.force_fetch)

                if error:
                    failures += 1
                    logging.warning("Ad %s (%s): %s", ad.id, ad.link, note)
                elif new_url:
                    updated += 1
                    logging.info("Updating ad %s with new image (%s)", ad.id, note)
                    ad.image_url = new_url
                    if args.dry_run:
                        logging.debug("Dry-run active; change will not be committed.")
                else:
                    unchanged += 1
                    logging.debug("Ad %s requires no update (%s)", ad.id, note)

                if fetched and args.sleep > 0:
                    wait = args.sleep + random.uniform(0, max(args.sleep / 2, 0.25))
                    time.sleep(wait)

        if updated and not args.dry_run:
            session.commit()
            logging.info("Committed %d updated records.", updated)
        else:
            session.rollback()
            if updated:
                logging.info("Dry-run finished; rolled back %d staged updates.", updated)
    finally:
        session.close()

    logging.info(
        "Finished processing %d ads (%d updated, %d unchanged, %d failures).",
        processed,
        updated,
        unchanged,
        failures,
    )


if __name__ == "__main__":
    main(sys.argv[1:])

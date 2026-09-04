import json
import random
import re
import time
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.settings import (
    ALLOWED_CATEGORY_IDS,
    DEFAULT_IMAGE_RULE,
    DETAIL_IMAGE_RULE,
    EXCLUDED_TERMS,
    REQUEST_TIMEOUT as SETTINGS_TIMEOUT,
    SCRAPING_LOG_DIR,
    SEARCH_CONFIGS,
    build_headers as settings_build_headers,
)
from src.models import Ad
from extraction.surfboard_parser import parse_listing
from extraction.extraction import (
    BRAND_MAP,
    BRAND_REGEX,
    FRACTION_MAP,
    FRACTION_SYMBOLS,
    POPULAR_BRANDS,
    create_brand_pattern,
    extract_dimensions,
    extract_liters,
    extract_price,
    find_brand,
    normalize_for_matching,
    parse_dimension_part,
    text_pre_processor,
)
from utils.logger import get_logger

logger = get_logger(__name__, SCRAPING_LOG_DIR)

REQUEST_TIMEOUT = SETTINGS_TIMEOUT


def build_headers(referrer=None):
    """Expose header builder while delegating to settings module."""
    return settings_build_headers(referrer=referrer)


def _build_image_url(base_url, rule=DEFAULT_IMAGE_RULE):
    """Append the expected Subito image rule to bare CDN URLs when needed."""
    if not base_url:
        return None
    base_url = base_url.strip()
    if not base_url:
        return None
    if base_url.startswith("//"):
        base_url = "https:" + base_url
    if not rule or "rule=" in base_url:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}rule={rule}"


def _extract_image_from_entry(image_entry, rule=DEFAULT_IMAGE_RULE):
    """Return the first usable image URL from a Subito image entry."""
    if isinstance(image_entry, str):
        return _build_image_url(image_entry, rule=rule)
    if not isinstance(image_entry, dict):
        return None

    # Subito image entries often have full/preview keys; prefer the best available.
    candidates = [
        image_entry.get('full'),
        image_entry.get('preview'),
        image_entry.get('thumbnail'),
    ]
    for candidate in candidates:
        if candidate:
            return _build_image_url(candidate, rule=rule)
    return None


def _ensure_image_url(existing_url, detail_soup):
    """Prefer a fully-qualified image URL, falling back to the detail page metadata."""
    image_url = existing_url or None
    if image_url and "rule=" not in image_url:
        image_url = _build_image_url(image_url, rule=DEFAULT_IMAGE_RULE)
    if image_url:
        return image_url

    if not detail_soup:
        return None

    og_image = detail_soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        candidate = og_image["content"].strip()
        if candidate:
            return _build_image_url(candidate, rule=DETAIL_IMAGE_RULE)
    return None


def _price_text_from_features(features):
    price_block = (features or {}).get('/price') or {}
    values = price_block.get('values') or []
    if not values:
        return ""
    return values[0].get('value') or ""


def _extract_listings_from_next_data(soup):
    """Parse Subito's Next.js payload; tolerate layout changes by merging list variants."""
    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag or not script_tag.string:
        return []
    try:
        payload = json.loads(script_tag.string)
    except json.JSONDecodeError:
        logger.warning("Could not decode __NEXT_DATA__ JSON payload; skipping fallback.")
        return []

    page_props = payload.get('props', {}).get('pageProps', {})
    initial_state = page_props.get('initialState', {}) or {}
    items_state = (initial_state.get('items') or {})
    entity_items = (initial_state.get('entities') or {}).get('items') or {}

    # Some responses now populate rankedList/galleryList while list can be empty.
    raw_entries = []
    for key in ('list', 'rankedList', 'galleryList', 'originalList'):
        entries = items_state.get(key) or []
        if isinstance(entries, list):
            raw_entries.extend(entries)

    if not raw_entries:
        return []

    listings = []
    seen_links = set()
    for entry in raw_entries:
        # Support both old format (entry.item) and new format (entry IS the item)
        item = entry.get('item') or entity_items.get(entry.get('urn')) or (entry if entry.get('kind') else {})
        if (item.get('kind') or '').lower() != 'aditem':
            continue
        category_id = str((item.get('category') or {}).get('id', '')).strip()
        if category_id and category_id not in ALLOWED_CATEGORY_IDS:
            continue
        listing_type = (item.get('type') or {}).get('key')
        if listing_type and listing_type.lower() != 's':
            continue

        url = (item.get('urls') or {}).get('default')
        if not url or url in seen_links:
            continue
        seen_links.add(url)

        subject = item.get('subject') or "N/A"
        location = (
            (item.get('geo') or {}).get('town') or {}
        ).get('value') or (
            (item.get('geo') or {}).get('city') or {}
        ).get('value') or ""
        price_text = _price_text_from_features(item.get('features'))
        body = item.get('body') or ""
        image_candidates = item.get('images') or []
        image_url = _extract_image_from_entry(image_candidates[0], rule=DEFAULT_IMAGE_RULE) if image_candidates else None

        combined_text = " ".join(
            part for part in (subject, price_text, location, body)
            if part
        )

        listings.append(
            {
                'source': 'json',
                'link': url,
                'model': subject,
                'full_text': combined_text,
                'image_url': image_url,
                'location_text': location,
            }
        )

    return listings


def _extract_listings_from_html(soup):
    # New markup uses <article> cards with generated class names (no more item-card divs).
    containers = soup.find_all(
        "article",
        class_=lambda cls: cls and 'aditem' in cls.lower() if isinstance(cls, str) else (cls and any('aditem' in c.lower() for c in cls)),
    )
    # Fallback for legacy fixtures/tests using div.item-card
    if not containers:
        containers = soup.find_all("div", class_="item-card")
    listings = []
    for container in containers:
        link_tag = container.find("a", href=True)
        if not link_tag:
            continue
        link = link_tag['href']
        title_tag = container.find(["h3", "h2"])
        model = title_tag.get_text(strip=True) if title_tag else "N/A"
        full_text = container.get_text(" ", strip=True)
        image_url = None
        img_tag = container.find("img")
        if img_tag and img_tag.get('src'):
            image_url = img_tag['src']

        listings.append(
            {
                'source': 'html',
                'link': link,
                'model': model,
                'full_text': full_text,
                'image_url': image_url,
                'location_text': None,
            }
        )
    return listings

search_configs = list(SEARCH_CONFIGS)

def scrape_and_store(db: Session):
    ads_added = []
    
    logger.info("Fetching existing ad links from the database...")
    existing_links = {result[0] for result in db.query(Ad.link).all()}
    logger.info(f"Found {len(existing_links)} existing links.")

    configs = list(search_configs)
    random.shuffle(configs)

    with httpx.Client(follow_redirects=True, http2=True, timeout=REQUEST_TIMEOUT, verify=False) as client:
        def fetch_with_resilience(target_url, referrer=None, max_attempts=3):
            """Retry fetches on soft-block signals with cooldowns and header rotation."""
            for attempt in range(1, max_attempts + 1):
                try:
                    response = client.get(
                        target_url,
                        headers=build_headers(referrer=referrer),
                    )
                except httpx.RequestError as exc:
                    logger.error(f"Network error while fetching {target_url}: {exc}")
                    time.sleep(random.uniform(5, 12))
                    continue

                if response.status_code == 403:
                    cooldown = random.uniform(45, 90) * attempt
                    logger.warning(
                        "Received 403 for %s on attempt %d. Cooling down for %.1f seconds.",
                        target_url,
                        attempt,
                        cooldown,
                    )
                    client.cookies.clear()
                    time.sleep(cooldown)
                    continue

                if response.status_code in (429, 503):
                    cooldown = random.uniform(30, 60) * attempt
                    logger.warning(
                        "Received %d for %s. Cooling down for %.1f seconds before retrying.",
                        response.status_code,
                        target_url,
                        cooldown,
                    )
                    time.sleep(cooldown)
                    continue

                return response

            logger.error("Exceeded retry attempts for %s", target_url)
            return None

        # This now uses the global search_configs variable
        for city, region, term in configs:
            base_url = f"https://www.subito.it/annunci-{region}/vendita/usato/{city}/?q={term}"
            for page_num in range(1, 6):
                url = f"{base_url}&o={page_num}"
                logger.info(f"Scraping search results from: {url}")
                time.sleep(random.uniform(2, 5))
                try:
                    response = fetch_with_resilience(
                        url,
                        referrer=base_url if page_num == 1 else f"{base_url}&o={page_num - 1}",
                    )
                    if response is None:
                        logger.error(f"Failed to fetch {url} after retries. Skipping page.")
                        break
                    if response.status_code != 200:
                        logger.error(f"Failed to fetch {url}. Status: {response.status_code}")
                        continue
                    if "Access Denied" in response.text:
                        logger.error(f"Access Denied for {url}. We are being blocked.")
                        break
                except httpx.RequestError as e:
                    logger.error(f"Network error while fetching {url}: {e}")
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                listings = _extract_listings_from_next_data(soup)
                listings_source = "json" if listings else "html"
                if not listings:
                    listings = _extract_listings_from_html(soup)
                logger.info(
                    "Found %d potential ad listings on page %d using %s path.",
                    len(listings),
                    page_num,
                    listings_source,
                )

                if not listings:
                    logger.info(f"No more ads found on page {page_num}. Moving to next search term.")
                    break

                for listing in listings:
                    link = listing.get('link')
                    if not link:
                        continue

                    logger.info("-" * 60)
                    logger.info(
                        "Processing ad link: %s (source=%s)",
                        link,
                        listing.get('source'),
                    )
                    if link in existing_links:
                        logger.info(f"Skipping ad, already in database: %s", link)
                        continue

                    full_text = listing.get('full_text') or ""
                    if "€" not in full_text:
                        continue

                    model = listing.get('model') or "N/A"

                    if "sacca" in model.lower():
                        logger.info(f"Skipping ad {link}: title contains 'sacca'")
                        continue

                    keywords = ["tavola", "surf", "softboard", "longboard", 
                                "shortboard", "wingfoil", "windsurf", "foil",
                                  "skateboard", "bodyboard", "paddle", "paddleboard", "snowboard"]
                    if not any(kw in full_text.lower() for kw in keywords):
                        logger.info(f"Skipping ad {link}: not surf-related")
                        continue

                    ad_data = {
                        "model": model,
                        "price": extract_price(full_text),
                        "location": (listing.get('location_text') or city.replace('-', ' ').capitalize()),
                        "link": link,
                        "brand": None,
                        "image_url": listing.get('image_url'),
                    }

                    try:
                        detail_resp = fetch_with_resilience(link, referrer=url, max_attempts=2)
                        if detail_resp is None:
                            logger.error(f"  > Could not fetch detail page after retries: {link}")
                            continue
                        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                        detail_image = _ensure_image_url(ad_data.get('image_url'), detail_soup)
                        if detail_image:
                            ad_data['image_url'] = detail_image
                        desc_div = detail_soup.find("p", class_=lambda c: c and 'description' in c.lower())
                        desc_text = desc_div.get_text(separator=" ", strip=True) if desc_div else ""
                        full_desc_text = f"{ad_data['model']} {desc_text}"

                        # Extract all attributes at once via parse_listing
                        parsed = parse_listing(full_desc_text)
                        ad_data["brand"] = parsed["brand"]
                        ad_data["liters"] = parsed["liters"]
                        ad_data["length_ft"] = parsed["length_ft"]
                        ad_data["length_in"] = parsed["length_in"]
                        ad_data["width_in"] = parsed["width_in"]
                        ad_data["thickness_in"] = parsed["thickness_in"]
                        
                        # Check if ad should be visible based on criteria
                        is_visible = True
                        
                        # Check for excluded terms
                        excluded_terms = EXCLUDED_TERMS
                        for term in excluded_terms:
                            if re.search(rf"\b{re.escape(term)}\b", full_desc_text, re.IGNORECASE):
                                logger.info(f"Marking ad as not visible {link}: contains excluded term '{term}'")
                                is_visible = False
                                break
                        
                        # Check for valid dimensions or brand
                        if is_visible:
                            length_ft = ad_data.get("length_ft")
                            brand = ad_data.get("brand")
                            price = ad_data.get("price")
                            valid_length = isinstance(length_ft, (int, float)) and length_ft >= 4
                            valid_brand = isinstance(brand, str) and brand.strip()
                            if not (valid_length or valid_brand):
                                logger.warning(f"  > Marking ad as not visible (length_ft is missing or < 4' and no valid brand): Found value 'length_ft={length_ft}', brand='{brand}', price='{price}'. Link: {link}")
                                is_visible = False
                        
                        ad_data["is_visible"] = is_visible
                        
                        logger.info(f"  > Scraped Data for Ad (is_visible={is_visible}):")
                        log_data = ad_data.copy()
                        for key, value in log_data.items():
                            logger.info(f"    - {key.ljust(15)}: {value}")

                        # Add all ads to database regardless of visibility
                        ad = Ad(**ad_data)
                        db.add(ad)
                        ads_added.append(ad)
                        existing_links.add(link)

                    except Exception as e:
                        logger.error(f"  > Could not process detail page {link}. Error: {e}")
                    
                    time.sleep(random.uniform(20, 40))
            
            time.sleep(random.uniform(10, 20))
    
    if ads_added:
        logger.info(f"Attempting to commit {len(ads_added)} new ads to the database...")
        try:
            db.commit()
            logger.info("Commit successful. Added %d new ads.", len(ads_added))
        except IntegrityError:
            db.rollback()
            logger.warning(
                "Commit failed due to an IntegrityError. "
                "This likely means another process added the same ad(s) concurrently. Rolling back."
            )
            return [] 
        except Exception as e:
            db.rollback()
            logger.error(f"An unexpected error occurred during commit: {e}")
            raise
    else:
        logger.info("No new ads to add in this session.")
        
    return ads_added
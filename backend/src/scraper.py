import json
import random
import re
import time
from datetime import datetime
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.settings import (
    ALLOWED_CATEGORY_IDS,
    DEFAULT_IMAGE_RULE,
    DETAIL_IMAGE_RULE,
    ENABLE_VINTED_SOURCE,
    EQUIPMENT_ACCESSORY_TERMS,
    EXCLUDED_TERMS,
    FOIL_ITEM_TERMS,
    FOIL_PRODUCT_TERMS,
    KITE_HARNESS_TERMS,
    KITE_ITEM_TERMS,
    KITE_PRODUCT_TERMS,
    REQUEST_TIMEOUT as SETTINGS_TIMEOUT,
    SCRAPING_LOG_DIR,
    SEARCH_CONFIGS,
    SKIP_ADS_TERMS,
    VINTED_BASE_URL,
    VINTED_MAX_PAGES_PER_SEARCH,
    VINTED_SEARCH_TERMS,
    build_headers as settings_build_headers,
)
from src import vinted as vinted_source
from src.models import Ad
from extraction.surfboard_parser import parse_listing
from extraction.extraction import (
    BRAND_MAP,
    BRAND_REGEX,
    FRACTION_MAP,
    FRACTION_SYMBOLS,
    POPULAR_BRANDS,
    create_brand_pattern,
    extract_board_dimensions_cm,
    extract_dimensions,
    extract_foil_area_cm2,
    extract_foil_wingspan_cm,
    extract_liters,
    extract_mast_length_cm,
    extract_price,
    extract_wing_area_m2,
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
    # Newer payloads expose a bare 'cdnBaseUrl' that needs the rule appended.
    if image_entry.get('cdnBaseUrl'):
        return _build_image_url(image_entry['cdnBaseUrl'], rule=rule)

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
    value = values[0].get('value')
    return str(value) if value is not None else ""


def _listing_is_complete(parsed):
    """Return True when the parsed listing already carries enough data to skip the detail page."""
    has_identity = bool(parsed.get("brand")) or isinstance(parsed.get("length_ft"), (int, float)) or any(
        parsed.get(key) is not None
        for key in (
            "foil_area_cm2", "mast_length_cm", "foil_wingspan_cm", "wing_area_m2",
            "board_length_cm", "board_width_cm",
        )
    )
    has_metrics = any(
        parsed.get(key) is not None
        for key in (
            "liters",
            "width_in",
            "thickness_in",
            "foil_area_cm2",
            "mast_length_cm",
            "foil_wingspan_cm",
            "wing_area_m2",
            "board_length_cm",
            "board_width_cm",
        )
    )
    return has_identity and has_metrics


def classify_board_type(text):
    """Classify an ad as 'kite', 'foil' or 'surf' based on its text."""
    if not text:
        return "surf"
    lowered = text.lower()
    if re.search(r"(?<!\w)(?:kite|kitesurf|kiteboard|kitefoil|parakite|parawing|lowwing)(?!\w)", lowered):
        return "kite"
    if re.search(
        r"(?<!\w)(?:e[- ]?foil|wing[- ]?foil|hydrofoil|windfoil|surf foil|foilboard|foil)(?!\w)",
        lowered,
    ):
        return "foil"
    return "surf"


def _contains_term(text, term):
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE))


def _contains_any_term(text, terms):
    return any(_contains_term(text, term) for term in terms)


def _model_is_accessory_only(model, board_type):
    """Reject Ads whose title is an accessory, not the requested equipment."""
    if not _contains_any_term(model, EQUIPMENT_ACCESSORY_TERMS):
        return False

    if board_type == "kite" and _contains_any_term(model, KITE_HARNESS_TERMS):
        return False

    if board_type == "foil":
        component_terms = (
            "front wing", "frontwing", "rear wing", "tail wing", "ala anteriore",
            "ala front", "ala posteriore", "stabilizzatore", "stabilizer",
            "fusoliera", "piantone", "mast", "tavola", "board", "set", "kit", "attrezzatura",
        )
        return not _contains_any_term(model, component_terms)

    component_terms = (
        "tavola", "board", "kiteboard", "twintip", "twin tip", "ala", "vela",
        "set", "kit", "attrezzatura", "surfino", "kite",
    )
    return not _contains_any_term(model, component_terms)


def _is_relevant_equipment_ad(text, model, board_type, parsed):
    """Return whether a foil/kite Ad has an equipment or size signal."""
    if board_type not in {"foil", "kite"}:
        return True
    if _model_is_accessory_only(model, board_type):
        return False
    if board_type == "kite" and _contains_any_term(model, KITE_HARNESS_TERMS):
        return True

    has_dimension = any(
        parsed.get(key) is not None
        for key in (
            "foil_area_cm2", "mast_length_cm", "foil_wingspan_cm", "wing_area_m2",
            "board_length_cm", "board_width_cm",
        )
    )
    if has_dimension or parsed.get("brand"):
        return True

    if board_type == "foil":
        component_terms = (
            "front wing", "frontwing", "rear wing", "tail wing", "ala anteriore",
            "ala front", "ala posteriore", "stabilizzatore", "stabilizer",
            "fusoliera", "piantone", "mast", "tavola", "board", "set foil", "kit foil",
            "vela wing", "ala wing",
        )
        configured_terms = tuple(
            term for term in FOIL_ITEM_TERMS
            if term not in {"foil", "hydrofoil", "wingfoil", "wing foil", "windfoil", "efoil", "e-foil"}
        ) + tuple(FOIL_PRODUCT_TERMS)
    else:
        component_terms = (
            "tavola", "board", "kiteboard", "twintip", "twin tip", "ala", "vela",
            "set", "kit", "attrezzatura", "surfino",
        )
        configured_terms = tuple(
            term for term in KITE_ITEM_TERMS
            if term not in {"kite", "kitesurf", "kite surf"}
        ) + tuple(KITE_PRODUCT_TERMS)
    return _contains_any_term(text, component_terms) or _contains_any_term(text, configured_terms)


def classify_equipment_type(text, model=None):
    """Classify a relevant Ad into a frontend-friendly equipment component."""
    if not text:
        return "other"
    title = model or text
    if _contains_any_term(title, KITE_HARNESS_TERMS):
        return "harness"
    if re.search(
        r"(?<!\w)(?:tavola|board|kiteboard|foilboard|twintip|twin tip|surfino)(?!\w)",
        title,
        re.IGNORECASE,
    ):
        return "board"
    if _contains_any_term(
        text,
        (
            "front wing", "frontwing", "rear wing", "tail wing", "ala anteriore",
            "ala front", "ala posteriore", "stabilizzatore", "stabilizer", "fusoliera",
            "piantone", "mast",
        ),
    ):
        return "foil"
    if re.search(r"(?<!\w)(?:ala|vela|wing|parawing|lowwing)(?!\w)", title, re.IGNORECASE):
        return "wing"
    if classify_board_type(text) == "foil":
        return "foil"
    if classify_board_type(text) == "kite":
        return "kite"
    return "other"


def _reconcile_existing_ad(ad, text):
    """Re-evaluate an existing Ad after classification or visibility rules change."""
    combined_text = f"{ad.model or ''} {text or ''}".strip()
    parsed = parse_listing(combined_text)
    board_type = classify_board_type(combined_text)
    equipment_type = classify_equipment_type(combined_text, ad.model)

    if _contains_any_term(combined_text, SKIP_ADS_TERMS):
        is_visible = False
    elif board_type in {"foil", "kite"}:
        is_visible = _is_relevant_equipment_ad(combined_text, ad.model or "", board_type, parsed)
    else:
        has_excluded_term = _contains_any_term(combined_text, EXCLUDED_TERMS)
        length_ft = parsed.get("length_ft") or ad.length_ft
        brand = parsed.get("brand") or ad.brand
        is_visible = not has_excluded_term and (
            (isinstance(length_ft, (int, float)) and length_ft >= 4)
            or bool(isinstance(brand, str) and brand.strip())
        )

    changed = False
    for key, value in (
        ("board_type", board_type),
        ("equipment_type", equipment_type),
        ("is_visible", is_visible),
    ):
        if getattr(ad, key) != value:
            setattr(ad, key, value)
            changed = True

    # Search cards may now carry fields that were unavailable when the Ad was
    # first stored. Never erase richer values just because this card is sparse.
    for key in (
        "brand", "liters", "length_ft", "length_in", "width_in", "thickness_in",
        "foil_area_cm2", "mast_length_cm", "foil_wingspan_cm", "wing_area_m2",
        "board_length_cm", "board_width_cm",
    ):
        value = parsed.get(key)
        if value is not None and getattr(ad, key) != value:
            setattr(ad, key, value)
            changed = True

    return changed


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
    # Current Subito cards use hashed classes on article elements; use the
    # semantic element and child tags instead of relying on class names.
    containers = soup.find_all("article")
    # Fallback for legacy fixtures/tests using div.item-card.
    if not containers:
        containers = soup.find_all("div", class_="item-card")
    listings = []
    for container in containers:
        link_tag = container.find("a", href=True)
        if not link_tag:
            continue
        link = link_tag['href']
        title_tag = container.find(["h3", "h2"])
        if not title_tag:
            continue
        model = title_tag.get_text(strip=True) if title_tag else "N/A"
        full_text = container.get_text(" ", strip=True)
        location_tag = container.find(
            ["span", "p"],
            class_=lambda classes: classes and "location" in (
                classes.lower() if isinstance(classes, str) else " ".join(classes).lower()
            ),
        )
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
                'location_text': location_tag.get_text(strip=True) if location_tag else None,
            }
        )
    return listings

search_configs = list(SEARCH_CONFIGS)

_PARSED_ATTRIBUTE_KEYS = (
    "brand",
    "liters",
    "length_ft",
    "length_in",
    "width_in",
    "thickness_in",
    "foil_area_cm2",
    "mast_length_cm",
    "foil_wingspan_cm",
    "wing_area_m2",
    "board_length_cm",
    "board_width_cm",
)

_SURF_KEYWORDS = [
    "tavola", "surf", "softboard", "longboard",
    "shortboard", "wingfoil", "foil", "kite",
    "kitesurf", "kiteboard", "surfboard", "parakite", "parawing", "lowwing",
]


def _detail_image_url(marketplace, seed_url, detail_soup):
    """Resolve the best image URL from a detail page, per marketplace."""
    if marketplace == "vinted":
        if seed_url:
            return seed_url
        og_image = detail_soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            candidate = og_image["content"].strip()
            return candidate or None
        return None
    return _ensure_image_url(seed_url, detail_soup)


def _ingest_listing(
    db,
    listing,
    *,
    referrer_url,
    location_fallback,
    existing_links,
    existing_ads,
    fetch_detail,
):
    """Filter, parse and store a single raw listing.

    Shared by the Subito and Vinted passes so both sources follow the same
    classification, visibility-storage and reconciliation rules.

    Returns ``(new_ad_or_None, existing_ad_changed)``.
    """
    link = listing.get("link")
    if not link:
        return None, False

    logger.info("-" * 60)
    logger.info(
        "Processing ad link: %s (source=%s)",
        link,
        listing.get("source"),
    )

    if link in existing_links:
        existing_ad = existing_ads.get(link)
        changed = False
        if existing_ad is not None:
            changed = _reconcile_existing_ad(
                existing_ad, listing.get("full_text") or ""
            )
        logger.info("Skipping ad, already in database: %s", link)
        return None, changed

    full_text = listing.get("full_text") or ""
    model = listing.get("model") or "N/A"
    marketplace = listing.get("marketplace") or "subito"

    # Hard-skip: board categories the user does not want at all
    # (snowboard, windsurf, SUP, skate, wake, bodyboard, ...).
    skipped_category = next(
        (
            term
            for term in SKIP_ADS_TERMS
            if re.search(rf"\b{re.escape(term)}\b", full_text, re.IGNORECASE)
        ),
        None,
    )
    if skipped_category:
        logger.info(
            "Skipping ad %s: belongs to skipped category '%s'",
            link,
            skipped_category,
        )
        return None, False

    if "sacca" in model.lower():
        logger.info("Skipping ad %s: title contains 'sacca'", link)
        return None, False

    if not any(kw in full_text.lower() for kw in _SURF_KEYWORDS):
        logger.info("Skipping ad %s: not surf/foil/kite-related", link)
        return None, False

    ad_data = {
        "source": marketplace,
        "model": model,
        "price": extract_price(full_text),
        "location": listing.get("location_text") or location_fallback,
        "link": link,
        "brand": None,
        "image_url": listing.get("image_url"),
    }

    needs_detail = False
    try:
        # Parse attributes straight from the search listing text first.
        # Subito's __NEXT_DATA__ payload already embeds the full ad body, so
        # most ads can be captured without a detail-page round-trip. This
        # keeps the request footprint low and reduces the chance of being
        # blocked.
        parsed = parse_listing(full_text)
        for key in _PARSED_ATTRIBUTE_KEYS:
            ad_data[key] = parsed[key]

        needs_detail = not _listing_is_complete(parsed)
        desc_text = ""
        if needs_detail:
            detail_resp = fetch_detail(link, referrer=referrer_url, max_attempts=2)
            if detail_resp is None:
                logger.error("  > Could not fetch detail page after retries: %s", link)
            else:
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                detail_image = _detail_image_url(
                    marketplace, ad_data.get("image_url"), detail_soup
                )
                if detail_image:
                    ad_data["image_url"] = detail_image

                if marketplace == "vinted":
                    desc_text = vinted_source.strip_price_mentions(
                        vinted_source.extract_detail_description(detail_soup)
                    )
                else:
                    desc_div = detail_soup.find(
                        "p", class_=lambda c: c and "description" in c.lower()
                    )
                    desc_text = (
                        desc_div.get_text(separator=" ", strip=True) if desc_div else ""
                    )

                if desc_text:
                    full_desc_text = f"{ad_data['model']} {desc_text}"
                    parsed = parse_listing(full_desc_text)
                    for key in _PARSED_ATTRIBUTE_KEYS:
                        ad_data[key] = parsed[key]

        full_desc_text = (
            f"{ad_data['model']} {desc_text}".strip() if desc_text else full_text
        ) or ad_data["model"]

        # Classify the board type: kite, foil, or surf.
        ad_data["board_type"] = classify_board_type(full_desc_text)
        ad_data["equipment_type"] = classify_equipment_type(full_desc_text, model)

        # Check if ad should be visible based on criteria
        is_visible = True

        # Accessory mentions hide surf Ads, but complete foil/kite packages
        # commonly include a bag or wetsuit.
        if ad_data["board_type"] == "surf":
            for term in EXCLUDED_TERMS:
                if re.search(rf"\b{re.escape(term)}\b", full_desc_text, re.IGNORECASE):
                    logger.info(
                        "Marking ad as not visible %s: contains excluded term '%s'",
                        link,
                        term,
                    )
                    is_visible = False
                    break

        # Apply a sport-specific gate. Surf Ads retain the established
        # length/brand rule; foil and kite Ads need an equipment component,
        # known brand, or metric.
        if is_visible:
            if ad_data["board_type"] in {"foil", "kite"}:
                if not _is_relevant_equipment_ad(
                    full_desc_text,
                    model,
                    ad_data["board_type"],
                    ad_data,
                ):
                    logger.warning(
                        "  > Marking %s Ad as not visible: no equipment signal found",
                        link,
                    )
                    is_visible = False
            else:
                length_ft = ad_data.get("length_ft")
                brand = ad_data.get("brand")
                price = ad_data.get("price")
                valid_length = isinstance(length_ft, (int, float)) and length_ft >= 4
                valid_brand = isinstance(brand, str) and brand.strip()
                if not (valid_length or valid_brand):
                    logger.warning(
                        "  > Marking ad as not visible (length_ft is missing or < 4' "
                        "and no valid brand): Found value 'length_ft=%s', brand='%s', "
                        "price='%s'. Link: %s",
                        length_ft,
                        brand,
                        price,
                        link,
                    )
                    is_visible = False

        ad_data["is_visible"] = is_visible

        logger.info("  > Scraped Data for Ad (is_visible=%s):", is_visible)
        log_data = ad_data.copy()
        for key, value in log_data.items():
            logger.info("    - %s: %s", key.ljust(15), value)

        # Add all ads to database regardless of visibility.
        ad = Ad(**ad_data)
        db.add(ad)
        existing_links.add(link)
        return ad, False

    except Exception as e:
        logger.error("  > Could not process detail page %s. Error: %s", link, e)
        return None, False
    finally:
        # Deeper politeness pause after an actual detail-page request.
        if needs_detail:
            time.sleep(random.uniform(20, 40))
        else:
            time.sleep(random.uniform(4, 8))


def _scrape_vinted(
    db,
    *,
    fetch_with_resilience,
    existing_links,
    existing_ads,
):
    """Scrape the opt-in Vinted source and ingest its listings."""
    ads_added = []
    existing_ads_changed = False

    for term in VINTED_SEARCH_TERMS:
        base_url = f"{VINTED_BASE_URL}?search_text={quote_plus(term)}"
        for page_num in range(1, VINTED_MAX_PAGES_PER_SEARCH + 1):
            url = f"{base_url}&page={page_num}"
            logger.info(f"Scraping Vinted search results from: {url}")
            time.sleep(random.uniform(2, 5))

            response = fetch_with_resilience(
                url,
                referrer=base_url if page_num == 1 else f"{base_url}&page={page_num - 1}",
            )
            if response is None:
                logger.error(f"Failed to fetch {url} after retries. Skipping page.")
                break
            if response.status_code != 200:
                logger.error(f"Failed to fetch {url}. Status: {response.status_code}")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            listings = vinted_source.extract_listings_from_html(soup)
            logger.info(
                "Found %d potential Vinted ad listings on page %d.",
                len(listings),
                page_num,
            )
            if not listings:
                logger.info(
                    f"No more Vinted ads found on page {page_num}. Moving to next search term."
                )
                break

            for listing in listings:
                ad, changed = _ingest_listing(
                    db,
                    listing,
                    referrer_url=url,
                    location_fallback="Italy",
                    existing_links=existing_links,
                    existing_ads=existing_ads,
                    fetch_detail=fetch_with_resilience,
                )
                if ad is not None:
                    ads_added.append(ad)
                existing_ads_changed = existing_ads_changed or changed

        time.sleep(random.uniform(10, 20))

    return ads_added, existing_ads_changed


def scrape_and_store(db: Session):
    ads_added = []

    logger.info("Fetching existing ad links from the database...")
    existing_rows = db.query(Ad).all()
    existing_links = {
        row[0] if isinstance(row, tuple) else row.link
        for row in existing_rows
    }
    existing_ads = {
        row.link: row
        for row in existing_rows
        if hasattr(row, "link")
    }
    existing_ads_changed = False
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
                    ad, changed = _ingest_listing(
                        db,
                        listing,
                        referrer_url=url,
                        location_fallback=city.replace("-", " ").capitalize(),
                        existing_links=existing_links,
                        existing_ads=existing_ads,
                        fetch_detail=fetch_with_resilience,
                    )
                    if ad is not None:
                        ads_added.append(ad)
                    existing_ads_changed = existing_ads_changed or changed

            time.sleep(random.uniform(10, 20))

        # Opt-in Vinted pass, sharing the same ingestion pipeline.
        if ENABLE_VINTED_SOURCE:
            vinted_ads, vinted_changed = _scrape_vinted(
                db,
                fetch_with_resilience=fetch_with_resilience,
                existing_links=existing_links,
                existing_ads=existing_ads,
            )
            ads_added.extend(vinted_ads)
            existing_ads_changed = existing_ads_changed or vinted_changed

    if ads_added or existing_ads_changed:
        logger.info(
            "Attempting to commit %d new Ads and existing-Ad updates to the database...",
            len(ads_added),
        )
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

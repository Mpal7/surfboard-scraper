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
from models import Ad
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
        item = entry.get('item') or entity_items.get(entry.get('urn')) or {}
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

# Constants
FRACTION_SYMBOLS = {
    'Â¼': ' 1/4', 'Â½': ' 1/2', 'Â¾': ' 3/4',
    '¼': ' 1/4', '½': ' 1/2', '¾': ' 3/4',
    '⅛': ' 1/8', '⅜': ' 3/8', '⅝': ' 5/8', '⅞': ' 7/8'
}

FRACTION_MAP = {
    '1/2': 0.5, '1/4': 0.25, '3/4': 0.75,
    '1/8': 0.125, '3/8': 0.375, '5/8': 0.625, '7/8': 0.875
}

POPULAR_BRANDS = [
    'slater designs', 'hayden shapes', 'channel islands', 'al merrick',
    'js industries', 'bruce hansel', 'luke studer', 'stefan steinberger',
    'catch surf', 'prescription', 'x surfboard', 'log machine', 'lightning bolt',
    'channel island', 'steinberger', 'sharpeye', 'jetsurf', 'surftech',
    'firewire', 'bradley', 'outride', 'victory', 'mayhem', 'olaian',
    'pukas', 'steve lis', 'stefan', 'hayden', 'lost', 'pyzel', 'rrd',
    'torq', 'mccoy', 'dhd', 'bic', 'sic', 'nsp', 'bob', 'hs', 'js', 'rt',
    'cj nelson', 'shaper x', 'ocean earth', 'Ocean&Earth', 'redz', 'quicksilver',
    'tomo', 'rusti', 'chilli', 'franz', 'all merick', 'al merrick', 'al merrik',
    'all merrik','chanell island', 'full and cas', 'full & cas', 'full&cas', 'collective',
    'reds', 'town & country', 'town&country', 'town and country', 'M.A.T',
    'bushman', 'xd2', 'red’s', 'reds' 'duppies', 'xsurfboards', 'xsurfboard',
    'gerry lopez', 'saints', 'peterpan', 'peter pan', 'Devil’s Tongue', 'Aztron',
    'honu', 'quiksilver', 'mckee', 'Andrea X', 'alessio fantozzi', 'indio', 'semente',
    'XDII', 'LSD', "scott burke", "tahe", "album", "ryan lovelace", 'alibi', 'pike',
    'webber', 'infinity','sundek', 'duppies', 'rickland', 'odysea', 'clay','clayton', 'Rusty',
    'wave', 'wp', 'spider'
]

# 2. Create a map for correct capitalization.
BRAND_MAP = {brand.lower(): ' '.join([w.capitalize() for w in brand.split()]) for brand in POPULAR_BRANDS}

# Manual override for brands with special capitalization
BRAND_MAP['js'] = 'JS'
BRAND_MAP['hs'] = 'HS'
BRAND_MAP['bob'] = 'BOB'
BRAND_MAP['rt'] = 'RT'
BRAND_MAP['rrd'] = 'RRD'
BRAND_MAP['cj nelson'] = 'CJ Nelson'
BRAND_MAP['shaper x'] = 'X Surfboard'
BRAND_MAP['andrea x'] = "X Surfboard"
BRAND_MAP['xsurfboards'] = 'X Surfboard'
BRAND_MAP['xsurfboard'] = 'X Surfboard'
BRAND_MAP['XD2'] = 'X Surfboard'
BRAND_MAP['XDII'] = 'X Surfboard'
BRAND_MAP['ocean earth'] = 'Ocean & Earth'
BRAND_MAP['lost'] = 'Lost Mayhem'  
BRAND_MAP['mayhem'] = 'Lost Mayhem'
BRAND_MAP['all merick'] = 'Channel Islands - Al Merrik'
BRAND_MAP['al merrik'] = 'Channel Islands - Al Merrik'
BRAND_MAP['al merrick'] = 'Channel Islands - Al Merrik'
BRAND_MAP['all merrick'] = 'Channel Islands - Al Merrik'
BRAND_MAP['chanell island'] = 'Channel Islands - Al Merrik'
BRAND_MAP['full and cas'] = 'Full&Cas'
BRAND_MAP['full & cas'] = 'Full&Cas'
BRAND_MAP['town & country'] = 'Town&Country'
BRAND_MAP['town and country'] = 'Town&Country'
BRAND_MAP['Red’s'] = "Redz"
BRAND_MAP['reds'] = "Redz"
BRAND_MAP['Peterpan'] = "Peter Pan"
BRAND_MAP['quiksilver'] = "Quicksilver"
BRAND_MAP['Rusti'] = 'Rusty'
BRAND_MAP['Clay'] = 'Clayton'

# Build a single, efficient, case-insensitive regex from the brand list.
def create_brand_pattern(brand_key):
    """
    Takes a brand name like "Channel Islands - Al Merrik" and returns a regex pattern
    like "channel\\s*islands" that matches with or without spaces.
    """
    # 1. Split into words: "channel", "islands"
    parts = brand_key.split(' ')
    # 2. Escape each part to treat special characters literally
    escaped_parts = [re.escape(part) for part in parts]
    # 3. Join with \s* to allow zero or more spaces between words
    return r'\s*'.join(escaped_parts)

# Create a pattern for each brand in our map
brand_patterns = (create_brand_pattern(key) for key in BRAND_MAP.keys())

# Join all individual brand patterns with '|' (OR)
BRAND_REGEX = re.compile(
    r"\b(" + "|".join(brand_patterns) + r")\b",
    re.IGNORECASE
)

def find_brand(text):
    """
    Finds the first matching brand in the text using a pre-compiled regex
    that matches only whole words and handles flexible spacing for multi-word brands.
    """
    match = BRAND_REGEX.search(text)
    if match:
        # To find the correct key for BRAND_MAP, we remove all whitespace
        # from the matched text and convert to lowercase.
        matched_text = match.group(1)
        normalized_key = "".join(matched_text.split()).lower()

        # The BRAND_MAP keys also need to be normalized in the same way for lookup.
        for key, value in BRAND_MAP.items():
            if "".join(key.split()) == normalized_key:
                return value
    return None

def text_pre_processor(text):
    """Normalize text for parsing while avoiding over-aggressive replacements."""
    # Normalize unicode fraction characters into ascii ' 1/4' etc.
    for sym, repl in FRACTION_SYMBOLS.items():
        text = text.replace(sym, repl)
    
    # Normalize variant apostrophes and double-quotes to standard ones
    text = re.sub(r"[’′`]", "'", text)
    text = re.sub(r"[“”˝″]", '"', text)
    
    # Normalize separators: only map explicit 'x' or multiplication symbols to ' x '
    text = re.sub(r'\s*[xX×*]\s*', ' x ', text)

    # Remove explicit unit words, including when attached to digits (e.g. '6ft', '21.25in')
    # Added Italian 'pollici' / 'pollice' to the list of inch words to drop after digits.
    text = re.sub(r'(?<=\d)(?:\s*)(?:ft|foot|feet)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?<=\d)(?:\s*)(?:in|inch|inches|pollici|pollice)\b', '', text, flags=re.IGNORECASE)

    # normalize cm to token (keep cm token so metric detection can still apply)
    text = re.sub(r'(?<=\d)(?:\s*)(?:cm|centimeters|centimetri)\b', 'cm', text, flags=re.IGNORECASE)
    
    # Collapse repeated spaces and tidy
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_for_matching(text):
    """
    Lightweight normalization focused on matching numeric dimensions reliably in live HTML.
    It purposely avoids heavy transformations that would interfere with unit words.
    """
    if not text:
        return text
    # remove common invisible / zero-width characters and NBSP
    text = text.replace('\u00A0', ' ').replace('\u200B', '').replace('\u200C', '')
    text = text.replace('\uFEFF', '')

    # replace common dot-like unicode characters with ASCII dot
    dot_variants = ['\u00B7', '\u2024', '\u2027', '\u22C5', '\u2219', '\u30FB', '\uFF0E', '\u2022']
    for dv in dot_variants:
        text = text.replace(dv, '.')

    # also common visible variants
    text = text.replace('·', '.').replace('•', '.')

    # Normalize variant apostrophes and double-quotes to standard ones
    text = re.sub(r"[’‘′`]", "'", text)
    text = re.sub(r"[“”˝″]", '"', text)

    # collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_dimension_part(part):
    """Convert a dimension piece like '21 1/4' or '2 1/2' to float inches."""
    if not part:
        return None
    part = part.strip()
    total = 0.0

    # Handle compact forms like '19/14' which often mean 19 + 1/4.
    compact = re.match(r"^(?P<int>\d{1,2})/(?P<frac>1?4)$", part)
    if compact:
        total += float(compact.group("int"))
        total += 0.25
        return total

    # fraction like '1/4'
    fraction_match = re.search(r'(\d/\d)', part)
    if fraction_match:
        f = fraction_match.group(1)
        total += FRACTION_MAP.get(f, 0.0)
        part = part.replace(f, '').strip()
    # tokens like '1/2'
    token_match = re.search(r'\b(1/4|1/2|3/4|1/8|3/8|5/8|7/8)\b', part)
    if token_match and not fraction_match:
        f = token_match.group(1)
        total += FRACTION_MAP.get(f, 0.0)
        part = part.replace(f, '').strip()
    # integer or decimal part
    if part:
        m = re.match(r'(\d{1,3}(?:[.,]\d+)?)', part)
        if m:
            try:
                total += float(m.group(1).replace(',', '.'))
            except:
                pass
    return total if total != 0.0 else None


def extract_dimensions(text):
    """Main extraction for length / width / thickness (US inches + feet).
    """
    if not text:
        return None

    original = normalize_for_matching(text)
    
    text_for_parsing = re.sub(r'\s*\([^)]*\)', '', original)

    isolated = None

    # Try explicit feet'inches like 5'6 or with comma/dot like 5,11 or 5.11
    m = re.search(r"\b(?P<ft>\d{1,2})\s*(?:'|’|′)\s*(?P<in>\d{1,2})?", text_for_parsing)
    if not m:
        m = re.search(r"\b(?P<ft>\d{1,2})[.,](?P<in>\d{1,2})(?=\D|$)", text_for_parsing)

    if m:
        try:
            ft = int(m.group('ft'))
            inch_str = m.group('in')
            inch = int(inch_str) if inch_str else 0
            if 4 <= ft <= 10 and 0 <= inch <= 11:
                isolated = {'ft': ft, 'in': inch}
        except Exception:
            isolated = None

    processed = text_pre_processor(text_for_parsing)

    pattern = (
        r"(?<!/)"
        r"(?P<length>\d{1,2}(?:['\".,]\d{1,2})?)['\"]*\s*x\s+"
        r"(?P<width>\d{1,3}(?:[.,]\d+)?(?:\s+\d/\d|/\d{1,2})?)['\"]*"
        r"(?:\s*x\s+(?P<thickness>\d{1,2}(?:[.,]\d+)?(?:\s+\d/\d|/\d{1,2})?))?['\"]*"
    )

    matches = list(re.finditer(pattern, processed, re.IGNORECASE))
    full_match = matches[-1] if matches else None

    if full_match:
        data = full_match.groupdict()
        len_str = (data.get('length') or '').strip()
        thickness_val = parse_dimension_part(data.get('thickness') or '')
        width_val = parse_dimension_part(data.get('width') or '')
        
        # if width looks unrealistic for inches (e.g. > 25) try to interpret as metric fallback
        if width_val is not None and width_val > 25:
            if len_str and ("," in len_str or "." in len_str):
                try:
                    meters_val = float(len_str.replace(',', '.'))
                    length_in_total = meters_val * 39.3701
                    return {
                        'length_ft': int(length_in_total // 12),
                        'length_in': int(round(length_in_total % 12)),
                        'width_in': round(width_val * 0.393701, 2),
                        'thickness_in': thickness_val,
                    }
                except Exception:
                    pass
            if isolated:
                return {
                    'length_ft': isolated['ft'],
                    'length_in': isolated['in'],
                    'width_in': None,
                    'thickness_in': None
                }
            return None

        length_ft = None; length_in = None
        if "'" in len_str or '"' in len_str:
            parts = re.split(r'[\'"]', len_str)
            try:
                length_ft = int(parts[0])
                length_in = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            except:
                length_ft, length_in = None, None
        elif '.' in len_str or ',' in len_str:
            sep = '.' if '.' in len_str else ','
            p = len_str.split(sep)
            try:
                length_ft = int(p[0])
                length_in = int(p[1]) if p[1] else 0
            except:
                length_ft, length_in = None, None
        else:
            try:
                length_ft = int(float(len_str)) if len_str else None; length_in = 0
            except:
                length_ft, length_in = None, None

        # Heuristic: if full_match's parsed feet looks suspicious, prefer the isolated ft/in we detected earlier.
        suspicious = False
        try:
            # outside plausible feet range for surfboards
            if length_ft is None or not (4 <= length_ft <= 10):
                suspicious = True
            # if the parsed "feet" equals the isolated inches (e.g. parsed 10 or 11), it's likely the regex
            # matched beginning on the inches token instead of the feet token.
            if isolated and isinstance(length_ft, int) and length_ft == isolated['in']:
                suspicious = True
        except Exception:
            suspicious = False

        if suspicious and isolated:
            return {
                'length_ft': isolated['ft'],
                'length_in': isolated['in'],
                'width_in': width_val,
                'thickness_in': thickness_val
            }

        return {
            'length_ft': length_ft,
            'length_in': length_in,
            'width_in': width_val,
            'thickness_in': thickness_val
        }

    # Metric-like pattern such as "1,83 x 55" (meters x cm)
    metric_m_cm = re.search(r"(?P<m>\d{1},\d{1,2})\s*x\s*(?P<cm>\d{2,3})(?!\d)", processed)
    if metric_m_cm:
        try:
            meters = float(metric_m_cm.group('m').replace(',', '.'))
            cm_width = float(metric_m_cm.group('cm'))
            length_in_total = meters * 39.3701
            return {
                'length_ft': int(length_in_total // 12),
                'length_in': int(round(length_in_total % 12)),
                'width_in': round(cm_width * 0.393701, 2),
                'thickness_in': None,
            }
        except Exception:
            pass

    # Named Italian fields: lunghezza / larghezza / spessore without x separators.
    m_lung = re.search(r"lunghezza\s*(?P<len>\d{1,2}(?:[.,]\d{1,2})?)", text_for_parsing, re.IGNORECASE)
    m_larg = re.search(r"larghezza\s*(?P<wid>\d{1,2}(?:\s+\d/\d|/\d{1,2}|[.,]\d{1,2})?)", text_for_parsing, re.IGNORECASE)
    m_spess = re.search(r"spessore\s*(?P<thk>\d{1,2}(?:\s+\d/\d|/\d{1,2}|[.,]\d{1,2})?)", text_for_parsing, re.IGNORECASE)
    if m_lung:
        len_token = m_lung.group('len')
        length_ft, length_in = None, None
        if '.' in len_token or ',' in len_token:
            sep = '.' if '.' in len_token else ','
            parts = len_token.split(sep)
            try:
                length_ft = int(parts[0]); length_in = int(parts[1]) if parts[1] else 0
            except Exception:
                length_ft, length_in = None, None
        else:
            try:
                length_ft = int(len_token); length_in = 0
            except Exception:
                length_ft, length_in = None, None

        width_in = parse_dimension_part(m_larg.group('wid')) if m_larg else None
        thickness_in = parse_dimension_part(m_spess.group('thk')) if m_spess else None

        if isolated:
            return {
                'length_ft': isolated['ft'],
                'length_in': isolated['in'],
                'width_in': width_in,
                'thickness_in': thickness_in,
            }

        return {
            'length_ft': length_ft,
            'length_in': length_in,
            'width_in': width_in,
            'thickness_in': thickness_in,
        }

    if isolated:
        return {
            'length_ft': isolated['ft'],
            'length_in': isolated['in'],
            'width_in': None,
            'thickness_in': None
        }

    m_ft_only = re.search(r"\b(?P<ft>\d{1,2})\s*(?:ft|feet|foot|piedi)\b", text_for_parsing, re.IGNORECASE)
    if m_ft_only:
        try:
            ft = int(m_ft_only.group('ft'))
            if 4 <= ft <= 10:
                return {'length_ft': ft, 'length_in': 0, 'width_in': None, 'thickness_in': None}
        except:
            pass

    if re.search(r'\b(misur[ae]|misura|misure|lunghezza|size)\b', text_for_parsing, re.IGNORECASE):
        m_num = re.search(r"\b(misur[ae]|misura|misure|lunghezza|size)\s*[:]?\s*(?P<ft>\d{1,2})\b", text_for_parsing, re.IGNORECASE)
        if m_num:
            try:
                ft = int(m_num.group('ft'))
                if 4 <= ft <= 10:
                    return {'length_ft': ft, 'length_in': 0, 'width_in': None, 'thickness_in': None}
            except:
                pass

    metric_match = re.search(r'(\d{3,})\s*x\s+(\d{2,}(?:[.,]\d+)?)\s*x\s+(\d(?:[.,]\d+)?)', processed)
    if metric_match:
        try:
            cm_to_inch = 0.393701
            length_in_total = float(metric_match.group(1)) * cm_to_inch
            return {
                'length_ft': int(length_in_total // 12),
                'length_in': int(length_in_total % 12),
                'width_in': float(metric_match.group(2)) * cm_to_inch,
                'thickness_in': float(metric_match.group(3)) * cm_to_inch
            }
        except:
            pass

    m_apost = re.search(r"[‘’']\s*(?P<ft>\d{1,2})(?!\d)", text_for_parsing)
    if m_apost:
        try:
            ft = int(m_apost.group('ft'))
            if 4 <= ft <= 10:
                return {'length_ft': ft, 'length_in': 0, 'width_in': None, 'thickness_in': None}
        except:
            pass
    
    m_slash = re.search(r"(?P<ft>\d{1,2})\s*/\s*(?P<in>\d{1,2})", text_for_parsing)
    if m_slash:
        try:
            ft = int(m_slash.group('ft'))
            inch = int(m_slash.group('in'))
            if 4 <= ft <= 10 and 0 <= inch < 12:
                return {'length_ft': ft, 'length_in': inch, 'width_in': None, 'thickness_in': None}
        except:
            pass

    m_cm = re.search(r"(?P<cm>\d{2,3})\s*cm", text_for_parsing)
    if m_cm:
        try:
            cm = int(m_cm.group('cm'))
            if 120 <= cm <= 300:
                total_inches = round(cm / 2.54)
                ft = total_inches // 12
                inch = total_inches % 12
                return {'length_ft': ft, 'length_in': inch, 'width_in': None, 'thickness_in': None}
        except:
            pass

    m_decimal_fallback = re.search(r"\b(?P<ft>\d{1,2})[.,](?P<in>\d{1,2})(?!\d)", text_for_parsing)
    if m_decimal_fallback:
        try:
            ft = int(m_decimal_fallback.group('ft'))
            inch = int(m_decimal_fallback.group('in'))
            if 4 <= ft <= 10 and 0 <= inch <= 11:
                return {'length_ft': ft, 'length_in': inch, 'width_in': None, 'thickness_in': None}
        except:
            pass

    return None
    
def extract_liters(text):
    pattern = re.compile(
        r"(?:\b(?:volume|vol)\b\s*)?"
        r"(?:(?P<num1>\d{1,3}(?:[.,]\d{1,2})?)\s*(?:l\b|lt\b|ltr\b|liters?\b|litres?\b|litri\b)"
        r"|(?:l\b|lt\b|ltr\b|liters?\b|litres?\b|litri\b)\s*(?P<num2>\d{1,3}(?:[.,]\d{1,2})?))",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    value = match.group('num1') or match.group('num2')
    try:
        return float(value.replace(',', '.'))
    except Exception:
        return None

def extract_price(text):
    """
    Extract numeric price from strings like:
      - "1500 €"
      - "1.500 €"         (EU thousands separator)
      - "1.500,50 €"      (EU decimal comma)
      - "1,500.50 €"      (US style)
      - "1 500 €"         (space thousands sep)
    Returns float or None.
    """
    match = re.search(r'([\d.,]+)\s*(?:€|euro|\u20AC)', text, re.IGNORECASE)
    if not match:
        return None
    s = match.group(1).strip()
    s = re.sub(r'[^\d\.,]', '', s)

    # If both dot and comma present -> decide decimal by last occurrence
    if '.' in s and ',' in s:
        # whichever separator appears last is the decimal separator
        if s.rfind(',') > s.rfind('.'):
            # comma is decimal: remove dots (thousand sep) and turn comma -> dot
            s = s.replace('.', '').replace(',', '.')
        else:
            # dot is decimal: remove commas (thousand sep)
            s = s.replace(',', '')
    elif '.' in s:
        # single dot: ambiguous. If dot is followed by exactly 3 digits -> treat as thousands sep
        parts = s.split('.')
        if len(parts) > 1 and len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            s = s.replace('.', '')  # thousand separators
        # else keep dot as decimal point (like "1500.50" or "1.5")
    elif ',' in s:
        # single comma -> decimal separator (common EU format)
        s = s.replace(',', '.')
    # otherwise plain integer string "1500"

    try:
        return float(s)
    except Exception:
        return None

def scrape_and_store(db: Session):
    ads_added = []
    
    logger.info("Fetching existing ad links from the database...")
    existing_links = {result[0] for result in db.query(Ad.link).all()}
    logger.info(f"Found {len(existing_links)} existing links.")

    configs = list(search_configs)
    random.shuffle(configs)

    with httpx.Client(follow_redirects=True, http2=True, timeout=REQUEST_TIMEOUT) as client:
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

                        # Extract brand and dimensions first
                        ad_data["brand"] = find_brand(full_desc_text)
                        ad_data["liters"] = extract_liters(full_desc_text)
                        dims = extract_dimensions(full_desc_text)
                        if dims:
                             ad_data.update(dims)
                        
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
                        if dims: log_data.update(dims)
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
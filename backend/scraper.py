import re
import random
import time
import httpx
from bs4 import BeautifulSoup
from models import Ad
from sqlalchemy.orm import Session
import logging
from datetime import datetime
import os  

# --- 1. Logging Configuration ---

LOG_DIR = "scraping_logs"

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Prevent handlers from being added multiple times if the script is re-imported
if not logger.handlers:
    # Create a file handler that logs to a file named with the current date
    log_filename = os.path.join(LOG_DIR, f"scraping_{datetime.now().strftime('%Y-%m-%d')}.log")
    file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    # Create a console handler to also print logs to the terminal
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create a formatter and set it for both handlers
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# --- 2. Headers and Search Constants ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
    'Referer': 'https://www.subito.it/',
    'Sec-Ch-Ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
}

SEARCH_URLS = [
    "https://www.subito.it/annunci-lazio/vendita/usato/roma/roma/?q=tavola+da+surf",
    "https://www.subito.it/annunci-lazio/vendita/usato/roma/roma/?q=surfboard",
]

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
    'cj nelson', 'shaper x', 'ocean earth', 'Ocean&Earth', 'redz'
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
BRAND_MAP['ocean earth'] = 'Ocean & Earth'


# Build a single, efficient, case-insensitive regex from the brand list.
def create_brand_pattern(brand_key):
    """
    Takes a brand name like "channel islands" and returns a regex pattern
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
        r"(?P<length>\d{1,2}(?:['.]\d{1,2})?)['\"]*\s*x\s+"
        r"(?P<width>\d{1,3}(?:[.,]\d+)?(?:\s+\d/\d)?)['\"]*"
        r"(?:\s*x\s+(?P<thickness>\d{1,2}(?:[.,]\d+)?(?:\s+\d/\d)?))?['\"]*"
    )
    full_match = re.search(pattern, processed, re.IGNORECASE)

    if full_match:
        data = full_match.groupdict()
        width_val = parse_dimension_part(data.get('width') or '')
        
        if width_val is not None and width_val > 25:
            if isolated:
                return {
                    'length_ft': isolated['ft'],
                    'length_in': isolated['in'],
                    'width_in': None,
                    'thickness_in': None
                }
            return None

        len_str = (data.get('length') or '').strip()
        length_ft = None; length_in = None
        if "'" in len_str:
            parts = len_str.split("'")
            try:
                length_ft = int(parts[0]); length_in = int(parts[1]) if len(parts) > 1 and parts[1] else 0
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

        thickness_val = parse_dimension_part(data.get('thickness') or '')
        return {
            'length_ft': length_ft,
            'length_in': length_in,
            'width_in': width_val,
            'thickness_in': thickness_val
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
    match = re.search(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:l\b|lt\b|ltr\b|liters\b|litres\b|litri\b)', text, re.IGNORECASE)
    if match:
        try: return float(match.group(1).replace(',', '.'))
        except: return None
    return None

def extract_price(text):
    match = re.search(r'(\d+[.,]?\d*)\s*(?:€|euro|\u20AC)', text, re.IGNORECASE)
    if match:
        try: return float(match.group(1).replace(',', '.'))
        except: return None
    return None



def scrape_and_store(db: Session):
    ads_added = []
    
    # --- EFFICIENCY IMPROVEMENT: Fetch all existing links once ---
    logger.info("Fetching existing ad links from the database...")
    existing_links = {result[0] for result in db.query(Ad.link).all()}
    logger.info(f"Found {len(existing_links)} existing links.")

    BASE_SEARCH_URLS = [
        "https://www.subito.it/annunci-lazio/vendita/usato/roma/roma/?q=tavola+da+surf",
        "https://www.subito.it/annunci-lazio/vendita/usato/roma/roma/?q=surfboard",
    ]

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        for base_url in BASE_SEARCH_URLS:
            for page_num in range(1, 6): 
                url = f"{base_url}&o={page_num}"
                logger.info(f"Scraping search results from: {url}")
                try:
                    response = client.get(url)
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
                ad_containers = soup.find_all("div", class_=lambda x: x and 'item-card' in x)
                logger.info(f"Found {len(ad_containers)} potential ad containers on page {page_num}.")

                if not ad_containers:
                    logger.info(f"No more ads found on page {page_num}. Moving to next search term.")
                    break

                for container in ad_containers:
                    full_text = container.get_text(" ", strip=True)
                    link_tag = container.find("a", href=True)

                    if "Roma" in full_text and "€" in full_text and link_tag:
                        link = link_tag['href']
                        
                        title_tag = container.find("h2")
                        model = title_tag.get_text(strip=True) if title_tag else "N/A"

                        if "sacca" in model.lower():
                            logger.info(f"Skipping ad {link}: title contains 'sacca'")
                            continue

                        keywords = ["tavola", "surf", "softboard", "longboard", "shortboard"]
                        if not any(kw in full_text.lower() for kw in keywords):
                            logger.info(f"Skipping ad {link}: not surf-related")
                            continue

                        ad_data = {
                            "model": model,
                            "price": extract_price(full_text),
                            "location": "Roma (RM)",
                            "link": link,
                            "length_ft": None,
                            "length_in": None,
                        }

                        try:
                            detail_resp = client.get(link)
                            detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                            desc_div = detail_soup.find("p", class_="AdDescription_description__154FP")
                            desc_text = desc_div.get_text(separator=" ", strip=True) if desc_div else ""
                            full_desc_text = f"{ad_data['model']} {desc_text}"

                            ad_data["brand"] = find_brand(full_desc_text) or ad_data["brand"]
                            ad_data["liters"] = extract_liters(full_desc_text)
                            dims = extract_dimensions(full_desc_text)
                            if dims: ad_data.update(dims)
                            
                            logger.info(f"  > Scraped Data for Ad:")
                            for key, value in ad_data.items():
                                logger.info(f"    - {key.ljust(15)}: {value}")
                            length_ft = ad_data.get("length_ft")
                            if isinstance(length_ft, (int, float)) and length_ft >= 5:
                                ad = Ad(**ad_data)
                                db.add(ad)
                                ads_added.append(ad)
                            else:
                                logger.warning(f"  > Skipping ad (length_ft is missing or < 5'): Found value '{length_ft}'. Link: {link}")

                        except Exception as e:
                            logger.error(f"  > Could not process detail page {link}. Error: {e}")
                        
                        time.sleep(random.uniform(5, 10)) 
            
            time.sleep(random.uniform(2, 4))
    
    logger.info("Committing new ads to the database...")
    db.commit()
    logger.info(f"Scraping session finished. Added {len(ads_added)} new ads.")
    return ads_added
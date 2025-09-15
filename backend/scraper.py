import re
import random
import time
import httpx
from bs4 import BeautifulSoup
from models import Ad
from sqlalchemy.orm import Session
import logging
from datetime import datetime
import os  # <-- Added missing import for os.makedirs

# --- 1. Logging Configuration ---

# Define the directory where logs will be saved
LOG_DIR = "scraping_logs"

# Ensure the log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Create a logger instance for this scraper module
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


# --- 3. New Merged Extraction Logic ---

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
    'lost', 'mayhem', 'channel islands', 'al merrick', 'pyzel', 'firewire',
    'slater designs', 'js industries', 'hayden shapes', 'pukas', 'nsp', 'bic',
    'sic', 'torq', 'hayden', 'hs', 'channel islands', 'victory', 'BOB', 'BoB', 'bob',
    'olaian'
]

def find_brand(text):
    text_lower = text.lower()
    for brand in POPULAR_BRANDS:
        if brand in text_lower:
            return ' '.join([w.capitalize() for w in brand.split()])
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
    Improved to handle:
     - decimal ft.in patterns followed immediately by letters (e.g. '6.0pollici'),
     - uppercase/lowercase 'FT' (e.g. '7FT') as a feet-only fallback,
     - keeps earlier full-dimension and metric parsing logic.
     - Handles feet-only apostrophe (e.g. 8') and Italian 'piedi'.
    """
    if not text:
        return None

    original = text  # keep original for unit-aware heuristics

    # --- 1) Try isolated ft'in or ft.in patterns on ORIGINAL text (more permissive) ---
    isolated = None

    # a) feet + apostrophe + (optional) inches: 8', 6'0, 5’6, etc.
    # <--- CHANGE: Removed the trailing `\b` which failed on patterns like `8' `.
    m = re.search(r"\b(?P<ft>\d{1,2})\s*(?:'|’|′)\s*(?P<in>\d{1,2})?", original)
    # b) decimal-style ft.in or ft,in allowing letters immediately after (e.g. "6.0pollici")
    if not m:
        m = re.search(r"\b(?P<ft>\d{1,2})[.,](?P<in>\d{1,2})(?=\D|$)", original)

    if m:
        try:
            ft = int(m.group('ft'))
            # Handle the case where the 'in' group is not found (is None)
            inch_str = m.group('in')
            inch = int(inch_str) if inch_str else 0
            if 4 <= ft <= 10 and 0 <= inch <= 11:
                isolated = {'ft': ft, 'in': inch}
        except Exception:
            isolated = None

    # --- 2) normalize text for 'x' splitting and unit removal and run full-dim pattern ---
    processed = text_pre_processor(original)

    # Full dimensions pattern length x width x thickness
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
        # width >=25 likely liters (guard)
        if width_val is not None and width_val > 25:
            # if we previously captured an isolated ft.in, prefer that
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
            # handle '5.11' or '5,11' style in the length token
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

    # --- 3) fallback to isolated ft.in captured earlier ---
    if isolated:
        return {
            'length_ft': isolated['ft'],
            'length_in': isolated['in'],
            'width_in': None,
            'thickness_in': None
        }

    # --- 4) feet-only patterns in ORIGINAL text (e.g. "7FT", "8 piedi") ---
    # Added 'piedi' to the list of recognized words for feet.
    m_ft_only = re.search(r"\b(?P<ft>\d{1,2})\s*(?:ft|feet|foot|piedi)\b", original, re.IGNORECASE)
    if m_ft_only:
        try:
            ft = int(m_ft_only.group('ft'))
            if 4 <= ft <= 10:
                return {'length_ft': ft, 'length_in': 0, 'width_in': None, 'thickness_in': None}
        except:
            pass

    # also handle a bare numeric that follows a length-keyword (e.g. "misura 7", "lunghezza 6")
    if re.search(r'\b(misur[ae]|misura|misure|lunghezza|size)\b', original, re.IGNORECASE):
        # A more specific search to avoid grabbing prices or other numbers
        m_num = re.search(r"\b(misur[ae]|misura|misure|lunghezza|size)\s*[:]?\s*(?P<ft>\d{1,2})\b", original, re.IGNORECASE)
        if m_num:
            try:
                ft = int(m_num.group('ft'))
                if 4 <= ft <= 10:
                    return {'length_ft': ft, 'length_in': 0, 'width_in': None, 'thickness_in': None}
            except:
                pass

    # --- 5) metric match (cm x cm x cm) ---
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

    # --- 6) bare apostrophe before a number (e.g. "circa ‘9", "‘8") ---
    m_apost = re.search(r"[‘’']\s*(?P<ft>\d{1,2})(?!\d)", original)
    if m_apost:
        try:
            ft = int(m_apost.group('ft'))
            if 4 <= ft <= 10:
                return {'length_ft': ft, 'length_in': 0, 'width_in': None, 'thickness_in': None}
        except:
            pass
    
    # --- 7) ft/in written with slash (e.g. "7/ 11", "6/4") ---
    m_slash = re.search(r"(?P<ft>\d{1,2})\s*/\s*(?P<in>\d{1,2})", original)
    if m_slash:
        try:
            ft = int(m_slash.group('ft'))
            inch = int(m_slash.group('in'))
            if 4 <= ft <= 10 and 0 <= inch < 12:
                return {'length_ft': ft, 'length_in': inch, 'width_in': None, 'thickness_in': None}
        except:
            pass

    # --- 8) pure centimeters (e.g. "182cm", " 200 cm") ---
    m_cm = re.search(r"(?P<cm>\d{2,3})\s*cm", original)
    if m_cm:
        try:
            cm = int(m_cm.group('cm'))
            if 120 <= cm <= 300:  # range plausibile per tavole
                total_inches = round(cm / 2.54)
                ft = total_inches // 12
                inch = total_inches % 12
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
    
    # --- Define the base URLs ---
    BASE_SEARCH_URLS = [
        "https://www.subito.it/annunci-lazio/vendita/usato/roma/roma/?q=tavola+da+surf",
        "https://www.subito.it/annunci-lazio/vendita/usato/roma/roma/?q=surfboard",
    ]

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        # --- Loop through your search terms ---
        for base_url in BASE_SEARCH_URLS:
            
            # --- Loop through a number of pages (e.g., 1 to 5) ---
            # Subito has about 35 ads per page, so 5 pages should be enough for 152 results.
            for page_num in range(1, 6): 
                
                # Construct the full URL for the current page
                url = f"{base_url}&o={page_num}"
                
                logger.info(f"Scraping search results from: {url}")
                try:
                    response = client.get(url)
                    if response.status_code != 200:
                        logger.error(f"Failed to fetch {url}. Status: {response.status_code}")
                        continue
                    if "Access Denied" in response.text:
                        logger.error(f"Access Denied for {url}. We are being blocked.")
                        break # Stop trying this search term if blocked

                except httpx.RequestError as e:
                    logger.error(f"Network error while fetching {url}: {e}")
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                
                ad_containers = soup.find_all("div", class_=lambda x: x and 'item-card' in x)
                logger.info(f"Found {len(ad_containers)} potential ad containers on page {page_num}.")

                # --- IMPORTANT: Stop if a page has no ads ---
                if not ad_containers:
                    logger.info(f"No more ads found on page {page_num}. Moving to next search term.")
                    break # Exit the page loop and go to the next base_url

                # (The rest of your ad processing logic remains the same)
                for container in ad_containers:
                    full_text = container.get_text(separator=" ", strip=True)
                    link_tag = container.find("a", href=True)

                    if "Roma" in full_text and "€" in full_text and link_tag:
                        link = link_tag['href']
                        if not db.query(Ad).filter_by(link=link).first():
                            # ... (your existing ad detail scraping logic) ...
                            # This part does not need to change
                            logger.info(f"--- Processing NEW ad: {link} ---")
                        
                            ad_data = {
                                "model": link_tag.find('h2').get_text(strip=True) if link_tag.find('h2') else "N/A",
                                "price": extract_price(full_text),
                                "location": "Roma (RM)", "link": link,
                                "brand": find_brand(full_text), "length_ft": None, "length_in": None,
                                "width_in": None, "thickness_in": None, "liters": None
                            }

                            try:
                                detail_resp = client.get(link)
                                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                                # Use the CORRECTED selector from our previous conversation
                                desc_div = detail_soup.find("p", class_="AdDescription_description__154FP")
                                desc_text = desc_div.get_text(separator=" ", strip=True) if desc_div else ""
                                full_desc_text = f"{ad_data['model']} {desc_text}"

                                ad_data["brand"] = find_brand(full_desc_text) or ad_data["brand"]
                                ad_data["liters"] = extract_liters(full_desc_text)
                                dims = extract_dimensions(full_desc_text)
                                if dims: ad_data.update(dims)
                                # --- Only insert if at least one length component is present ---
                                if ad_data.get("length_ft") not in (None, "") or ad_data.get("length_in") not in (None, ""):
                                    ad = Ad(**ad_data)
                                    db.add(ad)
                                    ads_added.append(ad)
                                else:
                                    logger.info(f"Skipping ad {link}: no length information found.")
                                logger.info(f"  > Scraped Data for Ad:")
                                for key, value in ad_data.items():
                                    logger.info(f"    - {key.ljust(15)}: {value}")
                                
                                ad = Ad(**ad_data)
                                db.add(ad)
                                ads_added.append(ad)

                            except Exception as e:
                                logger.error(f"  > Could not process detail page {link}. Error: {e}")
                            
                            time.sleep(random.uniform(1, 3)) # Delay between processing each ad
                
                # --- Add a small delay between scraping pages to be polite ---
                time.sleep(random.uniform(2, 4))
        
        logger.info("Committing new ads to the database...")
        db.commit()
        logger.info(f"Scraping session finished. Added {len(ads_added)} new ads.")
    return ads_added
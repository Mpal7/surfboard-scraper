"""Surfboard attribute extraction functions.

This module contains all the pure extraction logic for parsing surfboard
listings.  It is the implementation behind the ``parse_listing`` interface
in ``surfboard_parser.py``.
"""

from __future__ import annotations

import re

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

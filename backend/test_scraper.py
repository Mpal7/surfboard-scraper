import pytest
from scraper import extract_dimensions, extract_liters, extract_price, find_brand

test_cases = {
    "Caso 1 (Il tuo bug)": {
        "text": "Tavola da surf Firewire Seaside misure 5.6 x 21 1/4 x 2 1/2 x 32.7 litri. Prezzo 430€",
        "expected": {
            "length_ft": 5, "length_in": 6,
            "width_in": 21.25, "thickness_in": 2.5,
            "liters": 32.7, "price": 430.0, "brand": "Firewire"
        }
    },
    "Caso 2 (Punto decimale)": {
        "text": "Tavola Surf Pukas Hyperlink 5.11 - 32 Litri Roma",
        "expected": {
            "length_ft": 5, "length_in": 11,
            "liters": 32.0, "brand": "Pukas"
        }
    },
    "Caso 3 (Standard)": {
        "text": "Vendo 6'0\"x21\"x2 1/2\" shortboard usata poco, marca Lost",
        "expected": {
            "length_ft": 6, "length_in": 0,
            "width_in": 21.0, "thickness_in": 2.5,
            "brand": "Lost"
        }
    },
    "Caso 4 (Unità esplicite)": {
        "text": "Misure 6ft x 21.25in x 2.5in, volume 34L. Vendo a 250€.",
        "expected": {
            "length_ft": 6, "length_in": 0,
            "width_in": 21.25, "thickness_in": 2.5,
            "liters": 34.0, "price": 250.0
        }
    },
    "Caso 5 (Metrico)": {
        "text": "Tavola 183cm x 53.5cm x 6.5cm, marca Channel Islands",
        "expected": {
            "brand": "Channel Islands"
        }
    },
    "Caso 6 (Lunghezza isolata)": {
        "text": "Vendo tavola surf morbida Hayden Shapes modello Loot. Misura 5’6 - 36 litri",
        "expected": {
            "length_ft": 5, "length_in": 6,
            "liters": 36.0
        }
    },
    "Caso 7 (Senza spazi)": {
        "text": "Vendo 6x21x2.5 Firewire, 300 euro",
        "expected": {
            "length_ft": 6, "length_in": 0,
            "width_in": 21.0, "thickness_in": 2.5,
            "brand": "Firewire", "price": 300.0
        }
    },
    "Caso 8 (Simboli frazione)": {
        "text": "Misure 6’0’’x21¼x2½",
        "expected": {
            "length_ft": 6, "length_in": 0,
            "width_in": 21.25, "thickness_in": 2.5
        }
    },
    "Caso 9 (Solo litri)": {
        "text": "Tavola da surf 30L, marca NSP, prezzo 200€",
        "expected": {
            "liters": 30.0, "brand": "Nsp", "price": 200.0
        }
    },
    "Caso 10 (parziale)": {
        "text": "Misura 5’6 - 36 litri",
        "expected": {
            "length_ft": 5, "length_in": 6,
            "liters": 36.0
        }
    "Caso 11 pollici": {
        "text": "6.0pollici",
        "expected": {
            "length_ft": 6, "length_in": 0,

        }
    "Caso 12 7ft/7FT": {
        "text": "7FT",
        "expected": {
            "length_ft": 7, "length_in": 0,
        }      
    }
}

@pytest.mark.parametrize("name,case", test_cases.items())
def test_scraper(name, case):
    text = case["text"]
    expected = case["expected"]

    dims = extract_dimensions(text) or {}
    liters = extract_liters(text)
    price = extract_price(text)
    brand = find_brand(text)

    result = {
        "length_ft": dims.get("length_ft") if dims else None,
        "length_in": dims.get("length_in") if dims else None,
        "width_in": dims.get("width_in") if dims else None,
        "thickness_in": dims.get("thickness_in") if dims else None,
        "liters": liters,
        "price": price,
        "brand": brand
    }

    for key, expected_value in expected.items():
        assert result[key] == expected_value, f"{name}: Expected {key}={expected_value}, got {result[key]}"

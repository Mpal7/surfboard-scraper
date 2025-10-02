import pytest
from scraper import extract_dimensions, extract_liters, extract_price, find_brand

test_cases = {
    "Il tuo bug": {
        "text": "Tavola da surf Firewire Seaside misure 5.6 x 21 1/4 x 2 1/2 x 32.7 litri. Prezzo 430€",
        "expected": {
            "length_ft": 5, "length_in": 6,
            "width_in": 21.25, "thickness_in": 2.5,
            "liters": 32.7, "price": 430.0, "brand": "Firewire"
        }
    },
    "Punto decimale": {
        "text": "Tavola Surf Pukas Hyperlink 5.11 - 32 Litri Roma",
        "expected": {
            "length_ft": 5, "length_in": 11,
            "liters": 32.0, "brand": "Pukas"
        }
    },
    "Standard": {
        "text": "Vendo 6'0\"x21\"x2 1/2\" shortboard usata poco, marca Lost",
        "expected": {
            "length_ft": 6, "length_in": 0,
            "width_in": 21.0, "thickness_in": 2.5,
            "brand": "Lost Mayhem"
        }
    },
    "Unità esplicite": {
        "text": "Misure 6ft x 21.25in x 2.5in, volume 34L. Vendo a 250€.",
        "expected": {
            "length_ft": 6, "length_in": 0,
            "width_in": 21.25, "thickness_in": 2.5,
            "liters": 34.0, "price": 250.0
        }
    },
    "Metrico": {
        "text": "Tavola 183cm x 53.5cm x 6.5cm, marca Channel Islands",
        "expected": {
            "brand": "Channel Islands"
        }
    },
    "Lunghezza isolata": {
        "text": "Vendo tavola surf morbida Hayden Shapes modello Loot. Misura 5’6 - 36 litri",
        "expected": {
            "length_ft": 5, "length_in": 6,
            "liters": 36.0
        }
    },
    "Senza spazi": {
        "text": "Vendo 6x21x2.5 Firewire, 300 euro",
        "expected": {
            "length_ft": 6, "length_in": 0,
            "width_in": 21.0, "thickness_in": 2.5,
            "brand": "Firewire", "price": 300.0
        }
    },
    "Simboli frazione": {
        "text": "Misure 6’0’’x21¼x2½",
        "expected": {
            "length_ft": 6, "length_in": 0,
            "width_in": 21.25, "thickness_in": 2.5
        }
    },
    "Solo litri": {
        "text": "Tavola da surf 30L, marca NSP, prezzo 200€",
        "expected": {
            "liters": 30.0, "brand": "Nsp", "price": 200.0
        }
    },
    "parziale": {
        "text": "Misura 5’6 - 36 litri",
        "expected": {
            "length_ft": 5, "length_in": 6,
            "liters": 36.0
        }
    },
    "pollici": {
        "text": "6.0pollici",
        "expected": {
            "length_ft": 6, "length_in": 0,

        }
    },
    "7ft/7FT": {
        "text": "7FT",
        "expected": {
            "length_ft": 7, "length_in": 0,
        }      
    },
    "8 piedi": {
        "text": "Vendo tavola da surf da 8 piedi soft della Victory",
        "expected": {
            "length_ft": 8, "length_in": 0,
            "brand": "Victory"
        }
    },
    "8'":{
        "text": "Tavola da surf soft 8' ",
        "expected": {
            "length_ft": 8, "length_in": 0,
        }
    },
    "8' piedi (8' seguito da spazio e parola)": {
        "text": "Tavola da surf soft 8' piedi ",
        "expected": {
            "length_ft": 8, "length_in": 0,
        }
    },
    "Tavola da surf circa ‘9":{
        "text": "Tavola da surf circa ‘9",
        "expected": {
            "length_ft": 9, "length_in": 0,
        }
    },
    "Tavola da surf 7/ 11”":{
        "text": "Tavola da surf 7/ 11”",
        "expected": {
            "length_ft": 7, "length_in": 11,
        }
    },
    "182cm":{
        "text": "le misure non si leggono benissimo ma l'altezza totale è di 182cm, tavola",
        "expected": { 
            "length_ft": 6, "length_in": 0,
        }
    },
    "Dimensioni: 4’6” (140 cm) x 20” (60 cm) x 2 3/8” (20 cm). Volume approx 28L": {
        "text": "Dimensioni: 4’6” (140 cm) x 20” (60 cm) x 2 3/8” (20 cm). Volume approx 28L",
        "expected": {
            "length_ft": 4, "length_in": 6,
            "width_in": 20.0, "thickness_in": 2.375,
            "liters": 28.0
        }
    },
    "Tavola Surf Pukas Hyperlink 5.11 - 32 Litri Roma": {
        "text": "Tavola Surf Pukas Hyperlink 5.11 - 32 Litri Roma",
        "expected": {
            "length_ft": 5, "length_in": 11,
            "liters": 32.0, "brand": "Pukas"
        }
    },
    "test case con virgola e apostrofo - 5,11”x 19 1/2 x 2 5/8.": {
        "text": "Town & country the saint model 5,11”x 19 1/2 x 2 5/8 volume 34 litri.",
        "expected": {
            "length_ft": 5, "length_in": 11,
            "width_in": 19.50, "thickness_in": 2.625
        }
    },
    "test case apostrofi - un taglietto 5\"10 x 19 x 2 3/2\"x 27,26 L - Carbon Wrap technology":{
        "text": "Tavola Surf Firewire Seaside 5\"10 x 19 x 2 3/8\"x 27,26 L - Carbon Wrap technology",
        "expected": {
            "length_ft": 5, "length_in": 10,
            "width_in": 19.0, "thickness_in": 2.375,
            "liters": 27.26, "brand": "Firewire"
        }
    },
    "test case , e basta - deck 5,11×21 3/4 × 2 5/8.":{
        "text": "Tdeck 5,11×21 3/4 × 2 5/8.",
        "expected": {
            "length_ft": 5, "length_in": 11,
            "width_in": 21.75, "thickness_in": 2.625
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

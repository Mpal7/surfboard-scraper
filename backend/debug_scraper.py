# File: debug_parser.py
# Eseguilo con: python debug_parser.py
from scraper import extract_dimensions, extract_liters, find_brand, extract_price, text_pre_processor

# --- INCOLLA QUI IL TESTO CHE VUOI ANALIZZARE ---
# Puoi decommentare uno di questi esempi per testare diversi formati
test_cases = {
    "Caso 1 (Il tuo bug)": "Tavola da surf Firewire Seaside misure 5.6 x 21 1/4 x 2 1/2 x 32.7 litri. Prezzo 430€",
    "Caso 2 (Punto decimale)": "Tavola Surf Pukas Hyperlink 5.11 - 32 Litri Roma",
    "Caso 3 (Standard)": "Vendo 6'0\"x21\"x2 1/2\" shortboard usata poco, marca Lost",
    "Caso 4 (Unità esplicite)": "Misure 6ft x 21.25in x 2.5in, volume 34L. Vendo a 250€.",
    "Caso 5 (Metrico)": "Tavola 183cm x 53.5cm x 6.5cm, marca Channel Islands",
    "Caso 6 (Lunghezza isolata)": "Vendo tavola surf morbida Hayden Shapes modello Loot. Misura 5’6 - 36 litri",
    "Caso 7 (Senza spazi)": "Vendo 6x21x2.5 Firewire, 300 euro",
    "Caso 8 (Simboli frazione)": "Misure 6’0’’x21¼x2½",
    "Caso 9 (Solo litri)": "Tavola da surf 30L, marca NSP, prezzo 200€",
    "Caso 10 (parziale)": "Misura 5’6 - 36 litri"
}

# --- SELEZIONA QUALE CASO TESTARE ---
text_to_test = test_cases["Caso 1 (Il tuo bug)"]


print("--- ANALISI DEL TESTO ---")
print(f"Testo in input:\n---\n{text_to_test}\n---\n")

# Mostra il testo dopo la normalizzazione
processed_text = text_pre_processor(text_to_test)
print("Testo dopo la pre-elaborazione (quello che vede la regex):\n---\n" + processed_text + "\n---\n")

# Estrai tutti i dati
dims = extract_dimensions(text_to_test)
liters = extract_liters(text_to_test)
brand = find_brand(text_to_test)
price = extract_price(text_to_test)

print("--- RISULTATI ESTRATTI ---")

# Dati grezzi per il DB
print("Dati estratti (valori numerici per DB):")
print(f"  - Brand          : {brand}")
print(f"  - Price          : {price}")
print(f"  - Liters         : {liters}")
if dims:
    for key, value in dims.items():
        print(f"  - {key.ljust(15)}: {value}")
else:
    print("  - Dimensioni     : Non trovate")

# Anteprima output API
print("\nAnteprima output formattato (stile API):")
if dims:
    length_str = f"{dims.get('length_ft', '?')}'{int(round(dims.get('length_in', 0)))}\""
    width_str = f"{dims.get('width_in', '?')}\""
    thickness_str = f"{dims.get('thickness_in', '?')}\""
    print(f"  - Length         : {length_str}")
    print(f"  - Width          : {width_str}")
    print(f"  - Thickness      : {thickness_str}")
else:
    print("  - Misure non disponibili")
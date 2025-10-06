import os
import sys

def parse_int_env(name, default):
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        print(f"Warning: env {name}='{val}' is not an integer — using default {default}")
        return default

# Valeurs par défaut (adapte si besoin)
MIN_EXPONENTS = parse_int_env("MIN_EXPONENTS", 8)
MAX_EXPONENTS = parse_int_env("MAX_EXPONENTS", 20)

def run_scraper():
    # Exemple minimal : remplace par ton code réel de scraping si nécessaire.
    print(f"Starting scraper with MIN_EXPONENTS={MIN_EXPONENTS} and MAX_EXPONENTS={MAX_EXPONENTS}")
    # Ici place le code principal ; ceci évite que l'erreur de cast plante le job.
    try:
        # Simuler un comportement ou appeler la fonction réelle
        for e in range(MIN_EXPONENTS, min(MAX_EXPONENTS + 1, MIN_EXPONENTS + 5)):
            print(f"Processing exponent {e}")
        print("Scraper finished successfully.")
    except Exception as exc:
        print("Error during scraping:", exc)
        raise

def main():
    try:
        run_scraper()
    except Exception as e:
        print("Fatal:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()

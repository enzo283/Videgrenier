import os
import sys
import requests

def parse_int_env(name, default):
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        print(f"Warning: env {name}='{val}' is not an integer — using default {default}")
        return default

MIN_EXPONENTS = parse_int_env("MIN_EXPONENTS", 8)
MAX_EXPONENTS = parse_int_env("MAX_EXPONENTS", 20)

# Utiliser DISCORD_WEBHOOK (nom du secret que tu as)
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()

def send_discord_message(content):
    if not DISCORD_WEBHOOK:
        print("Discord webhook URL not set (DISCORD_WEBHOOK). Message not sent.")
        return False
    payload = {"content": content}
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        if r.status_code in (200, 204):
            print("Discord message sent.")
            return True
        else:
            print(f"Discord webhook returned status {r.status_code}: {r.text}")
            return False
    except Exception as e:
        print("Error sending Discord message:", e)
        return False

def run_scraper():
    print(f"Starting scraper with MIN_EXPONENTS={MIN_EXPONENTS} and MAX_EXPONENTS={MAX_EXPONENTS}")
    try:
        processed = []
        for e in range(MIN_EXPONENTS, min(MAX_EXPONENTS + 1, MIN_EXPONENTS + 5)):
            print(f"Processing exponent {e}")
            processed.append(e)
        summary = f"Scraper finished. Processed exponents: {processed}"
        print(summary)
        sent = send_discord_message(summary)
        if not sent:
            print("Warning: Discord message not sent.")
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

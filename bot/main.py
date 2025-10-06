# bot/main.py
import os
import sys
from .scraper import fetch_events
from .filter import keep_big_events, deduplicate
from .formatter import build_plain_message, build_embed_payload
from .notifier import send_text, send_embed

MIN_EXPOSANTS = int(os.getenv("MIN_EXPOSANTS", "80"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
SOURCE_URL = os.getenv("SOURCE_URL")

def main():
    if not SOURCE_URL:
        print("SOURCE_URL not set. Exiting.")
        sys.exit(1)
    if not DISCORD_WEBHOOK:
        print("DISCORD_WEBHOOK not set. Exiting.")
        sys.exit(1)

    print("Fetching events from", SOURCE_URL)
    events = fetch_events(SOURCE_URL)
    print("Parsed events:", len(events))

    big = keep_big_events(events, min_exposants=MIN_EXPOSANTS)
    print("After filtering >= {}: {}".format(MIN_EXPOSANTS, len(big)))

    unique = deduplicate(big)
    print("After deduplication:", len(unique))

    if not unique:
        print("No matching events. Nothing to send.")
        return

    # Construire un message texte — si trop long, on peut envoyer un embed
    text = build_plain_message(unique, header=f"Trouvés {len(unique)} vide‑greniers avec ≥ {MIN_EXPOSANTS} exposants :")
    # Envoi
    ok = send_text(DISCORD_WEBHOOK, text)
    if ok:
        print("Message envoyé (texte).")
    else:
        # essai embed en fallback
        print("Texte non envoyé, essai embed...")
        payload = build_embed_payload(unique)
        ok2 = send_embed(DISCORD_WEBHOOK, payload)
        print("Embed envoyé :", ok2)

if __name__ == "__main__":
    main()

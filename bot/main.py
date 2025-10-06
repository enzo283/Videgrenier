#!/usr/bin/env python3
import os
import sys
import json
import logging
from datetime import datetime, timezone
from scraper import select_scraper, normalize_items
from notifier import DiscordNotifier

LOGFILE = "/tmp/scrape-debug/full-run.json"

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def save_log(data):
    try:
        with open(LOGFILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Wrote JSON debug to {LOGFILE}")
    except Exception as e:
        logging.exception("Failed to write JSON log")

def main():
    setup_logging()
    src = os.getenv("SOURCE_URL")
    if not src:
        logging.error("SOURCE_URL not set")
        sys.exit(2)

    webhook = os.getenv("DISCORD_WEBHOOK")
    if not webhook:
        logging.warning("DISCORD_WEBHOOK not set — will only print results to stdout")

    logging.info(f"Starting scrape for {src}")
    scraper = select_scraper(src)
    try:
        items = scraper.scrape(src)
    except Exception:
        logging.exception("Scraper failed")
        items = []

    logging.info(f"Raw items found: {len(items)}")
    items = normalize_items(items)
    logging.info(f"After normalize/dedupe/filter: {len(items)}")

    # Save debug log
    debug = {
        "source": src,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "raw_count": len(items),
        "items": items
    }
    save_log(debug)

    notifier = DiscordNotifier(webhook) if webhook else None

    if not items:
        logging.info("No items to send.")
        if notifier:
            notifier.send_text(f"Scraper finished: 0 items from {src}")
        return

    # Try to send compact embeds (batch if many items)
    try:
        if notifier:
            sent = notifier.send_items_embeds(src, items)
            if not sent:
                # fallback: upload text file (full list) + short message
                notifier.send_text(f"Scraper: {len(items)} items found from {src} — sending full list as attachment.")
                notifier.send_file("/tmp/scrape-debug/full-run.json", "scrape-results.json")
                logging.info("Sent fallback file to Discord")
        else:
            # print nicely to stdout
            for i, it in enumerate(items, 1):
                print(f"--- ITEM {i} ---")
                print(json.dumps(it, ensure_ascii=False, indent=2))
                print()
    except Exception:
        logging.exception("Notifier failed")
        sys.exit(4)

if __name__ == "__main__":
    main()

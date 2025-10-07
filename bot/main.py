#!/usr/bin/env python3
import os
import sys
import json
import logging
from datetime import datetime, timezone
from scraper import select_scraper, normalize_items
from notifier import DiscordNotifier

LOG_DIR = "/tmp/scrape-debug"
LOG_JSON = f"{LOG_DIR}/full-run.json"
LOG_SUMMARY = f"{LOG_DIR}/summary_by_region_dept.txt"

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.StreamHandler(sys.stdout)])

def save_json(payload):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logging.info(f"Wrote JSON debug to {LOG_JSON}")
    except Exception:
        logging.exception("Failed to write JSON debug")

def save_summary_text(text):
    try:
        with open(LOG_SUMMARY, "w", encoding="utf-8") as f:
            f.write(text)
        logging.info(f"Wrote summary to {LOG_SUMMARY}")
    except Exception:
        logging.exception("Failed to write summary")

def weekday_label(iso):
    if not iso:
        return "Sans date"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%A").lower()  # e.g. 'samedi'
    except Exception:
        return "Sans date"

def group_region_dept_days(items):
    # structure: {region: {department: {'samedi':[], 'dimanche':[], 'autres':[]}}}
    from collections import defaultdict
    out = defaultdict(lambda: defaultdict(lambda: {"samedi": [], "dimanche": [], "autres": []}))
    for it in items:
        region = it.get("region") or "Autres"
        dept = it.get("department") or it.get("dept") or "Inconnu"
        day = weekday_label(it.get("date"))
        if "samedi" in day:
            bucket = "samedi"
        elif "dimanche" in day:
            bucket = "dimanche"
        elif it.get("date"):
            bucket = "autres"
        else:
            bucket = "autres"
        out[region][dept][bucket].append(it)
    return out

def human_text_region_dept(region, dept, buckets):
    lines = []
    lines.append(f"== {region} — {dept} ==")
    for day_label in ("samedi", "dimanche", "autres"):
        items = buckets.get(day_label, [])
        if not items:
            continue
        header = "Samedi" if day_label=="samedi" else ("Dimanche" if day_label=="dimanche" else "Autres jours")
        lines.append(f"-- {header} --")
        for i, it in enumerate(items, 1):
            title = it.get("title") or "Annonce"
            date = it.get("date") or "date non renseignée"
            ville = it.get("ville") or ""
            adresse = it.get("adresse") or ""
            url = it.get("url") or ""
            lines.append(f"{i}. {title}")
            lines.append(f"   📅 {date}  📍 {ville}" if ville else f"   📅 {date}")
            if adresse:
                lines.append(f"   🏠 {adresse}")
            if url:
                lines.append(f"   🔗 {url}")
            lines.append("")
    return "\n".join(lines)

def main():
    setup_logging()
    src = os.getenv("SOURCE_URL")
    if not src:
        logging.error("SOURCE_URL not set")
        sys.exit(2)
    webhook = os.getenv("DISCORD_WEBHOOK")
    if not webhook:
        logging.warning("DISCORD_WEBHOOK not set — will only print results")

    logging.info(f"Starting scrape for {src}")
    scraper = select_scraper(src)
    try:
        raw = scraper.scrape(src)
    except Exception:
        logging.exception("Scraper failed")
        raw = []

    logging.info(f"Raw items: {len(raw)}")
    items = normalize_items(raw)
    logging.info(f"Normalized items: {len(items)}")

    grouped = group_region_dept_days(items)

    # prepare debug payload
    payload = {"source": src, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "raw_count": len(raw), "normalized_count": len(items), "grouped": grouped}
    save_json(payload)

    # build human-friendly text
    parts = []
    for region in sorted(grouped.keys()):
        for dept in sorted(grouped[region].keys(), key=lambda s: s.lower()):
            txt = human_text_region_dept(region, dept, grouped[region][dept])
            parts.append(txt)
    full_text = "\n\n".join(parts)
    save_summary_text(full_text[:200000])

    notifier = DiscordNotifier(webhook) if webhook else None

    if not items:
        logging.info("No items found.")
        if notifier:
            notifier.send_text(f"Scraper terminé — 0 annonce(s) trouvée(s) sur {src}")
        return

    try:
        if notifier:
            notifier.send_text(f"📣 Scraper: {len(items)} annonce(s) trouvée(s) — triées par région puis département, séparées Samedi / Dimanche / Autres")
            # send department-by-department: if long, send as file
            for region in sorted(grouped.keys()):
                for dept in sorted(grouped[region].keys(), key=lambda s: s.lower()):
                    buckets = grouped[region][dept]
                    dept_text = human_text_region_dept(region, dept, buckets)
                    if len(dept_text) <= 1800:
                        notifier.send_embed(f"{dept} — {region}", dept_text)
                    elif len(dept_text) <= 1900:
                        notifier.send_text(f"**{dept} — {region}**\n{dept_text}")
                    else:
                        path = f"/tmp/scrape-debug/{region.replace(' ','_')}_{dept.replace(' ','_')}.txt"
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(dept_text)
                        notifier.send_text(f"{dept} — {region} : trop volumineux, fichier joint.")
                        notifier.send_file(path, f"{dept}.txt")
        else:
            print(full_text)
    except Exception:
        logging.exception("Notifier failed")
        if notifier:
            notifier.send_text("Erreur lors de l'envoi — upload JSON complet.")
            notifier.send_file(LOG_JSON, "scrape-results.json")
        sys.exit(4)

if __name__ == "__main__":
    main()

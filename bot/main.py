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
LOG_SUMMARY = f"{LOG_DIR}/summary_by_region.txt"

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

def weekday_label(iso):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
        wd = dt.strftime("%A").lower()
        if "samedi" in wd:
            return "samedi"
        if "dimanche" in wd:
            return "dimanche"
        return "autres"
    except Exception:
        return "autres"

def group_by_region_dept_day(items):
    # { region: { department: { 'samedi':[], 'dimanche':[], 'autres':[] } } }
    from collections import defaultdict, OrderedDict
    grp = defaultdict(lambda: defaultdict(lambda: {"samedi": [], "dimanche": [], "autres": []}))
    for it in items:
        region = it.get("region") or "Autres"
        dept = it.get("department") or it.get("dept") or "Inconnu"
        day_bucket = weekday_label(it.get("date"))
        if day_bucket is None:
            day_bucket = "autres"
        grp[region][dept][day_bucket].append(it)
    # order regions alphabetically
    ordered = OrderedDict()
    for region in sorted(grp.keys(), key=lambda s: s.lower()):
        ordered[region] = OrderedDict()
        for dept in sorted(grp[region].keys(), key=lambda s: s.lower()):
            ordered[region][dept] = grp[region][dept]
    return ordered

def make_region_text(region, region_data):
    # produce three sections: Samedi / Dimanche / Autres (dept grouped sequentially)
    lines = []
    lines.append(f"== Région: {region} ==")
    for day_label, header in (("samedi","Samedi"), ("dimanche","Dimanche"), ("autres","Autres jours")):
        # check if any dept has items for this day
        any_items = any(region_data[dept][day_label] for dept in region_data)
        if not any_items:
            continue
        lines.append(f"-- {header} --")
        for dept in region_data:
            items = region_data[dept][day_label]
            if not items:
                continue
            lines.append(f"### {dept}")
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
            lines.append("")  # small gap after dept
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

    grouped = group_by_region_dept_day(items)

    # save debug json
    payload = {"source": src, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "raw_count": len(raw), "normalized_count": len(items), "grouped": grouped}
    save_json(payload)

    # for each region produce a text file separated by Samedi/Dimanche/Autres
    os.makedirs(LOG_DIR, exist_ok=True)
    region_files = []
    for region, region_data in grouped.items():
        text = make_region_text(region, region_data)
        path = os.path.join(LOG_DIR, f"region-{region.replace(' ','_')}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text if text else f"== Région: {region} ==\n(Aucune annonce)")
        region_files.append((region, path, len(text)))

    # summary small file
    summary_lines = []
    for region, path, size in region_files:
        summary_lines.append(f"{region}: {size} caractères — {os.path.basename(path)}")
    with open(LOG_SUMMARY, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    notifier = DiscordNotifier(webhook) if webhook else None

    if not items:
        logging.info("No items found.")
        if notifier:
            notifier.send_text(f"Scraper terminé — 0 annonce(s) trouvée(s) sur {src}")
        return

    # send: 1) header, 2) for each region try to send short preview as embed/text, then attach file if > limit
    try:
        if notifier:
            notifier.send_text(f"📣 Scraper: {len(items)} annonce(s) trouvée(s) — fichiers par région envoyés (Samedi/Dimanche/Autres).")
            for region, path, size in region_files:
                # read small preview (first 1500 chars)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                preview = content[:1700]
                if len(content) <= 1800:
                    # short: send as embed (nicely formatted)
                    notifier.send_embed(f"{region} — aperçu", preview)
                else:
                    # send preview then file
                    preview_short = preview + "\n\n(…Voir le fichier joint pour la liste complète.)"
                    notifier.send_text(f"**{region}**\n{preview_short}")
                    notifier.send_file(path, os.path.basename(path))
        else:
            # print all region files concatenated
            for region, path, _ in region_files:
                with open(path, "r", encoding="utf-8") as f:
                    print(f.read())
    except Exception:
        logging.exception("Notifier failed")
        if notifier:
            notifier.send_text("Erreur lors de l'envoi — upload JSON complet.")
            notifier.send_file(LOG_JSON, "scrape-results.json")
        sys.exit(4)

if __name__ == "__main__":
    main()

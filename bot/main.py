#!/usr/bin/env python3
import os
import sys
import json
import logging
from datetime import datetime, timezone
from collections import defaultdict, OrderedDict
from scraper import select_scraper, normalize_items
from notifier import DiscordNotifier

LOG_DIR = "/tmp/scrape-debug"
LOG_JSON = f"{LOG_DIR}/full-run.json"
SUMMARY = f"{LOG_DIR}/summary_departments.txt"

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def save_json(payload):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logging.info(f"Wrote {LOG_JSON}")

def safe(s):
    return s or ""

def classify_day(iso):
    if not iso:
        return "autres"
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

def md_for_department(dept_name, region, items):
    lines = []
    lines.append(f"# {dept_name} — {region}\n")
    buckets = {"samedi": [], "dimanche": [], "autres": []}
    for it in items:
        bucket = classify_day(it.get("date"))
        buckets[bucket].append(it)

    for key, header in (("samedi","Samedi"),("dimanche","Dimanche"),("autres","Autres jours")):
        items_list = buckets[key]
        if not items_list:
            continue
        lines.append(f"## {header}\n")
        for idx, it in enumerate(items_list, 1):
            title = safe(it.get("title"))
            date = safe(it.get("date"))
            time_ = safe(it.get("time"))
            ville = safe(it.get("ville"))
            adresse = safe(it.get("adresse"))
            exposants = safe(str(it.get("nb_exposants") or ""))
            url = safe(it.get("url"))
            desc = safe(it.get("excerpt"))
            lines.append(f"### {idx}. {title}")
            lines.append(f"- Date : **{date}**")
            if time_:
                lines.append(f"- Heures : **{time_}**")
            if ville:
                lines.append(f"- Ville : **{ville}**")
            if adresse:
                lines.append(f"- Adresse : {adresse}")
            if exposants:
                lines.append(f"- Nombre d'exposants : {exposants}")
            if url:
                lines.append(f"- Lien : {url}")
            if desc:
                # indent description block for readability
                lines.append(f"- Description :\n\n    {desc.replace('\\n','\\n    ')}")
            lines.append("")  # gap
        lines.append("")  # gap between day sections
    return "\n".join(lines)

def main():
    setup_logging()
    src = os.getenv("SOURCE_URL")
    if not src:
        logging.error("SOURCE_URL not set")
        sys.exit(2)
    webhook = os.getenv("DISCORD_WEBHOOK")
    if not webhook:
        logging.warning("DISCORD_WEBHOOK not set — will only write files locally")

    logging.info(f"Scraping {src}")
    scraper = select_scraper(src)
    try:
        raw = scraper.scrape(src)
    except Exception:
        logging.exception("Scraper failed")
        raw = []

    logging.info(f"Raw items: {len(raw)}")
    items = normalize_items(raw)
    logging.info(f"Normalized items: {len(items)}")

    by_dept = defaultdict(lambda: {"region": "Autres", "items": []})
    for it in items:
        dept = safe(it.get("department")).strip() or "Inconnu"
        region = safe(it.get("region")) or "Autres"
        by_dept[dept]["region"] = region
        by_dept[dept]["items"].append(it)

    payload = {"source": src, "ts": datetime.now(timezone.utc).isoformat(), "raw_count": len(raw), "normalized_count": len(items)}
    payload["by_department"] = {k: v["items"] for k, v in by_dept.items()}
    save_json(payload)

    os.makedirs(LOG_DIR, exist_ok=True)
    dept_files = []
    for dept in sorted(by_dept.keys(), key=lambda s: s.lower()):
        region = by_dept[dept]["region"]
        md = md_for_department(dept, region, by_dept[dept]["items"])
        filename = f"department-{dept.replace(' ','_').replace('/','_')}.md"
        path = os.path.join(LOG_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md if md.strip() else f"# {dept} — {region}\n\n(Aucune annonce)")
        dept_files.append((dept, region, path, os.path.getsize(path)))

    with open(SUMMARY, "w", encoding="utf-8") as f:
        for dept, region, path, size in dept_files:
            f.write(f"{dept} | {region} | {os.path.basename(path)} | {size} bytes\n")

    notifier = DiscordNotifier(webhook) if webhook else None

    if notifier:
        try:
            notifier.send_text(f"📁 Scraper: {len(items)} annonces — envoi {len(dept_files)} fichiers (un par département).")
            # send files only (one by department)
            for dept, region, path, size in dept_files:
                notifier.send_file(path, os.path.basename(path))
        except Exception:
            logging.exception("Failed to send files")
            try:
                notifier.send_file(LOG_DIR + "/full-run.json", "full-run.json")
            except Exception:
                pass
    else:
        logging.info("No webhook configured — files written to %s", LOG_DIR)

if __name__ == "__main__":
    main()

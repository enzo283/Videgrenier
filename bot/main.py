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
LOG_SUMMARY = f"{LOG_DIR}/summary_by_department.txt"

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def save_json(data):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Wrote JSON debug to {LOG_JSON}")
    except Exception:
        logging.exception("Failed to write JSON debug")

def save_summary_text(text):
    try:
        with open(LOG_SUMMARY, "w", encoding="utf-8") as f:
            f.write(text)
        logging.info(f"Wrote summary to {LOG_SUMMARY}")
    except Exception:
        logging.exception("Failed to write summary text")

def group_by_department(items):
    # returns ordered dict-like: {department_code_or_name: {region:..., items:[..]}}
    from collections import defaultdict, OrderedDict
    groups = defaultdict(lambda: {"region": None, "items": []})
    for it in items:
        dept = it.get("department") or it.get("dept") or it.get("department_name") or "Inconnu"
        region = it.get("region") or "Autres"
        groups[dept]["region"] = region
        groups[dept]["items"].append(it)
    # order departments by name/code
    ordered = OrderedDict()
    for dept in sorted(groups.keys(), key=lambda s: s.lower()):
        ordered[dept] = groups[dept]
    return ordered

def human_text_for_dept(dept_name, region, items):
    lines = []
    header = f"=== {dept_name} — {region} ==="
    lines.append(header)
    if not items:
        lines.append("  (Aucune annonce)")
        return "\n".join(lines)
    for i, it in enumerate(items, 1):
        title = it.get("title") or "Annonce"
        date = it.get("date") or "date non renseignée"
        ville = it.get("ville") or it.get("city") or ""
        adresse = it.get("adresse") or it.get("address") or ""
        url = it.get("url") or ""
        lines.append(f"{i}. {title}")
        lines.append(f"   📅 {date}  📍 {ville}" if ville else f"   📅 {date}")
        if adresse:
            lines.append(f"   🏠 {adresse}")
        if url:
            lines.append(f"   🔗 {url}")
        # add small separator
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

    # group by department (ordered)
    grouped = group_by_department(items)

    # sort each dept by date (dates first)
    from dateutil import parser as dparser
    from datetime import datetime
    def sort_key(it):
        try:
            return dparser.parse(it["date"]) if it.get("date") else datetime.max
        except Exception:
            return datetime.max

    for dept in grouped:
        grouped[dept]["items"].sort(key=sort_key)

    # debug payload
    payload = {
        "source": src,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "raw_count": len(raw),
        "normalized_count": len(items),
        "by_department": grouped
    }
    save_json(payload)

    # build human-readable full text, department after department, aéré
    all_text_parts = []
    for dept, info in grouped.items():
        region = info.get("region") or "Autres"
        txt = human_text_for_dept(dept, region, info.get("items", []))
        all_text_parts.append(txt)
    full_text = "\n\n".join(all_text_parts)
    # keep summary file (limit to reasonable size)
    save_summary_text(full_text[:120000])  # store up to 120k chars

    notifier = DiscordNotifier(webhook) if webhook else None

    if not items:
        logging.info("No items found.")
        if notifier:
            notifier.send_text(f"Scraper terminé — 0 annonce trouvée sur {src}")
        return

    # Send sequential department messages in a readable form:
    try:
        if notifier:
            notifier.send_text(f"📣 Scraper: {len(items)} annonce(s) trouvée(s) — triées par département")
            # send department-by-department as text messages; if a department text > 1800 chars, send as file or multiple messages
            for dept, info in grouped.items():
                region = info.get("region") or "Autres"
                dept_text = human_text_for_dept(dept, region, info.get("items", []))
                # if short, send as embed (nicer), else as plain text or file
                if len(dept_text) <= 1800:
                    notifier.send_embed(f"{dept} — {region}", dept_text)
                elif len(dept_text) <= 1900:
                    notifier.send_text(f"**{dept} — {region}**\n{dept_text}")
                else:
                    # write per-department file and send brief message + file
                    path = f"/tmp/scrape-debug/department-{dept.replace(' ','_')}.txt"
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(dept_text)
                    notifier.send_text(f"{dept} — {region} : trop d'annonces pour un message. Voir le fichier joint.")
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

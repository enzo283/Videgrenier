import os
import sys
import json
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configuration
INDEX_URL = "https://vide-greniers.org/evenements/"
MIN_EXPOSANTS = int(os.getenv("MIN_EXPONENTS", "80"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()
SEEN_FILE = "data/seen.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; scraper/1.0)"}

def load_seen():
    try:
        os.makedirs(os.path.dirname(SEEN_FILE) or ".", exist_ok=True)
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen)), f, ensure_ascii=False, indent=2)

def post_discord_embed(title, description, fields):
    if not DISCORD_WEBHOOK:
        print("Discord webhook not set (DISCORD_WEBHOOK). Skipping send.")
        return False
    embed = {"title": title, "description": description, "fields": fields[:25], "timestamp": datetime.utcnow().isoformat(), "color": 0x2F3136}
    payload = {"embeds": [embed]}
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=15)
        if r.status_code in (200, 204):
            print("Discord: embed sent.")
            return True
        else:
            print("Discord returned", r.status_code, r.text)
            return False
    except Exception as e:
        print("Error sending to Discord:", e)
        return False

def extract_time_from_text(text):
    if not text:
        return None
    m = re.search(r"(\d{1,2}[:hH]\d{2})", text)
    if m:
        t = m.group(1).replace("H", "h")
        return t if ":" in t else t.replace("h", ":00")
    m2 = re.search(r"\b(\d{1,2})h\b", text, re.I)
    if m2:
        return f"{int(m2.group(1)):02d}:00"
    return None

def parse_event_card(card, base_url):
    text = card.get_text(" ", strip=True)
    a = card.find("a", href=True)
    href = None
    if a:
        href = urljoin(base_url, a["href"])
    title_el = card.find(["h2","h3","h4"]) or a
    title = title_el.get_text(strip=True) if title_el else (text[:60] if text else "Événement")
    date = None
    time_el = card.find("time")
    if time_el and time_el.get("datetime"):
        date = time_el["datetime"]
    else:
        m = re.search(r"(\d{1,2}\s+[A-Za-zéûô]+(?:\s+\d{4})?|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})", text)
        if m:
            date = m.group(1)
    addr = None
    addr_sel = card.find(class_=re.compile(r"(adresse|lieu|ville|localisation|location)", re.I))
    if addr_sel:
        addr = addr_sel.get_text(" ", strip=True)
    else:
        m = re.search(r"(Adresse|Lieu|Place|Rue)\s*[:\-]\s*([^\.|\n]{5,200})", text, re.I)
        if m:
            addr = m.group(2).strip()

    exposants = None
    m = re.search(r"(\d{1,4})\s*(?:exposant|exposants|stand|stands)", text, re.I)
    if m:
        try:
            exposants = int(m.group(1))
        except:
            exposants = None

    heure_exposants = None
    heure_visiteurs = None
    m_e = re.search(r"(?:installation|arriv|exposant)[^\d\n]*?(\d{1,2}[:h]\d{2}|\d{1,2}h?)", text, re.I)
    if m_e:
        heure_exposants = extract_time_from_text(m_e.group(1))
    m_v = re.search(r"(?:ouvert|ouverture|visiteur|visiteurs)[^\d\n]*?(\d{1,2}[:h]\d{2}|\d{1,2}h?)", text, re.I)
    if m_v:
        heure_visiteurs = extract_time_from_text(m_v.group(1))

    uid = href or (title + "|" + (date or "") + "|" + (addr or ""))
    return {"id": uid, "title": title, "url": href, "date": date, "address": addr, "exposants": exposants, "heure_exposants": heure_exposants, "heure_visiteurs": heure_visiteurs, "raw": text}

def find_department_urls(index_url):
    try:
        r = requests.get(index_url, headers=HEADERS, timeout=15)
    except Exception as e:
        print("Index request failed:", e)
        return []
    if r.status_code != 200:
        print("Index non-200:", r.status_code)
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # garde les liens contenant '/evenements/' et une partie après (ex: /evenements/Loire-Atlantique)
        if "/evenements/" in href:
            full = urljoin(index_url, href)
            # évite les liens d'événements individuels (contiennent souvent '/evenement/' ou un slug plus long)
            # on garde les slugs départementaux qui ressemblent à '/evenements/Name' (1 segment après)
            path = full.split("/evenements/")[-1].strip("/")
            if path and "/" not in path:
                links.add(full)
    return sorted(list(links))

def scrape_url(url):
    print("Scraping", url)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        print("Request failed:", e)
        return []
    if r.status_code != 200:
        print("Non-200 status", r.status_code)
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    # candidates: cartes d'événements
    selectors = [".evenement", ".event", ".card", ".article-evenement", "li.event", "article", ".result-item"]
    candidates = []
    for sel in selectors:
        found = soup.select(sel)
        if found:
            candidates.extend(found)
    if not candidates:
        candidates = soup.find_all("li")
    events = []
    for c in candidates:
        ev = parse_event_card(c, url)
        if not ev:
            continue
        if ev["exposants"] is not None and ev["exposants"] >= MIN_EXPOSANTS:
            events.append(ev)
    unique = {e["id"]: e for e in events}
    return list(unique.values())

def group_by_date(events):
    grouped = {}
    for e in events:
        d = e.get("date") or "Date inconnue"
        grouped.setdefault(d, []).append(e)
    return grouped

def build_discord_fields(grouped, dept_name):
    fields = []
    for date in sorted(grouped.keys()):
        items = grouped[date]
        lines = []
        for ev in items:
            parts = []
            if ev.get("title"):
                parts.append(f"**{ev['title']}**")
            if ev.get("exposants") is not None:
                parts.append(f"Exposants: {ev['exposants']}")
            if ev.get("heure_exposants"):
                parts.append(f"Arrivée exposants: {ev['heure_exposants']}")
            if ev.get("heure_visiteurs"):
                parts.append(f"Ouverture visiteurs: {ev['heure_visiteurs']}")
            if ev.get("address"):
                parts.append(f"Adresse: {ev['address']}")
            if ev.get("url"):
                parts.append(f"[Détails]({ev['url']})")
            lines.append(" • ".join(parts))
        value = "\n".join(lines) if lines else "Aucun événement trouvé"
        fields.append({"name": f"{dept_name} — {date}", "value": value})
    return fields

def main():
    seen = load_seen()
    dept_urls = find_department_urls(INDEX_URL)
    if not dept_urls:
        print("Aucune URL départementale trouvée — vérifie INDEX_URL")
        return
    print(f"Found {len(dept_urls)} departments to scrape")
    all_events = []
    for url in dept_urls:
        # déduit nom département depuis l'URL
        dept_name = url.rstrip("/").split("/")[-1].replace("-", " ")
        evs = scrape_url(url)
        if evs:
            # ajoute champ dept pour groupement par département si besoin
            for e in evs:
                e["department"] = dept_name
            all_events.extend(evs)

    if not all_events:
        print("No events matching filter found across all departments.")
        return

    new = [e for e in all_events if e["id"] not in seen]
    if not new:
        print("No new events since last run.")
        return

    # group by department then date for Discord fields
    by_dept = {}
    for e in new:
        dept = e.get("department", "Inconnu")
        by_dept.setdefault(dept, []).append(e)

    fields = []
    for dept, items in sorted(by_dept.items()):
        grouped = group_by_date(items)
        fields.extend(build_discord_fields(grouped, dept))

    title = f"Vide‑greniers (exposants ≥ {MIN_EXPOSANTS}) — nouveaux événements"
    description = f"Départements scannés: {len(dept_urls)}. Événements nouveaux: {len(new)}."

    sent = post_discord_embed(title, description, fields)
    if sent:
        for e in new:
            seen.add(e["id"])
        save_seen(seen)
    else:
        print("Failed to send Discord message; not updating seen list.")

if __name__ == "__main__":
    main()

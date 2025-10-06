import os
import sys
import json
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# Configuration
DEPT_URLS = [
    "https://vide-greniers.org/evenements/Loire-Atlantique"
    # Ajoute d'autres pages départementales si besoin
]
MIN_EXPOSANTS = int(os.getenv("MIN_EXPONENTS", "80"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()
SEEN_FILE = "data/seen.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; scraper/1.0; +https://example.org)"
}

# Utilitaires
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
    embed = {
        "title": title,
        "description": description,
        "fields": fields[:25],  # Discord limite à 25 fields par embed
        "timestamp": datetime.utcnow().isoformat(),
        "color": 0x2F3136
    }
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

def parse_int_from_text(text):
    if not text:
        return None
    m = re.search(r"(\d{1,4})\s*(exposant|exposants|stand|stands)?", text, re.I)
    if m:
        try:
            return int(m.group(1))
        except:
            return None
    return None

def extract_time_from_text(text):
    if not text:
        return None
    # cherche formats HH:MM ou HhMM ou HHhMM
    m = re.search(r"(\d{1,2}[:hH]\d{2})", text)
    if m:
        return m.group(1).replace("H", "h").replace(":", ":")
    # cherche heure simple
    m2 = re.search(r"\b(\d{1,2})h\b", text, re.I)
    if m2:
        return f"{int(m2.group(1)):02d}:00"
    return None

def parse_event_card(card):
    # Renvoie dict ou None
    text = card.get_text(" ", strip=True)
    href = None
    a = card.find("a", href=True)
    if a:
        href = a["href"]
        if href.startswith("/"):
            href = "https://vide-greniers.org" + href

    # Titre
    title_el = card.find(["h2","h3","h4"])
    title = title_el.get_text(strip=True) if title_el else (a.get_text(strip=True) if a else text[:60])

    # Date - cherche <time> ou éléments contenant jour/mois
    date = None
    time_el = card.find("time")
    if time_el and time_el.get("datetime"):
        try:
            date = datetime.fromisoformat(time_el["datetime"]).date().isoformat()
        except:
            date = time_el.get_text(strip=True)
    if not date:
        # heuristique : cherche dd/mm/yyyy ou dd month
        m = re.search(r"(\d{1,2}[\/\-\s]\d{1,2}[\/\-\s]\d{2,4})", text)
        if m:
            date = m.group(1)
        else:
            m2 = re.search(r"(\b(?:lun|mar|mer|jeu|ven|sam|dim)[a-z]*\b).*?(\d{1,2}\s+[A-Za-zéûô]+(?:\s+\d{4})?)", text, re.I)
            if m2:
                date = m2.group(2)

    # Adresse
    addr = None
    addr_sel = card.find(class_=re.compile(r"(adresse|lieu|location|localisation|ville)", re.I))
    if addr_sel:
        addr = addr_sel.get_text(" ", strip=True)
    else:
        # tentative: trouver "Adresse :" ou "Lieu :"
        m = re.search(r"(Adresse|Lieu|Place|Place de|Rue)\s*[:\-]\s*([^\n\r,]+(?:,[^\n\r]+)?)", text, re.I)
        if m:
            addr = m.group(2).strip()

    # Nombre d'exposants
    exposants = None
    # Cherche expressions comme "80 exposants" ou "80 stands"
    m = re.search(r"(\d{1,4})\s*(?:exposant|exposants|stand|stands)", text, re.I)
    if m:
        exposants = int(m.group(1))
    else:
        # parfois indiqué "Nombre d'exposants : 120"
        m2 = re.search(r"Nombre.*?[:]\s*(\d{1,4})", text, re.I)
        if m2:
            exposants = int(m2.group(1))

    # Heures
    heure_exposants = None
    heure_visiteurs = None
    # cherche phrases contenant 'exposant' et 'visiteur' / 'visiteurs' / 'ouverture'
    m_e = re.search(r"(?:installation|arriv|exposant)[^\d\n]*?(\d{1,2}[:h]\d{2}|\d{1,2}h?)", text, re.I)
    if m_e:
        heure_exposants = extract_time_from_text(m_e.group(1))
    m_v = re.search(r"(?:ouvert|ouverture|visiteur|visiteurs)[^\d\n]*?(\d{1,2}[:h]\d{2}|\d{1,2}h?)", text, re.I)
    if m_v:
        heure_visiteurs = extract_time_from_text(m_v.group(1))

    # Id unique simple
    uid = href or (title + "|" + (date or "") + "|" + (addr or ""))

    return {
        "id": uid,
        "title": title,
        "url": href,
        "date": date,
        "address": addr,
        "exposants": exposants,
        "heure_exposants": heure_exposants,
        "heure_visiteurs": heure_visiteurs,
        "raw": text
    }

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

    # Cherche éléments d'événements : cartes, list-items, articles
    candidates = []
    # sélecteurs usuels
    selectors = [
        ".evenement", ".event", ".card", ".article-evenement", "li.event", "article"
    ]
    for sel in selectors:
        found = soup.select(sel)
        if found:
            candidates.extend(found)

    # S'il n'y a rien, prend les li dans une liste
    if not candidates:
        candidates = soup.find_all("li")

    # Parse chaque candidate et garde celles plausibles
    events = []
    for c in candidates:
        ev = parse_event_card(c)
        if not ev:
            continue
        # Doit avoir date et exposants (ou au moins exposants >= MIN_EXPOSANTS)
        if ev["exposants"] is not None and ev["exposants"] >= MIN_EXPOSANTS:
            events.append(ev)
        else:
            # si exposants non présent, on skip (on filtre stricte)
            continue
    # déduplique par id
    unique = {e["id"]: e for e in events}
    return list(unique.values())

def group_by_date(events):
    grouped = {}
    for e in events:
        d = e.get("date") or "Date inconnue"
        grouped.setdefault(d, []).append(e)
    return grouped

def build_discord_fields(grouped):
    fields = []
    for date in sorted(grouped.keys()):
        items = grouped[date]
        # construit une valeur détaillée par département/événement — ici page départementale, on inclut titre + adresse + heures + lien
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
        fields.append({"name": date, "value": value})
    return fields

def main():
    seen = load_seen()
    all_events = []
    for url in DEPT_URLS:
        evs = scrape_url(url)
        all_events.extend(evs)

    if not all_events:
        print("No events matching filter found.")
        return

    # garde seulement nouveaux événements (ou envoie tout si seen vide)
    new = [e for e in all_events if e["id"] not in seen]

    if not new:
        print("No new events since last run.")
        return

    grouped = group_by_date(new)
    fields = build_discord_fields(grouped)

    title = f"Vide‑greniers (exposants ≥ {MIN_EXPOSANTS}) — résumé"
    description = f"Pages scrappées: {len(DEPT_URLS)}. Événements nouveaux: {len(new)}."

    sent = post_discord_embed(title, description, fields)
    if sent:
        for e in new:
            seen.add(e["id"])
        save_seen(seen)
    else:
        print("Failed to send Discord message; not updating seen list.")

if __name__ == "__main__":
    main()

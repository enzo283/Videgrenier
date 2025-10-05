#!/usr/bin/env python3
# fetch_vitegreniers.py
# Usage: DISCORD_WEBHOOK via GitHub Actions secret

import os, re, time, requests, datetime
from bs4 import BeautifulSoup

BASE = "https://vide-greniers.org"
HEADERS = {
    "User-Agent": "ViteGrenierBot/1.0 (+https://github.com/TON_COMPTE/ton-repo) - contact: ton-email",
}
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
THRESHOLD = 80  # nombre minimum d'exposants

def get(url, tries=2, pause=1.0):
    for i in range(tries):
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.text
        time.sleep(pause)
    r.raise_for_status()

def extract_number_of_exposants(text):
    m = re.search(r"(\d{1,4})\s*exposant", text, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None

def extract_event_info(event_url):
    html = get(event_url)
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n")
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else (soup.title.string if soup.title else "Événement")
    link = event_url
    mdate = re.search(r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}\s+\w+\s+\d{4}", text, flags=re.IGNORECASE)
    date_str = mdate.group(0) if mdate else "Date non renseignée"
    nb = extract_number_of_exposants(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    addr = None
    if "Localisation" in lines:
        idx = lines.index("Localisation")
        if idx + 1 < len(lines):
            addr = lines[idx+1]
    if not addr:
        maddr = re.search(r"\d{1,4}[\w\W]{0,80}(?:Rue|Avenue|Place|Boulevard|Bd|Impasse|Chemin)", text, flags=re.IGNORECASE)
        addr = maddr.group(0).strip() if maddr else "Adresse non renseignée"
    return {
        "title": title,
        "date": date_str,
        "exposants": nb,
        "address": addr,
        "link": link
    }

def build_listing(events_by_region):
    out_lines = []
    out_lines.append("📢 **Vite-Grenier — Liste des événements ≥ {} exposants**\n".format(THRESHOLD))
    for region, depts in sorted(events_by_region.items()):
        out_lines.append(f"### Région: {region}")
        for dept, cities in sorted(depts.items()):
            out_lines.append(f"  • Département: {dept}")
            for city, evs in sorted(cities.items()):
                out_lines.append(f"    - {city}:")
                for e in evs:
                    nb = e['exposants'] if e['exposants'] is not None else "?"
                    out_lines.append(f"      • {e['title']} ({e['date']}) — {nb} exposants — {e['address']}")
                    out_lines.append(f"        🔗 {e['link']}")
    return "\n".join(out_lines)

def main():
    if not DISCORD_WEBHOOK:
        print("Erreur: variable d'environnement DISCORD_WEBHOOK introuvable.")
        return
    print("Récupération de la page principale...")
    main_html = get(BASE)
    soup = BeautifulSoup(main_html, "lxml")
    dept_links = {}
    for a in soup.find_all("a", href=True):
        href = a['href']
        if href.startswith("/evenements/"):
            name = a.get_text(strip=True)
            url = BASE + href
            dept_links[name] = url
    print(f"{len(dept_links)} départements trouvés.")
    events_found = {}
    for dep_name, dep_url in dept_links.items():
        try:
            html = get(dep_url)
        except Exception as e:
            print("Erreur fetch dept", dep_name, e)
            continue
        dsoup = BeautifulSoup(html, "lxml")
        event_urls = set()
        for a in dsoup.find_all("a", href=True):
            if a['href'].startswith("/evenement/"):
                event_urls.add(BASE + a['href'])
        count = 0
        for ev_url in sorted(event_urls):
            if count >= 200:
                break
            time.sleep(0.6)
            try:
                info = extract_event_info(ev_url)
            except Exception as e:
                print("Erreur fetch événement", ev_url, e)
                continue
            if info['exposants'] is not None and info['exposants'] >= THRESHOLD:
                city = info['address'].split(",")[-1].strip() if info['address'] and "," in info['address'] else info['title']
                region = "France"
                events_found.setdefault(region, {}).setdefault(dep_name, {}).setdefault(city, []).append(info)
            count += 1
    if not events_found:
        content = f"Aucun événement avec ≥ {THRESHOLD} exposants trouvé cette semaine (données parfois manquantes)."
    else:
        content = build_listing(events_found)
    if len(content) < 1800:
        payload = {"content": content}
        r = requests.post(DISCORD_WEBHOOK, json=payload)
        print("Discord status:", r.status_code)
    else:
        files = {"file": ("vitegrenier.txt", content.encode("utf-8"))}
        r = requests.post(DISCORD_WEBHOOK, files=files)
        print("Discord (fichier) status:", r.status_code)

if __name__ == "__main__":
    main()

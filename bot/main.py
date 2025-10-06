#!/usr/bin/env python3
"""
main.py
Récupère les vide-greniers depuis une URL source, filtre >= MIN_EXPOSANTS,
formate par région/département et envoie au webhook Discord.
Configurer SOURCE_URL et quelques options via variables d'environnement
ou arguments.
"""

import os
import sys
import json
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from collections import defaultdict
from datetime import datetime
import pytz

# ---- CONFIG ----
SOURCE_URL = os.getenv("SOURCE_URL", "")  # URL à scrapper / API endpoint
MIN_EXPOSANTS = int(os.getenv("MIN_EXPOSANTS", "80"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")  # fourni via Secret GitHub
TIMEZONE = os.getenv("TIMEZONE", "Europe/Paris")  # pour affichage heure
MAX_EMBEDS_PER_MESSAGE = 10  # Discord limite, on chunkera si besoin

if not SOURCE_URL:
    print("Erreur: SOURCE_URL non défini. Mettre l'URL de la page/endpoint à scrapper.")
    sys.exit(1)
if not DISCORD_WEBHOOK:
    print("Erreur: DISCORD_WEBHOOK non défini.")
    sys.exit(1)

session = requests.Session()
session.headers.update({"User-Agent": "VG-Discord-Bot/1.0 (+https://github.com/)"})

# ---- Helpers: parsing dépendra du HTML/JSON de la source ----
def fetch_html(url):
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return r.text

def parse_events_from_html(html):
    """
    Adapter cette fonction selon la structure HTML de la source.
    On cherche pour chaque événement:
      - titre
      - region
      - department (ou code postal)
      - adresse (lieu)
      - n_exposants (int)
      - heure_installation (string)
      - heure_ouverture (string)
      - date (string)
      - url_detail (string)
    Si ta source est JSON, écris un parse JSON similaire.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []

    # Exemple générique: la page a des "div.event" (adapter au vrai sélecteur)
    for el in soup.select(".event, .annonce, .result-item"):
        try:
            title = el.select_one(".title, .titre, h2").get_text(strip=True)
        except:
            title = el.get_text(strip=True)[:60]

        # Localisation et adresse
        adresse = ""
        region = ""
        departement = ""
        cp = ""
        # tente divers sélecteurs
        if el.select_one(".adresse, .address"):
            adresse = el.select_one(".adresse, .address").get_text(" ", strip=True)
        if el.select_one(".region"):
            region = el.select_one(".region").get_text(strip=True)
        if el.select_one(".departement, .department"):
            departement = el.select_one(".departement, .department").get_text(strip=True)
        if el.select_one(".cp"):
            cp = el.select_one(".cp").get_text(strip=True)

        # Nombre d'exposants (essayer d'extraire nombre)
        n_exposants = 0
        txt = ""
        for s in el.stripped_strings:
            txt += " " + s.lower()
        # heuristique: chercher "exposant" suivi d'un nombre
        import re
        m = re.search(r"(\d{1,4})\s*-?\s*exposant", txt)
        if m:
            n_exposants = int(m.group(1))
        else:
            # autre pattern mm "80 exposants"
            m2 = re.search(r"(\d{1,4})\s+exposants?", txt)
            if m2:
                n_exposants = int(m2.group(1))

        # Heures (heuristique)
        heure_install = ""
        heure_ouverture = ""
        m_inst = re.search(r"install(?:ation)?[:\s]*([0-2]?\d[:h\.]?[0-5]\d)", txt)
        if m_inst:
            heure_install = m_inst.group(1).replace("h", ":").replace(".", ":")
        m_ouv = re.search(r"ouvr(?:e|ent)?:?[:\s]*([0-2]?\d[:h\.]?[0-5]\d)", txt)
        if m_ouv:
            heure_ouverture = m_ouv.group(1).replace("h", ":").replace(".", ":")

        # date et url détail
        date = ""
        link = None
        a = el.select_one("a")
        if a and a.get("href"):
            link = a.get("href")
            if link.startswith("/"):
                # base
                from urllib.parse import urljoin
                link = urljoin(SOURCE_URL, link)

        # push event
        events.append({
            "title": title,
            "region": region,
            "departement": departement,
            "cp": cp,
            "adresse": adresse,
            "n_exposants": n_exposants,
            "heure_install": heure_install,
            "heure_ouverture": heure_ouverture,
            "date": date,
            "url": link,
        })

    return events

def filter_and_group(events):
    # filtre >= MIN_EXPOSANTS
    filtered = [e for e in events if e.get("n_exposants", 0) >= MIN_EXPOSANTS]
    # groupe par region -> departement
    grouped = defaultdict(lambda: defaultdict(list))
    for e in filtered:
        region = e.get("region") or "Région inconnue"
        dept = e.get("departement") or (e.get("cp")[:2] if e.get("cp") else "Département inconnu")
        grouped[region][dept].append(e)
    return grouped

def build_discord_payload(grouped):
    """
    Crée une liste d'objects embed (Discord) ou texte si embed trop grand.
    Chaque embed contiendra événements d'un département (ou plusieurs petits).
    """
    embeds = []
    for region, depts in grouped.items():
        for dept, events in depts.items():
            # construire une description compacte
            lines = []
            for ev in events:
                parts = []
                title = ev.get("title", "Événement")
                parts.append(f"**{title}**")
                if ev.get("date"):
                    parts.append(f"({ev.get('date')})")
                if ev.get("n_exposants") is not None:
                    parts.append(f"- {ev.get('n_exposants')} exposants")
                if ev.get("adresse"):
                    parts.append(f"\n📍 {ev.get('adresse')}")
                if ev.get("heure_install"):
                    parts.append(f" • 🛠️ installation: {ev.get('heure_install')}")
                if ev.get("heure_ouverture"):
                    parts.append(f" • 🕗 ouverture: {ev.get('heure_ouverture')}")
                if ev.get("url"):
                    parts.append(f"\n🔗 {ev.get('url')}")
                lines.append("".join(parts))
            desc = "\n\n".join(lines)
            embed = {
                "title": f"{region} — {dept} ({len(events)} événements ≥ {MIN_EXPOSANTS})",
                "description": desc[:4096],  # limite embed
                "color": 3447003
            }
            embeds.append(embed)
    return embeds

def send_to_discord(embeds):
    # Discord limits: max 10 embeds per message. On chunk.
    webhook = DISCORD_WEBHOOK
    chunks = [embeds[i:i+MAX_EMBEDS_PER_MESSAGE] for i in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE)]
    for chunk in chunks:
        payload = {"username": "VideGreniers Bot", "embeds": chunk}
        r = session.post(webhook, json=payload, timeout=10)
        try:
            r.raise_for_status()
        except Exception as exc:
            print("Erreur en postant sur Discord:", r.status_code, r.text)
            raise

def main():
    html = fetch_html(SOURCE_URL)
    events = parse_events_from_html(html)
    grouped = filter_and_group(events)
    if not grouped:
        # envoie une notification vide
        session.post(DISCORD_WEBHOOK, json={"content": "Aucun vide-grenier >= {} exposants cette fois.".format(MIN_EXPOSANTS)})
        print("Aucun événement trouvé.")
        return
    embeds = build_discord_payload(grouped)
    send_to_discord(embeds)
    print("Terminé: {} embeds envoyés.".format(len(embeds)))

if __name__ == "__main__":
    main()

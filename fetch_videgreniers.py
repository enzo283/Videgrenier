#!/usr/bin/env python3
# fetch_videgrenier.py
# Script simple et robuste pour récupérer des événements et poster sur Discord via un webhook.
# IMPORTANT: nom du fichier = fetch_videgrenier.py

import os
import re
import time
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
# Change l'URL ci-dessous si tu préfères un site différent (ex: "https://vide-greniers.org")
BASE = "https://vitegrenier.org"
HEADERS = {"User-Agent": "ViteGrenierBot/1.0 (contact: ton-email)"}
THRESHOLD = 80  # minimum d'exposants pour lister l'événement

# Récupéré depuis les Secrets GitHub (DISCORD_WEBHOOK)
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# --- UTILITAIRES ---
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
        try:
            return int(m.group(1))
        except:
            return None
    return None

def extract_event_info(event_url):
    html = get(event_url)
    soup = BeautifulSoup(html, "lxml")
    title = soup.find("h1").get_text(strip=True) if soup.find("h1") else (soup.title.string if soup.title else "Événement")
    text = soup.get_text("\n")
    date_m = re.search(r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}\s+\w+\s+\d{4}", text, flags=re.IGNORECASE)
    date = date_m.group(0) if date_m else "Date non renseignée"
    exposants = extract_number_of_exposants(text)
    # heuristique d'adresse
    addr = "Adresse non renseignée"
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if "Localisation" in lines:
        idx = lines.index("Localisation")
        if idx + 1 < len(lines):
            addr = lines[idx+1]
    else:
        maddr = re.search(r"\d{1,4}[\w\W]{0,80}(?:Rue|Avenue|Place|Boulevard|Bd|Impasse|Chemin)", text, flags=re.IGNORECASE)
        if maddr:
            addr = maddr.group(0).strip()
    return {"title": title, "date": date, "exposants": exposants, "address": addr, "link": event_url}

def build_message(events_by_dept):
    lines = []
    lines.append(f"📢 **Vite-Grenier — événements ≥ {THRESHOLD} exposants**\n")
    for dept, evs in sorted(events_by_dept.items()):
        lines.append(f"**Département : {dept}**")
        for e in evs:
            nb = e['exposants'] if e['exposants'] is not None else "?"
            lines.append(f"- {e['title']} ({e['date']}) — {nb} exposants — {e['address']}")
            lines.append(f"  🔗 {e['link']}")
        lines.append("")  # ligne vide entre départements
    return "\n".join(lines)

# --- MAIN ---
def main():
    print("Début du script fetch_videgrenier.py")
    if not DISCORD_WEBHOOK:
        print("ERREUR : variable d'environnement DISCORD_WEBHOOK introuvable. Vérifie ton Secret GitHub.")
        raise SystemExit(1)

    print("Récupération de la page principale:", BASE)
    try:
        main_html = get(BASE)
    except Exception as e:
        print("Erreur en récupérant la page principale:", e)
        raise

    soup = BeautifulSoup(main_html, "lxml")

    # Récupérer liens de départements ou d'événements : recherche d'href contenant "evenement" ou "evenements"
    dept_links = {}
    for a in soup.find_all("a", href=True):
        href = a['href']
        if "/evenements/" in href or "/departement-" in href or "/evenement/" in href:
            name = a.get_text(strip=True) or href
            url = href if href.startswith("http") else (BASE.rstrip("/") + "/" + href.lstrip("/"))
            dept_links[name] = url

    print(f"{len(dept_links)} liens de départements trouvés (heuristique).")

    events_by_dept = {}
    # On parcourt chaque lien de département (sécurisé avec délai)
    for dep_name, dep_url in list(dept_links.items())[:60]:  # limite pour ne pas surcharger le site
        print("-> Inspect département:", dep_name, dep_url)
        try:
            dep_html = get(dep_url)
        except Exception as e:
            print("Erreur fetch département:", dep_name, e)
            continue
        dsoup = BeautifulSoup(dep_html, "lxml")
        event_urls = set()
        for a in dsoup.find_all("a", href=True):
            if "/evenement/" in a['href'] or "/annonce/" in a['href']:
                url = a['href'] if a['href'].startswith("http") else (BASE.rstrip("/") + "/" + a['href'].lstrip("/"))
                event_urls.add(url)
        print("  événements trouvés (heuristique):", len(event_urls))
        count = 0
        for ev in sorted(event_urls):
            if count >= 200:
                break
            time.sleep(0.5)
            try:
                info = extract_event_info(ev)
            except Exception as e:
                print("  erreur extraction événement:", ev, e)
                continue
            if info['exposants'] is not None and info['exposants'] >= THRESHOLD:
                events_by_dept.setdefault(dep_name, []).append(info)
            count += 1

    if not events_by_dept:
        message = f"Aucun événement trouvé avec ≥ {THRESHOLD} exposants (données parfois manquantes)."
        payload = {"content": message}
        r = requests.post(DISCORD_WEBHOOK, json=payload)
        print("Publié message simple sur Discord, status:", r.status_code)
        return

    content = build_message(events_by_dept)
    if len(content) < 1800:
        resp = requests.post(DISCORD_WEBHOOK, json={"content": content})
        print("Message envoyé sur Discord, status:", resp.status_code)
    else:
        # si trop long, envoie en fichier
        files = {"file": ("vitegrenier.txt", content.encode("utf-8"))}
        resp = requests.post(DISCORD_WEBHOOK, files=files)
        print("Fichier envoyé sur Discord, status:", resp.status_code)

if __name__ == "__main__":
    main()

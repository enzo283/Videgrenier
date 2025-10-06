# bot/scraper.py
import requests
from bs4 import BeautifulSoup
from .parser import parse_event_card
from .utils import safe_get

def fetch_page(url, timeout=15):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def fetch_events(source_url):
    html = fetch_page(source_url)
    soup = BeautifulSoup(html, "html.parser")
    events = []
    # ADAPTE ICI le sélecteur ".event-card" au site cible
    for card in soup.select(".event-card"):
        try:
            ev = parse_event_card(card)
            if ev:
                events.append(ev)
        except Exception as e:
            # garder le log simple pour debug
            print("parse error:", e)
    # fallback: si aucun ".event-card" trouvé, essayer un autre conteneur générique
    if not events:
        for item in soup.select("article, .card, .result"):
            try:
                ev = parse_event_card(item)
                if ev:
                    events.append(ev)
            except Exception:
                pass
    return events

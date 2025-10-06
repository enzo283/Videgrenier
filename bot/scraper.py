import requests
from bs4 import BeautifulSoup

def fetch_events(source_url):
    resp = requests.get(source_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    events = []
    # Exemple générique — adapte les sélecteurs au site réel
    for card in soup.select(".event-card"):
        title = card.select_one(".title").get_text(strip=True)
        date = card.select_one(".date").get_text(strip=True)
        exposants_text = card.select_one(".exposants").get_text(strip=True)
        try:
            exposants = int(''.join(filter(str.isdigit, exposants_text)) or 0)
        except:
            exposants = 0
        link = card.select_one("a")["href"]
        events.append({
            "title": title,
            "date": date,
            "exposants": exposants,
            "link": link,
        })
    return events

# bot/parser.py
from .utils import text_or_none, extract_int, join_url

def parse_event_card(card):
    # Exemple générique — adapte les selecteurs au site réel
    title_el = card.select_one(".title, .card-title, h2, h3")
    date_el = card.select_one(".date, .event-date, time")
    exposants_el = card.select_one(".exposants, .meta-exposants, .attendees")
    link_el = card.select_one("a")

    title = text_or_none(title_el)
    date = text_or_none(date_el)
    exposants_raw = text_or_none(exposants_el) or ""
    exposants = extract_int(exposants_raw)
    href = None
    if link_el and link_el.has_attr("href"):
        href = join_url(link_el["href"])

    if not title and not date:
        return None

    return {
        "title": title or "Sans titre",
        "date": date or "Date inconnue",
        "exposants": exposants,
        "link": href or ""
    }

# bot/formatter.py
from urllib.parse import urlparse

def build_plain_message(events, header=None, max_len=1900):
    if not events:
        return None
    header = header or f"Trouvés {len(events)} vide‑greniers avec le critère :"
    lines = [header, ""]
    for e in events:
        link = e.get("link") or ""
        title = e.get("title", "Sans titre")
        date = e.get("date", "Date inconnue")
        exposants = e.get("exposants", 0)
        short = f"- {date} — {title} ({exposants} exposants)"
        if link:
            short += f" — {link}"
        lines.append(short)
    text = "\n".join(lines)
    # Truncate if too long for a single Discord message
    if len(text) > max_len:
        text = text[:max_len-3] + "..."
    return text

def build_embed_payload(events, title="Vide‑greniers trouvés"):
    # Optionnel : retourne un JSON pour embed si tu veux un message riche
    fields = []
    for e in events[:10]:  # limiter le nombre d'embed fields
        name = f"{e.get('date')} — {e.get('title')}"
        value = f"{e.get('exposants',0)} exposants\n{e.get('link','')}"
        fields.append({"name": name[:256], "value": value[:1024], "inline": False})
    embed = {
        "title": title,
        "fields": fields
    }
    return {"embeds": [embed]}

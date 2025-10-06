# bot/utils.py
import re
from urllib.parse import urljoin
import os

def text_or_none(el):
    if not el:
        return None
    return el.get_text(strip=True)

def extract_int(s):
    if s is None:
        return 0
    digits = "".join(ch for ch in str(s) if ch.isdigit())
    try:
        return int(digits) if digits else 0
    except:
        return 0

def join_url(href):
    # Utilise une base si besoin (lire SOURCE_URL environ si présent)
    base = os.getenv("SOURCE_URL_BASE") or os.getenv("SOURCE_URL") or ""
    try:
        return urljoin(base, href)
    except:
        return href

def safe_get(d, key, default=None):
    return d.get(key, default) if isinstance(d, dict) else default

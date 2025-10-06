import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import dateparser

USER_AGENT = "Mozilla/5.0 (compatible; brocante-scraper/1.0; +https://example.com/bot)"

def select_scraper(url):
    # choose site-specific scraper when possible
    if "lesvidegreniers.fr" in url:
        return LesVideGreniersScraper()
    return GenericScraper()

def _get(url, timeout=15):
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def parse_date(text):
    if not text or not isinstance(text, str):
        return None
    # try to find a date-like substring
    # allow formats like "dimanche 12 septembre 2025", "12/09/2025", "12 sept 2025"
    dt = dateparser.parse(text, languages=['fr'], settings={'PREFER_DAY_OF_MONTH': 'first'})
    return dt.isoformat() if dt else None

def normalize_text(s):
    if not s:
        return ""
    # collapse whitespace, strip
    return re.sub(r'\s+', ' ', s).strip()

def normalize_items(items):
    # items: list of dicts {title, url, date, place, excerpt, raw}
    out = []
    seen = set()
    for it in items:
        title = normalize_text(it.get("title") or "")
        url = it.get("url") or ""
        excerpt = normalize_text(it.get("excerpt") or it.get("raw") or "")
        place = normalize_text(it.get("place") or "")
        date = it.get("date") or parse_date(excerpt) or parse_date(title)
        # dedupe key: title + url or excerpt snippet
        key = (title[:200], url, excerpt[:200])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title,
            "url": url,
            "date": date,
            "place": place,
            "excerpt": excerpt,
        })
    # sort by date if available (newest first)
    def _dt(it):
        try:
            return it["date"] or ""
        except:
            return ""
    out.sort(key=_dt, reverse=False)
    return out

class GenericScraper:
    def scrape(self, url):
        html = _get(url)
        soup = BeautifulSoup(html, "html.parser")
        candidates = []

        # strategy: find links that look like listing entries
        for a in soup.find_all("a", href=True):
            txt = a.get_text(separator=" ", strip=True)
            href = a['href']
            # skip navigation or short links
            if len(txt) < 20:
                continue
            # absolute url
            if href.startswith("/"):
                base = re.match(r'^(https?://[^/]+)', url)
                href = (base.group(1) if base else url.rstrip("/")) + href
            # heuristic: keep if contains brocante/vide/grenier keywords or date words
            low = txt.lower()
            if any(k in low for k in ("vide", "brocante", "grenier", "marché", "foire", "vide-grenier")) or re.search(r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b', txt):
                parent = a.find_parent()
                excerpt = parent.get_text(separator=" ", strip=True) if parent else txt
                candidates.append({"title": txt, "url": href, "excerpt": excerpt})
            # stop early if many
            if len(candidates) >= 150:
                break

        # fallback: scan article/li blocks
        if not candidates:
            selectors = ["article", "li", ".event", ".annonce", ".result", ".item", ".listing"]
            for sel in selectors:
                for el in soup.select(sel):
                    text = el.get_text(separator=" ", strip=True)
                    if len(text) < 50:
                        continue
                    # try to extract link inside
                    a = el.find("a", href=True)
                    href = a['href'] if a else ""
                    if href and href.startswith("/"):
                        base = re.match(r'^(https?://[^/]+)', url)
                        href = (base.group(1) if base else url.rstrip("/")) + href
                    candidates.append({"title": (a.get_text(strip=True) if a else text[:120]), "url": href, "excerpt": text})
                    if len(candidates) >= 150:
                        break
                if candidates:
                    break

        return candidates

class LesVideGreniersScraper:
    def scrape(self, url):
        # targeted scraper for lesvidegreniers.fr:
        html = _get(url)
        soup = BeautifulSoup(html, "html.parser")
        candidates = []

        # On la page principale il y a souvent des blocs ".list-card" ou ".card-listing" ou des liens dans h3/h2
        # 1) rechercher blocs avec class contenant "annonce", "result", "card", "listing", "evenement"
        blocks = soup.find_all(class_=re.compile(r"(annonce|result|card|listing|evenement|event|item)", re.I))
        for b in blocks:
            text = b.get_text(separator=" ", strip=True)
            if len(text) < 40:
                continue
            # find first link inside
            a = b.find("a", href=True)
            href = a['href'] if a else ""
            if href.startswith("/"):
                base = re.match(r'^(https?://[^/]+)', url)
                href = (base.group(1) if base else url.rstrip("/")) + href
            title = a.get_text(strip=True) if a else (b.find(["h2","h3"]).get_text(strip=True) if b.find(["h2","h3"]) else text[:120])
            # attempt to extract date/place in the block
            date = None
            place = None
            # common patterns: "Dimanche 12 septembre 2025", "12/09/2025", "Le 12 septembre"
            m_date = re.search(r'((?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b.*?\d{4})', text, re.I)
            if m_date:
                date = dateparser.parse(m_date.group(1), languages=['fr'])
            else:
                m_date2 = re.search(r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', text)
                if m_date2:
                    date = dateparser.parse(m_date2.group(1), languages=['fr'])
            # place heuristics: "Place", "Salle", "Rue", "Parc", "Centre"
            m_place = re.search(r'\b(Place|Rue|Parc|Salle|Centre|Espace|Jardin|Marché|Mairie|Château)\b.*?(?=(?:\d{1,2}[\/\-])|$)', text, re.I)
            if m_place:
                place = m_place.group(0).strip()
            excerpt = text
            candidates.append({
                "title": title,
                "url": href,
                "date": date.isoformat() if date else None,
                "place": place,
                "excerpt": excerpt,
                "raw": text
            })
            if len(candidates) >= 200:
                break

        # 2) if none found, scan main listing links
        if not candidates:
            for a in soup.find_all("a", href=True):
                txt = a.get_text(separator=" ", strip=True)
                if len(txt) < 30:
                    continue
                if any(k in txt.lower() for k in ("brocante","vide","grenier","marché","foire")) or re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}', txt):
                    href = a['href']
                    if href.startswith("/"):
                        base = re.match(r'^(https?://[^/]+)', url)
                        href = (base.group(1) if base else url.rstrip("/")) + href
                    parent = a.find_parent()
                    excerpt = parent.get_text(separator=" ", strip=True) if parent else txt
                    candidates.append({"title": txt, "url": href, "excerpt": excerpt})
                    if len(candidates) >= 200:
                        break

        return candidates

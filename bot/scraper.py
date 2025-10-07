import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import dateparser
from urllib.parse import urljoin
import logging
import time

USER_AGENT = "Mozilla/5.0 (compatible; brocante-scraper/1.1; +https://example.com/bot)"
REQUEST_TIMEOUT = 12

def select_scraper(url):
    if "lesvidegreniers.fr" in url:
        return LesVideGreniersScraper()
    return GenericScraper()

def _get(url, timeout=REQUEST_TIMEOUT):
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def parse_date(text):
    if not text:
        return None
    try:
        dt = dateparser.parse(text, languages=['fr'], settings={'PREFER_DAY_OF_MONTH': 'first'})
        return dt.isoformat() if dt else None
    except Exception:
        logging.exception("parse_date failed")
        return None

def normalize_text(s):
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s).strip()

def split_block_annonces(text):
    if not text:
        return []
    parts = []
    try:
        # primary separator
        if "➔" in text:
            for p in text.split("➔"):
                p = p.strip()
                if p:
                    parts.append(p)
        else:
            # split on repeated "Ville :" occurrences preserving fragments
            tokens = re.split(r'(?=(?:Ville\s*:))', text, flags=re.I)
            if len(tokens) > 1:
                for t in tokens:
                    t = t.strip()
                    if t:
                        parts.append(t)
            else:
                # fallback: split long paragraphs into sentences ~ heuristics
                if len(text) > 600:
                    # try split by double newline or " - "
                    for p in re.split(r'\n{2,}|\s[-–—]\s', text):
                        p = p.strip()
                        if p:
                            parts.append(p)
                else:
                    parts = [text.strip()]
    except Exception:
        logging.exception("split_block_annonces failed")
        parts = [text]
    return parts or [text]

def extract_fields_from_snippet(snip):
    title = ""
    ville = ""
    date = None
    adresse = ""
    lieu_precis = ""
    try:
        # Ville
        m = re.search(r'Ville\s*[:\-]?\s*([^DateAdresseHeureLieux➔\n\r]{1,120})', snip, re.I)
        if m:
            ville = m.group(1).strip(" ,;")
        # Date
        m = re.search(r'Date\s*[:\-]?\s*([^AdresseHeureLieux➔\n\r]{1,80})', snip, re.I)
        if m:
            date = parse_date(m.group(1).strip())
        # Heure / horaire inline
        # handled later by extract_time_from_text
        # Adresse / Lieu précis
        m = re.search(r'(?:Adresse|Lieu|Lieu précis)\s*[:\-]?\s*([^➔\n\r]{3,200})', snip, re.I)
        if m:
            adresse = m.group(1).strip(" ,;")
        # Title = before Ville: or Date:
        t = re.split(r'(?:Ville\s*:|Date\s*:|Adresse\s*:)', snip, flags=re.I)[0]
        title = normalize_text(t)[:250]
    except Exception:
        logging.exception("extract_fields_from_snippet failed")
    return {"title": title, "ville": ville, "date": date, "adresse": adresse, "excerpt": normalize_text(snip)}

def extract_time_from_text(text):
    if not text:
        return ""
    # 09h00, 9h00, 9:00, 9h-18h, 9h à 18h, 09:00 - 17:00, de 9h à 17h
    m = re.search(r'([0-2]?\d[:hH][0-5]\d(?:\s*(?:-|–|to|à|a|jusqu\'à|jusqu’à)\s*[0-2]?\d[:hH][0-5]\d)?)', text)
    if m:
        return m.group(1).replace('H', 'h')
    m2 = re.search(r'\b(?:de|ouverture|horaire|heures?)\s*[:\-]?\s*([0-2]?\d(?:h|:)[0-5]?\d?)', text, re.I)
    if m2:
        return m2.group(1)
    # simple patterns like "de 9h à 17h"
    m3 = re.search(r'de\s*([0-2]?\d(?:h|:)[0-5]?\d?)\s*(?:à|-|–|to)\s*([0-2]?\d(?:h|:)[0-5]?\d?)', text, re.I)
    if m3:
        return f"{m3.group(1)} - {m3.group(2)}"
    return ""

def extract_nb_exposants(text):
    if not text:
        return None
    # look for "xx exposants", "environ xx exposants", "xx stands", "plus de xx"
    m = re.search(r'(?:(?:environ|approx|~|plus de|près de)\s*)?(\d{1,4})\s*(?:exposant|exposants|stand|stands|vendeur|vendeurs)', text, re.I)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    # alternative "xx tables"
    m2 = re.search(r'(\d{1,4})\s*(?:tables|places)', text, re.I)
    if m2:
        try:
            return int(m2.group(1))
        except Exception:
            return None
    return None

def normalize_items(items):
    out = []
    seen = set()

    # First pass: normalize and split raw/excerpt blocks
    for it in items:
        raw = it.get("raw") or it.get("excerpt") or ""
        title = normalize_text(it.get("title") or "")
        url = it.get("url") or ""
        base = it.get("base") or ""
        if url and not url.startswith("http"):
            try:
                url = urljoin(base or "https://www.lesvidegreniers.fr", url)
            except Exception:
                pass
        region = it.get("region") or ""
        department = it.get("department") or it.get("dept") or it.get("department_name") or ""
        snippets = split_block_annonces(raw)
        for sn in snippets:
            fields = extract_fields_from_snippet(sn)
            final_title = title or fields.get("title") or (sn[:120] if sn else "Annonce")
            final_date = it.get("date") or fields.get("date") or parse_date(sn)
            final_ville = it.get("ville") or fields.get("ville") or ""
            final_adresse = it.get("place") or fields.get("adresse") or ""
            key = (final_title[:200], url or "", final_ville or "", final_date or "")
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "title": final_title,
                "url": url,
                "date": final_date,
                "ville": final_ville,
                "adresse": final_adresse,
                "excerpt": fields.get("excerpt") or raw,
                "region": region,
                "department": department,
                "time": "",
                "nb_exposants": None,
                "lieu_precis": ""  # optional more precise place
            })

    # Second pass: follow detail pages to enrich
    enriched = []
    MAX_FOLLOW = 120
    followed = 0
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for it in out:
        # follow only likely detail pages and up to cap
        if it.get("url") and "detail_vg.php" in it.get("url") and followed < MAX_FOLLOW:
            try:
                followed += 1
                r = session.get(it["url"], timeout=REQUEST_TIMEOUT)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                # nicer title
                tsel = soup.select_one("h1, h2")
                if tsel:
                    it["title"] = normalize_text(tsel.get_text(" ", strip=True))
                page_text = soup.get_text(" ", strip=True)
                # date
                md = re.search(r'(?:Date|Dates)\s*[:\-]?\s*([^\n\r]{4,160})', page_text, re.I)
                if md:
                    pd = parse_date(md.group(1).strip())
                    if pd:
                        it["date"] = pd
                # ville
                mv = re.search(r'(?:Ville|Commune)\s*[:\-]?\s*([A-Za-zÀ-ÿ\-\s]{1,120})', page_text)
                if mv:
                    it["ville"] = normalize_text(mv.group(1))
                # adresse / lieu précis
                ma = re.search(r'(?:Adresse|Lieu|Lieu précis)\s*[:\-]?\s*([^\n\r]{5,250})', page_text, re.I)
                if ma:
                    addr = normalize_text(ma.group(1))
                    it["adresse"] = addr
                    # try split address / place inside
                    if "," in addr:
                        it["lieu_precis"] = addr.split(",")[0].strip()
                # time / nb_exposants
                t = extract_time_from_text(page_text)
                if t:
                    it["time"] = t
                n = extract_nb_exposants(page_text)
                if n:
                    it["nb_exposants"] = n
                # department/region from breadcrumbs or meta
                crumb = soup.select_one(".breadcrumb, .breadcrumbs, nav[aria-label], .fil-ariane, .ariane")
                if crumb:
                    crumb_text = crumb.get_text(" ", strip=True)
                    mdept = re.search(r'([A-Za-zÀ-ÿ\-\s]+(?:§@customBackSlashd{1,3}!§)?)', crumb_text)
                    if mdept:
                        it["department"] = normalize_text(mdept.group(1))
                # description more precise
                sel_desc = soup.select_one(".description, .content, .texte, .desc, #content, .article")
                if sel_desc:
                    it["excerpt"] = normalize_text(sel_desc.get_text(" ", strip=True))[:3000]
                else:
                    it["excerpt"] = page_text[:2000]
                # polite pause
                time.sleep(0.08)
            except Exception:
                logging.exception("Failed to enrich detail page: %s", it.get("url"))
        else:
            # light heuristics on excerpt
            page_text = it.get("excerpt") or ""
            if not it.get("time"):
                t = extract_time_from_text(page_text)
                if t:
                    it["time"] = t
            if not it.get("nb_exposants"):
                n = extract_nb_exposants(page_text)
                if n:
                    it["nb_exposants"] = n
        enriched.append(it)

    return enriched

class GenericScraper:
    def scrape(self, url):
        logging.info("GenericScraper scraping %s", url)
        html = _get(url)
        base = re.match(r'^(https?://[^/]+)', url)
        base = base.group(1) if base else url
        soup = BeautifulSoup(html, "html.parser")
        candidates = []
        for a in soup.find_all("a", href=True):
            try:
                txt = a.get_text(" ", strip=True)
                href = a['href']
                if not txt or len(txt) < 20:
                    continue
                if any(x in href for x in ("departement.php", "departements.php", "/region", "categorie", "category", "/tags/")):
                    continue
                low = txt.lower()
                if any(k in low for k in ("vide","brocante","grenier","bourse","marché","foire")) or re.search(r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b', txt):
                    candidates.append({"title": txt, "url": urljoin(base, href), "excerpt": a.find_parent().get_text(" ", strip=True) if a.find_parent() else txt, "base": base})
                if len(candidates) >= 400:
                    break
            except Exception:
                logging.exception("Error processing link")
        if not candidates:
            selectors = ["article", "li", ".event", ".annonce", ".result", ".item", ".listing"]
            for sel in selectors:
                for el in soup.select(sel):
                    text = el.get_text(" ", strip=True)
                    if len(text) < 60:
                        continue
                    a = el.find("a", href=True)
                    href = a['href'] if a else ""
                    candidates.append({"title": a.get_text(strip=True) if a else text[:120], "url": urljoin(base, href) if href else "", "excerpt": text, "base": base})
                    if len(candidates) >= 400:
                        break
                if candidates:
                    break
        return candidates

class LesVideGreniersScraper:
    def scrape(self, url):
        logging.info("LesVideGreniersScraper scraping %s", url)
        html = _get(url)
        base = re.match(r'^(https?://[^/]+)', url)
        base = base.group(1) if base else url
        soup = BeautifulSoup(html, "html.parser")
        candidates = []

        main_selectors = ["#content", ".content", ".main", ".container", "main"]
        mains = []
        for sel in main_selectors:
            sel_el = soup.select_one(sel)
            if sel_el:
                mains.append(sel_el)
        if not mains:
            mains = [soup]

        seen = set()
        for main in mains:
            for a in main.find_all("a", href=True):
                try:
                    href = a['href']
                    full = urljoin(base, href)
                    if full in seen:
                        continue
                    seen.add(full)
                    txt = a.get_text(" ", strip=True) or (a.find_parent().get_text(" ", strip=True) if a.find_parent() else "")
                    if not txt or len(txt) < 20:
                        continue
                    if any(x in href for x in ("departement.php", "departements.php", "/region", "categorie", "category", "/tags/")):
                        continue
                    if txt.lower().strip() in ("lire la suite", "en savoir plus", "voir plus"):
                        continue
                    parent = a.find_parent()
                    excerpt = parent.get_text(" ", strip=True) if parent else txt
                    low = excerpt.lower()
                    if "detail_vg.php" in href or "ville" in low or "date" in low or re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}', excerpt) or any(k in low for k in ("vide","brocante","grenier","bourse","marché","foire")):
                        candidates.append({"title": txt, "url": full, "excerpt": excerpt, "base": base})
                    if len(candidates) >= 800:
                        break
                except Exception:
                    logging.exception("Error processing main links")
            if candidates:
                break

        if not candidates:
            for sel in ["article", "li", ".card", ".listing", ".result"]:
                for el in soup.select(sel):
                    try:
                        text = el.get_text(" ", strip=True)
                        if len(text) < 60:
                            continue
                        a = el.find("a", href=True)
                        href = a['href'] if a else ""
                        full = urljoin(base, href) if href else ""
                        candidates.append({"title": a.get_text(strip=True) if a else text[:120], "url": full, "excerpt": text, "base": base})
                        if len(candidates) >= 600:
                            break
                    except Exception:
                        logging.exception("Fallback block error")
                if candidates:
                    break

        return candidates

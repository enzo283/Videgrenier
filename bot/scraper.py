import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import dateparser
from urllib.parse import urljoin
import logging
import time

USER_AGENT = "Mozilla/5.0 (compatible; brocante-scraper/1.0; +https://example.com/bot)"

def select_scraper(url):
    if "lesvidegreniers.fr" in url:
        return LesVideGreniersScraper()
    return GenericScraper()

def _get(url, timeout=15):
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
    """
    Split a large block that may contain several announcements.
    Uses arrow '➔' as first separator, otherwise splits on repeated 'Ville :' occurrences.
    """
    if not text:
        return []
    parts = []
    try:
        if "➔" in text:
            for p in text.split("➔"):
                p = p.strip()
                if p:
                    parts.append(p)
        else:
            # split while keeping 'Ville :' markers at start of each chunk
            tokens = re.split(r'(?=(?:Ville\s*:))', text, flags=re.I)
            if len(tokens) > 1:
                for t in tokens:
                    t = t.strip()
                    if t:
                        parts.append(t)
            else:
                parts = [text.strip()]
    except Exception:
        logging.exception("split_block_annonces failed")
        parts = [text]
    return parts or [text]

def extract_fields_from_snippet(snip):
    """
    Given a snippet like "Brocante ... Ville : X Date : Y Adresse : Z", extract structured fields.
    """
    title = ""
    ville = ""
    date = None
    adresse = ""
    try:
        # Ville
        m_ville = re.search(r'Ville\s*:\s*([^DateAdresse➔\n\r]+)', snip, re.I)
        if m_ville:
            ville = m_ville.group(1).strip(" ,;")
        # Date
        m_date = re.search(r'Date\s*:\s*([^Adresse➔\n\r]+)', snip, re.I)
        if m_date:
            date = parse_date(m_date.group(1).strip())
        # Adresse
        m_ad = re.search(r'Adresse\s*:\s*([^➔\n\r]+)', snip, re.I)
        if m_ad:
            adresse = m_ad.group(1).strip(" ,;")
        # Title = text before Ville: or Date:
        t = re.split(r'(?:Ville\s*:|Date\s*:)', snip, flags=re.I)[0]
        title = normalize_text(t)[:250]
    except Exception:
        logging.exception("extract_fields_from_snippet failed")
    return {"title": title, "ville": ville, "date": date, "adresse": adresse, "excerpt": normalize_text(snip)}

def normalize_items(items):
    """
    items: list of dicts from scrapers (may contain title,url,excerpt,raw,base,region,department,date,...)
    Returns enriched list with absolute URLs, split announcements, dedup, and follow detail pages up to MAX_FOLLOW.
    """
    out = []
    seen = set()

    # First pass: split and normalize
    for it in items:
        raw = it.get("raw") or it.get("excerpt") or ""
        title = normalize_text(it.get("title") or "")
        url = it.get("url") or ""
        base = it.get("base") or ""
        # make absolute
        if url and not url.startswith("http"):
            try:
                url = urljoin(base or "https://www.lesvidegreniers.fr", url)
            except Exception:
                url = url
        region = it.get("region") or ""
        department = it.get("department") or it.get("dept") or it.get("department_name") or ""

        snippets = split_block_annonces(raw)
        for sn in snippets:
            fields = extract_fields_from_snippet(sn)
            final_title = title or fields.get("title") or sn[:120]
            final_date = it.get("date") or fields.get("date") or parse_date(sn)
            final_ville = it.get("ville") or fields.get("ville") or ""
            final_adresse = it.get("place") or fields.get("adresse") or ""
            key = (final_title[:180], url or "", final_ville or "", final_date or "")
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
                "department": department
            })

    # Second pass: follow detail pages for enrichment (cap to avoid long runs)
    enriched = []
    MAX_FOLLOW = 100
    followed = 0
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for it in out:
        # follow only detail pages that look like site detail
        if it.get("url") and "detail_vg.php" in it.get("url") and followed < MAX_FOLLOW:
            try:
                followed += 1
                r = session.get(it["url"], timeout=12)
                r.raise_for_status()
                html = r.text
                soup = BeautifulSoup(html, "html.parser")
                # Title override
                tsel = soup.select_one("h1, h2")
                if tsel:
                    it["title"] = normalize_text(tsel.get_text(" ", strip=True))
                # page text for regex extraction
                page_text = soup.get_text(" ", strip=True)
                # Date
                md = re.search(r'(?:Date\s*:?\s*)([^\n\r]{4,120})', page_text, re.I)
                if md:
                    pd = parse_date(md.group(1))
                    if pd:
                        it["date"] = pd
                # Ville
                mv = re.search(r'(?:Ville\s*:?\s*)([A-Za-zÀ-ÿ\-\s]{1,120})', page_text)
                if mv:
                    it["ville"] = normalize_text(mv.group(1))
                # Adresse
                ma = re.search(r'(?:Adresse\s*:?\s*)(.{5,200})', page_text)
                if ma:
                    it["adresse"] = normalize_text(ma.group(1))
                # Department / region from breadcrumbs or meta
                crumb = soup.select_one(".breadcrumb, .breadcrumbs, nav[aria-label], .fil-ariane")
                if crumb:
                    crumb_text = crumb.get_text(" ", strip=True)
                    # try find patterns like "Ain (01)" or single department word
                    mdept = re.search(r'([A-Za-zÀ-ÿ\-\s]+(?:§@customBackSlashd{1,3}!§)?)', crumb_text)
                    if mdept:
                        it["department"] = normalize_text(mdept.group(1))
                # description
                sel_desc = soup.select_one(".description, .content, .texte, .desc, #content")
                if sel_desc:
                    it["excerpt"] = normalize_text(sel_desc.get_text(" ", strip=True))[:3000]
                else:
                    it["excerpt"] = page_text[:2000]
                # polite pause
                time.sleep(0.08)
            except Exception:
                logging.exception("Failed to fetch/enrich detail page: %s", it.get("url"))
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
        # fallback: block scanning
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

        # Prefer content area(s)
        main_selectors = ["#content", ".content", ".main", ".container", "main"]
        mains = []
        for sel in main_selectors:
            sel_el = soup.select_one(sel)
            if sel_el:
                mains.append(sel_el)
        if not mains:
            mains = [soup]

        seen = set()
        # Prefer links that look like detail pages or contain Ville/Date clues
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
                    # Skip navigation / department lists / menu items
                    if any(x in href for x in ("departement.php", "departements.php", "/region", "categorie", "category", "/tags/")):
                        continue
                    if txt.lower().strip() in ("lire la suite", "en savoir plus", "voir plus"):
                        continue
                    parent = a.find_parent()
                    excerpt = parent.get_text(" ", strip=True) if parent else txt
                    low = excerpt.lower()
                    if "detail_vg.php" in href or "ville" in low or "date" in low or re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}', excerpt) or any(k in low for k in ("vide","brocante","grenier","bourse","marché","foire")):
                        candidates.append({"title": txt, "url": full, "excerpt": excerpt, "base": base})
                    # safety cap
                    if len(candidates) >= 800:
                        break
                except Exception:
                    logging.exception("Error processing main links")
            if candidates:
                break

        # Fallback: scan for blocks likely containing multiple items
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

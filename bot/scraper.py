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
    dt = dateparser.parse(text, languages=['fr'], settings={'PREFER_DAY_OF_MONTH': 'first'})
    return dt.isoformat() if dt else None

def normalize_text(s):
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s).strip()

def split_block_annonces(text):
    # split occurrences like "Ville : <X> Date : <Y> Adresse : <Z> ➔" or "Ville : ... Date : ..."
    parts = []
    if not text:
        return parts
    # use the arrow symbol or repeated "Ville :" as separator
    if "➔" in text:
        for part in text.split("➔"):
            p = part.strip()
            if p:
                parts.append(p)
    else:
        # try to split by "Ville :" occurrences
        matches = re.split(r'(?=(Ville\s*:))', text, flags=re.I)
        if len(matches) > 1:
            accum = ""
            for m in matches:
                if not m:
                    continue
                if m.lower().startswith("ville"):
                    if accum:
                        parts.append(accum.strip())
                    accum = m
                else:
                    accum += m
            if accum:
                parts.append(accum.strip())
        else:
            parts = [text]
    return parts or [text]

def extract_fields_from_snippet(snip):
    title = ""
    ville = ""
    date = None
    adresse = ""
    # ville
    m_ville = re.search(r'Ville\s*:\s*([^DateAdresse➔\n\r]+)', snip, re.I)
    if m_ville:
        ville = m_ville.group(1).strip(" ,;")
    # date
    m_date = re.search(r'Date\s*:\s*([^Adresse➔\n\r]+)', snip, re.I)
    if m_date:
        date = parse_date(m_date.group(1).strip())
    # adresse
    m_ad = re.search(r'Adresse\s*:\s*([^➔\n\r]+)', snip, re.I)
    if m_ad:
        adresse = m_ad.group(1).strip(" ,;")
    # title: take text before Ville: or Date:
    t = re.split(r'(?:Ville\s*:|Date\s*:)', snip, flags=re.I)[0]
    title = normalize_text(t)[:200]
    return {"title": title, "ville": ville, "date": date, "adresse": adresse, "excerpt": normalize_text(snip)}

def normalize_items(items):
    out = []
    seen = set()
    for it in items:
        raw = it.get("raw") or it.get("excerpt") or ""
        title = normalize_text(it.get("title") or "")
        url = it.get("url") or ""
        base = it.get("base") or ""
        if url and not url.startswith("http"):
            url = urljoin(base or "https://www.lesvidegreniers.fr", url)
        region = it.get("region") or ""
        department = it.get("department") or it.get("dept") or it.get("department_name") or ""
        # split multiple annonces in raw
        snippets = split_block_annonces(raw)
        for sn in snippets:
            fields = extract_fields_from_snippet(sn)
            final_title = title or fields.get("title") or sn[:120]
            final_date = it.get("date") or fields.get("date") or parse_date(sn)
            final_ville = it.get("ville") or fields.get("ville") or ""
            final_adresse = it.get("place") or fields.get("adresse") or ""
            key = (final_title[:150], url, final_ville, final_date or "")
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
    # enrich following detail pages (detail_vg.php) up to a cap
    enriched = []
    MAX_FOLLOW = 80
    followed = 0
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    for it in out:
        if it.get("url") and "detail_vg.php" in it.get("url") and followed < MAX_FOLLOW:
            try:
                followed += 1
                r = session.get(it["url"], timeout=12)
                r.raise_for_status()
                html = r.text
                soup = BeautifulSoup(html, "html.parser")
                # title
                tsel = soup.select_one("h1, h2")
                if tsel:
                    it["title"] = normalize_text(tsel.get_text(" ", strip=True))
                # attempt to find structured fields on detail
                page_text = soup.get_text(" ", strip=True)
                md = re.search(r'(?:Date\s*:?\s*)([^\n\r]{4,80})', page_text, re.I)
                if md:
                    pd = parse_date(md.group(1))
                    if pd:
                        it["date"] = pd
                mv = re.search(r'(?:Ville\s*:?\s*)([A-Za-zÀ-ÿ\-\s]{1,80})', page_text)
                if mv:
                    it["ville"] = normalize_text(mv.group(1))
                ma = re.search(r'(?:Adresse\s*:?\s*)(.{5,150})', page_text)
                if ma:
                    it["adresse"] = normalize_text(ma.group(1))
                # attempt to get department/region from breadcrumbs or meta
                crumb = soup.select_one(".breadcrumb, .breadcrumbs, nav[aria-label]")
                if crumb:
                    crumb_text = crumb.get_text(" ", strip=True)
                    # try extract department like "Ain (01)" or simple department names
                    mdept = re.search(r'([A-Za-zÀ-ÿ\-\s]+(?:§@customBackSlashd{1,3}!§)?)', crumb_text)
                    if mdept:
                        it["department"] = normalize_text(mdept.group(1))
                # description
                sel_desc = soup.select_one(".description, .content, .texte, .desc, #content")
                if sel_desc:
                    it["excerpt"] = normalize_text(sel_desc.get_text(" ", strip=True))[:2000]
                else:
                    it["excerpt"] = page_text[:1000]
                time.sleep(0.12)
            except Exception:
                logging.exception("detail fetch failed")
        enriched.append(it)
    return enriched

class GenericScraper:
    def scrape(self, url):
        logging.info(f"GenericScraper scraping {url}")
        html = _get(url)
        base = re.match(r'^(https?://[^/]+)', url).group(1) if re.match(r'^(https?://[^/]+)', url) else url
        soup = BeautifulSoup(html, "html.parser")
        candidates = []
        for a in soup.find_all("a", href=True):
            txt = a.get_text(" ", strip=True)
            href = a['href']
            if len(txt) < 20:
                continue
            if any(x in href for x in ("departement.php", "departements.php", "/region", "categorie", "category", "/tags/")):
                continue
            low = txt.lower()
            if any(k in low for k in ("vide","brocante","grenier","bourse","marché","foire")) or re.search(r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b', txt):
                candidates.append({"title": txt, "url": urljoin(base, href), "excerpt": a.find_parent().get_text(" ", strip=True) if a.find_parent() else txt, "base": base})
            if len(candidates) >= 300:
                break
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
                    if len(candidates) >= 300:
                        break
                if candidates:
                    break
        return candidates

class LesVideGreniersScraper:
    def scrape(self, url):
        logging.info(f"LesVideGreniersScraper scraping {url}")
        html = _get(url)
        base = re.match(r'^(https?://[^/]+)', url).group(1) if re.match(r'^(https?://[^/]+)', url) else url
        soup = BeautifulSoup(html, "html.parser")
        candidates = []
        # focus on listing blocks and detail links
        main = soup.select_one("#content, .content, .main, .container") or soup
        seen = set()
        # prefer links to detail_vg.php
        for a in main.find_all("a", href=True):
            href = a['href']
            full = urljoin(base, href)
            if full in seen:
                continue
            seen.add(full)
            txt = a.get_text(" ", strip=True) or a.find_parent().get_text(" ", strip=True)
            # skip nav/department list
            if any(x in href for x in ("departement.php", "departements.php", "/region", "categorie", "category", "/tags/")):
                continue
            if txt.lower().strip() in ("lire la suite", "en savoir plus", "voir plus"):
                continue
            if len(txt) < 20:
                continue
            parent = a.find_parent()
            excerpt = parent.get_text(" ", strip=True) if parent else txt
            # heuristics: prefer detail_vg or blocks containing Ville/Date/Adresse
            low = excerpt.lower()
            if "detail_vg.php" in href or "ville" in low or "date" in low or re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}', excerpt) or any(k in low for k in ("vide","brocante","grenier","bourse","marché","foire")):
                candidates.append({"title": txt, "url": full, "excerpt": excerpt, "base": base})
            if len(candidates) >= 600:
                break
        # fallback: if none, look for blocks with several annonces and include them
        if not candidates:
            for sel in ["article", "li", ".card", ".listing", ".result"]:
                for el in soup.select(sel):
                    text = el.get_text(" ", strip=True)
                    if len(text) < 60:
                        continue
                    a = el.find("a", href=True)
                    href = a['href'] if a else ""
                    full = urljoin(base, href) if href else ""
                    candidates.append({"title": a.get_text(strip=True) if a else text[:120], "url": full, "excerpt": text, "base": base})
                    if len(candidates) >= 400:
                        break
                if candidates:
                    break
        return candidates

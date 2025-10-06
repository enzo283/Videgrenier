#!/usr/bin/env python3
import os
import sys
import time
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# Normalise la SOURCE_URL pour enlever un slash final si présent
INDEX = os.getenv("SOURCE_URL", "http://agenda-des-brocantes.fr").rstrip('/')
HEADERS = {"User-Agent": "scraper-test/1.0"}
TIMEOUT = 15
DELAY_BEFORE_REQ = 1.0  # seconds between requests to be polite

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        print(f"[fetch] {url} -> {r.status_code}", flush=True)
        return r
    except Exception as e:
        print(f"[fetch] Request error for {url}: {e}", flush=True)
        return None

def find_department_urls(index_url, html):
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for a in soup.select("a"):
        href = a.get("href") or ""
        if not href:
            continue
        full = urljoin(index_url, href)
        path = urlparse(full).path.lower()
        # heuristiques pour détecter pages départementales
        if "departement" in path or "/departements" in path or "/departement-" in path:
            urls.add(full)
        elif path.strip("/").split("-")[0].isdigit():
            urls.add(full)
    return sorted(urls)

def extract_events_from_dept(dept_url, html):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    # essais de sélecteurs communs
    candidates = soup.select(".event,.listing-item,.card,.annonce,.result-item") or soup.find_all("article")
    if not candidates:
        # fallback: liens contenant des mots-clés
        for a in soup.select("a"):
            href = a.get("href","")
            if any(k in href for k in ("evenement","vide-grenier","brocante")):
                title = (a.get_text() or "").strip()
                if title:
                    events.append({"title": title, "url": urljoin(dept_url, href)})
        return events

    for node in candidates:
        title = None
        date = None
        place = None
        t = node.select_one("h1,h2,h3,.title,.titre")
        if t:
            title = t.get_text(strip=True)
        else:
            a = node.select_one("a")
            if a:
                title = a.get_text(strip=True)
        d = node.select_one(".date,.dates,.event-date")
        if d:
            date = d.get_text(strip=True)
        p = node.select_one(".lieu,.place,.city,.location,.adresse")
        if p:
            place = p.get_text(strip=True)
        link = node.select_one("a")
        url = urljoin(dept_url, link.get("href")) if link and link.get("href") else None
        if title:
            events.append({"title": title, "date": date, "place": place, "url": url})
    return events

def main():
    print(f"INDEX_URL = {INDEX}", flush=True)
    r = fetch(INDEX)
    if not r:
        print("Failed to fetch index page.", flush=True)
        sys.exit(1)
    print("Status:", r.status_code, flush=True)
    print("Final URL:", r.url, flush=True)
    print("Content-start:\n", (r.text or "")[:800].replace("\n", " "), flush=True)

    dept_urls = find_department_urls(r.url, r.text)
    if not dept_urls:
        print("No department URLs auto-detected from index. (Check the Content-start output above.)", flush=True)
    else:
        print(f"Found {len(dept_urls)} department URLs (showing up to 20):", flush=True)
        for u in dept_urls[:20]:
            print(" -", u, flush=True)

    # scrape each department (limited to first 50 to avoid long runs)
    for i, du in enumerate(dept_urls[:50]):
        print(f"\n=== Dept {i+1}/{len(dept_urls)}: {du} ===", flush=True)
        rd = fetch(du)
        if not rd:
            print("  Failed to fetch department page.", flush=True)
            continue
        time.sleep(DELAY_BEFORE_REQ)
        events = extract_events_from_dept(du, rd.text)
        if not events:
            print("  No events found on this department page (check selectors).", flush=True)
            continue
        print(f"  Found {len(events)} events (showing up to 10):", flush=True)
        for ev in events[:10]:
            parts = [ev.get("title") or "<no title>"]
            if ev.get("date"):
                parts.append(ev["date"])
            if ev.get("place"):
                parts.append(ev["place"])
            if ev.get("url"):
                parts.append(ev["url"])
            print("   -", " | ".join(parts), flush=True)

if __name__ == "__main__":
    main()

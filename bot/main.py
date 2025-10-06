#!/usr/bin/env python3
import os
import time
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

INDEX = os.getenv("SOURCE_URL", "http://agenda-des-brocantes.fr")
HEADERS = {"User-Agent": "scraper-test/1.0"}
TIMEOUT = 15
DELAY_BEFORE_REQ = 1.0  # seconds between requests to be polite

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        return r
    except Exception as e:
        print(f"Request error for {url}: {e}")
        return None

def find_department_urls(index_url, html):
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for a in soup.select("a"):
        href = a.get("href") or ""
        if not href:
            continue
        # normalize relative URLs
        full = urljoin(index_url, href)
        # heuristic: includes 'departement' or 'departements' or 'departements' path or ends with dept slug
        path = urlparse(full).path.lower()
        if "departement" in path or "/departements" in path or "/departement-" in path:
            urls.add(full)
        # also accept links that look like /<num>-<name> typical for departmental pages
        elif path.strip("/").split("-")[0].isdigit():
            urls.add(full)
    return sorted(urls)

def extract_events_from_dept(dept_url, html):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    # try several common selectors
    candidates = soup.select(".event,.listing-item,.card,.annonce,.result-item,.clevent") or soup.find_all("article")
    if not candidates:
        # fallback: try to find links that contain '/evenement/' or similar
        for a in soup.select("a"):
            href = a.get("href","")
            if "evenement" in href or "vide-grenier" in href or "brocante" in href:
                title = (a.get_text() or "").strip()
                if title:
                    events.append({"title": title, "url": urljoin(dept_url, href)})
        return events

    for node in candidates:
        title = None
        date = None
        place = None
        # title heuristics
        t = node.select_one("h1,h2,h3,.title,.titre")
        if t:
            title = t.get_text(strip=True)
        else:
            # any link text
            a = node.select_one("a")
            if a:
                title = a.get_text(strip=True)
        # date/place heuristics
        d = node.select_one(".date,.dates,.event-date")
        if d:
            date = d.get_text(strip=True)
        p = node.select_one(".lieu,.place,.city,.location,.adresse")
        if p:
            place = p.get_text(strip=True)
        # url/id
        link = node.select_one("a")
        url = urljoin(dept_url, link.get("href")) if link and link.get("href") else None

        if title:
            events.append({"title": title, "date": date, "place": place, "url": url})
    return events

def main():
    print("INDEX_URL =", INDEX)
    r = fetch(INDEX)
    if not r:
        print("Failed to fetch index page.")
        return
    print("Status:", r.status_code)
    print("Final URL:", r.url)
    content_start = (r.text or "")[:800].replace("\n", " ")
    print("Content-start:\n", content_start)

    dept_urls = find_department_urls(r.url, r.text)
    if not dept_urls:
        print("No department URLs auto-detected from index. If page structure differs, open the index HTML above and adapt selectors.")
        return

    print(f"Found {len(dept_urls)} department URLs (showing up to 20):")
    for u in dept_urls[:20]:
        print(" -", u)

    # scrape each department (limit during tests)
    for i, du in enumerate(dept_urls):
        print(f"\n=== Dept {i+1}/{len(dept_urls)}: {du} ===")
        rd = fetch(du)
        if not rd:
            print("  Failed to fetch department page.")
            continue
        time.sleep(DELAY_BEFORE_REQ)
        events = extract_events_from_dept(du, rd.text)
        if not events:
            print("  No events found on this department page (check selectors).")
            continue
        print(f"  Found {len(events)} events (showing up to 10):")
        for ev in events[:10]:
            parts = [ev.get("title") or "<no title>"]
            if ev.get("date"):
                parts.append(ev["date"])
            if ev.get("place"):
                parts.append(ev["place"])
            if ev.get("url"):
                parts.append(ev["url"])
            print("   -", " | ".join(parts))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import sys
import requests
from bs4 import BeautifulSoup

def main():
    url = os.getenv("SOURCE_URL")
    if not url:
        print("ERROR: SOURCE_URL not set", file=sys.stderr)
        sys.exit(2)

    print(f"Fetching: {url}")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"ERROR: request failed: {e}", file=sys.stderr)
        sys.exit(3)

    print(f"Status: {r.status_code}")
    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    # heuristique générique : chercher éléments qui ressemblent à des annonces (li, article, .event, .annonce)
    selectors = ["article", "li", ".event", ".annonce", ".listing", ".card"]
    items = []
    for sel in selectors:
        for el in soup.select(sel):
            text = el.get_text(separator=" ", strip=True)
            if len(text) > 30:
                items.append(text)
        if items:
            break

    # deduplicate and limit
    seen = set()
    filtered = []
    for t in items:
        if t in seen: continue
        seen.add(t)
        filtered.append(t)
        if len(filtered) >= 50: break

    print(f"Found {len(filtered)} potential items")
    for i, t in enumerate(filtered, 1):
        print(f"--- ITEM {i} ---")
        print(t[:400])
        print("")

if __name__ == "__main__":
    main()

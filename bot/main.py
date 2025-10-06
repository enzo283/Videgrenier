#!/usr/bin/env python3
import os
import sys
import requests
from bs4 import BeautifulSoup
import json
import textwrap

def send_discord(webhook_url, title, content):
    # Discord webhook simple embed (keeps message compact)
    data = {
        "embeds": [
            {
                "title": title,
                "description": content,
                "color": 5814783
            }
        ]
    }
    try:
        r = requests.post(webhook_url, json=data, timeout=10)
        r.raise_for_status()
        return True, r.status_code
    except Exception as e:
        return False, str(e)

def extract_items(html):
    soup = BeautifulSoup(html, "html.parser")
    selectors = ["article", "li", ".event", ".annonce", ".listing", ".card", ".result", ".item"]
    items = []
    for sel in selectors:
        for el in soup.select(sel):
            text = el.get_text(separator=" ", strip=True)
            # heuristique : doit contenir lieu/date ou au moins être assez long
            if len(text) > 50 and any(word in text.lower() for word in ["brocante","vide","grenier","dimanche","samedi","h:","€","place","rdv"]):
                items.append(text)
        if items:
            break
    # fallback : any long text nodes
    if not items:
        for el in soup.find_all(["p","div"]):
            t = el.get_text(separator=" ", strip=True)
            if len(t) > 120:
                items.append(t)
            if len(items) >= 20:
                break
    # dedupe and limit
    seen = set()
    out = []
    for t in items:
        if t in seen: continue
        seen.add(t)
        out.append(t)
        if len(out) >= 20: break
    return out

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
    items = extract_items(r.text)
    print(f"Found {len(items)} items")

    if not items:
        print("No items found; exiting without sending message.")
        return

    # prepare content: join first items trimmed
    parts = []
    for i, t in enumerate(items, 1):
        t_short = textwrap.shorten(t, width=300, placeholder="…")
        parts.append(f"**{i}.** {t_short}")
    content = "\n\n".join(parts[:10])  # limit embed size

    webhook = os.getenv("DISCORD_WEBHOOK")
    if not webhook:
        print("DISCORD_WEBHOOK not set; printing items to stdout instead.")
        for i, t in enumerate(items, 1):
            print(f"--- ITEM {i} ---")
            print(t)
            print()
        return

    title = f"Scraper: {len(items)} item(s) from {url}"
    ok, info = send_discord(webhook, title, content)
    if ok:
        print(f"Discord message sent (HTTP {info})")
    else:
        print(f"Failed to send Discord message: {info}", file=sys.stderr)
        sys.exit(4)

if __name__ == "__main__":
    main()

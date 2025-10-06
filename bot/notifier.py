import os
import json
import requests
import logging
from math import ceil

DISCORD_MAX_EMBEDS = 10
EMBED_DESC_MAX = 2048
EMBED_TITLE_MAX = 256

class DiscordNotifier:
    def __init__(self, webhook_url):
        self.webhook = webhook_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "brocante-notifier/1.0"})

    def send(self, payload):
        if not self.webhook:
            logging.error("No webhook configured")
            return False
        r = self.session.post(self.webhook, json=payload, timeout=15)
        try:
            r.raise_for_status()
            logging.info(f"Discord webhook posted (status {r.status_code})")
            return True
        except Exception as e:
            logging.exception(f"Discord webhook failed: {e} - body: {r.text[:400]}")
            return False

    def _make_embed(self, title, description, url=None, color=5814783):
        embed = {"title": title[:EMBED_TITLE_MAX], "description": description[:EMBED_DESC_MAX], "color": color}
        if url:
            embed["url"] = url
        return embed

    def send_text(self, text):
        payload = {"content": text}
        return self.send(payload)

    def send_file(self, path, name=None):
        if not self.webhook:
            return False
        name = name or os.path.basename(path)
        try:
            with open(path, "rb") as f:
                files = {"file": (name, f)}
                r = requests.post(self.webhook, files=files, timeout=30)
                r.raise_for_status()
                logging.info(f"Uploaded file {name} to Discord")
                return True
        except Exception:
            logging.exception("Failed to upload file to Discord")
            return False

    def send_items_embeds(self, source_url, items):
        # items: list of dict with title,url,date,place,excerpt
        if not items:
            return True
        # Build embed pages: each embed contains up to N items (limit by description length)
        embeds = []
        current_desc = []
        def flush_embed():
            if not current_desc:
                return
            desc = "\n\n".join(current_desc)
            title = f"Scraper results from {source_url}"
            embeds.append(self._make_embed(title, desc))
            current_desc.clear()

        for i, it in enumerate(items, 1):
            title = it.get("title") or f"Item {i}"
            date = it.get("date") or ""
            place = it.get("place") or ""
            url = it.get("url") or ""
            excerpt = it.get("excerpt") or ""
            line = f"**{i}.** {title}\n"
            if date:
                line += f"📅 {date}  "
            if place:
                line += f"📍 {place}  "
            if url:
                line += f"\n🔗 {url}"
            # add excerpt truncated
            if excerpt:
                ex = excerpt if len(excerpt) <= 300 else excerpt[:300].rsplit(" ",1)[0] + "…"
                line += f"\n_{ex}_"
            # check if adding line would overflow embed description
            projected = "\n\n".join(current_desc + [line])
            if len(projected) > 1800:
                flush_embed()
            current_desc.append(line)
            if len(embeds) >= DISCORD_MAX_EMBEDS:
                break
        flush_embed()

        # Discord allows up to 10 embeds per message; if more, send in multiple messages
        messages_needed = ceil(len(embeds) / DISCORD_MAX_EMBEDS)
        for m in range(messages_needed):
            batch = embeds[m*DISCORD_MAX_EMBEDS:(m+1)*DISCORD_MAX_EMBEDS]
            payload = {"embeds": batch}
            ok = self.send(payload)
            if not ok:
                logging.error("Failed to send embeds batch")
                return False
        return True

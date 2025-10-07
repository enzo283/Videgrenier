import os
import requests
import logging

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
        try:
            r = self.session.post(self.webhook, json=payload, timeout=15)
            r.raise_for_status()
            logging.info(f"Discord webhook posted (status {r.status_code})")
            return True
        except Exception:
            logging.exception("Discord webhook failed")
            return False

    def send_text(self, text):
        return self.send({"content": text})

    def send_embed(self, title, description, url=None, color=5814783):
        embed = {"title": title[:EMBED_TITLE_MAX], "description": description[:EMBED_DESC_MAX], "color": color}
        if url:
            embed["url"] = url
        return self.send({"embeds": [embed]})

    def send_file(self, path, name=None):
        if not self.webhook:
            return False
        name = name or os.path.basename(path)
        try:
            with open(path, "rb") as f:
                files = {"file": (name, f)}
                r = requests.post(self.webhook, files=files, timeout=60)
                r.raise_for_status()
                logging.info(f"Uploaded file {name} to Discord")
                return True
        except Exception:
            logging.exception("Failed to upload file to Discord")
            return False

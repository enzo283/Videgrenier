import os
import requests
import logging
import time

MAX_RETRIES = 3
BACKOFF = 2

class DiscordNotifier:
    def __init__(self, webhook_url):
        self.webhook = webhook_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "brocante-notifier/1.0"})

    def _post_json(self, payload):
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                r = self.session.post(self.webhook, json=payload, timeout=15)
                r.raise_for_status()
                logging.info("Discord JSON post ok (%s)", r.status_code)
                return True
            except Exception:
                attempt += 1
                logging.exception("Discord JSON post failed attempt %s", attempt)
                time.sleep(BACKOFF * attempt)
        return False

    def _post_file(self, path, name):
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                with open(path, "rb") as f:
                    files = {"file": (name, f)}
                    # send file without JSON payload (simple multipart)
                    r = self.session.post(self.webhook, files=files, timeout=60)
                    r.raise_for_status()
                    logging.info("Discord file upload ok (%s) %s", r.status_code, name)
                    return True
            except Exception:
                attempt += 1
                logging.exception("Discord file upload failed attempt %s for %s", attempt, name)
                time.sleep(BACKOFF * attempt)
        return False

    def send_text(self, text):
        if not self.webhook:
            logging.error("No webhook configured")
            return False
        return self._post_json({"content": text})

    def send(self, payload):
        return self._post_json(payload)

    def send_file(self, path, name=None):
        if not self.webhook:
            logging.error("No webhook configured")
            return False
        if not os.path.exists(path):
            logging.error("File not found for upload: %s", path)
            return False
        name = name or os.path.basename(path)
        return self._post_file(path, name)

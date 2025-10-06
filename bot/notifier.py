# bot/notifier.py
import requests
import os
import time

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

def post_json(url, payload, timeout=10):
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            if 200 <= r.status_code < 300:
                return True
            print("webhook status:", r.status_code, r.text)
        except Exception as e:
            print("webhook exception:", e)
        time.sleep(1 + attempt)
    return False

def send_text(webhook, text):
    if not webhook or not text:
        print("No webhook or no text to send")
        return False
    payload = {"content": text}
    return post_json(webhook, payload)

def send_embed(webhook, embed_payload):
    if not webhook or not embed_payload:
        print("No webhook or no embed")
        return False
    return post_json(webhook, embed_payload)

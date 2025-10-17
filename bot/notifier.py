import requests
import os

def send_to_discord(message):
    """Envoie le message formaté vers le webhook Discord"""
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url:
        raise ValueError("DISCORD_WEBHOOK n’est pas défini dans les secrets GitHub.")
    
    payload = {"content": message}
    response = requests.post(webhook_url, json=payload)

    if response.status_code != 204:
        print(f"Erreur Discord : {response.status_code} - {response.text}")

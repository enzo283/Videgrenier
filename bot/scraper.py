import requests
import json
import os

def load_events():
    """Récupère les événements depuis le fichier JSON source"""
    source_url = os.getenv("SOURCE_URL")

    if not source_url:
        raise ValueError("SOURCE_URL n’est pas défini dans les secrets GitHub.")

    response = requests.get(source_url)
    response.raise_for_status()
    data = response.json()

    return data.get("events", [])

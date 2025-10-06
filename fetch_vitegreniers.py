import requests
from bs4 import BeautifulSoup
import os

# On récupère l'URL du webhook Discord depuis les secrets GitHub
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

if not DISCORD_WEBHOOK:
    raise ValueError("Aucun webhook Discord trouvé ! Vérifie ton secret DISCORD_WEBHOOK sur GitHub.")

# URL du site vitegrenier.org
URL = "https://vide-greniers.org"

def get_videgreniers():
    """Récupère la liste des vide-greniers depuis le site"""
    page = requests.get(URL)
    soup = BeautifulSoup(page.text, "html.parser")

    events = []
    for item in soup.select(".event"):  # ce sélecteur dépend du site
        title = item.get_text(strip=True)
        link = item.get("href", "")
        exposants = 0

        # Exemple : recherche du nombre d'exposants dans le texte
        if "exposants" in title:
            try:
                exposants = int("".join([c for c in title if c.isdigit()]))
            except:
                exposants = 0

        if exposants >= 80:
            events.append(f"- [{title}]({URL}{link})")

    return events


def send_to_discord(events):
    """Envoie la liste sur Discord via le webhook"""
    if not events:
        message = "😕 Aucun vide-grenier trouvé avec plus de 80 exposants cette semaine."
    else:
        message = "**📅 Vide-Greniers de la semaine (+80 exposants)**\n\n" + "\n".join(events)

    data = {"content": message}
    requests.post(DISCORD_WEBHOOK, json=data)


if __name__ == "__main__":
    try:
        events = get_videgreniers()
        send_to_discord(events)
        print("✅ Liste envoyée sur Discord !")
    except Exception as e:
        print(f"❌ Erreur : {e}")

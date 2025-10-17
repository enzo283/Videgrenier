from bot.scraper import load_events
from bot.filter import filter_events
from bot.formatter import format_discord_message
from bot.notifier import send_to_discord

def main():
    print("Chargement des événements...")
    events = load_events()

    print("Filtrage...")
    valid_events = filter_events(events)

    print("Formatage du message...")
    message = format_discord_message(valid_events)

    print("Envoi sur Discord...")
    send_to_discord(message)

if __name__ == "__main__":
    main()

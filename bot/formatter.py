from collections import defaultdict

def group_by_region(events):
    grouped = defaultdict(list)
    for e in events:
        grouped[e["region"]].append(e)
    return grouped

def format_discord_message(events):
    """Crée un message Discord formaté par région et département"""
    if not events:
        return "Aucun vide-grenier trouvé pour ce week-end. 😢"

    grouped = group_by_region(events)
    message = "**🧺 Liste des vide-greniers du week-end :**\n\n"

    for region, items in grouped.items():
        message += f"📍 **{region}**\n"
        items_sorted = sorted(items, key=lambda x: x["department"])
        for e in items_sorted:
            message += (
                f"> 🏘️ **{e['title']}** ({e['department']})\n"
                f"> 📅 {e['date']} ({e['day']})\n"
                f"> ⏰ Visiteurs : {e['opening_time']} / Exposants : {e['exhibitors_arrival_time']}\n"
                f"> 📍 {e['address']}\n"
                f"> 🔗 [Lien]({e['source_url']})\n\n"
            )
    return message

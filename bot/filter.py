from datetime import datetime
from bot.utils import is_event_this_weekend

def filter_events(events):
    """Filtre les événements du bon week-end avec +80 exposants"""
    valid_events = []
    for e in events:
        try:
            event_date = datetime.strptime(e["date"], "%Y-%m-%d").date()
            if e["exhibitors_count"] >= 80 and is_event_this_weekend(event_date):
                valid_events.append(e)
        except Exception as err:
            print(f"Erreur filtrage : {err}")
    return valid_events

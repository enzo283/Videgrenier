import datetime

def get_next_weekend_dates():
    today = datetime.date.today()
    # Trouver le prochain samedi et dimanche
    saturday = today + datetime.timedelta((5 - today.weekday()) % 7)
    sunday = saturday + datetime.timedelta(days=1)
    return saturday, sunday

def is_event_this_weekend(event_date):
    saturday, sunday = get_next_weekend_dates()
    return event_date in [saturday, sunday]

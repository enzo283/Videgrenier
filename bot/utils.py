# bot/utils.py
from datetime import date, timedelta, datetime

def this_week_sat_sun(ref_date=None):
    """Return dates (YYYY-MM-DD) for the Saturday and Sunday of the current week
    relative to ref_date. Week considered: Monday..Sunday. If today is Friday,
    return upcoming Saturday and Sunday."""
    if ref_date is None:
        ref_date = date.today()
    # find Monday of current week
    monday = ref_date - timedelta(days=ref_date.weekday())
    saturday = monday + timedelta(days=5)
    sunday = monday + timedelta(days=6)
    return saturday, sunday

def iso_date(d: date) -> str:
    return d.isoformat()

def ensure_region_dir(base='results', region_slug='unknown'):
    import os
    path = os.path.join(base, region_slug)
    os.makedirs(path, exist_ok=True)
    return path

def region_slug(name: str) -> str:
    return name.lower().replace(' ', '-').replace("'", "-")

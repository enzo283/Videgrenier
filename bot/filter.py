# bot/filter.py
def keep_big_events(events, min_exposants=80):
    filtered = [e for e in events if (e.get("exposants") or 0) >= min_exposants]
    return filtered

def deduplicate(events, key_fields=("link", "title")):
    seen = set()
    out = []
    for e in events:
        key = tuple(e.get(f) for f in key_fields)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out

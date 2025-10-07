#!/usr/bin/env python3
import sys
import os
import json
from datetime import datetime

LOG_DIR = "/tmp/scrape-debug"
FULL = os.path.join(LOG_DIR, "full-run.json")

def safe(x): return x or ""

def classify_day(iso):
    if not iso:
        return "autres"
    try:
        from datetime import datetime as dt
        d = dt.fromisoformat(iso)
        wd = d.strftime("%A").lower()
        if "samedi" in wd: return "samedi"
        if "dimanche" in wd: return "dimanche"
    except Exception:
        pass
    return "autres"

def make_md(dept, items):
    lines = []
    region = items[0].get("region","Autres") if items else "Autres"
    lines.append(f"# {dept} — {region}\n")
    buckets = {"samedi": [], "dimanche": [], "autres": []}
    for it in items:
        buckets[classify_day(it.get("date"))].append(it)
    for key, hdr in (("samedi","Samedi"),("dimanche","Dimanche"),("autres","Autres jours")):
        L = buckets[key]
        if not L: continue
        lines.append(f"## {hdr}\n")
        for i,it in enumerate(L,1):
            lines.append(f"### {i}. {safe(it.get('title'))}")
            lines.append(f"- Date : **{safe(it.get('date'))}**")
            if it.get("time"): lines.append(f"- Heures : **{it.get('time')}**")
            if it.get("ville"): lines.append(f"- Ville : **{it.get('ville')}**")
            if it.get("lieu_precis"): lines.append(f"- Lieu précis : {it.get('lieu_precis')}")
            if it.get("adresse"): lines.append(f"- Adresse : {it.get('adresse')}")
            if it.get("nb_exposants"): lines.append(f"- Nombre d'exposants : {it.get('nb_exposants')}")
            if it.get("url"): lines.append(f"- Lien : {it.get('url')}")
            if it.get("excerpt"): lines.append(f"- Description :\n\n    {it.get('excerpt').replace('\\n','\\n    ')}")
            lines.append("")
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: generate-dept.py <Departement name>")
        sys.exit(2)
    dept = sys.argv[1]
    if not os.path.exists(FULL):
        print("Error: full-run.json not found in", LOG_DIR); sys.exit(3)
    data = json.load(open(FULL, "r", encoding="utf-8"))
    by_dept = data.get("by_department") or {}
    items = by_dept.get(dept) or by_dept.get(dept.replace(" ", "_")) or []
    out = make_md(dept, items)
    out_path = os.path.join(LOG_DIR, f"department-{dept.replace(' ','_')}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out if out.strip() else f"# {dept} — (Aucune annonce)\n")
    print("Wrote", out_path)

if __name__ == "__main__":
    main()

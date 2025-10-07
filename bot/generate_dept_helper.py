#!/usr/bin/env python3
import os
def safe(x): return x or ""
def classify_day(iso):
    if not iso: return "autres"
    try:
        from datetime import datetime as dt
        d = dt.fromisoformat(iso); wd = d.strftime("%A").lower()
        if "samedi" in wd: return "samedi"
        if "dimanche" in wd: return "dimanche"
    except Exception:
        pass
    return "autres"

def regenerate_all(by_dept, log_dir="/tmp/scrape-debug"):
    os.makedirs(log_dir, exist_ok=True)
    for dept, items in by_dept.items():
        region = items[0].get("region","Autres") if items else "Autres"
        lines = [f"# {dept} — {region}\n"]
        buckets = {"samedi": [], "dimanche": [], "autres": []}
        for it in items:
            buckets[classify_day(it.get("date"))].append(it)
        for key,hdr in (("samedi","Samedi"),("dimanche","Dimanche"),("autres","Autres jours")):
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
            lines.append("")
        path = os.path.join(log_dir, f"department-{dept.replace(' ','_')}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) if lines else f"# {dept}\n\n(Aucune annonce)")

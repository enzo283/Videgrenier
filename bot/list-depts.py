#!/usr/bin/env python3
import os, json
LOG_DIR = "/tmp/scrape-debug"
FULL = os.path.join(LOG_DIR, "full-run.json")

def main():
    if not os.path.exists(FULL):
        print("full-run.json not found in", LOG_DIR); return
    data = json.load(open(FULL, "r", encoding="utf-8"))
    by_dept = data.get("by_department") or {}
    rows = []
    for d, items in sorted(by_dept.items(), key=lambda x: x[0].lower()):
        fn = f"department-{d.replace(' ','_')}.md"
        path = os.path.join(LOG_DIR, fn)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        rows.append((d, len(items), fn, size))
    print("Departement | #annonces | fichier | bytes")
    for r in rows:
        print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]}")

if __name__ == "__main__":
    main()

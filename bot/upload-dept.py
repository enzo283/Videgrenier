#!/usr/bin/env python3
import os, sys, requests

LOG_DIR = "/tmp/scrape-debug"
WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not WEBHOOK:
    print("Set DISCORD_WEBHOOK env var"); sys.exit(2)

def main():
    if len(sys.argv) < 2:
        print("Usage: upload-dept.py <Departement name>"); sys.exit(2)
    dept = sys.argv[1]
    fn = f"department-{dept.replace(' ','_')}.md"
    path = os.path.join(LOG_DIR, fn)
    if not os.path.exists(path):
        print("File not found:", path); sys.exit(3)
    with open(path, "rb") as f:
        files = {"file": (fn, f)}
        r = requests.post(WEBHOOK, files=files, timeout=60)
        try:
            r.raise_for_status()
            print("Uploaded", fn)
        except Exception as e:
            print("Upload failed:", e, r.status_code, r.text)

if __name__ == "__main__":
    main()

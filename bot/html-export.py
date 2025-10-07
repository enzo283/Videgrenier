#!/usr/bin/env python3
import os, glob, markdown
LOG_DIR = "/tmp/scrape-debug"
OUT_DIR = os.path.join(LOG_DIR, "html")
TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial; margin:24px; max-width:900px}}
h1{{color:#1b3b6f}}
h2{{color:#2b6a9b}}
pre, code{{background:#f6f8fa;padding:8px;border-radius:6px}}
.md-meta{{color:#555;font-size:0.95em;margin-bottom:8px}}
.card{{border:1px solid #e1e4e8;padding:12px;border-radius:8px;margin-bottom:10px}}
</style></head><body>
{body}
</body></html>"""

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for path in glob.glob(os.path.join(LOG_DIR, "department-*.md")):
        name = os.path.basename(path).rsplit(".",1)[0]
        md = open(path, "r", encoding="utf-8").read()
        html = markdown.markdown(md, extensions=['fenced_code','tables'])
        out = TEMPLATE.format(title=name, body=html)
        out_path = os.path.join(OUT_DIR, name + ".html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out)
        print("Wrote", out_path)

if __name__ == "__main__":
    main()

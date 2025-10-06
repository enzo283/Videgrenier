import os, requests
INDEX = os.getenv("SOURCE_URL", "http://agenda-des-brocantes.fr")
print("INDEX_URL =", INDEX)
try:
    r = requests.get(INDEX, timeout=15, headers={"User-Agent":"scraper-test/1.0"})
    print("Status:", r.status_code)
    print("Redirected to:", r.url)
    print("Content-start:\n", (r.text or "")[:600].replace("\n"," "))
except Exception as e:
    print("Request error:", e)

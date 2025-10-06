Usage and notes for the scraper + notifier.

Secrets required:
- SOURCE_URL: site root or listing page (example: https://www.lesvidegreniers.fr)
- DISCORD_WEBHOOK: full Discord webhook URL

What the pipeline does:
- Runs weekly (cron) or on manual dispatch.
- Downloads SOURCE_URL HTML, runs a site-specific scraper if available,
  otherwise falls back to a generic scraper.
- Extracts title, link, date, place, excerpt.
- Normalizes/deduplicates results.
- Sends results to DISCORD_WEBHOOK as embeds (batched).
- If embeds fail or are too large, the workflow uploads a JSON file artifact with full results.

Debugging:
- After run, download the artifact "scrape-debug" which contains a small curl output and the script stdout.
- The script also writes /tmp/scrape-debug/full-run.json with the structured items.

Extending:
- To support another site, add a new Scraper class in `bot/scraper.py` and update `select_scraper`.

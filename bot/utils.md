README: Scraper orienté "liste par département"

Secrets:
- SOURCE_URL: https://www.lesvidegreniers.fr
- DISCORD_WEBHOOK: https://discord.com/api/webhooks/...

Comportement:
- Scrape la page SOURCE_URL (site-specific scraper pour lesvidegreniers.fr).
- Normalise URLs, splitte blocs multiples, suit pages détail (detail_vg.php) pour enrichir.
- Filtre menus/départements et garde les annonces.
- Regroupe PAR DÉPARTEMENT (ordre alphabétique) et trie par date.
- Envoie sur Discord: message d'en-tête puis un message par département (embed si court, fichier si trop long).
- Logs: /tmp/scrape-debug/full-run.json et /tmp/scrape-debug/summary_by_department.txt

Conseils:
- Si tu veux filtrer uniquement certains départements, je peux ajouter un whitelist (liste de codes ou noms).
- Si tu veux augmenter le nombre de pages détail suivies, modifie MAX_FOLLOW dans `scraper.normalize_items`.
- Après run, télécharge l'artifact "scrape-debug" et colle le JSON si quelque chose cloche.

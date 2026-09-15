# DrJonsson (mappen aaron-prints) – regler för AI-agenter

Läs `../.agents/PROTOKOLL.md` först (pengar, tillstånd, omstart).

- **Pengar:** `printify_bulk.py --publish` skapar Etsy-listningar à 0,20 USD. Kör aldrig
  `--publish` utan Marcs uttryckliga ja för just den körningen. `--dry-run` är alltid fritt.
- **Konton:** Etsy-, Printify- och Stripe-konton, ID-verifiering, bankuppgifter och API-token
  skapas av Marc själv. Ingen agent fyller i lösenord, kort eller ID.
- **Bilderna** genereras lokalt (Z-Image-Turbo, `pipeline/generate_daily.py`) – gratis. Inga
  betalda bildtjänster (Higgsfield, Gemini-bilder) utan Marcs ja. Slim Aarons-stilen bara i prompten,
  aldrig hans namn i butikstext.
- **Daglig körning:** uppgiften `DrJonsson-Daily` 07:30 (`schedule/`). Dashboard: docs/ → GitHub Pages.
- Hemligheter ligger i `pipeline/.env` (gitignorad). Aldrig i kod, aldrig i listings.json.
- Guide och status: `README.md`. Varumärke: `brand/BRAND.md`.

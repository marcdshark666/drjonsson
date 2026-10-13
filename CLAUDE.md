# DrJonsson (mappen aaron-prints) – regler för AI-agenter

Läs `../.agents/PROTOKOLL.md` först (pengar, tillstånd, omstart).

> **2026-10-13 (Marc): fotokonceptet "Aaron" är AVSLUTAT – fokus är nu "DrJonsson 3D Prints"
> (3D-printade föremål på Etsy DrJonssonDesign).** `DrJonsson-Daily/-Drain/-Etsy` är avstängda,
> de 39 Etsy-listningarna raderade (backup `state/etsy-borttagning-20261013-backup.json`),
> Pop-Up-butiken drjonsson.printify.me ligger kvar som fotoarkiv. Sajten docs/ = 3D Prints-sidan,
> grafik i `branding/`. Slå inte på bildgenereringen igen utan Marcs ja. Reglerna nedan gäller
> den gamla fotokedjan.

- **Pengar:** `printify_bulk.py --publish` skapar Etsy-listningar à 0,20 USD. Kör aldrig
  `--publish` utan Marcs uttryckliga ja för just den körningen. `--dry-run` är alltid fritt.
- **Konton:** Etsy-, Printify- och Stripe-konton, ID-verifiering, bankuppgifter och API-token
  skapas av Marc själv. Ingen agent fyller i lösenord, kort eller ID.
- **Bilderna** genereras lokalt (Z-Image-Turbo, `pipeline/generate_daily.py`) – gratis. Inga
  betalda bildtjänster (Higgsfield, Gemini-bilder) utan Marcs ja. Slim Aarons-stilen bara i prompten,
  aldrig hans namn i butikstext.
- **Daglig körning:** uppgiften `DrJonsson-Daily` 07:30 (`schedule/`), **35 motiv per dygn**
  (Marc 2026-09-16). Volymen står på två ställen: `motifs.DAILY_COUNT` och `daily.ps1 -Count`.
  Printify-delen har tidsbudget (`--printify-minutes`) och tar efterslapningen nästa körning. Dashboard: docs/ → GitHub Pages.
- Hemligheter ligger i `pipeline/.env` (gitignorad). Aldrig i kod, aldrig i listings.json.
- Guide och status: `README.md`. Varumärke: `brand/BRAND.md`.

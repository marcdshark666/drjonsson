# DrJonsson – Rich in every frame

Fem nya motiv om dagen i Slim Aarons-anda ("attractive people doing attractive things in
attractive places"), genererade gratis på den egna RTX 4090:n, tryckta på beställning av Printify
och sålda via Pop-Up-storen `drjonsson.printify.me` och Etsy-butiken DrJonsson.

- **Dashboard:** https://marcdshark666.github.io/drjonsson/ (GitHub Pages, repo `marcdshark666/drjonsson`)
- **Mapp:** `APP ideas/aaron-prints` (mappnamnet är kvar; allt synligt heter DrJonsson)
- **Daglig körning:** Windows-uppgiften `DrJonsson-Daily` 07:30 → `schedule/daily.ps1` → `pipeline/generate_daily.py`

## Kedjan varje morgon

```
motifs.pick(datum)            plats × sällskap × ljus, datumet som frö, inga upprepningar
   → generate_image()         Z-Image-Turbo (Tongyi-MAI) via diffusers, 1536×2304 → 3600×5400 JPEG
   → listings.json            titel ≤140, 13 taggar ≤20 tecken, beskrivning
   → printify_bulk.py         upload + poster 12×18/18×24/24×36 (Sensaria)
        Pop-Up-butiken        publiceras direkt (gratis, 0 % provision)
        Etsy                  utkast gratis; publicering (0,20 USD/st) frågas i Telegram med foto
   → docs/data/status.json    + docs/img/<slug>.jpg → git push → dashboarden
   → Telegram                 kontaktark med dagens fem + länk
```

Modellen ligger i `E:\CHAT-RTX\hf-cache` (HF_HOME). Första nedladdningen ~20 GB.
Bilderna i full storlek ligger i `outputs/<datum>/` (gitignorat); bara 800 px-thumbnails går till GitHub.

## Kommandon

```
.venv\Scripts\python.exe pipeline\generate_daily.py --dry-run          # välj motiv, generera inget
.venv\Scripts\python.exe pipeline\generate_daily.py                    # hela kedjan för idag
.venv\Scripts\python.exe pipeline\generate_daily.py --no-printify --no-push --no-telegram
python pipeline\printify_bulk.py --shops                               # butiks-id till .env
python pipeline\printify_bulk.py --only <slug1>,<slug2> --shop <id> --publish
powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule\install_task.ps1   # (om)registrera 07:30
```

## Det som bara Marc kan göra (dashboardens "Att göra")

Ordning: Printify-konto → Pop-Up Store (namn `drjonsson`) + Stripe → API-token i `pipeline/.env`
(`PRINTIFY_TOKEN`, `PRINTIFY_POPUP_SHOP_ID`) → Etsy-butik (setup 15–29 USD, ID-verifiering) →
koppla Printify↔Etsy → `PRINTIFY_ETSY_SHOP_ID` → testköp → Skatteverket.
Claude öppnar rätt sida i Chrome och förklarar fälten; lösenord, kort och ID fyller Marc i själv.

## Regler

- Ingenting som kostar utan Marcs ja: Etsy-publicering frågas per dag i Telegram (`telegram-godkann.js`).
- Slim Aarons nämns bara i prompten. Aldrig i titlar, taggar, beskrivningar eller butiksnamn (Getty).
- Etsy kräver att AI-genererade bilder anges i listningen ("creativity standards"). Görs i Etsy per listning.
- EU-kunder har 14 dagars ångerrätt på icke-personaliserade varor: returpolicy "accepteras".

## Avgifter (18×24", 39 USD, köparen betalar frakt ~8 USD)

| | USD |
|---|---|
| Sensaria tryck | −12,00 |
| Etsy: listning 0,20 + 6,5 % + Payments ~4 % + 0,30 | −5,44 |
| Kvar via Etsy | ≈ 21,50 (≈ 14,50 om Offsite Ads, 15 %) |
| Kvar via Pop-Up | ≈ 26 (minus Stripe) |

## Källor

Printify Etsy-integration https://printify.com/etsy/ · Pop-Up https://printify.com/pop-up-store/ ·
Utbetalning https://help.printify.com/hc/en-us/articles/12051908094993 · Etsy-avgifter 2026
https://printify.com/blog/how-much-does-etsy-take-per-sale/ · Setup-avgift
https://help.erank.com/blog/understanding-etsys-new-15-setup-fee/ · Printify API https://developers.printify.com/ ·
Z-Image-Turbo https://huggingface.co/Tongyi-MAI/Z-Image-Turbo (Apache 2.0)

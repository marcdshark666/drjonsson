# AARON – Rich in every frame

Print-on-demand-butik med fotografen Aarons bilder av de rika. Printify trycker och skickar,
Etsy ger trafiken, Printify Pop-Up är den egna sajten. Skapad 2026-09-15.

## ⚠️ Innan något annat: rättigheterna

Bilderna får bara säljas som tryck om **du äger dem** eller har **skriftlig licens som uttryckligen
täcker kommersiell tryckförsäljning** (inte bara "får publiceras"). Är Aaron en annan verklig
fotograf: avtal med honom om royalty/andel innan första listningen. Är det riktiga, igenkännbara
personer på bilderna behövs dessutom **model release** – annars är kommersiell försäljning ett
intrång även om fotot är hans. Etsy stänger butiker vid första IP-anmälan.

Är bilderna AI-genererade måste Etsy-listningen sedan 2024 ange att du använt AI-verktyg
("Creativity standards"). Skriptet skriver inte det åt dig; det sätts per listning i Etsy.

## Arkitekturen (det bästa upplägget enligt Printifys egna guider och Etsy-forumen)

```
images/*.jpg ──> printify_bulk.py ──> Printify (produkter, mockups, tryck, frakt)
                                          │
                       ┌──────────────────┴──────────────────┐
                       ▼                                     ▼
                Etsy-butik "AARON"                Pop-Up: aaron.printify.me
                trafik från Etsys sök             egen adress, 0 kr, 0 % provision
                ~10–11 % avgifter + 0,20 USD/listning       men du drar trafiken själv
                       │                                     │
                       └──────── kund betalar ───────────────┘
                                          │
                       Printify drar tryck+frakt, du får mellanskillnaden
                       (Etsy: till Etsy Payments → din bank;  Pop-Up: via Stripe)
```

**Varför båda:** Etsy ger köpare från dag ett men tar avgifter. Pop-Up-storen är gratis och
provisionsfri men har ingen trafik – den blir länken i Instagram/TikTok-bio. Samma Printify-produkt
kopieras till båda ("Copy to another store" i Printify).

**Tryckeri:** Sensaria (id 2) för väggkonst – störst i USA, 175 g matt papper. Undvik "Printify
Choice" för posters (byter tryckeri utan att säga till, ojämn kvalitet). Vill du sälja till EU-kunder
utan tull: lägg till en EU-leverantör (`--providers` visar vilka) som andra produkt.

## Vad Claude gjorde (klart)

| Del | Fil |
|---|---|
| Varumärke: namn, slogan *Rich in every frame*, färger, tonalitet | `brand/BRAND.md` |
| Logotyp ljus/mörk + kvadratiskt monogram (SVG) | `brand/logo.svg`, `logo-dark.svg`, `monogram.svg` |
| 20 färdiga listningar: titel (≤140 tecken), 13 taggar (≤20 tecken), beskrivning | `listings/listings.json` |
| Skript som laddar upp bilder, skapar posterprodukter i 3 storlekar, publicerar | `pipeline/printify_bulk.py` |

Skriptet är testat för syntax och förkontroll, **inte mot Printify live** – det kräver din token.

## Vad du måste göra själv (kan inte delegeras)

Ordningen spelar roll. Kostnader markeras med 💰.

1. **Printify-konto** – printify.com, gratis. Hoppa över Premium (29 USD/mån ger 20 % rabatt
   på tryck; lönar sig först runt 100+ beställningar/mån).
2. **Pop-Up Store** – Printify › My stores › Add store › Pop-Up Store. Namn `aaron`
   (blir aaron.printify.me). Klart på två minuter. **Stripe-verifiering** krävs innan första
   utbetalningen (ID + bank); första utbetalningen hålls 7 dagar.
3. **Etsy-konto** 💰 – etsy.com/sell. Butiksnamn `AARONprints` eller `RichInEveryFrame`
   (AARON ensamt är troligen taget). Etsy tar en **engångs setup-avgift på 15–29 USD** och
   kräver **ID-verifiering** (foto-ID + selfie via Persona) samt bankkonto för Etsy Payments.
   Sverige stöds. Fyll i "production partner": Printify (Etsy kräver att det anges).
4. **Koppla Printify → Etsy** – Printify › My stores › Connect › Etsy › godkänn i Etsy-fönstret.
   Klart under 10 min. Etsy-butiken måste vara öppen (en första listning krävs för att öppna;
   gör den billigaste 12×18 som första listning 💰 0,20 USD).
5. **API-token** – Printify › My profile › Connections › Generate token, scopes
   `shops.read catalog.read uploads.write products.write`. Klistra i `pipeline/.env`
   (kopiera `.env.example`). Kör `python pipeline/printify_bulk.py --shops` och sätt
   `PRINTIFY_SHOP_ID` till Etsy-butikens id.
6. **Bilderna** – lägg 20 filer i `images/` döpta exakt som sluggarna i `listings.json`
   (`yacht-club.jpg`, `polo-morning.jpg` …). Krav: stående format 2:3, **minst 3600×5400 px**,
   helst 7200×10800 (300 dpi på 24×36"). sRGB, JPEG kvalitet 90+ eller PNG. Byt gärna titlarna
   i `listings.json` så de matchar motiven – rubrikerna är mina förslag.
7. **Torrkörning** – `python pipeline/printify_bulk.py --dry-run`. Rätta det den klagar på.
8. **Skapa utkast** – `python pipeline/printify_bulk.py`. Öppna Printify › Products och
   kontrollera mockups (bilden ska fylla ytan; skriptet centrerar med scale 1).
9. **Publicera** 💰 – `python pipeline/printify_bulk.py --publish` = 20 × 0,20 USD = 4 USD.
   Skriptet frågar en gång till. Efter publicering: gå in i varje Etsy-listning och sätt
   *Who made it / What is it / When* (Etsys "creativity standards"), samt AI-upplysning om det gäller.
10. **Butiken** – ladda upp `brand/logo.svg` som banner (exportera 1200×300 PNG) och
    `monogram.svg` som ikon (500×500). Skriv "About", returpolicy (Printify: omtryck vid
    tryckfel, inga ångerreturer på made-to-order – men EU-konsumenter har 14 dagars ångerrätt
    på icke-personaliserade varor, så sätt policyn till "returer accepteras" för att inte bryta
    mot lagen), och fraktprofil (Printify skapar den automatiskt).
11. **Testköp** 💰 – beställ ett 12×18 till dig själv (~15 USD med frakt). Alla guider säger
    samma sak: se papperet innan du säljer det.
12. **Skatt** – tala med Skatteverket eller din redovisare: regelbunden försäljning är
    näringsverksamhet (enskild firma, F-skatt, momsregistrering). Etsy rapporterar EU-säljares
    intäkter till skattemyndigheterna (DAC7) sedan 2023.

## Avgifter och marginal (exempel 18×24", pris 39 USD, köparen betalar frakt)

| Post | USD |
|---|---|
| Kundpris | 39,00 |
| Sensaria tryck (ungefär) | −12,00 |
| Etsy listning | −0,20 |
| Etsy transaktion 6,5 % (på pris + frakt ~8) | −3,06 |
| Etsy Payments (EU-nivå ~4 % + 0,30) | −2,18 |
| **Kvar till dig** | **≈ 21,50** |
| Om köpet kom via Offsite Ads (obligatoriskt, 15 % under 10 000 USD/år) | −7,05 → ≈ 14,50 |

Samma poster i Pop-Up-storen: 39 − 12 = **27 USD** minus Stripes avgift. Därför är den egna
sajten värd att driva trafik till.

## Lärdomar från Etsy-forumen och guiderna

- **Gratis frakt över 35 USD** boostar Etsy-ranking i USA – baka in frakten i priset på 18×24
  och 24×36.
- Titeln: viktigaste sökordet först. Alla 13 taggar, inga upprepningar av titeln.
- Etsy ger nya listningar en synlighetsboost; publicera gärna 2–3 om dagen i stället för 20 på
  en gång, så håller boosten i en vecka.
- Mockups: lägg till 2–3 egna "lifestyle"-bilder (tavlan på en vägg) utöver Printifys. Det är
  den vanligaste skillnaden mellan butiker som säljer och inte.
- En leverantör per produkt. Blanda aldrig Sensaria och Printify Choice i samma listning.
- Fotodisplayproblem: ibland syns bara en bild i Etsy efter publicering – öppna listningen i
  Etsy och spara om, det löser det.
- Kolla `state.json` innan du kör om skriptet: det hoppar över redan skapade produkter, så det
  är säkert att köra igen efter ett fel.

## Källor

- Printify Etsy-integration: https://printify.com/etsy/ · https://skup.net/blog/how-to-connect-printify-to-etsy/
- Pop-Up Store: https://printify.com/pop-up-store/ · https://help.printify.com/hc/en-us/articles/12051908094993
- Etsy-avgifter 2026: https://printify.com/blog/how-much-does-etsy-take-per-sale/ · https://craftybase.com/blog/the-complete-guide-to-etsy-fees
- Setup-avgift och ID-verifiering: https://help.erank.com/blog/understanding-etsys-new-15-setup-fee/ · https://help.etsy.com/hc/en-us/articles/22504854625815
- Printify API: https://developers.printify.com/
- Sensaria: https://printify.com/app/print-provider/2/sensaria · Posterblueprint 282: https://printify.com/app/products/282/generic-brand/matte-vertical-posters
- Digitalt vs fysiskt: https://printshrimp.com/blogs/news/digital-wallart-etsy
- Etsy community om Printify-strul: https://community.etsy.com/t5/Technical-Issues/Printify/td-p/144368590

Obs: sökningarna hittade inga specifika Reddit-trådar; underlaget är Printifys och Etsys egna
hjälpsidor, Etsy-communityt och 2026-guider.

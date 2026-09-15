#!/usr/bin/env python3
"""
DrJonsson - bulkskapa posterprodukter i Printify fran en mapp med bilder.

Flode per bild:
  images/<slug>.jpg  +  listings/listings.json[<slug>]
    -> ladda upp bilden till Printify
    -> skapa produkt (Matte Vertical Posters, blueprint 282) med valda storlekar
    -> (valfritt) publicera till den butik som shop_id pekar pa (Etsy eller Pop-Up)

Kraver bara Python 3.9+ standardbibliotek. Ingen pip.

Miljovariabler (lagg i .env bredvid detta skript, aldrig i git):
  PRINTIFY_TOKEN    personlig API-token (Printify > My profile > Connections > API)
  PRINTIFY_SHOP_ID  butikens id (hamta med --shops)

Exempel:
  python printify_bulk.py --shops                 # lista butiker och deras id
  python printify_bulk.py --variants              # visa storlekar hos vald leverantor
  python printify_bulk.py --dry-run               # visa exakt vad som skulle skapas
  python printify_bulk.py                         # skapa produkter som utkast
  python printify_bulk.py --publish               # skapa och publicera (kostar Etsy-listningsavgift!)
  python printify_bulk.py --only yacht-club --publish

Publicering till Etsy kostar 0,20 USD per listning. Skriptet vagrar publicera
utan flaggan --publish, och fragar en gang till om det ar fler an 5 bilder.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.printify.com/v1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
IMAGES_DIR = ROOT / "images"
LISTINGS = ROOT / "listings" / "listings.json"
STATE = HERE / "state.json"          # slug -> {upload_id, product_id, published}

# Matte Vertical Posters (Generic brand) = blueprint 282.
# Leverantor: 2 = Sensaria (USA, storst pa vaggkonst). Byt till EU-leverantor
# med --provider nar --providers visar vilka som finns.
DEFAULT_BLUEPRINT = 282
DEFAULT_PROVIDER = 2

# Storlek (tum, som Printify skriver varianttiteln) -> pris i USD-cent.
# Utgangsforslag: Sensarias kostnad ligger ungefar 5-19 USD, sa detta ger
# ~55-60 % bruttomarginal fore Etsys avgifter (~10 %).
DEFAULT_PRICES = {
    '12" x 18"': 2900,
    '18" x 24"': 3900,
    '24" x 36"': 5900,
}

# Minsta pixelmatt for 150 dpi pa 24x36 (Printify varnar under ~150 dpi).
MIN_PX = (3600, 5400)


def env() -> dict[str, str]:
    """Laser .env (KEY=VALUE) utan externa paket."""
    out: dict[str, str] = {}
    p = HERE / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    out.update({k: v for k, v in os.environ.items() if k.startswith("PRINTIFY_")})
    return out


class Printify:
    def __init__(self, token: str):
        self.token = token

    def call(self, method: str, path: str, body: dict | None = None, retries: int = 3):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{API}{path}", data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("User-Agent", "drjonsson-prints/1.0")
        req.add_header("Content-Type", "application/json")
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    txt = r.read().decode()
                    return json.loads(txt) if txt else {}
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")
                if e.code == 429 and attempt < retries - 1:
                    time.sleep(10 * (attempt + 1))
                    continue
                raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {msg}") from None
            except urllib.error.URLError as e:
                if attempt < retries - 1:
                    time.sleep(5)
                    continue
                raise RuntimeError(f"{method} {path} -> natverksfel: {e}") from None

    # --- katalog ---
    def shops(self):
        return self.call("GET", "/shops.json")

    def providers(self, blueprint: int):
        return self.call("GET", f"/catalog/blueprints/{blueprint}/print_providers.json")

    def variants(self, blueprint: int, provider: int):
        return self.call("GET", f"/catalog/blueprints/{blueprint}/print_providers/{provider}/variants.json")

    # --- skapa ---
    def upload(self, path: Path):
        raw = path.read_bytes()
        if len(raw) > 45 * 1024 * 1024:
            raise RuntimeError(f"{path.name} ar {len(raw)/1e6:.0f} MB - Printify tar max ~50 MB per bild")
        return self.call("POST", "/uploads/images.json", {
            "file_name": path.name,
            "contents": base64.b64encode(raw).decode(),
        })

    def create_product(self, shop: str, body: dict):
        return self.call("POST", f"/shops/{shop}/products.json", body)

    def publish(self, shop: str, product_id: str):
        return self.call("POST", f"/shops/{shop}/products/{product_id}/publish.json", {
            "title": True, "description": True, "images": True,
            "variants": True, "tags": True, "keyFeatures": True, "shipping_template": True,
        })


def image_size(path: Path) -> tuple[int, int] | None:
    """Pixelmatt for PNG/JPEG utan Pillow. None om okant format."""
    with path.open("rb") as f:
        head = f.read(26)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                if marker[1] in (0xC0, 0xC1, 0xC2):
                    f.read(3)
                    h = int.from_bytes(f.read(2), "big")
                    w = int.from_bytes(f.read(2), "big")
                    return w, h
                seg = int.from_bytes(f.read(2), "big")
                f.seek(seg - 2, 1)
    return None


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")


def pick_variants(all_variants: list[dict], prices: dict[str, int]) -> list[dict]:
    """Valjer de varianter vars titel innehaller en storlek ur prislistan.
    Undviker dubbelmatchning (t.ex. att '12" x 18"' matchar '12" x 18" / Framed')."""
    chosen = []
    for v in all_variants:
        title = v.get("title", "")
        for size, price in prices.items():
            if size in title and "/" not in title:
                chosen.append({"id": v["id"], "price": price, "is_enabled": True})
                break
    return chosen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shops", action="store_true", help="lista butiker (Etsy / Pop-Up) och deras id")
    ap.add_argument("--providers", action="store_true", help="lista tryckerier for posterblueprinten")
    ap.add_argument("--variants", action="store_true", help="lista storlekar hos valt tryckeri")
    ap.add_argument("--blueprint", type=int, default=DEFAULT_BLUEPRINT)
    ap.add_argument("--provider", type=int, default=DEFAULT_PROVIDER)
    ap.add_argument("--only", help="kor bara dessa slugs (kommaseparerade)")
    ap.add_argument("--shop", help="butiks-id, overstyr PRINTIFY_SHOP_ID")
    ap.add_argument("--dry-run", action="store_true", help="visa vad som skulle goras, skapa ingenting")
    ap.add_argument("--publish", action="store_true", help="publicera till butiken (Etsy tar 0,20 USD per listning)")
    ap.add_argument("--yes", action="store_true", help="hoppa over bekraftelsefragan vid --publish")
    args = ap.parse_args()

    e = env()
    token = e.get("PRINTIFY_TOKEN")
    if not token:
        print("Saknar PRINTIFY_TOKEN. Skapa pipeline/.env fran .env.example.", file=sys.stderr)
        return 2
    api = Printify(token)

    if args.shops:
        for s in api.shops():
            print(f"  id={s['id']:<10} {s['title']:<30} kanal={s.get('sales_channel')}")
        return 0
    if args.providers:
        for p in api.providers(args.blueprint):
            print(f"  id={p['id']:<6} {p['title']}")
        return 0
    if args.variants:
        for v in api.variants(args.blueprint, args.provider).get("variants", []):
            print(f"  id={v['id']:<8} {v['title']}")
        return 0

    shop = args.shop or e.get("PRINTIFY_SHOP_ID") or e.get("PRINTIFY_POPUP_SHOP_ID")
    if not shop:
        print("Saknar PRINTIFY_SHOP_ID. Kor --shops och lagg id:t i .env.", file=sys.stderr)
        return 2

    if not LISTINGS.exists():
        print(f"Saknar {LISTINGS}", file=sys.stderr)
        return 2
    listings = json.loads(LISTINGS.read_text(encoding="utf-8"))
    prices = {k: int(v) for k, v in listings.get("_prices", DEFAULT_PRICES).items()}
    common_tail = listings.get("_description_tail", "")
    items = {k: v for k, v in listings.items() if not k.startswith("_")}

    images = sorted(p for p in IMAGES_DIR.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if args.only:
        wanted = set(args.only.split(","))
        images = [p for p in images if p.stem in wanted]
    if not images:
        print(f"Inga bilder i {IMAGES_DIR} (jpg/png). Dop dem efter slug i listings.json.", file=sys.stderr)
        return 2

    # Forkontroll: varje bild maste ha en listning och tillracklig upplosning.
    problems = []
    for p in images:
        if p.stem not in items:
            problems.append(f"{p.name}: ingen post '{p.stem}' i listings.json")
        sz = image_size(p)
        if sz and (sz[0] < MIN_PX[0] or sz[1] < MIN_PX[1]):
            problems.append(f"{p.name}: {sz[0]}x{sz[1]} px - behover minst {MIN_PX[0]}x{MIN_PX[1]} for 24x36 (helst 7200x10800)")
        lst = items.get(p.stem, {})
        if len(lst.get("tags", [])) > 13:
            problems.append(f"{p.name}: Etsy tillater max 13 taggar")
        if any(len(t) > 20 for t in lst.get("tags", [])):
            problems.append(f"{p.name}: en tagg ar langre an 20 tecken")
        if len(lst.get("title", "")) > 140:
            problems.append(f"{p.name}: titeln ar langre an 140 tecken")
    if problems:
        print("STOPP - ratta forst:")
        for x in problems:
            print("  -", x)
        return 1

    variants_all = api.variants(args.blueprint, args.provider).get("variants", [])
    chosen = pick_variants(variants_all, prices)
    if not chosen:
        print("Hittade inga varianter som matchar storlekarna i _prices. Kor --variants och justera.", file=sys.stderr)
        return 1
    variant_ids = [v["id"] for v in chosen]

    if args.publish and not args.dry_run and len(images) > 5 and not args.yes:
        ans = input(f"Publicera {len(images)} listningar (~{0.2*len(images):.2f} USD i Etsy-avgift)? skriv ja: ")
        if ans.strip().lower() != "ja":
            print("Avbrutet.")
            return 0

    state = load_state()
    for p in images:
        lst = items[p.stem]
        st = state.setdefault(f"{shop}:{p.stem}", {})
        # uppladdningen ar gemensam for alla butiker
        for k, v in state.items():
            if k.endswith(":" + p.stem) and v.get("upload_id") and not st.get("upload_id"):
                st["upload_id"] = v["upload_id"]
        body = {
            "title": lst["title"],
            "description": (lst["description"].rstrip() + "\n\n" + common_tail).strip(),
            "tags": lst.get("tags", []),
            "blueprint_id": args.blueprint,
            "print_provider_id": args.provider,
            "variants": chosen,
            "print_areas": [{
                "variant_ids": variant_ids,
                "placeholders": [{
                    "position": "front",
                    "images": [{"id": st.get("upload_id", "<uppladdning>"), "x": 0.5, "y": 0.5, "scale": 1, "angle": 0}],
                }],
            }],
        }
        print(f"\n=== {p.stem} ===")
        print(f"  titel : {lst['title']}")
        print(f"  taggar: {', '.join(lst.get('tags', []))}")
        print(f"  storlekar: {len(chosen)} st, pris {min(prices.values())/100:.0f}-{max(prices.values())/100:.0f} USD")
        if args.dry_run:
            print("  (dry-run - inget skickas)")
            continue

        if not st.get("upload_id"):
            up = api.upload(p)
            st["upload_id"] = up["id"]
            save_state(state)
            print(f"  uppladdad: {up['id']} ({up.get('width')}x{up.get('height')})")
        body["print_areas"][0]["placeholders"][0]["images"][0]["id"] = st["upload_id"]

        if not st.get("product_id"):
            prod = api.create_product(shop, body)
            st["product_id"] = prod["id"]
            save_state(state)
            print(f"  produkt skapad: {prod['id']}")
        else:
            print(f"  produkt finns redan: {st['product_id']} (hoppar over)")

        if args.publish and not st.get("published"):
            api.publish(shop, st["product_id"])
            st["published"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            save_state(state)
            print("  publicerad -> butiken")
            time.sleep(2)  # gransen ar 200 publiceringar per 30 min; vi ligger langt under

    print("\nKlart. Status i", STATE)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as err:
        print("FEL:", err, file=sys.stderr)
        sys.exit(1)

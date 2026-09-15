#!/usr/bin/env python3
"""
DrJonsson - gor varje motiv till en hel produktfamilj i Printify (poster, inramad,
canvas, metall, akryl, mugg, tygkasse, t-shirt ...) och publicerar. Printify skoter
sedan allt: bestallning, tryck, paket, frakt och sparning. Marc ar aldrig mellanhand.

  images/<slug>.jpg + listings/listings.json[<slug>] + products.json
    -> ladda upp bilden en gang
    -> for varje produkttyp: hitta blueprint + tryckeri i katalogen, valj varianter,
       skapa produkten, las Printifys kostnad, satt pris = kostnad x markup (.99),
       publicera till butiken (Pop-Up gratis; Etsy 0,20 USD per listning)

Miljo (pipeline/.env):
  PRINTIFY_TOKEN, PRINTIFY_POPUP_SHOP_ID, PRINTIFY_ETSY_SHOP_ID (eller --shop)

  python printify_bulk.py --shops                      butiker och id
  python printify_bulk.py --catalog "mug"              sok katalogtitlar (for products.json)
  python printify_bulk.py --resolve                    visa vilket blueprint/tryckeri varje produkttyp far
  python printify_bulk.py --dry-run                    visa allt, skicka inget
  python printify_bulk.py --only a,b --shop 123 --products poster,mug --publish --yes
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

API = "https://api.printify.com/v1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
IMAGES_DIR = ROOT / "images"
LISTINGS = ROOT / "listings" / "listings.json"
PRODUCTS = HERE / "products.json"
STATE = HERE / "state.json"            # "shop:slug:product" -> {product_id, published}; "upload:slug" -> id
CATALOG_CACHE = HERE / "catalog_cache.json"
MIN_PX = (3000, 4500)


def env() -> dict[str, str]:
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

    def call(self, method: str, path: str, body: dict | None = None, retries: int = 4):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{API}{path}", data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("User-Agent", "drjonsson-prints/1.0")
        req.add_header("Content-Type", "application/json")
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    txt = r.read().decode()
                    return json.loads(txt) if txt else {}
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")
                if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                    # 429 "Too Many Attempts" slog till efter ~40 publiceringar i rad (2026-09-15):
                    # vanta rejalt, inte 10 s
                    time.sleep((30, 60, 120)[min(attempt, 2)] if e.code == 429 else 10 * (attempt + 1))
                    continue
                raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {msg[:400]}") from None
            except urllib.error.URLError as e:
                if attempt < retries - 1:
                    time.sleep(5)
                    continue
                raise RuntimeError(f"{method} {path} -> natverksfel: {e}") from None

    def shops(self):
        return self.call("GET", "/shops.json")

    def blueprints(self) -> list[dict]:
        if CATALOG_CACHE.exists() and time.time() - CATALOG_CACHE.stat().st_mtime < 7 * 86400:
            return json.loads(CATALOG_CACHE.read_text(encoding="utf-8"))
        bps = self.call("GET", "/catalog/blueprints.json")
        CATALOG_CACHE.write_text(json.dumps(bps), encoding="utf-8")
        return bps

    def providers(self, blueprint: int):
        return self.call("GET", f"/catalog/blueprints/{blueprint}/print_providers.json")

    def variants(self, blueprint: int, provider: int):
        return self.call("GET", f"/catalog/blueprints/{blueprint}/print_providers/{provider}/variants.json").get("variants", [])

    def upload(self, path: Path):
        raw = path.read_bytes()
        if len(raw) > 45 * 1024 * 1024:
            raise RuntimeError(f"{path.name} ar {len(raw)/1e6:.0f} MB - max ~50 MB")
        return self.call("POST", "/uploads/images.json", {"file_name": path.name, "contents": base64.b64encode(raw).decode()})

    def create_product(self, shop: str, body: dict):
        return self.call("POST", f"/shops/{shop}/products.json", body)

    def update_product(self, shop: str, pid: str, body: dict):
        return self.call("PUT", f"/shops/{shop}/products/{pid}.json", body)

    def publish(self, shop: str, pid: str):
        return self.call("POST", f"/shops/{shop}/products/{pid}/publish.json", {
            "title": True, "description": True, "images": True, "variants": True,
            "tags": True, "keyFeatures": True, "shipping_template": True})


# ---------- katalog ----------

def resolve_blueprint(api: Printify, title: str) -> dict | None:
    bps = api.blueprints()
    t = title.lower()
    exact = [b for b in bps if b["title"].lower() == t]
    if exact:
        return exact[0]
    part = [b for b in bps if t in b["title"].lower()]
    return sorted(part, key=lambda b: len(b["title"]))[0] if part else None


def resolve_provider(api: Printify, blueprint_id: int, wanted: list[str]) -> dict | None:
    provs = api.providers(blueprint_id)
    by = {p["title"].lower(): p for p in provs}
    for w in wanted:
        if w.lower() in by:
            return by[w.lower()]
    return provs[0] if provs else None


def norm(s: str) -> str:
    """Printify skriver tum som ″ (dubbelprim) i vissa varianter och " i andra."""
    return str(s).replace("″", '"').replace("”", '"').replace("×", "x").replace("  ", " ").strip()


def filter_variants(variants: list[dict], cfg: dict) -> list[dict]:
    """include = storlekar (matchas mot options.size eller titeln), colors/sizes/paper = options,
    exclude = delstrangar i titeln som diskvalificerar."""
    out = []
    for v in variants:
        title = norm(v.get("title", ""))
        opts = {k.lower(): norm(val) for k, val in (v.get("options") or {}).items()}
        size = opts.get("size", "")
        if cfg.get("include") and not any(norm(s) == size or norm(s) in title for s in cfg["include"]):
            continue
        if cfg.get("exclude") and any(norm(s) in title for s in cfg["exclude"]):
            continue
        if cfg.get("colors") and opts.get("color") and opts["color"] not in cfg["colors"]:
            continue
        if cfg.get("sizes") and size and size not in [norm(x) for x in cfg["sizes"]]:
            continue
        if cfg.get("paper") and opts.get("paper") and opts["paper"] not in cfg["paper"]:
            continue
        out.append(v)
    return out[: cfg.get("max_variants", 40)]


def price_from_cost(cost_cents: int, markup: float) -> int:
    usd = math.ceil(cost_cents * markup / 100)
    return max(usd, 5) * 100 - 1   # .99


# ---------- hjalp ----------

def image_size(path: Path) -> tuple[int, int] | None:
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


def make_title(name: str, cfg: dict) -> str:
    """Motivets namn ar allt fore ' | ' i listningstiteln."""
    base = name.split(" | ")[0]
    return (base + cfg.get("title_tail", ""))[:140]


# ---------- huvud ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shops", action="store_true")
    ap.add_argument("--catalog", metavar="SOK", help="sok blueprint-titlar i katalogen")
    ap.add_argument("--resolve", action="store_true", help="visa blueprint/tryckeri/antal varianter per produkttyp")
    ap.add_argument("--only", help="slugs, kommaseparerade")
    ap.add_argument("--shop", help="butiks-id (annars PRINTIFY_POPUP_SHOP_ID)")
    ap.add_argument("--products", help="produkttyper, kommaseparerade (annars products.json 'default')")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--publish", action="store_true", help="publicera (Etsy: 0,20 USD per listning)")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    e = env()
    token = e.get("PRINTIFY_TOKEN")
    if not token or token.startswith("eyJ..."):
        print("Saknar PRINTIFY_TOKEN i pipeline/.env", file=sys.stderr)
        return 2
    api = Printify(token)

    if args.shops:
        for s in api.shops():
            print(f"  id={s['id']:<10} {s['title']:<30} kanal={s.get('sales_channel')}")
        return 0
    if args.catalog:
        q = args.catalog.lower()
        for b in api.blueprints():
            if q in b["title"].lower():
                print(f"  id={b['id']:<6} {b['title']}  ({b.get('brand')})")
        return 0

    prod_cfg = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    keys = args.products.split(",") if args.products else prod_cfg.get("default", ["poster"])

    # Los blueprint + tryckeri + varianter per produkttyp (en gang per korning)
    plan: dict[str, dict] = {}
    for key in keys:
        cfg = prod_cfg.get(key)
        if not cfg:
            print(f"  {key}: finns inte i products.json - hoppar over")
            continue
        bp = resolve_blueprint(api, cfg["blueprint"])
        if not bp:
            print(f"  {key}: hittar inget blueprint for '{cfg['blueprint']}' - kor --catalog och ratta products.json")
            continue
        prov = resolve_provider(api, bp["id"], cfg.get("providers", []))
        if not prov:
            print(f"  {key}: inget tryckeri for {bp['title']}")
            continue
        variants = filter_variants(api.variants(bp["id"], prov["id"]), cfg)
        if not variants:
            print(f"  {key}: inga varianter matchade filtret hos {prov['title']}")
            continue
        plan[key] = {"cfg": cfg, "bp": bp, "prov": prov, "variants": variants}
        print(f"  {key:<8} {bp['title']} (id {bp['id']}) hos {prov['title']} (id {prov['id']}), {len(variants)} varianter")
    if args.resolve:
        return 0
    if not plan:
        print("Ingen produkttyp gick att losa.", file=sys.stderr)
        return 1

    shop = args.shop or e.get("PRINTIFY_POPUP_SHOP_ID") or e.get("PRINTIFY_SHOP_ID")
    if not shop:
        print("Saknar butiks-id (--shop eller PRINTIFY_POPUP_SHOP_ID).", file=sys.stderr)
        return 2
    listings = json.loads(LISTINGS.read_text(encoding="utf-8")) if LISTINGS.exists() else {}
    tail = listings.get("_description_tail", "")
    items = {k: v for k, v in listings.items() if not k.startswith("_")}

    images = sorted(p for p in IMAGES_DIR.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if args.only:
        wanted = set(args.only.split(","))
        images = [p for p in images if p.stem in wanted]
    problems = []
    for p in images:
        if p.stem not in items:
            problems.append(f"{p.name}: ingen post i listings.json")
        sz = image_size(p)
        if sz and (sz[0] < MIN_PX[0] or sz[1] < MIN_PX[1]):
            problems.append(f"{p.name}: {sz[0]}x{sz[1]} px < {MIN_PX[0]}x{MIN_PX[1]}")
    if problems:
        print("STOPP:\n  " + "\n  ".join(problems))
        return 1
    if not images:
        print("Inga bilder att kora.", file=sys.stderr)
        return 2

    n_listings = len(images) * len(plan)
    if args.publish and not args.dry_run and not args.yes and n_listings > 5:
        ans = input(f"Publicera {n_listings} produkter i butik {shop}? (Etsy: ~{0.2*n_listings:.2f} USD) skriv ja: ")
        if ans.strip().lower() != "ja":
            return 0

    state = load_state()
    errors = 0
    for p in images:
        lst = items[p.stem]
        print(f"\n=== {p.stem}: {lst['title'].split(' | ')[0]}")
        up_key = f"upload:{p.stem}"
        if not args.dry_run and not state.get(up_key):
            try:
                up = api.upload(p)
                state[up_key] = up["id"]
                save_state(state)
                print(f"  uppladdad {up['id']}")
            except RuntimeError as ex:
                print("  FEL uppladdning:", ex)
                errors += 1
                continue
        upload_id = state.get(up_key, "<upload>")

        for key, pl in plan.items():
            cfg = pl["cfg"]
            skey = f"{shop}:{p.stem}:{key}"
            st = state.setdefault(skey, {})
            title = make_title(lst["title"], cfg)
            tags = (lst.get("tags", [])[:11] + cfg.get("tags_extra", []))[:13]
            body = {
                "title": title,
                "description": (lst["description"].rstrip() + "\n\n" + tail).strip(),
                "tags": tags,
                "blueprint_id": pl["bp"]["id"],
                "print_provider_id": pl["prov"]["id"],
                "variants": [{"id": v["id"], "price": 1999, "is_enabled": True} for v in pl["variants"]],
                "print_areas": [{
                    "variant_ids": [v["id"] for v in pl["variants"]],
                    "placeholders": [{"position": cfg.get("position", "front"),
                                      "images": [{"id": upload_id, "x": cfg.get("x", 0.5), "y": cfg.get("y", 0.5),
                                                  "scale": cfg.get("scale", 1.0), "angle": 0}]}],
                }],
            }
            print(f"  {key:<8} {title[:70]}")
            if args.dry_run:
                continue
            try:
                if not st.get("product_id"):
                    prod = api.create_product(shop, body)
                    st["product_id"] = prod["id"]
                    # pris = Printifys kostnad x markup, avrundat till .99
                    priced = []
                    for v in prod.get("variants", []):
                        if v.get("is_enabled") and v.get("cost"):
                            priced.append({"id": v["id"], "price": price_from_cost(v["cost"], cfg.get("markup", 2.2)), "is_enabled": True})
                    if priced:
                        api.update_product(shop, prod["id"], {"variants": priced})
                        st["price_range"] = [min(x["price"] for x in priced) / 100, max(x["price"] for x in priced) / 100]
                    save_state(state)
                    print(f"           skapad {prod['id']} pris {st.get('price_range')}")
                if args.publish and not st.get("published"):
                    api.publish(shop, st["product_id"])
                    st["published"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    st.pop("error", None)
                    save_state(state)
                    print("           publicerad")
                    time.sleep(4)   # publiceringsgransen: ~40 i rad gav 429
            except RuntimeError as ex:
                print(f"           FEL {key}: {ex}")
                st["error"] = str(ex)[:300]
                save_state(state)
                errors += 1

    print(f"\nKlart. {errors} fel. Status i {STATE}")
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as err:
        print("FEL:", err, file=sys.stderr)
        sys.exit(1)

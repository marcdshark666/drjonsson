import sys
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import generate_daily as g
import printify_bulk as pb

env = g.env()
P = pb.Printify(env["PRINTIFY_TOKEN"])
shop = "28449034"

prod_cfg = json.loads((g.HERE / "products.json").read_text(encoding="utf-8"))
prods = P.call("GET", f"/shops/{shop}/products.json")

print(f"Updating prices for shop {shop} (DrJonssonDesign)...")

for p in prods.get("data", []):
    pid = p["id"]
    title = p.get("title", "")
    
    # Determine product type key
    typ = "poster"
    if "Framed Canvas" in title:
        typ = "framed_canvas"
    elif "Canvas" in title:
        typ = "canvas"
    elif "Framed" in title:
        typ = "framed"
    elif "Metal" in title:
        typ = "metal"
        
    cfg = prod_cfg.get(typ, {})
    markup = cfg.get("markup", 2.2)
    
    # Conversion: 1 USD ~ 10.50 SEK
    # Cost is in USD cents. Multiply by markup and 10.50 to get SEK price in cents
    priced = []
    for v in p.get("variants", []):
        if v.get("is_enabled") and v.get("cost"):
            cost_usd = v["cost"] / 100.0
            price_sek = math.ceil(cost_usd * markup * 10.50) * 100 - 1
            priced.append({"id": v["id"], "price": price_sek, "is_enabled": True})
            
    if priced:
        P.update_product(shop, pid, {"variants": priced})
        min_p = min(x["price"] for x in priced) / 100.0
        max_p = max(x["price"] for x in priced) / 100.0
        print(f"  ✔ {typ.upper():<14} ({pid}): priser uppdaterade till {min_p:.2f} kr - {max_p:.2f} kr SEK")

print("\nAll product prices updated to SEK currency in Printify/Etsy!")

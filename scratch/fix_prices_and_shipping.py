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

print("=== FIXING VARIANT SIZE PRICES & SHIPPING TEMPLATES ===")

for p in prods.get("data", []):
    pid = p["id"]
    title = p.get("title", "")
    
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
    markup = cfg.get("markup", 2.4)
    
    # Calculate price PER VARIANT based on variant cost
    priced = []
    print(f"\nProduct: {title[:50]} ({typ.upper()})")
    for v in p.get("variants", []):
        if v.get("is_enabled") and v.get("cost"):
            cost_usd = v["cost"] / 100.0
            price_sek = math.ceil(cost_usd * markup * 10.50) * 100 - 1
            priced.append({"id": v["id"], "price": price_sek, "is_enabled": True})
            print(f"  • Size: {v.get('title'):<30} | Inköp: ${cost_usd:6.2f} USD ➔ Utpris: {price_sek/100.0:7.2f} kr SEK")
            
    if priced:
        try:
            P.update_product(shop, pid, {"variants": priced})
            print(f"  ✔ Updated variant prices in Printify!")
            
            # Publish with shipping template enabled
            P.publish(shop, pid)
            print(f"  ✔ Published to Etsy with Printify Worldwide Shipping Profile!")
        except Exception as ex:
            print(f"  ⚠️ Error updating {pid}: {ex}")

print("\nDone! All size variant prices and shipping profiles updated!")

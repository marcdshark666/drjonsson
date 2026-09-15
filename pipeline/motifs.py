"""
Motivbank for DrJonsson - "attractive people doing attractive things in attractive places".

Varje motiv = plats x sallskap x ljus. Kombinationerna valjs med dagens datum
som fro sa samma dag alltid ger samma fem, och state/used.json ser till att en
plats+sallskap-kombination inte aterkommer forran allt ar anvant.

Stilen ar Slim Aarons (1950-70-tal, Kodachrome, hog utsiktspunkt, mattat bla
vatten). Hans namn far sta i PROMPTEN (intern), aldrig i titlar, taggar eller
butikstext - Getty ager arkivet och Etsy tar ner listningar pa namnet.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STATE = Path(__file__).resolve().parent.parent / "state" / "used.json"

# (slug, namn i titeln, scenbeskrivning)
PLACES = [
    ("lake-como", "Lake Como", "a terraced villa garden on Lake Como with cypress trees, a long turquoise pool and the lake and mountains beyond"),
    ("palm-springs", "Palm Springs", "a mid-century modernist house in Palm Springs with a kidney-shaped pool, palm trees and desert mountains behind"),
    ("amalfi", "Amalfi Coast", "a cliffside terrace on the Amalfi coast with lemon trees, white parasols and the deep blue Tyrrhenian sea far below"),
    ("gstaad", "Gstaad", "a sun terrace of a chalet in Gstaad with snowy peaks, wooden loungers and fur throws"),
    ("acapulco", "Acapulco", "a cliff-top villa in Acapulco with a white infinity pool, bougainvillea and the Pacific bay glittering below"),
    ("capri", "Capri", "a bathing platform lido on Capri with striped umbrellas, limestone rocks and the Faraglioni in the distance"),
    ("monaco", "Monaco", "a yacht deck in the harbour of Monaco with teak decking, brass rails and the pastel apartment blocks of Monte Carlo behind"),
    ("palm-beach", "Palm Beach", "a manicured lawn of a Palm Beach estate with a pink stucco mansion, clipped hedges and a croquet set"),
    ("saint-tropez", "Saint-Tropez", "the quay of Saint-Tropez with wooden speedboats, pastel houses and café tables under plane trees"),
    ("marbella", "Marbella", "a whitewashed Andalusian villa in Marbella with a blue-tiled pool, orange trees and arched colonnades"),
    ("mustique", "Mustique", "a white sand beach on Mustique with a thatched pavilion, a wooden sailboat and impossibly clear turquoise water"),
    ("cortina", "Cortina d'Ampezzo", "a snowy hotel terrace in Cortina with the pink Dolomites, sunbeds and steaming cups of chocolate"),
    ("beverly-hills", "Beverly Hills", "a Beverly Hills garden with a rectangular pool, a white modernist house, sculpted topiary and palm trees"),
    ("sardinia", "Costa Smeralda", "a rocky cove on the Costa Smeralda in Sardinia with granite boulders, a wooden Riva boat and emerald water"),
    ("riviera-garden", "The Riviera", "a Riviera cypress garden seen from a balcony, with a long sapphire pool, stone balustrades and the Mediterranean beyond"),
    ("lake-geneva", "Lake Geneva", "a lakeside lawn on Lake Geneva with a white wooden pier, a vintage motorboat and the Alps across the water"),
    ("marrakech", "Marrakech", "a riad courtyard in Marrakech with a green-tiled pool, orange trees, ochre walls and a striped cabana"),
    ("bermuda", "Bermuda", "a pink-sand beach in Bermuda with a pastel-yellow colonial house, white shutters and a wooden dinghy"),
    ("cannes", "Cannes", "a hotel balcony on the Croisette in Cannes with white balustrades, palm trees and the bay full of yachts"),
    ("lake-tahoe", "Lake Tahoe", "a timber lodge dock on Lake Tahoe with a mahogany speedboat, pines and clear cobalt water"),
]

# (slug, kort namn, sallskap)
PARTIES = [
    ("magenta-gown", "Magenta at Noon", "an elegant woman in a floor-length sheer magenta gown and a wide white sun hat standing by the pool with two dalmatians"),
    ("tennis-whites", "Tennis Whites", "a couple in crisp 1960s tennis whites with wooden racquets, laughing beside a courtside table with lemonade"),
    ("loungers", "The Loungers", "a group of glamorous friends in colourful swimsuits and caftans on sun loungers under striped umbrellas, cocktails in hand"),
    ("cream-suit", "The Cream Suit", "a silver-haired man in a cream linen suit and sunglasses leaning on a vintage pale-blue convertible"),
    ("caftans", "Three Caftans", "three women in pastel silk caftans and oversized sunglasses holding champagne coupes"),
    ("speedboat", "The Speedboat", "a family in nautical stripes stepping off a polished wooden speedboat with a picnic hamper"),
    ("silk-robe", "The Silk Robe", "an elderly gentleman in a paisley silk dressing gown reading a newspaper with a white standard poodle at his feet"),
    ("emerald-turban", "The Hostess", "a hostess in an emerald turban and gold jewellery arranging a table of pastries and fruit"),
    ("polo", "After Polo", "two polo players in white breeches and coloured jerseys with a groom holding a chestnut horse"),
    ("ski-suits", "Après-ski", "friends in 1970s coloured ski suits and fur hats toasting with hot chocolate on the terrace"),
    ("golf", "The Foursome", "four golfers in cashmere sweaters and plaid trousers with a caddie and vintage golf bags"),
    ("cocktail-hour", "Cocktail Hour", "a crowd in evening wear at a garden cocktail party with waiters in white jackets carrying silver trays"),
    ("water-skis", "Water Skis", "a young woman in a red swimsuit and white cap carrying water skis along the shore"),
    ("gardener", "The Gardener", "a woman in a broad-brimmed hat and gloves cutting roses into a basket while a butler waits with a tray"),
    ("chess", "Chess on the Terrace", "two men in linen shirts playing chess at a marble table under a lemon tree"),
    ("backgammon", "Backgammon", "a couple in swimwear playing backgammon on a striped towel beside the pool"),
    ("horse-riding", "The Morning Ride", "a rider in a hacking jacket on a grey horse on a gravel drive lined with cypresses"),
    ("picnic", "The Picnic", "a picnic on a tartan rug with a wicker hamper, a bottle of rosé in a silver bucket and a vintage convertible parked behind"),
]

LIGHT = [
    "harsh midday sun with short shadows",
    "warm late-afternoon light with long shadows",
    "clear morning light, sky a saturated cerulean",
]

VANTAGE = [
    "photographed from a high vantage point looking down",
    "photographed at eye level with a slightly wide lens",
]

STYLE = (
    "1960s Kodachrome colour photograph in the style of Slim Aarons, society and leisure editorial photography, "
    "medium format film, saturated blues and greens, crisp detail, elegant staged composition, "
    "tall vertical framing, no text"
)
NEGATIVE = "text, watermark, logo, signature, caption, blurry, deformed hands, extra limbs, cartoon, painting, illustration, modern clothing, phone"

BASE_TAGS = ["old money decor", "luxury wall art", "fine art photography", "rich aesthetic",
             "wall art print", "photography print", "matte poster", "drjonsson print", "living room art"]

TITLE_TAIL = " | DrJonsson Fine Art Photography Print | Old Money Aesthetic Wall Art | Luxury Lifestyle Poster"

CAPTIONS = [
    "The yacht is rented. The tan is real.",
    "Eleven a.m. on a Tuesday. Nobody here has a Tuesday.",
    "The bill arrives face down. It has always arrived face down.",
    "Fourteen rooms for two people and a dog with its own room.",
    "Nobody is smiling at the same person.",
    "The pool is heated, unused and photographed daily.",
    "The hedges are older than the family fortune, and better kept.",
    "Cashmere in thirty degrees. The staff carry the conversation.",
    "Every boat is named after a daughter. Every daughter is elsewhere.",
    "The painting is not for sale. The couple looking at it might be.",
]


def _load_used() -> set[str]:
    if STATE.exists():
        return set(json.loads(STATE.read_text(encoding="utf-8")))
    return set()


def _save_used(used: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(used), indent=1), encoding="utf-8")


def pick(day: date, count: int = 5, commit: bool = True) -> list[dict]:
    """Valjer `count` oanvanda plats+sallskap-par for dagen.
    Dagens val sparas i state/day-<datum>.json sa en omkorning samma dag ger SAMMA motiv
    (annars skulle used.json ha stangt dem och en kraschad korning fatt fem nya)."""
    day_file = STATE.parent / f"day-{day.isoformat()}.json"
    if day_file.exists():
        saved = json.loads(day_file.read_text(encoding="utf-8"))
        if len(saved) >= count:
            return saved[:count]
    rng = random.Random(day.isoformat())
    used = _load_used()
    pairs = [(p, s) for p in PLACES for s in PARTIES]
    rng.shuffle(pairs)
    free = [x for x in pairs if f"{x[0][0]}+{x[1][0]}" not in used]
    if len(free) < count:          # allt anvant: borja om
        used = set()
        free = pairs
    chosen = free[:count]
    out = []
    for i, (place, party) in enumerate(chosen, 1):
        key = f"{place[0]}+{party[0]}"
        used.add(key)
        slug = f"{day.strftime('%Y%m%d')}-{i}-{place[0]}-{party[0]}"
        name = f"{party[1]}, {place[1]}"
        prompt = f"{party[2]}, {place[2]}, {rng.choice(LIGHT)}, {rng.choice(VANTAGE)}. {STYLE}"
        place_tag = place[1].lower().replace("'", "")[:20]
        tags = ([f"{place_tag} print", f"{place_tag} poster", "vintage riviera"] + BASE_TAGS)[:13]
        tags = [t[:20] for t in tags]
        title = (name + TITLE_TAIL)[:140]
        out.append({
            "slug": slug, "name": name, "place": place[1], "party": party[1],
            "prompt": prompt, "negative": NEGATIVE, "seed": rng.randrange(1, 2**31),
            "title": title, "tags": tags,
            "description": f"{name}\n\n{rng.choice(CAPTIONS)}\n\nFrom the DrJonsson series: rich in every frame.",
            "key": key,
        })
    if commit:
        _save_used(used)
        day_file.parent.mkdir(parents=True, exist_ok=True)
        day_file.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    for m in pick(d, commit=False):
        print(m["slug"], "|", m["name"])
        print("   ", m["prompt"][:160], "...")

"""
Motivbank for DrJonsson - "attractive people doing attractive things in attractive places".

Varje motiv = plats x sallskap x ljus. Kombinationerna valjs med dagens datum
som fro sa samma dag alltid ger samma motiv, och state/used.json ser till att en
plats+sallskap-kombination inte aterkommer forran allt ar anvant.

Dagsvolymen ar 35 motiv (Marc 2026-09-16). Darfor ar banken 39 platser x 35 sallskap,
och varje sallskap bar en lista `needs` med platstaggar det kraver - annars hamnade
apres-ski i Acapulco och polospelare pa ett yachtdack. ~1000 giltiga par racker en
manad innan used.json nollstalls.

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

DAILY_COUNT = 35          # dagens volym - andras har och i schedule/daily.ps1

# Platstaggar:
#   sun    varmt, badbart      snow   vinter/fjall      water  strand/sjo/hav i bild
#   boat   bat/brygga/hamn     estate gods, grasmatta, stall, golf
#   town   kaj, promenad, stad garden tradgard/terrass
#
# (slug, namn i titeln, scenbeskrivning, taggar)
PLACES = [
    ("lake-como", "Lake Como", "a terraced villa garden on Lake Como with cypress trees, a long turquoise pool and the lake and mountains beyond", ("sun", "water", "garden", "estate")),
    ("palm-springs", "Palm Springs", "a mid-century modernist house in Palm Springs with a kidney-shaped pool, palm trees and desert mountains behind", ("sun", "garden")),
    ("amalfi", "Amalfi Coast", "a cliffside terrace on the Amalfi coast with lemon trees, white parasols and the deep blue Tyrrhenian sea far below", ("sun", "water", "garden")),
    ("gstaad", "Gstaad", "a sun terrace of a chalet in Gstaad with snowy peaks, wooden loungers and fur throws", ("snow",)),
    ("acapulco", "Acapulco", "a cliff-top villa in Acapulco with a white infinity pool, bougainvillea and the Pacific bay glittering below", ("sun", "water", "garden")),
    ("capri", "Capri", "a bathing platform lido on Capri with striped umbrellas, limestone rocks and the Faraglioni in the distance", ("sun", "water", "boat")),
    ("monaco", "Monaco", "a yacht deck in the harbour of Monaco with teak decking, brass rails and the pastel apartment blocks of Monte Carlo behind", ("sun", "water", "boat", "town")),
    ("palm-beach", "Palm Beach", "a manicured lawn of a Palm Beach estate with a pink stucco mansion, clipped hedges and a croquet set", ("sun", "estate", "garden")),
    ("saint-tropez", "Saint-Tropez", "the quay of Saint-Tropez with wooden speedboats, pastel houses and cafe tables under plane trees", ("sun", "water", "boat", "town")),
    ("marbella", "Marbella", "a whitewashed Andalusian villa in Marbella with a blue-tiled pool, orange trees and arched colonnades", ("sun", "garden", "estate")),
    ("mustique", "Mustique", "a white sand beach on Mustique with a thatched pavilion, a wooden sailboat and impossibly clear turquoise water", ("sun", "water", "boat")),
    ("cortina", "Cortina d'Ampezzo", "a snowy hotel terrace in Cortina with the pink Dolomites, sunbeds and steaming cups of chocolate", ("snow",)),
    ("beverly-hills", "Beverly Hills", "a Beverly Hills garden with a rectangular pool, a white modernist house, sculpted topiary and palm trees", ("sun", "garden", "estate")),
    ("sardinia", "Costa Smeralda", "a rocky cove on the Costa Smeralda in Sardinia with granite boulders, a wooden Riva boat and emerald water", ("sun", "water", "boat")),
    ("riviera-garden", "The Riviera", "a Riviera cypress garden seen from a balcony, with a long sapphire pool, stone balustrades and the Mediterranean beyond", ("sun", "garden", "estate")),
    ("lake-geneva", "Lake Geneva", "a lakeside lawn on Lake Geneva with a white wooden pier, a vintage motorboat and the Alps across the water", ("sun", "water", "boat", "estate", "garden")),
    ("marrakech", "Marrakech", "a riad courtyard in Marrakech with a green-tiled pool, orange trees, ochre walls and a striped cabana", ("sun", "garden")),
    ("bermuda", "Bermuda", "a pink-sand beach in Bermuda with a pastel-yellow colonial house, white shutters and a wooden dinghy", ("sun", "water", "boat")),
    ("cannes", "Cannes", "a hotel balcony on the Croisette in Cannes with white balustrades, palm trees and the bay full of yachts", ("sun", "water", "town")),
    ("lake-tahoe", "Lake Tahoe", "a timber lodge dock on Lake Tahoe with a mahogany speedboat, pines and clear cobalt water", ("sun", "water", "boat")),
    ("portofino", "Portofino", "the pastel harbour of Portofino seen from above, with fishing boats, ochre and rose facades and a wooded headland", ("sun", "water", "boat", "town")),
    ("ibiza", "Ibiza", "a whitewashed finca terrace on Ibiza with a rough stone wall, a rectangular pool and pine-covered hills falling to the sea", ("sun", "garden")),
    ("hamptons", "The Hamptons", "a shingled Hamptons beach house with a striped awning, a clipped privet hedge and dune grass leading down to the Atlantic", ("sun", "water", "estate", "garden")),
    ("newport", "Newport", "the lawn of a Newport mansion above the cliff walk with a marble balustrade, old oaks and sailing yachts out on the sound", ("sun", "water", "estate", "garden")),
    ("st-moritz", "St. Moritz", "the frozen lake at St. Moritz with a grand hotel behind, horse-drawn sleighs and sharp alpine light", ("snow",)),
    ("santorini", "Santorini", "a whitewashed Santorini terrace with a blue-domed church, a small plunge pool and the caldera dropping to the Aegean", ("sun", "water", "garden")),
    ("positano", "Positano", "the tiered pastel houses of Positano seen from a balcony, with bougainvillea, a pebble beach and fishing boats below", ("sun", "water", "boat", "town")),
    ("rio", "Rio de Janeiro", "a modernist apartment terrace above Copacabana in Rio with a mosaic pool, palms and Sugarloaf beyond", ("sun", "water", "garden", "town")),
    ("havana", "Havana", "a Havana courtyard with faded turquoise colonnades, a vintage convertible in the drive and royal palms", ("sun", "town", "garden")),
    ("kenya", "Kenya", "a safari lodge veranda in Kenya with cane furniture, a brass telescope and golden plains and flat acacias beyond", ("sun", "estate")),
    ("jaipur", "Jaipur", "a pink sandstone palace courtyard in Jaipur with a marble step-pool, fretwork screens and potted palms", ("sun", "garden", "estate")),
    ("bali", "Bali", "a hillside villa on Bali with a black-tiled pool, carved stone lanterns and terraced rice fields in the haze", ("sun", "garden")),
    ("sydney", "Sydney", "a harbourside lawn in Sydney with a sandstone house, a diving board over deep blue water and ferries crossing behind", ("sun", "water", "boat", "garden")),
    ("malibu", "Malibu", "a redwood beach house deck in Malibu with a glass windbreak, surfboards and the Pacific breaking below", ("sun", "water")),
    ("aspen", "Aspen", "a log-and-glass lodge in Aspen with a stone chimney, snow-laden aspens and skis stacked by the door", ("snow",)),
    ("deauville", "Deauville", "the boardwalk at Deauville with candy-striped parasols, white bathing cabins and the grey-green Channel", ("sun", "water", "town")),
    ("estoril", "Estoril", "a casino-hotel terrace at Estoril with azulejo tiles, a crescent bay below and pine-covered hills", ("sun", "water", "town", "garden")),
    ("nantucket", "Nantucket", "a grey-shingled Nantucket house with white trim, blue hydrangeas, a picket fence and catboats out in the harbour", ("sun", "water", "boat", "garden")),
    ("highlands", "The Highlands", "the lawn of a Scottish country house with a gravel drive, heather hills, a dark green estate car and a loch beyond", ("estate", "garden")),
]

# (slug, kort namn, sallskap, needs) - needs = platsen maste ha MINST en av taggarna.
# Tom tuple = passar overallt.
PARTIES = [
    ("magenta-gown", "Magenta at Noon", "an elegant woman in a floor-length sheer magenta gown and a wide white sun hat standing by the pool with two dalmatians", ("garden",)),
    ("tennis-whites", "Tennis Whites", "a couple in crisp 1960s tennis whites with wooden racquets, laughing beside a courtside table with lemonade", ("sun", "estate")),
    ("loungers", "The Loungers", "a group of glamorous friends in colourful swimsuits and caftans on sun loungers under striped umbrellas, cocktails in hand", ("sun",)),
    ("cream-suit", "The Cream Suit", "a silver-haired man in a cream linen suit and sunglasses leaning on a vintage pale-blue convertible", ()),
    ("caftans", "Three Caftans", "three women in pastel silk caftans and oversized sunglasses holding champagne coupes", ("sun",)),
    ("speedboat", "The Speedboat", "a family in nautical stripes stepping off a polished wooden speedboat with a picnic hamper", ("boat",)),
    ("silk-robe", "The Silk Robe", "an elderly gentleman in a paisley silk dressing gown reading a newspaper with a white standard poodle at his feet", ()),
    ("emerald-turban", "The Hostess", "a hostess in an emerald turban and gold jewellery arranging a table of pastries and fruit", ()),
    ("polo", "After Polo", "two polo players in white breeches and coloured jerseys with a groom holding a chestnut horse", ("estate",)),
    ("ski-suits", "Apres-ski", "friends in 1970s coloured ski suits and fur hats toasting with hot chocolate on the terrace", ("snow",)),
    ("golf", "The Foursome", "four golfers in cashmere sweaters and plaid trousers with a caddie and vintage golf bags", ("estate",)),
    ("cocktail-hour", "Cocktail Hour", "a crowd in evening wear at a garden cocktail party with waiters in white jackets carrying silver trays", ("garden", "estate", "town")),
    ("water-skis", "Water Skis", "a young woman in a red swimsuit and white cap carrying water skis along the shore", ("water",)),
    ("gardener", "The Gardener", "a woman in a broad-brimmed hat and gloves cutting roses into a basket while a butler waits with a tray", ("garden", "estate")),
    ("chess", "Chess on the Terrace", "two men in linen shirts playing chess at a marble table under a lemon tree", ("sun", "garden")),
    ("backgammon", "Backgammon", "a couple in swimwear playing backgammon on a striped towel beside the pool", ("garden", "water")),
    ("horse-riding", "The Morning Ride", "a rider in a hacking jacket on a grey horse on a gravel drive lined with cypresses", ("estate",)),
    ("picnic", "The Picnic", "a picnic on a tartan rug with a wicker hamper, a bottle of rose in a silver bucket and a vintage convertible parked behind", ("garden", "estate", "water")),
    ("croquet", "The Croquet Match", "four players in white summer clothes with croquet mallets and a scoreboard, a spaniel watching from the shade", ("estate", "garden")),
    ("bridge", "The Bridge Four", "four women at a card table under a parasol with iced drinks and a silver cigarette box", ()),
    ("high-board", "The High Board", "a young woman in a white swimming cap poised on a diving board while friends watch from the water below", ("sun", "water")),
    ("newlyweds", "The Newlyweds", "a young couple in wedding clothes barefoot at the water's edge, shoes in hand and confetti still in her hair", ("water",)),
    ("vespa", "The Vespa", "a couple in sunglasses on a pale-blue Vespa loaded with a straw basket and a bottle of wine", ("town", "sun")),
    ("sunbathers", "The Sunbathers", "two women in matching yellow swimsuits reading magazines on a wooden raft out in the water", ("water",)),
    ("late-breakfast", "Breakfast at Eleven", "a couple in silk dressing gowns at a breakfast table with silver domes, orange juice and a stack of newspapers", ()),
    ("shooting-party", "The Shooting Party", "a party in tweed with two labradors and shooting sticks gathered beside a dark green estate wagon", ("estate",)),
    ("cousins", "The Cousins", "three children in matching sailor outfits with a nanny in white holding a toy boat", ("water", "garden", "estate")),
    ("the-painter", "The Painter", "a woman at an easel in a straw hat painting the view while a friend in a swimsuit watches over her shoulder", ("sun", "garden")),
    ("the-catch", "The Catch", "two men in rolled-up trousers on a jetty with rods and a wicker creel, a boy holding up the day's catch", ("water", "boat")),
    ("roadster", "The Silver Roadster", "a couple leaning against a silver open-top roadster with driving gloves, folded maps and a picnic basket on the bonnet", ()),
    ("the-arrival", "The Arrival", "a woman in a fur stole and evening gloves stepping from a car while a porter carries monogrammed leather luggage", ("town", "estate", "snow")),
    ("the-trio", "The Trio", "a small band in white dinner jackets playing beside the pool while guests dance barefoot on the terrace", ("sun", "garden")),
    ("afternoon-tea", "Afternoon Tea", "a family at a lace-laid tea table with a tiered cake stand while a butler pours", ("garden", "estate")),
    ("the-float", "The Float", "a woman in a red bikini on a striped inflatable float with a cocktail balanced on the rim", ("garden", "water")),
    ("the-archers", "The Archers", "two women in white with longbows and a straw target set up on the lawn", ("estate", "garden")),
]

LIGHT = [
    "harsh midday sun with short shadows",
    "warm late-afternoon light with long shadows",
    "clear morning light, sky a saturated cerulean",
    "low golden hour sun raking across the scene",
    "bright hazy noon with the horizon washed pale",
]

VANTAGE = [
    "photographed from a high vantage point looking down",
    "photographed at eye level with a slightly wide lens",
    "photographed from a low terrace step, the sky filling the upper third",
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
    "Three generations of this view and nobody has looked at it since 1961.",
    "The car is washed weekly and driven twice a year.",
    "Lunch was two hours ago and is still being cleared.",
    "Everyone here learned to swim in this pool. Nobody swims in it.",
    "The invitation said informal. This is informal.",
]


def compatible(place: tuple, party: tuple) -> bool:
    """Sallskapet maste passa platsen: apres-ski bara dar det finns sno, polo bara pa gods."""
    needs = party[3]
    return not needs or bool(set(needs) & set(place[3]))


def _load_used() -> set[str]:
    if STATE.exists():
        return set(json.loads(STATE.read_text(encoding="utf-8")))
    return set()


def _save_used(used: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(used), indent=1), encoding="utf-8")


def _build(place: tuple, party: tuple, day: date, index: int, rng: random.Random) -> dict:
    slug = f"{day.strftime('%Y%m%d')}-{index}-{place[0]}-{party[0]}"
    name = f"{party[1]}, {place[1]}"
    prompt = f"{party[2]}, {place[2]}, {rng.choice(LIGHT)}, {rng.choice(VANTAGE)}. {STYLE}"
    place_tag = place[1].lower().replace("'", "")[:20]
    tags = ([f"{place_tag} print", f"{place_tag} poster", "vintage riviera"] + BASE_TAGS)[:13]
    tags = [t[:20] for t in tags]
    return {
        "slug": slug, "name": name, "place": place[1], "party": party[1],
        "prompt": prompt, "negative": NEGATIVE, "seed": rng.randrange(1, 2**31),
        "title": (name + TITLE_TAIL)[:140], "tags": tags,
        "description": f"{name}\n\n{rng.choice(CAPTIONS)}\n\nFrom the DrJonsson series: rich in every frame.",
        "key": f"{place[0]}+{party[0]}",
    }


def pick(day: date, count: int = DAILY_COUNT, commit: bool = True) -> list[dict]:
    """Valjer `count` oanvanda plats+sallskap-par for dagen.

    Dagens val sparas i state/day-<datum>.json sa en omkorning samma dag ger SAMMA motiv
    (annars skulle used.json ha stangt dem och en kraschad korning fatt nya). Bes man om
    FLER an vad dagsfilen redan har (t.ex. nar volymen gick fran 5 till 35) fylls listan
    pa i slutet - de redan genererade behaller sitt slug och sin plats i ordningen."""
    day_file = STATE.parent / f"day-{day.isoformat()}.json"
    saved: list[dict] = []
    if day_file.exists():
        saved = json.loads(day_file.read_text(encoding="utf-8"))
        if len(saved) >= count:
            return saved[:count]
    rng = random.Random(day.isoformat())
    used = _load_used() | {m["key"] for m in saved}
    pairs = [(p, s) for p in PLACES for s in PARTIES if compatible(p, s)]
    rng.shuffle(pairs)
    need = count - len(saved)
    free = [x for x in pairs if f"{x[0][0]}+{x[1][0]}" not in used]
    if len(free) < need:                       # allt anvant: borja om, men skydda dagens egna
        used = {m["key"] for m in saved}
        free = [x for x in pairs if f"{x[0][0]}+{x[1][0]}" not in used]
    out = list(saved)
    for i, (place, party) in enumerate(free[:need], len(saved) + 1):
        m = _build(place, party, day, i, rng)
        used.add(m["key"])
        out.append(m)
    if commit:
        _save_used(used)
        day_file.parent.mkdir(parents=True, exist_ok=True)
        day_file.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def bank_size() -> int:
    return sum(1 for p in PLACES for s in PARTIES if compatible(p, s))


if __name__ == "__main__":
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    n = int(sys.argv[2]) if len(sys.argv) > 2 else DAILY_COUNT
    print(f"{len(PLACES)} platser x {len(PARTIES)} sallskap = {bank_size()} giltiga par "
          f"({bank_size() // DAILY_COUNT} dagar a {DAILY_COUNT})")
    for m in pick(d, n, commit=False):
        print(m["slug"], "|", m["name"])
        print("   ", m["prompt"][:160], "...")

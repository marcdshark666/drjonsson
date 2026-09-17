#!/usr/bin/env python3
"""
DrJonsson - dagens 35 motiv: generera lokalt (gratis, RTX 4090), lagg i Printify,
uppdatera dashboarden pa GitHub Pages och saga till i Telegram.

Steg (alla kan stangas av med flaggor, sa delarna gar att kora var for sig):
  1. valj motiv         motifs.pick(datum, antal)
  2. generera bilder    Z-Image-Turbo via diffusers -> outputs/<datum>/<slug>.jpg (3600x5400)
  3. listningar         lagg till i listings/listings.json + kopiera till images/
  4. Printify           utkast + publicering i Pop-Up-butiken (gratis) om PRINTIFY_POPUP_SHOP_ID finns
                        Etsy: bara efter Marcs ja i Telegram (0,20 USD/listning) om PRINTIFY_ETSY_SHOP_ID finns
  5. dashboard          docs/data/status.json + docs/img/<slug>.jpg (800 px) -> git push -> GitHub Pages
  6. Telegram           kontaktark med dagens motiv + lank till dashboarden

  python generate_daily.py                  hela kedjan for idag
  python generate_daily.py --count 35 --date 2026-09-16
  python generate_daily.py --printify-minutes 45   krymp Printify-delen (resten tas nasta dag)
  python generate_daily.py --dry-run        valj motiv, generera INTE, rora inte Printify/git/Telegram
  python generate_daily.py --no-printify --no-push --no-telegram
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import motifs  # noqa: E402

OUTPUTS = ROOT / "outputs"
IMAGES = ROOT / "images"
DOCS = ROOT / "docs"
DOCS_IMG = DOCS / "img"
STATUS = DOCS / "data" / "status.json"
LISTINGS = ROOT / "listings" / "listings.json"
STORE_MAIL = ROOT / "state" / "store-mail.json"   # rutinen DrJonsson-ButikMail skriver hit
LOG = ROOT / "outputs" / "daily.log"
HOOKS = Path.home() / ".claude" / "hooks"
PY = sys.executable

MODEL_ID = os.environ.get("AARON_MODEL", "Tongyi-MAI/Z-Image-Turbo")
GEN_W, GEN_H = 1536, 2304          # 2:3, Z-Image klarar upp till 2048 pa langsta sidan
OUT_W, OUT_H = 3600, 5400          # 150 dpi pa 24x36", 300 dpi pa 12x18"
THUMB_W = 800
SHEET_COLS = 7                     # kontaktarket ar ett rutnat: 35 motiv pa en rad blev
                                   # 14 500 px brett och refuserades av Telegram
PRINTIFY_MAX_NEW = 400             # tak per korning; 35 motiv x 9 produkter = 315
PRINTIFY_MINUTES = 75              # ~9 s mellan publiceringar -> 315 st tar knappt en timme
DASHBOARD_URL = "https://marcdshark666.github.io/drjonsson/"


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


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


# ---------- status.json (dashboardens sanning) ----------

def product_count() -> int:
    """Antal produkttyper per motiv enligt products.json (9 i dag)."""
    try:
        return len(json.loads((HERE / "products.json").read_text(encoding="utf-8")).get("default", ["poster"]))
    except Exception:
        return 1


def load_status() -> dict:
    if STATUS.exists():
        return json.loads(STATUS.read_text(encoding="utf-8"))
    return {"items": [], "runs": [], "todo": [], "stats": {}}


def save_status(s: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    s["updated"] = datetime.now().isoformat(timespec="seconds")
    items = s["items"]
    s["stats"] = {
        "generated": len(items),
        "printify_drafts": sum(1 for i in items if i.get("printify", {}).get("popup_product") or i.get("printify", {}).get("etsy_product")),
        "popup_live": sum(1 for i in items if i.get("printify", {}).get("popup_published")),
        "etsy_live": sum(1 for i in items if i.get("printify", {}).get("etsy_published")),
        "days": len({i["date"] for i in items}),
        "streak": _streak(sorted({i["date"] for i in items})),
        "errors_last_run": len(s["runs"][-1]["errors"]) if s["runs"] else 0,
        "product_types": product_count(),
    }
    STATUS.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")


def _streak(days: list[str]) -> int:
    if not days:
        return 0
    n, prev = 0, None
    for d in reversed(days):
        cur = date.fromisoformat(d)
        if prev is None or (prev - cur).days == 1:
            n += 1
            prev = cur
        else:
            break
    return n


def load_store_mail() -> dict:
    """Vad Gmail-kollen (rutinen DrJonsson-ButikMail) senast sag om butiken.

    Pipelinen kan inte sjalv lasa Gmail - den rutinen kors av en Claude-session
    med Gmail-atkomst och lagger svaret i state/store-mail.json. Saknas filen
    eller ar den trasig later vi bara bli: dashboarden visar da ingen rad, och
    inget annat i korningen paverkas.
    """
    try:
        d = json.loads(STORE_MAIL.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(d, dict):
        return {}
    return d


# Dashboarden ligger pa GitHub Pages i ett PUBLIKT repo. store-mail.json gor det
# inte - den star i .gitignore bredvid etsy_verifiering.json - och bara de har
# falten foljer med in i status.json. Avsandare, amnesrader, inloggningsplatser
# och historik stannar pa datorn.
STORE_MAIL_PUBLIC = ("checked", "status", "shop_open", "headline", "action_url", "who")


def public_store_mail(mail: dict) -> dict:
    return {k: mail[k] for k in STORE_MAIL_PUBLIC if k in mail}


def refresh_todo(s: dict, e: dict) -> None:
    """Marcs manuella steg. Det som gar att kanna av automatiskt bockas av har."""
    model_ok = (HERE / ".model_ok").exists()
    have_token = bool(e.get("PRINTIFY_TOKEN") and not e["PRINTIFY_TOKEN"].startswith("eyJ..."))
    mail = load_store_mail()
    auto = {
        "venv": (ROOT / ".venv" / "Scripts" / "python.exe").exists(),
        "model": model_ok,
        "printify-token": have_token,
        "popup-shop": bool(e.get("PRINTIFY_POPUP_SHOP_ID")),
        "etsy-shop": bool(e.get("PRINTIFY_ETSY_SHOP_ID")),
    }
    # Butiken bockas av forst nar Gmail-kollen sett bekraftelsen - ett oppnat
    # PRINTIFY_ETSY_SHOP_ID rader inte, for Etsy kan halla betalningarna kvar.
    if mail.get("shop_open") is True:
        auto["etsy-account"] = True
    manual_default = [
        ("venv", "Python-miljö med CUDA-torch och diffusers", "Claude installerar (klart när bocken syns)", True),
        ("model", "Bildmodellen Z-Image-Turbo nedladdad (~20 GB)", "Claude laddar ner första gången", True),
        ("printify-account", "Printify-konto (gratis)", "printify.com – du", False),
        ("popup-store", "Pop-Up Store skapad (aaron.printify.me) + Stripe-verifiering", "Printify › My stores › Add store – du", False),
        ("printify-token", "API-token i pipeline/.env", "Printify › My profile › Connections – du", True),
        ("popup-shop", "PRINTIFY_POPUP_SHOP_ID i .env", "python printify_bulk.py --shops – du/Claude", True),
        ("etsy-account", "Etsy-butik öppnad (15–29 USD, ID-verifiering)", "etsy.com/sell – du (Gmail-kollen bockar av)", False),
        ("etsy-connect", "Printify kopplad till Etsy", "Printify › My stores › Connect › Etsy – du", False),
        ("etsy-shop", "PRINTIFY_ETSY_SHOP_ID i .env", "python printify_bulk.py --shops – du/Claude", True),
        ("test-order", "Testköp av ett 12×18 (~15 USD)", "du", False),
        ("tax", "Skatteverket: näringsverksamhet, F-skatt, moms", "du", False),
    ]
    existing = {t["id"]: t for t in s.get("todo", [])}
    todo = []
    for tid, text, who, is_auto in manual_default:
        # Ett varde i `auto` vager alltid tyngst - aven for de manuella stegen, sa
        # att Gmail-kollens bekraftelse kan bocka av "etsy-account" utan Marc.
        prev = existing.get(tid, {}).get("done", False)
        done = auto[tid] if tid in auto else prev
        todo.append({"id": tid, "text": text, "who": who, "auto": is_auto, "done": bool(done)})
    s["todo"] = todo
    if mail:
        s["store_mail"] = public_store_mail(mail)
    elif "store_mail" in s:
        del s["store_mail"]


# ---------- bildgenerering ----------

_pipe = None


def get_pipe():
    global _pipe
    if _pipe is not None:
        return _pipe
    import torch
    import diffusers
    log(f"laddar {MODEL_ID} (diffusers {diffusers.__version__}, torch {torch.__version__}, cuda {torch.cuda.is_available()})")
    if not torch.cuda.is_available():
        raise RuntimeError("Ingen CUDA - torch ar CPU-bygget eller drivrutinen saknas")
    cls = getattr(diffusers, "ZImagePipeline", None)
    if cls is None:
        raise RuntimeError("diffusers saknar ZImagePipeline - uppgradera: pip install -U diffusers")
    pipe = cls.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload()
    _pipe = pipe
    (HERE / ".model_ok").write_text(MODEL_ID, encoding="utf-8")
    return pipe


def generate_image(m: dict, out_path: Path) -> None:
    import torch
    from PIL import Image, ImageFilter
    pipe = get_pipe()
    gen = torch.Generator("cuda").manual_seed(m["seed"])
    t0 = time.time()
    img = pipe(prompt=m["prompt"], negative_prompt=m["negative"], height=GEN_H, width=GEN_W,
               num_inference_steps=8, guidance_scale=0.0, generator=gen).images[0]
    log(f"  genererad pa {time.time()-t0:.0f} s: {img.size}")
    big = img.resize((OUT_W, OUT_H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    big.save(out_path, "JPEG", quality=94, subsampling=0, dpi=(150, 150))


def make_thumb(src: Path, dst: Path, width: int = THUMB_W) -> None:
    from PIL import Image
    im = Image.open(src)
    im.thumbnail((width, width * 2))
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=85)


def contact_sheet(thumbs: list[Path], dst: Path, day: str) -> Path:
    """Rutnat, max SHEET_COLS per rad - Telegram tar inte emot foton bredare an ~10 000 px
    eller med sidforhallande over 20:1, vilket en enda rad med 35 motiv blir."""
    from PIL import Image, ImageDraw
    cell_w, cell_h, pad, head = 300, 450, 12, 44
    cols = min(SHEET_COLS, len(thumbs)) or 1
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w + (cols + 1) * pad,
                              rows * cell_h + (rows + 1) * pad + head), "#F4EFE6")
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(thumbs):
        im = Image.open(t)
        im.thumbnail((cell_w, cell_h))
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad) + (cell_w - im.width) // 2
        y = head + pad + r * (cell_h + pad) + (cell_h - im.height) // 2
        sheet.paste(im, (x, y))
    d.text((pad, 14), f"DrJonsson  {day}  -  {len(thumbs)} motiv  -  rich in every frame", fill="#111111")
    sheet.save(dst, "JPEG", quality=88)
    return dst


# ---------- Printify ----------

def printify_run(slugs: list[str], shop: str, publish: bool, minutes: float = 0, max_new: int = 0) -> tuple[bool, str]:
    cmd = [PY, str(HERE / "printify_bulk.py"), "--only", ",".join(slugs), "--shop", shop, "--yes"]
    if publish:
        cmd.append("--publish")
    if minutes:
        cmd += ["--max-minutes", str(minutes)]
    if max_new:
        cmd += ["--max-new", str(max_new)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    out = (r.stdout + r.stderr).strip()
    log(f"  printify shop {shop} publish={publish} exit={r.returncode}")
    return r.returncode == 0, out


def printify_queue(status: dict, prefix: str, today: list[str], expected: int) -> list[str]:
    """Dagens motiv forst, sedan aldre som inte blev fardiga (avbruten korning, 429,
    ny produkttyp i products.json). Utan detta skulle allt som foll bort ligga kvar."""
    q = list(today)
    for it in status["items"]:
        if it["slug"] in q:
            continue
        try:
            pub = int(str(it.get("printify", {}).get(f"{prefix}_count", "0/0")).split("/")[0])
        except ValueError:
            pub = 0
        if pub < expected:
            q.append(it["slug"])
    return q


def printify_ids(shop: str) -> dict:
    """slug -> {"products": {typ: id}, "published": n, "total": n, "errors": [..]} for en butik."""
    p = HERE / "state.json"
    if not p.exists():
        return {}
    st = json.loads(p.read_text(encoding="utf-8"))
    out: dict = {}
    for k, v in st.items():
        parts = k.split(":")
        if len(parts) != 3 or parts[0] != shop:
            continue
        _, slug, key = parts
        o = out.setdefault(slug, {"products": {}, "published": 0, "total": 0, "errors": []})
        o["total"] += 1
        if v.get("product_id"):
            o["products"][key] = v["product_id"]
        if v.get("published"):
            o["published"] += 1
        if v.get("error"):
            o["errors"].append(f"{key}: {v['error'][:120]}")
    return out


# ---------- Marcs beslut (dashboardens ✅/❌) ----------

APPROVALS = DOCS / "data" / "approvals.json"


def git_pull() -> None:
    """Dashboarden skriver approvals.json direkt i GitHub; hamta det innan vi laser."""
    r = subprocess.run(["git", "pull", "-q", "--rebase", "--autostash", "origin", "main"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        log("  git pull misslyckades: " + (r.stderr or r.stdout).strip()[-200:])
        subprocess.run(["git", "rebase", "--abort"], cwd=str(ROOT), capture_output=True)


def approvals() -> dict:
    """slug -> {"beslut": "ja"|"nej", "nar": iso, "av": login}"""
    if not APPROVALS.exists():
        return {}
    try:
        return json.loads(APPROVALS.read_text(encoding="utf-8")).get("items", {}) or {}
    except ValueError:
        return {}


def approved_slugs(status: dict) -> list[str]:
    """Motiv Marc bockat ✅ pa dashboarden och som inte redan ar helt publicerade pa Etsy."""
    ok = {k for k, v in approvals().items() if v.get("beslut") == "ja"}
    n_types = product_count()
    out = []
    for it in status["items"]:
        if it["slug"] not in ok:
            continue
        try:
            pub = int(str(it.get("printify", {}).get("etsy_count", "0/0")).split("/")[0])
        except ValueError:
            pub = 0
        if pub < n_types:
            out.append(it["slug"])
    return out


def etsy_publish_approved(status: dict, run: dict, e: dict, minutes: float, max_new: int) -> int:
    """Publicerar BARA Marcs ✅-motiv pa Etsy. Ingen Telegram-fraga: bocken pa sidan ar hans ja
    (knappen visar kostnaden, 0,20 USD per listning). Returnerar antal publicerade produkter."""
    etsy = e.get("PRINTIFY_ETSY_SHOP_ID")
    if not etsy:
        log("  etsy: PRINTIFY_ETSY_SHOP_ID saknas - godkanda motiv vantar")
        return 0
    slugs = approved_slugs(status)
    if not slugs:
        log("  etsy: inga nya godkanda motiv")
        return 0
    log(f"  etsy: {len(slugs)} godkanda motiv publiceras")
    ok, out = printify_run(slugs, etsy, publish=True, minutes=minutes, max_new=max_new)
    if not ok:
        run["errors"].append("printify etsy publish: " + out[-300:])
    ids = printify_ids(etsy)
    n = 0
    for it in status["items"]:
        if it["slug"] in ids:
            o = ids[it["slug"]]
            it["printify"]["etsy_products"] = o["products"]
            it["printify"]["etsy_product"] = bool(o["products"])
            it["printify"]["etsy_published"] = o["published"] > 0
            it["printify"]["etsy_count"] = f"{o['published']}/{o['total']}"
            n += o["published"]
    return n


# ---------- Telegram ----------

def telegram_ask_etsy(sheet: Path, n: int) -> bool:
    script = HOOKS / "telegram-godkann.js"
    if not script.exists():
        log("  telegram-godkann.js saknas - Etsy publiceras inte")
        return False
    r = subprocess.run(["node", str(script), "--projekt", "drjonsson-prints",
                        "--vad", f"Publicera dagens {n} produkter pa Etsy ({0.2*n:.2f} USD i listningsavgift)",
                        "--bild", str(sheet), "--storlek", "stor", "--timeout", "900", "--json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    log(f"  telegram-godkann exit={r.returncode} {r.stdout.strip()[:200]}")
    return r.returncode == 0


def telegram_send(sheet: Path | None, text: str) -> None:
    script = HERE / "telegram_send.js"
    args = ["node", str(script), "--text", text]
    if sheet:
        args += ["--bild", str(sheet)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log(f"  telegram exit={r.returncode} {(r.stdout or r.stderr).strip()[:160]}")


# ---------- git ----------

def git_push() -> tuple[bool, str]:
    def run(*a):
        return subprocess.run(["git", *a], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    run("add", "docs", "listings", "state")
    c = run("commit", "-m", f"Dagens motiv {date.today().isoformat()}")
    if c.returncode != 0 and "nothing to commit" in (c.stdout + c.stderr):
        return True, "inget att committa"
    p = run("push", "origin", "HEAD:main")
    ok = p.returncode == 0
    log(f"  git push exit={p.returncode} {(p.stderr or p.stdout).strip()[-160:]}")
    return ok, (p.stderr or p.stdout).strip()[-300:]


# ---------- huvudflodet ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=motifs.DAILY_COUNT)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-printify", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--no-etsy-ask", action="store_true", help="(kvar for kompatibilitet; Etsy fragas inte langre i Telegram)")
    ap.add_argument("--etsy-only", action="store_true", help="generera inget: publicera bara Marcs ✅-motiv pa Etsy och uppdatera dashboarden")
    ap.add_argument("--printify-minutes", type=float, default=PRINTIFY_MINUTES,
                    help="tidsbudget for Printify-delen; resten tas i nasta korning")
    ap.add_argument("--printify-max-new", type=int, default=PRINTIFY_MAX_NEW,
                    help="tak for antal nya produkter per korning")
    args = ap.parse_args()

    day = date.fromisoformat(args.date)
    e = env()
    status = load_status()
    run = {"date": day.isoformat(), "started": datetime.now().isoformat(timespec="seconds"),
           "count": args.count, "generated": 0, "popup": 0, "etsy": 0, "errors": [], "dry_run": args.dry_run}
    log(f"=== DrJonsson dagskorning {day} (count={args.count}, dry_run={args.dry_run}) ===")

    git_pull()   # dashboardens beslut ligger i GitHub

    if args.etsy_only:
        run["count"] = 0
        n = etsy_publish_approved(status, run, e, args.printify_minutes, args.printify_max_new)
        run["finished"] = datetime.now().isoformat(timespec="seconds")
        run["note"] = "etsy-only"
        if n or run["errors"]:
            status["runs"].append(run)
            status["runs"] = status["runs"][-60:]
        refresh_todo(status, e)
        save_status(status)
        if n or run["errors"]:
            if not args.no_push:
                git_push()
            if not args.no_telegram:
                telegram_send(None, f"🛒 DrJonsson: {n} produkter publicerade pa Etsy efter dina ✅"
                              + (f", {len(run['errors'])} fel" if run["errors"] else "") + f"\n{DASHBOARD_URL}")
        log(f"=== etsy-only klart: {n} publicerade, {len(run['errors'])} fel ===")
        return 0

    chosen = motifs.pick(day, args.count, commit=not args.dry_run)
    for m in chosen:
        log(f"  motiv: {m['slug']}  {m['name']}")
    if args.dry_run:
        refresh_todo(status, e)
        save_status(status)
        print(json.dumps([{k: m[k] for k in ("slug", "name", "prompt")} for m in chosen], indent=1, ensure_ascii=False))
        return 0

    # 2. generera
    day_dir = OUTPUTS / day.isoformat()
    thumbs: list[Path] = []
    done: list[dict] = []
    listings = json.loads(LISTINGS.read_text(encoding="utf-8")) if LISTINGS.exists() else {}
    for m in chosen:
        full = day_dir / f"{m['slug']}.jpg"
        try:
            if not full.exists():
                log(f"genererar {m['slug']}")
                generate_image(m, full)
            thumb = DOCS_IMG / f"{m['slug']}.jpg"
            make_thumb(full, thumb)
            IMAGES.mkdir(exist_ok=True)
            (IMAGES / full.name).write_bytes(full.read_bytes())
            listings[m["slug"]] = {"title": m["title"], "description": m["description"], "tags": m["tags"]}
            thumbs.append(thumb)
            done.append(m)
            run["generated"] += 1
            if not any(i["slug"] == m["slug"] for i in status["items"]):
                status["items"].append({
                    "slug": m["slug"], "date": day.isoformat(), "name": m["name"], "place": m["place"],
                    "party": m["party"], "title": m["title"], "tags": m["tags"], "thumb": f"img/{m['slug']}.jpg",
                    "prompt": m["prompt"], "seed": m["seed"], "printify": {},
                })
        except Exception as ex:  # en trasig bild ska inte stoppa de andra
            msg = f"{m['slug']}: {type(ex).__name__}: {ex}"
            log("FEL " + msg)
            log(traceback.format_exc()[-800:])
            run["errors"].append(msg)
    LISTINGS.write_text(json.dumps(listings, indent=2, ensure_ascii=False), encoding="utf-8")
    refresh_todo(status, e)
    save_status(status)

    sheet = None
    if thumbs:
        sheet = contact_sheet(thumbs, day_dir / "kontaktark.jpg", day.isoformat())
        make_thumb(sheet, DOCS_IMG / f"{day.isoformat()}-ark.jpg", 1600)

    # 4. Printify
    slugs = [m["slug"] for m in done]
    n_types = product_count()
    popup, etsy = e.get("PRINTIFY_POPUP_SHOP_ID"), e.get("PRINTIFY_ETSY_SHOP_ID")
    have_token = bool(e.get("PRINTIFY_TOKEN")) and not e["PRINTIFY_TOKEN"].startswith("eyJ...")
    if slugs and not args.no_printify and have_token:
        if popup:
            q = printify_queue(status, "popup", slugs, n_types)
            if len(q) > len(slugs):
                log(f"  popup-ko: {len(slugs)} nya + {len(q) - len(slugs)} fran tidigare dagar")
            ok, out = printify_run(q, popup, publish=True,          # Pop-Up: gratis, publiceras direkt
                                   minutes=args.printify_minutes, max_new=args.printify_max_new)
            if not ok:
                run["errors"].append("printify popup: " + out[-300:])
            ids = printify_ids(popup)
            for it in status["items"]:
                if it["slug"] in ids:
                    o = ids[it["slug"]]
                    it["printify"]["popup_products"] = o["products"]
                    it["printify"]["popup_product"] = bool(o["products"])
                    it["printify"]["popup_published"] = o["published"] > 0
                    it["printify"]["popup_count"] = f"{o['published']}/{o['total']}"
                    run["popup"] += o["published"]
        # Etsy: ENBART motiv Marc bockat ✅ pa dashboarden (docs/data/approvals.json).
        run["etsy"] = etsy_publish_approved(status, run, e, args.printify_minutes, args.printify_max_new)
    elif slugs and not have_token:
        run["note"] = "Printify hoppades over: ingen PRINTIFY_TOKEN i pipeline/.env"
        log("  " + run["note"])

    run["finished"] = datetime.now().isoformat(timespec="seconds")
    status["runs"].append(run)
    status["runs"] = status["runs"][-60:]
    save_status(status)

    # 5. dashboard
    if not args.no_push:
        ok, out = git_push()
        if not ok:
            run["errors"].append("git push: " + out)
            save_status(status)

    # 6. Telegram
    if not args.no_telegram:
        n_err = len(run["errors"])
        text = (f"🖼 DrJonsson {day}: {run['generated']}/{args.count} motiv genererade"
                + (f", {run['popup']} live i Pop-Up" if popup else "")
                + (f", {run['etsy']} live pa Etsy" if etsy else "")
                + (f", {n_err} fel" if n_err else "")
                + (f"\n{run['note']}" if run.get("note") else "")
                + f"\nDashboard: {DASHBOARD_URL}")
        telegram_send(sheet, text)

    log(f"=== klart: {run['generated']} genererade, {len(run['errors'])} fel ===")
    return 1 if run["errors"] and run["generated"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())

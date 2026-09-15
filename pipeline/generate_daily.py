#!/usr/bin/env python3
"""
DrJonsson - dagens fem motiv: generera lokalt (gratis, RTX 4090), lagg i Printify,
uppdatera dashboarden pa GitHub Pages och saga till i Telegram.

Steg (alla kan stangas av med flaggor, sa delarna gar att kora var for sig):
  1. valj motiv         motifs.pick(datum, antal)
  2. generera bilder    Z-Image-Turbo via diffusers -> outputs/<datum>/<slug>.jpg (3600x5400)
  3. listningar         lagg till i listings/listings.json + kopiera till images/
  4. Printify           utkast + publicering i Pop-Up-butiken (gratis) om PRINTIFY_POPUP_SHOP_ID finns
                        Etsy: bara efter Marcs ja i Telegram (0,20 USD/listning) om PRINTIFY_ETSY_SHOP_ID finns
  5. dashboard          docs/data/status.json + docs/img/<slug>.jpg (800 px) -> git push -> GitHub Pages
  6. Telegram           kontaktark med dagens fem + lank till dashboarden

  python generate_daily.py                  hela kedjan for idag
  python generate_daily.py --count 5 --date 2026-09-16
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
LOG = ROOT / "outputs" / "daily.log"
HOOKS = Path.home() / ".claude" / "hooks"
PY = sys.executable

MODEL_ID = os.environ.get("AARON_MODEL", "Tongyi-MAI/Z-Image-Turbo")
GEN_W, GEN_H = 1536, 2304          # 2:3, Z-Image klarar upp till 2048 pa langsta sidan
OUT_W, OUT_H = 3600, 5400          # 150 dpi pa 24x36", 300 dpi pa 12x18"
THUMB_W = 800
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


def refresh_todo(s: dict, e: dict) -> None:
    """Marcs manuella steg. Det som gar att kanna av automatiskt bockas av har."""
    model_ok = (HERE / ".model_ok").exists()
    have_token = bool(e.get("PRINTIFY_TOKEN") and not e["PRINTIFY_TOKEN"].startswith("eyJ..."))
    auto = {
        "venv": (ROOT / ".venv" / "Scripts" / "python.exe").exists(),
        "model": model_ok,
        "printify-token": have_token,
        "popup-shop": bool(e.get("PRINTIFY_POPUP_SHOP_ID")),
        "etsy-shop": bool(e.get("PRINTIFY_ETSY_SHOP_ID")),
    }
    manual_default = [
        ("venv", "Python-miljö med CUDA-torch och diffusers", "Claude installerar (klart när bocken syns)", True),
        ("model", "Bildmodellen Z-Image-Turbo nedladdad (~20 GB)", "Claude laddar ner första gången", True),
        ("printify-account", "Printify-konto (gratis)", "printify.com – du", False),
        ("popup-store", "Pop-Up Store skapad (aaron.printify.me) + Stripe-verifiering", "Printify › My stores › Add store – du", False),
        ("printify-token", "API-token i pipeline/.env", "Printify › My profile › Connections – du", True),
        ("popup-shop", "PRINTIFY_POPUP_SHOP_ID i .env", "python printify_bulk.py --shops – du/Claude", True),
        ("etsy-account", "Etsy-butik öppnad (15–29 USD, ID-verifiering)", "etsy.com/sell – du", False),
        ("etsy-connect", "Printify kopplad till Etsy", "Printify › My stores › Connect › Etsy – du", False),
        ("etsy-shop", "PRINTIFY_ETSY_SHOP_ID i .env", "python printify_bulk.py --shops – du/Claude", True),
        ("test-order", "Testköp av ett 12×18 (~15 USD)", "du", False),
        ("tax", "Skatteverket: näringsverksamhet, F-skatt, moms", "du", False),
    ]
    existing = {t["id"]: t for t in s.get("todo", [])}
    todo = []
    for tid, text, who, is_auto in manual_default:
        done = auto.get(tid, existing.get(tid, {}).get("done", False)) if is_auto else existing.get(tid, {}).get("done", False)
        todo.append({"id": tid, "text": text, "who": who, "auto": is_auto, "done": bool(done)})
    s["todo"] = todo


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
    from PIL import Image, ImageDraw
    cell_w, cell_h, pad = 400, 600, 16
    cols = len(thumbs)
    sheet = Image.new("RGB", (cols * cell_w + (cols + 1) * pad, cell_h + 2 * pad + 40), "#F4EFE6")
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(thumbs):
        im = Image.open(t)
        im.thumbnail((cell_w, cell_h))
        sheet.paste(im, (pad + i * (cell_w + pad), pad + 40))
    d.text((pad, 12), f"DrJonsson  {day}  -  rich in every frame", fill="#111111")
    sheet.save(dst, "JPEG", quality=88)
    return dst


# ---------- Printify ----------

def printify_run(slugs: list[str], shop: str, publish: bool) -> tuple[bool, str]:
    cmd = [PY, str(HERE / "printify_bulk.py"), "--only", ",".join(slugs), "--shop", shop, "--yes"]
    if publish:
        cmd.append("--publish")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    out = (r.stdout + r.stderr).strip()
    log(f"  printify shop {shop} publish={publish} exit={r.returncode}")
    return r.returncode == 0, out


def printify_ids(shop: str) -> dict:
    p = HERE / "state.json"
    if not p.exists():
        return {}
    st = json.loads(p.read_text(encoding="utf-8"))
    return {k.split(":", 1)[1]: v for k, v in st.items() if k.startswith(f"{shop}:")}


# ---------- Telegram ----------

def telegram_ask_etsy(sheet: Path, n: int) -> bool:
    script = HOOKS / "telegram-godkann.js"
    if not script.exists():
        log("  telegram-godkann.js saknas - Etsy publiceras inte")
        return False
    r = subprocess.run(["node", str(script), "--projekt", "drjonsson-prints",
                        "--vad", f"Publicera dagens {n} listningar pa Etsy ({0.2*n:.2f} USD i listningsavgift)",
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
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-printify", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--no-etsy-ask", action="store_true", help="fraga inte om Etsy i Telegram")
    args = ap.parse_args()

    day = date.fromisoformat(args.date)
    e = env()
    status = load_status()
    run = {"date": day.isoformat(), "started": datetime.now().isoformat(timespec="seconds"),
           "count": args.count, "generated": 0, "popup": 0, "etsy": 0, "errors": [], "dry_run": args.dry_run}
    log(f"=== DrJonsson dagskorning {day} (count={args.count}, dry_run={args.dry_run}) ===")

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
    popup, etsy = e.get("PRINTIFY_POPUP_SHOP_ID"), e.get("PRINTIFY_ETSY_SHOP_ID")
    have_token = bool(e.get("PRINTIFY_TOKEN")) and not e["PRINTIFY_TOKEN"].startswith("eyJ...")
    if slugs and not args.no_printify and have_token:
        if popup:
            ok, out = printify_run(slugs, popup, publish=True)      # Pop-Up: gratis, publiceras direkt
            if not ok:
                run["errors"].append("printify popup: " + out[-300:])
            ids = printify_ids(popup)
            for it in status["items"]:
                if it["slug"] in ids:
                    it["printify"]["popup_product"] = ids[it["slug"]].get("product_id")
                    it["printify"]["popup_published"] = bool(ids[it["slug"]].get("published"))
                    run["popup"] += 1 if it["printify"]["popup_published"] else 0
        if etsy:
            ok, out = printify_run(slugs, etsy, publish=False)      # utkast ar gratis
            if not ok:
                run["errors"].append("printify etsy drafts: " + out[-300:])
            approved = False
            if sheet and not args.no_etsy_ask and not args.no_telegram:
                approved = telegram_ask_etsy(sheet, len(slugs))    # 0,20 USD/listning -> Marcs ja kravs
            if approved:
                ok, out = printify_run(slugs, etsy, publish=True)
                if not ok:
                    run["errors"].append("printify etsy publish: " + out[-300:])
            ids = printify_ids(etsy)
            for it in status["items"]:
                if it["slug"] in ids:
                    it["printify"]["etsy_product"] = ids[it["slug"]].get("product_id")
                    it["printify"]["etsy_published"] = bool(ids[it["slug"]].get("published"))
                    run["etsy"] += 1 if it["printify"]["etsy_published"] else 0
            run["etsy_approved"] = approved
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

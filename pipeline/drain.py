#!/usr/bin/env python3
"""
DrJonsson - draneringen: utfor Marcs beslut fran dashboarden (docs/data/approvals.json).
Kors varje timme av uppgiften DrJonsson-Etsy. Genererar inga nya motiv.

  1. git pull                  dashboarden skriver approvals.json direkt i GitHub
  2. radera                    Marc tryckte 🗑: produkterna tas bort i Printify (Pop-Up + Etsy)
                               och motivet flyttas till "raderade" pa dashboarden
  3. redigera                  Marc skrev en andring: bilden genereras om med onskemalet i
                               prompten, blir ett nytt motiv (<slug>-v2) i Pop-Up-butiken,
                               det gamla tas bort. Max EDITS_PER_RUN per timme.
  4. mockups                   Printifys produktbilder (vaska, mugg, troja ...) hamtas sa
                               dashboarden visar samma som drjonsson.printify.me
  5. publicera pa Etsy         BARA motiv med ✅ och bara de produkttyper Marc kryssat
                               (0,20 USD per listning - bocken pa sidan ar Marcs ja)
  6. git push + Telegram       om nagot hande

  python drain.py            hela dräneringen
  python drain.py --dry-run  visa vad som skulle goras
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_daily as g   # noqa: E402  (hjalpfunktioner, samma sokvagar)
import printify_bulk as pb   # noqa: E402

EDITS_PER_RUN = 5
MOCKUPS_PER_RUN = 120
APPROVALS = g.DOCS / "data" / "approvals.json"


# ---------- approvals.json ----------

def load_approvals() -> dict:
    if not APPROVALS.exists():
        return {"items": {}, "updated": None}
    try:
        d = json.loads(APPROVALS.read_text(encoding="utf-8"))
    except ValueError:
        return {"items": {}, "updated": None}
    d.setdefault("items", {})
    return d


def save_approvals(d: dict) -> None:
    d["updated"] = datetime.now().isoformat(timespec="seconds")
    APPROVALS.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def all_types() -> list[str]:
    cfg = json.loads((HERE / "products.json").read_text(encoding="utf-8"))
    return list(cfg.get("default", ["poster"]))


def item_by_slug(status: dict, slug: str) -> dict | None:
    return next((i for i in status["items"] if i["slug"] == slug), None)


# ---------- Printify-hjalp ----------

def api() -> pb.Printify | None:
    e = g.env()
    tok = e.get("PRINTIFY_TOKEN")
    if not tok or tok.startswith("eyJ..."):
        return None
    return pb.Printify(tok)


def product_ids(shop: str, slug: str) -> dict[str, str]:
    """typ -> product_id i en butik, ur printify_bulk.state.json"""
    st = pb.load_state()
    out = {}
    for k, v in st.items():
        parts = k.split(":")
        if len(parts) == 3 and parts[0] == shop and parts[1] == slug and isinstance(v, dict) and v.get("product_id"):
            out[parts[2]] = v["product_id"]
    return out


def forget_products(shop: str, slug: str) -> None:
    st = pb.load_state()
    for k in [k for k in st if k.startswith(f"{shop}:{slug}:")]:
        del st[k]
    pb.save_state(st)


def run_bulk(slugs: list[str], shop: str, publish: bool, products: list[str] | None = None, dry: bool = False,
             split: bool = False) -> tuple[bool, str]:
    cmd = [g.PY, str(HERE / "printify_bulk.py"), "--only", ",".join(slugs), "--shop", shop, "--yes", "--max-minutes", "40"]
    if publish:
        cmd.append("--publish")
    if split:
        cmd.append("--split-variants")
    if products:
        cmd += ["--products", ",".join(products)]
    if dry:
        g.log("  (dry) " + " ".join(cmd[2:]))
        return True, ""
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(g.ROOT))
    out = (r.stdout + r.stderr).strip()
    g.log(f"  printify_bulk shop={shop} publish={publish} products={products or 'alla'} exit={r.returncode}")
    return r.returncode == 0, out


# ---------- 2. radera ----------

def do_deletes(status: dict, appr: dict, e: dict, P: pb.Printify | None, dry: bool) -> int:
    n = 0
    for slug, a in list(appr["items"].items()):
        if not a.get("radera") or a.get("raderad"):
            continue
        it = item_by_slug(status, slug)
        g.log(f"radera {slug}")
        for shop_key in ("PRINTIFY_POPUP_SHOP_ID", "PRINTIFY_ETSY_SHOP_ID"):
            shop = e.get(shop_key)
            if not shop or not P:
                continue
            for typ, pid in product_ids(shop, slug).items():
                if dry:
                    g.log(f"  (dry) DELETE {shop}/{pid} ({typ})")
                    continue
                try:
                    P.delete_product(shop, pid)
                    g.log(f"  borttagen {typ} {pid} i {shop}")
                except RuntimeError as ex:
                    if "404" in str(ex):
                        g.log(f"  redan borta: {typ} {pid}")
                    else:
                        g.log(f"  FEL delete {typ}: {ex}")
            if not dry:
                forget_products(shop, slug)
        if dry:
            continue
        if it:
            status["items"] = [i for i in status["items"] if i["slug"] != slug]
            status.setdefault("raderade", []).insert(0, {"slug": slug, "name": it.get("name"), "date": it.get("date"),
                                                         "raderad": datetime.now().isoformat(timespec="seconds")})
            status["raderade"] = status["raderade"][:200]
        for p in (g.DOCS_IMG / f"{slug}.jpg", g.IMAGES / f"{slug}.jpg"):
            if p.exists():
                p.unlink()
        a["raderad"] = datetime.now().isoformat(timespec="seconds")
        n += 1
    return n


# ---------- 3. redigera ----------

def do_edits(status: dict, appr: dict, e: dict, P: pb.Printify | None, dry: bool) -> int:
    n = 0
    for slug, a in list(appr["items"].items()):
        if n >= EDITS_PER_RUN:
            break
        pending = [r for r in a.get("redigera", []) if not r.get("klar")]
        if not pending or a.get("raderad"):
            continue
        it = item_by_slug(status, slug)
        if not it:
            for r in pending:
                r["klar"] = datetime.now().isoformat(timespec="seconds")
                r["fel"] = "motivet finns inte langre"
            continue
        req = pending[0]
        version = (it.get("version") or 1) + 1
        base = it.get("root") or slug.split("-v")[0]
        new_slug = f"{base}-v{version}"
        text = req["text"].strip()
        g.log(f"redigera {slug} -> {new_slug}: {text[:80]}")
        if dry:
            continue
        try:
            m = {"prompt": f"{it['prompt']} Requested change: {text}.", "negative": g.motifs.NEGATIVE,
                 "seed": (int(it.get("seed") or 1) * 7 + version * 1013) % (2**31 - 1) or 1}
            out = g.OUTPUTS / "redigerade" / f"{new_slug}.jpg"
            g.generate_image(m, out)
            g.make_thumb(out, g.DOCS_IMG / f"{new_slug}.jpg")
            g.IMAGES.mkdir(exist_ok=True)
            (g.IMAGES / f"{new_slug}.jpg").write_bytes(out.read_bytes())
            listings = json.loads(g.LISTINGS.read_text(encoding="utf-8"))
            src = listings.get(slug) or listings.get(base) or {}
            listings[new_slug] = {"title": src.get("title", it.get("title", it["name"])),
                                  "description": src.get("description", ""), "tags": src.get("tags", it.get("tags", []))}
            g.LISTINGS.write_text(json.dumps(listings, indent=2, ensure_ascii=False), encoding="utf-8")
            new_it = dict(it)
            new_it.update({"slug": new_slug, "name": f"{it['name'].split(' (v')[0]} (v{version})", "thumb": f"img/{new_slug}.jpg",
                           "prompt": m["prompt"], "seed": m["seed"], "printify": {}, "version": version, "root": base,
                           "edited_from": slug, "edit_text": text, "edited": datetime.now().isoformat(timespec="seconds")})
            status["items"].insert(0, new_it)
            # Pop-Up: nya produkter, sedan bort med de gamla
            popup = e.get("PRINTIFY_POPUP_SHOP_ID")
            if popup and P:
                ok, o = run_bulk([new_slug], popup, publish=True)
                if not ok:
                    g.log("  FEL pop-up for redigerat motiv: " + o[-200:])
                for typ, pid in product_ids(popup, slug).items():
                    try:
                        P.delete_product(popup, pid)
                    except RuntimeError as ex:
                        g.log(f"  FEL delete gammal {typ}: {ex}")
                forget_products(popup, slug)
                ids = g.printify_ids(popup)
                if new_slug in ids:
                    o2 = ids[new_slug]
                    new_it["printify"].update({"popup_products": o2["products"], "popup_product": True,
                                               "popup_published": o2["published"] > 0, "popup_count": f"{o2['published']}/{o2['total']}"})
            # gamla motivet: ut ur listan (ersatt)
            status["items"] = [i for i in status["items"] if i["slug"] != slug]
            for p in (g.DOCS_IMG / f"{slug}.jpg",):
                if p.exists():
                    p.unlink()
            req["klar"] = datetime.now().isoformat(timespec="seconds")
            req["ny_slug"] = new_slug
            a["ersatt_av"] = new_slug
            a["beslut"] = None          # nya versionen vantar pa nytt beslut
            appr["items"].setdefault(new_slug, {"beslut": None, "produkter": a.get("produkter"), "redigera": [],
                                                "nar": datetime.now().isoformat(timespec="seconds"), "av": "drain", "fran": slug})
            n += 1
        except Exception as ex:
            g.log(f"  FEL redigering {slug}: {type(ex).__name__}: {ex}")
            g.log(traceback.format_exc()[-600:])
            req["fel"] = f"{type(ex).__name__}: {ex}"[:200]
            req["klar"] = datetime.now().isoformat(timespec="seconds")
    return n


# ---------- 4. mockups ----------

def do_mockups(status: dict, e: dict, P: pb.Printify | None, dry: bool) -> int:
    popup = e.get("PRINTIFY_POPUP_SHOP_ID")
    if not popup or not P:
        return 0
    n = 0
    for it in status["items"]:
        pr = it.setdefault("printify", {})
        prods = pr.get("popup_products") or {}
        mock = pr.setdefault("mockups", {})
        for typ, pid in prods.items():
            if (typ in mock and typ in pr.get("variants", {})) or n >= MOCKUPS_PER_RUN:
                continue
            if dry:
                continue
            try:
                time.sleep(0.15)   # 600 anrop/min ar taket; ~7/s haller oss under
                p = P.get_product(popup, pid)
                imgs = p.get("images") or []
                front = next((x for x in imgs if x.get("is_default")), imgs[0] if imgs else None)
                pr.setdefault("variants", {})[typ] = sum(1 for v in p.get("variants", []) if v.get("is_enabled"))
                if front and front.get("src"):
                    mock[typ] = front["src"]
                    pr.setdefault("popup_urls", {})[typ] = f"https://drjonsson.printify.me/product/{pid}"
                    n += 1
            except RuntimeError as ex:
                g.log(f"  mockup {it['slug']}/{typ}: {ex}")
                if "429" in str(ex):
                    return n
    return n


# ---------- 5. Etsy ----------

def etsy_todo(status: dict, appr: dict, e: dict) -> list[tuple[str, list[str], bool]]:
    """(slug, produkttyper som saknas pa Etsy, separat) for varje ✅-motiv.
    separat = Marcs val "Separata listningar": en listning per storlek/farg (printify_bulk --split-variants).
    Annars "Samma listning": alla storlekar som alternativ i en listning per produkttyp."""
    etsy = e.get("PRINTIFY_ETSY_SHOP_ID")
    types = all_types()
    out = []
    st = pb.load_state() if etsy else {}
    for slug, a in appr["items"].items():
        if a.get("beslut") != "ja" or a.get("raderad") or a.get("ersatt_av"):
            continue
        if not item_by_slug(status, slug):
            continue
        wanted = [t for t in (a.get("produkter") or []) if t in types]   # inga kryss = inget till Etsy
        done = {k.split(":")[2].split("#")[0] for k, v in st.items()
                if etsy and k.startswith(f"{etsy}:{slug}:") and isinstance(v, dict) and v.get("published")}
        missing = [t for t in wanted if t not in done]
        if missing:
            out.append((slug, missing, a.get("lage") == "separat"))
    return out


def do_etsy(status: dict, appr: dict, e: dict, dry: bool) -> int:
    etsy = e.get("PRINTIFY_ETSY_SHOP_ID")
    todo = etsy_todo(status, appr, e)
    if not todo:
        g.log("  etsy: inget nytt godkant")
        return 0
    if not etsy:
        g.log(f"  etsy: {len(todo)} godkanda motiv vantar - PRINTIFY_ETSY_SHOP_ID saknas")
        return 0
    n = 0
    # gruppera per identisk produktlista sa det blir fa anrop
    groups: dict[tuple, list[str]] = {}
    for slug, missing, separat in todo:
        groups.setdefault((tuple(missing), separat), []).append(slug)
    for (types, separat), slugs in groups.items():
        g.log(f"  etsy: {len(slugs)} motiv x {list(types)} {'separata listningar' if separat else 'samma listning'}")
        ok, out = run_bulk(slugs, etsy, publish=True, products=list(types), dry=dry, split=separat)
        if not ok:
            g.log("  FEL etsy: " + out[-300:])
    ids = g.printify_ids(etsy)
    for it in status["items"]:
        if it["slug"] in ids:
            o = ids[it["slug"]]
            it["printify"].update({"etsy_products": o["products"], "etsy_product": bool(o["products"]),
                                   "etsy_published": o["published"] > 0, "etsy_count": f"{o['published']}/{o['total']}"})
            n += o["published"]
    return n


# ---------- huvud ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run

    g.log("=== dranering (Marcs beslut) ===")
    g.git_pull()
    e = g.env()
    P = api()
    status = g.load_status()
    appr = load_approvals()

    deleted = do_deletes(status, appr, e, P, dry)
    edited = do_edits(status, appr, e, P, dry)
    mocks = do_mockups(status, e, P, dry)
    published = do_etsy(status, appr, e, dry)

    if not dry:
        g.refresh_todo(status, e)
        save_approvals(appr)
        g.save_status(status)
        changed = deleted or edited or mocks or published
        if changed and not args.no_push:
            g.git_push()
        if (deleted or edited or published) and not args.no_telegram:
            parts = []
            if deleted:
                parts.append(f"{deleted} raderade")
            if edited:
                parts.append(f"{edited} omgjorda efter dina onskemal")
            if published:
                parts.append(f"{published} produkter publicerade pa Etsy")
            g.telegram_send(None, "🧭 DrJonsson: " + ", ".join(parts) + f"\n{g.DASHBOARD_URL}")
    g.log(f"=== dranering klar: raderade={deleted} redigerade={edited} mockups={mocks} etsy={published} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

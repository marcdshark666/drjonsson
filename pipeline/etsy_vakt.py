"""
etsy_vakt.py - Vakthund 14 (Etsy-hunden): ENBART LASANDE koll av Etsy-butiken DrJonssonDesign.

  .venv\\Scripts\\python.exe pipeline\\etsy_vakt.py            # vanlig korning (Telegram + ev. Work List-mejl)
  .venv\\Scripts\\python.exe pipeline\\etsy_vakt.py --dry      # skriv bara rapporten, skicka/spara inget
  .venv\\Scripts\\python.exe pipeline\\etsy_vakt.py --force    # skicka aven om passet redan rapporterats

Koras av uppgiften DrJonsson-EtsyVakt 09:00 och 18:00 (schedule/install_etsyvakt_task.ps1),
aldrig i standbysessionen (protokollets par. 3g/14).

Vad den gor:
  1. Butikssidan etsy.com/shop/DrJonssonDesign: forst vanlig HTTP, sedan headless Chrome.
     Etsy skyddar sidan med DataDome (captcha) - da rapporteras "kunde inte lasa", ingen gissning.
  2. Printify (befintlig token i pipeline/.env, aldrig i kod): butikerna, Etsy-butikens produkter
     (synliga + kopplade till en Etsy-listning = aktiva listningar), och att varje produkts
     standardmockup laddar (HTTP 200, rimlig storlek) fran Printifys bild-CDN.
  3. Ordrar: GET /v1/shops/{id}/orders.json - nya sedan forra korningen, status, fastnade/felade.
  4. Kort rapport (<= 8 rader) till Marcs Telegram; tyst dag = "Etsy: allt lugnt".
     Dubbelsandningsspärr per pass (datum + natt/fm/em) i state/etsy-vakt.json.
  5. Nagot viktigt (ny order, felad/fastnad order, butiken borta, trasiga foton) -> ETT uppdrag pa
     The Work List: "skicka mejl till Marc". Ett schemalagt skript har ingen Gmail-nyckel och far
     inte skaffa en; vakthunden som tar uppdraget skickar via Gmail-MCP. Work List-sajten ar
     publik: texten bar bara antal och status, aldrig namn, adresser eller belopp per kund.
     Samma handelse mejlas bara en gang (nycklar i state).

Absolut: inga kop, publiceringar, andringar i listningar/priser, inga inloggningar. Bara GET.
Printifys 429: max ~3 API-anrop per korning och graciost stopp vid strypning.
state/etsy-vakt.json ar gitignorad - repot ar PUBLIKT.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STATE = ROOT / "state" / "etsy-vakt.json"
LOG = ROOT / "outputs" / "etsy-vakt.log"
SHOP_URL = "https://www.etsy.com/shop/DrJonssonDesign"
API = "https://api.printify.com/v1"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TG_SEND = Path.home() / ".claude" / "hooks" / "telegram-send.js"
WORKLIST = ROOT.parent / "the-work-list" / "worklist.js"
MARKER = "DrJonsson-EtsyVakt"
MAIL_TO = "mkjonssonpf@gmail.com"
MIN_BILD_BYTES = 10_000
CHROME = next((p for p in (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
) if os.path.exists(p)), None)

# Printify-orderstatusar
FELADE = {"has-issues", "payment-not-received", "canceled", "cancelled"}
VANTANDE = {"pending", "on-hold"}           # fastnad om aldre an FAST_TIMMAR
FAST_TIMMAR = 48


def log(msg: str) -> None:
    rad = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(rad + "\n")
    except OSError:
        pass
    print(rad)


def env() -> dict[str, str]:
    out: dict[str, str] = {}
    p = HERE / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    out.update({k: v for k, v in os.environ.items() if k.startswith("PRINTIFY_")})
    return out


class Strypt(Exception):
    """Printify svarade 429 - sluta fraga, rapportera det man har."""


def printify_get(token: str, path: str) -> dict | list:
    req = urllib.request.Request(f"{API}{path}", method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", "drjonsson-etsyvakt/1.0")
    for forsok in range(2):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read().decode()
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise Strypt(path) from None
            if e.code >= 500 and forsok == 0:
                time.sleep(10)
                continue
            raise RuntimeError(f"GET {path} -> HTTP {e.code}") from None
        except urllib.error.URLError as e:
            if forsok == 0:
                time.sleep(5)
                continue
            raise RuntimeError(f"GET {path} -> natverksfel: {e.reason}") from None
    raise RuntimeError(f"GET {path} misslyckades")


# ---------- 1. butikssidan ----------

def _tolka_sida(html: str) -> dict:
    low = html.lower()
    if "datadome" in low or "captcha" in low:
        return {"ok": None, "skal": "blockerad (DataDome/captcha)"}
    if "drjonssondesign" not in low:
        return {"ok": None, "skal": "sidan saknade butiksnamnet"}
    import re
    antal = None
    m = re.search(r"([\d,]+)\s+(?:items|artiklar|listings)", html, re.I)
    if m:
        antal = int(m.group(1).replace(",", ""))
    return {"ok": True, "skal": "svarar", "antal": antal}


def las_butikssida() -> dict:
    # a) vanlig HTTP
    try:
        req = urllib.request.Request(SHOP_URL, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=30) as r:
            res = _tolka_sida(r.read().decode(errors="replace"))
            res["via"] = "http"
            if res["ok"]:
                return res
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return {"ok": False, "skal": f"HTTP {e.code} - butiken hittas inte", "via": "http"}
        if e.code >= 500:
            http_fel = f"HTTP {e.code}"
        else:
            http_fel = None   # 403 = DataDome, prova Chrome
    except Exception:
        pass
    # b) headless Chrome
    if not CHROME:
        return {"ok": None, "skal": "kunde inte lasa (chrome saknas, HTTP blockerad)", "via": "-"}
    prof = tempfile.mkdtemp(prefix="etsyvakt-chrome-")
    try:
        out = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             "--disable-extensions", "--disable-blink-features=AutomationControlled",
             f"--user-data-dir={prof}", f"--user-agent={UA}", "--window-size=1366,900",
             "--virtual-time-budget=12000", "--dump-dom", SHOP_URL],
            capture_output=True, timeout=90)
        res = _tolka_sida(out.stdout.decode("utf-8", errors="replace"))
        res["via"] = "chrome"
        return res
    except Exception as e:
        return {"ok": None, "skal": f"kunde inte lasa ({type(e).__name__})", "via": "chrome"}
    finally:
        shutil.rmtree(prof, ignore_errors=True)


# ---------- 2. foton ----------

def kolla_bild(url: str) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(2_000_000)
            typ = r.headers.get("Content-Type", "")
            if r.status != 200:
                return False, f"HTTP {r.status}"
            if "image" not in typ:
                return False, f"typ {typ or '?'}"
            if len(data) < MIN_BILD_BYTES:
                return False, f"bara {len(data)} byte"
            return True, ""
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, type(e).__name__


def standardbild(prod: dict) -> str | None:
    bilder = prod.get("images") or []
    for b in bilder:
        if b.get("is_default") and b.get("src"):
            return b["src"]
    return bilder[0]["src"] if bilder and bilder[0].get("src") else None


# ---------- 3. ordrar ----------

def _tid(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None


def granska_ordrar(ordrar: list[dict], sedda: dict) -> dict:
    nu = dt.datetime.now(dt.timezone.utc)
    nya, felade, fastnade, andrade = [], [], [], []
    for o in ordrar:
        oid = str(o.get("id"))
        st = str(o.get("status") or "?").lower()
        if oid not in sedda:
            nya.append((oid, st))
        elif sedda[oid] != st:
            andrade.append((oid, sedda[oid], st))
        if st in FELADE:
            felade.append((oid, st))
        elif st in VANTANDE:
            t = _tid(o.get("created_at"))
            if t and t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            if t and (nu - t).total_seconds() > FAST_TIMMAR * 3600:
                fastnade.append((oid, st))
    return {"nya": nya, "felade": felade, "fastnade": fastnade, "andrade": andrade}


def kortid(oid: str) -> str:
    return oid[-6:]


# ---------- state / utskick ----------

def las_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def spara_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE)


def skicka_telegram(text: str) -> bool:
    try:
        r = subprocess.run(["node", str(TG_SEND), text], capture_output=True, timeout=60)
        if r.returncode != 0:
            log(f"telegram-send misslyckades: {r.stderr.decode(errors='replace')[:200]}")
        return r.returncode == 0
    except Exception as e:
        log(f"telegram-send kunde inte koras: {e}")
        return False


def lagg_mejluppdrag(amne: str, kropp: list[str]) -> bool:
    """ETT Work List-uppdrag; vakthunden skickar mejlet via Gmail-MCP. Ingen kunddata."""
    text = (
        f"{MARKER} {dt.date.today():%Y-%m-%d}: skicka ETT mejl via Gmail-MCP till {MAIL_TO} "
        f"med amnet \"DrJonsson Etsy: {amne}\" och brodtexten nedan (ordagrant). "
        "Inget annat - rör inte butiken, Printify eller listningarna.\n\n" + "\n".join(kropp)
        + "\n\n(Skickat av Etsy-vakten, aaron-prints/pipeline/etsy_vakt.py. Detaljer: Printify-appen.)"
    )
    try:
        r = subprocess.run(["node", str(WORKLIST), "add", text], capture_output=True, timeout=120)
        ut = (r.stdout or b"").decode(errors="replace").strip()
        log(f"work list: {ut or r.stderr.decode(errors='replace')[:200]}")
        return r.returncode == 0
    except Exception as e:
        log(f"kunde inte lagga Work List-uppdrag: {e}")
        return False


# ---------- huvud ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="skicka och spara inget, skriv bara rapporten")
    ap.add_argument("--force", action="store_true", help="skicka aven om passet redan rapporterats")
    a = ap.parse_args()

    nu = dt.datetime.now()
    pass_id = f"{nu:%Y-%m-%d}-{'natt' if nu.hour < 6 else 'fm' if nu.hour < 13 else 'em'}"
    state = las_state()
    if not a.dry and not a.force and state.get("senast_skickat_pass") == pass_id:
        log(f"passet {pass_id} redan rapporterat - inget skickas (--force for att skicka igen)")
        return 0

    e = env()
    token = e.get("PRINTIFY_TOKEN")
    etsy_id = e.get("PRINTIFY_ETSY_SHOP_ID") or ""
    popup_id = e.get("PRINTIFY_POPUP_SHOP_ID") or ""
    rader: list[str] = []
    larm: list[tuple[str, str]] = []   # (nyckel, kort text) - viktigt -> mejl
    strypt = False

    # 1. butikssidan
    sida = las_butikssida()
    if sida["ok"] is False:
        larm.append((f"butik-nere:{nu:%Y-%m-%d}", f"butikssidan: {sida['skal']}"))
        rader.append(f"Butikssidan: NERE - {sida['skal']}")
    elif sida["ok"]:
        rader.append(f"Butikssidan svarar" + (f", {sida['antal']} listningar" if sida.get("antal") else ""))
    else:
        rader.append(f"Butikssidan: kunde inte läsa ({sida['skal']})")

    # 2-3. Printify
    shop_id, shop_namn = (etsy_id, "Etsy") if etsy_id else (popup_id, "Pop-Up")
    produkter: list[dict] = []
    ordrar: list[dict] = []
    if not token:
        rader.append("Printify: token saknas i pipeline/.env")
    else:
        try:
            shops = printify_get(token, "/shops.json")
            ids = {str(s.get("id")): s for s in shops} if isinstance(shops, list) else {}
            if etsy_id and etsy_id not in ids:
                larm.append((f"etsy-koppling-borta:{nu:%Y-%m-%d}", "Etsy-butiken saknas i Printify (kopplingen bruten?)"))
                rader.append("Printify: Etsy-butiken saknas i kontot - kopplingen bruten?")
                shop_id, shop_namn = popup_id, "Pop-Up"
            elif not etsy_id:
                rader.append("Printify: Etsy-kopplingen saknas (PRINTIFY_ETSY_SHOP_ID) - kollar Pop-Up")
            pr = printify_get(token, f"/shops/{shop_id}/products.json?limit=50&page=1")
            produkter = [p for p in pr.get("data", []) if not p.get("is_deleted")]
            totalt = pr.get("total", len(produkter))
            od = printify_get(token, f"/shops/{shop_id}/orders.json?limit=50&page=1")
            ordrar = od.get("data", []) or []
        except Strypt as s:
            strypt = True
            log(f"Printify strypte (429) vid {s} - stoppar graciost")
        except Exception as ex:
            rader.append(f"Printify: fel - {ex}"[:150])
            log(f"Printify-fel: {ex}")

    # listningar + foton
    if produkter:
        aktiva = [p for p in produkter if p.get("visible") and (p.get("external") or {}).get("id")]
        utan_bild, trasiga = [], []
        for p in produkter:
            src = standardbild(p)
            if not src:
                utan_bild.append(p)
                continue
            ok, why = kolla_bild(src)
            if not ok:
                trasiga.append((p, why))
        prev_aktiva = state.get("aktiva_listningar")
        diff = f" ({len(aktiva) - prev_aktiva:+d})" if isinstance(prev_aktiva, int) and prev_aktiva != len(aktiva) else ""
        rader.append(f"{shop_namn}: {len(aktiva)} aktiva listningar av {totalt} produkter{diff}")
        # Inget larm vid 0 aktiva listningar: DrJonsson-printsen togs bort fran Etsy 2026-10-13
        # (Marcs beslut) - motiven saljs via Pop-Up-butiken, Etsy-butiken far senare 3D-printlistningar.
        if not utan_bild and not trasiga:
            rader.append(f"Foton: alla {len(produkter)} mockups laddar")
        else:
            delar = []
            if trasiga:
                delar.append(f"{len(trasiga)} trasiga ({trasiga[0][1]})")
            if utan_bild:
                delar.append(f"{len(utan_bild)} utan mockup")
            rader.append("Foton: " + ", ".join(delar))
            nyckel = "foton:" + ",".join(sorted(str(p.get("id"))[-6:] for p, _ in trasiga) + sorted(str(p.get("id"))[-6:] for p in utan_bild))
            larm.append((nyckel, "Foton: " + ", ".join(delar)))
        state["aktiva_listningar"] = len(aktiva)
    elif token and not strypt and shop_id:
        rader.append(f"{shop_namn}: 0 listningar (väntat - DrJonsson-printsen borttagna 2026-10-13)")

    # ordrar
    sedda: dict = state.get("ordrar", {})
    if ordrar or (token and not strypt):
        g = granska_ordrar(ordrar, sedda)
        forsta = not sedda and "ordrar" not in state
        if g["nya"] and not forsta:
            st = ", ".join(sorted({s for _, s in g["nya"]}))
            rader.append(f"🛒 {len(g['nya'])} ny(a) order ({st})")
            larm.append(("ny:" + ",".join(sorted(o for o, _ in g["nya"])), f"{len(g['nya'])} ny(a) order ({st})"))
        elif forsta:
            rader.append(f"Ordrar: {len(ordrar)} totalt (första körningen, baslinje satt)")
        if g["felade"]:
            rader.append("⚠️ Felade: " + ", ".join(f"#{kortid(o)} {s}" for o, s in g["felade"]))
            larm.append(("fel:" + ",".join(sorted(f"{o}={s}" for o, s in g["felade"])), f"{len(g['felade'])} order med problem ({', '.join(sorted({s for _, s in g['felade']}))})"))
        if g["fastnade"]:
            rader.append(f"⏳ Fastnade >{FAST_TIMMAR} h: " + ", ".join(f"#{kortid(o)} {s}" for o, s in g["fastnade"]))
            larm.append(("fast:" + ",".join(sorted(o for o, _ in g["fastnade"])), f"{len(g['fastnade'])} order fastnad(e) i pending/on-hold > {FAST_TIMMAR} h"))
        if g["andrade"]:
            rader.append("Statusbyten: " + ", ".join(f"#{kortid(o)} {a}→{b}" for o, a, b in g["andrade"][:4]))
        if not (g["nya"] or g["felade"] or g["fastnade"] or g["andrade"] or forsta):
            rader.append(f"Ordrar: inga nya ({len(ordrar)} totalt)")
        state["ordrar"] = {str(o.get("id")): str(o.get("status") or "?").lower() for o in ordrar} or sedda
    if strypt:
        rader.append("Printify strypte (429) - kollen avbröts, tar resten nästa pass")

    # rapport
    viktigt = [t for _, t in larm]
    tyst = not viktigt and not strypt and all(not r.startswith(("Printify: fel", "Printify: token")) for r in rader)
    if tyst:
        aktiva_txt = next((r for r in rader if "aktiva listningar" in r), "")
        text = "🛍️ Etsy: allt lugnt" + (f" · {aktiva_txt.split(': ', 1)[-1].split(' av ')[0]}" if aktiva_txt else "")
        if sida["ok"] is None:
            text += " · butikssidan ej läsbar (DataDome)"
    else:
        text = "🛍️ <b>Etsy-vakten (Vakthund 14)</b>\n" + "\n".join(rader[:7])

    log("rapport:\n" + text)
    if a.dry:
        print("\n--- DRY: inget skickat, inget sparat ---\n" + text)
        return 0

    mejlade: list = state.get("mejlade", [])
    nya_larm = [(k, t) for k, t in larm if k not in mejlade]
    if nya_larm:
        amne = nya_larm[0][1][:60]
        kropp = [f"- {t}" for _, t in nya_larm] + [f"- Läge: {r}" for r in rader if r not in {t for _, t in nya_larm}][:5]
        if lagg_mejluppdrag(amne, kropp):
            mejlade.extend(k for k, _ in nya_larm)
            state["mejlade"] = mejlade[-200:]

    if skicka_telegram(text):
        state["senast_skickat_pass"] = pass_id
    state["senast_korning"] = nu.isoformat(timespec="seconds")
    state["senast_rapport"] = text
    spara_state(state)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:  # aldrig tyst dod: logga och tala om det
        log(f"etsy_vakt kraschade: {ex!r}")
        sys.exit(1)

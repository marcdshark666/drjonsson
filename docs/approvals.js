/* approvals.js — Marcs beslut per motiv, sparade i repot (docs/data/approvals.json).
 *
 * Sidan ligger på GitHub Pages utan server. Läsning går via raw.githubusercontent
 * (ingen inloggning). Skrivning går rakt mot api.github.com med Marcs egen
 * fine-grained token (Contents: read & write, bara repot marcdshark666/drjonsson),
 * som ligger i den här webbläsarens localStorage och aldrig i sidan. Samma
 * mönster som The Work List (wl-github.js). Read-modify-write med ett återförsök
 * vid sha-krock, så två snabba klick inte tappar varandra.
 *
 * Post per motiv:
 *   beslut    "ja" | "nej" | null      ja = publicera på Etsy (0,20 USD/listning)
 *   produkter ["poster", "mug", ...]   vilka produkttyper som ska till Etsy (tom = inget)
 *   lage      "samma" | "separat"       samma = storlekar/farger som alternativ i EN listning per
 *                                       produkttyp (Printify kan aldrig lagga olika produkttyper i
 *                                       samma Etsy-listning); separat = en listning per storlek/farg
 *   radera    iso | null               Marc vill ta bort motivet (Printify + sidan)
 *   raderad   iso | null               utfört av pipeline/drain.py
 *   redigera  [{text, nar, klar, ny_slug, fel}]   ändringsönskemål; drain.py gör om bilden
 *   ersatt_av slug                     nya versionen efter en redigering
 *
 * pipeline/drain.py (uppgiften DrJonsson-Etsy, varje timme) utför besluten.
 */
window.DJ_APPROVALS = (function () {
  "use strict";
  const REPO = "marcdshark666/drjonsson";
  const PATH = "docs/data/approvals.json";
  const API = `https://api.github.com/repos/${REPO}/contents/${PATH}`;
  const RAW = `https://raw.githubusercontent.com/${REPO}/main/${PATH}`;
  const KEY = "dj.gh.token", KEY_LOGIN = "dj.gh.login";
  const ls = {
    get: (k) => { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } },
    set: (k, v) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch (e) { /* privat läge */ } },
  };
  let token = ls.get(KEY), login = ls.get(KEY_LOGIN);
  // Engangslank fran Telegram: https://.../drjonsson/#gh=<token>  (fragmentet nar aldrig servern)
  try {
    const m = /[#&]gh=([^&]+)/.exec(location.hash || "");
    if (m) {
      token = decodeURIComponent(m[1]).trim(); login = "";
      ls.set(KEY, token);
      history.replaceState(null, "", location.pathname + location.search);
    }
  } catch (e) { /* */ }
  let cache = { data: { items: {}, updated: null }, sha: null };

  const b64enc = (s) => btoa(unescape(encodeURIComponent(s)));
  const b64dec = (s) => decodeURIComponent(escape(atob(String(s || "").replace(/\s+/g, ""))));
  const now = () => new Date().toISOString();

  async function readViaApi() {
    const r = await fetch(API + "?ref=main&ts=" + Date.now(), { headers: { Authorization: "Bearer " + token, Accept: "application/vnd.github+json" }, cache: "no-store" });
    if (r.status === 404) return { data: { items: {}, updated: null }, sha: null };
    if (!r.ok) throw new Error("GitHub " + r.status);
    const j = await r.json();
    return { data: JSON.parse(b64dec(j.content) || "{}"), sha: j.sha };
  }
  async function readRaw() {
    const r = await fetch(RAW + "?ts=" + Date.now(), { cache: "no-store" });
    if (r.status === 404) return { data: { items: {}, updated: null }, sha: null };
    if (!r.ok) throw new Error("raw " + r.status);
    return { data: await r.json(), sha: null };
  }
  async function load() {
    if (token && !login) { login = await whoami(token); if (login) ls.set(KEY_LOGIN, login); else { token = ""; ls.set(KEY, ""); } }
    try { cache = token ? await readViaApi() : await readRaw(); }
    catch (e) { try { cache = await readRaw(); } catch (e2) { /* behåll det vi har */ } }
    if (!cache.data.items) cache.data.items = {};
    return cache.data;
  }

  async function whoami(t) {
    const r = await fetch("https://api.github.com/user", { headers: { Authorization: "Bearer " + t, Accept: "application/vnd.github+json" } });
    if (!r.ok) return "";
    return (await r.json()).login || "";
  }
  async function connect() {
    const t = window.prompt(
      "För att spara dina beslut behövs din egen GitHub-token (den stannar i den här webbläsaren).\n\n" +
      "Skapa den på github.com → Settings → Developer settings → Fine-grained tokens:\n" +
      "Repository: bara marcdshark666/drjonsson · Permissions: Contents = Read and write.\n\nKlistra in token här:", "");
    if (!t) return false;
    const l = await whoami(t.trim());
    if (!l) { window.alert("GitHub godkände inte den token."); return false; }
    token = t.trim(); login = l; ls.set(KEY, token); ls.set(KEY_LOGIN, login);
    await load();
    return true;
  }
  function disconnect() { token = ""; login = ""; ls.set(KEY, ""); ls.set(KEY_LOGIN, ""); }

  function summarize(data) {
    const v = Object.values(data.items || {});
    return v.filter((x) => x.beslut === "ja").length + " ja, " + v.filter((x) => x.beslut === "nej").length + " nej, "
      + v.filter((x) => x.radera && !x.raderad).length + " att radera, "
      + v.reduce((n, x) => n + (x.redigera || []).filter((r) => !r.klar).length, 0) + " redigeringar";
  }

  async function write(mutate) {
    if (!token && !(await connect())) throw new Error("Inte kopplad till GitHub");
    for (let attempt = 0; attempt < 2; attempt++) {
      const cur = await readViaApi();
      const data = cur.data; data.items = data.items || {};
      mutate(data);
      data.updated = now();
      const body = { message: "Beslut: " + summarize(data), content: b64enc(JSON.stringify(data, null, 2) + "\n"), branch: "main" };
      if (cur.sha) body.sha = cur.sha;
      const r = await fetch(API, { method: "PUT", headers: { Authorization: "Bearer " + token, Accept: "application/vnd.github+json", "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (r.status === 409 && attempt === 0) continue;   // sha-krock: läs om och skriv igen
      if (!r.ok) throw new Error("GitHub " + r.status + " " + (await r.text()).slice(0, 120));
      const j = await r.json();
      cache = { data, sha: j.content && j.content.sha };
      return data;
    }
    throw new Error("Kunde inte spara (sha-krock två gånger)");
  }

  function entry(data, slug) {
    return (data.items[slug] = data.items[slug] || { beslut: null, produkter: null, radera: null, raderad: null, redigera: [] });
  }

  /** beslut: "ja" | "nej" | null */
  function decide(slugs, beslut) {
    return write((data) => slugs.forEach((slug) => { const e = entry(data, slug); e.beslut = beslut; e.nar = now(); e.av = login || "?"; }));
  }
  /** produkter: lista av typer, eller null = alla */
  function setProducts(slug, produkter) {
    return write((data) => { const e = entry(data, slug); e.produkter = produkter; e.nar = now(); e.av = login || "?"; });
  }
  /** lage: "samma" | "separat" */
  function setMode(slug, lage) {
    return write((data) => { const e = entry(data, slug); e.lage = lage; e.nar = now(); e.av = login || "?"; });
  }
  function requestEdit(slug, text) {
    return write((data) => { const e = entry(data, slug); (e.redigera = e.redigera || []).push({ text, nar: now(), klar: null }); e.av = login || "?"; });
  }
  function remove(slugs, undo) {
    return write((data) => slugs.forEach((slug) => { const e = entry(data, slug); e.radera = undo ? null : now(); e.av = login || "?"; }));
  }

  return {
    load, decide, setProducts, setMode, requestEdit, remove, connect, disconnect,
    get: (slug) => (cache.data.items || {})[slug] || null,
    all: () => cache.data.items || {},
    connected: () => !!token,
    login: () => login,
  };
})();

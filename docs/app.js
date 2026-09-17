/* DrJonsson dashboard – läser data/status.json (pipelinen) och data/approvals.json (Marcs beslut).
   Knapparna skriver besluten till GitHub via approvals.js; pipeline/drain.py utför dem varje timme.
   Regeln (Marc 2026-09-17): ✅ på ett motiv publicerar BARA det motivet, och bara de produkter
   han kryssat i. Inga "alla"-knappar. Utan kryss går inget till Etsy. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (iso) => iso ? iso.replace("T", " ").slice(0, 16) : "–";
  const A = window.DJ_APPROVALS;
  const PER_ITEM_USD = 0.2;

  const TYPES = [
    ["poster", "Poster"], ["framed", "Inramad"], ["canvas", "Canvas"], ["framed_canvas", "Inramad canvas"],
    ["metal", "Metall"], ["mug", "Mugg"], ["tote", "Kasse"], ["tshirt", "T-shirt"],
  ];
  let types = TYPES.map((t) => t[0]);
  const label = (t) => (TYPES.find((x) => x[0] === t) || [t, t])[1];

  let status = null, tab = "vantar";
  try { tab = localStorage.getItem("dj.tab") || "vantar"; } catch (e) { /* */ }

  const dec = (it) => (A && A.get(it.slug)) || null;
  const pendingEdits = (a) => (a && a.redigera || []).filter((r) => !r.klar);
  const wanted = (a) => (a && a.produkter) || [];          // inga kryss = inget till Etsy
  const isDeleted = (a) => !!(a && a.radera && !a.raderad);

  function bucket(it) {
    const a = dec(it), p = it.printify || {};
    if (isDeleted(a)) return "raderade";
    if (pendingEdits(a).length || it.edited_from) return "redigerade";
    if (a && a.beslut === "ja") return "godkanda";
    if (p.etsy_published) return "godkanda";
    if (a && a.beslut === "nej") return "nekade";
    return "vantar";
  }

  /* ---------- kort ---------- */

  function stateLine(it) {
    const a = dec(it), p = it.printify || {};
    const c = [];
    if (isDeleted(a)) c.push('<span class="chip no">🗑 raderas nästa timme</span>');
    else if (pendingEdits(a).length) c.push('<span class="chip wait">✏️ görs om nästa timme</span>');
    else if (p.etsy_published) c.push('<span class="chip ok">etsy ' + esc(p.etsy_count || "live") + '</span>');
    else if (a && a.beslut === "ja") c.push('<span class="chip ok">✅ ' + wanted(a).length + ' produkter publiceras nästa timme</span>');
    else if (a && a.beslut === "nej") c.push('<span class="chip no">❌ nekad</span>');
    else c.push('<span class="chip wait">väntar på ditt beslut</span>');
    if (p.popup_published) c.push('<span class="chip">pop-up ' + esc(p.popup_count || "live") + '</span>');
    if (it.edited_from) c.push('<span class="chip">omgjord: ' + esc((it.edit_text || "").slice(0, 60)) + '</span>');
    return c.join("");
  }

  function productRow(it) {
    const a = dec(it), p = it.printify || {};
    const sel = new Set(wanted(a));
    const mock = p.mockups || {}, urls = p.popup_urls || {};
    return '<div class="prods">' + types.map((t) => {
      const on = sel.has(t);
      const img = mock[t] ? `<img src="${esc(mock[t])}" alt="${esc(label(t))}" loading="lazy">` : `<span class="ph">${esc(label(t))}<br><small>bild hämtas inom en timme</small></span>`;
      const zoom = mock[t] ? `<button type="button" class="pz" data-src="${esc(mock[t])}" data-name="${esc(label(t))}" title="Förstora">🔍</button>` : "";
      const link = urls[t] ? `<a class="pl" href="${esc(urls[t])}" target="_blank" rel="noopener" title="Öppna i butiken">↗</a>` : "";
      return `<label class="prod${on ? " on" : ""}" title="${esc(label(t))} – kryssa i för att ta med till Etsy">
        <input type="checkbox" data-type="${esc(t)}" ${on ? "checked" : ""}>${img}<span class="pn">${on ? "☑ " : "☐ "}${esc(label(t))}</span>${zoom}${link}</label>`;
    }).join("") + "</div>";
  }

  function buttons(it) {
    const a = dec(it), p = it.printify || {};
    const ja = a && a.beslut === "ja", nej = a && a.beslut === "nej";
    const n = wanted(a).length;
    const del = isDeleted(a);
    return `<div class="btns">
      <button class="ja${ja ? " on" : ""}" data-act="ja" ${p.etsy_published ? "disabled" : ""} title="Publicera de ikryssade produkterna på Etsy: ${n} listningar ≈ ${(n * PER_ITEM_USD).toFixed(2)} USD">✅ Ja${n ? " (" + n + ")" : ""}</button>
      <button class="nej${nej ? " on" : ""}" data-act="nej" title="Publicera inte på Etsy">❌ Nej</button>
      <button class="edit" data-act="edit" title="Be om en ändring – bilden görs om">✏️ Redigera</button>
      <button class="del${del ? " on" : ""}" data-act="del" title="${del ? "Ångra radering" : "Ta bort från Printify och sidan"}">🗑 ${del ? "Ångra" : "Radera"}</button>
    </div>`;
  }

  function card(it) {
    const a = dec(it), b = bucket(it);
    const edits = (a && a.redigera || []);
    const editList = edits.length ? '<ul class="edits">' + edits.slice(-3).map((r) =>
      `<li>${r.klar ? (r.fel ? "⚠️ " : "✔ ") : "⏳ "}${esc(r.text)}${r.fel ? ' <i>' + esc(r.fel) + '</i>' : ""}</li>`).join("") + "</ul>" : "";
    return `<div class="card ${b}" data-slug="${esc(it.slug)}">
      <img class="hero" src="${esc(it.thumb)}" alt="${esc(it.name)}" loading="lazy">
      <div class="b"><div class="n">${esc(it.name)}</div><div class="p">${esc(it.date)}</div>
        <div class="chips">${stateLine(it)}</div>${productRow(it)}${editList}${buttons(it)}</div>
    </div>`;
  }

  /* ---------- handlingar ---------- */

  function rerender() { if (status) render(status); }

  async function decide(slug, beslut, btn) {
    if (beslut === "ja") {
      const n = wanted(A.get(slug)).length;
      if (!n) { window.alert("Kryssa först i vilka produkter (poster, mugg, kasse …) som ska till Etsy, tryck sedan ✅ Ja."); return; }
      if (!window.confirm("Publicera det här motivet på Etsy som " + n + " produkter?\nEtsys listningsavgift: ≈ " + (n * PER_ITEM_USD).toFixed(2) + " USD. Inget annat kostar.")) return;
    }
    if (btn) btn.disabled = true;
    try { await A.decide([slug], beslut); rerender(); }
    catch (e) { window.alert("Kunde inte spara: " + e.message); if (btn) btn.disabled = false; }
  }

  function openEdit(slug) {
    const it = status.items.find((i) => i.slug === slug);
    $("#ed-name").textContent = it ? it.name : slug;
    $("#ed-text").value = "";
    $("#ed").dataset.slug = slug;
    $("#ed").showModal();
    $("#ed-text").focus();
  }

  function wire() {
    document.querySelectorAll(".card .btns button").forEach((b) => b.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      const slug = b.closest(".card").dataset.slug;
      const cur = A.get(slug);
      const act = b.dataset.act;
      if (act === "edit") return openEdit(slug);
      if (act === "del") {
        const undo = isDeleted(cur);
        if (!undo && !window.confirm("Ta bort motivet från Printify (alla produkter) och från den här sidan?")) return;
        b.disabled = true;
        try { await A.remove([slug], undo); rerender(); } catch (e) { window.alert("Kunde inte spara: " + e.message); b.disabled = false; }
        return;
      }
      decide(slug, cur && cur.beslut === act ? null : act, b);   // klick igen = ångra
    }));
    document.querySelectorAll(".card .prods input").forEach((cb) => cb.addEventListener("change", async () => {
      const cardEl = cb.closest(".card"), slug = cardEl.dataset.slug;
      const list = [...cardEl.querySelectorAll(".prods input")].filter((x) => x.checked).map((x) => x.dataset.type);
      cb.disabled = true;
      try { await A.setProducts(slug, list); rerender(); }
      catch (e) { window.alert("Kunde inte spara: " + e.message); cb.disabled = false; cb.checked = !cb.checked; }
    }));
    document.querySelectorAll(".card .prods .pz").forEach((b) => b.addEventListener("click", (ev) => {
      ev.preventDefault(); ev.stopPropagation();
      $("#dlg-img").src = b.dataset.src; $("#dlg-img").alt = b.dataset.name;
      $("#dlg-txt").textContent = b.dataset.name + " – " + (b.closest(".card").querySelector(".n") || {}).textContent;
      $("#dlg").showModal();
    }));
    document.querySelectorAll(".card img.hero").forEach((img) => img.addEventListener("click", () => {
      const it = status.items.find((i) => i.slug === img.closest(".card").dataset.slug);
      if (!it) return;
      $("#dlg-img").src = it.thumb; $("#dlg-img").alt = it.name;
      $("#dlg-txt").textContent = it.title;
      $("#dlg").showModal();
    }));
    document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => {
      tab = b.dataset.tab; try { localStorage.setItem("dj.tab", tab); } catch (e) { /* */ }
      rerender();
    }));
  }

  /* ---------- GitHub-rad ---------- */

  function ghBar() {
    const el = $("#gh");
    if (!A) { el.hidden = true; return; }
    el.hidden = false;
    el.innerHTML = A.connected()
      ? `Kopplad till GitHub som <b>${esc(A.login())}</b>. Dina beslut sparas i repot. <button id="gh-off">Koppla från</button>`
      : `<b>Koppla GitHub</b> för att spara dina beslut (behövs en gång per webbläsare). <button id="gh-on">Koppla</button>`;
    const on = $("#gh-on"), off = $("#gh-off");
    if (on) on.addEventListener("click", async () => { if (await A.connect()) rerender(); });
    if (off) off.addEventListener("click", () => { A.disconnect(); rerender(); });
  }

  /* ---------- butiksmail (rutinen DrJonsson-ButikMail) ---------- */

  const MAIL_ORD = { bekraftat: ["Butiken är klar", "bekraftat"], "atgard-kravs": ["Butiken väntar på dig", "atgard"], inget: ["Inget nytt om butiken", ""] };
  const fmtLocal = (iso) => {
    if (!iso) return "–";
    if (!/[zZ]$|[+-]\d\d:?\d\d$/.test(iso)) return fmt(iso);
    const d = new Date(iso);
    return isNaN(d) ? fmt(iso) : new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().replace("T", " ").slice(0, 16);
  };
  function storeMail(m) {
    const el = $("#storemail");
    if (!m || !m.checked) { el.hidden = true; return; }
    const [rubrik, kls] = MAIL_ORD[m.status] || MAIL_ORD.inget;
    el.className = "mail" + (kls ? " " + kls : "");
    const lank = m.action_url ? ` <a href="${esc(m.action_url)}" target="_blank" rel="noopener">${esc(m.action_url)}</a>` : "";
    el.innerHTML = `<b>${esc(rubrik)}</b><div class="h">${esc(m.headline || "")}</div>
      ${m.detail ? `<div class="d">${esc(m.detail)}${lank}</div>` : (lank ? `<div class="d">${lank}</div>` : "")}
      <div class="k">Gmail lästes ${fmtLocal(m.checked)}${m.source ? " · " + esc(m.source) : ""}</div>`;
    el.hidden = false;
  }

  /* ---------- render ---------- */

  function render(s) {
    status = s;
    const st = s.stats || {};
    const runs = s.runs || [];
    const last = runs[runs.length - 1];
    if (st.product_types && st.product_types !== types.length) types = TYPES.slice(0, st.product_types).map((t) => t[0]);
    $("#pulse").innerHTML = `Senast uppdaterad <b>${fmt(s.updated)}</b><br>Nya motiv <b>07:30</b> · besluten utförs <b>varje timme</b>` +
      (last && last.errors && last.errors.length ? `<br><span style="color:var(--warn)">${last.errors.length} fel i senaste körningen</span>` : "");

    const items = (s.items || []).slice().sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
    const by = { vantar: [], godkanda: [], redigerade: [], nekade: [], raderade: [] };
    items.forEach((i) => by[bucket(i)].push(i));
    const tiles = [
      [st.generated || 0, "motiv totalt"], [st.popup_live || 0, "live i pop-up"],
      [by.vantar.length, "väntar på beslut"], [by.godkanda.length, "godkända"], [st.etsy_live || 0, "live på etsy"],
      [by.redigerade.length, "redigerade"], [by.nekade.length, "nekade"], [by.raderade.length + (s.raderade || []).length, "raderade"],
    ];
    $("#tiles").innerHTML = tiles.map(([v, l]) => `<div class="tile"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
    ghBar();

    const TABS = [["vantar", "Väntar"], ["godkanda", "Godkända / postade"], ["redigerade", "Redigerade"], ["nekade", "Nekade"], ["raderade", "Raderade"]];
    $("#tabs").innerHTML = TABS.map(([k, l]) => `<button data-tab="${k}" class="${k === tab ? "on" : ""}">${l} <span>${by[k].length + (k === "raderade" ? (s.raderade || []).length : 0)}</span></button>`).join("");

    const list = by[tab] || [];
    const today = items.length ? items[0].date : "";
    const todayList = list.filter((i) => i.date === today), olderList = list.filter((i) => i.date !== today);
    let html = "";
    if (todayList.length) html += `<h3>Idag ${esc(today)}</h3><div class="grid">${todayList.map(card).join("")}</div>`;
    if (olderList.length) html += `<h3>${todayList.length ? "Tidigare" : ""}</h3><div class="grid">${olderList.map(card).join("")}</div>`;
    if (tab === "raderade" && (s.raderade || []).length) {
      html += `<h3>Borttagna</h3><ul class="plain">${s.raderade.map((r) => `<li>${esc(r.name || r.slug)} <small>${esc(r.date || "")} · raderad ${fmt(r.raderad)}</small></li>`).join("")}</ul>`;
    }
    if (!html) html = '<div class="empty">Inget här just nu.</div>';
    $("#list").innerHTML = html;
    wire();

    storeMail(s.store_mail);
    const todo = s.todo || [];
    $("#todo").innerHTML = todo.map((t) => `<li class="${t.done ? "done" : "open"}"><span class="m">${t.done ? "[x]" : "[ ]"}</span><span class="t">${esc(t.text)}</span><span class="w">${esc(t.who)}</span></li>`).join("");
    const nextOpen = todo.find((t) => !t.done);
    const nx = $("#next");
    if (nextOpen) { nx.hidden = false; nx.innerHTML = `<b>Nästa steg</b>${esc(nextOpen.text)} <span style="color:var(--ink-2)">(${esc(nextOpen.who)})</span>`; }
    else nx.hidden = true;

    $("#runs tbody").innerHTML = runs.slice().reverse().slice(0, 30).map((r) => `<tr>
      <td>${esc(r.date)}${r.dry_run ? " (torr)" : ""}${r.note === "etsy-only" ? " (beslut)" : ""}</td><td>${fmt(r.started)}</td>
      <td class="n">${r.generated}/${r.count}</td><td class="n">${r.popup || 0}</td><td class="n">${r.etsy || 0}</td>
      <td class="err">${esc((r.errors || []).join(" · ") || (r.note || ""))}</td></tr>`).join("")
      || '<tr><td colspan="6" class="empty">Inga körningar ännu.</td></tr>';
  }

  /* ---------- redigeringsdialog ---------- */
  $("#ed-save").addEventListener("click", async (ev) => {
    ev.preventDefault();
    const slug = $("#ed").dataset.slug, text = $("#ed-text").value.trim();
    if (!text) return;
    $("#ed-save").disabled = true;
    try { await A.requestEdit(slug, text); $("#ed").close(); rerender(); }
    catch (e) { window.alert("Kunde inte spara: " + e.message); }
    $("#ed-save").disabled = false;
  });
  $("#ed-cancel").addEventListener("click", (ev) => { ev.preventDefault(); $("#ed").close(); });
  $("#dlg").addEventListener("click", () => $("#dlg").close());

  Promise.all([
    fetch("data/status.json?ts=" + Date.now(), { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }),
    A ? A.load() : Promise.resolve(null),
  ])
    .then(([s]) => render(s))
    .catch((e) => { $("#pulse").textContent = "Kunde inte läsa status.json: " + e.message; $("#list").innerHTML = '<div class="empty">Ingen status ännu.</div>'; });
})();

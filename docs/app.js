/* DrJonsson dashboard – läser data/status.json som pipelinen skriver varje morgon. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (iso) => iso ? iso.replace("T", " ").slice(0, 16) : "–";

  const A = window.DJ_APPROVALS;
  const PER_ITEM_USD = 0.2;
  let nTypes = 8;

  function decision(it) { return (A && A.get(it.slug)) || null; }

  function chips(it) {
    const p = it.printify || {};
    const c = [];
    const d = decision(it);
    if (p.etsy_published) c.push('<span class="chip ok">etsy ' + (p.etsy_count || 'live') + '</span>');
    else if (d && d.beslut === "ja") c.push('<span class="chip ok">✅ godkänd, publiceras nästa timme</span>');
    else if (d && d.beslut === "nej") c.push('<span class="chip no">❌ nekad</span>');
    else c.push('<span class="chip wait">väntar på ditt beslut</span>');
    if (p.popup_published) c.push('<span class="chip ok">pop-up ' + (p.popup_count || 'live') + '</span>');
    else if (p.popup_product) c.push('<span class="chip">pop-up utkast</span>');
    else c.push('<span class="chip">pop-up väntar</span>');
    return c.join("");
  }

  function buttons(it) {
    const p = it.printify || {};
    if (p.etsy_published) return "";
    const d = decision(it);
    const ja = d && d.beslut === "ja", nej = d && d.beslut === "nej";
    return `<div class="btns">
      <button class="ja${ja ? " on" : ""}" data-act="ja" title="Publicera på Etsy: ${nTypes} listningar ≈ ${(nTypes * PER_ITEM_USD).toFixed(2)} USD">✅ Ja</button>
      <button class="nej${nej ? " on" : ""}" data-act="nej" title="Publicera aldrig på Etsy">❌ Nej</button>
    </div>`;
  }

  function card(it) {
    const d = decision(it);
    return `<div class="card${d ? " " + d.beslut : ""}" data-slug="${esc(it.slug)}">
      <img src="${esc(it.thumb)}" alt="${esc(it.name)}" loading="lazy">
      <div class="b"><div class="n">${esc(it.name)}</div><div class="p">${esc(it.date)}</div><div class="chips">${chips(it)}</div>${buttons(it)}</div>
    </div>`;
  }

  function dayButtons(items) {
    const open = items.filter((i) => !decision(i) && !(i.printify || {}).etsy_published).map((i) => i.slug);
    if (!open.length) return "";
    return `<div class="daybtns" data-slugs="${esc(open.join(","))}">
      <span>${open.length} väntar på beslut</span>
      <button data-act="ja">✅ Ja till alla ${open.length} (≈ ${(open.length * nTypes * PER_ITEM_USD).toFixed(2)} USD)</button>
      <button data-act="nej">❌ Nej till alla</button>
    </div>`;
  }

  function ghBar() {
    const el = $("#gh");
    if (!A) { el.hidden = true; return; }
    el.hidden = false;
    el.innerHTML = A.connected()
      ? `Kopplad till GitHub som <b>${esc(A.login())}</b>. Dina ✅/❌ sparas i repot. <button id="gh-off">Koppla från</button>`
      : `<b>Koppla GitHub</b> för att spara dina ✅/❌ (behövs en gång per webbläsare). <button id="gh-on">Koppla</button>`;
    const on = $("#gh-on"), off = $("#gh-off");
    if (on) on.addEventListener("click", async () => { if (await A.connect()) rerender(); });
    if (off) off.addEventListener("click", () => { A.disconnect(); rerender(); });
  }

  let lastStatus = null;
  function rerender() { if (lastStatus) render(lastStatus); }

  async function act(slugs, beslut, btn) {
    if (!slugs.length) return;
    if (beslut === "ja") {
      const usd = (slugs.length * nTypes * PER_ITEM_USD).toFixed(2);
      if (!window.confirm("Publicera " + slugs.length + " motiv × " + nTypes + " produkter på Etsy?\nEtsys listningsavgift: ≈ " + usd + " USD. Inget annat kostar.")) return;
    }
    if (btn) btn.disabled = true;
    try { await A.decide(slugs, beslut); rerender(); }
    catch (e) { window.alert("Kunde inte spara: " + e.message); if (btn) btn.disabled = false; }
  }

  function wireButtons() {
    document.querySelectorAll(".card .btns button").forEach((b) => b.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const slug = b.closest(".card").dataset.slug;
      const cur = A.get(slug);
      const beslut = cur && cur.beslut === b.dataset.act ? null : b.dataset.act;   // klick igen = ångra
      act([slug], beslut, b);
    }));
    document.querySelectorAll(".daybtns button").forEach((b) => b.addEventListener("click", (ev) => {
      ev.stopPropagation();
      act(b.closest(".daybtns").dataset.slugs.split(",").filter(Boolean), b.dataset.act, b);
    }));
  }

  /* Butiksmailet: rutinen DrJonsson-ButikMail lasar Gmail varje morgon och
     skriver state/store-mail.json. "bekraftat" = butiken far oppnas,
     "atgard-kravs" = Etsy/Printify vantar pa Marc, "inget" = inget nytt. */
  const MAIL_ORD = {
    bekraftat: ["Butiken är klar", "bekraftat"],
    "atgard-kravs": ["Butiken väntar på dig", "atgard"],
    inget: ["Inget nytt om butiken", ""],
  };

  /* Rutinen skriver `checked` i UTC (med Z), pipelinen skriver `updated` i lokal
     tid utan zon. Visa bada i lasarens tid sa att raderna gar att jamfora. */
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
    el.innerHTML = `<b>${esc(rubrik)}</b>
      <div class="h">${esc(m.headline || "")}</div>
      ${m.detail ? `<div class="d">${esc(m.detail)}${lank}</div>` : (lank ? `<div class="d">${lank}</div>` : "")}
      <div class="k">Gmail lästes ${fmtLocal(m.checked)}${m.source ? " · " + esc(m.source) : ""}</div>`;
    el.hidden = false;
  }

  function render(s) {
    const st = s.stats || {};
    const runs = s.runs || [];
    const last = runs[runs.length - 1];
    $("#pulse").innerHTML = `Senast uppdaterad <b>${fmt(s.updated)}</b><br>Nästa körning <b>07:30</b> varje dag` +
      (last && last.errors && last.errors.length ? `<br><span style="color:var(--warn)">${last.errors.length} fel i senaste körningen</span>` : "");

    lastStatus = s;
    nTypes = st.product_types || nTypes;
    const allItems = s.items || [];
    const nJa = allItems.filter((i) => (decision(i) || {}).beslut === "ja" && !(i.printify || {}).etsy_published).length;
    const nNej = allItems.filter((i) => (decision(i) || {}).beslut === "nej").length;
    const nOpen = allItems.filter((i) => !decision(i) && !(i.printify || {}).etsy_published).length;
    const tiles = [
      [st.generated || 0, "motiv totalt"],
      [st.popup_live || 0, "live i pop-up"],
      [nOpen, "väntar på ditt beslut"],
      [nJa, "godkända, väntar på etsy"],
      [st.etsy_live || 0, "live på etsy"],
      [nNej, "nekade"],
      [st.streak || 0, "dagar i rad"],
    ];
    ghBar();
    $("#tiles").innerHTML = tiles.map(([v, l]) => `<div class="tile"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");

    const items = (s.items || []).slice().sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
    const today = items.length ? items.filter((i) => i.date === items[0].date) : [];
    $("#today-date").textContent = today.length ? today[0].date : "";
    $("#today-btns").innerHTML = dayButtons(today);
    $("#today").innerHTML = today.length ? today.map(card).join("") : '<div class="empty">Inga motiv ännu. Första körningen pågår eller väntar på 07:30.</div>';
    const older = items.filter((i) => !today.includes(i));
    $("#all-btns").innerHTML = dayButtons(older);
    $("#all").innerHTML = older.map(card).join("");
    wireButtons();
    $("#all-count").textContent = items.length ? `${items.length} st` : "";

    storeMail(s.store_mail);

    const todo = s.todo || [];
    $("#todo").innerHTML = todo.map((t) => `<li class="${t.done ? "done" : "open"}"><span class="m">${t.done ? "[x]" : "[ ]"}</span><span class="t">${esc(t.text)}</span><span class="w">${esc(t.who)}</span></li>`).join("");
    const nextOpen = todo.find((t) => !t.done);
    const nx = $("#next");
    if (nextOpen) { nx.hidden = false; nx.innerHTML = `<b>Nästa steg</b>${esc(nextOpen.text)} <span style="color:var(--ink-2)">(${esc(nextOpen.who)})</span>`; }
    else nx.hidden = true;

    $("#runs tbody").innerHTML = runs.slice().reverse().map((r) => `<tr>
      <td>${esc(r.date)}${r.dry_run ? " (torr)" : ""}</td><td>${fmt(r.started)}</td>
      <td class="n">${r.generated}/${r.count}</td><td class="n">${r.popup || 0}</td><td class="n">${r.etsy || 0}</td>
      <td class="err">${esc((r.errors || []).join(" · ") || (r.note || ""))}</td></tr>`).join("")
      || '<tr><td colspan="6" class="empty">Inga körningar ännu.</td></tr>';

    document.querySelectorAll(".card img").forEach((img) => img.addEventListener("click", () => {
      const el = img.closest(".card");
      const it = items.find((i) => i.slug === el.dataset.slug);
      if (!it) return;
      $("#dlg-img").src = it.thumb; $("#dlg-img").alt = it.name;
      $("#dlg-txt").textContent = it.title;
      $("#dlg").showModal();
    }));
    $("#dlg").addEventListener("click", () => $("#dlg").close());
  }

  Promise.all([
    fetch("data/status.json?ts=" + Date.now(), { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }),
    A ? A.load() : Promise.resolve(null),
  ])
    .then(([s]) => render(s))
    .catch((e) => { $("#pulse").textContent = "Kunde inte läsa status.json: " + e.message; $("#today").innerHTML = '<div class="empty">Ingen status ännu.</div>'; });
})();

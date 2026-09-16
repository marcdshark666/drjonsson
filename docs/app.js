/* DrJonsson dashboard – läser data/status.json som pipelinen skriver varje morgon. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (iso) => iso ? iso.replace("T", " ").slice(0, 16) : "–";

  function chips(it) {
    const p = it.printify || {};
    const c = [];
    c.push('<span class="chip ok">genererad</span>');
    if (p.popup_published) c.push('<span class="chip ok">pop-up ' + (p.popup_count || 'live') + '</span>');
    else if (p.popup_product) c.push('<span class="chip">pop-up utkast</span>');
    else c.push('<span class="chip">pop-up väntar</span>');
    if (p.etsy_published) c.push('<span class="chip ok">etsy ' + (p.etsy_count || 'live') + '</span>');
    else if (p.etsy_product) c.push('<span class="chip">etsy utkast</span>');
    else c.push('<span class="chip">etsy väntar</span>');
    return c.join("");
  }

  function card(it) {
    return `<div class="card" data-slug="${esc(it.slug)}">
      <img src="${esc(it.thumb)}" alt="${esc(it.name)}" loading="lazy">
      <div class="b"><div class="n">${esc(it.name)}</div><div class="p">${esc(it.date)}</div><div class="chips">${chips(it)}</div></div>
    </div>`;
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

    const tiles = [
      [st.generated || 0, "motiv totalt"],
      [st.popup_live || 0, "live i pop-up"],
      [st.etsy_live || 0, "live på etsy"],
      [st.days || 0, "dagar"],
      [st.streak || 0, "dagar i rad"],
    ];
    $("#tiles").innerHTML = tiles.map(([v, l]) => `<div class="tile"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");

    const items = (s.items || []).slice().sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
    const today = items.length ? items.filter((i) => i.date === items[0].date) : [];
    $("#today-date").textContent = today.length ? today[0].date : "";
    $("#today").innerHTML = today.length ? today.map(card).join("") : '<div class="empty">Inga motiv ännu. Första körningen pågår eller väntar på 07:30.</div>';
    $("#all").innerHTML = items.map(card).join("");
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

    document.querySelectorAll(".card").forEach((el) => el.addEventListener("click", () => {
      const it = items.find((i) => i.slug === el.dataset.slug);
      if (!it) return;
      $("#dlg-img").src = it.thumb; $("#dlg-img").alt = it.name;
      $("#dlg-txt").textContent = it.title;
      $("#dlg").showModal();
    }));
    $("#dlg").addEventListener("click", () => $("#dlg").close());
  }

  fetch("data/status.json?ts=" + Date.now(), { cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(render)
    .catch((e) => { $("#pulse").textContent = "Kunde inte läsa status.json: " + e.message; $("#today").innerHTML = '<div class="empty">Ingen status ännu.</div>'; });
})();

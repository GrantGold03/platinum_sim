// Platinum Team Optimizer page (T068). Plain JS, no framework. API: contracts/http-api.md.
(function () {
  "use strict";

  const POLL_MS = 2000;
  const SEARCH_DEBOUNCE_MS = 150;
  const LAST_JOB_KEY = "platsim:lastJob";

  const $ = (id) => document.getElementById(id);
  const els = {
    search: $("search"), showExcluded: $("show-excluded"), status: $("search-status"), results: $("results"),
    slots: $("slots"), count: $("team-count"), form: $("opt-form"), minClear: $("min-clear"), seed: $("seed"),
    optimize: $("optimize"), formError: $("form-error"), progCard: $("progress-card"), progress: $("progress"),
    jobError: $("job-error"), resCard: $("result-card"), summary: $("summary"), downloads: $("downloads"),
    table: $("result-table"), allowEgg: $("allow-egg-moves"), allowTrade: $("allow-trade-evolutions"),
  };

  const team = []; // [{key, name, types}]
  let searchSeq = 0;
  let pollTimer = null;
  let searchTimer = null;

  function el(tag, attrs, ...children) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children) if (c !== null && c !== undefined) n.append(c);
    return n;
  }

  function store(key, value) {
    try { if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value); } catch (_) { /* optional */ }
  }
  function load(key) {
    try { return localStorage.getItem(key); } catch (_) { return null; }
  }

  // ---- search ------------------------------------------------------------------------------
  async function runSearch() {
    const seq = ++searchSeq;
    const q = els.search.value.trim();
    const excluded = els.showExcluded.checked ? 1 : 0;
    const trade = els.allowTrade.checked ? 1 : 0;
    let res;
    try {
      res = await fetch(`/api/species?q=${encodeURIComponent(q)}&excluded=${excluded}&trade_evolutions=${trade}`);
    } catch (e) {
      if (seq === searchSeq) els.status.textContent = "Cannot reach the server.";
      return;
    }
    if (seq !== searchSeq) return;
    if (res.status === 503) {
      els.status.textContent = "Loading species data (first start takes about a minute)…";
      clearTimeout(searchTimer);
      searchTimer = setTimeout(runSearch, POLL_MS);
      return;
    }
    if (!res.ok) {
      els.status.textContent = `Search failed (${res.status}).`;
      return;
    }
    renderResults(await res.json(), q);
  }

  function renderResults(list, q) {
    els.results.replaceChildren();
    if (!list.length) {
      els.status.textContent = q ? `No species match “${q}”.` : "No species.";
      return;
    }
    const nAvail = list.filter((s) => s.available).length;
    els.status.textContent = `${list.length} shown` + (els.showExcluded.checked ? ` (${nAvail} available)` : "") +
      (list.length >= 25 ? " — type more to narrow" : "");
    for (const s of list) {
      const label = s.available ? `Add ${s.name} to the team` : `${s.name}: excluded, ${s.reason}`;
      const btn = el("button", { type: "button", "aria-label": label, disabled: !s.available || team.length >= 6,
        onclick: () => addMember(s) },
        el("span", { class: "name", text: s.name }),
        el("span", { class: "types", text: s.types.join(" / ") }),
        s.available ? null : el("span", { class: "reason", text: s.reason }),
        s.available && s.note ? el("span", { class: "note", text: s.note }) : null);
      els.results.append(el("li", { class: s.available ? "" : "excluded" }, btn));
    }
  }

  // ---- team --------------------------------------------------------------------------------
  function addMember(s) {
    if (team.length >= 6 || !s.available) return;
    team.push({ key: s.key, name: s.name, types: s.types });
    renderTeam();
    for (const b of els.results.querySelectorAll("li:not(.excluded) button")) b.disabled = team.length >= 6;
  }

  function removeMember(i) {
    team.splice(i, 1);
    renderTeam();
    for (const b of els.results.querySelectorAll("li:not(.excluded) button")) b.disabled = team.length >= 6;
  }

  function renderTeam() {
    els.slots.replaceChildren();
    for (let i = 0; i < 6; i++) {
      const m = team[i];
      if (m) {
        els.slots.append(el("li", {},
          el("span", { class: "slot-name", title: m.name }, el("span", { class: "slot-num", text: `${i + 1}.` }), m.name),
          el("button", { type: "button", "aria-label": `Remove ${m.name} from slot ${i + 1}`, text: "Remove",
            onclick: () => removeMember(i) })));
      } else {
        els.slots.append(el("li", { class: "empty" },
          el("span", { class: "slot-name" }, el("span", { class: "slot-num", text: `${i + 1}.` }), "Empty")));
      }
    }
    els.count.textContent = `(${team.length}/6)`;
    els.optimize.disabled = team.length !== 6;
  }

  // ---- submit ------------------------------------------------------------------------------
  function showError(box, message, reasons) {
    box.replaceChildren(document.createTextNode(message));
    const entries = Object.entries(reasons || {});
    if (entries.length) {
      const ul = el("ul");
      for (const [k, v] of entries) ul.append(el("li", { text: `${k}: ${v}` }));
      box.append(ul);
    }
    box.hidden = false;
  }

  async function submit(ev) {
    ev.preventDefault();
    els.formError.hidden = true;
    const pct = Number(els.minClear.value);
    if (!Number.isFinite(pct) || pct <= 0 || pct > 100) {
      showError(els.formError, "Minimum clear rate must be between 1 and 100%.");
      els.minClear.focus();
      return;
    }
    if (team.length !== 6) {
      showError(els.formError, "Choose exactly six species.");
      return;
    }
    els.optimize.disabled = true;
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ species: team.map((m) => m.key), min_clear: pct / 100, seed: els.seed.value.trim() || "default",
          allow_egg_moves: els.allowEgg.checked, allow_trade_evolutions: els.allowTrade.checked }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.status !== 201) {
        showError(els.formError, typeof body.detail === "string" ? body.detail : `Request failed (${res.status}).`, body.reasons);
        return;
      }
      store(LAST_JOB_KEY, body.id);
      startPolling(body.id);
    } catch (e) {
      showError(els.formError, "Cannot reach the server.");
    } finally {
      els.optimize.disabled = team.length !== 6;
    }
  }

  // ---- progress / result -------------------------------------------------------------------
  function startPolling(id) {
    clearTimeout(pollTimer);
    els.progCard.hidden = false;
    els.resCard.hidden = true;
    els.jobError.hidden = true;
    poll(id);
  }

  async function poll(id) {
    let job;
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(id)}`);
      if (res.status === 404) { store(LAST_JOB_KEY, null); els.progCard.hidden = true; return; }
      if (!res.ok) throw new Error(String(res.status));
      job = await res.json();
    } catch (e) {
      pollTimer = setTimeout(() => poll(id), POLL_MS);
      return;
    }
    renderProgress(job);
    if (job.status === "queued" || job.status === "running") {
      pollTimer = setTimeout(() => poll(id), POLL_MS);
    } else if (job.status === "done") {
      renderResult(job);
    } else if (job.status === "failed") {
      showError(els.jobError, `Job failed: ${job.error || "unknown error"}`, job.invalid_reasons);
    }
  }

  function fmtPct(x) { return typeof x === "number" ? `${(x * 100).toFixed(1)}%` : "—"; }
  function fmtCI(ci) { return Array.isArray(ci) ? `${fmtPct(ci[0])}–${fmtPct(ci[1])}` : ""; }

  function kv(dl, pairs) {
    dl.replaceChildren();
    for (const [k, v] of pairs) {
      if (v === null || v === undefined || v === "") continue;
      dl.append(el("dt", { text: k }), el("dd", {}, v));
    }
  }

  function bestText(best) {
    if (!best || typeof best !== "object") return null;
    return Object.entries(best).map(([k, v]) => {
      if (typeof v === "number" && v > 0 && v <= 1 && /rate|clear/i.test(k)) return `${k}: ${fmtPct(v)}`;
      if (Array.isArray(v)) return `${k}: ${v.map((x) => (typeof x === "object" ? JSON.stringify(x) : x)).join(", ")}`;
      if (v && typeof v === "object") return `${k}: ${JSON.stringify(v)}`;
      return `${k}: ${v}`;
    }).join(" · ");
  }

  function renderProgress(job) {
    const p = job.progress || {};
    const runs = p.runs_planned ? `${p.runs_done} / ${p.runs_planned}` : String(p.runs_done ?? 0);
    const status = el("span", { class: `badge ${job.status === "done" ? "ok" : job.status === "failed" ? "bad" : "warn"}`, text: job.status });
    kv(els.progress, [
      ["Job", job.id],
      ["Status", status],
      ["Queue position", job.queue_position ? String(job.queue_position) : null],
      ["Stage", p.stage],
      ["Runs done", runs],
      ["Detail", p.detail],
      ["Best so far", bestText(p.best_so_far)],
      ["Species", (job.species || []).join(", ")],
      ["Options", job.options ? `min clear ${fmtPct(job.options.min_clear)}, seed “${job.options.seed}”, budget ${job.options.budget}` +
        `, egg moves ${job.options.allow_egg_moves ? "allowed" : "off"}, trade evolutions ${job.options.allow_trade_evolutions ? "allowed" : "off"}` : null],
    ]);
  }

  function renderResult(job) {
    els.resCard.hidden = false;
    const s = job.summary || {};
    const badge = s.qualified ? el("span", { class: "badge ok", text: "qualified" })
      : s.borderline ? el("span", { class: "badge warn", text: "borderline" })
      : el("span", { class: "badge bad", text: s.no_qualifying ? "no qualifying team" : "not qualified" });
    const dl = el("dl", { class: "kv" });
    kv(dl, [
      ["Verdict", badge],
      ["Clear rate", s.clear_rate !== undefined ? `${fmtPct(s.clear_rate)} (95% CI ${fmtCI(s.clear_ci95)}), ${s.n_runs} runs` : null],
      ["Cynthia win rate", typeof s.champion_rate === "number" ? `${fmtPct(s.champion_rate)} (95% CI ${fmtCI(s.champion_ci95)})` : null],
      ["Expected avg final level", typeof s.expected_avg_final_level === "number" ? s.expected_avg_final_level.toFixed(2) : null],
      ["Final level gap", typeof s.final_level_gap_max === "number" ? s.final_level_gap_max.toFixed(1) : null],
      ["Threshold", typeof s.threshold === "number" ? fmtPct(s.threshold) : null],
      ["Budget", s.budget_preset],
      ["Legality options", s.legality_options ? `egg moves ${s.legality_options.allow_egg_moves ? "allowed" : "off"}, trade evolutions ${s.legality_options.allow_trade_evolutions ? "allowed" : "off"}` : null],
      ["Policies", s.player_policy ? `player ${s.player_policy}; opponent ${s.opponent_policy}` : null],
      ["Objective", s.objective],
      ["Commits", s.decomp_commit ? `decomp ${String(s.decomp_commit).slice(0, 10)}, Showdown ${String(s.showdown_commit).slice(0, 10)}, ledger ${s.divergence_ledger_version}` : null],
    ]);
    els.summary.replaceChildren(dl);
    if (Array.isArray(s.warnings) && s.warnings.length) {
      const ul = el("ul", { class: "warnings" });
      for (const w of s.warnings) ul.append(el("li", { text: w }));
      els.summary.append(ul);
    }

    els.downloads.replaceChildren();
    const labels = { "result.xlsx": "Spreadsheet (.xlsx)", "result.csv": "CSV", "result.json": "JSON report", "team.txt": "Showdown team (team.txt)" };
    for (const [name, href] of Object.entries(job.downloads || {})) {
      els.downloads.append(el("a", { href, download: name.endsWith(".json") || name.endsWith(".txt") ? null : `${job.id}-${name}`, text: labels[name] || name }));
    }

    const thead = els.table.tHead, tbody = els.table.tBodies[0];
    thead.replaceChildren(); tbody.replaceChildren();
    const t = job.table;
    if (!t) return;
    const hr = el("tr");
    for (const h of t.headers) hr.append(el("th", { scope: "col", text: h }));
    thead.append(hr);
    for (const row of t.rows) {
      const tr = el("tr");
      row.forEach((cell, i) => tr.append(el("td", { "data-label": t.headers[i] || "", text: cell })));
      tbody.append(tr);
    }
  }

  // ---- wire up -----------------------------------------------------------------------------
  els.search.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, SEARCH_DEBOUNCE_MS); });
  els.showExcluded.addEventListener("change", runSearch);
  els.allowTrade.addEventListener("change", runSearch); // availability depends on it (egg moves never do)
  els.form.addEventListener("submit", submit);
  renderTeam();
  runSearch();
  const last = load(LAST_JOB_KEY);
  if (last) startPolling(last);
})();

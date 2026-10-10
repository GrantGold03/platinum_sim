// Platinum Team Optimizer page (T068, redesigned in 002). Plain JS, no framework, no build step.
// API: specs/002-webui-redesign/contracts/http-api.md. Page behaviour: contracts/ui.md.
(function () {
  "use strict";

  const POLL_MS = 2000;
  const SEARCH_DEBOUNCE_MS = 150;
  const TRAINER_BATTLES = "battles";

  const $ = (id) => document.getElementById(id);
  const els = {
    search: $("search"), showExcluded: $("show-excluded"), status: $("search-status"), results: $("results"),
    slots: $("slots"), count: $("team-count"), form: $("opt-form"), minClear: $("min-clear"), seed: $("seed"),
    budget: $("budget"), optimize: $("optimize"), formError: $("form-error"),
    allowEgg: $("allow-egg-moves"), allowTrade: $("allow-trade-evolutions"),
    runStatus: $("run-status"), progCard: $("progress-card"), progress: $("progress"), queue: $("queue"),
    picker: $("run-picker"), noRuns: $("no-runs"), runMessage: $("run-message"), result: $("result"),
    summary: $("summary"), chartBody: $("chart-body"), chartTip: $("chart-tip"), cards: $("team-cards"),
    downloads: $("downloads"),
  };

  const team = []; // [{key, name, types, icon}]
  let searchSeq = 0;
  let searchTimer = null;
  let pollTimer = null;
  let tickTimer = null;
  let jobs = []; // last GET /api/jobs, newest first
  let shownJob = null; // id of the run in the result panel
  let newestDone = null; // newest done id seen so far (a new one switches the panel, FR-014)
  let tipSeq = 0;
  let pickerSig = "";

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

  function svg(tag, attrs, ...children) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) n.setAttribute(k, v);
    for (const c of children) if (c !== null && c !== undefined) n.append(c);
    return n;
  }

  // A focusable term with a tooltip shown on hover and keyboard focus.
  function withTip(content, tipText, cls) {
    const id = `tip-${++tipSeq}`;
    const term = el("span", { class: cls, tabindex: "0", "aria-describedby": id }, content);
    return el("span", { class: "tip-wrap" }, term, el("span", { class: "tip", id, role: "tooltip", text: tipText }));
  }

  // A sprite box showing the first frame; a failed load becomes a same-size placeholder.
  function sprite(src, kind) {
    const box = el("span", { class: kind === "icon" ? "sprite-icon" : "sprite-front" });
    if (!src) { box.classList.add("sprite-placeholder"); return box; }
    const img = el("img", { src, alt: "", loading: "lazy" });
    img.addEventListener("error", () => { img.remove(); box.classList.add("sprite-placeholder"); });
    box.append(img);
    return box;
  }

  function fmtPct(x) { return typeof x === "number" ? `${(x * 100).toFixed(1)}%` : "—"; }
  function fmtCount(n) { return typeof n === "number" ? n.toLocaleString() : "?"; }
  function fmtGap(g) { return Number.isInteger(g) ? String(g) : g.toFixed(1); }
  function fmtLocal(iso) {
    const d = iso ? new Date(iso) : null;
    if (!d || Number.isNaN(d.getTime())) return "";
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }
  function fmtElapsed(s) {
    s = Math.max(0, Math.floor(s));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  function announce(text) { els.runStatus.textContent = text; }

  // ---- search (FR-003: no list until the player types) -------------------------------------
  function scheduleSearch() { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, SEARCH_DEBOUNCE_MS); }

  async function runSearch() {
    const seq = ++searchSeq;
    const q = els.search.value.trim();
    if (!q) {
      els.results.hidden = true;
      els.results.replaceChildren();
      els.status.textContent = "";
      return;
    }
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
    els.results.hidden = false;
    if (!list.length) {
      els.status.textContent = `No species match “${q}”.`;
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

  // ---- team (FR-004, FR-007) ---------------------------------------------------------------
  function addMember(s) {
    if (team.length >= 6 || !s.available) return;
    team.push({ key: s.key, name: s.name, types: s.types, icon: s.sprite_icon || `/api/sprites/${s.key}/icon.png` });
    renderTeam();
  }

  function removeMember(i) {
    team.splice(i, 1);
    renderTeam();
  }

  function renderTeam() {
    els.slots.replaceChildren();
    for (let i = 0; i < 6; i++) {
      const m = team[i];
      if (m) {
        els.slots.append(el("li", {},
          el("span", { class: "slot-name", title: m.name }, el("span", { class: "slot-num", text: `${i + 1}.` }),
            sprite(m.icon, "icon"), el("span", { class: "slot-label", text: m.name })),
          el("button", { type: "button", "aria-label": `Remove ${m.name} from slot ${i + 1}`, text: "Remove",
            onclick: () => removeMember(i) })));
      } else {
        els.slots.append(el("li", { class: "empty" },
          el("span", { class: "slot-name" }, el("span", { class: "slot-num", text: `${i + 1}.` }), "Empty")));
      }
    }
    els.count.textContent = `(${team.length}/6)`;
    els.optimize.disabled = team.length !== 6;
    for (const b of els.results.querySelectorAll("li:not(.excluded) button")) b.disabled = team.length >= 6;
  }

  // ---- submit (FR-005) ---------------------------------------------------------------------
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
        body: JSON.stringify({ species: team.map((m) => m.key), min_clear: pct / 100,
          seed: els.seed.value.trim() || "default", budget: els.budget.value,
          allow_egg_moves: els.allowEgg.checked, allow_trade_evolutions: els.allowTrade.checked }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.status !== 201) {
        showError(els.formError, typeof body.detail === "string" ? body.detail : `Request failed (${res.status}).`, body.reasons);
        return;
      }
      announce("Run queued.");
      refreshJobs();
    } catch (e) {
      showError(els.formError, "Cannot reach the server.");
    } finally {
      els.optimize.disabled = team.length !== 6;
    }
  }

  // ---- jobs list, progress, cancel (FR-008 to FR-012) --------------------------------------
  function speciesText(job) { return (job.species || []).join(", "); }
  function jobLabel(job) { return job.label || `${speciesText(job)} · ${job.verdict || job.status}`; }

  async function refreshJobs() {
    clearTimeout(pollTimer);
    try {
      const res = await fetch("/api/jobs");
      if (res.ok) {
        const prev = new Map(jobs.map((j) => [j.id, j.status]));
        jobs = await res.json();
        for (const j of jobs) {
          const was = prev.get(j.id);
          if (!was || was === j.status) continue;
          if (j.status === "cancelled") announce("Run cancelled");
          else if (j.status === "running") announce("Run started.");
          else if (j.status === "done") announce(`Run finished: ${jobLabel(j)}`);
          else if (j.status === "failed") announce(`Run failed: ${j.error || "see the run for details"}`);
        }
        renderProgress();
        renderPicker();
      }
    } catch (_) { /* server unreachable; retry */ }
    pollTimer = setTimeout(refreshJobs, POLL_MS);
  }

  function renderProgress() {
    const running = jobs.find((j) => j.status === "running");
    const queued = jobs.filter((j) => j.status === "queued").sort((a, b) => (a.queue_position || 0) - (b.queue_position || 0));
    els.progCard.hidden = !running && !queued.length;
    els.progress.replaceChildren();
    els.queue.replaceChildren();
    clearInterval(tickTimer);
    if (els.progCard.hidden) return;

    const head = running || queued[0];
    const p = head.progress || {};
    const elapsed = el("span", { class: "elapsed" });
    const started = head.started ? Date.parse(head.started) : null;
    const tick = () => { elapsed.textContent = started ? `elapsed ${fmtElapsed((Date.now() - started) / 1000)}` : "waiting to start"; };
    tick();
    if (started) tickTimer = setInterval(tick, 1000);
    const eta = !running ? null : typeof head.eta_s === "number"
      ? `about ${Math.max(1, Math.ceil(head.eta_s / 60))} min left` : "estimating…";
    const runs = p.runs_planned ? `${fmtCount(p.runs_done)} / ${fmtCount(p.runs_planned)} runs` : null;
    els.progress.append(
      el("p", { class: "prog-line" },
        el("strong", { text: running ? "Running" : "Waiting to start" }),
        el("span", { class: "q-text", text: speciesText(head) })),
      el("p", { class: "prog-line" },
        el("span", { class: "stage", text: `Stage: ${running ? (p.stage || "starting") : "queued"}` }),
        runs ? el("span", { text: runs }) : null,
        elapsed,
        eta ? el("span", { class: "eta", text: eta }) : null,
        cancelButton(head)));
    for (const q of queued) {
      if (q === head) continue;
      els.queue.append(el("li", {},
        el("span", { class: "q-text", text: `position ${q.queue_position} · ${speciesText(q)}` }),
        cancelButton(q)));
    }
  }

  function cancelButton(job) {
    const btn = el("button", { type: "button", class: "danger", text: "Cancel",
      "aria-label": `Cancel the run of ${speciesText(job)}` });
    btn.addEventListener("click", async () => {
      if (!window.confirm("Cancel this run? Progress so far will be discarded.")) return;
      btn.disabled = true;
      try {
        const res = await fetch(`/api/jobs/${encodeURIComponent(job.id)}/cancel`, { method: "POST" });
        if (res.status === 200) announce("Run cancelled");
        else if (res.status === 202) announce("Cancelling…");
        else { btn.disabled = false; announce(`Could not cancel (${res.status}).`); }
      } catch (_) {
        btn.disabled = false;
        announce("Cannot reach the server.");
      }
      refreshJobs();
    });
    return btn;
  }

  // ---- run picker (FR-014 to FR-016) -------------------------------------------------------
  function renderPicker() {
    const listed = jobs.filter((j) => j.status !== "queued" && j.status !== "running");
    const doneIds = listed.filter((j) => j.status === "done").map((j) => j.id);
    const latestDone = doneIds[0] || null;
    els.noRuns.hidden = listed.length > 0;
    const prevValue = els.picker.value;
    const sig = listed.map((j) => `${j.id}:${j.status}:${j.label || ""}`).join("|");
    if (sig !== pickerSig) { // rebuild only on change, so an open dropdown isn't reset every poll
      pickerSig = sig;
      els.picker.replaceChildren(...listed.map((j) =>
        el("option", { value: j.id, text: `${fmtLocal(j.created)} · ${jobLabel(j)}` })));
    }
    els.picker.disabled = !listed.length;
    // Newest done run on load, and again whenever a newer run finishes (no remembered pick, N6).
    let target = shownJob && listed.some((j) => j.id === shownJob) ? shownJob : latestDone;
    if (latestDone && latestDone !== newestDone) target = latestDone;
    newestDone = latestDone;
    if (!target && listed.length) target = listed[0].id;
    if (target) els.picker.value = target;
    if (target && (target !== shownJob || prevValue !== target)) showRun(target);
    if (!target) { els.result.hidden = true; els.runMessage.hidden = true; shownJob = null; }
  }

  async function showRun(id) {
    shownJob = id;
    let job;
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(id)}`);
      if (!res.ok) throw new Error(String(res.status));
      job = await res.json();
    } catch (_) {
      return;
    }
    if (shownJob !== id) return;
    if (job.status === "done" && job.summary) {
      els.runMessage.hidden = true;
      renderResult(job);
    } else {
      els.result.hidden = true;
      showError(els.runMessage, `Status: ${job.status}${job.error ? ` — ${job.error}` : ""}`, job.invalid_reasons);
    }
  }

  // ---- result (FR-017 to FR-027) -----------------------------------------------------------
  function kv(dl, pairs) {
    dl.replaceChildren();
    for (const [k, v] of pairs) {
      if (v === null || v === undefined || v === "") continue;
      dl.append(el("dt", { text: k }), el("dd", {}, v));
    }
  }

  function renderResult(job) {
    els.result.hidden = false;
    const s = job.summary || {};
    const badge = s.verdict === "qualified" ? el("span", { class: "badge ok", text: "qualified" })
      : s.verdict === "borderline" ? el("span", { class: "badge warn", text: "borderline" })
      : el("span", { class: "badge bad", text: s.no_qualifying ? "no qualifying team" : "not qualified" });
    const ci = Array.isArray(s.clear_ci95) ? s.clear_ci95 : null;
    const clearTip = ci ? `95% interval ${fmtPct(ci[0]).slice(0, -1)}–${fmtPct(ci[1])} · ${fmtCount(s.n_runs)} runs`
      : `${fmtCount(s.n_runs)} runs`;
    const lo = s.legality_options;
    const dl = el("dl", { class: "kv" });
    kv(dl, [
      ["Verdict", badge],
      ["Clear rate", typeof s.clear_rate === "number" ? withTip(fmtPct(s.clear_rate), clearTip, "clear-rate") : null],
      ["Final level", typeof s.avg_final_level === "number"
        ? `${s.avg_final_level.toFixed(2)} (level gap of ${typeof s.level_gap === "number" ? fmtGap(s.level_gap) : "?"})` : null],
      ["Threshold", typeof s.threshold === "number" ? fmtPct(s.threshold) : null],
      ["Budget", s.budget],
      ["Legality options", lo ? `egg moves ${lo.allow_egg_moves ? "allowed" : "off"}, trade evolutions ${lo.allow_trade_evolutions ? "allowed" : "off"}` : null],
      ["Version", s.platsim_version ? `platsim ${s.platsim_version}` : "platsim version not recorded"],
    ]);
    els.summary.replaceChildren(dl);
    if (Array.isArray(s.warnings) && s.warnings.length) {
      const ul = el("ul", { class: "warnings" });
      for (const w of s.warnings) ul.append(el("li", { text: w }));
      els.summary.append(ul);
    }
    renderChart(job.per_trainer || [], s.threshold);
    renderCards(job.team || []);

    els.downloads.replaceChildren();
    const labels = { "result.xlsx": "Spreadsheet (.xlsx)", "result.csv": "CSV", "result.json": "JSON report", "team.txt": "Showdown team (team.txt)" };
    for (const [name, href] of Object.entries(job.downloads || {})) {
      els.downloads.append(el("a", { href, download: name.endsWith(".json") || name.endsWith(".txt") ? null : `${job.id}-${name}`, text: labels[name] || name }));
    }
  }

  function renderChart(rows, threshold) {
    els.chartBody.replaceChildren();
    els.chartTip.hidden = true;
    if (!rows.length) {
      els.chartBody.append(el("p", { class: "muted", text: "Per-trainer data is not available for this run" }));
      return;
    }
    const W = 520, labelW = 70, valueW = 56, barH = 18, gap = 10, top = 4;
    const plotW = W - labelW - valueW;
    const H = top + rows.length * (barH + gap) + 18;
    const x = (v) => labelW + Math.max(0, Math.min(1, v)) * plotW;
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "group", "aria-label": "Clear rate by trainer" });
    rows.forEach((r, i) => {
      const y = top + i * (barH + gap);
      const ci = Array.isArray(r.ci95) ? r.ci95 : null;
      const text = `${r.label} ${fmtPct(r.rate)}` + (ci ? `, 95% interval ${fmtPct(ci[0]).slice(0, -1)}–${fmtPct(ci[1])}` : "") +
        `, ${fmtCount(r.battles)} ${TRAINER_BATTLES}`;
      const g = svg("g", { class: "bar-group", tabindex: "0", role: "img", "aria-label": text },
        svg("title", {}, text),
        svg("text", { x: 0, y: y + barH - 4 }, r.label),
        svg("rect", { class: "track", x: labelW, y, width: plotW, height: barH, rx: 3 }),
        svg("rect", { class: "bar", x: labelW, y, width: Math.max(0, x(r.rate || 0) - labelW), height: barH, rx: 3 }),
        ci ? svg("line", { class: "whisker", x1: x(ci[0]), x2: x(ci[1]), y1: y + barH / 2, y2: y + barH / 2 }) : null,
        ci ? svg("line", { class: "whisker", x1: x(ci[0]), x2: x(ci[0]), y1: y + 4, y2: y + barH - 4 }) : null,
        ci ? svg("line", { class: "whisker", x1: x(ci[1]), x2: x(ci[1]), y1: y + 4, y2: y + barH - 4 }) : null,
        svg("text", { x: W - valueW + 6, y: y + barH - 4 }, fmtPct(r.rate)));
      const show = () => {
        els.chartTip.textContent = text;
        els.chartTip.hidden = false;
        els.chartTip.style.left = `${(labelW / W) * 100}%`;
        els.chartTip.style.top = `${((y + barH + 22) / H) * 100}%`;
      };
      const hide = () => { els.chartTip.hidden = true; };
      g.addEventListener("mouseenter", show);
      g.addEventListener("focus", show);
      g.addEventListener("mouseleave", hide);
      g.addEventListener("blur", hide);
      root.append(g);
    });
    if (typeof threshold === "number") {
      const yEnd = top + rows.length * (barH + gap) - gap;
      root.append(svg("line", { class: "threshold", x1: x(threshold), x2: x(threshold), y1: 0, y2: yEnd }));
      root.append(svg("g", { class: "axis" }, svg("text", { x: x(threshold) - 20, y: H - 2 }, `threshold ${fmtPct(threshold)}`)));
    }
    els.chartBody.append(root);
    // Screen-reader copy of the numbers.
    const table = el("table", { class: "sr-only" },
      el("caption", { text: "Clear rate by trainer" }),
      el("tr", {}, el("th", { text: "Trainer" }), el("th", { text: "Clear rate" }), el("th", { text: "95% interval" }), el("th", { text: "Battles" })));
    for (const r of rows) {
      table.append(el("tr", {}, el("td", { text: r.label }), el("td", { text: fmtPct(r.rate) }),
        el("td", { text: Array.isArray(r.ci95) ? `${fmtPct(r.ci95[0])}–${fmtPct(r.ci95[1])}` : "" }),
        el("td", { text: fmtCount(r.battles) })));
    }
    els.chartBody.append(table);
  }

  function renderCards(members) {
    els.cards.replaceChildren();
    for (const m of members) {
      const moves = el("div", { class: "field moves" });
      for (const mv of m.moves || []) moves.append(withTip(mv.name, mv.source || "source unknown", "move"));
      els.cards.append(el("article", { class: "mon", "aria-label": m.species },
        el("span", { class: "field slot", text: `Slot ${m.slot}` }),
        el("span", { class: "field sprite" }, sprite(m.sprite, "front")),
        el("span", { class: "field species", text: m.species }),
        el("span", { class: "field levels", text: `Lv ${m.start_level} → ${m.final_level}` }),
        el("span", { class: "field ability" }, el("span", { class: "label", text: "Ability: " }), m.ability || "—"),
        el("span", { class: "field item" }, el("span", { class: "label", text: "Item: " }), m.held_item || "none"),
        el("span", { class: "field obtained", text: m.obtained_from || "" }),
        moves));
    }
  }

  // ---- wire up -----------------------------------------------------------------------------
  els.search.addEventListener("input", scheduleSearch);
  els.showExcluded.addEventListener("change", runSearch);
  els.allowTrade.addEventListener("change", runSearch); // availability depends on it (egg moves never do)
  els.form.addEventListener("submit", submit);
  els.picker.addEventListener("change", () => showRun(els.picker.value));
  renderTeam();
  refreshJobs();
})();

"use strict";
// Pay of AI-training / data-annotation jobs: one box plot (pay in US$ on the y axis, per hour or per task /
// project, any grouping on the x axis, dots colored by any grouping) above a table, both driven by the same filters.
// Data: data/jobs.json, built by `python3 -m annotationjobs.site`.

(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const fmtInt = d3.format(",");
  const money = (v) => (v == null ? "" : v >= 1000 ? "$" + fmtInt(Math.round(v)) : Number.isInteger(v) ? "$" + v : "$" + v.toFixed(2));
  const debounce = (f, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => f(...a), ms); }; };

  const MIN_BOX = 5; // fewer jobs than this: dots only, no box
  const ACCENT = "#2563eb";
  const OTHER = "#b8bfca";
  // 12 colors, most distinct first (the largest groups get the first ones); grey is kept for the rest
  const PALETTE = ["#4269d0", "#efb118", "#ff725c", "#6cc5b0", "#3ca951", "#ff8ab7", "#a463f2", "#97bbf5", "#9c6b4e",
    "#1d2b53", "#8a8f1c", "#7a1f3d"];
  const RAMP = d3.interpolateRgbBasis(["#f2b134", "#e4572e", "#b8336a", "#5b2a86", "#16324f"]);
  const NEUTRAL = new Set(["Not stated", "None mentioned", "Nothing about pay", "No pay figure", "Amount, unit not stated", "Not said"]);
  const FILTER_ORDER = ["field", "site", "kind", "degree", "years", "mode", "who", "contract", "unit", "pay", "dep", "cur"];
  // pay basis: one at a time, a per-hour and a per-task figure do not belong on the same axis
  const BASES = {
    hour: { label: "Per hour", unit: "/hr", axis: "Top of hourly rate (US$)", title: "Hourly pay", color: "pay",
      sub: "Top of each job's hourly rate in US$ (salaries at 40 hours a week, other currencies converted)" },
    piece: { label: "Per task or project", unit: "", axis: "Top of pay per task, project or session (US$)", title: "Pay per task or project",
      color: "unit", sub: "Top of each job's pay per task, project or session in US$ (other currencies converted)" },
    none: { label: "No pay figure", unit: "", axis: "", title: "Jobs with no pay figure", color: "pay", sub: "" },
  };
  const yv = (j) => (S.basis === "hour" ? j.h : S.basis === "piece" ? j.pt : null);
  const basisOf = (j) => (j.h != null ? "hour" : j.pt != null ? "piece" : "none");
  const SHORT = { "United States": "US", "United Kingdom": "UK", "United Arab Emirates": "UAE" };
  const SYM = { USD: "$", EUR: "€", GBP: "£", CAD: "CA$", AUD: "A$", INR: "₹", PHP: "₱" };
  const UNIT = { hour: "/hr", year: "/year", month: "/month", project: " per project", task: " per task", session: " per session" };
  const DEFAULTS = { basis: "hour", x: "field", color: "pay", sort: "auto", scale: "log" };

  let DIMS, DI, JOBS, SNAPSHOT, POSTINGS, COUNTRIES, FXDATE, LOGOS;
  const LOGO = 16, LOGO_GAP = 5; // logo size and the space after it, in px
  // small logo of a site, shown before its name (decorative: the name follows, so no alt text)
  const logoSrc = (key, value) => (key === "site" && LOGOS[value]) || null;
  const logoImg = (key, value) => {
    const src = logoSrc(key, value);
    return src ? `<img class="logo" src="${esc(src)}" alt="" width="${LOGO}" height="${LOGO}" decoding="async" onerror="this.remove()">` : "";
  };
  const PAGE = 10; // table rows shown at first, and added by "Show more"
  let filtered = [];
  let tableRows = [];
  const S = {
    ...DEFAULTS, f: {}, q: "", live: "", unclear: true, min: null, max: null,
    hl: new Set(), legendMode: "hide", // highlighted values of the color grouping; what a click on the legend does
    ts: "h", td: -1, limit: PAGE, sel: null, open: new Set(),
  };

  // ---------------------------------------------------------------- data

  fetch("data/jobs.json").then((r) => r.json()).then(init).catch((e) => {
    $("#chart-sub").textContent = "Could not load the data: " + e;
  });

  function init(data) {
    DIMS = data.dims;
    DI = Object.fromEntries(DIMS.map((d, i) => [d.key, i]));
    JOBS = data.jobs;
    SNAPSHOT = data.snapshot;
    POSTINGS = data.postings;
    FXDATE = data.fx && data.fx.date;
    LOGOS = data.logos || {};
    for (const j of JOBS) j.text = [j.t, j.co, j.s, ...j.loc, ...j.pl].join(" ").toLowerCase();
    const cc = new Map();
    for (const j of JOBS) if (j.w !== "except") for (const p of j.pl) cc.set(p, (cc.get(p) || 0) + 1);
    COUNTRIES = [...cc].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([c]) => c);

    $("#x").innerHTML = DIMS.map((d) => `<option value="${d.key}">${esc(d.label)}</option>`).join("");
    $("#color").innerHTML = `<option value="">Nothing (one color)</option>` +
      DIMS.map((d) => `<option value="${d.key}">${esc(d.label)}</option>`).join("");
    readHash();
    buildFilterButtons();
    bindControls();
    const sites = new Set(JOBS.map((j) => j.s)).size;
    const nh = JOBS.filter((j) => j.h != null).length, np = JOBS.filter((j) => j.pt != null).length;
    $("#lede").innerHTML = `<b>${fmtInt(JOBS.length)}</b> open jobs (${fmtInt(POSTINGS)} postings once each city's copy is counted) ` +
      `from <b>${sites}</b> sites: contributor platforms, data companies' own boards, AI labs and big tech. ` +
      `<b>${fmtInt(nh)}</b> give an hourly rate or a salary, <b>${fmtInt(np)}</b> a rate per task or project. Collected ${niceDate(SNAPSHOT)}.`;
    $("#foot").innerHTML = `Data collected ${niceDate(SNAPSHOT)} from the sites' public job pages. ` +
      (FXDATE ? `Other currencies converted to US$ at the European Central Bank rates of ${niceDate(FXDATE)}. ` : "") +
      `Code, method and full data: <a href="https://github.com/lillyguisnet/annotationjobs">github.com/lillyguisnet/annotationjobs</a>.`;
    let lastW = 0;
    new ResizeObserver(debounce(() => {
      const w = $("#chart-scroll").clientWidth;
      if (w !== lastW) { lastW = w; renderChart(); }
    }, 80)).observe($("#chart-scroll"));
    update();
  }

  function niceDate(s) {
    const d = new Date(s + "T00:00:00");
    return isNaN(d) ? s : d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  }

  const val = (j, key) => DIMS[DI[key]].values[j.c[DI[key]]];

  // ---------------------------------------------------------------- filters

  function openTo(j, c) {
    switch (j.w) {
      case "any": return true;
      case "except": return !j.pl.includes(c);
      case "only": return j.pl.includes(c);
      case "onsite": return j.pl.length ? j.pl.includes(c) : S.unclear;
      case "listed": return j.pl.includes(c) || S.unclear;
      default: return S.unclear;
    }
  }

  function passes(j, except) {
    if (except !== "basis" && basisOf(j) !== S.basis) return false;
    for (const k in S.f) {
      if (k === except) continue;
      if (!S.f[k].has(j.c[DI[k]])) return false;
    }
    if (S.q) for (const w of S.q.toLowerCase().split(/\s+/)) if (w && !j.text.includes(w)) return false;
    if (S.live && except !== "live" && !openTo(j, S.live)) return false;
    if (except !== "pay$" && (S.min != null || S.max != null)) {
      const v = yv(j);
      if (v == null || (S.min != null && v < S.min) || (S.max != null && v > S.max)) return false;
    }
    return true;
  }

  function setFilter(key, set) {
    if (!set || set.size === 0 || set.size === DIMS[DI[key]].values.length) delete S.f[key];
    else S.f[key] = set;
  }

  // ---------------------------------------------------------------- URL (shareable views)

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    for (const k of ["x", "color"]) {
      const v = p.get(k);
      if (v != null && (v in DI || (k === "color" && v === ""))) S[k] = v;
    }
    if (["auto", "median", "count", "natural"].includes(p.get("sort"))) S.sort = p.get("sort");
    if (["log", "linear"].includes(p.get("scale"))) S.scale = p.get("scale");
    S.basis = p.get("pay") in BASES ? p.get("pay") : DEFAULTS.basis;
    for (const d of DIMS) {
      const idx = (v) => v.split("|").map((x) => d.values.indexOf(x)).filter((i) => i >= 0);
      if (p.get("f." + d.key) != null) {
        const set = new Set(idx(p.get("f." + d.key)));
        if (set.size) setFilter(d.key, set);
      } else if (p.get("not." + d.key) != null) { // "all but": values added later stay in
        const out = new Set(idx(p.get("not." + d.key)));
        setFilter(d.key, new Set(d.values.map((_, i) => i).filter((i) => !out.has(i))));
      }
    }
    S.hl = new Set();
    if (S.color && p.get("hl") != null) {
      const vals = DIMS[DI[S.color]].values;
      for (const v of p.get("hl").split("|")) if (vals.includes(v)) S.hl.add(vals.indexOf(v));
    }
    if (S.hl.size) S.legendMode = "highlight";
    S.q = p.get("q") || "";
    S.live = COUNTRIES.includes(p.get("live")) ? p.get("live") : "";
    S.unclear = p.get("unclear") !== "0";
    const num = (s) => (s != null && s !== "" && isFinite(+s) ? +s : null);
    S.min = num(p.get("min"));
    S.max = num(p.get("max"));
    $("#q").value = S.q;
  }

  function writeHash() {
    const p = new URLSearchParams();
    if (S.basis !== DEFAULTS.basis) p.set("pay", S.basis);
    for (const k of ["x", "color", "sort", "scale"]) if (S[k] !== DEFAULTS[k]) p.set(k, S[k]);
    for (const k in S.f) {
      const vals = DIMS[DI[k]].values, on = S.f[k];
      if (on.size > vals.length / 2) p.set("not." + k, vals.filter((_, i) => !on.has(i)).join("|"));
      else p.set("f." + k, [...on].map((i) => vals[i]).join("|"));
    }
    if (S.color && S.hl.size) p.set("hl", [...S.hl].map((i) => DIMS[DI[S.color]].values[i]).join("|"));
    if (S.q) p.set("q", S.q);
    if (S.live) p.set("live", S.live);
    if (!S.unclear) p.set("unclear", "0");
    if (S.min != null) p.set("min", S.min);
    if (S.max != null) p.set("max", S.max);
    const h = p.toString();
    history.replaceState(null, "", h ? "#" + h : location.pathname + location.search);
  }

  // ---------------------------------------------------------------- controls

  function bindControls() {
    const x = $("#x"), color = $("#color"), sort = $("#sort");
    x.value = S.x; color.value = S.color; sort.value = S.sort;
    x.onchange = () => { S.x = x.value; update(); };
    color.onchange = () => { S.color = color.value; S.hl = new Set(); update(); };
    sort.onchange = () => { S.sort = sort.value; update(); };
    for (const b of document.querySelectorAll("#scale button")) {
      b.onclick = () => { S.scale = b.dataset.v; update(); };
    }
    $("#q").addEventListener("input", debounce((e) => { S.q = e.target.value.trim(); S.limit = PAGE; update(); }, 150));
    $("#csv").onclick = downloadCsv;
    document.addEventListener("pointerdown", (e) => {
      if (!$("#pop").hidden && !e.target.closest("#pop") && !e.target.closest(".fbtn")) closePop();
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePop(); });
    window.addEventListener("hashchange", () => { /* links pasted in the same tab */
      S.f = {}; readHash(); $("#x").value = S.x; $("#color").value = S.color; $("#sort").value = S.sort; update();
    });
  }

  // short names for the filter buttons (the popover shows the full name and what it means)
  const BTN = { live: "Open to people in", "pay$": "Pay range", field: "Field", site: "Site", kind: "Site type", who: "Who can apply",
    mode: "Work mode", degree: "Degree", years: "Experience", contract: "Job type", unit: "Paid per", pay: "Pay clarity", dep: "Rate set by", cur: "Currency" };
  const SMALL = matchMedia("(max-width: 720px)");

  function buildFilterButtons() {
    const zone = $("#zone-pay");
    const seg = document.createElement("div");
    seg.className = "seg basis";
    seg.id = "basis";
    seg.setAttribute("role", "radiogroup");
    seg.setAttribute("aria-label", "Pay basis");
    seg.innerHTML = Object.entries(BASES).map(([k, b]) =>
      `<button type="button" role="radio" data-v="${k}">${esc(b.label)}<span class="n"></span></button>`).join("");
    seg.querySelectorAll("button").forEach((b) => b.onclick = () => setBasis(b.dataset.v));
    zone.appendChild(seg);
    const mk = (id) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "fbtn"; b.dataset.f = id; b.setAttribute("aria-expanded", "false");
      b.onclick = () => ($("#pop").dataset.f === id && !$("#pop").hidden ? closePop() : openPop(id, b));
      return b;
    };
    const box = $("#filters");
    for (const id of ["live", "field", "site", "kind", "who", "mode", "degree", "years", "contract"]) box.appendChild(mk(id));
    // filters about pay sit with the pay switch (the range's unit follows it); on a phone they lead the scrolling filter row
    const payFilters = ["pay$", "unit", "pay", "dep", "cur"].map(mk);
    const payBox = document.createElement("div");
    payBox.className = "filters pay-filters";
    zone.appendChild(payBox);
    const place = () => (SMALL.matches ? box.prepend(...payFilters) : payBox.append(...payFilters));
    place();
    SMALL.addEventListener("change", () => { closePop(); place(); });
  }

  function refreshFilterButtons() {
    for (const b of document.querySelectorAll(".fbtn")) {
      const id = b.dataset.f;
      let on = false, label = BTN[id], badge = "";
      if (id === "live") { if (S.live) { on = true; label = "Open to people in " + S.live; } }
      else if (id === "pay$") {
        b.hidden = S.basis === "none";
        if (S.min != null || S.max != null) { on = true; label = rangeText() + BASES[S.basis].unit; }
      } else if (S.f[id]) {
        on = true;
        const t = filterText(id);
        if (t) label = `${BTN[id]}: ${t.length > 24 ? t.slice(0, 23) + "…" : t}`;
        else badge = S.f[id].size;
      }
      b.classList.toggle("on", on);
      b.title = on ? `${DIMS[DI[id]]?.label || BTN[id]}: click to change` : "";
      b.innerHTML = `<span class="l">${esc(label)}</span>${badge ? `<span class="badge">${badge}</span>` : ""}<span class="caret"></span>`;
    }
  }

  function setBasis(v) {
    if (v === S.basis) return;
    if (S.color === BASES[S.basis].color && S.color !== BASES[v].color) { // follow the suggested coloring unless it was changed
      S.color = BASES[v].color;
      S.hl = new Set();
    }
    $("#color").value = S.color;
    S.basis = v;
    S.min = S.max = null; // a per-hour limit means nothing per task
    S.limit = PAGE;
    update();
  }

  function refreshBasis() {
    const n = { hour: 0, piece: 0, none: 0 };
    for (const j of JOBS) if (passes(j, "basis")) n[basisOf(j)]++;
    for (const b of document.querySelectorAll("#basis button")) {
      b.classList.toggle("on", b.dataset.v === S.basis);
      b.setAttribute("aria-checked", b.dataset.v === S.basis);
      b.querySelector(".n").textContent = fmtInt(n[b.dataset.v]);
    }
  }

  const rangeText = () => (S.min != null && S.max != null ? `${money(S.min)}–${money(S.max)}` : S.min != null ? `≥ ${money(S.min)}` : `≤ ${money(S.max)}`);

  // ---------------------------------------------------------------- popovers

  function openPop(id, btn) {
    for (const b of document.querySelectorAll(".fbtn")) b.setAttribute("aria-expanded", b === btn ? "true" : "false");
    const pop = $("#pop");
    pop.dataset.f = id;
    pop.hidden = false;
    pop._btn = btn;
    fillPop();
    placePop();
    const first = pop.querySelector("input[type=search], select, input[type=number], input");
    if (first && matchMedia("(pointer: fine)").matches) first.focus();
  }

  function placePop() {
    const pop = $("#pop"), btn = pop._btn;
    if (pop.hidden || !btn) return;
    const r = btn.getBoundingClientRect();
    pop.style.position = "fixed";
    pop.style.top = r.bottom + 6 + "px";
    pop.style.left = Math.max(12, Math.min(r.left, innerWidth - pop.offsetWidth - 12)) + "px";
  }
  window.addEventListener("resize", placePop);

  function closePop() {
    $("#pop").hidden = true;
    $("#pop").dataset.f = "";
    for (const b of document.querySelectorAll(".fbtn")) b.setAttribute("aria-expanded", "false");
  }

  function fillPop() {
    const pop = $("#pop"), id = pop.dataset.f;
    if (pop.hidden || !id) return;
    if (id === "live") return fillLive(pop);
    if (id === "pay$") return fillPay(pop);
    const d = DIMS[DI[id]], i = DI[id];
    const counts = new Array(d.values.length).fill(0);
    for (const j of JOBS) if (passes(j, id)) counts[j.c[i]]++;
    const set = S.f[id];
    const search = pop.querySelector(".pop-search")?.value || "";
    pop.innerHTML = `<div class="pop-head"><b>${esc(d.label)}</b><p>${esc(d.help)}</p></div>` +
      (d.values.length > 12 ? `<div class="pop-body" style="padding-bottom:0"><input type="search" class="pop-search" placeholder="Find…" value="${esc(search)}"></div>` : "") +
      `<div class="pop-list">` + d.values.map((v, k) => `
        <label class="pop-row${counts[k] ? "" : " zero"}" data-k="${k}" ${search && !v.toLowerCase().includes(search.toLowerCase()) ? "hidden" : ""}>
          <input type="checkbox" data-k="${k}" ${!set || set.has(k) ? "checked" : ""}>
          ${logoImg(id, v)}<span class="lab">${esc(v)}</span>
          <button type="button" class="only" data-only="${k}">only</button>
          <span class="n">${fmtInt(counts[k])}</span>
        </label>`).join("") + `</div>
      <div class="pop-foot"><button type="button" class="linkbtn" data-all>Select all</button>
        <span class="muted" style="font-size:12px">Numbers: jobs matching your other filters</span></div>`;
    pop.querySelectorAll("input[type=checkbox]").forEach((cb) => cb.onchange = () => {
      const cur = S.f[id] ? new Set(S.f[id]) : new Set(d.values.map((_, k) => k));
      cb.checked ? cur.add(+cb.dataset.k) : cur.delete(+cb.dataset.k);
      setFilter(id, cur);
      S.limit = PAGE;
      update();
    });
    pop.querySelectorAll("[data-only]").forEach((b) => b.onclick = (e) => {
      e.preventDefault();
      setFilter(id, new Set([+b.dataset.only]));
      update();
    });
    pop.querySelector("[data-all]").onclick = () => { setFilter(id, null); update(); };
    const s = pop.querySelector(".pop-search");
    if (s) {
      s.oninput = () => pop.querySelectorAll(".pop-row").forEach((r) => {
        r.hidden = !!s.value && !d.values[+r.dataset.k].toLowerCase().includes(s.value.toLowerCase());
      });
    }
  }

  function fillLive(pop) {
    const base = JOBS.filter((j) => passes(j, "live"));
    const unclear = base.filter((j) => (j.w === "" || j.w === "listed" || (j.w === "onsite" && !j.pl.length)) && !(S.live && j.pl.includes(S.live))).length;
    const counts = new Map(COUNTRIES.map((c) => [c, 0]));
    for (const j of base) if (j.w !== "except") for (const p of j.pl) counts.set(p, counts.get(p) + 1);
    pop.innerHTML = `<div class="pop-head"><b>Open to people in</b>
        <p>Keeps the jobs you could do from one country: jobs open to anyone, jobs that name it, and on-site jobs there.</p></div>
      <div class="pop-body">
        <label>Country<select id="live">
          <option value="">Any country (no filter)</option>
          ${COUNTRIES.map((c) => `<option value="${esc(c)}" ${c === S.live ? "selected" : ""}>${esc(c)} (${fmtInt(counts.get(c))} name it)</option>`).join("")}
        </select></label>
        <label class="check"><input type="checkbox" id="unclear" ${S.unclear ? "checked" : ""}>
          <span>Also keep jobs that do not say who can apply (${fmtInt(unclear)})</span></label>
        <p class="hint">Read from the listings automatically: check the listing itself before applying.</p>
      </div>`;
    pop.querySelector("#live").onchange = (e) => { S.live = e.target.value; S.limit = PAGE; update(); };
    pop.querySelector("#unclear").onchange = (e) => { S.unclear = e.target.checked; update(); };
  }

  function fillPay(pop) {
    if (pop.querySelector("#pmin")) return; // keep focus while typing
    const u = S.basis === "hour" ? "$/hr" : "$ per piece";
    pop.innerHTML = `<div class="pop-head"><b>Pay range</b><p>${S.basis === "hour" ? "Top of the hourly rate" : "Top of the pay per task, project or session"}, in US$.</p></div>
      <div class="pop-body"><div class="row2">
        <label>At least (${u})<input type="number" id="pmin" min="0" step="1" inputmode="decimal" value="${S.min ?? ""}" placeholder="any"></label>
        <label>At most (${u})<input type="number" id="pmax" min="0" step="1" inputmode="decimal" value="${S.max ?? ""}" placeholder="any"></label>
      </div></div>
      <div class="pop-foot"><button type="button" class="linkbtn" data-clear>Clear</button></div>`;
    const read = debounce(() => {
      const a = pop.querySelector("#pmin").value, b = pop.querySelector("#pmax").value;
      S.min = a === "" ? null : +a;
      S.max = b === "" ? null : +b;
      S.limit = PAGE;
      update();
    }, 250);
    pop.querySelector("#pmin").oninput = read;
    pop.querySelector("#pmax").oninput = read;
    pop.querySelector("[data-clear]").onclick = () => {
      S.min = S.max = null; pop.innerHTML = ""; update(); fillPay(pop);
    };
  }

  // ---------------------------------------------------------------- active filters
  // Each filter button says what it holds ("Field: Law", "Site · 3"); one "Clear all" at the end of the row.

  function filterText(k) { // short description of a dimension filter, or "" when it is off
    if (!S.f[k]) return "";
    const d = DIMS[DI[k]], on = [...S.f[k]].sort((a, b) => a - b);
    const off = d.values.filter((_, i) => !S.f[k].has(i));
    if (on.length === 1) return d.values[on[0]];
    if (off.length === 1) return "not " + off[0];
    return "";
  }

  function renderClearAll() {
    let btn = $("#clear-all");
    if (!btn) {
      btn = document.createElement("button");
      btn.type = "button"; btn.id = "clear-all"; btn.className = "clear-all";
      btn.textContent = "Clear all";
      btn.onclick = () => { S.f = {}; S.q = ""; $("#q").value = ""; S.live = ""; S.min = S.max = null; S.limit = PAGE; update(); };
      $("#filters").appendChild(btn);
    }
    btn.hidden = !(S.q || S.live || S.min != null || S.max != null || Object.keys(S.f).length);
  }


  // ---------------------------------------------------------------- update

  function update() {
    filtered = JOBS.filter((j) => passes(j));
    for (const b of document.querySelectorAll("#scale button")) b.classList.toggle("on", b.dataset.v === S.scale);
    refreshBasis();
    refreshFilterButtons();
    renderClearAll();
    renderChart();
    renderTable();
    fillPop();
    placePop();
    writeHash();
  }

  // ---------------------------------------------------------------- colors

  function colors(ptsAll) {
    // ptsAll: chart points ignoring the filter on the color grouping, so hidden values stay in the legend.
    // Only the values still shown get a color, so hiding one hands its color to the next largest.
    if (!S.color) return { of: () => ACCENT, items: [] };
    const ci = DI[S.color], d = DIMS[ci];
    const n = new Map();
    for (const j of ptsAll) n.set(j.c[ci], (n.get(j.c[ci]) || 0) + 1);
    const on = (k) => !S.f[S.color] || S.f[S.color].has(k);
    const map = new Map();
    const shown = [...n.keys()].filter((k) => on(k) && !NEUTRAL.has(d.values[k]));
    if (d.ordinal) {
      shown.sort((a, b) => a - b).forEach((k, r) => map.set(k, RAMP(shown.length === 1 ? 0.5 : r / (shown.length - 1))));
    } else {
      shown.sort((a, b) => n.get(b) - n.get(a) || a - b).slice(0, PALETTE.length).forEach((k, r) => map.set(k, PALETTE[r]));
    }
    const of = (j) => map.get(j.c[ci]) || OTHER;
    const keys = [...n.keys()].sort((a, b) => (d.ordinal ? a - b : n.get(b) - n.get(a) || a - b)); // legend order does not move
    const items = keys.map((k) => ({ k, label: d.values[k], n: n.get(k), color: map.get(k) || OTHER, on: on(k), hl: S.hl.has(k) }));
    return { of, items, ci };
  }

  // ---------------------------------------------------------------- chart

  let chartState = null;

  function renderChart() {
    if (!DIMS) return;
    const svg = d3.select("#chart");
    svg.selectAll("*").remove();
    hideTip();
    const xi = DI[S.x], xd = DIMS[xi];
    const B = BASES[S.basis];
    const pts = filtered.filter((j) => yv(j) != null);
    const col = colors(S.color ? JOBS.filter((j) => yv(j) != null && passes(j, S.color)) : pts);

    const med = d3.median(pts, yv);
    $("#chart-title").textContent = S.basis === "none" ? B.title : `${B.title} by ${xd.label.toLowerCase()}`;
    // jobs matching the filters but under another pay basis: say so, with a link (e.g. a site whose jobs state no pay)
    const elsewhere = { hour: 0, piece: 0, none: 0 };
    const narrowed = S.q || S.live || Object.keys(S.f).length;
    if (narrowed) for (const j of JOBS) if (basisOf(j) !== S.basis && passes(j, "basis")) elsewhere[basisOf(j)]++;
    const also = Object.entries(elsewhere).filter(([, n]) => n)
      .map(([k, n]) => `<button type="button" class="linkbtn" data-basis="${k}">${fmtInt(n)} under \u201c${esc(BASES[k].label)}\u201d</button>`);
    const alsoText = also.length ? ` <span class="also">Also matching: ${also.join(", ")}.</span>` : "";
    $("#chart-sub").innerHTML = (S.basis === "none"
      ? `<b>${fmtInt(filtered.length)}</b> jobs match your filters but give no pay figure that could be read. They are listed in the table, with what each listing says about pay.`
      : pts.length
        ? `${B.sub}. <b>${fmtInt(pts.length)}</b> jobs match your filters (median <b>${money(med)}${B.unit}</b>).`
        : `No job matches these filters.`) + alsoText;
    $("#chart-sub").querySelectorAll("[data-basis]").forEach((b) => b.onclick = () => setBasis(b.dataset.basis));
    const cd = S.color ? DIMS[DI[S.color]] : null;
    $("#chart-note").innerHTML = `<b>${esc(xd.label)}:</b> ${esc(xd.help)}` + (cd && cd !== xd ? ` <b>${esc(cd.label)}:</b> ${esc(cd.help)}` : "");
    renderLegend(col);

    // groups along x
    const by = new Map();
    for (const j of pts) {
      const k = j.c[xi];
      if (!by.has(k)) by.set(k, []);
      by.get(k).push(j);
    }
    const logScale = S.scale === "log";
    const tf = logScale ? Math.log : (v) => v;
    const groups = [...by].map(([k, js]) => {
      const v = js.map(yv).sort((a, b) => a - b);
      const g = { k, label: xd.values[k], js, v, n: v.length,
        q1: d3.quantileSorted(v, 0.25), med: d3.quantileSorted(v, 0.5), q3: d3.quantileSorted(v, 0.75) };
      const iqr = tf(g.q3) - tf(g.q1);
      g.lo = v.find((x) => tf(x) >= tf(g.q1) - 1.5 * iqr);
      g.hi = [...v].reverse().find((x) => tf(x) <= tf(g.q3) + 1.5 * iqr);
      return g;
    });
    const mode = S.sort === "auto" ? (xd.ordinal ? "natural" : "median") : S.sort;
    groups.sort(mode === "natural" ? (a, b) => a.k - b.k
      : mode === "count" ? (a, b) => b.n - a.n || b.med - a.med
      : (a, b) => (b.n >= MIN_BOX) - (a.n >= MIN_BOX) || b.med - a.med || b.n - a.n);

    // layout
    const wrapW = $("#chart-scroll").clientWidth || 900;
    const small = wrapW < 640;
    const M = { t: 18, r: 18, l: 66 };
    const minBand = small ? 34 : 40;
    const n = Math.max(groups.length, 1);
    const maxChars = 30;
    const lw = groups.some((g) => logoSrc(S.x, g.label)) ? LOGO * Math.SQRT2 + LOGO_GAP : 0; // room for the logos before the names
    let width = Math.max(wrapW, M.l + M.r + n * minBand);
    let band = (width - M.l - M.r) / n;
    const rotate = band < 62;
    if (rotate && groups.length) { // slanted labels reach left of their group: make room for the furthest one
      const reach = d3.max(groups, (g, i) => (Math.min(g.label.length + 4, maxChars + 4) * 6.4 + lw) * Math.SQRT1_2 + 4 - i * minBand);
      if (reach > M.l) {
        M.l = Math.ceil(reach);
        width = Math.max(wrapW, M.l + M.r + n * minBand);
        band = (width - M.l - M.r) / n;
      }
    }
    const longest = d3.max(groups, (g) => Math.min(g.label.length, maxChars)) || 0;
    const nLines = rotate ? 0 : d3.max(groups, (g) => wrapLabel(g.label, band - lw).length) || 1;
    M.b = rotate ? 22 + (longest * 6.4 + lw) * Math.SQRT1_2 : 30 + nLines * 14.5;
    const plotH = small ? 320 : 420;
    const height = M.t + plotH + M.b;
    svg.attr("width", width).attr("height", height).attr("viewBox", `0 0 ${width} ${height}`);

    if (!pts.length) {
      svg.attr("height", 120).attr("viewBox", `0 0 ${width} 120`);
      svg.append("text").attr("class", "empty").attr("x", width / 2).attr("y", 60).attr("text-anchor", "middle")
        .text(S.basis === "none" ? "Nothing to plot: these jobs give no pay figure. See the table below."
          : also.length ? "No job here: see \u201cAlso matching\u201d above." : "No job matches these filters.");
      chartState = null;
      return;
    }

    const [lo, hi] = d3.extent(pts, yv);
    const y = logScale
      ? d3.scaleLog().domain([Math.max(lo / 1.35, 0.01), hi * 1.35]).range([M.t + plotH, M.t])
      : d3.scaleLinear().domain([0, hi * 1.05]).nice().range([M.t + plotH, M.t]);
    let ticks;
    if (logScale) {
      const [a, b] = y.domain();
      ticks = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000].filter((t) => t >= a && t <= b);
      if (ticks.length < 4) ticks = [1, 1.5, 2, 3, 5, 7.5, 10, 15, 20, 30, 50, 75, 100, 150, 200, 300, 500, 750, 1000].filter((t) => t >= a && t <= b);
    } else ticks = y.ticks(8);

    const gGrid = svg.append("g").attr("class", "grid");
    gGrid.selectAll("line").data(ticks).join("line")
      .attr("x1", M.l).attr("x2", width - M.r).attr("y1", (t) => y(t)).attr("y2", (t) => y(t));
    const gY = svg.append("g").attr("class", "axis");
    gY.selectAll("text").data(ticks).join("text")
      .attr("x", M.l - 8).attr("y", (t) => y(t)).attr("dy", "0.32em").attr("text-anchor", "end").text((t) => money(t));
    svg.append("text").attr("class", "ylab").attr("transform", `translate(12,${M.t + plotH / 2}) rotate(-90)`)
      .attr("text-anchor", "middle").text(B.axis);

    // median of everything shown
    svg.append("line").attr("x1", M.l).attr("x2", width - M.r).attr("y1", y(med)).attr("y2", y(med))
      .attr("stroke", "#94a3b8").attr("stroke-dasharray", "4 4");
    const medLabel = () => svg.append("text").attr("x", width - M.r).attr("y", y(med) - 5).attr("text-anchor", "end")
      .attr("fill", "#475467").attr("font-size", 11.5).attr("paint-order", "stroke").attr("stroke", "#fff")
      .attr("stroke-width", 4).attr("stroke-linejoin", "round").text(`median of all shown ${money(med)}`);

    const cx = (i) => M.l + band * (i + 0.5);
    const boxW = Math.min(band * 0.62, 84);
    const colored = !!S.color;
    const gBox = svg.append("g"), gDot = svg.append("g"), gMed = svg.append("g");
    const nodes = [];
    groups.forEach((g, i) => {
      const x = cx(i);
      g.x = x;
      if (g.n >= MIN_BOX) {
        gBox.append("line").attr("x1", x).attr("x2", x).attr("y1", y(g.lo)).attr("y2", y(g.hi)).attr("stroke", "#a3adbb");
        for (const w of [g.lo, g.hi]) {
          gBox.append("line").attr("x1", x - boxW * 0.18).attr("x2", x + boxW * 0.18).attr("y1", y(w)).attr("y2", y(w)).attr("stroke", "#a3adbb");
        }
        gBox.append("rect").attr("x", x - boxW / 2).attr("width", boxW).attr("y", y(g.q3)).attr("height", Math.max(1, y(g.q1) - y(g.q3)))
          .attr("rx", 3).attr("fill", colored ? "#eef1f5" : "#e3ebfd").attr("stroke", colored ? "#8a94a6" : "#7d9ce8");
        gMed.append("line").attr("x1", x - boxW / 2).attr("x2", x + boxW / 2).attr("y1", y(g.med)).attr("y2", y(g.med))
          .attr("stroke", "#fff").attr("stroke-width", 5).attr("stroke-linecap", "round");
        gMed.append("line").attr("x1", x - boxW / 2).attr("x2", x + boxW / 2).attr("y1", y(g.med)).attr("y2", y(g.med))
          .attr("stroke", "#0f172a").attr("stroke-width", 2.5).attr("stroke-linecap", "round");
      }
      const spread = Math.min(band * 0.72, Math.max(boxW, 30 + Math.sqrt(g.n) * 4)); // big groups get room
      for (const j of g.js) nodes.push({ j, g, px: x + jitter(j.id) * spread * 0.48, py: y(yv(j)) });
    });
    // rarer colors drawn last so they are not buried
    if (S.color) {
      const ci = DI[S.color], freq = new Map(col.items.map((it) => [it.k, it.n]));
      nodes.sort((a, b) => (freq.get(b.j.c[ci]) || 0) - (freq.get(a.j.c[ci]) || 0));
    }
    const r = pts.length > 1200 ? 2.6 : pts.length > 400 ? 3 : 3.6;
    const dots = gDot.selectAll("circle").data(nodes).join("circle")
      .attr("cx", (d) => d.px).attr("cy", (d) => d.py).attr("fill", (d) => col.of(d.j));

    // x labels (click: show only this group), with the site's logo before its name
    const gX = svg.append("g");
    if (lw) svg.append("defs").append("clipPath").attr("id", "logo-clip").attr("clipPathUnits", "objectBoundingBox")
      .append("rect").attr("width", 1).attr("height", 1).attr("rx", 0.2);
    const addLogo = (t, src, cx, cy) => t.append("image").attr("href", src).attr("x", cx - LOGO / 2).attr("y", cy - LOGO / 2)
      .attr("width", LOGO).attr("height", LOGO).attr("clip-path", "url(#logo-clip)");
    groups.forEach((g) => {
      const src = logoSrc(S.x, g.label);
      const t = gX.append("g").attr("class", "xlabel").attr("transform", `translate(${g.x},${M.t + plotH + 14})`);
      t.append("title").text(`${g.label}: ${g.n} jobs. Click to show only this group.`);
      t.append("rect").attr("x", rotate ? -6 : -band / 2).attr("y", -10).attr("width", rotate ? 12 : band).attr("height", rotate ? 14 : 20 + nLines * 14.5)
        .attr("fill", "transparent");
      if (rotate) {
        const lab = g.label.length > maxChars ? g.label.slice(0, maxChars - 1) + "…" : g.label;
        // upright logo under the axis, the slanted name after it (all names start the same distance out, logo or not)
        const tx = t.append("text").attr("transform", "rotate(-45)").attr("text-anchor", "end").attr("dy", "0.32em")
          .attr("x", lw ? -(LOGO * Math.SQRT1_2 + LOGO_GAP) : 0); // the square's corner, not its side, faces the text
        tx.append("tspan").attr("class", "name").text(lab);
        tx.append("tspan").attr("class", "n").text(` ${g.n}`);
        if (src) addLogo(t, src, 0, 0);
      } else {
        const lines = wrapLabel(g.label, band - lw);
        const tx = t.append("text").attr("text-anchor", "middle");
        lines.forEach((l, k) => tx.append("tspan").attr("class", "name").attr("x", 0).attr("dy", k ? "1.15em" : "0.32em").text(l));
        if (src) { // logo + first line centered together under the group
          const first = tx.select("tspan").attr("x", (LOGO + LOGO_GAP) / 2);
          const w = first.node().getComputedTextLength();
          addLogo(t, src, (LOGO + LOGO_GAP) / 2 - w / 2 - LOGO_GAP - LOGO / 2, 0);
        }
        t.append("text").attr("class", "n").attr("text-anchor", "middle").attr("y", nLines * 14.5 + 2).attr("dy", "0.32em").text(`n=${g.n}`);
      }
      t.on("click", () => {
        const cur = S.f[S.x];
        setFilter(S.x, cur && cur.size === 1 && cur.has(g.k) ? null : new Set([g.k]));
        S.limit = PAGE;
        update();
      });
    });

    // hover + click, nearest dot within reach, else the group under the pointer
    const hover = svg.append("circle").attr("r", r + 3).attr("fill", "none").attr("stroke", "#0f172a").attr("stroke-width", 1.5)
      .attr("pointer-events", "none").style("display", "none");
    const selRing = svg.append("circle").attr("r", r + 4.5).attr("fill", "none").attr("stroke", ACCENT).attr("stroke-width", 2.5)
      .attr("pointer-events", "none").style("display", "none");
    const delaunay = d3.Delaunay.from(nodes, (d) => d.px, (d) => d.py);
    const overlay = svg.append("rect").attr("x", M.l).attr("y", M.t - 6).attr("width", width - M.l - M.r).attr("height", plotH + 12)
      .attr("fill", "transparent").style("cursor", "crosshair");
    const tip = $("#tip");
    const pick = (ev) => {
      const [mx, my] = d3.pointer(ev, svg.node());
      const i = delaunay.find(mx, my);
      const d = nodes[i];
      if (d && Math.hypot(d.px - mx, d.py - my) <= Math.max(10, r * 3)) return { d };
      const gi = Math.floor((mx - M.l) / band);
      return { g: groups[gi] };
    };
    overlay.on("pointermove", (ev) => {
      const p = pick(ev);
      if (p.d) {
        hover.style("display", null).attr("cx", p.d.px).attr("cy", p.d.py);
        overlay.style("cursor", "pointer");
        showTip(ev, jobTip(p.d.j, col));
      } else if (p.g) {
        hover.style("display", "none");
        overlay.style("cursor", "crosshair");
        showTip(ev, groupTip(p.g));
      } else hideTip();
    });
    overlay.on("pointerleave", (ev) => { if (ev.pointerType === "mouse") { hover.style("display", "none"); hideTip(); } });
    // touch: first tap shows the details, a second tap on the same dot opens it in the table
    let lastType = "mouse", tapped = null;
    overlay.on("pointerdown", (ev) => { lastType = ev.pointerType || "mouse"; });
    overlay.on("click", (ev) => {
      const p = pick(ev);
      if (lastType !== "mouse") {
        const id = p.d ? p.d.j.id : p.g ? "g:" + p.g.k : null;
        if (id && id !== tapped) {
          tapped = id;
          if (p.d) { hover.style("display", null).attr("cx", p.d.px).attr("cy", p.d.py); showTip(ev, jobTip(p.d.j, col, true)); }
          else { hover.style("display", "none"); showTip(ev, groupTip(p.g)); }
          return;
        }
        tapped = null;
        hideTip();
      }
      if (p.d) selectJob(p.d.j.id, true);
    });
    medLabel();
    chartState = { nodes, selRing, dots, r, colored, ci: col.ci };
    styleDots();
    drawSelection();
  }

  // highlighted values pop (bigger, opaque, on top), the rest fade; `preview` is a legend hover
  function styleDots(preview) {
    if (!chartState) return;
    const { dots, r, colored, ci } = chartState;
    const H = preview || S.hl;
    const lit = (d) => H.has(d.j.c[ci]);
    if (!colored || !H.size) {
      dots.attr("r", r).attr("fill-opacity", colored ? 0.8 : 0.5).attr("stroke", "#fff").attr("stroke-width", 0.5).attr("stroke-opacity", 0.8);
      return;
    }
    dots.attr("r", (d) => (lit(d) ? r * 1.45 : r * 0.9)).attr("fill-opacity", (d) => (lit(d) ? 1 : 0.12))
      .attr("stroke", (d) => (lit(d) ? "#0f172a" : "#fff")).attr("stroke-width", (d) => (lit(d) ? 0.7 : 0.5))
      .attr("stroke-opacity", (d) => (lit(d) ? 0.55 : 0.4));
    dots.filter(lit).raise();
    chartState.selRing.raise();
  }

  function drawSelection() {
    if (!chartState) return;
    const d = chartState.nodes.find((n) => n.j.id === S.sel);
    chartState.selRing.style("display", d ? null : "none");
    if (d) chartState.selRing.attr("cx", d.px).attr("cy", d.py).raise();
  }

  function wrapLabel(s, band, maxLines = 3) {
    const per = Math.max(5, Math.floor((band - 6) / 6.4)); // characters that fit in the band
    const lines = [];
    let cur = "";
    for (const w of s.split(" ")) {
      if (cur && (cur + " " + w).length > per) { lines.push(cur); cur = w; } else cur = cur ? cur + " " + w : w;
    }
    if (cur) lines.push(cur);
    const out = lines.slice(0, maxLines).map((l) => (l.length > per ? l.slice(0, per - 1) + "…" : l));
    if (lines.length > maxLines) out[maxLines - 1] = out[maxLines - 1].slice(0, per - 1).replace(/[\s,&]+$/, "") + "…";
    return out;
  }

  function jitter(id) { // stable in [-1, 1] so dots do not jump when filters change
    let h = 2166136261;
    for (let i = 0; i < id.length; i++) { h ^= id.charCodeAt(i); h = Math.imul(h, 16777619); }
    return ((h >>> 0) / 4294967295) * 2 - 1;
  }

  function showTip(ev, html) {
    const tip = $("#tip"), wrap = $("#chart-wrap").getBoundingClientRect();
    tip.innerHTML = html;
    tip.hidden = false;
    const x = ev.clientX - wrap.left, y = ev.clientY - wrap.top;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = (x + 16 + w > wrap.width ? Math.max(0, x - w - 16) : x + 16) + "px";
    tip.style.top = Math.max(0, Math.min(y - h / 2, wrap.height - h)) + "px";
  }
  function hideTip() { $("#tip").hidden = true; }

  function jobTip(j, col, touch) {
    const rows = [["Field", val(j, "field")], ["Who can apply", whoText(j)]];
    if (S.color && !["field"].includes(S.color)) rows.push([DIMS[DI[S.color]].label, val(j, S.color)]);
    if (!["site"].includes(S.x) && S.color !== "site") rows.splice(1, 0, ["Site", j.s]);
    return `<b>${esc(j.t)}</b><span class="muted">${esc(j.co || j.s)}</span>
      <div class="big"><span class="sw" style="background:${col.of(j)}"></span>${money(yv(j))}${S.basis === "hour" ? "/hr" : " per " + (j.unit || "piece")}</div>
      <div class="muted">as stated: ${esc(payText(j))}</div>
      ${j.ev.Converted ? `<div class="muted">${esc(j.ev.Converted)}</div>` : ""}
      <table>${rows.map(([a, b]) => `<tr><td class="muted">${esc(a)}</td><td>${esc(b)}</td></tr>`).join("")}</table>
      <div class="muted" style="margin-top:6px">${touch ? "Tap again" : "Click"} to see it in the table</div>`;
  }

  function groupTip(g) {
    const rows = [["Jobs", fmtInt(g.n)], ["Median", money(g.med) + BASES[S.basis].unit]];
    if (g.n >= MIN_BOX) rows.push(["Middle half", `${money(g.q1)} – ${money(g.q3)}`]);
    rows.push(["Lowest – highest", `${money(g.v[0])} – ${money(g.v[g.v.length - 1])}`]);
    return `<b>${esc(g.label)}</b><table>${rows.map(([a, b]) => `<tr><td class="muted">${a}</td><td>${b}</td></tr>`).join("")}</table>` +
      (g.n < MIN_BOX ? `<div class="muted" style="margin-top:6px">Fewer than ${MIN_BOX} jobs: no box.</div>` : "");
  }

  function renderLegend(col) {
    const el = $("#legend");
    if (!S.color || !col.items.length) { el.innerHTML = ""; return; }
    for (const k of [...S.hl]) if (!col.items.some((it) => it.k === k && it.on)) S.hl.delete(k); // hidden: no highlight
    const hiMode = S.legendMode === "highlight", anyHl = S.hl.size > 0;
    const greyed = col.items.filter((i) => i.on && i.color === OTHER && !NEUTRAL.has(i.label)).length;
    el.innerHTML = `<div class="legend-head"><span class="ttl">${esc(DIMS[DI[S.color]].label)}</span>
        <span class="mode">Click a color to
          <span class="seg mini" role="group" aria-label="What a click on the legend does">
            <button type="button" data-mode="hide" class="${hiMode ? "" : "on"}">hide it</button><button type="button" data-mode="highlight" class="${hiMode ? "on" : ""}">highlight it</button>
          </span></span>
        ${anyHl ? `<button type="button" class="linkbtn" data-clearhl>Clear highlight</button>` : ""}
        ${col.items.some((i) => !i.on) ? `<button type="button" class="linkbtn" data-showall>Show all</button>` : ""}
      </div>
      <div class="legend-items">` + col.items.map((it) =>
      `<button type="button" class="item${it.on ? "" : " off"}${it.hl ? " lit" : anyHl && it.on ? " dim" : ""}" data-k="${it.k}"
          title="${it.on ? (hiMode ? "Click to highlight" : "Click to hide") : "Hidden: click to show again"}">
        <span class="sw" style="${it.on ? `background:${it.color}` : "background:transparent;box-shadow:inset 0 0 0 1.5px #b8bfca"}"></span>${logoImg(S.color, it.label)}${esc(it.label)} <span class="n">${fmtInt(it.n)}</span></button>`).join("") +
      (greyed > 1 ? `<span class="n note-grey">Grey: shown groups beyond the ${PALETTE.length} largest. Hide some to free colors.</span>` : "") +
      `</div>`;
    el.querySelectorAll("[data-mode]").forEach((b) => b.onclick = () => { S.legendMode = b.dataset.mode; renderLegend(col); });
    const clearHl = el.querySelector("[data-clearhl]");
    if (clearHl) clearHl.onclick = () => { S.hl = new Set(); update(); };
    const showAll = el.querySelector("[data-showall]");
    if (showAll) showAll.onclick = () => { delete S.f[S.color]; update(); };
    el.querySelectorAll(".item").forEach((b) => {
      const k = +b.dataset.k, it = col.items.find((i) => i.k === k);
      b.onclick = () => {
        if (it.on && hiMode) { // highlight: several at once, the chart's boxes and the table do not change
          S.hl.has(k) ? S.hl.delete(k) : S.hl.add(k);
          update();
          return;
        }
        const d = DIMS[DI[S.color]];
        const cur = S.f[S.color] ? new Set(S.f[S.color]) : new Set(d.values.map((_, i) => i));
        cur.has(k) ? cur.delete(k) : cur.add(k);
        if (cur.size === 0) return; // keep at least one
        S.hl.delete(k);
        setFilter(S.color, cur);
        update();
      };
      // in "highlight it" mode, hovering previews the highlight (mouse only: touch screens have no hover)
      b.onpointerenter = (e) => { if (e.pointerType === "mouse" && it.on && S.legendMode === "highlight") styleDots(new Set([...S.hl, k])); };
      b.onpointerleave = (e) => { if (e.pointerType === "mouse") styleDots(); };
    });
  }

  // ---------------------------------------------------------------- table

  function payText(j) {
    if (j.pmax == null) return "";
    const pre = SYM[j.cur] ?? (j.cur ? j.cur + " " : "");
    const f = (v) => pre + (v >= 1000 ? fmtInt(Math.round(v)) : Number.isInteger(v) ? v : v.toFixed(2));
    const range = j.pmin == null ? "up to " + f(j.pmax) : j.pmin === j.pmax ? f(j.pmax) : f(j.pmin) + "–" + f(j.pmax);
    return range + (UNIT[j.unit] ?? (j.unit ? " per " + j.unit : ""));
  }

  function whoText(j) {
    const pl = j.pl.map((p) => SHORT[p] || p);
    const list = (a, n = 3) => (a.length <= n ? a.join(", ") : a.slice(0, n).join(", ") + ` +${a.length - n}`);
    switch (j.w) {
      case "any": return "Anywhere";
      case "only": return pl.length ? "Only " + list(pl) : "Listed places only";
      case "except": return "Anywhere except " + list(pl);
      case "onsite": return "On site" + (j.loc.length ? ": " + list(j.loc.map((l) => l.split(",")[0]), 2) : "");
      case "listed": return "Lists " + (j.loc.length ? list(j.loc, 2) : list(pl)) + ", not said if required";
      default: return "Not stated";
    }
  }

  const COLS = [
    { k: "t", label: "Job", sort: (j) => j.t.toLowerCase(),
      cell: (j) => `<div class="t-title">${esc(j.t)}</div>${j.co ? `<div class="t-sub">${esc(j.co)}</div>` : ""}` },
    { k: "s", label: "Site", sort: (j) => j.s.toLowerCase(), cell: (j) => `<span class="site">${logoImg("site", j.s)}<span>${esc(j.s)}</span></span>` },
    { k: "pay", label: "Pay as stated", sort: null, cell: (j) => {
      const t = payText(j);
      const tags = [];
      if (j.pmax != null && j.pmin == null) tags.push(`<span class="tag warn">only "up to"</span>`);
      // a range already says pay varies; what it varies with is the news (the quote is in the job's details)
      if (j.ev["Pay depends on"]) tags.push(`<span class="tag" title="${esc(j.ev["Pay depends on"])}">depends on ${esc(val(j, "dep").toLowerCase())}</span>`);
      if (val(j, "cur").includes("assumed")) tags.push(`<span class="tag">"$" assumed US$</span>`);
      if (val(j, "cur").startsWith("Converted")) tags.push(`<span class="tag">converted</span>`);
      if (j.unit === "year" || j.unit === "month") tags.push(`<span class="tag">salary, 40 h/week</span>`);
      return (t ? esc(t) : `<span class="muted">${esc(val(j, "pay"))}</span>`) + (tags.length ? "<br>" + tags.join(" ") : "");
    } },
    { k: "h", label: "Top US$", num: true, sort: (j) => yv(j), cell: (j) => (yv(j) != null ? `<span class="hr">${money(yv(j))}</span>` : `<span class="muted">–</span>`) },
    { k: "field", label: "Field", dim: true },
    { k: "who", label: "Who can apply", sort: (j) => j.w + whoText(j), cell: (j) => esc(whoText(j)) },
    { k: "mode", label: "Work mode", dim: true },
    { k: "years", label: "Experience", dim: true },
    { k: "degree", label: "Degree", dim: true },
    { k: "posted", label: "Posted", nowrap: true, sort: (j) => j.posted || "", cell: (j) => (j.posted ? esc(j.posted) : `<span class="muted">–</span>`) },
  ];
  for (const c of COLS) {
    if (!c.dim) continue;
    c.sort = (j) => (DIMS[DI[c.k]].ordinal ? j.c[DI[c.k]] : val(j, c.k).toLowerCase());
    c.cell = (j) => { const v = val(j, c.k); return NEUTRAL.has(v) ? `<span class="muted">${esc(v)}</span>` : esc(v); };
  }

  function sortRows() {
    const c = COLS.find((x) => x.k === S.ts) || COLS[3];
    const dir = S.td;
    tableRows = filtered.slice().sort((a, b) => {
      const va = c.sort(a), vb = c.sort(b);
      const na = va == null || va === "", nb = vb == null || vb === "";
      if (na !== nb) return na ? 1 : -1; // empty values last whichever the direction
      if (va < vb) return -dir;
      if (va > vb) return dir;
      return (b.h ?? -1) - (a.h ?? -1) || a.t.localeCompare(b.t);
    });
  }

  function renderTable() {
    sortRows();
    $("#table-title").textContent = `${fmtInt(filtered.length)} jobs`;
    const thead = $("#table thead");
    const label = (c) => (c.k !== "h" ? c.label : S.basis === "hour" ? "Top US$/hr" : S.basis === "piece" ? "Top US$ per piece" : "Top US$");
    thead.innerHTML = "<tr>" + COLS.map((c) => `<th class="${c.num ? "num" : ""}" data-k="${c.k}" ${c.sort ? "" : 'style="cursor:default"'}>` +
      `${esc(label(c))}${S.ts === c.k ? `<span class="arr">${S.td < 0 ? "↓" : "↑"}</span>` : ""}</th>`).join("") + "</tr>";
    thead.querySelectorAll("th").forEach((th) => th.onclick = () => {
      const c = COLS.find((x) => x.k === th.dataset.k);
      if (!c.sort) return;
      if (S.ts === c.k) S.td = -S.td;
      else { S.ts = c.k; S.td = c.k === "h" || c.k === "posted" ? -1 : 1; }
      renderTable();
    });
    const shown = tableRows.slice(0, S.limit);
    $("#table tbody").innerHTML = shown.map((j) => {
      const open = S.open.has(j.id);
      return `<tr class="job${j.id === S.sel ? " sel" : ""}" data-id="${esc(j.id)}">` +
        COLS.map((c) => `<td class="${c.num ? "num" : ""}${c.nowrap ? " nowrap" : ""}">${c.cell(j)}</td>`).join("") + "</tr>" +
        (open ? `<tr class="detail"><td colspan="${COLS.length}">${detail(j)}</td></tr>` : "");
    }).join("") || `<tr><td colspan="${COLS.length}" class="muted" style="padding:28px 20px">No job matches these filters` +
      `${$("#chart-sub .also") ? " here. " + $("#chart-sub .also").innerHTML : "."}</td></tr>`;
    $("#table tbody").querySelectorAll("[data-basis]").forEach((b) => b.onclick = () => setBasis(b.dataset.basis));
    $("#table tbody").querySelectorAll("tr.job").forEach((tr) => tr.onclick = (e) => {
      if (e.target.closest("a")) return;
      const id = tr.dataset.id;
      if (S.open.has(id)) { S.open.delete(id); if (S.sel === id) S.sel = null; } else { S.open.add(id); S.sel = id; }
      renderTable();
      drawSelection();
    });
    const more = $("#more");
    if (tableRows.length > S.limit) {
      more.innerHTML = `Showing ${fmtInt(S.limit)} of ${fmtInt(tableRows.length)}
        <button type="button" class="btn" data-more>Show ${fmtInt(Math.min(PAGE, tableRows.length - S.limit))} more</button>
        <button type="button" class="btn" data-allrows>Show all</button>`;
      more.querySelector("[data-more]").onclick = () => { S.limit += PAGE; renderTable(); };
      more.querySelector("[data-allrows]").onclick = () => { S.limit = tableRows.length; renderTable(); };
    } else more.innerHTML = "";
  }

  function detail(j) {
    const ev = j.ev, why = (v, k) => (ev[k] ? `${v} (${ev[k]})` : v);
    const items = [
      ["Pay", why(payText(j) || val(j, "pay"), "Pay read from")],
      ["Used in the chart", j.h != null ? money(j.h) + "/hr (top of the range), under \u201cPer hour\u201d"
        : j.pt != null ? `${money(j.pt)} per ${j.unit || "piece"} (top of the range), under \u201cPer task or project\u201d` : "not in the chart: no pay figure"],
      ["Conversion", ev["Converted"]],
      ["Pay as written", ev["Pay as written"]],
      ["Currency", ev["Currency"]],
      ["Pay depends on", ev["Pay depends on"]],
      ["About pay", ev["About pay"]],
      ["Earnings claim (not used)", ev["Earnings claim (not used)"]],
      ["Who can apply", whoText(j) + (ev["Who can apply"] ? ` (${ev["Who can apply"]})` : "")],
      ["Work mode", why(val(j, "mode"), "Work mode")],
      ["Kind of job", why(val(j, "contract"), "Kind of job")],
      ["Experience asked", why(val(j, "years"), "Experience")],
      ["Degrees mentioned", ev["Degrees mentioned"]],
      ["Hours per week", ev["Hours per week"]],
      ["Field (from the title)", val(j, "field")],
      ["Type of site", val(j, "kind")],
      ["Places listed", j.loc.length ? j.loc.join("; ") + (j.nloc > j.loc.length ? ` and ${j.nloc - j.loc.length} more` : "") : ""],
      ["Countries read", j.pl.join(", ")],
    ].filter(([, v]) => v);
    return `<div class="detail-top"><a class="btn" href="${esc(j.u)}" target="_blank" rel="noopener">Open the listing ↗</a>
      <span class="muted">${j.n > 1 ? `Posted ${fmtInt(j.n)} times (once per place). ` : ""}${j.posted ? "Posted " + esc(j.posted) + "." : ""}</span></div>
      <dl class="detail-grid">${items.map(([a, b]) => `<div><dt>${esc(a)}</dt><dd>${esc(b)}</dd></div>`).join("")}</dl>`;
  }

  function selectJob(id, fromChart) {
    S.sel = id;
    S.open.add(id);
    sortRows();
    const i = tableRows.findIndex((j) => j.id === id);
    if (i >= S.limit) S.limit = Math.ceil((i + 1) / PAGE) * PAGE;
    renderTable();
    drawSelection();
    if (fromChart) {
      const tr = document.querySelector(`tr.job[data-id="${CSS.escape(id)}"]`);
      if (tr) {
        tr.scrollIntoView({ behavior: "smooth", block: "center" });
        tr.classList.add("flash");
      }
    }
  }

  // ---------------------------------------------------------------- CSV

  function downloadCsv() {
    sortRows();
    const head = ["title", "company", "site", "url", "pay_as_stated", "top_usd_per_hour", "top_usd_per_piece", "conversion", ...DIMS.map((d) => d.label),
      "who_can_apply", "countries", "places_listed", "posted"];
    const q = (s) => { s = String(s ?? ""); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    const lines = [head.map(q).join(",")];
    for (const j of tableRows) {
      lines.push([j.t, j.co, j.s, j.u, payText(j), j.h ?? "", j.pt ?? "", j.ev.Converted || "", ...DIMS.map((d) => d.values[j.c[DI[d.key]]]),
        whoText(j), j.pl.join("; "), j.loc.join("; "), j.posted].map(q).join(","));
    }
    const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `annotation-jobs-${SNAPSHOT}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
})();

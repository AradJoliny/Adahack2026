const CURRENCY = "£";
const MAX_SEGMENTS = 12; // smaller project slices are folded into "Other"

const $ = (id) => document.getElementById(id);
const fmt = (n, d = 0) => Number(n).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
const money = (n, d = 0) => CURRENCY + fmt(n, d);
const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC_MAP[c]);

const COLUMNS = [
  { key: "project_name", label: "Project" },
  { key: "status", label: "Status", badge: "status" },
  { key: "project_type", label: "Type" },
  { key: "region", label: "Region" },
  { key: "country", label: "Country" },
  { key: "developer", label: "Developer" },
  { key: "vintage_year", label: "Vintage", num: true, plain: true },
  { key: "price_per_tonne", label: "Price / t", num: true, fmt: (v) => money(v, 2) },
  { key: "risk", label: "Risk", badge: "risk" },
  { key: "tonnes_chosen", label: "Tonnes chosen", num: true, fmt: (v) => fmt(v) },
  { key: "total_spend", label: "Total spend", num: true, fmt: (v) => money(v) },
];

const state = { data: null, metric: "carbon", regionSub: "carbon", sort: { key: "tonnes_chosen", dir: -1 }, chart: null };

/* ---------- API ---------- */
async function post(body) {
  const res = await fetch("/api/portfolio", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const json = await res.json();
  if (!res.ok) throw new Error(json.error || res.statusText);
  return json;
}
async function loadSample() {
  const res = await fetch("/api/sample");
  if (!res.ok) throw new Error("Could not load sample data");
  return res.json();
}
async function run(promiseFn) {
  hideAlert();
  try { setData(await promiseFn()); }
  catch (e) { showAlert(e.message); }
}

function showAlert(msg, warn = false) { const a = $("alert"); a.textContent = msg; a.className = "alert" + (warn ? " warn" : ""); a.hidden = false; }
function hideAlert() { $("alert").hidden = true; }

/* ---------- data -> view ---------- */
function setData(data) {
  state.data = data;
  $("dashboard").hidden = false;
  $("empty").hidden = true;
  if (data.warnings?.length) showAlert("Note: " + data.warnings.join(" · "), true);
  renderStats(); renderMapping(); renderTable(); renderChart();
  $("dashboard").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderStats() {
  const s = state.data.summary;
  const items = [
    ["Projects", fmt(s.project_count), `${s.region_count} regions`],
    ["Carbon saved", fmt(s.total_tonnes), "tonnes CO₂e chosen"],
    ["Total spend", money(s.total_spend), "tonnes × price per tonne"],
    ["Avg price", money(s.weighted_avg_price, 2), "per tonne, weighted"],
  ];
  $("stats").innerHTML = items.map(([l, v, sub], i) =>
    `<div class="card stat" style="animation-delay:${i * 70}ms"><div class="label">${l}</div><div class="value">${v}</div><div class="sub">${sub}</div></div>`).join("");
}

function renderMapping() {
  $("mapping-body").innerHTML = Object.entries(state.data.mapping).map(([k, src]) =>
    src ? `<span class="chip">${esc(k.replace(/_/g, " "))} <em>←</em> ${esc(src)}</span>`
        : `<span class="chip miss">${esc(k.replace(/_/g, " "))} <em>not found</em></span>`).join("");
}

function badgeClass(kind, v) {
  const s = String(v ?? "").toLowerCase();
  if (kind === "risk") return /low|^a|^1$/.test(s) ? "b-green" : /med|^b|^2$/.test(s) ? "b-amber" : /high|^c|^d|^3$/.test(s) ? "b-red" : "b-grey";
  return /active|operat|issued|live/.test(s) ? "b-green" : /develop|pilot|pending|plan|valid/.test(s) ? "b-amber" : /cancel|retire|suspend|halt/.test(s) ? "b-red" : "b-grey";
}

function renderTable() {
  const { key, dir } = state.sort;
  const rows = [...state.data.records].sort((a, b) => {
    const x = a[key], y = b[key];
    if (x == null) return 1; if (y == null) return -1;
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * dir;
  });
  $("table").querySelector("thead").innerHTML = "<tr>" + COLUMNS.map((c) =>
    `<th data-key="${c.key}" class="${c.num ? "num" : ""}">${c.label}<span class="arrow">${c.key === key ? (dir > 0 ? "▲" : "▼") : ""}</span></th>`).join("") + "</tr>";
  $("table").querySelector("tbody").innerHTML = rows.map((r) =>
    `<tr data-name="${esc(r.project_name)}">` + COLUMNS.map((c) => {
      const v = r[c.key];
      let html = v == null ? '<span style="color:var(--muted)">—</span>'
        : c.badge ? `<span class="badge ${badgeClass(c.badge, v)}">${esc(v)}</span>`
        : c.fmt ? c.fmt(v) : esc(v);
      return `<td class="${c.num ? "num" : ""}">${html}</td>`;
    }).join("") + "</tr>").join("");
}

/* ---------- pie ---------- */
function palette(n) {
  return Array.from({ length: n }, (_, i) => `hsl(${(160 + i * (360 / Math.max(n, 6)) * 1.0) % 360} ${62 + (i % 3) * 8}% ${56 - (i % 2) * 8}%)`);
}

function buildSlices() {
  const recs = state.data.records;
  const measure = state.metric === "region" ? state.regionSub : state.metric;
  const val = (r) => (measure === "spend" ? r.total_spend : r.tonnes_chosen);
  let slices;
  if (state.metric === "region") {
    const m = new Map();
    recs.forEach((r) => m.set(r.region, (m.get(r.region) || 0) + val(r)));
    slices = [...m].map(([label, value]) => ({ label, value }));
  } else {
    slices = recs.map((r) => ({ label: r.project_name, value: val(r) }));
  }
  slices = slices.filter((s) => s.value > 0).sort((a, b) => b.value - a.value);
  if (slices.length > MAX_SEGMENTS) {
    const rest = slices.splice(MAX_SEGMENTS - 1);
    slices.push({ label: `Other (${rest.length})`, value: rest.reduce((t, s) => t + s.value, 0) });
  }
  return { slices, measure };
}

function renderChart() {
  const { slices, measure } = buildSlices();
  const total = slices.reduce((t, s) => t + s.value, 0);
  const colors = palette(slices.length);
  const unit = (v) => (measure === "spend" ? money(v) : fmt(v) + " t");
  const title = { carbon: "Carbon saved (tonnes)", spend: "Price spent" }[measure] + (state.metric === "region" ? " by region" : " by project");

  $("region-sub").hidden = state.metric !== "region";
  const data = { labels: slices.map((s) => s.label), datasets: [{ data: slices.map((s) => s.value), backgroundColor: colors,
    borderColor: "#0a121b", borderWidth: 2, hoverOffset: 14 }] };

  if (state.chart) {
    state.chart.data = data;
    state.chart.options.plugins.tooltip.callbacks.label = (c) => ` ${unit(c.parsed)} · ${(c.parsed / total * 100).toFixed(1)}%`;
    state.chart.options.plugins.title.text = title;
    state.chart.update();
  } else {
    state.chart = new Chart($("pie"), {
      type: "pie", data,
      options: {
        maintainAspectRatio: false, animation: { duration: 700, easing: "easeOutQuart" },
        onHover: (_, els) => highlight(els.length ? els[0].index : null),
        plugins: {
          legend: { display: false },
          title: { display: true, text: title, color: "#8ea3a0", font: { family: "Outfit", size: 13, weight: 400 }, padding: { bottom: 10 } },
          tooltip: { backgroundColor: "rgba(7,13,20,.95)", borderColor: "rgba(255,255,255,.12)", borderWidth: 1, padding: 12, titleFont: { family: "Outfit", size: 14 }, bodyFont: { family: "Outfit", size: 13 },
            callbacks: { label: (c) => ` ${unit(c.parsed)} · ${(c.parsed / total * 100).toFixed(1)}%` } },
        },
      },
    });
  }

  $("legend").innerHTML = slices.map((s, i) =>
    `<li data-i="${i}"><span class="dot" style="background:${colors[i]}"></span><span class="name" title="${esc(s.label)}">${esc(s.label)}</span><span class="val">${unit(s.value)}</span><span class="pct">${(s.value / total * 100).toFixed(1)}%</span></li>`).join("");
}

function highlight(i) {
  document.querySelectorAll("#legend li").forEach((li) => li.classList.toggle("hl", Number(li.dataset.i) === i));
}

/* ---------- events ---------- */
document.querySelectorAll('#size-options input').forEach((cb) => cb.addEventListener("change", () => {
  // Behaves as an exclusive checkbox group: ticking one unticks the rest; the active one can't be cleared.
  if (!cb.checked) { cb.checked = true; return; }
  document.querySelectorAll('#size-options input').forEach((o) => { if (o !== cb) o.checked = false; });
  state.metric = cb.value;
  renderChart();
}));

document.querySelectorAll(".seg").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".seg").forEach((o) => o.classList.toggle("active", o === b));
  state.regionSub = b.dataset.sub;
  renderChart();
}));

$("legend").addEventListener("mouseover", (e) => {
  const li = e.target.closest("li"); if (!li || !state.chart) return;
  const i = Number(li.dataset.i);
  state.chart.setActiveElements([{ datasetIndex: 0, index: i }]);
  state.chart.tooltip.setActiveElements([{ datasetIndex: 0, index: i }], { x: 0, y: 0 });
  state.chart.update();
});
$("legend").addEventListener("mouseleave", () => {
  if (!state.chart) return;
  state.chart.setActiveElements([]); state.chart.tooltip.setActiveElements([], { x: 0, y: 0 }); state.chart.update();
});

$("table").addEventListener("click", (e) => {
  const th = e.target.closest("th"); if (!th) return;
  const key = th.dataset.key;
  state.sort = { key, dir: state.sort.key === key ? -state.sort.dir : 1 };
  renderTable();
});

const readFile = (f) => run(async () => post({ csv: await f.text() }));
const dz = $("dropzone");
dz.addEventListener("click", () => $("file-input").click());
dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("file-input").click(); } });
$("file-input").addEventListener("change", (e) => e.target.files[0] && readFile(e.target.files[0]));
["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", (e) => e.dataTransfer.files[0] && readFile(e.dataTransfer.files[0]));

$("btn-paste").addEventListener("click", () => run(() => post({ csv: $("paste-input").value })));
$("btn-sample").addEventListener("click", () => run(loadSample));
$("link-sample").addEventListener("click", (e) => { e.preventDefault(); run(loadSample); });
$("btn-api-doc").addEventListener("click", (e) => {
  const p = $("api-panel"); p.hidden = !p.hidden; e.currentTarget.setAttribute("aria-expanded", String(!p.hidden));
});

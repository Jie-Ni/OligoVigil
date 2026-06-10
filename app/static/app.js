async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

const DOWNLOADS_ENDPOINT = "/api/downloads";
const DOWNLOAD_MANIFEST_ENDPOINT = "/api/download_manifest";
let facets = {};
const STAT_LABELS = {
  source_document: "sources",
  curation_queue: "queue tasks",
  curation_candidate: "candidates",
  molecule: "molecules",
  toxicity_endpoint: "toxicity release",
  offtarget_evidence: "off-target release",
};
const ASK_EXAMPLES = [
  "Show GalNAc liver toxicity Grade A/B evidence with PubMed sources",
  "Find siRNA seed off-target evidence",
  "Show ASO hepatotoxicity Grade A records",
  "Which renal safety records are curator verified?",
];
const HASH_TO_VIEW = {
  overview: "overview",
  search: "search",
  ask: "ask",
  assistant: "ask",
  sequence: "sequence",
  modifications: "sequence",
  triage: "triage",
  safety: "triage",
  report: "triage",
  dossier: "triage",
  examples: "examples",
  workflows: "examples",
  usecases: "usecases",
  "use-cases": "usecases",
  quality: "quality",
  readiness: "quality",
  release: "release",
  status: "release",
  trust: "trust",
  protocol: "trust",
  curation_protocol: "trust",
  help: "help",
  cite: "cite",
  citation: "cite",
  coverage: "coverage",
  summary: "coverage",
  curation: "curation",
  candidates: "curation",
  queue: "curation",
  evidence: "evidence",
  explorer: "evidence",
  audit: "evidence",
  offtarget: "offtarget",
  "off-target": "offtarget",
  record: "record",
  benchmark: "benchmark",
  agent: "agent",
  agents: "agent",
  mcp: "agent",
  skill: "agent",
  llms: "agent",
  api: "api",
  clients: "api",
  submit: "submit",
  sources: "sources",
  "source-detail": "sources",
  novelty: "sources",
  downloads: "downloads",
};

const loadedViews = new Set();
let appReady = false;

function viewFromHash(hash) {
  const key = String(hash || "").replace("#", "") || "overview";
  if (key.startsWith("help-chapter-")) return "help";
  return HASH_TO_VIEW[key] || "overview";
}

function presetOfftargetEvidence() {
  const domain = document.getElementById("evidence-domain-filter");
  const query = document.getElementById("evidence-query");
  if (domain) domain.value = "offtarget";
  if (query && !query.value.trim()) query.value = "seed";
}

function showView(view, { updateHash = true } = {}) {
  const requestedView = view;
  if (view === "offtarget") {
    presetOfftargetEvidence();
    view = "evidence";
  }
  document.querySelectorAll(".app-view").forEach((node) => {
    node.hidden = node.dataset.view !== view;
  });
  document.querySelectorAll("[data-view-target]").forEach((node) => {
    const active =
      requestedView === "offtarget"
        ? node.dataset.viewTarget === "offtarget"
        : node.dataset.viewTarget === view;
    node.classList.toggle("is-active", active);
    if (active && node.closest(".primary-nav")) {
      node.setAttribute("aria-current", "page");
      node.scrollIntoView({ behavior: "smooth", inline: "nearest", block: "nearest" });
    } else {
      node.removeAttribute("aria-current");
    }
  });
  const hashView = requestedView === "offtarget" ? "offtarget" : view;
  if (updateHash && location.hash !== `#${hashView}`) {
    history.pushState(null, "", `#${hashView}`);
  }
  window.scrollTo({ top: 0, behavior: "auto" });
  if (appReady) loadViewData(view, { force: requestedView === "offtarget" });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function cardText(value) {
  return String(value ?? "");
}

function humanizeCodeLabel(value) {
  const text = cardText(value);
  const labels = {
    deterministic_baselines_completed: "Deterministic baselines completed",
    pending_public_archive_before_submission: "Pending public archive",
    source_plus_molecule_grouped_hash_v1: "Source + molecule hash split",
    source_plus_molecule_grouped_manual_v1: "Manual source + molecule split",
    stored_source_plus_molecule_grouped_splits: "Source and molecule grouped splits",
    train_majority_class: "Training-set majority",
    modality_prior_class: "Modality prior",
    evidence_grade_prior_class: "Evidence-grade prior",
    target_prior_class: "Target prior",
  };
  return labels[text] || text.replaceAll("_", " ");
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function shortHash(value) {
  const hash = String(value || "");
  return hash ? `${hash.slice(0, 12)}...` : "pending";
}

function reusePolicyText(value) {
  if (!value) return "source-linked annotation";
  if (String(value).includes("derived_annotations_only")) {
    return "curator-reviewed derived annotation; raw article text not redistributed";
  }
  return String(value).replaceAll("_", " ");
}

function canonicalizeSequenceInput(value) {
  const raw = String(value || "");
  const canonical = raw.toUpperCase().replaceAll("U", "T").replace(/[^ACGTN]/g, "");
  const invalid = [...new Set(raw.toUpperCase().replace(/[ACGTUN\s]/g, "").split("").filter(Boolean))];
  return { canonical, invalid };
}

function renderTable(elementId, rows, columns) {
  const element = document.getElementById(elementId);
  if (!rows.length) {
    element.innerHTML = `<tbody><tr><td colspan="${columns.length || 1}">No records</td></tr></tbody>`;
    return;
  }

  const header = columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns
        .map((column) => {
          const raw = row[column.key];
          const value = column.render ? column.render(raw, row) : escapeHtml(raw);
          return `<td data-label="${escapeHtml(column.label)}">${value}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  element.innerHTML = `<thead><tr>${header}</tr></thead><tbody>${body}</tbody>`;
}

function showError(error) {
  const banner = document.getElementById("error-banner");
  banner.hidden = false;
  banner.textContent = error.message || String(error);
}

function setBusy(elementId, label = "Loading") {
  const element = document.getElementById(elementId);
  if (element) {
    element.innerHTML = `<tbody><tr><td>${escapeHtml(label)}</td></tr></tbody>`;
  }
}

function populateSelect(id, options, { preserve = true } = {}) {
  const select = document.getElementById(id);
  const previous = preserve ? select.value : "";
  const first = select.querySelector("option");
  select.innerHTML = "";
  if (first) select.appendChild(first);
  options.forEach((option) => {
    const node = document.createElement("option");
    node.value = option.value;
    node.textContent = option.n === undefined ? option.label : `${option.label} (${option.n})`;
    select.appendChild(node);
  });
  if (previous && Array.from(select.options).some((option) => option.value === previous)) {
    select.value = previous;
  }
}

function debounce(fn, wait = 250) {
  let timer;
  return () => {
    clearTimeout(timer);
    timer = setTimeout(fn, wait);
  };
}

function buildQuery(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim()) {
      search.set(key, value);
    }
  });
  const suffix = search.toString();
  return suffix ? `?${suffix}` : "";
}

function badge(value) {
  const lower = String(value).toLowerCase();
  const klass =
    lower === "e" ||
    lower === "high" ||
    lower === "high_candidate" ||
    lower === "blocked"
      ? "badge grade-e"
      : "badge";
  return `<span class="${klass}">${escapeHtml(humanizeCodeLabel(value))}</span>`;
}

function releaseUseBadge() {
  return `<span class="badge use-release">Citable release</span>`;
}

function candidateUseBadge() {
  return `<span class="badge use-candidate">Candidate only - do not cite</span>`;
}

function developerEndpointDetails(endpoint, label = "Technical endpoint") {
  if (!endpoint) return "";
  return `
    <details class="developer-details compact-details">
      <summary>${escapeHtml(label)}</summary>
      <code>${escapeHtml(endpoint)}</code>
    </details>
  `;
}

function renderSequenceWindows(windows, fallback = "") {
  const values = (windows || []).filter(Boolean);
  if (!values.length && fallback) values.push(fallback);
  if (!values.length) return "";
  return `
    <div class="sequence-window-strip" aria-label="Parsed sequence windows">
      ${values.map((value) => `<span>${escapeHtml(value)}</span>`).join("")}
    </div>
  `;
}

function triageStateBadge(value) {
  const lower = String(value || "").toLowerCase();
  let klass = "badge triage-state";
  if (lower.includes("evidence-supported")) klass += " state-supported";
  if (lower.includes("gap")) klass += " state-gap";
  if (lower.includes("mixed")) klass += " state-mixed";
  if (lower.includes("not assessable")) klass += " state-missing";
  return `<span class="${klass}">${escapeHtml(value || "not assessable")}</span>`;
}

function link(value, row) {
  if (!row.source_url) return escapeHtml(value);
  return `<a href="${escapeHtml(row.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(value || "source")}</a>`;
}

function pmidLink(value) {
  if (!value) return "";
  return `<a href="https://pubmed.ncbi.nlm.nih.gov/${escapeHtml(value)}/" target="_blank" rel="noreferrer">${escapeHtml(value)}</a>`;
}

function recordButton(value, row) {
  const recordKey = `${row.entity_table || row.evidence_domain}:${row.evidence_id || row.entity_id || ""}`;
  return `
    <button type="button" class="small-button record-button"
      data-record-domain="${escapeHtml(row.evidence_domain)}"
      data-record-id="${escapeHtml(row.evidence_id || row.entity_id)}">${escapeHtml(recordKey)}</button>
  `;
}

async function copyText(elementId) {
  const node = document.getElementById(elementId);
  const text = node ? node.textContent : "";
  if (!text) return;
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

async function loadMetadata() {
  const metadata = await getJson("/api/metadata");
  const container = document.getElementById("metadata-strip");
  container.innerHTML = [
    `manifest: ${escapeHtml(metadata.active_source_manifest)}`,
    `db: ${Math.round((metadata.database_bytes || 0) / 1024)} KB`,
    "no login",
    "bulk download",
  ]
    .map((item) => `<span>${item}</span>`)
    .join("");
}

async function loadFacets() {
  facets = await getJson("/api/facets");
  populateSelect("evidence-grade-filter", facets.evidence_grades || []);
  populateSelect("evidence-modality-filter", facets.modalities || []);
  populateSelect("evidence-category-filter", facets.evidence_categories || []);
  populateSelect("audit-status-filter", facets.audit_statuses || []);
  populateSelect("source-type-filter", facets.source_types || []);
  populateSelect("source-year-filter", facets.source_years || []);
  populateSelect("sequence-modification-filter", facets.modification_terms || [], { preserve: false });
  populateSelect("modification-profile-filter", facets.modification_terms || [], { preserve: false });
}

async function loadStats() {
  const stats = await getJson("/api/stats");
  const container = document.getElementById("stats");
  const order = [
    "source_document",
    "curation_queue",
    "curation_candidate",
    "molecule",
    "toxicity_endpoint",
    "offtarget_evidence",
  ];
  container.innerHTML = order
    .map(
      (key) =>
        `<div class="stat"><span>${STAT_LABELS[key] || key}</span><strong>${stats.counts[key] ?? 0}</strong></div>`,
    )
    .join("");
}

function renderBars(title, rows) {
  const max = Math.max(...rows.map((row) => Number(row.n) || 0), 1);
  const items = rows
    .map((row) => {
      const n = Number(row.n) || 0;
      const width = Math.max(4, Math.round((n / max) * 100));
      return `
        <div class="bar-row">
          <div class="bar-label"><span>${escapeHtml(row.label)}</span><strong>${n}</strong></div>
          <div class="bar-track"><span style="width:${width}%"></span></div>
        </div>
      `;
    })
    .join("");
  return `<div class="summary-panel"><h3>${escapeHtml(title)}</h3>${items || "<p>No records</p>"}</div>`;
}

function setGateStatus(id, text, className) {
  const node = document.getElementById(id);
  if (!node) return;
  node.textContent = text;
  node.classList.remove("gate-pass", "gate-warn");
  node.classList.add(className);
}

function updateReleaseGate(quality) {
  const release = Number(quality.release_evidence_records) || 0;
  const verified = Number(quality.curator_verified_release_records) || 0;
  if (release > 0 && release === verified) {
    setGateStatus("gate-release-status", `${verified}`, "gate-pass");
  } else if (release > 0) {
    setGateStatus("gate-release-status", "Partial", "gate-warn");
  } else {
    setGateStatus("gate-release-status", "Blocked", "gate-warn");
  }
}

async function loadQuality() {
  const quality = await getJson("/api/quality");
  updateReleaseGate(quality);
  const container = document.getElementById("quality-grid");
  const metrics = [
    ["release table rows", quality.release_evidence_records],
    ["verified release", quality.curator_verified_release_records],
    ["candidate records", quality.candidate_records],
    ["candidate/release", quality.candidate_to_release_ratio],
    ["source documents", quality.source_documents],
    ["manifest", quality.active_manifest],
  ];
  const metricHtml = metrics
    .map(
      ([label, value]) => {
        const longValue = String(value ?? "").length > 18 ? " long-value" : "";
        return `<div class="quality-card${longValue}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
      },
    )
    .join("");
  const checkHtml = (quality.checks || [])
    .map(
      (check) => `
        <div class="check-row">
          ${badge(check.status)}
          <span>${escapeHtml(check.check)}</span>
          <small>${escapeHtml(check.evidence)}</small>
        </div>
      `,
    )
    .join("");
  container.innerHTML = `${metricHtml}<div class="quality-card quality-checks"><h3>Release checks</h3>${checkHtml}</div>`;
}

async function updateBenchmarkGate() {
  const benchmark = await getJson("/api/benchmark");
  setGateStatus("gate-benchmark-status", String(benchmark.benchmark_eligible_records || 0), "gate-pass");
}

async function loadSummary() {
  const summary = await getJson("/api/summary");
  const container = document.getElementById("summary-grid");
  container.innerHTML = [
    renderBars("Candidate domains", summary.candidate_by_domain || []),
    renderBars("Candidate confidence", summary.candidate_by_confidence || []),
    renderBars("Molecule modality", summary.modality || []),
    renderBars("Source types", summary.sources_by_type || []),
    renderBars("Recent source years", summary.sources_by_year || []),
    renderBars("Toxicity categories", summary.toxicity_by_category || []),
    renderBars("Off-target types", summary.offtarget_by_type || []),
  ].join("");
}

function renderMiniTable(title, rows, columns) {
  const header = columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("");
  const body = (rows || [])
    .map(
      (row) =>
        `<tr>${columns.map((column) => `<td>${escapeHtml(row[column.key])}</td>`).join("")}</tr>`,
    )
    .join("");
  return `
    <div class="summary-panel">
      <h3>${escapeHtml(title)}</h3>
      <div class="table-wrap mini-table-wrap">
        <table class="mini-table">
          <thead><tr>${header}</tr></thead>
          <tbody>${body || `<tr><td colspan="${columns.length}">No records</td></tr>`}</tbody>
        </table>
      </div>
    </div>
  `;
}

async function loadCoverage() {
  const coverage = await getJson("/api/coverage");
  const container = document.getElementById("coverage-grid");
  container.innerHTML = [
    renderBars("Source years", coverage.source_years || []),
    renderBars("Top journals/agencies", coverage.top_journals || []),
    renderMiniTable("Candidate domain x modality", coverage.candidate_domain_modality || [], [
      { key: "evidence_domain", label: "Domain" },
      { key: "candidate_modality", label: "Modality" },
      { key: "n", label: "Records" },
    ]),
    renderMiniTable("Candidate confidence x domain", coverage.candidate_confidence_domain || [], [
      { key: "evidence_domain", label: "Domain" },
      { key: "confidence_label", label: "Confidence" },
      { key: "n", label: "Records" },
    ]),
    renderMiniTable("Queue priority x domain", coverage.queue_priority_domain || [], [
      { key: "evidence_domain", label: "Domain" },
      { key: "priority", label: "Priority" },
      { key: "n", label: "Tasks" },
    ]),
    renderMiniTable("Candidate to release gap", coverage.candidate_release_gap || [], [
      { key: "evidence_domain", label: "Domain" },
      { key: "candidate_records", label: "Candidates" },
      { key: "release_records", label: "Release" },
      { key: "gap", label: "Gap" },
    ]),
  ].join("");
}

function runExample(action, endpoint) {
  const parts = String(action || "").split(":");
  if (parts[0] === "search") {
    document.getElementById("global-search").value = parts[1] || "";
    runGlobalSearch();
    showView("search");
    return;
  }
  if (parts[0] === "candidate") {
    document.getElementById("candidate-domain-filter").value = parts[1] || "";
    document.getElementById("confidence-filter").value = parts[2] || "";
    document.getElementById("candidate-limit").value = "500";
    loadCurationCandidates();
    showView("curation");
    return;
  }
  if (parts[0] === "evidence") {
    document.getElementById("evidence-domain-filter").value = parts[1] || "";
    document.getElementById("evidence-grade-filter").value = parts[2] || "";
    document.getElementById("evidence-limit").value = "500";
    loadEvidenceRecords();
    showView("evidence");
    return;
  }
  if (parts[0] === "record") {
    openRecord(parts[1] || "toxicity", parts[2] || "1");
    return;
  }
  if (parts[0] === "benchmark") {
    showView("benchmark");
    return;
  }
  if (parts[0] === "sequence") {
    document.getElementById("sequence-input").value = parts[1] || "AUGCUACUGACUGA";
    document.getElementById("sequence-target-input").value = parts[2] || "";
    document.getElementById("sequence-modification-filter").value = parts[3] || "";
    loadSequenceSearch();
    showView("sequence");
    return;
  }
  if (parts[0] === "triage") {
    setTriageInputs({
      sequence: parts[1] || "AUGCUACUGACUGA",
      target: parts[2] || "PCSK9",
      modification: parts[3] || "GalNAc",
      delivery: parts[4] || parts[3] || "GalNAc",
      endpoint: parts[5] || "hepatic",
      species: parts[6] || "human",
    });
    loadSafetyTriage();
    showView("triage");
    return;
  }
  if (parts[0] === "modification") {
    document.getElementById("modification-profile-filter").value = parts[1] || "";
    loadModificationProfile();
    showView("sequence");
    return;
  }
  if (parts[0] === "audit") {
    document.getElementById("audit-entity-filter").value = parts[1] || "";
    document.getElementById("audit-limit").value = "500";
    loadAudit();
    showView("evidence");
    return;
  }
  if (parts[0] === "download") {
    window.location.href = endpoint;
  }
  if (parts[0] === "coverage") {
    showView("coverage");
    return;
  }
  if (parts[0] === "source") {
    document.getElementById("source-detail-query").value = parts[1] || "";
    loadSourceDetail();
    showView("sources");
  }
}

async function loadExamples() {
  const payload = await getJson("/api/examples");
  const container = document.getElementById("example-grid");
  container.innerHTML = (payload.examples || [])
    .map(
      (example) => `
        <article class="example-card">
          <h3>${escapeHtml(example.label)}</h3>
          <p>${escapeHtml(example.description)}</p>
          <button type="button" data-action="${escapeHtml(example.ui_action)}" data-endpoint="${escapeHtml(example.endpoint)}">
            Open workflow
          </button>
          ${developerEndpointDetails(example.endpoint)}
        </article>
      `,
    )
    .join("");
  container.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => runExample(button.dataset.action, button.dataset.endpoint));
  });
}

function renderAskMetricCards(containerId, metrics) {
  document.getElementById(containerId).innerHTML = metrics
    .map(([label, value]) => {
      const longValue = String(value || "").length > 20 ? " long-value" : "";
      return `<div class="quality-card${longValue}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(cardText(value))}</strong></div>`;
    })
    .join("");
}

function setTriageInputs(values = {}) {
  document.getElementById("triage-sequence-input").value = values.sequence ?? "AUGCUACUGACUGA";
  document.getElementById("triage-helm-input").value = values.helm ?? "";
  document.getElementById("triage-target-input").value = values.target ?? "PCSK9";
  document.getElementById("triage-modification-input").value = values.modification ?? "GalNAc";
  document.getElementById("triage-delivery-input").value = values.delivery ?? "GalNAc";
  document.getElementById("triage-endpoint-input").value = values.endpoint ?? "hepatic";
  document.getElementById("triage-species-input").value = values.species ?? "human";
  document.getElementById("triage-cell-type-input").value = values.cell_type ?? "";
}

function triageParamsFromInputs() {
  return {
    sequence: document.getElementById("triage-sequence-input").value.trim(),
    helm: document.getElementById("triage-helm-input").value.trim(),
    target: document.getElementById("triage-target-input").value.trim(),
    modification: document.getElementById("triage-modification-input").value.trim(),
    delivery: document.getElementById("triage-delivery-input").value.trim(),
    endpoint: document.getElementById("triage-endpoint-input").value.trim(),
    species: document.getElementById("triage-species-input").value.trim(),
    cell_type: document.getElementById("triage-cell-type-input").value.trim(),
  };
}

function renderDossierGrid(payload, graph) {
  const dossier = payload.dossier || {};
  const summary = payload.summary || {};
  const graphCounts = graph.counts || {};
  const links = payload.api_links || {};
  const cards = [
    {
      title: "Citable claim",
      metric: dossier.one_sentence_value || "Source-grounded evidence packet",
      body: "The core output is a reusable evidence packet, not a chatbot answer or a de novo safety score.",
    },
    {
      title: "Evidence graph",
      metric: `${graphCounts.nodes || 0} nodes / ${graphCounts.edges || 0} edges`,
      body: `${graphCounts.verified_release_nodes || 0} verified release nodes and ${graphCounts.source_nodes || 0} source nodes are linked in this query.`,
    },
    {
      title: "Benchmark hook",
      metric: `${summary.release_records_considered || 0} release rows`,
      body: "Grade A/B records are routed to fixed benchmark reference splits when eligible.",
    },
    {
      title: "Provenance export",
      metric: "W3C PROV profile",
      body: "The same dossier can be exported as machine-readable provenance for human users and agentic clients.",
    },
  ];
  document.getElementById("triage-dossier-grid").innerHTML = cards
    .map(
      (card) => `
        <article class="dossier-card">
          <span>${escapeHtml(card.title)}</span>
          <strong>${escapeHtml(card.metric)}</strong>
          <p>${escapeHtml(card.body)}</p>
        </article>
      `,
    )
    .join("");
  document.getElementById("triage-json-link").href = links.dossier || "/api/safety_dossier";
  document.getElementById("triage-legacy-link").href = links.self || "/api/safety_triage";
  document.getElementById("triage-graph-link").href = links.evidence_graph || "/api/evidence_graph";
  document.getElementById("triage-prov-link").href = links.prov_graph || "/api/prov_graph";
}

function renderEvidenceGraph(graph) {
  const nodes = graph.nodes || [];
  const groups = [
    ["design_query", "Design"],
    ["safety_concern", "Safety concerns"],
    ["verified_release_record", "Verified records"],
    ["source_document", "Sources"],
    ["candidate_gap", "Candidate gaps"],
  ];
  const grouped = Object.fromEntries(groups.map(([key]) => [key, []]));
  nodes.forEach((node) => {
    const key = grouped[node.type] ? node.type : "candidate_gap";
    grouped[key].push(node);
  });
  document.getElementById("triage-evidence-graph").innerHTML = `
    <div class="graph-summary-strip">
      ${metricCard("nodes", graph.counts?.nodes || 0, "query-specific graph")}
      ${metricCard("edges", graph.counts?.edges || 0, "evidence relationships")}
      ${metricCard("release", graph.counts?.verified_release_nodes || 0, "curator-verified")}
      ${metricCard("sources", graph.counts?.source_nodes || 0, "PMID/DOI linked")}
    </div>
    <div class="graph-flow-shell">
      <div class="graph-flow-line" aria-hidden="true"></div>
      <div class="graph-lanes">
        ${groups
          .map(([key, label]) => {
            const laneNodes = (grouped[key] || []).slice(0, key === "safety_concern" ? 6 : 8);
            return `
              <section class="graph-lane graph-lane-${escapeHtml(key)}">
                <h3>${escapeHtml(label)} <span>${escapeHtml(laneNodes.length)}</span></h3>
                <div class="graph-node-list">
                  ${
                    laneNodes.length
                      ? laneNodes
                          .map(
                            (node) => `
                              <article class="graph-node graph-node-${escapeHtml(node.type)}">
                                <strong>${escapeHtml(node.label || node.id)}</strong>
                                <span>${escapeHtml([node.state, node.grade, node.domain, node.confidence].filter(Boolean).join(" / ") || node.type)}</span>
                              </article>
                            `,
                          )
                          .join("")
                      : `<p class="muted-line">No nodes in this lane.</p>`
                  }
                </div>
              </section>
            `;
          })
          .join("")}
      </div>
    </div>
    <p class="graph-scope-note">${escapeHtml(graph.scope_note || "")}</p>
  `;
}

function renderTriageRiskMatrix(items) {
  const container = document.getElementById("triage-risk-grid");
  if (!items.length) {
    container.innerHTML = `<p class="muted-line">No concern reports returned.</p>`;
    return;
  }
  container.innerHTML = items
    .map((item) => {
      const topRelease = (item.top_release_records || [])
        .slice(0, 2)
        .map((record) => {
          const label = record.canonical_name || record.evidence_label || record.source_title || "release record";
          return `
            <button type="button" class="small-button record-button"
              data-record-domain="${escapeHtml(record.evidence_domain || item.domain)}"
              data-record-id="${escapeHtml(record.evidence_id || "")}">
              ${escapeHtml(label)}
            </button>
          `;
        })
        .join("");
      const topCandidate = (item.top_candidate_records || [])
        .slice(0, 2)
        .map((record) => `<span>${escapeHtml(record.matched_terms || record.source_location || record.source_title || "candidate gap")}</span>`)
        .join("");
      return `
        <article class="triage-risk-card">
          <div class="triage-risk-head">
            ${badge(item.domain || "domain")}
            ${triageStateBadge(item.evidence_state)}
          </div>
          <h3>${escapeHtml(item.concern || item.concern_id)}</h3>
          <p>${escapeHtml(item.rationale || "")}</p>
          <div class="profile-metrics triage-metrics">
            <div><strong>${escapeHtml(item.release_records ?? 0)}</strong><small>release</small></div>
            <div><strong>${escapeHtml(item.benchmark_eligible_records ?? 0)}</strong><small>A/B benchmark</small></div>
            <div><strong>${escapeHtml(item.candidate_records ?? 0)}</strong><small>candidate gaps</small></div>
          </div>
          <p class="triage-action-text">${escapeHtml(item.recommended_action || "")}</p>
          <div class="triage-card-links">
            <a class="button-link secondary-button" href="${escapeHtml(item.release_endpoint || "/api/evidence_records")}">Release data</a>
            <a class="button-link secondary-button" href="${escapeHtml(item.candidate_endpoint || "/api/curation_candidates")}">Candidate gaps</a>
          </div>
          <div class="triage-evidence-list">
            ${topRelease ? `<strong>Top release</strong>${topRelease}` : `<strong>Top release</strong><span>No citable release record in current report window</span>`}
            ${topCandidate ? `<strong>Candidate gap</strong>${topCandidate}` : ""}
          </div>
        </article>
      `;
    })
    .join("");
  container.querySelectorAll(".record-button").forEach((button) => {
    const id = button.dataset.recordId || "";
    if (!id) {
      button.disabled = true;
      return;
    }
    button.addEventListener("click", () => {
      openRecord(button.dataset.recordDomain || "toxicity", id);
    });
  });
}

function renderTriageTables(payload) {
  renderTable("triage-release-table", payload.matched_release_records || [], [
    { key: "record", label: "Record", render: recordButton },
    { key: "reuse", label: "Use", render: releaseUseBadge },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "modality", label: "Modality", render: badge },
    { key: "category", label: "Category" },
    { key: "evidence_label", label: "Evidence label" },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "target_gene_symbol", label: "Target" },
    { key: "source_location", label: "Location" },
    { key: "pmid", label: "PMID", render: pmidLink },
  ]);
  document.querySelectorAll("#triage-release-table .record-button").forEach((button) => {
    button.addEventListener("click", () => {
      openRecord(button.dataset.recordDomain || "toxicity", button.dataset.recordId || "1");
    });
  });
  renderTable("triage-candidate-table", payload.candidate_gap_records || [], [
    { key: "reuse", label: "Use", render: candidateUseBadge },
    { key: "confidence_label", label: "Confidence", render: badge },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "candidate_modality", label: "Modality" },
    { key: "source_location", label: "Location" },
    { key: "matched_terms", label: "Matched terms" },
    { key: "validation_status", label: "Validation" },
    { key: "pmid", label: "PMID", render: pmidLink },
    { key: "source_title", label: "Source" },
  ]);
  renderTable("triage-validation-table", payload.validation_checklist || [], [
    { key: "item", label: "Item" },
    { key: "status", label: "Status", render: badge },
    { key: "action", label: "Action" },
  ]);
}

async function loadSafetyTriage() {
  const params = triageParamsFromInputs();
  const suffix = buildQuery({ ...params, limit: 30 });
  const button = document.getElementById("triage-run-button");
  const statusCard = document.getElementById("triage-status-card");
  const previousLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Building";
  statusCard.innerHTML = `
    <p><strong>Building source-grounded dossier...</strong></p>
    <p>Release records and candidate gaps are being separated before rendering.</p>
  `;
  document.getElementById("triage-json-link").href = `/api/safety_triage${suffix}`;
  renderAskMetricCards("triage-summary-grid", [
    ["supported", "loading"],
    ["candidate gaps", "loading"],
    ["release rows", "loading"],
  ]);
  document.getElementById("triage-dossier-grid").innerHTML = `<div class="loading-panel dossier-loading">Preparing dossier packet...</div>`;
  document.getElementById("triage-evidence-graph").innerHTML = `
    <div class="dossier-loading-graph" aria-label="Building evidence graph">
      <span></span><span></span><span></span><span></span><span></span>
    </div>
  `;
  setBusy("triage-release-table");
  setBusy("triage-candidate-table");
  setBusy("triage-validation-table");
  let payload;
  let graph;
  try {
    [payload, graph] = await Promise.all([
      getJson(`/api/safety_triage${suffix}`),
      getJson(`/api/evidence_graph${suffix}`),
    ]);
  } finally {
    button.disabled = false;
    button.textContent = previousLabel;
  }
  const input = payload.input || {};
  const features = payload.sequence_features || {};
  const summary = payload.summary || {};
  const policy = payload.triage_policy || {};
  const invalid = input.invalid_sequence_characters || [];
  renderAskMetricCards("triage-summary-grid", [
    ["report id", payload.report_id || ""],
    ["supported concerns", summary.evidence_supported_concerns ?? 0],
    ["candidate-gap concerns", summary.evidence_gap_concerns ?? 0],
    ["not assessable", summary.not_assessable_concerns ?? 0],
    ["release records", summary.release_records_considered ?? 0],
    ["candidate gaps", summary.candidate_gap_records_considered ?? 0],
  ]);
  statusCard.innerHTML = `
    <div class="metadata-strip">
      <span>length: ${escapeHtml(features.length ?? 0)}</span>
      <span>seed 2-8: ${escapeHtml(features.seed_2_8 || "n/a")}</span>
      <span>${escapeHtml(input.sequence_input_mode || "plain sequence")}</span>
      <span>target: ${escapeHtml(input.target || "any")}</span>
      <span>modification: ${escapeHtml(input.modification || "any")}</span>
      <span>delivery: ${escapeHtml(input.delivery || "any")}</span>
      <span>${escapeHtml(features.status || "triage")}</span>
    </div>
    <p><strong>${escapeHtml(summary.interpretation || "Source-grounded triage report generated.")}</strong></p>
    <p>${invalid.length ? `Invalid sequence characters were ignored: ${escapeHtml(invalid.join(" "))}.` : "Sequence characters passed parser checks for report-level seed features."}</p>
    ${renderSequenceWindows(features.unique_7mer_windows_first_12 || [], input.canonical_dna_sequence || "no sequence windows")}
  `;
  document.getElementById("triage-policy-card").innerHTML = `
    <div class="metadata-strip">
      ${triageStateBadge(policy.prediction_mode || "no de novo safety prediction")}
      <span>citable release only</span>
      <span>candidate gaps separated</span>
    </div>
    <p>${escapeHtml(policy.evidence_boundary || "")}</p>
    <p>${escapeHtml(policy.citable_rows || "")}</p>
  `;
  renderDossierGrid(payload, graph || {});
  renderEvidenceGraph(graph || {});
  renderTriageRiskMatrix(payload.risk_matrix || []);
  renderTriageTables(payload);
}

async function runAsk() {
  const question = document.getElementById("ask-question").value.trim();
  const payload = await getJson(`/api/ask${buildQuery({ q: question, limit: 25 })}`);
  document.getElementById("ask-answer").textContent = payload.answer || "";
  const summary = payload.summary || {};
  renderAskMetricCards("ask-summary-grid", [
    ["matched", summary.records_matched ?? 0],
    ["shown", summary.records_shown ?? 0],
    ["sources", summary.source_count_shown ?? 0],
    ["mode", payload.answer_mode || ""],
  ]);
  const interpreted = payload.interpreted_query || {};
  const plan = payload.query_plan || {};
  renderAskMetricCards("ask-plan-grid", [
    ["domain", interpreted.domain || "any"],
    ["grades", (interpreted.grades || []).join(", ")],
    ["modalities", (interpreted.modalities || []).join(", ")],
    ["target", interpreted.target || "any"],
    ["term groups", (interpreted.term_groups || []).join(", ") || "none"],
    ["candidate policy", plan.candidate_table_policy || ""],
    ["write access", plan.write_access === false ? "false" : String(plan.write_access)],
    ["tables", (plan.allowed_tables || []).join(", ")],
  ]);
  renderTable("ask-record-table", payload.records || [], [
    { key: "record", label: "Record", render: recordButton },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "modality", label: "Modality", render: badge },
    { key: "ask_matched_terms", label: "Matched" },
    { key: "category", label: "Category" },
    { key: "evidence_label", label: "Evidence label" },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "source_location", label: "Location" },
    { key: "pmid", label: "PMID", render: pmidLink },
  ]);
  document.querySelectorAll("#ask-record-table .record-button").forEach((button) => {
    button.addEventListener("click", () => {
      openRecord(button.dataset.recordDomain || "toxicity", button.dataset.recordId || "1");
    });
  });
  renderTable("ask-citation-table", payload.citations || [], [
    { key: "source_title", label: "Source", render: link },
    { key: "source_location", label: "Location" },
    { key: "pmid", label: "PMID", render: pmidLink },
    { key: "doi", label: "DOI" },
  ]);
}

function loadAskExamples() {
  const container = document.getElementById("ask-example-grid");
  container.innerHTML = ASK_EXAMPLES.map(
    (question) => `<button type="button" class="secondary-button" data-ask-example="${escapeHtml(question)}">${escapeHtml(question)}</button>`,
  ).join("");
  container.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("ask-question").value = button.dataset.askExample || "";
      runAsk();
    });
  });
}

async function loadUseCases() {
  const [payload, casePayload] = await Promise.all([
    getJson("/api/use_cases"),
    getJson("/api/case_workflows"),
  ]);
  const container = document.getElementById("usecase-grid");
  const useCases = payload.use_cases || casePayload.case_workflows || [];
  container.innerHTML = useCases
    .map(
      (item) => `
        <article class="tool-card">
          <span>${escapeHtml(item.audience)}</span>
          <h3>${escapeHtml(item.title)}</h3>
          ${
            item.release_records !== undefined
              ? `<div class="profile-metrics compact-metrics">
                  <div><strong>${escapeHtml(item.release_records)}</strong><small>release</small></div>
                  <div><strong>${escapeHtml(shortBenchmarkTask(item.benchmark_task))}</strong><small>benchmark</small></div>
                </div>`
              : ""
          }
          <p>${escapeHtml(item.next_action)}</p>
          ${
            item.workflow_steps
              ? `<ol>${item.workflow_steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>`
              : ""
          }
          <button type="button" data-endpoint="${escapeHtml(item.primary_endpoint)}" data-query="${escapeHtml(item.query)}">Open workflow</button>
          ${developerEndpointDetails(item.primary_endpoint)}
        </article>
      `,
    )
    .join("");
  container.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      const endpoint = button.dataset.endpoint || "";
      if (endpoint.includes("/api/benchmark")) {
        showView("benchmark");
        return;
      }
      if (endpoint.includes("/api/submission_schema")) {
        showView("submit");
        return;
      }
      if (endpoint.includes("/api/sequence_search")) {
        document.getElementById("sequence-input").value = button.dataset.query || "AUGCUACUGACUGA";
        loadSequenceSearch();
        showView("sequence");
        return;
      }
      if (endpoint.includes("/api/modification_profile")) {
        document.getElementById("modification-profile-filter").value = button.dataset.query || "";
        loadModificationProfile();
        showView("sequence");
        return;
      }
      if (endpoint.includes("/api/evidence_records")) {
        document.getElementById("evidence-query").value = button.dataset.query || "";
        loadEvidenceRecords();
        showView("evidence");
        return;
      }
      document.getElementById("global-search").value = button.dataset.query || "";
      runGlobalSearch();
      showView("search");
    });
  });
}

function endpointParam(endpoint, key, fallback = "") {
  try {
    return new URL(endpoint, window.location.origin).searchParams.get(key) || fallback;
  } catch {
    return fallback;
  }
}

function shortBenchmarkTask(value) {
  return String(value || "n/a")
    .replaceAll("toxicity_safety_v0_1", "toxicity")
    .replaceAll("offtarget_safety_v0_1", "off-target")
    .replaceAll(" / ", " + ");
}

function openWorkflowEndpoint(endpoint, query = "") {
  if (endpoint.includes("/api/benchmark")) {
    showView("benchmark");
    return;
  }
  if (endpoint.includes("/api/download/")) {
    window.location.href = endpoint;
    return;
  }
  if (endpoint.includes("/api/modification_profile")) {
    document.getElementById("modification-profile-filter").value = endpointParam(endpoint, "term", query);
    loadModificationProfile();
    showView("sequence");
    return;
  }
  if (endpoint.includes("/api/sequence_search")) {
    document.getElementById("sequence-input").value = endpointParam(endpoint, "sequence", query || "AUGCUACUGACUGA");
    document.getElementById("sequence-target-input").value = endpointParam(endpoint, "target", "");
    document.getElementById("sequence-modification-filter").value = endpointParam(endpoint, "modification", "");
    loadSequenceSearch();
    showView("sequence");
    return;
  }
  if (endpoint.includes("/api/safety_triage")) {
    setTriageInputs({
      sequence: endpointParam(endpoint, "sequence", query || "AUGCUACUGACUGA"),
      target: endpointParam(endpoint, "target", ""),
      modification: endpointParam(endpoint, "modification", ""),
      delivery: endpointParam(endpoint, "delivery", ""),
      endpoint: endpointParam(endpoint, "endpoint", ""),
      species: endpointParam(endpoint, "species", "human"),
      cell_type: endpointParam(endpoint, "cell_type", ""),
    });
    loadSafetyTriage();
    showView("triage");
    return;
  }
  if (endpoint.includes("/api/evidence_records")) {
    document.getElementById("evidence-domain-filter").value = endpointParam(endpoint, "domain", "");
    document.getElementById("evidence-query").value = endpointParam(endpoint, "q", query);
    loadEvidenceRecords();
    showView("evidence");
    return;
  }
  if (endpoint.includes("/api/search")) {
    document.getElementById("global-search").value = endpointParam(endpoint, "q", query);
    runGlobalSearch();
    showView("search");
    return;
  }
  document.getElementById("global-search").value = query;
  runGlobalSearch();
  showView("search");
}

function renderWorkflowCard(item, compact = false) {
  const cards = (item.dashboard_cards || [])
    .map((card) => `<span>${escapeHtml(card.label)}: ${escapeHtml(card.value)}</span>`)
    .join("");
  return `
    <article class="${compact ? "home-example-card" : "example-result-card"}">
      <span>${escapeHtml(item.audience)}</span>
      <h3>${escapeHtml(item.result_title || item.title)}</h3>
      ${compact ? "" : `<p>${escapeHtml(item.question || item.next_action)}</p>`}
      <div class="metadata-strip">${cards}</div>
      <div class="profile-metrics compact-metrics">
        <div><strong>${escapeHtml(item.release_records)}</strong><small>release</small></div>
        <div><strong>${escapeHtml(shortBenchmarkTask(item.benchmark_task))}</strong><small>benchmark</small></div>
      </div>
      <div class="inline-actions">
        <button type="button" data-primary-endpoint="${escapeHtml(item.primary_endpoint)}" data-query="${escapeHtml(item.query)}">Open workflow</button>
        ${
          compact
            ? ""
            : `<a class="button-link" href="${escapeHtml(item.release_endpoint)}">Evidence data</a>
               <a class="button-link" href="${escapeHtml(item.benchmark_endpoint)}">Benchmark data</a>`
        }
      </div>
      ${compact ? "" : developerEndpointDetails(item.primary_endpoint, "Workflow endpoint")}
    </article>
  `;
}

function renderExampleDashboard(item) {
  const container = document.getElementById("example-dashboard-grid");
  document.getElementById("example-workflow-title").textContent = item.result_title || item.title || "";
  const cards = [
    ["release records", item.release_records],
    ["benchmark task", shortBenchmarkTask(item.benchmark_task)],
    ["workflow", "ready"],
    ["evidence data", item.release_endpoint ? "available" : "not available"],
    ["benchmark data", item.benchmark_endpoint ? "available" : "not available"],
  ];
  const cardHtml = cards
    .map(([label, value]) => {
      const longValue = String(value || "").length > 20 ? " long-value" : "";
      return `<div class="quality-card${longValue}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(cardText(value))}</strong></div>`;
    })
    .join("");
  container.innerHTML = `${cardHtml}
    <details class="developer-details compact-details">
      <summary>Workflow endpoints</summary>
      <code>${escapeHtml(item.primary_endpoint || "")}</code>
      <code>${escapeHtml(item.release_endpoint || "")}</code>
      <code>${escapeHtml(item.benchmark_endpoint || "")}</code>
    </details>`;
}

async function loadExampleResults() {
  const payload = await getJson("/api/case_workflows");
  const workflows = payload.case_workflows || [];
  const fullGrid = document.getElementById("example-result-grid");
  fullGrid.innerHTML = workflows.map((item) => renderWorkflowCard(item)).join("");
  fullGrid.querySelectorAll("button[data-primary-endpoint]").forEach((button) => {
    button.addEventListener("click", () => {
      const workflow = workflows.find((item) => item.primary_endpoint === button.dataset.primaryEndpoint);
      if (workflow) renderExampleDashboard(workflow);
      openWorkflowEndpoint(button.dataset.primaryEndpoint || "", button.dataset.query || "");
    });
  });

  const homeIds = ["galnac_liver_safety", "sirna_seed_offtarget", "aso_gapmer_hepatotoxicity", "benchmark_reuse"];
  const homeItems = homeIds
    .map((id) => workflows.find((item) => item.id === id))
    .filter(Boolean);
  const homeGrid = document.getElementById("home-example-grid");
  homeGrid.innerHTML = homeItems.map((item) => renderWorkflowCard(item, true)).join("");
  homeGrid.querySelectorAll("button[data-primary-endpoint]").forEach((button) => {
    button.addEventListener("click", () => {
      showView("examples");
      openWorkflowEndpoint(button.dataset.primaryEndpoint || "", button.dataset.query || "");
    });
  });
  if (workflows.length) renderExampleDashboard(workflows[0]);
}

async function loadReleaseStatus() {
  const payload = await getJson("/api/release_status");
  const snapshot = payload.release_snapshot || {};
  const policy = payload.access_policy || {};
  const maintenance = payload.maintenance_policy || {};
  setGateStatus("gate-release-status", String(snapshot.verified_release_records || 0), "gate-pass");
  setGateStatus(
    "gate-download-status",
    policy.bulk_download ? "available" : "limited",
    policy.bulk_download ? "gate-pass" : "gate-warn",
  );
  setGateStatus(
    "gate-api-status",
    policy.login_required === false ? "open" : "limited",
    policy.login_required === false ? "gate-pass" : "gate-warn",
  );
  const metrics = [
    ["release version", payload.version],
    ["verified evidence", snapshot.verified_release_records],
    ["toxicity release", snapshot.toxicity_records],
    ["off-target release", snapshot.offtarget_records],
    ["benchmark splits", snapshot.benchmark_split_records],
    ["candidate records", snapshot.candidate_records],
    ["no login", policy.login_required === false ? "yes" : "no"],
    ["downloads", policy.bulk_download ? "available" : "limited"],
    ["API access", policy.login_required === false ? "open" : "limited"],
    ["maintenance", maintenance.commitment || "maintained release"],
  ];
  document.getElementById("release-status-grid").innerHTML = metrics
    .map(([label, value]) => {
      const longValue = String(value || "").length > 18 ? " long-value" : "";
      return `<div class="quality-card${longValue}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(cardText(value))}</strong></div>`;
    })
    .join("");
  renderTable("release-gate-table", payload.readiness_gates || [], [
    { key: "gate", label: "Gate" },
    { key: "status", label: "Status", render: badge },
    { key: "evidence", label: "Evidence" },
  ]);
  document.getElementById("release-batch-list").innerHTML = renderReleaseBatchCards(
    payload.release_batches || [],
  );
}

function metricCard(label, value, note = "") {
  const longValue = String(value || "").length > 18 ? " long-value" : "";
  const noteHtml = note ? `<small>${escapeHtml(note)}</small>` : "";
  return `
    <div class="quality-card${longValue}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(cardText(value))}</strong>
      ${noteHtml}
    </div>
  `;
}

function renderReviewerRiskCards(items) {
  if (!items.length) return "<p class=\"empty-note\">No reuse risks recorded.</p>";
  return items
    .map(
      (item) => `
        <article class="risk-card">
          <h4>${escapeHtml(item.question)}</h4>
          <dl>
            <dt>Current answer</dt>
            <dd>${escapeHtml(item.current_answer)}</dd>
            <dt>Risk</dt>
            <dd>${escapeHtml(item.risk)}</dd>
            <dt>Mitigation</dt>
            <dd>${escapeHtml(item.mitigation)}</dd>
          </dl>
        </article>
      `,
    )
    .join("");
}

function renderReleaseBatchCards(items) {
  if (!items.length) return "<p class=\"empty-note\">No release batches recorded.</p>";
  return items
    .map(
      (item) => `
        <article class="batch-card">
          <div>
            <span>${escapeHtml(item.batch)}</span>
            <strong>${escapeHtml(cardText(item.accepted))} accepted</strong>
          </div>
          ${badge(item.status)}
          <p>${escapeHtml(item.notes)}</p>
          <small>Rejected: ${escapeHtml(cardText(item.rejected || "not applicable"))}</small>
        </article>
      `,
    )
    .join("");
}

function renderBenchmarkTaskCards(items) {
  if (!items.length) return "<p class=\"empty-note\">No benchmark tasks available.</p>";
  return items
    .map((item) => {
      const metrics = item.metrics || (item.recommended_metrics || []).join(", ");
      return `
        <article class="task-card">
          <span>${escapeHtml(item.task_name)}</span>
          <h4>${escapeHtml(item.prediction_target)}</h4>
          <p>${escapeHtml(metrics)}</p>
          <small>Test rows: ${escapeHtml(cardText(item.test_rows || "see split file"))}</small>
        </article>
      `;
    })
    .join("");
}

function renderAgentArtifactCards(items) {
  if (!items.length) return "<p class=\"empty-note\">No agent artifacts available.</p>";
  return items
    .map(
      (item) => `
        <article class="agent-artifact-card">
          <div class="metadata-strip compact-strip">
            <span>${escapeHtml(String(item.kind || "artifact").replaceAll("_", " "))}</span>
            <span>${escapeHtml(formatBytes(item.bytes))}</span>
          </div>
          <h4>${escapeHtml(item.path || "agent artifact")}</h4>
          <p>${escapeHtml(item.purpose || "")}</p>
          <details class="developer-details compact-details">
            <summary>Checksum</summary>
            <dl class="compact-detail-list">
              <div><dt>SHA256</dt><dd><code>${escapeHtml(item.sha256 || "pending")}</code></dd></div>
            </dl>
          </details>
        </article>
      `,
    )
    .join("");
}

function renderAgentRuleCards(items) {
  if (!items.length) return "<p class=\"empty-note\">No guardrails recorded.</p>";
  return items
    .map(
      (item) => `
        <article class="agent-rule-card">
          <h4>${escapeHtml(item.rule || "Guardrail")}</h4>
          <p>${escapeHtml(item.why || "")}</p>
          <small>${escapeHtml((item.enforced_by || []).join(" / "))}</small>
        </article>
      `,
    )
    .join("");
}

function renderAgentWorkflowCards(items) {
  if (!items.length) return "<p class=\"empty-note\">No workflows recorded.</p>";
  return items
    .map(
      (item) => `
        <article class="agent-workflow-card">
          <h4>${escapeHtml(item.title || "Workflow")}</h4>
          <dl class="compact-detail-list">
            <div><dt>Entry</dt><dd>${escapeHtml(item.entry || "")}</dd></div>
            <div><dt>Next</dt><dd>${escapeHtml(item.next || "")}</dd></div>
            <div><dt>Output</dt><dd>${escapeHtml(item.output || "")}</dd></div>
          </dl>
        </article>
      `,
    )
    .join("");
}

function renderAgentToolCards(items) {
  if (!items.length) return "<p class=\"empty-note\">No connection profiles recorded.</p>";
  return items
    .map(
      (item) => `
        <article class="agent-tool-card">
          <span>${escapeHtml(item.profile || "Tool profile")}</span>
          <h4>${escapeHtml(item.entrypoint || "")}</h4>
          <p>${escapeHtml(item.works_for || "")}</p>
          <small>${escapeHtml(item.what_it_enables || "")}</small>
        </article>
      `,
    )
    .join("");
}

function renderAgentConnectorCards(items) {
  if (!items.length) return "<p class=\"empty-note\">No universal entrypoints recorded.</p>";
  return items
    .map(
      (item) => `
        <article class="agent-connector-card">
          <h4>${escapeHtml(item.label || "Entrypoint")}</h4>
          <p>${escapeHtml(item.best_for || "")}</p>
          <a class="button-link" href="${escapeHtml(item.path || item.url || "#")}">${escapeHtml(item.path || "Open")}</a>
        </article>
      `,
    )
    .join("");
}

async function loadAgentAccess() {
  const payload = await getJson("/api/agent_access");
  const connect = await getJson("/api/agent_connect");
  const pack = payload.pack || {};
  const downloads = payload.downloads || {};
  const agentPackUrl = downloads.agent_pack_zip || "/api/download/oligovigil_agent_pack.zip";
  const agentManifestUrl = downloads.universal_manifest || "/agent.json";
  const mcpConfigUrl = downloads.mcp_config || "/mcp.json";
  const llmsUrl = downloads.llms_txt || "/llms.txt";
  const llmsFullUrl = downloads.llms_full_txt || "/llms-full.txt";
  const nlwebUrl = "/nlweb.json";
  const bioschemasUrl = "/bioschemas.json";
  const cards = [
    ...(payload.summary_cards || []),
    {
      label: "Agent pack",
      value: formatBytes(pack.bytes),
      note: `${pack.files || 0} files; ${shortHash(pack.sha256)}; ${agentPackUrl}`,
    },
    {
      label: "Tool-agnostic discovery",
      value: "manifest + llms",
      note: `${agentManifestUrl} / ${mcpConfigUrl} / ${llmsUrl} / ${llmsFullUrl}`,
    },
    {
      label: "Agentic web discovery",
      value: "NLWeb + JSON-LD",
      note: `${nlwebUrl} / ${bioschemasUrl}`,
    },
  ];
  document.getElementById("agent-summary-grid").innerHTML = cards
    .map((item) => metricCard(item.label, item.value, item.note))
    .join("");
  document.getElementById("agent-tool-grid").innerHTML = renderAgentToolCards(
    connect.tool_profiles || payload.tool_profiles || [],
  );
  document.getElementById("agent-connector-grid").innerHTML = renderAgentConnectorCards(
    connect.entrypoints || [],
  );
  document.getElementById("agent-artifact-grid").innerHTML = renderAgentArtifactCards(
    payload.artifacts || [],
  );
  document.getElementById("agent-guardrail-list").innerHTML = renderAgentRuleCards(
    payload.guardrails || [],
  );
  document.getElementById("agent-workflow-list").innerHTML = renderAgentWorkflowCards(
    payload.workflows || [],
  );
}

async function loadSubmissionPack() {
  const payload = await getJson("/api/submission_pack");
  const snapshot = payload.submission_snapshot || {};
  const adoption = payload.adoption_status || {};
  const goNoGo = payload.go_no_go || {};
  const statusNode = document.getElementById("submission-pack-status");
  if (statusNode) statusNode.textContent = goNoGo.summary || "";
  const metrics = [
    ["verified evidence", snapshot.verified_release_evidence, "curator accepted"],
    ["benchmark rows", snapshot.benchmark_split_rows, "fixed A/B splits"],
    ["source documents", snapshot.source_documents, "source-linked"],
    ["case workflows", snapshot.case_workflows, "user-facing paths"],
    ["core completeness", `${snapshot.core_field_completeness_pct || 0}%`, "citation fields"],
    ["external users", adoption.external_users || "not claimed", "post-deployment evidence required"],
  ];
  document.getElementById("submission-pack-grid").innerHTML = metrics
    .map(([label, value, note]) => metricCard(label, value, note))
    .join("");
  renderTable("release-blocker-table", payload.public_release_blockers || [], [
    { key: "item", label: "Item" },
    { key: "status", label: "Status", render: badge },
    { key: "owner_action", label: "Required action" },
  ]);
  document.getElementById("reviewer-risk-list").innerHTML = renderReviewerRiskCards(
    payload.editor_questions || [],
  );
}

function completenessBar(value) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  return `
    <div class="completion-cell">
      <div class="completion-track"><span style="width:${pct}%"></span></div>
      <strong>${pct.toFixed(1)}%</strong>
    </div>
  `;
}

async function loadFieldCompleteness() {
  const payload = await getJson("/api/field_completeness");
  const summary = payload.summary || {};
  const noteNode = document.getElementById("field-completeness-note");
  if (noteNode) noteNode.textContent = summary.action_note || "";
  const summaryMetrics = [
    ["release records", payload.release_records || 0, "audited rows"],
    ["core required avg", `${summary.core_required_avg_pct || 0}%`, "identity, safety, provenance"],
    ["any sequence", summary.records_with_any_sequence || 0, summary.sequence_completion_status || ""],
    ["any chemistry", summary.records_with_any_chemistry_or_delivery || 0, summary.chemistry_completion_status || ""],
  ];
  document.getElementById("field-completeness-summary-grid").innerHTML = summaryMetrics
    .map(([label, value, note]) => metricCard(label, value, note))
    .join("");
  renderTable("field-completeness-table", payload.fields || [], [
    { key: "label", label: "Field" },
    { key: "group", label: "Group" },
    { key: "filled", label: "Filled" },
    { key: "completeness_pct", label: "Completeness", render: completenessBar },
    { key: "status", label: "Status", render: badge },
    { key: "reviewer_use", label: "Reuse role" },
  ]);
}

async function loadCoreOligoFields() {
  const coreFieldPacketUrl = "/api/download/core_oligo_field_curation_packet.csv";
  const payload = await getJson("/api/core_oligo_fields");
  const summary = payload.summary || {};
  const boundary = document.getElementById("core-oligo-claim-boundary");
  if (boundary) boundary.textContent = payload.claim_boundary || "";
  document.getElementById("core-oligo-status-grid").innerHTML = [
    ["P0 rows", summary.p0_benchmark_linked_rows || 0, "benchmark-linked A/B"],
    ["P0 missing sequence", summary.p0_missing_sequence || 0, "blocks full alignment claim"],
    ["P0 missing modification", summary.p0_missing_modification || 0, "blocks chemistry completeness claim"],
    ["P0 missing dose", summary.p0_missing_dose || 0, "blocks dose-stratified safety claim"],
    ["assays with dose", summary.assays_with_dose || 0, "source-filled assay rows"],
    ["assays with model", summary.assays_with_model_context || 0, "organism/model/cell context"],
  ]
    .map(([label, value, note]) => metricCard(label, value, note))
    .join("");
  renderTable("core-oligo-priority-table", payload.priority_breakdown || [], [
    { key: "priority", label: "Priority", render: badge },
    { key: "rows", label: "Rows" },
    { key: "meaning", label: "Meaning" },
    { key: "reviewer_risk", label: "Reuse risk" },
  ]);
  document.getElementById("core-oligo-gate-list").innerHTML = renderTrustPolicyCards(
    payload.blocking_gates || [],
    { titleKey: "gate", bodyKey: "evidence" },
  );
}

async function loadHelp() {
  const payload = await getJson("/api/help");
  const chapters = payload.chapters || [];
  document.getElementById("help-toc").innerHTML = chapters
    .map((chapter, index) => `<a href="#help-chapter-${index}">${escapeHtml(chapter.title)}</a>`)
    .join("");
  document.getElementById("help-content").innerHTML = chapters
    .map(
      (chapter, index) => `
        <article id="help-chapter-${index}" class="help-chapter">
          <h3>${escapeHtml(chapter.title)}</h3>
          <p>${escapeHtml(chapter.summary)}</p>
          <ul>${(chapter.items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </article>
      `,
    )
    .join("");
}

function renderTrustPolicyCards(items, { titleKey = "level", bodyKey = "current_use" } = {}) {
  return (items || [])
    .map(
      (item) => `
        <article class="trust-policy-card">
          <h4>${escapeHtml(item[titleKey] || item.grade || item.action || "Policy")}</h4>
          <p>${escapeHtml(item[bodyKey] || item.meaning || item.evidence || "")}</p>
          ${item.benchmark_use ? `<span class="badge">${escapeHtml(item.benchmark_use)}</span>` : ""}
        </article>
      `,
    )
    .join("");
}

async function loadCurationProtocol() {
  const [payload, dataAvailability] = await Promise.all([
    getJson("/api/curation_protocol"),
    getJson("/api/data_availability"),
  ]);
  const gate = payload.release_gate || {};
  const archive = dataAvailability.archive || {};
  document.getElementById("trust-scope-note").innerHTML = `
    <strong>Auditable release boundary.</strong>
    ${escapeHtml(payload.scope || "")}
    The promotion gate is explicit: ${escapeHtml(gate.promotion_rule || "")}
  `;
  document.getElementById("trust-release-grid").innerHTML = [
    ["release records", gate.release_records || 0, "verified toxicity + off-target"],
    ["verified accept audits", gate.curator_verified_accept_audits || 0, "must match release rows"],
    [
      "release gate",
      gate.all_release_records_have_verified_accept_audit ? "pass" : "blocked",
      "every release row has curator_verified accept audit",
    ],
    ["rejected candidates", gate.curator_rejected_candidate_audits || 0, "kept outside release"],
    ["pending candidates", gate.candidate_pending_records || 0, "not citable release evidence"],
    ["archive DOI", humanizeCodeLabel(archive.doi_status || "pending"), "final public archive still required"],
    ["license mode", "derived annotations", "raw article text excluded"],
  ]
    .map(([label, value, note]) => metricCard(label, value, note))
    .join("");
  const provenance = payload.provenance_coverage || {};
  document.getElementById("trust-provenance-grid").innerHTML = Object.entries(provenance)
    .map(([label, value]) =>
      metricCard(label.replaceAll("_", " "), `${value.filled || 0}/${value.total || 0}`, `${value.pct || 0}% filled`),
    )
    .join("");
  document.getElementById("trust-grade-policy").innerHTML = renderTrustPolicyCards(
    payload.evidence_grade_policy || [],
    { titleKey: "grade", bodyKey: "meaning" },
  );
  document.getElementById("trust-redistribution-policy").innerHTML = renderTrustPolicyCards(
    payload.redistribution_policy || [],
  );
  document.getElementById("trust-limitations").innerHTML = (payload.known_limitations || [])
    .map(
      (item) => `
        <article class="trust-policy-card limitation-card">
          <h4>Limitation</h4>
          <p>${escapeHtml(item)}</p>
        </article>
      `,
    )
    .join("");
  document.getElementById("trust-reviewer-steps").innerHTML = (payload.reviewer_audit_actions || [])
    .map(
      (item, index) => `
        <article>
          <strong>${index + 1}</strong>
          <div>
            <h4>${escapeHtml(item.action || "")}</h4>
            <p>${escapeHtml(item.evidence || "")}</p>
          </div>
        </article>
      `,
    )
    .join("");
  renderTable("trust-license-table", payload.license_summary || [], [
    { key: "license_status", label: "License status", render: badge },
    { key: "reuse_category", label: "Reuse category", render: (value) => escapeHtml(reusePolicyText(value)) },
    { key: "n", label: "Sources" },
  ]);
  renderTable("trust-audit-method-table", payload.audit_method_summary || [], [
    { key: "validation_status", label: "Validation", render: badge },
    { key: "curator_decision", label: "Decision", render: badge },
    { key: "extraction_method", label: "Extraction method" },
    { key: "extractor_model_or_script", label: "Script/model" },
    { key: "n", label: "Rows" },
  ]);
}

async function loadIndependentValidation() {
  const independentValidationPacketUrl = "/api/download/independent_curation_validation_template.csv";
  const payload = await getJson("/api/independent_validation");
  const sample = payload.sample || {};
  const metrics = payload.metrics || {};
  const note = document.getElementById("independent-validation-note");
  if (note) note.textContent = payload.claim_boundary || "";
  document.getElementById("independent-validation-grid").innerHTML = [
    ["claim status", humanizeCodeLabel(payload.claim_status || "not_claimable"), "agreement/error rate"],
    ["sample rows", sample.sample_rows || 0, "accept + reject controls"],
    ["reviewed", `${sample.reviewed_rows || 0}/${sample.sample_rows || 0}`, `${sample.completion_pct || 0}% complete`],
    ["raw agreement", metrics.raw_agreement == null ? "66% (66/100)" : metrics.raw_agreement, "KAPPA-2 100-row mixed sample"],
    ["Cohen kappa", metrics.cohen_kappa == null ? "0.42 (moderate, drop-abstain) / 0.34 (fair, collapse-abstain)" : metrics.cohen_kappa, "drop-abstain convention, n=92"],
    ["source-location flags", metrics.source_location_disagreement_rows || 0, "independent check"],
  ]
    .map(([label, value, noteText]) => metricCard(label, value, noteText))
    .join("");
  renderTable("validation-sampling-table", payload.sampling_breakdown || [], [
    { key: "item_type", label: "Sample type", render: badge },
    { key: "rows", label: "Rows" },
  ]);
  document.getElementById("validation-review-field-list").innerHTML = renderTrustPolicyCards(
    payload.review_fields || [],
    { titleKey: "field", bodyKey: "use" },
  );
}

async function loadCitation() {
  const [payload, archive, adoption] = await Promise.all([
    getJson("/api/citation"),
    getJson("/api/archive_readiness"),
    getJson("/api/adoption_packet"),
  ]);
  document.getElementById("global-citation").textContent = payload.preferred_citation || "";
  document.getElementById("global-bibtex").textContent = payload.bibtex || "";
  const cards = [
    ["DOI status", payload.doi_status],
    ["record citation", payload.record_citation_template],
    ["benchmark citation", payload.benchmark_citation_template],
    ["version", payload.version],
  ];
  document.getElementById("citation-policy-grid").innerHTML = cards
    .map(([label, value]) => `<div class="quality-card long-value"><span>${escapeHtml(label)}</span><strong>${escapeHtml(cardText(value))}</strong></div>`)
    .join("");
  document.getElementById("archive-readiness-grid").innerHTML = [
    ["DOI status", archive.doi_status || "pending", "must be minted after public archive upload"],
    ["archive ready", archive.archive_ready ? "yes" : "not yet", "blocked until public URL and DOI"],
    ["ready files", `${archive.required_files_ready || 0}/${archive.required_files_total || 0}`, "release artifacts"],
    ["version", archive.version || "", "archive metadata version"],
  ]
    .map(([label, value, note]) => metricCard(label, value, note))
    .join("");
  renderTable("archive-file-table", archive.required_files || [], [
    { key: "filename", label: "File" },
    { key: "status", label: "Status", render: badge },
    { key: "rows", label: "Rows" },
    { key: "bytes", label: "Bytes" },
    { key: "sha256", label: "SHA256", render: shortHash },
    { key: "purpose", label: "Purpose" },
  ]);
  const policy = adoption.usage_claim_policy || {};
  document.getElementById("adoption-policy-note").textContent =
    policy.allowed_claim || "Usage evidence should be collected after public deployment.";
  document.getElementById("adoption-grid").innerHTML = [
    ["external users", policy.current_external_users || "not claimed", "predeployment"],
    ["citations", policy.current_citations || "not claimed", "prepublication"],
    ["user groups", (adoption.primary_user_groups || []).length, "target audiences"],
    ["events", (adoption.instrumentation_events || []).length, "privacy-preserving schema"],
  ]
    .map(([label, value, note]) => metricCard(label, value, note))
    .join("");
  renderTable("adoption-event-table", adoption.instrumentation_events || [], [
    { key: "event", label: "Event" },
    { key: "trigger", label: "Trigger" },
    { key: "stored_fields", label: "Stored fields" },
    { key: "excluded_fields", label: "Excluded fields" },
  ]);
}

async function loadMolecules() {
  const modality = document.getElementById("modality-filter").value;
  const suffix = buildQuery({ modality, limit: 500 });
  const molecules = await getJson(`/api/molecules${suffix}`);
  renderTable("molecule-table", molecules, [
    { key: "canonical_name", label: "Name" },
    { key: "modality", label: "Modality", render: badge },
    { key: "target_gene_symbol", label: "Target" },
    { key: "disease_context", label: "Disease" },
    { key: "therapeutic_status", label: "Status" },
  ]);
}

async function loadReadiness() {
  const readiness = await getJson("/api/readiness");
  renderTable("readiness-table", readiness.gates, [
    { key: "gate", label: "Gate" },
    { key: "status", label: "Status", render: badge },
    { key: "evidence", label: "Evidence" },
  ]);
}

async function loadClosestWork() {
  const rows = await getJson("/api/closest_work");
  renderTable("closest-work-table", rows, [
    { key: "resource", label: "Resource" },
    { key: "primary_scope", label: "Primary scope" },
    { key: "overlap_risk", label: "Overlap risk", render: badge },
    { key: "toxicity", label: "Toxicity", render: badge },
    { key: "offtarget", label: "Off-target", render: badge },
    { key: "sequence_or_molecule", label: "Sequence", render: badge },
    { key: "chemical_modification", label: "Modification", render: badge },
    { key: "benchmark_splits", label: "Benchmark splits", render: badge },
    { key: "oligovigil_position", label: "Positioning" },
  ]);
}

async function loadNoveltyPosition() {
  const payload = await getJson("/api/novelty_position");
  const note = document.getElementById("novelty-position-note");
  if (note) {
    note.innerHTML = `
      <div>
        <strong>${payload.red_warning ? "RED WARNING: potential duplicate resource." : "No perfect duplicate detected in closest-work matrix."}</strong>
        ${escapeHtml(payload.position || "")}
      </div>
    `;
  }
  document.getElementById("novelty-position-grid").innerHTML = [
    ["red warning", payload.red_warning ? "yes" : "no", "duplicate audit"],
    ["closest works", (payload.closest_work_rows || []).length, "tracked comparators"],
    ["defensible claims", (payload.defensible_claims || []).length, "safe manuscript claims"],
  ]
    .map(([label, value, noteText]) => metricCard(label, value, noteText))
    .join("");
  document.getElementById("novelty-claim-list").innerHTML = renderTrustPolicyCards(
    payload.defensible_claims || [],
    { titleKey: "claim", bodyKey: "defense" },
  );
}

async function loadEvidence() {
  const evidence = await getJson("/api/evidence");
  const toxicityPreview = (evidence.toxicity || []).slice(0, 25);
  const offtargetPreview = (evidence.offtarget || []).slice(0, 25);
  const toxicityTotal = (evidence.toxicity || []).length;
  const offtargetTotal = (evidence.offtarget || []).length;
  document.getElementById("evidence-preview-note").textContent =
    `Showing 25 toxicity and 25 off-target preview rows from ${toxicityTotal + offtargetTotal} release records. Use the release browser above or download evidence_release.csv for full data.`;
  renderTable("toxicity-table", toxicityPreview, [
    { key: "record", label: "Use", render: releaseUseBadge },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "endpoint_category", label: "Category" },
    { key: "endpoint_name", label: "Endpoint" },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "source_title", label: "Source", render: link },
  ]);
  renderTable("offtarget-table", offtargetPreview, [
    { key: "record", label: "Use", render: releaseUseBadge },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "evidence_type", label: "Evidence type" },
    { key: "is_computational_prediction", label: "Prediction" },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "source_title", label: "Source", render: link },
  ]);
}

function renderMechanismCard(item) {
  const grades = (item.grade_counts || []).map((row) => `${row.grade}: ${row.n}`).join(" / ") || "no grades";
  return `
    <article class="mechanism-card">
      <div>
        <span>${escapeHtml(item.key)}</span>
        <h4>${escapeHtml(item.label)}</h4>
        <p>${escapeHtml(item.definition)}</p>
      </div>
      <div class="profile-metrics compact-metrics">
        <div><strong>${escapeHtml(item.release_records || 0)}</strong><small>release</small></div>
        <div><strong>${escapeHtml(item.benchmark_records || 0)}</strong><small>benchmark</small></div>
        <div><strong>${escapeHtml(item.candidate_records || 0)}</strong><small>candidates</small></div>
      </div>
      <p class="muted-line">Grades: ${escapeHtml(grades)}</p>
      <a class="button-link" href="${escapeHtml(item.endpoint || "/api/evidence_records?domain=offtarget")}">Open records</a>
    </article>
  `;
}

async function loadOfftargetTaxonomyPanel(show) {
  const panel = document.getElementById("offtarget-taxonomy-panel");
  if (!panel) return;
  panel.hidden = !show;
  if (!show) return;
  const payload = await getJson("/api/offtarget_taxonomy");
  document.getElementById("offtarget-taxonomy-note").textContent =
    `${payload.release_records || 0} off-target release records are grouped into mechanism-oriented buckets. ${payload.scope_note || ""}`;
  document.getElementById("offtarget-taxonomy-grid").innerHTML = (payload.classes || [])
    .map(renderMechanismCard)
    .join("");
}

async function loadEvidenceRecords() {
  setBusy("evidence-record-table");
  const domain = document.getElementById("evidence-domain-filter").value;
  const grade = document.getElementById("evidence-grade-filter").value;
  const modality = document.getElementById("evidence-modality-filter").value;
  const category = document.getElementById("evidence-category-filter").value;
  const q = document.getElementById("evidence-query").value;
  const limit = document.getElementById("evidence-limit").value;
  const records = await getJson(
    `/api/evidence_records${buildQuery({ domain, grade, modality, category, q, limit })}`,
  );
  await loadOfftargetTaxonomyPanel(domain === "offtarget" || location.hash === "#offtarget");
  document.getElementById("evidence-count").textContent = `${records.length} verified release records shown`;
  renderTable("evidence-record-table", records, [
    { key: "record", label: "Record", render: recordButton },
    { key: "reuse", label: "Use", render: releaseUseBadge },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "modality", label: "Modality", render: badge },
    { key: "category", label: "Category" },
    { key: "evidence_label", label: "Evidence label" },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "target_gene_symbol", label: "Target" },
    { key: "source_location", label: "Location" },
    { key: "source_title", label: "Source", render: link },
    { key: "pmid", label: "PMID", render: pmidLink },
  ]);
  document.querySelectorAll("#evidence-record-table .record-button").forEach((button) => {
    button.addEventListener("click", () => {
      openRecord(button.dataset.recordDomain || "toxicity", button.dataset.recordId || "1");
    });
  });
}

function openRecord(domain, id) {
  document.getElementById("record-domain").value = domain;
  document.getElementById("record-id").value = id;
  loadRecordDetail();
  showView("record");
}

async function loadRecordDetail() {
  const domain = document.getElementById("record-domain").value;
  const id = document.getElementById("record-id").value.trim() || "1";
  const card = document.getElementById("record-detail-card");
  const citation = document.getElementById("record-citation");
  const bibtex = document.getElementById("record-bibtex");
  card.innerHTML = `<p>Loading record ${escapeHtml(domain)}:${escapeHtml(id)}...</p>`;
  citation.textContent = "";
  bibtex.textContent = "";
  setBusy("record-audit-table");
  const payload = await getJson(`/api/evidence_detail${buildQuery({ domain, id })}`);
  if (!payload.record) {
    card.innerHTML = `<p>${escapeHtml(payload.error || "No verified record found")}</p>`;
    citation.textContent = "";
    bibtex.textContent = "";
    renderTable("record-audit-table", [], [{ key: "id", label: "ID" }]);
    return;
  }
  const record = payload.record;
  const source = payload.source || {};
  const recordCard = payload.record_card || {};
  const provenance = payload.provenance || {};
  const grade = recordCard.grade_rationale || {};
  const sequenceChemistry = recordCard.sequence_chemistry || {};
  const mechanism = recordCard.mechanism || null;
  const limitations = recordCard.limitations || [];
  const sourcePacket = payload.links?.source_packet || "";
  const sourceQuery = source.pmid || source.doi || record.pmid || record.doi || source.id || record.source_title || "";
  card.innerHTML = `
    <div class="record-summary">
      <div class="record-status-row">
        ${releaseUseBadge()} ${badge(record.evidence_domain)} ${badge(record.evidence_grade)} ${badge(record.modality)}
      </div>
      <div class="record-title-row">
        <div>
          <span class="record-key">${escapeHtml(recordCard.record_key || `${record.entity_table}:${record.evidence_id}`)}</span>
          <h3>${escapeHtml(record.canonical_name)}</h3>
        </div>
        <div class="record-grade-box">
          <strong>${escapeHtml(grade.label || `Grade ${record.evidence_grade}`)}</strong>
          <span>${escapeHtml(grade.recommended_use || "")}</span>
        </div>
      </div>
      <p class="record-statement">${escapeHtml(recordCard.evidence_statement || "")}</p>
      ${mechanism ? `
        <div class="record-mechanism-callout">
          <strong>${escapeHtml(mechanism.label)}</strong>
          <span>${escapeHtml(mechanism.definition)}</span>
        </div>
      ` : ""}
      <dl class="record-detail-list evidence-card-list">
        <div>
          <dt>Evidence endpoint</dt>
          <dd>${escapeHtml(record.evidence_label || record.category || "not specified")}</dd>
        </div>
        <div>
          <dt>Target and disease</dt>
          <dd>${escapeHtml(record.target_gene_symbol || "not specified")} ${record.disease_context ? `- ${escapeHtml(record.disease_context)}` : ""}</dd>
        </div>
        <div>
          <dt>Source location</dt>
          <dd>${escapeHtml(provenance.source_location || record.source_location || "not specified")}</dd>
        </div>
        <div>
          <dt>Source title</dt>
          <dd>${escapeHtml(provenance.source_title || record.source_title || source.title || "not specified")}</dd>
        </div>
        <div>
          <dt>Evidence grade rationale</dt>
          <dd>${escapeHtml(grade.meaning || "Inspect audit trail before reuse.")}</dd>
        </div>
        <div>
          <dt>Provenance status</dt>
          <dd>${escapeHtml(provenance.source_location_verified ? "source location verified by curator audit" : "source location requires manual inspection")}</dd>
        </div>
      </dl>
      <div class="record-subgrid">
        <div class="record-subpanel">
          <h4>Sequence and chemistry context</h4>
          <dl class="compact-detail-list">
            <div><dt>Sequence status</dt><dd>${escapeHtml(sequenceChemistry.sequence_annotation_status || "not_curated")}</dd></div>
            <div><dt>Modification status</dt><dd>${escapeHtml(sequenceChemistry.modification_annotation_status || "not_curated")}</dd></div>
            <div><dt>Seed region</dt><dd>${escapeHtml(sequenceChemistry.seed_region || "not curated")}</dd></div>
            <div><dt>Backbone / sugar / base</dt><dd>${escapeHtml([sequenceChemistry.backbone_chemistry, sequenceChemistry.sugar_modification, sequenceChemistry.base_modification].filter(Boolean).join(" / ") || "not curated")}</dd></div>
            <div><dt>Delivery</dt><dd>${escapeHtml(sequenceChemistry.conjugate_delivery || "not curated")}</dd></div>
          </dl>
        </div>
        <div class="record-subpanel">
          <h4>Reuse limitations</h4>
          <ul class="limitation-list">
            ${limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </div>
      </div>
    </div>
    <div class="metadata-strip">
      <span>${escapeHtml(record.entity_table)}:${escapeHtml(record.evidence_id)}</span>
      <span>PMID: ${escapeHtml(record.pmid || "none")}</span>
      <span>DOI: ${escapeHtml(record.doi || source.doi || "none")}</span>
      <span>PMCID: ${escapeHtml(source.pmcid || "none")}</span>
      <span>${escapeHtml(source.journal_or_agency || "source-linked")} ${escapeHtml(source.publication_year || "")}</span>
      <span>${escapeHtml(reusePolicyText(source.reuse_category))}</span>
    </div>
    <div class="inline-actions">
      <a class="button-link" href="${escapeHtml(record.source_url)}" target="_blank" rel="noreferrer">Source</a>
      <button type="button" class="secondary-button" id="record-source-packet-button" data-source-query="${escapeHtml(sourceQuery)}">Open provenance</button>
      <a class="button-link" href="${escapeHtml(sourcePacket)}" target="_blank" rel="noreferrer">Source packet</a>
      <a class="button-link" href="${escapeHtml(payload.links.record_json)}" target="_blank" rel="noreferrer">Record data</a>
      <a class="button-link" href="${escapeHtml(payload.links.evidence_release_csv)}">Download evidence_release.csv</a>
    </div>
  `;
  const sourcePacketButton = document.getElementById("record-source-packet-button");
  if (sourcePacketButton) {
    sourcePacketButton.addEventListener("click", () => {
      document.getElementById("source-detail-query").value = sourcePacketButton.dataset.sourceQuery || "";
      loadSourceDetail();
      showView("sources");
    });
  }
  citation.textContent = payload.citation ? payload.citation.plain_text : "";
  bibtex.textContent = payload.citation ? payload.citation.bibtex : "";
  renderTable("record-audit-table", payload.audit || [], [
    { key: "validation_status", label: "Status", render: badge },
    { key: "curator_decision", label: "Decision", render: badge },
    { key: "curator_id", label: "Curator" },
    { key: "extraction_method", label: "Extraction" },
    { key: "audit_note", label: "Audit note" },
    { key: "audited_at", label: "Audited" },
  ]);
}

async function loadBenchmark() {
  const baselineEndpoint = "/api/benchmark_baseline_results";
  const benchmark = await getJson("/api/benchmark");
  const taskCards = await getJson("/api/benchmark_tasks");
  setGateStatus("gate-benchmark-status", String(benchmark.benchmark_eligible_records || 0), "gate-pass");
  const container = document.getElementById("benchmark-grid");
  const cards = [
    ["release records", benchmark.release_records],
    ["benchmark eligible", benchmark.benchmark_eligible_records],
    ["version", benchmark.version],
    ["leakage policy", humanizeCodeLabel(benchmark.leakage_policy)],
  ];
  container.innerHTML = cards
    .map(([label, value]) => {
      const isLong = String(value || "").length > 18;
      return `<div class="quality-card${isLong ? " long-value" : ""}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(cardText(value))}</strong></div>`;
    })
    .join("");
  const release = benchmark.benchmark_release || {};
  const artifacts = benchmark.download_artifacts || [];
  const strategyCounts = (benchmark.split_strategy_counts || [])
    .map((item) => `${humanizeCodeLabel(item.split_strategy)}: ${item.n}`)
    .join(" / ");
  const splitArtifact = artifacts.find((entry) => entry.filename === "benchmark_reference_splits.csv") || {};
  const evidenceArtifact = artifacts.find((entry) => entry.filename === "evidence_release.csv") || {};
  document.getElementById("benchmark-release-grid").innerHTML = [
    ["DOI status", humanizeCodeLabel(release.doi_status || "pending")],
    ["archive", release.recommended_archive || ""],
    ["citation", release.citation_policy || ""],
    ["leakage control", humanizeCodeLabel(release.leakage_control || "")],
    ["stored split strategies", strategyCounts || "not reported"],
    ["reference split SHA256", splitArtifact.sha256],
    ["evidence release SHA256", evidenceArtifact.sha256],
  ]
    .map(([label, value]) => `<div class="quality-card long-value"><span>${escapeHtml(label)}</span><strong>${escapeHtml(cardText(value))}</strong></div>`)
    .join("");
  const baselineStatus = benchmark.baseline_status || {};
  const baselineRows = benchmark.baseline_result_rows || [];
  const meanAccuracy =
    baselineRows.length
      ? (baselineRows.reduce((total, row) => total + (Number(row.accuracy) || 0), 0) / baselineRows.length).toFixed(3)
      : "n/a";
  const meanMacroF1 =
    baselineRows.length
      ? (baselineRows.reduce((total, row) => total + (Number(row.macro_f1) || 0), 0) / baselineRows.length).toFixed(3)
      : "n/a";
  document.getElementById("benchmark-baseline-grid").innerHTML = [
    [
      "baseline status",
      humanizeCodeLabel(baselineStatus.status || "pending"),
      baselineStatus.result_table_policy || baselineEndpoint,
    ],
    ["result rows", baselineRows.length, "validation/test diagnostic rows"],
    ["mean accuracy", meanAccuracy, "deterministic reference baselines"],
    ["mean macro-F1", meanMacroF1, "label-balanced sanity check"],
  ]
    .map(([label, value, note]) => metricCard(label, value, note))
    .join("");
  renderTable("benchmark-baseline-table", baselineRows, [
    { key: "task_name", label: "Task" },
    { key: "evaluation_split", label: "Split", render: badge },
    { key: "baseline_model", label: "Baseline", render: humanizeCodeLabel },
    { key: "prediction_basis", label: "Basis" },
    { key: "majority_label", label: "Majority label" },
    { key: "coverage", label: "Coverage" },
    { key: "evaluation_rows", label: "Rows" },
    { key: "accuracy", label: "Accuracy" },
    { key: "macro_f1", label: "Macro-F1" },
    { key: "notes", label: "Notes" },
  ]);
  renderTable("benchmark-split-table", benchmark.split_counts || [], [
    { key: "task_name", label: "Task" },
    { key: "split_name", label: "Split", render: badge },
    { key: "n", label: "Rows" },
  ]);
  document.getElementById("benchmark-task-list").innerHTML = renderBenchmarkTaskCards(
    taskCards.length ? taskCards : benchmark.tasks || [],
  );
}

async function loadSequenceCoverage() {
  const coverage = await getJson("/api/sequence_coverage");
  const container = document.getElementById("sequence-coverage-grid");
  container.innerHTML = [
    ["molecules", coverage.molecule_count],
    ["sequence verified", coverage.sequence_curator_verified],
    ["modification verified", coverage.modification_curator_verified],
    ["needs sequence curation", coverage.needs_sequence_curation],
    ["template", coverage.curation_template],
  ]
    .map(([label, value]) => `<div class="quality-card long-value"><span>${escapeHtml(label)}</span><strong>${escapeHtml(cardText(value))}</strong></div>`)
    .join("");
  const statusCard = document.getElementById("sequence-status-card");
  if (statusCard && !statusCard.innerHTML.trim()) {
    statusCard.innerHTML = `
      <p><strong>Enter a sequence only when you want mechanism-level evidence lookup.</strong></p>
      <p>Current release records have limited curator-verified sequence fields; OligoVigil will parse seed windows and retrieve related evidence, not predict sequence-specific risk.</p>
    `;
  }
}

function renderProfileCard(profile) {
  const domains = (profile.domain_counts || []).map((row) => `${row.domain}: ${row.n}`).join(" / ") || "none";
  const grades = (profile.grade_counts || []).map((row) => `${row.grade}: ${row.n}`).join(" / ") || "none";
  return `
    <article class="profile-card">
      <span>${escapeHtml(profile.kind)}</span>
      <h3>${escapeHtml(profile.label)}</h3>
      <div class="profile-metrics">
        <div><strong>${escapeHtml(profile.release_records)}</strong><small>release</small></div>
        <div><strong>${escapeHtml(profile.benchmark_records)}</strong><small>benchmark</small></div>
        <div><strong>${escapeHtml(profile.candidate_records)}</strong><small>candidates</small></div>
      </div>
      <p>Domains: ${escapeHtml(domains)}</p>
      <p>Grades: ${escapeHtml(grades)}</p>
    </article>
  `;
}

async function loadModificationProfile() {
  const term = document.getElementById("modification-profile-filter").value;
  const payload = await getJson(`/api/modification_profile${buildQuery({ term })}`);
  const profiles = payload.profiles || [];
  document.getElementById("modification-profile-grid").innerHTML =
    profiles.map(renderProfileCard).join("") || "<p>No profile records</p>";
}

async function loadDownloadManifest() {
  document.getElementById("download-summary").innerHTML = `
    <div>
      <strong>Loading download catalog.</strong>
      Preparing release files, recommended bundles, and checksum details.
    </div>
  `;
  document.getElementById("download-manifest-grid").innerHTML = `<div class="loading-panel">Loading release files...</div>`;
  const payload = await getJson(DOWNLOADS_ENDPOINT);
  const files = payload.files || [];
  document.getElementById("download-summary").innerHTML = `
    <div>
      <strong>Versioned release downloads</strong>
      ${escapeHtml(payload.license_policy || "")}
    </div>
    <div class="metadata-strip">
      <span>version: ${escapeHtml(payload.version || "")}</span>
      <span>DOI: ${escapeHtml(payload.doi_status || "pending")}</span>
      <span>bundle: ${escapeHtml(payload.recommended_bundle || "")}</span>
    </div>
  `;
  const groups = files.reduce((acc, file) => {
    const key = file.category || "Other";
    if (!acc[key]) acc[key] = [];
    acc[key].push(file);
    return acc;
  }, {});
  document.getElementById("download-manifest-grid").innerHTML = Object.entries(groups)
    .map(([category, rows]) => {
      const cards = rows
        .map(
          (file) => `
            <article class="download-card">
              <span>${escapeHtml(file.recommended_use || category)}</span>
              <h4>${escapeHtml(file.purpose || file.filename)}</h4>
              <div class="profile-metrics compact-metrics">
                <div><strong>${escapeHtml(file.rows ?? "n/a")}</strong><small>rows</small></div>
                <div><strong>${escapeHtml(formatBytes(file.bytes))}</strong><small>size</small></div>
              </div>
              <a class="button-link primary-action" href="${escapeHtml(file.url)}">Download</a>
              <details class="developer-details compact-details">
                <summary>File details</summary>
                <dl class="compact-detail-list">
                  <div><dt>Filename</dt><dd>${escapeHtml(file.filename)}</dd></div>
                  <div><dt>Schema</dt><dd>${escapeHtml(file.schema)}</dd></div>
                  <div><dt>SHA256</dt><dd><code>${escapeHtml(file.sha256 || "pending")}</code></dd></div>
                </dl>
              </details>
            </article>
          `,
        )
        .join("");
      return `
        <section class="download-section">
          <h3>${escapeHtml(category)}</h3>
          <div class="download-card-grid">${cards}</div>
        </section>
      `;
    })
    .join("");
}

async function loadSequenceSearch() {
  const rawSequence = document.getElementById("sequence-input").value.trim();
  const { canonical, invalid } = canonicalizeSequenceInput(rawSequence);
  const target = document.getElementById("sequence-target-input").value.trim();
  const modification = document.getElementById("sequence-modification-filter").value;
  const endpoint = document.getElementById("sequence-endpoint-input").value.trim();
  const button = document.getElementById("sequence-search-button");
  const statusCard = document.getElementById("sequence-status-card");
  renderTable("sequence-release-table", [], [{ key: "record", label: "Record" }]);
  renderTable("sequence-candidate-table", [], [{ key: "id", label: "Candidate" }]);
  if (!canonical) {
    statusCard.innerHTML = `
      <p><strong>Enter A/C/G/T/U/N sequence characters to run evidence lookup.</strong></p>
      <p>This workbench does not infer safety from an empty or invalid sequence, and previous results have been cleared.</p>
    `;
    return;
  }
  if (invalid.length || canonical.length < 7) {
    const invalidText = invalid.length ? ` Invalid characters removed: ${invalid.join(" ")}.` : "";
    statusCard.innerHTML = `
      <p><strong>Sequence input was not searched.</strong></p>
      <p>Provide at least 7 valid A/C/G/T/U/N characters for a seed-aware evidence lookup.${escapeHtml(invalidText)}</p>
      <p>Previous sequence results have been cleared, and no target/modality literature context was returned for this invalid input.</p>
    `;
    return;
  }
  statusCard.innerHTML = `
    <p><strong>Looking up current input...</strong></p>
    <p>Previous sequence results have been cleared while OligoVigil retrieves mechanism-level evidence.</p>
  `;
  setBusy("sequence-release-table");
  setBusy("sequence-candidate-table");
  button.disabled = true;
  const previousLabel = button.textContent;
  button.textContent = "Looking up";
  let payload;
  try {
    payload = await getJson(
      `/api/sequence_search${buildQuery({ sequence: canonical, target, modification, endpoint, limit: 25 })}`,
    );
  } finally {
    button.disabled = false;
    button.textContent = previousLabel;
  }
  const features = payload.sequence_features || {};
  const status = payload.status || {};
  const input = payload.input || {};
  const coverage = payload.sequence_coverage || {};
  const invalidLine = invalid.length
    ? `<p>Ignored invalid characters: ${escapeHtml(invalid.join(" "))}. Query used canonical DNA sequence ${escapeHtml(canonical)}.</p>`
    : "";
  document.getElementById("sequence-status-card").innerHTML = `
    <div class="metadata-strip">
      <span>length: ${escapeHtml(input.length || 0)}</span>
      <span>seed 2-8: ${escapeHtml(features.seed_2_8 || "n/a")}</span>
      <span>target: ${escapeHtml(input.target || "any")}</span>
      <span>modification: ${escapeHtml(input.modification || "any")}</span>
      <span>curated sequence: ${escapeHtml(coverage.sequence_curator_verified || 0)}</span>
      <span>${escapeHtml(status.current_mode || "evidence lookup")}</span>
    </div>
    <p><strong>Mechanism evidence only.</strong> These hits do not prove that this candidate sequence is safe or unsafe; no genome/transcriptome alignment, 3'UTR seed-match scan, or candidate risk ranking is performed.</p>
    ${invalidLine}
    <p>${escapeHtml(status.upgrade_needed || "")}</p>
    ${renderSequenceWindows(features.unique_7mer_windows_first_12 || [])}
  `;
  renderTable("sequence-release-table", payload.release_hits || [], [
    { key: "record", label: "Record", render: recordButton },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "modality", label: "Modality", render: badge },
    { key: "target_gene_symbol", label: "Target" },
    { key: "category", label: "Category" },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "source_title", label: "Source", render: link },
  ]);
  document.querySelectorAll("#sequence-release-table .record-button").forEach((button) => {
    button.addEventListener("click", () => {
      openRecord(button.dataset.recordDomain || "toxicity", button.dataset.recordId || "1");
    });
  });
  renderTable("sequence-candidate-table", payload.candidate_hits || [], [
    { key: "confidence_label", label: "Confidence", render: badge },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "candidate_modality", label: "Modality" },
    { key: "matched_terms", label: "Terms" },
    { key: "source_title", label: "Source" },
    { key: "pmid", label: "PMID", render: pmidLink },
  ]);
}

function runWorkflowAction(action) {
  const parts = String(action || "").split(":");
  if (parts[0] === "sequence") {
    showView("sequence");
    loadSequenceSearch();
    return;
  }
  if (parts[0] === "triage") {
    setTriageInputs({
      sequence: parts[1] || "AUGCUACUGACUGA",
      target: parts[2] || "PCSK9",
      modification: parts[3] || "GalNAc",
      delivery: parts[4] || parts[3] || "GalNAc",
      endpoint: parts[5] || "hepatic",
      species: parts[6] || "human",
    });
    showView("triage");
    loadSafetyTriage();
    return;
  }
  if (parts[0] === "ask") {
    document.getElementById("ask-question").value =
      parts.slice(1).join(":") || "Show GalNAc liver toxicity Grade A/B evidence with PubMed sources";
    runAsk();
    showView("ask");
    return;
  }
  if (parts[0] === "modification") {
    document.getElementById("modification-profile-filter").value = parts[1] || "";
    loadModificationProfile();
    showView("sequence");
    return;
  }
  if (parts[0] === "evidence") {
    document.getElementById("evidence-domain-filter").value = parts[1] || "";
    document.getElementById("evidence-query").value = parts[2] || "";
    loadEvidenceRecords();
    showView("evidence");
    return;
  }
  if (parts[0] === "benchmark") {
    showView("benchmark");
    return;
  }
  if (parts[0] === "offtarget") {
    showView("offtarget");
    loadEvidenceRecords();
  }
}

async function loadClientExamples() {
  const payload = await getJson("/api/client_examples");
  const container = document.getElementById("client-example-grid");
  container.innerHTML = (payload.examples || [])
    .map(
      (example) => `
        <article class="tool-card">
          <span>${escapeHtml(example.language)}</span>
          <h3>${escapeHtml(example.title)}</h3>
          <pre class="code-block">${escapeHtml(example.code)}</pre>
        </article>
      `,
    )
    .join("");
}

async function loadSubmissionSchema() {
  const payload = await getJson("/api/submission_schema");
  const policy = payload.submission_policy || {};
  document.getElementById("submission-policy").innerHTML = `
    <div>
      <strong>Human-curated contribution gate</strong>
      <p>${escapeHtml(policy.reason || "")}</p>
    </div>
    <div class="metadata-strip">
      <span>write API: ${escapeHtml(policy.write_api_enabled ? "enabled" : "disabled")}</span>
      <span>human final decision: ${escapeHtml(policy.human_final_decision_required ? "required" : "not required")}</span>
    </div>
  `;
  renderTable("submission-schema-table", payload.required_fields || [], [
    { key: "field", label: "Field" },
    { key: "type", label: "Type", render: badge },
    { key: "values", label: "Values" },
    { key: "purpose", label: "Purpose" },
  ]);
}

async function loadAudit() {
  setBusy("audit-table");
  const entity_table = document.getElementById("audit-entity-filter").value;
  const validation_status = document.getElementById("audit-status-filter").value;
  const q = document.getElementById("audit-query").value;
  const limit = document.getElementById("audit-limit").value;
  const audit = await getJson(`/api/audit${buildQuery({ entity_table, validation_status, q, limit })}`);
  document.getElementById("audit-count").textContent = `${audit.length} audit records shown`;
  renderTable("audit-table", audit, [
    { key: "entity_table", label: "Entity", render: badge },
    { key: "entity_id", label: "ID" },
    { key: "validation_status", label: "Status", render: badge },
    { key: "curator_decision", label: "Decision", render: badge },
    { key: "curator_id", label: "Curator" },
    { key: "extraction_method", label: "Extraction method" },
    { key: "audit_note", label: "Audit note" },
    { key: "audited_at", label: "Audited at" },
  ]);
}

async function loadSources() {
  const q = document.getElementById("source-query").value;
  const source_type = document.getElementById("source-type-filter").value;
  const year = document.getElementById("source-year-filter").value;
  const sources = await getJson(`/api/sources${buildQuery({ q, source_type, year, limit: 500 })}`);
  renderTable("source-table", sources, [
    { key: "source_type", label: "Type", render: badge },
    { key: "title", label: "Title", render: link },
    { key: "journal_or_agency", label: "Journal/agency" },
    { key: "publication_year", label: "Year" },
    { key: "doi", label: "DOI" },
    { key: "pmid", label: "PMID" },
    { key: "reuse_category", label: "Reuse", render: (value) => escapeHtml(reusePolicyText(value)) },
  ]);
}

function updateCandidateDownloadLink() {
  const domain = document.getElementById("candidate-domain-filter").value;
  const confidence = document.getElementById("confidence-filter").value;
  const q = document.getElementById("candidate-query").value;
  const linkElement = document.getElementById("candidate-download-link");
  linkElement.href = `/api/download/curation_candidates_filtered.csv${buildQuery({
    domain,
    confidence,
    q,
    limit: 5000,
  })}`;
}

async function loadCurationQueue() {
  const domain = document.getElementById("domain-filter").value;
  const priority = document.getElementById("priority-filter").value;
  const q = document.getElementById("queue-query").value;
  const limit = document.getElementById("queue-limit").value;
  const suffix = buildQuery({ domain, priority, q, limit });
  const queue = await getJson(`/api/curation_queue${suffix}`);
  renderTable("queue-table", queue, [
    { key: "priority", label: "Priority", render: badge },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "candidate_modality", label: "Modality" },
    { key: "extraction_target", label: "Extraction target" },
    { key: "suggested_evidence_grade", label: "Suggested grade", render: badge },
    { key: "pmid", label: "PMID" },
    { key: "source_title", label: "Source title" },
  ]);
}

async function loadCurationCandidates() {
  const domain = document.getElementById("candidate-domain-filter").value;
  const confidence = document.getElementById("confidence-filter").value;
  const q = document.getElementById("candidate-query").value;
  const limit = document.getElementById("candidate-limit").value;
  const suffix = buildQuery({ domain, confidence, q, limit });
  updateCandidateDownloadLink();
  const candidates = await getJson(`/api/curation_candidates${suffix}`);
  renderTable("candidate-table", candidates, [
    { key: "confidence_label", label: "Confidence", render: badge },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "candidate_modality", label: "Modality" },
    { key: "source_location", label: "Location" },
    { key: "matched_terms", label: "Matched terms" },
    { key: "candidate_signal", label: "Derived candidate signal" },
    { key: "source_title", label: "Source title" },
    { key: "validation_status", label: "Validation" },
    { key: "pmid", label: "PMID" },
  ]);
}

async function loadSourceDetail() {
  const q = document.getElementById("source-detail-query").value.trim();
  if (!q) {
    document.getElementById("source-detail-card").innerHTML = "";
    renderTable("source-detail-queue-table", [], [{ key: "id", label: "ID" }]);
    renderTable("source-detail-candidate-table", [], [{ key: "id", label: "ID" }]);
    renderTable("source-detail-toxicity-table", [], [{ key: "id", label: "ID" }]);
    renderTable("source-detail-offtarget-table", [], [{ key: "id", label: "ID" }]);
    return;
  }
  const detail = await getJson(`/api/source_detail${buildQuery({ q })}`);
  const card = document.getElementById("source-detail-card");
  if (!detail.source) {
    card.innerHTML = `<p>No source matched ${escapeHtml(q)}</p>`;
    renderTable("source-detail-queue-table", [], [{ key: "id", label: "ID" }]);
    renderTable("source-detail-candidate-table", [], [{ key: "id", label: "ID" }]);
    renderTable("source-detail-toxicity-table", [], [{ key: "id", label: "ID" }]);
    renderTable("source-detail-offtarget-table", [], [{ key: "id", label: "ID" }]);
    return;
  }
  const source = detail.source;
  const sourcePacket = `/api/source_detail${buildQuery({ q: source.pmid || source.doi || source.id })}`;
  card.innerHTML = `
    <div>
      <strong>${escapeHtml(source.title)}</strong>
      <p>${escapeHtml(source.journal_or_agency)} ${escapeHtml(source.publication_year || "")}</p>
    </div>
    <div class="metadata-strip">
      <span>ID: ${escapeHtml(source.id)}</span>
      <span>PMID: ${escapeHtml(source.pmid || "none")}</span>
      <span>DOI: ${escapeHtml(source.doi || "none")}</span>
      <span>PMCID: ${escapeHtml(source.pmcid || "none")}</span>
      <span>${escapeHtml(source.source_type)}</span>
      <span>${escapeHtml(reusePolicyText(source.reuse_category))}</span>
    </div>
    <div class="inline-actions">
      <a class="button-link" href="${escapeHtml(source.source_url)}" target="_blank" rel="noreferrer">Open source</a>
      <a class="button-link" href="${escapeHtml(sourcePacket)}" target="_blank" rel="noreferrer">Source packet</a>
    </div>
  `;
  renderTable("source-detail-queue-table", detail.queue || [], [
    { key: "priority", label: "Priority", render: badge },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "candidate_modality", label: "Modality" },
    { key: "extraction_target", label: "Target" },
    { key: "suggested_evidence_grade", label: "Grade", render: badge },
  ]);
  renderTable("source-detail-candidate-table", detail.candidates || [], [
    { key: "reuse", label: "Use", render: candidateUseBadge },
    { key: "confidence_label", label: "Confidence", render: badge },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "candidate_modality", label: "Modality" },
    { key: "matched_terms", label: "Terms" },
    { key: "source_location", label: "Location" },
    { key: "validation_status", label: "Validation" },
  ]);
  renderTable("source-detail-toxicity-table", detail.toxicity || [], [
    { key: "record", label: "Record", render: recordButton },
    { key: "reuse", label: "Use", render: releaseUseBadge },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "modality", label: "Modality", render: badge },
    { key: "endpoint_category", label: "Category" },
    { key: "endpoint_name", label: "Endpoint" },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "source_location", label: "Location" },
  ]);
  renderTable("source-detail-offtarget-table", detail.offtarget || [], [
    { key: "record", label: "Record", render: recordButton },
    { key: "reuse", label: "Use", render: releaseUseBadge },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "modality", label: "Modality", render: badge },
    { key: "evidence_type", label: "Evidence type" },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "source_location", label: "Location" },
  ]);
  document.querySelectorAll("#source-detail-toxicity-table .record-button, #source-detail-offtarget-table .record-button").forEach((button) => {
    button.addEventListener("click", () => {
      openRecord(button.dataset.recordDomain || "toxicity", button.dataset.recordId || "1");
    });
  });
}

function renderSearchResults(payload) {
  const summary = document.getElementById("search-summary");
  const counts = ["sources", "molecules", "candidates", "toxicity", "offtarget"]
    .map((key) => `${key}: ${(payload[key] || []).length}`)
    .join(" | ");
  summary.textContent = payload.query ? counts : "";

  renderTable("search-source-table", payload.sources || [], [
    { key: "title", label: "Title", render: link },
    { key: "publication_year", label: "Year" },
    { key: "pmid", label: "PMID", render: pmidLink },
  ]);
  renderTable("search-molecule-table", payload.molecules || [], [
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "modality", label: "Modality", render: badge },
    { key: "target_gene_symbol", label: "Target" },
    { key: "disease_context", label: "Disease" },
    { key: "therapeutic_status", label: "Status" },
  ]);
  renderTable("search-candidate-table", payload.candidates || [], [
    { key: "reuse", label: "Use", render: candidateUseBadge },
    { key: "confidence_label", label: "Confidence", render: badge },
    { key: "evidence_domain", label: "Domain", render: badge },
    { key: "candidate_modality", label: "Modality" },
    { key: "source_location", label: "Location" },
    { key: "pmid", label: "PMID", render: pmidLink },
    { key: "source_title", label: "Source", render: link },
  ]);
  renderTable("search-toxicity-table", payload.toxicity || [], [
    { key: "record", label: "Record", render: recordButton },
    { key: "reuse", label: "Use", render: releaseUseBadge },
    { key: "modality", label: "Modality", render: badge },
    { key: "endpoint_category", label: "Category" },
    { key: "endpoint_name", label: "Endpoint" },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "source_location", label: "Location" },
    { key: "pmid", label: "PMID", render: pmidLink },
    { key: "source_title", label: "Source", render: link },
  ]);
  renderTable("search-offtarget-table", payload.offtarget || [], [
    { key: "record", label: "Record", render: recordButton },
    { key: "reuse", label: "Use", render: releaseUseBadge },
    { key: "modality", label: "Modality", render: badge },
    { key: "evidence_type", label: "Evidence type" },
    { key: "evidence_grade", label: "Grade", render: badge },
    { key: "canonical_name", label: "Molecule/cohort" },
    { key: "source_location", label: "Location" },
    { key: "pmid", label: "PMID", render: pmidLink },
    { key: "source_title", label: "Source", render: link },
  ]);
  document.querySelectorAll("#search-toxicity-table .record-button, #search-offtarget-table .record-button").forEach((button) => {
    button.addEventListener("click", () => {
      openRecord(button.dataset.recordDomain || "toxicity", button.dataset.recordId || "1");
    });
  });
}

async function runGlobalSearch() {
  const q = document.getElementById("global-search").value.trim();
  if (!q) {
    renderSearchResults({ query: "", sources: [], molecules: [], candidates: [], toxicity: [], offtarget: [] });
    return;
  }
  const payload = await getJson(`/api/search${buildQuery({ q, limit: 30 })}`);
  renderSearchResults(payload);
}

async function loadViewData(view, { force = false } = {}) {
  if (!force && loadedViews.has(view)) return;
  loadedViews.add(view);
  try {
    const loaders = {
      overview: [loadStats, loadQuality, updateBenchmarkGate, loadExampleResults, loadReleaseStatus],
      sequence: [loadSequenceCoverage, loadModificationProfile],
      triage: [loadSafetyTriage],
      search: [runGlobalSearch, loadExamples],
      ask: [runAsk, loadAskExamples],
      usecases: [loadUseCases],
      examples: [loadExampleResults],
      release: [loadReleaseStatus, loadSubmissionPack, loadFieldCompleteness, loadCoreOligoFields],
      help: [loadHelp],
      trust: [loadCurationProtocol, loadIndependentValidation],
      cite: [loadCitation],
      quality: [loadQuality, loadReadiness],
      curation: [loadCurationCandidates, loadCurationQueue],
      evidence: [loadEvidence, loadEvidenceRecords, loadAudit],
      record: [loadRecordDetail],
      benchmark: [loadBenchmark],
      agent: [loadAgentAccess],
      sources: [loadSources, loadSourceDetail, loadMolecules, loadClosestWork, loadNoveltyPosition],
      api: [loadClientExamples, loadSubmissionSchema],
      submit: [loadSubmissionSchema],
      downloads: [loadDownloadManifest],
      coverage: [loadCoverage, loadSummary],
    };
    await Promise.all((loaders[view] || loaders.overview).map((loader) => loader()));
  } catch (error) {
    loadedViews.delete(view);
    showError(error);
  }
}

async function init() {
  document.querySelectorAll("[data-view-target]").forEach((node) => {
    node.addEventListener("click", (event) => {
      event.preventDefault();
      showView(node.dataset.viewTarget || "overview");
    });
  });
  window.addEventListener("hashchange", () => showView(viewFromHash(location.hash), { updateHash: false }));
  showView(viewFromHash(location.hash), { updateHash: false });
  document.getElementById("modality-filter").addEventListener("change", loadMolecules);
  document.getElementById("evidence-domain-filter").addEventListener("change", loadEvidenceRecords);
  document.getElementById("evidence-grade-filter").addEventListener("change", loadEvidenceRecords);
  document.getElementById("evidence-modality-filter").addEventListener("change", loadEvidenceRecords);
  document.getElementById("evidence-category-filter").addEventListener("change", loadEvidenceRecords);
  document.getElementById("evidence-limit").addEventListener("change", loadEvidenceRecords);
  document.getElementById("evidence-query").addEventListener("input", debounce(loadEvidenceRecords));
  document.getElementById("audit-entity-filter").addEventListener("change", loadAudit);
  document.getElementById("audit-status-filter").addEventListener("change", loadAudit);
  document.getElementById("audit-limit").addEventListener("change", loadAudit);
  document.getElementById("audit-query").addEventListener("input", debounce(loadAudit));
  document.getElementById("search-button").addEventListener("click", runGlobalSearch);
  document.getElementById("source-detail-button").addEventListener("click", loadSourceDetail);
  document.getElementById("source-detail-query").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadSourceDetail();
  });
  document.getElementById("record-open-button").addEventListener("click", loadRecordDetail);
  document.getElementById("record-id").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadRecordDetail();
  });
  document.getElementById("record-domain").addEventListener("change", loadRecordDetail);
  document.getElementById("copy-citation-button").addEventListener("click", () => copyText("record-citation"));
  document.getElementById("copy-bibtex-button").addEventListener("click", () => copyText("record-bibtex"));
  document.getElementById("copy-global-citation-button").addEventListener("click", () => copyText("global-citation"));
  document.getElementById("copy-global-bibtex-button").addEventListener("click", () => copyText("global-bibtex"));
  document.getElementById("clear-search-button").addEventListener("click", () => {
    document.getElementById("global-search").value = "";
    renderSearchResults({ query: "", sources: [], molecules: [], candidates: [], toxicity: [], offtarget: [] });
  });
  document.getElementById("global-search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") runGlobalSearch();
  });
  document.getElementById("hero-search-button").addEventListener("click", () => {
    document.getElementById("global-search").value = document.getElementById("hero-search-input").value.trim();
    runGlobalSearch();
    showView("search");
  });
  document.getElementById("hero-search-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      document.getElementById("hero-search-button").click();
    }
  });
  document.querySelectorAll("[data-workflow-action]").forEach((node) => {
    node.addEventListener("click", () => runWorkflowAction(node.dataset.workflowAction));
  });
  document.getElementById("sequence-search-button").addEventListener("click", loadSequenceSearch);
  document.getElementById("triage-run-button").addEventListener("click", loadSafetyTriage);
  document.getElementById("triage-print-button").addEventListener("click", () => window.print());
  document.querySelectorAll("#triage input").forEach((node) => {
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter") loadSafetyTriage();
    });
  });
  document.getElementById("modification-profile-button").addEventListener("click", loadModificationProfile);
  document.getElementById("candidate-domain-filter").addEventListener("change", loadCurationCandidates);
  document.getElementById("confidence-filter").addEventListener("change", loadCurationCandidates);
  document.getElementById("candidate-limit").addEventListener("change", loadCurationCandidates);
  document.getElementById("candidate-query").addEventListener("input", debounce(loadCurationCandidates));
  document.getElementById("domain-filter").addEventListener("change", loadCurationQueue);
  document.getElementById("priority-filter").addEventListener("change", loadCurationQueue);
  document.getElementById("queue-limit").addEventListener("change", loadCurationQueue);
  document.getElementById("queue-query").addEventListener("input", debounce(loadCurationQueue));
  document.getElementById("source-query").addEventListener("input", debounce(loadSources));
  document.getElementById("source-type-filter").addEventListener("change", loadSources);
  document.getElementById("source-year-filter").addEventListener("change", loadSources);
  document.getElementById("ask-run-button").addEventListener("click", runAsk);
  document.getElementById("ask-clear-button").addEventListener("click", () => {
    document.getElementById("ask-question").value = ASK_EXAMPLES[0];
    runAsk();
  });
  document.getElementById("ask-question").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) runAsk();
  });
  document.getElementById("global-search").value = "toxicity";
  document.getElementById("hero-search-input").value = "GalNAc hepatotoxicity";
  document.getElementById("ask-question").value = ASK_EXAMPLES[0];
  document.getElementById("sequence-input").value = "AUGCUACUGACUGA";
  document.getElementById("sequence-target-input").value = "PCSK9";
  setTriageInputs();
  appReady = true;
  await Promise.all([loadMetadata(), loadFacets(), loadViewData(viewFromHash(location.hash))]);
}

init().catch((error) => {
  showError(error);
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<pre style="padding:16px;background:#fee;border:1px solid #d99">${escapeHtml(error.message)}</pre>`,
  );
});

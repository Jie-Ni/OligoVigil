const state = {
  evidence: [],
  sources: [],
};

const MAX_TABLE_ROWS = 200;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
}

function showError(error) {
  const banner = document.getElementById("error-banner");
  banner.textContent = `The release data could not be loaded. ${error.message}`;
  banner.hidden = false;
}

function normalize(value) {
  return String(value ?? "").trim().toLowerCase();
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function shortHash(value) {
  const hash = String(value || "");
  return hash.length > 16 ? `${hash.slice(0, 16)}…` : hash;
}

function versionLabel(value) {
  const version = String(value || "");
  return version.startsWith("v") ? version : `v${version}`;
}

function sourceLink(record) {
  const url = record.source_url || (record.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${record.pmid}/` : "");
  const label = record.pmid ? `PMID ${record.pmid}` : "Open source";
  return url
    ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>`
    : "—";
}

function setReleaseCounts(metadata, stats) {
  const snapshot = metadata.release_snapshot || {};
  const counts = stats.counts || {};
  const toxicity = Number(snapshot.toxicity_records ?? counts.toxicity_endpoint) || 0;
  const offtarget = Number(snapshot.offtarget_records ?? counts.offtarget_evidence) || 0;
  const total = Number(snapshot.verified_release_records) || toxicity + offtarget;
  const sources = Number(snapshot.primary_studies ?? counts.source_document) || 0;
  const benchmark = Number(snapshot.benchmark_split_records ?? counts.benchmark_split) || 0;
  const audit = Number(counts.curation_audit) || 0;

  document.getElementById("release-version").textContent = versionLabel(
    metadata.data_release_version || "1.0.2",
  );
  document.getElementById("hero-release-total").textContent = total;
  document.getElementById("hero-source-total").textContent = sources;
  document.getElementById("hero-benchmark-total").textContent = benchmark;
  document.getElementById("stat-release").textContent = total;
  document.getElementById("stat-toxicity").textContent = toxicity;
  document.getElementById("stat-offtarget").textContent = offtarget;
  document.getElementById("stat-sources").textContent = sources;
  document.getElementById("stat-audit").textContent = audit;
}

function evidenceText(record) {
  return [
    record.canonical_name,
    record.modality,
    record.target_gene_symbol,
    record.category,
    record.evidence_label,
    record.source_title,
    record.source_location,
    record.pmid,
    record.pmcid,
    record.doi,
  ]
    .map(normalize)
    .join(" ");
}

function renderEvidence() {
  const query = normalize(document.getElementById("evidence-query").value);
  const domain = document.getElementById("evidence-domain").value;
  const grade = document.getElementById("evidence-grade").value;
  const matches = state.evidence.filter((record) => {
    if (domain && record.evidence_domain !== domain) return false;
    if (grade && record.evidence_grade !== grade) return false;
    return !query || evidenceText(record).includes(query);
  });
  const visible = matches.slice(0, MAX_TABLE_ROWS);
  document.getElementById("evidence-status").textContent =
    matches.length > MAX_TABLE_ROWS
      ? `${matches.length} records match; showing the first ${MAX_TABLE_ROWS}.`
      : `${matches.length} records match.`;
  document.getElementById("evidence-rows").innerHTML = visible.length
    ? visible
        .map(
          (record) => `
            <tr>
              <td>${escapeHtml(record.evidence_domain)}</td>
              <td><strong>${escapeHtml(record.canonical_name || "Unspecified oligonucleotide")}</strong></td>
              <td>${escapeHtml(record.modality || "—")}</td>
              <td>${escapeHtml(record.evidence_label || record.category || "—")}</td>
              <td><span class="grade-badge">${escapeHtml(record.evidence_grade || "—")}</span></td>
              <td>${sourceLink(record)}</td>
            </tr>`,
        )
        .join("")
    : '<tr><td colspan="6">No release records match these filters.</td></tr>';
}

function sourceText(record) {
  return [
    record.title,
    record.journal_or_agency,
    record.publication_year,
    record.pmid,
    record.pmcid,
    record.doi,
  ]
    .map(normalize)
    .join(" ");
}

function identifierLinks(record) {
  const links = [];
  if (record.pmid) {
    links.push(`<a href="https://pubmed.ncbi.nlm.nih.gov/${encodeURIComponent(record.pmid)}/" target="_blank" rel="noopener">PMID ${escapeHtml(record.pmid)}</a>`);
  }
  if (record.pmcid) {
    links.push(`<a href="https://pmc.ncbi.nlm.nih.gov/articles/${encodeURIComponent(record.pmcid)}/" target="_blank" rel="noopener">${escapeHtml(record.pmcid)}</a>`);
  }
  if (record.doi) {
    links.push(`<a href="https://doi.org/${encodeURIComponent(record.doi)}" target="_blank" rel="noopener">DOI</a>`);
  }
  return links.join(" · ") || "—";
}

function sourceTitle(record) {
  const title = escapeHtml(record.title || "Untitled source");
  return record.source_url
    ? `<a href="${escapeHtml(record.source_url)}" target="_blank" rel="noopener"><strong>${title}</strong></a>`
    : `<strong>${title}</strong>`;
}

function renderSources() {
  const query = normalize(document.getElementById("source-query").value);
  const matches = state.sources.filter((record) => !query || sourceText(record).includes(query));
  const visible = matches.slice(0, MAX_TABLE_ROWS);
  document.getElementById("source-status").textContent =
    matches.length > MAX_TABLE_ROWS
      ? `${matches.length} studies match; showing the first ${MAX_TABLE_ROWS}.`
      : `${matches.length} studies match.`;
  document.getElementById("source-rows").innerHTML = visible.length
    ? visible
        .map(
          (record) => `
            <tr>
              <td>${escapeHtml(record.publication_year || "—")}</td>
              <td>${sourceTitle(record)}</td>
              <td>${escapeHtml(record.journal_or_agency || "—")}</td>
              <td>${identifierLinks(record)}</td>
            </tr>`,
        )
        .join("")
    : '<tr><td colspan="4">No studies match this search.</td></tr>';
}

function renderDownloads(manifest) {
  const files = Array.isArray(manifest.files) ? manifest.files : [];
  const priority = [
    "evidence_release.csv",
    "source_document.csv",
    "molecule.csv",
    "curation_audit.csv",
    "benchmark_reference_splits.csv",
    "benchmark_task_cards.csv",
    "benchmark_baseline_results.csv",
    "data_dictionary_v1.csv",
    "source_license_manifest_v1.csv",
    "all_tables.zip",
  ];
  const order = new Map(priority.map((name, index) => [name, index]));
  files.sort((a, b) => (order.get(a.filename) ?? 999) - (order.get(b.filename) ?? 999));
  document.getElementById("download-list").innerHTML = files.length
    ? files
        .map(
          (file) => `
            <article class="download-row">
              <div>
                <h3><a href="${escapeHtml(file.url)}">${escapeHtml(file.filename)}</a></h3>
                <p>${escapeHtml(file.purpose || "Release file")}</p>
              </div>
              <dl>
                <div><dt>Rows</dt><dd>${escapeHtml(file.rows ?? "—")}</dd></div>
                <div><dt>Size</dt><dd>${formatBytes(file.bytes)}</dd></div>
                <div><dt>SHA-256</dt><dd><code title="${escapeHtml(file.sha256)}">${escapeHtml(shortHash(file.sha256))}</code></dd></div>
              </dl>
            </article>`,
        )
        .join("")
    : "<p>No release files were found.</p>";
}

function renderValidation(payload) {
  const sample = payload.sample || payload;
  const ci = sample.wilson_95_ci || payload.wilson_95_ci || [0.63, 0.81];
  const values = [
    ["Stratified sample", sample.sample_size ?? sample.n ?? 126],
    ["Machine-accepted subset", sample.machine_accepted ?? 90],
    ["False accepts", sample.false_accepts ?? 66],
    ["False-accept rate", sample.false_accept_rate ?? 0.73],
    ["Wilson 95% CI", Array.isArray(ci) ? `${ci[0]}–${ci[1]}` : ci],
  ];
  document.getElementById("validation-facts").innerHTML = values
    .map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");
}

function renderCitation(payload) {
  const archived = payload.archived_snapshot || payload.version_map?.archived_snapshot || {};
  const web = payload.web_release || payload.version_map?.web_release || {};
  const citation =
    payload.recommended_citation ||
    payload.citation ||
    payload.preferred_citation ||
    `Ni J. OligoVigil: curated oligonucleotide safety and off-target evidence. Web release v${web.version || "1.0.2"}. ${web.url || "https://oligovigil.pages.dev/"}`;
  document.getElementById("citation-text").textContent = citation;
  document.getElementById("archive-version").textContent = versionLabel(
    archived.version || "1.0.1",
  );
  document.getElementById("web-version").textContent = versionLabel(web.version || "1.0.2");
  if (archived.doi) {
    const link = document.getElementById("archive-doi");
    link.textContent = archived.doi;
    link.href = `https://doi.org/${archived.doi}`;
  }
}

async function copyCitation() {
  const text = document.getElementById("citation-text").textContent.trim();
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
  } else {
    const field = document.createElement("textarea");
    field.value = text;
    document.body.appendChild(field);
    field.select();
    document.execCommand("copy");
    field.remove();
  }
  const status = document.getElementById("copy-status");
  status.textContent = "Copied";
  window.setTimeout(() => {
    status.textContent = "";
  }, 1800);
}

async function init() {
  try {
    const [metadata, stats, evidence, sources, manifest, validation, citation] = await Promise.all([
      getJson("/api/metadata"),
      getJson("/api/stats"),
      getJson("/api/evidence_records?limit=1000"),
      getJson("/api/sources?limit=1000"),
      getJson("/api/download_manifest"),
      getJson("/api/independent_validation"),
      getJson("/api/citation"),
    ]);
    state.evidence = Array.isArray(evidence) ? evidence : [];
    state.sources = Array.isArray(sources) ? sources : [];
    setReleaseCounts(metadata, stats);
    renderEvidence();
    renderSources();
    renderDownloads(manifest);
    renderValidation(validation);
    renderCitation(citation);
  } catch (error) {
    showError(error);
  }
}

document.getElementById("evidence-query").addEventListener("input", renderEvidence);
document.getElementById("evidence-domain").addEventListener("change", renderEvidence);
document.getElementById("evidence-grade").addEventListener("change", renderEvidence);
document.getElementById("evidence-clear").addEventListener("click", () => {
  document.getElementById("evidence-query").value = "";
  document.getElementById("evidence-domain").value = "";
  document.getElementById("evidence-grade").value = "";
  renderEvidence();
  document.getElementById("evidence-query").focus();
});
document.getElementById("source-query").addEventListener("input", renderSources);
document.getElementById("source-clear").addEventListener("click", () => {
  document.getElementById("source-query").value = "";
  renderSources();
  document.getElementById("source-query").focus();
});
document.getElementById("copy-citation").addEventListener("click", () => {
  copyCitation().catch(showError);
});

init();

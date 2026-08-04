export class OligoVigilClient {
  constructor(baseUrl = "https://oligovigil.pages.dev") {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  url(path, params = {}) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value).trim() !== "") {
        search.set(key, value);
      }
    });
    const suffix = search.toString();
    return `${this.baseUrl}${path}${suffix ? `?${suffix}` : ""}`;
  }

  async getJson(path, params = {}) {
    const response = await fetch(this.url(path, params), { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${path}: ${response.status}`);
    return response.json();
  }

  search(query, limit = 20) {
    return this.getJson("/api/search", { q: query, limit });
  }

  evidenceRecords({ domain = "", query = "", limit = 100 } = {}) {
    return this.getJson("/api/evidence_records", { domain, q: query, limit });
  }

  evidenceDetail(domain, evidenceId) {
    return this.getJson("/api/evidence_detail", { domain, id: evidenceId });
  }

  safetyTriage({
    sequence = "",
    helm = "",
    target = "",
    modification = "",
    delivery = "",
    endpoint = "",
    species = "",
  } = {}) {
    return this.getJson("/api/safety_triage", {
      sequence,
      helm,
      target,
      modification,
      delivery,
      endpoint,
      species,
    });
  }

  safetyDossier({
    sequence = "",
    helm = "",
    target = "",
    modification = "",
    delivery = "",
    endpoint = "",
    species = "",
  } = {}) {
    return this.getJson("/api/safety_dossier", {
      sequence,
      helm,
      target,
      modification,
      delivery,
      endpoint,
      species,
    });
  }

  evidenceGraph({
    sequence = "",
    helm = "",
    target = "",
    modification = "",
    delivery = "",
    endpoint = "",
    species = "",
  } = {}) {
    return this.getJson("/api/evidence_graph", {
      sequence,
      helm,
      target,
      modification,
      delivery,
      endpoint,
      species,
    });
  }

  benchmark() {
    return this.getJson("/api/benchmark");
  }

  downloadManifest() {
    return this.getJson("/api/download_manifest");
  }

  offtargetTaxonomy() {
    return this.getJson("/api/offtarget_taxonomy");
  }

  downloadUrl(path) {
    return this.url(path);
  }

  benchmarkSplitsUrl() {
    return this.downloadUrl("/api/download/benchmark_reference_splits.csv");
  }

  benchmarkBaselineUrl() {
    return this.downloadUrl("/api/download/benchmark_baseline_results.csv");
  }

  benchmarkTaskCardsUrl() {
    return this.downloadUrl("/api/download/benchmark_task_cards.csv");
  }
}

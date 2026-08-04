from __future__ import annotations

import csv
import io
import json
import sys
import time
from urllib.error import HTTPError
from urllib.request import urlopen

BASE_URL = "http://127.0.0.1:8077"
ARCHIVED_VERSION = "v1.0.1"
ARCHIVED_DOI = "10.5281/zenodo.20633779"
WEB_VERSION = "1.0.2"

RETIRED_PUBLIC_PATHS = (
    "/api/examples",
    "/api/ask",
    "/api/help",
    "/api/use_cases",
    "/api/case_workflows",
    "/api/sequence_coverage",
    "/api/sequence_search",
    "/api/safety_triage",
    "/api/safety_dossier",
    "/api/evidence_graph",
    "/api/prov_graph",
    "/api/modification_profile",
    "/api/client_examples",
    "/api/submission_schema",
    "/api/openapi.json",
    "/api/search",
    "/api/source_detail",
    "/api/evidence_detail",
    "/api/offtarget_taxonomy",
    "/api/quality",
    "/api/curation_protocol",
    "/api/release_status",
    "/api/closest_work",
    "/api/core_oligo_fields",
    "/api/field_completeness",
    "/api/novelty_position",
    "/api/adoption_packet",
    "/api/readiness",
    "/api/archive_readiness",
    "/api/agent_access",
    "/api/agent_connect",
    "/api/submission_pack",
    "/api/curation_queue",
    "/api/curation_candidates",
    "/agent.json",
    "/.well-known/ai-plugin.json",
    "/.well-known/nlweb.json",
    "/.well-known/oligovigil-agent.json",
    "/mcp.json",
    "/nlweb.json",
    "/llms.txt",
    "/llms-full.txt",
    "/api/download/oligovigil_agent_pack.zip",
    "/api/download/sequence_modification_curation_template.csv",
    "/api/download/core_oligo_field_curation_packet.csv",
    "/api/download/independent_curation_validation_template.csv",
    "/api/download/curation_queue.csv",
    "/api/download/curation_candidate.csv",
    "/api/download/curation_candidates_filtered.csv",
    "/api/download/assay.csv",
    "/api/manifest/sequence_modification_curation_template_v1.csv",
    "/api/manifest/core_oligo_field_curation_packet_v1.csv",
    "/api/manifest/independent_curation_validation_template_v1.csv",
    "/api/manifest/closest_work_matrix_v1.csv",
    "/api/manifest/curation_queue_v1.csv",
    "/api/manifest/curation_candidate_v1.csv",
    "/api/manifest/source_candidates_v1.csv",
    "/api/manifest/source_candidates_v2.csv",
    "/api/manifest/source_candidates_v3.csv",
    "/api/manifest/source_candidates_v4.csv",
    "/api/manifest/source_candidates_v5.csv",
    "/api/manifest/source_candidates_v6.csv",
    "/api/manifest/pubmed_discovery_candidates_v1.csv",
    "/api/manifest/pubmed_discovery_candidates_v2.csv",
    "/api/manifest/pubmed_discovery_candidates_v3.csv",
    "/api/manifest/pubmed_discovery_candidates_v4.csv",
    "/api/manifest/source_document_pubmed_v1.csv",
)


def fail(message: str) -> None:
    raise AssertionError(message)


def get(path: str) -> str:
    last_error: Exception | None = None
    for _ in range(8):
        try:
            with urlopen(f"{BASE_URL}{path}", timeout=5) as response:
                if response.status != 200:
                    fail(f"{path} returned {response.status}")
                return response.read().decode("utf-8-sig")
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise last_error or AssertionError(f"{path} failed")


def get_json(path: str) -> object:
    return json.loads(get(path))


def get_csv_rows(path: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(get(path))))


def assert_not_found(path: str) -> None:
    try:
        with urlopen(f"{BASE_URL}{path}", timeout=5) as response:
            fail(f"{path} returned {response.status}; expected 404")
    except HTTPError as error:
        if error.code != 404:
            raise


def assert_no_internal_work_keys(payload: object, label: str, path: str = "$") -> None:
    forbidden_keys = {
        "candidate_records",
        "queue_tasks",
        "curation_candidate",
        "curation_candidates",
        "curation_queue",
    }
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            if key_text.lower() in forbidden_keys:
                fail(f"{label} exposes withheld internal key {path}.{key_text}")
            assert_no_internal_work_keys(value, label, f"{path}.{key_text}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_no_internal_work_keys(value, label, f"{path}[{index}]")


def assert_release_counts(metadata: object, stats: object) -> None:
    if not isinstance(metadata, dict):
        fail("metadata endpoint returned a non-object payload")
    if metadata.get("data_release_version") != WEB_VERSION:
        fail("metadata endpoint does not report web release 1.0.2")
    snapshot = metadata.get("release_snapshot", {})
    if not isinstance(snapshot, dict) or snapshot != {
        "verified_release_records": 737,
        "toxicity_records": 626,
        "offtarget_records": 111,
        "benchmark_split_records": 344,
        "primary_studies": 660,
    }:
        fail("metadata release snapshot differs from the submitted manuscript contract")

    if not isinstance(stats, dict) or not isinstance(stats.get("counts"), dict):
        fail("stats endpoint returned a malformed payload")
    counts = stats["counts"]
    for key, expected in {
        "source_document": 660,
        "molecule": 524,
        "toxicity_endpoint": 626,
        "offtarget_evidence": 111,
        "curation_audit": 737,
        "benchmark_split": 344,
    }.items():
        if counts.get(key) != expected:
            fail(f"stats endpoint {key} count must be {expected}")
    assert_no_internal_work_keys(stats, "stats endpoint")


def main() -> None:
    html = get("/")
    for marker in [
        'id="overview"',
        'id="evidence"',
        'id="sources"',
        'id="downloads"',
        'id="methods"',
        'id="citation"',
        'id="release-version"',
        'id="hero-release-total"',
        'id="hero-source-total"',
        'id="hero-benchmark-total"',
        'id="stat-release"',
        'id="stat-toxicity"',
        'id="stat-offtarget"',
        'id="stat-sources"',
        'id="stat-audit"',
        'id="evidence-filter"',
        'id="evidence-query"',
        'id="evidence-domain"',
        'id="evidence-grade"',
        'id="evidence-rows"',
        'id="source-query"',
        'id="source-rows"',
        'id="download-list"',
        'id="validation-facts"',
        'id="citation-text"',
        'id="archive-version"',
        'id="archive-doi"',
        'id="web-version"',
        "/api/download/evidence_release.csv",
        "/api/download/all_tables.zip",
        "/api/download/source_document.csv",
        "/api/download/curation_audit.csv",
        "/api/data_availability",
        "/api/download_manifest",
        "/bioschemas.json",
    ]:
        if marker not in html:
            fail(f"missing simplified release UI marker: {marker}")

    app_js = get("/app.js?v=contract")
    for marker in [
        "getJson",
        "setReleaseCounts",
        "renderEvidence",
        "renderSources",
        "renderDownloads",
        "renderValidation",
        "renderCitation",
        "copyCitation",
        "init",
        "/api/metadata",
        "/api/stats",
        "/api/evidence_records?limit=1000",
        "/api/sources?limit=1000",
        "/api/download_manifest",
        "/api/independent_validation",
        "/api/citation",
    ]:
        if marker not in app_js:
            fail(f"missing simplified frontend contract marker: {marker}")

    frontend_text = f"{html}\n{app_js}"
    for marker in RETIRED_PUBLIC_PATHS:
        if marker in frontend_text:
            fail(f"retired public path is still linked by the frontend: {marker}")
    for marker in [
        'id="search"',
        'id="ask"',
        'id="sequence"',
        'id="triage"',
        'id="agent"',
        'id="submit"',
        "release_batches",
        "availability_statement_draft",
        "candidate_records",
        "curation_candidate",
        "curation_queue",
        "assay.csv",
    ]:
        if marker in frontend_text:
            fail(f"retired frontend contract is still exposed: {marker}")

    metadata = get_json("/api/metadata")
    stats = get_json("/api/stats")
    assert_release_counts(metadata, stats)

    evidence_records = get_json("/api/evidence_records?limit=1000")
    if not isinstance(evidence_records, list) or len(evidence_records) != 737:
        fail("evidence_records endpoint must expose exactly 737 release rows")
    domains = {
        domain: sum(1 for row in evidence_records if row.get("evidence_domain") == domain)
        for domain in ("toxicity", "offtarget")
    }
    if domains != {"toxicity": 626, "offtarget": 111}:
        fail("evidence_records domain counts must be 626 toxicity and 111 off-target")

    for path, expected in [
        ("/api/sources?limit=1000", 660),
        ("/api/molecules?limit=1000", 524),
        ("/api/audit?limit=1000", 737),
    ]:
        payload = get_json(path)
        if not isinstance(payload, list) or len(payload) != expected:
            fail(f"{path} must expose exactly {expected} release rows")

    for path in [
        "/api/coverage",
        "/api/independent_validation",
        "/api/data_availability",
    ]:
        payload = get_json(path)
        if not isinstance(payload, dict):
            fail(f"{path} returned a non-object payload")
        assert_no_internal_work_keys(payload, path)

    validation = get_json("/api/independent_validation")
    sample = validation.get("sample", {})
    metrics = validation.get("metrics", {})
    if (
        sample.get("sample_rows") != 126
        or sample.get("machine_accept_rows") != 90
        or sample.get("false_accept_rows") != 66
        or metrics.get("false_accept_rate") != 0.73
        or metrics.get("wilson_95_ci") != [0.63, 0.81]
    ):
        fail("independent validation differs from the submitted manuscript audit summary")

    data_availability = get_json("/api/data_availability")
    if "availability_statement_draft" in data_availability:
        fail("data_availability endpoint exposes a draft statement")
    if not data_availability.get("availability_statement"):
        fail("data_availability endpoint is missing its public statement")

    citation = get_json("/api/citation")
    archived = citation.get("archived_snapshot", {})
    web_release = citation.get("web_release", {})
    if archived.get("version") != ARCHIVED_VERSION or archived.get("doi") != ARCHIVED_DOI:
        fail("citation endpoint does not identify the manuscript-cited archived snapshot")
    if web_release.get("version") != WEB_VERSION:
        fail("citation endpoint does not identify the current web release")
    if not citation.get("preferred_citation"):
        fail("citation endpoint is missing the preferred citation")

    bioschemas = get_json("/bioschemas.json")
    if not isinstance(bioschemas, dict) or bioschemas.get("@type") != "Dataset":
        fail("bioschemas.json must expose Dataset JSON-LD")

    manifest = get_json("/api/download_manifest")
    if not isinstance(manifest, dict) or manifest.get("data_release_version") != WEB_VERSION:
        fail("download manifest does not report web release 1.0.2")
    files = manifest.get("files", [])
    if not isinstance(files, list):
        fail("download manifest files field is malformed")
    by_name = {
        entry.get("filename"): entry
        for entry in files
        if isinstance(entry, dict) and entry.get("filename")
    }
    for filename, expected_rows in {
        "evidence_release.csv": 737,
        "source_document.csv": 660,
        "molecule.csv": 524,
        "curation_audit.csv": 737,
        "benchmark_split.csv": 344,
        "benchmark_reference_splits.csv": 344,
        "source_license_manifest_v1.csv": 660,
    }.items():
        entry = by_name.get(filename)
        if not isinstance(entry, dict) or entry.get("rows") != expected_rows:
            fail(f"download manifest {filename} row count must be {expected_rows}")
        checksum = str(entry.get("sha256") or "")
        if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum.lower()):
            fail(f"download manifest {filename} has no valid SHA-256 checksum")
    for filename in [
        "assay.csv",
        "curation_queue.csv",
        "curation_candidate.csv",
        "curation_candidates_filtered.csv",
        "independent_curation_validation_template.csv",
        "sequence_modification_curation_template.csv",
        "core_oligo_field_curation_packet.csv",
        "closest_work_matrix_v1.csv",
        "oligovigil_agent_pack.zip",
    ]:
        if filename in by_name:
            fail(f"download manifest exposes withheld file: {filename}")

    for path, expected_rows in [
        ("/api/download/source_document.csv", 660),
        ("/api/download/molecule.csv", 524),
        ("/api/download/toxicity_endpoint.csv", 626),
        ("/api/download/offtarget_evidence.csv", 111),
        ("/api/download/evidence_release.csv", 737),
        ("/api/download/curation_audit.csv", 737),
        ("/api/download/benchmark_split.csv", 344),
        ("/api/download/benchmark_reference_splits.csv", 344),
        ("/api/manifest/source_license_manifest_v1.csv", 660),
    ]:
        rows = get_csv_rows(path)
        if len(rows) != expected_rows:
            fail(f"{path} has {len(rows)} rows; expected {expected_rows}")

    for path in RETIRED_PUBLIC_PATHS:
        assert_not_found(path)

    print("frontend_contract_check=pass")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"frontend_contract_check=fail reason={exc}", file=sys.stderr)
        raise

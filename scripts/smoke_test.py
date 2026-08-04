from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

try:
    from test_public_static_release import collect_public_asset_failures
except ModuleNotFoundError as error:
    if error.name != "test_public_static_release":
        raise
    from scripts.test_public_static_release import collect_public_asset_failures

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
SOURCE_CANDIDATES = ROOT / "data" / "manifests" / "source_candidates_v1.csv"
SOURCE_CANDIDATES_EXPANDED = ROOT / "data" / "manifests" / "source_candidates_v2.csv"
SOURCE_CANDIDATES_V3 = ROOT / "data" / "manifests" / "source_candidates_v3.csv"
SOURCE_CANDIDATES_V4 = ROOT / "data" / "manifests" / "source_candidates_v4.csv"
SOURCE_CANDIDATES_V5 = ROOT / "data" / "manifests" / "source_candidates_v5.csv"
SOURCE_CANDIDATES_V6 = ROOT / "data" / "manifests" / "source_candidates_v6.csv"
BASE_URL = "http://127.0.0.1:8077"


def fail(message: str) -> None:
    raise AssertionError(message)


def get_json(path: str) -> object:
    last_error: Exception | None = None
    for _ in range(8):
        try:
            with urlopen(f"{BASE_URL}{path}", timeout=5) as response:
                if response.status != 200:
                    fail(f"{path} returned {response.status}")
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise last_error or AssertionError(f"{path} failed")


def assert_not_found(path: str) -> None:
    try:
        with urlopen(f"{BASE_URL}{path}", timeout=5) as response:
            fail(f"{path} returned {response.status}; expected 404")
    except HTTPError as error:
        if error.code != 404:
            raise


def find_internal_work_key(payload: object, path: str = "$") -> str | None:
    forbidden_keys = {
        "candidate_records",
        "queue_tasks",
        "curation_candidate",
        "curation_candidates",
        "curation_queue",
    }
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in forbidden_keys:
                return child_path
            found = find_internal_work_key(value, child_path)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found = find_internal_work_key(value, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def check_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        source_count = conn.execute("SELECT COUNT(*) FROM source_document").fetchone()[0]
        if source_count < 30000:
            fail("expected at least 30000 source documents after remote off-target expansion")

        queue_count = conn.execute("SELECT COUNT(*) FROM curation_queue").fetchone()[0]
        if queue_count < 36000:
            fail("expected at least 36000 curation queue tasks after 10x expansion")

        candidate_count = conn.execute("SELECT COUNT(*) FROM curation_candidate").fetchone()[0]
        if candidate_count < 10000:
            fail("expected at least 10000 curation candidate records after 10x expansion")

        toxicity_count = conn.execute("SELECT COUNT(*) FROM toxicity_endpoint").fetchone()[0]
        offtarget_count = conn.execute("SELECT COUNT(*) FROM offtarget_evidence").fetchone()[0]
        benchmark_count = conn.execute("SELECT COUNT(*) FROM benchmark_split").fetchone()[0]
        release_count = toxicity_count + offtarget_count
        if toxicity_count != 626 or offtarget_count != 111 or release_count != 737:
            fail("release evidence counts must remain 626 toxicity + 111 off-target = 737")
        if benchmark_count != 344:
            fail("benchmark_split must contain exactly 344 manuscript-aligned rows")
        release_without_audit = conn.execute("""
            SELECT SUM(n)
            FROM (
                SELECT COUNT(*) AS n
                FROM toxicity_endpoint AS entity
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM curation_audit AS audit
                    WHERE audit.entity_table = 'toxicity_endpoint'
                      AND audit.entity_id = entity.id
                      AND audit.validation_status = 'curator_verified'
                      AND audit.curator_decision = 'accept'
                )
                UNION ALL
                SELECT COUNT(*) AS n
                FROM offtarget_evidence AS entity
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM curation_audit AS audit
                    WHERE audit.entity_table = 'offtarget_evidence'
                      AND audit.entity_id = entity.id
                      AND audit.validation_status = 'curator_verified'
                      AND audit.curator_decision = 'accept'
                )
            )
            """).fetchone()[0]
        if release_without_audit:
            fail("release evidence rows must have curator_verified accept audit records")
        invalid_release_grades = conn.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT evidence_grade, source_location FROM toxicity_endpoint
                UNION ALL
                SELECT evidence_grade, source_location FROM offtarget_evidence
            )
            WHERE evidence_grade NOT IN ('A', 'B', 'C')
               OR source_location IS NULL
               OR source_location = ''
            """).fetchone()[0]
        if invalid_release_grades:
            fail("release evidence rows must have A/B/C grade and non-empty source location")
        benchmark_invalid = conn.execute("""
            SELECT COUNT(*)
            FROM benchmark_split AS split
            LEFT JOIN toxicity_endpoint AS tox
              ON split.entity_table = 'toxicity_endpoint' AND split.entity_id = tox.id
            LEFT JOIN offtarget_evidence AS off
              ON split.entity_table = 'offtarget_evidence' AND split.entity_id = off.id
            WHERE COALESCE(tox.evidence_grade, off.evidence_grade, '') NOT IN ('A', 'B')
            """).fetchone()[0]
        if benchmark_invalid:
            fail("benchmark splits may only reference Grade A/B release evidence")

        duplicate_pmids = conn.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT pmid
                FROM source_document
                WHERE pmid IS NOT NULL AND pmid != ''
                GROUP BY pmid
                HAVING COUNT(*) > 1
            )
            """).fetchone()[0]
        if duplicate_pmids:
            fail("source_document contains duplicate PMIDs")

        missing_queue_sources = conn.execute("""
            SELECT COUNT(*)
            FROM curation_queue AS queue
            LEFT JOIN source_document AS source ON source.id = queue.source_document_id
            WHERE source.id IS NULL
            """).fetchone()[0]
        if missing_queue_sources:
            fail("curation_queue contains missing source_document references")

        missing_candidate_refs = conn.execute("""
            SELECT COUNT(*)
            FROM curation_candidate AS candidate
            LEFT JOIN curation_queue AS queue ON queue.id = candidate.queue_id
            LEFT JOIN source_document AS source ON source.id = candidate.source_document_id
            WHERE queue.id IS NULL OR source.id IS NULL
            """).fetchone()[0]
        if missing_candidate_refs:
            fail("curation_candidate contains missing queue/source references")

        raw_abstract_leak = conn.execute("""
            SELECT COUNT(*)
            FROM curation_candidate
            WHERE redistribution_level != 'derived_annotations_only'
            """).fetchone()[0]
        if raw_abstract_leak:
            fail("curation candidates must remain derived annotations only")

        crispr_core = conn.execute(
            "SELECT COUNT(*) FROM modality WHERE name LIKE '%CRISPR%' AND in_core_scope = 1"
        ).fetchone()[0]
        if crispr_core:
            fail("CRISPR guide RNA must not be in core scope")

        crispr_molecules = conn.execute("""
            SELECT COUNT(*)
            FROM molecule
            JOIN modality ON molecule.modality_id = modality.id
            WHERE modality.name LIKE '%CRISPR%'
            """).fetchone()[0]
        if crispr_molecules:
            fail("CRISPR guide RNA must not appear in molecule records")

        unproven_release = conn.execute("""
            SELECT COUNT(*)
            FROM curation_audit
            WHERE validation_status IN (
                'needs_full_text_check',
                'unverified',
                'curator_verified_abstract_level'
            )
              AND curator_decision = 'accept'
            """).fetchone()[0]
        if unproven_release:
            fail("unverified or abstract-level records cannot be accepted")

        batch_script_audit = conn.execute("""
            SELECT COUNT(*)
            FROM curation_audit
            WHERE extractor_model_or_script = 'build_curator_batch1.py'
               OR extraction_method LIKE '%curator_batch1%'
            """).fetchone()[0]
        if batch_script_audit:
            fail("disabled curator batch1 script must not appear in release audit records")
    finally:
        conn.close()


def check_api() -> None:
    health = get_json("/api/health")
    if not isinstance(health, dict) or not health.get("ok"):
        fail("health check failed")

    stats = get_json("/api/stats")
    if not isinstance(stats, dict) or "counts" not in stats:
        fail("stats payload malformed")
    counts = stats.get("counts", {})
    release_count = int(counts.get("toxicity_endpoint", 0)) + int(
        counts.get("offtarget_evidence", 0)
    )
    for key, expected in {
        "source_document": 660,
        "molecule": 524,
        "curation_audit": 737,
        "benchmark_split": 344,
    }.items():
        if counts.get(key) != expected:
            fail(f"public stats {key} count must be {expected}")
    if release_count != 737:
        fail("public stats release evidence total must be 737")
    internal_key = find_internal_work_key(stats)
    if internal_key is not None:
        fail(f"public stats expose withheld curation work at {internal_key}")

    expected_endpoints = [
        "/api/metadata",
        "/api/summary",
        "/api/facets",
        "/api/coverage",
        "/api/independent_validation",
        "/api/data_availability",
        "/api/citation",
        "/bioschemas.json",
        "/api/download_manifest",
        "/api/downloads",
        "/api/sources?limit=1000",
        "/api/molecules?limit=1000",
        "/api/evidence",
        "/api/evidence_records?limit=1000",
        "/api/benchmark",
        "/api/benchmark_baseline_results",
        "/api/benchmark_tasks",
        "/api/audit?limit=1000",
        "/api/data_dictionary",
    ]
    payloads: dict[str, object] = {}
    for endpoint in expected_endpoints:
        payload = get_json(endpoint)
        if payload is None:
            fail(f"{endpoint} returned empty payload")
        internal_key = find_internal_work_key(payload)
        if internal_key is not None:
            fail(f"{endpoint} exposes withheld curation work at {internal_key}")
        payloads[endpoint] = payload

    metadata = payloads["/api/metadata"]
    if not isinstance(metadata, dict) or metadata.get("data_release_version") != "1.0.2":
        fail("metadata endpoint must report web release 1.0.2")
    release_snapshot = metadata.get("release_snapshot", {})
    if release_snapshot != {
        "verified_release_records": 737,
        "toxicity_records": 626,
        "offtarget_records": 111,
        "benchmark_split_records": 344,
        "primary_studies": 660,
    }:
        fail("metadata release snapshot differs from the submitted manuscript contract")

    for endpoint, expected_rows in [
        ("/api/evidence_records?limit=1000", 737),
        ("/api/sources?limit=1000", 660),
        ("/api/molecules?limit=1000", 524),
        ("/api/audit?limit=1000", 737),
    ]:
        payload = payloads[endpoint]
        if not isinstance(payload, list) or len(payload) != expected_rows:
            fail(f"{endpoint} must expose exactly {expected_rows} release rows")

    evidence_records = payloads["/api/evidence_records?limit=1000"]
    evidence_domains = {
        domain: sum(1 for row in evidence_records if row.get("evidence_domain") == domain)
        for domain in ("toxicity", "offtarget")
    }
    if evidence_domains != {"toxicity": 626, "offtarget": 111}:
        fail("evidence API must expose 626 toxicity and 111 off-target rows")

    data_availability = payloads["/api/data_availability"]
    if not isinstance(data_availability, dict):
        fail("data_availability endpoint returned a malformed payload")
    if "availability_statement_draft" in data_availability:
        fail("data_availability endpoint exposes a draft statement")
    if not data_availability.get("availability_statement"):
        fail("data_availability endpoint is missing its public statement")

    citation = payloads["/api/citation"]
    if not isinstance(citation, dict):
        fail("citation endpoint returned a malformed payload")
    archived = citation.get("archived_snapshot", {})
    web_release = citation.get("web_release", {})
    if archived.get("version") != "v1.0.1" or archived.get("doi") != ("10.5281/zenodo.20633779"):
        fail("citation endpoint does not identify the manuscript-cited archived snapshot")
    if web_release.get("version") != "1.0.2":
        fail("citation endpoint does not identify the current web release")

    benchmark = payloads["/api/benchmark"]
    if not isinstance(benchmark, dict) or benchmark.get("benchmark_eligible_records") != 344:
        fail("benchmark endpoint must report exactly 344 eligible release rows")

    baseline_results = payloads["/api/benchmark_baseline_results"]
    if not isinstance(baseline_results, list) or len(baseline_results) != 16:
        fail("benchmark_baseline_results endpoint must expose exactly 16 rows")
    benchmark_tasks = payloads["/api/benchmark_tasks"]
    if not isinstance(benchmark_tasks, list) or len(benchmark_tasks) != 2:
        fail("benchmark_tasks endpoint must expose exactly two task cards")

    with urlopen(f"{BASE_URL}/api/download/source_document.csv", timeout=5) as response:
        body = response.read().decode("utf-8")
    source_rows = list(csv.DictReader(io.StringIO(body)))
    if not source_rows or "source_url" not in source_rows[0]:
        fail("source_document.csv does not contain the expected release columns")
    if len(source_rows) != 660:
        fail("source_document.csv must contain exactly 660 release-linked sources")

    with urlopen(f"{BASE_URL}/api/download/all_tables.zip", timeout=5) as response:
        zip_body = response.read()
    if len(zip_body) < 1000:
        fail("all-table zip download is unexpectedly small")

    with urlopen(f"{BASE_URL}/api/download/evidence_release.csv", timeout=5) as response:
        evidence_release = response.read().decode("utf-8")
    if "evidence_domain" not in evidence_release:
        fail("evidence release CSV is missing its header")
    if len(list(csv.DictReader(io.StringIO(evidence_release)))) != 737:
        fail("evidence release CSV must contain exactly 737 release rows")

    with urlopen(f"{BASE_URL}/api/download/benchmark_reference_splits.csv", timeout=5) as response:
        benchmark_splits = response.read().decode("utf-8")
    if "task_name" not in benchmark_splits or "leakage_group" not in benchmark_splits:
        fail("benchmark reference split CSV is missing expected columns")
    if len(list(csv.DictReader(io.StringIO(benchmark_splits)))) != 344:
        fail("benchmark reference split CSV must contain exactly 344 rows")

    validation = payloads["/api/independent_validation"]
    sample = validation.get("sample", {}) if isinstance(validation, dict) else {}
    metrics = validation.get("metrics", {}) if isinstance(validation, dict) else {}
    if (
        sample.get("sample_rows") != 126
        or sample.get("machine_accept_rows") != 90
        or sample.get("false_accept_rows") != 66
        or metrics.get("false_accept_rate") != 0.73
        or metrics.get("wilson_95_ci") != [0.63, 0.81]
    ):
        fail("independent validation API does not match the submitted audit summary")

    assert_not_found("/api/download/independent_curation_validation_template.csv")

    with urlopen(f"{BASE_URL}/api/download/benchmark_baseline_results.csv", timeout=5) as response:
        baseline_results = response.read().decode("utf-8")
    if (
        "baseline_model" not in baseline_results
        or "macro_f1" not in baseline_results
        or "coverage" not in baseline_results
    ):
        fail("benchmark baseline result CSV is missing expected columns")

    with urlopen(f"{BASE_URL}/api/manifest/license_manifest_v1.csv", timeout=5) as response:
        manifest = response.read().decode("utf-8")
    for marker in ["PubMed metadata", "PMC Open Access subset", "linkout_only"]:
        if marker not in manifest:
            fail(f"license manifest download is missing release guardrail: {marker}")
    manifest_lower = manifest.lower()
    if "drugbank" in manifest_lower or "closest_work" in manifest_lower:
        fail("license manifest exposes a non-release source class")

    with urlopen(f"{BASE_URL}/api/manifest/source_license_manifest_v1.csv", timeout=5) as response:
        source_license = response.read().decode("utf-8")
    if (
        "raw_text_stored" not in source_license
        or "derived_annotation_allowed" not in source_license
    ):
        fail("source license manifest is missing record-level reuse fields")
    if len(list(csv.DictReader(io.StringIO(source_license)))) != 660:
        fail("source license manifest must contain exactly 660 release-linked sources")

    with urlopen(f"{BASE_URL}/api/manifest/data_dictionary_v1.csv", timeout=5) as response:
        data_dictionary = response.read().decode("utf-8")
    if "release_status" not in data_dictionary:
        fail("data dictionary manifest is missing release_status fields")
    if "curation_candidate" in data_dictionary or "curation_queue" in data_dictionary:
        fail("data dictionary exposes withheld curation work tables")

    assert_not_found("/api/manifest/curator_review_template_v1.csv")
    for path in [
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
        "/agent.json",
        "/.well-known/ai-plugin.json",
        "/.well-known/nlweb.json",
        "/.well-known/oligovigil-agent.json",
        "/mcp.json",
        "/nlweb.json",
        "/llms.txt",
        "/llms-full.txt",
        "/api/download/oligovigil_agent_pack.zip",
        "/api/curation_queue",
        "/api/curation_candidates",
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
    ]:
        assert_not_found(path)


def check_manifests() -> None:
    with SOURCE_CANDIDATES.open("r", encoding="utf-8", newline="") as handle:
        seen_pmids: set[str] = set()
        duplicate_pmids: set[str] = set()
        for row in csv.DictReader(handle):
            pmid = row.get("pmid") or ""
            if not pmid:
                continue
            if pmid in seen_pmids:
                duplicate_pmids.add(pmid)
            seen_pmids.add(pmid)
    if duplicate_pmids:
        fail(f"source candidate manifest contains duplicate PMIDs: {sorted(duplicate_pmids)}")
    if SOURCE_CANDIDATES_EXPANDED.exists():
        with SOURCE_CANDIDATES_EXPANDED.open("r", encoding="utf-8", newline="") as handle:
            expanded_rows = list(csv.DictReader(handle))
        if len(expanded_rows) < 50:
            fail("expanded source candidate manifest has fewer than 50 rows")
        seen_expanded: set[str] = set()
        duplicate_expanded: set[str] = set()
        for row in expanded_rows:
            pmid = row.get("pmid") or ""
            if not pmid:
                continue
            if pmid in seen_expanded:
                duplicate_expanded.add(pmid)
            seen_expanded.add(pmid)
        if duplicate_expanded:
            fail(
                f"expanded source candidate manifest contains duplicate PMIDs: {sorted(duplicate_expanded)}"
            )
    if SOURCE_CANDIDATES_V3.exists():
        with SOURCE_CANDIDATES_V3.open("r", encoding="utf-8", newline="") as handle:
            v3_rows = list(csv.DictReader(handle))
        if len(v3_rows) < 400:
            fail("v3 source candidate manifest has fewer than 400 rows")
        seen_v3: set[str] = set()
        duplicate_v3: set[str] = set()
        for row in v3_rows:
            pmid = row.get("pmid") or ""
            if not pmid:
                continue
            if pmid in seen_v3:
                duplicate_v3.add(pmid)
            seen_v3.add(pmid)
        if duplicate_v3:
            fail(f"v3 source candidate manifest contains duplicate PMIDs: {sorted(duplicate_v3)}")
    if SOURCE_CANDIDATES_V4.exists():
        with SOURCE_CANDIDATES_V4.open("r", encoding="utf-8", newline="") as handle:
            v4_rows = list(csv.DictReader(handle))
        if len(v4_rows) < 650:
            fail("v4 source candidate manifest has fewer than 650 rows")
        seen_v4: set[str] = set()
        duplicate_v4: set[str] = set()
        for row in v4_rows:
            pmid = row.get("pmid") or ""
            if not pmid:
                continue
            if pmid in seen_v4:
                duplicate_v4.add(pmid)
            seen_v4.add(pmid)
        if duplicate_v4:
            fail(f"v4 source candidate manifest contains duplicate PMIDs: {sorted(duplicate_v4)}")
    if SOURCE_CANDIDATES_V5.exists():
        with SOURCE_CANDIDATES_V5.open("r", encoding="utf-8", newline="") as handle:
            v5_rows = list(csv.DictReader(handle))
        if len(v5_rows) < 13000:
            fail("v5 source candidate manifest has fewer than 13000 rows")
        seen_v5: set[str] = set()
        duplicate_v5: set[str] = set()
        for row in v5_rows:
            pmid = row.get("pmid") or ""
            if not pmid:
                continue
            if pmid in seen_v5:
                duplicate_v5.add(pmid)
            seen_v5.add(pmid)
        if duplicate_v5:
            fail(f"v5 source candidate manifest contains duplicate PMIDs: {sorted(duplicate_v5)}")
    if SOURCE_CANDIDATES_V6.exists():
        with SOURCE_CANDIDATES_V6.open("r", encoding="utf-8", newline="") as handle:
            v6_rows = list(csv.DictReader(handle))
        if len(v6_rows) < 30000:
            fail("v6 source candidate manifest has fewer than 30000 rows")
        seen_v6: set[str] = set()
        duplicate_v6: set[str] = set()
        for row in v6_rows:
            pmid = row.get("pmid") or ""
            if not pmid:
                continue
            if pmid in seen_v6:
                duplicate_v6.add(pmid)
            seen_v6.add(pmid)
        if duplicate_v6:
            fail(f"v6 source candidate manifest contains duplicate PMIDs: {sorted(duplicate_v6)}")


def main() -> None:
    check_db()
    check_manifests()
    scanned, public_failures = collect_public_asset_failures()
    if public_failures:
        details = "; ".join(sorted(public_failures)[:10])
        fail(f"public static asset checks failed after scanning {scanned} assets: {details}")
    check_api()
    print("smoke_test=pass")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"smoke_test=fail reason={exc}", file=sys.stderr)
        raise

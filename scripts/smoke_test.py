from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import time
import zipfile
from pathlib import Path
from urllib.request import urlopen


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
        # Release is the human curator-verified survivor set (~658) after v2 + human
        # re-curation demoted the inflated v1 machine pre-curation. The old >=2000 gate
        # encoded the v1 over-count and is intentionally retired.
        if release_count < 600:
            fail("expected at least 600 human curator-verified release evidence records")
        if release_count == 0 and benchmark_count != 0:
            fail("benchmark_split must remain empty until verified release records exist")
        release_without_audit = conn.execute(
            """
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
            """
        ).fetchone()[0]
        if release_without_audit:
            fail("release evidence rows must have curator_verified accept audit records")
        invalid_release_grades = conn.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT evidence_grade, source_location FROM toxicity_endpoint
                UNION ALL
                SELECT evidence_grade, source_location FROM offtarget_evidence
            )
            WHERE evidence_grade NOT IN ('A', 'B', 'C')
               OR source_location IS NULL
               OR source_location = ''
            """
        ).fetchone()[0]
        if invalid_release_grades:
            fail("release evidence rows must have A/B/C grade and non-empty source location")
        benchmark_invalid = conn.execute(
            """
            SELECT COUNT(*)
            FROM benchmark_split AS split
            LEFT JOIN toxicity_endpoint AS tox
              ON split.entity_table = 'toxicity_endpoint' AND split.entity_id = tox.id
            LEFT JOIN offtarget_evidence AS off
              ON split.entity_table = 'offtarget_evidence' AND split.entity_id = off.id
            WHERE COALESCE(tox.evidence_grade, off.evidence_grade, '') NOT IN ('A', 'B')
            """
        ).fetchone()[0]
        if benchmark_invalid:
            fail("benchmark splits may only reference Grade A/B release evidence")

        duplicate_pmids = conn.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT pmid
                FROM source_document
                WHERE pmid IS NOT NULL AND pmid != ''
                GROUP BY pmid
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        if duplicate_pmids:
            fail("source_document contains duplicate PMIDs")

        missing_queue_sources = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_queue AS queue
            LEFT JOIN source_document AS source ON source.id = queue.source_document_id
            WHERE source.id IS NULL
            """
        ).fetchone()[0]
        if missing_queue_sources:
            fail("curation_queue contains missing source_document references")

        missing_candidate_refs = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_candidate AS candidate
            LEFT JOIN curation_queue AS queue ON queue.id = candidate.queue_id
            LEFT JOIN source_document AS source ON source.id = candidate.source_document_id
            WHERE queue.id IS NULL OR source.id IS NULL
            """
        ).fetchone()[0]
        if missing_candidate_refs:
            fail("curation_candidate contains missing queue/source references")

        raw_abstract_leak = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_candidate
            WHERE redistribution_level != 'derived_annotations_only'
            """
        ).fetchone()[0]
        if raw_abstract_leak:
            fail("curation candidates must remain derived annotations only")

        crispr_core = conn.execute(
            "SELECT COUNT(*) FROM modality WHERE name LIKE '%CRISPR%' AND in_core_scope = 1"
        ).fetchone()[0]
        if crispr_core:
            fail("CRISPR guide RNA must not be in core scope")

        crispr_molecules = conn.execute(
            """
            SELECT COUNT(*)
            FROM molecule
            JOIN modality ON molecule.modality_id = modality.id
            WHERE modality.name LIKE '%CRISPR%'
            """
        ).fetchone()[0]
        if crispr_molecules:
            fail("CRISPR guide RNA must not appear in molecule records")

        unproven_release = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_audit
            WHERE validation_status IN (
                'needs_full_text_check',
                'unverified',
                'curator_verified_abstract_level'
            )
              AND curator_decision = 'accept'
            """
        ).fetchone()[0]
        if unproven_release:
            fail("unverified or abstract-level records cannot be accepted")

        batch_script_audit = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_audit
            WHERE extractor_model_or_script = 'build_curator_batch1.py'
               OR extraction_method LIKE '%curator_batch1%'
            """
        ).fetchone()[0]
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

    for endpoint in [
        "/api/metadata",
        "/api/summary",
        "/api/facets",
        "/api/quality",
        "/api/coverage",
        "/api/examples",
        "/api/ask?q=Show%20GalNAc%20liver%20toxicity%20Grade%20A%2FB%20evidence",
        "/api/help",
        "/api/release_status",
        "/api/submission_pack",
        "/api/field_completeness",
        "/api/core_oligo_fields",
        "/api/curation_protocol",
        "/api/independent_validation",
        "/api/novelty_position",
        "/api/data_availability",
        "/api/archive_readiness",
        "/api/adoption_packet",
        "/api/agent_access",
        "/api/agent_connect",
        "/agent.json",
        "/mcp.json",
        "/api/citation",
        "/api/use_cases",
        "/api/client_examples",
        "/api/submission_schema",
        "/api/sequence_coverage",
        "/api/offtarget_taxonomy",
        "/api/sequence_search?sequence=AUGCUACUGACUGA&modification=galnac&target=PCSK9",
        "/api/safety_triage?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human",
        "/api/safety_dossier?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human",
        "/api/evidence_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human",
        "/api/prov_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human",
        "/bioschemas.json",
        "/nlweb.json",
        "/api/modification_profile?term=galnac",
        "/api/download_manifest",
        "/api/downloads",
        "/api/openapi.json",
        "/api/search?q=toxicity",
        "/api/source_detail?q=hepatotoxicity",
        "/api/sources",
        "/api/molecules",
        "/api/evidence",
        "/api/evidence_records?domain=toxicity&grade=C",
        "/api/evidence_detail?domain=toxicity&id=1",
        "/api/benchmark",
        "/api/benchmark_baseline_results",
        "/api/audit?entity_table=toxicity_endpoint",
        "/api/readiness",
        "/api/closest_work",
        "/api/data_dictionary",
        "/api/curation_queue",
        "/api/curation_candidates",
    ]:
        payload = get_json(endpoint)
        if payload is None:
            fail(f"{endpoint} returned empty payload")

    triage = get_json(
        "/api/safety_triage?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human"
    )
    if not isinstance(triage, dict) or not triage.get("risk_matrix"):
        fail("safety triage payload missing risk matrix")
    if triage.get("triage_policy", {}).get("prediction_mode") != "no de novo safety prediction":
        fail("safety triage must expose no-prediction policy")
    if not triage.get("dossier"):
        fail("safety triage payload missing dossier metadata")

    dossier = get_json(
        "/api/safety_dossier?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human"
    )
    if not isinstance(dossier, dict) or not dossier.get("evidence_graph"):
        fail("safety dossier payload missing evidence graph")
    graph = get_json(
        "/api/evidence_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human"
    )
    if not isinstance(graph, dict) or graph.get("counts", {}).get("nodes", 0) < 5:
        fail("evidence graph payload missing query graph nodes")
    prov = get_json(
        "/api/prov_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human"
    )
    if prov.get("standard") != "W3C PROV-compatible JSON profile":
        fail("PROV graph payload missing W3C profile")

    agent_access = get_json("/api/agent_access")
    if not isinstance(agent_access, dict) or not agent_access.get("guardrails"):
        fail("agent access payload missing guardrails")
    if agent_access.get("pack", {}).get("files", 0) < 14:
        fail("agent access pack metadata is incomplete")
    if not agent_access.get("tool_profiles"):
        fail("agent access payload missing universal tool profiles")

    agent_connect = get_json("/api/agent_connect")
    if not isinstance(agent_connect, dict) or not agent_connect.get("not_tool_specific"):
        fail("agent connect payload must be tool agnostic")
    if len(agent_connect.get("entrypoints", [])) < 5:
        fail("agent connect payload missing universal entrypoints")

    with urlopen(f"{BASE_URL}/api/download/source_document.csv", timeout=5) as response:
        body = response.read().decode("utf-8")
    if "source_url" not in body or "theRNA" not in body:
        fail("download CSV does not contain expected source rows")

    with urlopen(f"{BASE_URL}/api/download/all_tables.zip", timeout=5) as response:
        zip_body = response.read()
    if len(zip_body) < 1000:
        fail("all-table zip download is unexpectedly small")

    with urlopen(f"{BASE_URL}/llms.txt", timeout=5) as response:
        llms_text = response.read().decode("utf-8")
    if "Verified release evidence supports claims" not in llms_text:
        fail("llms.txt missing verified evidence guardrail")

    with urlopen(f"{BASE_URL}/api/download/oligovigil_agent_pack.zip", timeout=5) as response:
        agent_pack = response.read()
    with zipfile.ZipFile(io.BytesIO(agent_pack), "r") as archive:
        names = set(archive.namelist())
    if "agent_ready/mcp_server/oligovigil_mcp_server.py" not in names:
        fail("agent pack missing MCP server")
    if "agent_ready/oligovigil_skill/SKILL.md" not in names:
        fail("agent pack missing OligoVigil skill")
    if "agent_ready/connectors/universal_agent_manifest.json" not in names:
        fail("agent pack missing universal manifest")
    if "agent_ready/prompts/universal_vibecoding_connector.md" not in names:
        fail("agent pack missing universal vibe-coding connector prompt")

    with urlopen(f"{BASE_URL}/api/download/evidence_release.csv", timeout=5) as response:
        evidence_release = response.read().decode("utf-8")
    if "evidence_domain" not in evidence_release:
        fail("evidence release CSV is missing its header")
    evidence_release_lines = len([line for line in evidence_release.splitlines() if line.strip()])
    if release_count == 0 and evidence_release_lines != 1:
        fail("evidence release CSV must be header-only before verified promotion")
    if release_count > 0 and evidence_release_lines <= 1:
        fail("evidence release CSV must contain curator-verified release rows")

    with urlopen(f"{BASE_URL}/api/download/benchmark_reference_splits.csv", timeout=5) as response:
        benchmark_splits = response.read().decode("utf-8")
    if "task_name" not in benchmark_splits or "leakage_group" not in benchmark_splits:
        fail("benchmark reference split CSV is missing expected columns")
    if release_count > 0 and len([line for line in benchmark_splits.splitlines() if line.strip()]) <= 1:
        fail("benchmark reference split CSV must contain Grade A/B rows after verified promotion")

    core_fields = get_json("/api/core_oligo_fields")
    # P0 = Grade A/B benchmark-linked release rows. After honest re-curation the release is 658
    # with 345 benchmark rows, so P0 tracks the benchmark size (was >=1000 under the inflated v1).
    if not isinstance(core_fields, dict) or core_fields.get("summary", {}).get("p0_benchmark_linked_rows", 0) < 300:
        fail("core oligo field API must expose at least 300 P0 benchmark-linked rows")

    validation = get_json("/api/independent_validation")
    if not isinstance(validation, dict) or validation.get("sample", {}).get("sample_rows") != 500:
        fail("independent validation API must expose the 500-row second-review packet")

    with urlopen(f"{BASE_URL}/api/download/core_oligo_field_curation_packet.csv", timeout=5) as response:
        core_packet = response.read().decode("utf-8")
    if "missing_sequence" not in core_packet or "core-field-" not in core_packet:
        fail("core oligo field packet is missing expected curation columns")

    with urlopen(f"{BASE_URL}/api/download/independent_curation_validation_template.csv", timeout=5) as response:
        validation_packet = response.read().decode("utf-8")
    if "reviewer2_decision" not in validation_packet or "candidate_reject_control" not in validation_packet:
        fail("independent validation template is missing reviewer-2 or reject-control fields")

    with urlopen(f"{BASE_URL}/api/download/benchmark_baseline_results.csv", timeout=5) as response:
        baseline_results = response.read().decode("utf-8")
    if "baseline_model" not in baseline_results or "macro_f1" not in baseline_results or "coverage" not in baseline_results:
        fail("benchmark baseline result CSV is missing expected columns")

    with urlopen(f"{BASE_URL}/api/download/curation_candidates_filtered.csv?domain=toxicity", timeout=5) as response:
        filtered_candidates = response.read().decode("utf-8")
    if "candidate_signal" not in filtered_candidates or "toxicity" not in filtered_candidates:
        fail("filtered candidate download is missing expected toxicity candidates")

    with urlopen(f"{BASE_URL}/api/manifest/license_manifest_v1.csv", timeout=5) as response:
        manifest = response.read().decode("utf-8")
    if "DrugBank" not in manifest or "linkout_only" not in manifest:
        fail("license manifest download is missing expected guardrails")

    with urlopen(f"{BASE_URL}/api/manifest/source_license_manifest_v1.csv", timeout=5) as response:
        source_license = response.read().decode("utf-8")
    if "raw_text_stored" not in source_license or "derived_annotation_allowed" not in source_license:
        fail("source license manifest is missing record-level reuse fields")

    with urlopen(f"{BASE_URL}/api/manifest/closest_work_matrix_v1.csv", timeout=5) as response:
        closest_work = response.read().decode("utf-8")
    if "CMsiRNAdb" not in closest_work or "OligoVigil" not in closest_work:
        fail("closest-work matrix is missing critical comparators")

    with urlopen(f"{BASE_URL}/api/manifest/data_dictionary_v1.csv", timeout=5) as response:
        data_dictionary = response.read().decode("utf-8")
    if "curation_candidate" not in data_dictionary or "release_status" not in data_dictionary:
        fail("data dictionary manifest is missing expected fields")

    with urlopen(f"{BASE_URL}/api/manifest/curation_queue_v1.csv", timeout=5) as response:
        queue = response.read().decode("utf-8")
    if "evidence_domain" not in queue or "toxicity" not in queue:
        fail("curation queue manifest is missing expected tasks")

    with urlopen(f"{BASE_URL}/api/manifest/curation_candidate_v1.csv", timeout=5) as response:
        candidates = response.read().decode("utf-8")
    if "candidate_signal" not in candidates or "derived_annotations_only" not in candidates:
        fail("curation candidate manifest is missing expected guardrails")

    with urlopen(f"{BASE_URL}/api/manifest/curator_review_template_v1.csv", timeout=5) as response:
        review = response.read().decode("utf-8")
    if "curator_decision" not in review or "source_location_verified" not in review:
        fail("curator review template is missing promotion gate fields")


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
            fail(f"expanded source candidate manifest contains duplicate PMIDs: {sorted(duplicate_expanded)}")
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
    check_api()
    print("smoke_test=pass")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"smoke_test=fail reason={exc}", file=sys.stderr)
        raise

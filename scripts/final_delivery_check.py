from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DB_PATH = ROOT / "data" / "oligosafety.db"
DELIVERY_DIR = PROJECT_ROOT / "04_delivery"
REPORT_PATH = DELIVERY_DIR / "FINAL_QA_REPORT.md"
SCREENSHOT_DIR = DELIVERY_DIR / "screenshots"
RELEASE_MANIFEST_PATH = DELIVERY_DIR / "RELEASE_MANIFEST.json"
CHECKSUM_PATH = DELIVERY_DIR / "CHECKSUMS_SHA256.txt"
EXPECTED_SCREENSHOTS = [
    "oligosafetydb-final-desktop.png",
    "oligosafetydb-final-mobile.png",
]

EXPECTED_ENDPOINTS = [
    "/api/health",
    "/api/stats",
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
    "/.well-known/oligovigil-agent.json",
    "/.well-known/ai-plugin.json",
    "/mcp.json",
    "/api/citation",
    "/api/use_cases",
    "/api/case_workflows",
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
    "/api/client_examples",
    "/api/submission_schema",
    "/api/openapi.json",
    "/api/search?q=toxicity",
    "/api/source_detail?q=hepatotoxicity",
    "/api/readiness",
    "/api/closest_work",
    "/api/data_dictionary",
    "/api/sources",
    "/api/molecules",
    "/api/evidence",
    "/api/evidence_records?domain=toxicity&grade=C",
    "/api/evidence_detail?domain=toxicity&id=1",
    "/api/benchmark",
    "/api/benchmark_baseline_results",
    "/api/benchmark_tasks",
    "/api/audit?entity_table=toxicity_endpoint",
    "/api/curation_queue",
    "/api/curation_candidates",
]

EXPECTED_DOWNLOADS = [
    "/api/download/source_document.csv",
    "/api/download/molecule.csv",
    "/api/download/toxicity_endpoint.csv",
    "/api/download/offtarget_evidence.csv",
    "/api/download/evidence_release.csv",
    "/api/download/benchmark_reference_splits.csv",
    "/api/download/benchmark_baseline_results.csv",
    "/api/download/benchmark_task_cards.csv",
    "/api/download/sequence_modification_curation_template.csv",
    "/api/download/core_oligo_field_curation_packet.csv",
    "/api/download/independent_curation_validation_template.csv",
    "/api/download/curation_audit.csv",
    "/api/download/benchmark_split.csv",
    "/api/download/curation_queue.csv",
    "/api/download/curation_candidate.csv",
    "/api/download/curation_candidates_filtered.csv",
    "/api/download/all_tables.zip",
    "/api/download/oligovigil_agent_pack.zip",
    "/api/manifest/source_candidates_v1.csv",
    "/api/manifest/source_candidates_v2.csv",
    "/api/manifest/source_candidates_v3.csv",
    "/api/manifest/source_candidates_v4.csv",
    "/api/manifest/source_candidates_v5.csv",
    "/api/manifest/source_candidates_v6.csv",
    "/api/manifest/license_manifest_v1.csv",
    "/api/manifest/source_license_manifest_v1.csv",
    "/api/manifest/closest_work_matrix_v1.csv",
    "/api/manifest/data_dictionary_v1.csv",
    "/api/manifest/source_document_pubmed_v1.csv",
    "/api/manifest/curation_queue_v1.csv",
    "/api/manifest/curation_candidate_v1.csv",
    "/api/manifest/curator_review_template_v1.csv",
    "/api/manifest/sequence_modification_curation_template_v1.csv",
    "/api/manifest/core_oligo_field_curation_packet_v1.csv",
    "/api/manifest/independent_curation_validation_template_v1.csv",
    "/api/manifest/benchmark_task_cards_v1.csv",
    "/api/manifest/pubmed_discovery_candidates_v1.csv",
    "/api/manifest/pubmed_discovery_candidates_v2.csv",
    "/api/manifest/pubmed_discovery_candidates_v3.csv",
    "/api/manifest/pubmed_discovery_candidates_v4.csv",
]


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def get_json(base_url: str, path: str) -> object:
    last_error: Exception | None = None
    for _ in range(10):
        try:
            with urlopen(f"{base_url}{path}", timeout=5) as response:
                payload = response.read().decode("utf-8")
                if response.status != 200:
                    raise AssertionError(f"{path} returned {response.status}")
                return json.loads(payload)
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise last_error or AssertionError(f"{path} failed")


def head_status(base_url: str, path: str) -> tuple[int, int]:
    request = Request(f"{base_url}{path}", method="HEAD")
    with urlopen(request, timeout=5) as response:
        length = int(response.headers.get("Content-Length") or "0")
        return response.status, length


def db_checks(failures: list[str]) -> dict[str, object]:
    conn = sqlite3.connect(DB_PATH)
    try:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in [
                "source_document",
                "modality",
                "molecule",
                "assay",
                "toxicity_endpoint",
                "offtarget_evidence",
                "curation_audit",
                "benchmark_split",
                "curation_queue",
                "curation_candidate",
            ]
        }
        check(counts["source_document"] >= 13000, "source_document below 13000", failures)
        check(counts["curation_queue"] >= 36000, "curation_queue below 36000", failures)
        check(counts["curation_candidate"] >= 10000, "curation_candidate below 10000", failures)
        release_count = counts["toxicity_endpoint"] + counts["offtarget_evidence"]
        # Post v2 + independent human re-curation, the release is the human curator-verified
        # survivor set (~658), not the inflated v1 machine pre-curation count. The old >=2000
        # gate encoded the v1 over-count (~74% false-accept) and is intentionally retired.
        check(release_count >= 600, "human curator-verified release evidence below 600 rows", failures)
        check(
            release_count > 0 or counts["benchmark_split"] == 0,
            "benchmark_split must remain empty until verified release records exist",
            failures,
        )
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
        check(
            not release_without_audit,
            "release evidence rows must have curator_verified accept audit records",
            failures,
        )
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
        check(
            invalid_release_grades == 0,
            "release evidence rows must have A/B/C grade and non-empty source location",
            failures,
        )
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
        check(
            benchmark_invalid == 0,
            "benchmark splits may only reference Grade A/B release evidence",
            failures,
        )

        duplicate_pmids = conn.execute(
            """
            SELECT pmid, COUNT(*)
            FROM source_document
            WHERE pmid IS NOT NULL AND pmid != ''
            GROUP BY pmid
            HAVING COUNT(*) > 1
            """
        ).fetchall()
        check(not duplicate_pmids, f"duplicate PMIDs in source_document: {duplicate_pmids}", failures)

        missing_queue_refs = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_queue AS queue
            LEFT JOIN source_document AS source ON source.id = queue.source_document_id
            WHERE source.id IS NULL
            """
        ).fetchone()[0]
        check(missing_queue_refs == 0, "curation_queue has missing source refs", failures)

        missing_candidate_refs = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_candidate AS candidate
            LEFT JOIN curation_queue AS queue ON queue.id = candidate.queue_id
            LEFT JOIN source_document AS source ON source.id = candidate.source_document_id
            WHERE queue.id IS NULL OR source.id IS NULL
            """
        ).fetchone()[0]
        check(missing_candidate_refs == 0, "curation_candidate has missing refs", failures)

        unsafe_candidates = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_candidate
            WHERE redistribution_level != 'derived_annotations_only'
            """
        ).fetchone()[0]
        check(unsafe_candidates == 0, "curation_candidate has non-derived redistribution level", failures)

        unverified_accepts = conn.execute(
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
        check(
            unverified_accepts == 0,
            "unverified or abstract-level accepted audit records exist",
            failures,
        )

        batch_script_audit = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_audit
            WHERE extractor_model_or_script = 'build_curator_batch1.py'
               OR extraction_method LIKE '%curator_batch1%'
            """
        ).fetchone()[0]
        check(batch_script_audit == 0, "disabled curator batch1 audit records exist", failures)

        crispr_molecules = conn.execute(
            """
            SELECT COUNT(*)
            FROM molecule
            JOIN modality ON molecule.modality_id = modality.id
            WHERE modality.name LIKE '%CRISPR%'
            """
        ).fetchone()[0]
        check(crispr_molecules == 0, "CRISPR guide RNA appears in molecule records", failures)

        candidate_by_domain = conn.execute(
            """
            SELECT evidence_domain, COUNT(*)
            FROM curation_candidate
            GROUP BY evidence_domain
            ORDER BY evidence_domain
            """
        ).fetchall()
        candidate_by_confidence = conn.execute(
            """
            SELECT confidence_label, COUNT(*)
            FROM curation_candidate
            GROUP BY confidence_label
            ORDER BY confidence_label
            """
        ).fetchall()

        return {
            "counts": counts,
            "duplicate_pmids": duplicate_pmids,
            "missing_queue_refs": missing_queue_refs,
            "missing_candidate_refs": missing_candidate_refs,
            "candidate_by_domain": candidate_by_domain,
            "candidate_by_confidence": candidate_by_confidence,
        }
    finally:
        conn.close()


def manifest_checks(failures: list[str]) -> dict[str, object]:
    manifest = ROOT / "data" / "manifests" / "source_candidates_v6.csv"
    if not manifest.exists():
        failures.append("source_candidates_v6.csv is required for the source-candidate delivery manifest")
        return {
            "source_candidate_manifest": "missing",
            "source_candidate_pmids": 0,
            "duplicate_manifest_pmids": [],
        }
    seen: set[str] = set()
    duplicates: set[str] = set()
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            pmid = row.get("pmid") or ""
            if not pmid:
                continue
            if pmid in seen:
                duplicates.add(pmid)
            seen.add(pmid)
    check(not duplicates, f"duplicate PMIDs in source candidate manifest: {sorted(duplicates)}", failures)
    check(len(seen) >= 30000, "source_candidates_v6.csv has fewer than 30000 PMIDs", failures)
    return {
        "source_candidate_manifest": str(manifest.relative_to(ROOT)).replace("\\", "/"),
        "source_candidate_pmids": len(seen),
        "duplicate_manifest_pmids": sorted(duplicates),
    }


def http_checks(base_url: str, failures: list[str]) -> dict[str, object]:
    endpoint_status: dict[str, str] = {}
    for endpoint in EXPECTED_ENDPOINTS:
        try:
            payload = get_json(base_url, endpoint)
            endpoint_status[endpoint] = "200"
            check(payload is not None, f"{endpoint} returned empty payload", failures)
        except Exception as exc:
            endpoint_status[endpoint] = f"FAIL: {exc}"
            failures.append(f"{endpoint} failed: {exc}")

    download_status: dict[str, str] = {}
    for path in EXPECTED_DOWNLOADS:
        try:
            status, length = head_status(base_url, path)
            download_status[path] = f"{status}; bytes={length}"
            check(status == 200, f"{path} returned {status}", failures)
            check(length > 0, f"{path} has zero Content-Length", failures)
        except (URLError, OSError, AssertionError) as exc:
            download_status[path] = f"FAIL: {exc}"
            failures.append(f"{path} failed: {exc}")

    return {"endpoints": endpoint_status, "downloads": download_status}


def screenshot_checks(failures: list[str]) -> dict[str, int]:
    screenshots: dict[str, int] = {}
    for name in EXPECTED_SCREENSHOTS:
        path = SCREENSHOT_DIR / name
        if not path.exists():
            screenshots[name] = 0
            failures.append(f"missing screenshot: {path}")
            continue
        size = path.stat().st_size
        screenshots[name] = size
        check(size > 0, f"empty screenshot: {path}", failures)
    return screenshots


def release_artifact_checks(failures: list[str]) -> dict[str, object]:
    artifacts = {
        "RELEASE_MANIFEST.json": RELEASE_MANIFEST_PATH.stat().st_size
        if RELEASE_MANIFEST_PATH.exists()
        else 0,
        "CHECKSUMS_SHA256.txt": CHECKSUM_PATH.stat().st_size if CHECKSUM_PATH.exists() else 0,
    }
    for name, size in artifacts.items():
        check(size > 0, f"missing or empty release artifact: {name}", failures)
    if RELEASE_MANIFEST_PATH.exists():
        manifest = json.loads(RELEASE_MANIFEST_PATH.read_text(encoding="utf-8"))
        check(manifest.get("file_count", 0) > 20, "release manifest file_count is too small", failures)
        artifacts["file_count"] = manifest.get("file_count", 0)
    return artifacts


def write_report(
    base_url: str,
    db: dict[str, object],
    manifests: dict[str, object],
    http: dict[str, object],
    screenshots: dict[str, int],
    release_artifacts: dict[str, object],
    failures: list[str],
) -> None:
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    quick_tunnel = "trycloudflare.com" in base_url
    local_url = any(marker in base_url for marker in ["127.0.0.1", "localhost", "::1"])
    release_count = int(db["counts"].get("toxicity_endpoint", 0)) + int(
        db["counts"].get("offtarget_evidence", 0)
    )
    zero_verified_release = release_count == 0
    release_scale_ready = release_count >= 600
    if failures:
        status = "FAIL"
    elif quick_tunnel or local_url or zero_verified_release or not release_scale_ready:
        status = "TECHNICAL_QA_PASS__NAR_SUBMISSION_BLOCKED"
    else:
        status = "TECHNICAL_QA_PASS__NAR_PRESUBMISSION_READY"
    if quick_tunnel:
        nar_url_gate = "BLOCKED_TEMPORARY_QUICK_TUNNEL"
    elif local_url:
        nar_url_gate = "BLOCKED_LOCALHOST_URL"
    else:
        nar_url_gate = "READY_FOR_PUBLIC_URL_QA"
    release_gate = (
        "BLOCKED_ZERO_VERIFIED_RELEASE_EVIDENCE"
        if zero_verified_release
        else "READY_HUMAN_VERIFIED_RELEASE_REVIEW"
        if release_scale_ready
        else "BLOCKED_BELOW_600_HUMAN_VERIFIED_RELEASE_EVIDENCE"
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "# Final QA Report",
        "",
        f"Generated at: {now}",
        f"Base URL: `{base_url}`",
        f"Status: **{status}**",
        f"NAR submission URL gate: **{nar_url_gate}**",
        f"Verified release evidence gate: **{release_gate}**",
        f"Verified release evidence total: **{release_count}**",
        "",
        "## Database Counts",
        "",
    ]
    for key, value in db["counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Candidate Coverage", ""])
    for domain, count in db["candidate_by_domain"]:
        lines.append(f"- `{domain}`: {count}")
    lines.extend(["", "## Candidate Confidence", ""])
    for confidence, count in db["candidate_by_confidence"]:
        lines.append(f"- `{confidence}`: {count}")
    lines.extend(["", "## Manifest Checks", ""])
    lines.append(f"- source candidate manifest: `{manifests['source_candidate_manifest']}`")
    lines.append(f"- source candidate PMIDs: {manifests['source_candidate_pmids']}")
    lines.append(f"- duplicate manifest PMIDs: {manifests['duplicate_manifest_pmids']}")
    lines.extend(["", "## API Endpoints", ""])
    for path, status_text in http["endpoints"].items():
        lines.append(f"- `{path}`: {status_text}")
    lines.extend(["", "## Downloads", ""])
    for path, status_text in http["downloads"].items():
        lines.append(f"- `{path}`: {status_text}")
    lines.extend(["", "## Visual QA Artifacts", ""])
    for name, size in screenshots.items():
        lines.append(f"- `{name}`: {size} bytes")
    lines.extend(["", "## Release Artifacts", ""])
    for name, value in release_artifacts.items():
        lines.append(f"- `{name}`: {value}")
    lines.extend(["", "## Failures", ""])
    if failures:
        for failure in failures:
            lines.append(f"- {failure}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Presubmission Gate",
            "",
            "This QA report validates the local or configured deployment target. NAR presubmission still requires a stable public HTTPS URL with the same no-login behavior; temporary Quick Tunnel URLs are suitable for demonstration only.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8077")
    args = parser.parse_args()

    failures: list[str] = []
    db = db_checks(failures)
    manifests = manifest_checks(failures)
    http = http_checks(args.base_url.rstrip("/"), failures)
    screenshots = screenshot_checks(failures)
    release_artifacts = release_artifact_checks(failures)
    write_report(args.base_url.rstrip("/"), db, manifests, http, screenshots, release_artifacts, failures)

    if failures:
        print(f"final_delivery_check=fail report={REPORT_PATH}", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        raise SystemExit(1)
    print(f"final_delivery_check=pass report={REPORT_PATH}")


if __name__ == "__main__":
    main()

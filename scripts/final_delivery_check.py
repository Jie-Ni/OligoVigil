from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from test_public_static_release import collect_public_asset_failures
except ModuleNotFoundError as error:
    if error.name != "test_public_static_release":
        raise
    from scripts.test_public_static_release import collect_public_asset_failures

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
    "/api/coverage",
    "/api/independent_validation",
    "/api/data_availability",
    "/api/citation",
    "/bioschemas.json",
    "/api/download_manifest",
    "/api/downloads",
    "/api/data_dictionary",
    "/api/sources?limit=1000",
    "/api/molecules?limit=1000",
    "/api/evidence",
    "/api/evidence_records?limit=1000",
    "/api/benchmark",
    "/api/benchmark_baseline_results",
    "/api/benchmark_tasks",
    "/api/audit?limit=1000",
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
    "/api/download/benchmark_readme.md",
    "/api/download/curation_audit.csv",
    "/api/download/benchmark_split.csv",
    "/api/download/all_tables.zip",
    "/api/manifest/license_manifest_v1.csv",
    "/api/manifest/source_license_manifest_v1.csv",
    "/api/manifest/data_dictionary_v1.csv",
    "/api/manifest/benchmark_task_cards_v1.csv",
]

PROHIBITED_PUBLIC_PATHS = [
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
]

EXPECTED_REMOTE_CSV_ROWS = {
    "/api/download/source_document.csv": 660,
    "/api/download/molecule.csv": 524,
    "/api/download/toxicity_endpoint.csv": 626,
    "/api/download/offtarget_evidence.csv": 111,
    "/api/download/evidence_release.csv": 737,
    "/api/download/curation_audit.csv": 737,
    "/api/download/benchmark_split.csv": 344,
    "/api/download/benchmark_reference_splits.csv": 344,
    "/api/manifest/source_license_manifest_v1.csv": 660,
}


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


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
                "toxicity_endpoint",
                "offtarget_evidence",
                "benchmark_split",
            ]
        }
        counts["release_audit"] = conn.execute("""
            SELECT COUNT(*)
            FROM curation_audit AS audit
            WHERE audit.validation_status = 'curator_verified'
              AND audit.curator_decision = 'accept'
              AND (
                (audit.entity_table = 'toxicity_endpoint' AND EXISTS (
                    SELECT 1 FROM toxicity_endpoint AS entity WHERE entity.id = audit.entity_id
                ))
                OR
                (audit.entity_table = 'offtarget_evidence' AND EXISTS (
                    SELECT 1 FROM offtarget_evidence AS entity WHERE entity.id = audit.entity_id
                ))
              )
            """).fetchone()[0]
        release_count = counts["toxicity_endpoint"] + counts["offtarget_evidence"]
        check(
            counts["toxicity_endpoint"] == 626, "toxicity release must contain 626 rows", failures
        )
        check(
            counts["offtarget_evidence"] == 111,
            "off-target release must contain 111 rows",
            failures,
        )
        check(release_count == 737, "release evidence must contain exactly 737 rows", failures)
        check(
            counts["release_audit"] == 737, "release audit must contain exactly 737 rows", failures
        )
        check(
            counts["benchmark_split"] == 344,
            "benchmark split must contain exactly 344 rows",
            failures,
        )
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
        check(
            not release_without_audit,
            "release evidence rows must have curator_verified accept audit records",
            failures,
        )
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
        check(
            invalid_release_grades == 0,
            "release evidence rows must have A/B/C grade and non-empty source location",
            failures,
        )
        benchmark_invalid = conn.execute("""
            SELECT COUNT(*)
            FROM benchmark_split AS split
            LEFT JOIN toxicity_endpoint AS tox
              ON split.entity_table = 'toxicity_endpoint' AND split.entity_id = tox.id
            LEFT JOIN offtarget_evidence AS off
              ON split.entity_table = 'offtarget_evidence' AND split.entity_id = off.id
            WHERE COALESCE(tox.evidence_grade, off.evidence_grade, '') NOT IN ('A', 'B')
            """).fetchone()[0]
        check(
            benchmark_invalid == 0,
            "benchmark splits may only reference Grade A/B release evidence",
            failures,
        )

        return {"counts": counts}
    finally:
        conn.close()


def http_checks(base_url: str, failures: list[str]) -> dict[str, object]:
    endpoint_status: dict[str, str] = {}
    endpoint_payloads: dict[str, object] = {}
    for endpoint in EXPECTED_ENDPOINTS:
        try:
            payload = get_json(base_url, endpoint)
            endpoint_payloads[endpoint] = payload
            endpoint_status[endpoint] = "200"
            check(payload is not None, f"{endpoint} returned empty payload", failures)
            internal_key = find_internal_work_key(payload)
            check(
                internal_key is None,
                f"{endpoint} exposes withheld curation work at {internal_key}",
                failures,
            )
            if endpoint == "/api/stats" and isinstance(payload, dict):
                counts = payload.get("counts", {})
                for key, expected in {
                    "source_document": 660,
                    "molecule": 524,
                    "curation_audit": 737,
                    "benchmark_split": 344,
                }.items():
                    check(
                        counts.get(key) == expected,
                        f"public stats {key} count must be {expected}",
                        failures,
                    )
                release_count = int(counts.get("toxicity_endpoint") or 0) + int(
                    counts.get("offtarget_evidence") or 0
                )
                check(
                    release_count == 737, "public stats release evidence must total 737", failures
                )
            elif endpoint == "/api/metadata" and isinstance(payload, dict):
                check(
                    payload.get("data_release_version") == "1.0.2",
                    "metadata endpoint must report web release 1.0.2",
                    failures,
                )
                check(
                    payload.get("release_snapshot")
                    == {
                        "verified_release_records": 737,
                        "toxicity_records": 626,
                        "offtarget_records": 111,
                        "benchmark_split_records": 344,
                        "primary_studies": 660,
                    },
                    "metadata release snapshot differs from the submitted manuscript contract",
                    failures,
                )
            elif endpoint == "/api/data_availability" and isinstance(payload, dict):
                check(
                    "availability_statement_draft" not in payload,
                    "data_availability exposes a draft statement",
                    failures,
                )
                check(
                    bool(payload.get("availability_statement")),
                    "data_availability is missing its public statement",
                    failures,
                )
            elif endpoint == "/api/independent_validation" and isinstance(payload, dict):
                sample = payload.get("sample", {})
                metrics = payload.get("metrics", {})
                check(
                    sample.get("sample_rows") == 126
                    and sample.get("machine_accept_rows") == 90
                    and sample.get("false_accept_rows") == 66
                    and metrics.get("false_accept_rate") == 0.73
                    and metrics.get("wilson_95_ci") == [0.63, 0.81],
                    "independent_validation differs from the submitted audit summary",
                    failures,
                )
            elif endpoint == "/api/citation" and isinstance(payload, dict):
                archived = payload.get("archived_snapshot", {})
                web_release = payload.get("web_release", {})
                check(
                    archived.get("version") == "v1.0.1"
                    and archived.get("doi") == "10.5281/zenodo.20633779",
                    "citation endpoint does not identify the manuscript-cited snapshot",
                    failures,
                )
                check(
                    web_release.get("version") == "1.0.2",
                    "citation endpoint does not identify the current web release",
                    failures,
                )
        except Exception as exc:
            endpoint_status[endpoint] = f"FAIL: {exc}"
            failures.append(f"{endpoint} failed: {exc}")

    for endpoint, expected_rows in [
        ("/api/evidence_records?limit=1000", 737),
        ("/api/sources?limit=1000", 660),
        ("/api/molecules?limit=1000", 524),
        ("/api/audit?limit=1000", 737),
        ("/api/benchmark_baseline_results", 16),
        ("/api/benchmark_tasks", 2),
    ]:
        payload = endpoint_payloads.get(endpoint)
        check(
            isinstance(payload, list) and len(payload) == expected_rows,
            f"{endpoint} must expose exactly {expected_rows} release rows",
            failures,
        )

    evidence_records = endpoint_payloads.get("/api/evidence_records?limit=1000")
    if isinstance(evidence_records, list):
        domain_counts = {
            domain: sum(
                1
                for row in evidence_records
                if isinstance(row, dict) and row.get("evidence_domain") == domain
            )
            for domain in ("toxicity", "offtarget")
        }
        check(
            domain_counts == {"toxicity": 626, "offtarget": 111},
            "evidence API must expose 626 toxicity and 111 off-target rows",
            failures,
        )

    benchmark = endpoint_payloads.get("/api/benchmark")
    check(
        isinstance(benchmark, dict) and benchmark.get("benchmark_eligible_records") == 344,
        "benchmark endpoint must report exactly 344 eligible release rows",
        failures,
    )

    for path in PROHIBITED_PUBLIC_PATHS:
        try:
            with urlopen(f"{base_url}{path}", timeout=5) as response:
                endpoint_status[path] = str(response.status)
                failures.append(f"withheld public path returned {response.status}: {path}")
        except HTTPError as error:
            endpoint_status[path] = str(error.code)
            check(error.code == 404, f"{path} returned {error.code}; expected 404", failures)
        except (URLError, OSError) as error:
            endpoint_status[path] = f"FAIL: {error}"
            failures.append(f"{path} failed during absence check: {error}")

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

    for path, expected_rows in EXPECTED_REMOTE_CSV_ROWS.items():
        try:
            with urlopen(f"{base_url}{path}", timeout=10) as response:
                text = response.read().decode("utf-8-sig")
            rows = sum(1 for _ in csv.DictReader(io.StringIO(text)))
            check(
                rows == expected_rows, f"{path} has {rows} rows; expected {expected_rows}", failures
            )
        except (URLError, OSError, UnicodeDecodeError, csv.Error) as error:
            failures.append(f"{path} row-count check failed: {error}")

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
        "RELEASE_MANIFEST.json": (
            RELEASE_MANIFEST_PATH.stat().st_size if RELEASE_MANIFEST_PATH.exists() else 0
        ),
        "CHECKSUMS_SHA256.txt": CHECKSUM_PATH.stat().st_size if CHECKSUM_PATH.exists() else 0,
    }
    for name, size in artifacts.items():
        check(size > 0, f"missing or empty release artifact: {name}", failures)
    if RELEASE_MANIFEST_PATH.exists():
        manifest = json.loads(RELEASE_MANIFEST_PATH.read_text(encoding="utf-8"))
        check(
            manifest.get("file_count", 0) > 20, "release manifest file_count is too small", failures
        )
        artifacts["file_count"] = manifest.get("file_count", 0)
    return artifacts


def write_report(
    base_url: str,
    db: dict[str, object],
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
        status = "TECHNICAL_QA_PASS__PUBLIC_URL_REQUIRED"
    else:
        status = "TECHNICAL_QA_PASS__PUBLIC_RELEASE_READY"
    if quick_tunnel:
        public_url_gate = "BLOCKED_TEMPORARY_QUICK_TUNNEL"
    elif local_url:
        public_url_gate = "BLOCKED_LOCALHOST_URL"
    else:
        public_url_gate = "READY_FOR_PUBLIC_URL_QA"
    release_gate = (
        "BLOCKED_ZERO_VERIFIED_RELEASE_EVIDENCE"
        if zero_verified_release
        else (
            "READY_HUMAN_VERIFIED_RELEASE_REVIEW"
            if release_scale_ready
            else "BLOCKED_BELOW_600_HUMAN_VERIFIED_RELEASE_EVIDENCE"
        )
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "# Final QA Report",
        "",
        f"Generated at: {now}",
        f"Base URL: `{base_url}`",
        f"Status: **{status}**",
        f"Public deployment URL gate: **{public_url_gate}**",
        f"Verified release evidence gate: **{release_gate}**",
        f"Verified release evidence total: **{release_count}**",
        "",
        "## Database Counts",
        "",
    ]
    for key, value in db["counts"].items():
        lines.append(f"- `{key}`: {value}")
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
            "## Public Deployment Gate",
            "",
            "This QA report validates the local or configured deployment target. Public operation requires a stable HTTPS URL with the same no-login behavior; temporary Quick Tunnel URLs are suitable for demonstration only.",
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
    scanned_public_assets, public_asset_failures = collect_public_asset_failures()
    failures.extend(public_asset_failures)
    http = http_checks(args.base_url.rstrip("/"), failures)
    screenshots = screenshot_checks(failures)
    release_artifacts = release_artifact_checks(failures)
    release_artifacts["public_structured_assets_scanned"] = scanned_public_assets
    write_report(args.base_url.rstrip("/"), db, http, screenshots, release_artifacts, failures)

    if failures:
        print(f"final_delivery_check=fail report={REPORT_PATH}", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        raise SystemExit(1)
    print(f"final_delivery_check=pass report={REPORT_PATH}")


if __name__ == "__main__":
    main()

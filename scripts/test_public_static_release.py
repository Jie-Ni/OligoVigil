from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOT = ROOT / "public"
PUBLIC_API = ROOT / "public" / "api"
REQUIRED_DATA_RELEASE = "1.0.2"
PMCID_PATTERN = re.compile(r"PMC[1-9]\d*")
FORBIDDEN_TEXT_PATTERNS = (
    ("appended manuscript identifier", re.compile(r"manuscript-id\s*:", re.IGNORECASE)),
    ("appended embargo date", re.compile(r"embargo-date\s*:", re.IGNORECASE)),
    (
        "retired independent-curation template",
        re.compile(r"independent[_ -]curation[_ -]validation[_ -]template", re.IGNORECASE),
    ),
    (
        "retired 500-row validation template",
        re.compile(
            r"(?:500[- ]?rows?.{0,80}(?:validation|curation)|"
            r"(?:validation|curation).{0,80}500[- ]?rows?)",
            re.IGNORECASE,
        ),
    ),
    ("internal curator name suffix", re.compile(r"\bcurator\s*:", re.IGNORECASE)),
    (
        "internal recovery name suffix",
        re.compile(r"recovered\s+B2\s+from\s+PMID", re.IGNORECASE),
    ),
    ("internal extraction name suffix", re.compile(r"v1\s+extraction\s+artefact", re.IGNORECASE)),
    (
        "internal re-verification name suffix",
        re.compile(r"pending\s+source\s+re-verification", re.IGNORECASE),
    ),
    (
        "withheld curation work table",
        re.compile(r"\bcuration_(?:candidates?|queue)(?=$|[^a-z0-9])", re.IGNORECASE),
    ),
    (
        "withheld live curation count field",
        re.compile(r"\b(?:candidate_records|queue_tasks)\b", re.IGNORECASE),
    ),
    (
        "retired public endpoint",
        re.compile(
            r"/api/(?:examples|ask|help|use_cases|case_workflows|sequence_coverage|"
            r"sequence_search|safety_triage|safety_dossier|evidence_graph|prov_graph|"
            r"modification_profile|client_examples|submission_schema|openapi\.json|search|"
            r"source_detail|evidence_detail|offtarget_taxonomy|quality|curation_protocol|"
            r"release_status|closest_work|core_oligo_fields|"
            r"field_completeness|novelty_position|adoption_packet|readiness|"
            r"archive_readiness)(?=$|[^a-z0-9_])",
            re.IGNORECASE,
        ),
    ),
    (
        "withheld work-file reference",
        re.compile(
            r"(?:sequence_modification_curation_template|core_oligo_field_curation_packet|"
            r"closest_work_matrix)(?:_v1)?\.csv",
            re.IGNORECASE,
        ),
    ),
    ("internal release batch field", re.compile(r"\brelease_batches\b", re.IGNORECASE)),
    (
        "draft availability field",
        re.compile(r"\bavailability_statement_draft\b", re.IGNORECASE),
    ),
    (
        "withheld source-candidate manifest",
        re.compile(r"\bsource_candidates_v[1-6]\.csv\b", re.IGNORECASE),
    ),
    (
        "withheld discovery-candidate manifest",
        re.compile(r"\bpubmed_discovery_candidates_v[1-4]\.csv\b", re.IGNORECASE),
    ),
    (
        "withheld full-source manifest",
        re.compile(r"\bsource_document_pubmed_v1\.csv\b", re.IGNORECASE),
    ),
    ("withheld assay table", re.compile(r"\bassay\.csv\b", re.IGNORECASE)),
    (
        "retired agent endpoint",
        re.compile(
            r"(?:/api/(?:agent_access|agent_connect|submission_pack)|"
            r"/(?:agent|mcp|nlweb)\.json|/\.well-known/[a-z0-9_.-]+\.json)",
            re.IGNORECASE,
        ),
    ),
    (
        "retired agent artifact",
        re.compile(r"(?:oligovigil_agent_pack\.zip|llms(?:-full)?\.txt)", re.IGNORECASE),
    ),
)
EXPECTED_RELEASE_CSV_ROWS = {
    "source_document.csv": 660,
    "molecule.csv": 524,
    "toxicity_endpoint.csv": 626,
    "offtarget_evidence.csv": 111,
    "evidence_release.csv": 737,
    "curation_audit.csv": 737,
    "benchmark_split.csv": 344,
    "benchmark_reference_splits.csv": 344,
}
EXPECTED_RELEASE_MANIFEST_ROWS = {
    "source_license_manifest_v1.csv": 660,
    "benchmark_task_cards_v1.csv": 2,
}
PROHIBITED_PUBLIC_PATHS = (
    "api/examples",
    "api/ask",
    "api/help",
    "api/use_cases",
    "api/case_workflows",
    "api/sequence_coverage",
    "api/sequence_search",
    "api/safety_triage",
    "api/safety_dossier",
    "api/evidence_graph",
    "api/prov_graph",
    "api/modification_profile",
    "api/client_examples",
    "api/submission_schema",
    "api/openapi.json",
    "api/search",
    "api/source_detail",
    "api/evidence_detail",
    "api/offtarget_taxonomy",
    "api/quality",
    "api/curation_protocol",
    "api/release_status",
    "api/closest_work",
    "api/core_oligo_fields",
    "api/field_completeness",
    "api/novelty_position",
    "api/adoption_packet",
    "api/readiness",
    "api/archive_readiness",
    "api/agent_access",
    "api/agent_connect",
    "api/submission_pack",
    "api/curation_queue",
    "api/curation_candidates",
    "api/download/sequence_modification_curation_template.csv",
    "api/download/core_oligo_field_curation_packet.csv",
    "api/download/independent_curation_validation_template.csv",
    "api/download/curation_queue.csv",
    "api/download/curation_candidate.csv",
    "api/download/curation_candidates_filtered.csv",
    "api/download/assay.csv",
    "api/download/oligovigil_agent_pack.zip",
    "api/manifest/sequence_modification_curation_template_v1.csv",
    "api/manifest/core_oligo_field_curation_packet_v1.csv",
    "api/manifest/independent_curation_validation_template_v1.csv",
    "api/manifest/closest_work_matrix_v1.csv",
    "api/manifest/curation_queue_v1.csv",
    "api/manifest/curation_candidate_v1.csv",
    "api/manifest/source_candidates_v1.csv",
    "api/manifest/source_candidates_v2.csv",
    "api/manifest/source_candidates_v3.csv",
    "api/manifest/source_candidates_v4.csv",
    "api/manifest/source_candidates_v5.csv",
    "api/manifest/source_candidates_v6.csv",
    "api/manifest/pubmed_discovery_candidates_v1.csv",
    "api/manifest/pubmed_discovery_candidates_v2.csv",
    "api/manifest/pubmed_discovery_candidates_v3.csv",
    "api/manifest/pubmed_discovery_candidates_v4.csv",
    "api/manifest/source_document_pubmed_v1.csv",
    "agent.json",
    ".well-known/ai-plugin.json",
    ".well-known/nlweb.json",
    ".well-known/oligovigil-agent.json",
    "mcp.json",
    "nlweb.json",
    "llms.txt",
    "llms-full.txt",
)
PROHIBITED_BUNDLE_MEMBERS = {
    PurePosixPath(path).name for path in PROHIBITED_PUBLIC_PATHS if path.endswith(".csv")
}
SPEC = importlib.util.spec_from_file_location("oligovigil_server", ROOT / "app" / "server.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load app/server.py")
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


def append_failure(failures: list[str], message: str) -> None:
    if message not in failures:
        failures.append(message)


def scan_forbidden_text(text: str, label: str, failures: list[str]) -> None:
    for description, pattern in FORBIDDEN_TEXT_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        append_failure(failures, f"{description} found in {label}:{line_number}")


def collect_json_pmcid_errors(
    payload: object,
    path: str = "$",
    errors: list[tuple[str, object]] | None = None,
) -> list[tuple[str, object]]:
    if errors is None:
        errors = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            key_lower = key_text.lower()
            if "pmcid" in key_lower and key_lower not in {
                "with_pmcid",
                "without_pmcid",
                "pmcid_count",
                "source_pmcid_count",
            }:
                values = value if isinstance(value, list) else [value]
                for index, candidate in enumerate(values):
                    candidate_path = (
                        f"{child_path}[{index}]" if isinstance(value, list) else child_path
                    )
                    if candidate in (None, ""):
                        continue
                    if not isinstance(candidate, str) or PMCID_PATTERN.fullmatch(candidate) is None:
                        errors.append((candidate_path, candidate))
            collect_json_pmcid_errors(value, child_path, errors)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            collect_json_pmcid_errors(value, f"{path}[{index}]", errors)
    return errors


def scan_json(
    payload: object,
    label: str,
    failures: list[str],
    source_text: str | None = None,
) -> None:
    if source_text is not None:
        scan_forbidden_text(source_text, label, failures)
    if SERVER.public_payload_has_exposed_free_text(payload):
        append_failure(failures, f"withheld free text found in {label}")
    pmcid_errors = collect_json_pmcid_errors(payload)
    if pmcid_errors:
        examples = ", ".join(f"{path}={value!r}" for path, value in pmcid_errors[:3])
        append_failure(
            failures,
            f"invalid PMCID format in {label}: {len(pmcid_errors)} value(s); {examples}",
        )


def scan_csv(body: bytes, label: str, failures: list[str]) -> None:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        append_failure(failures, f"CSV is not UTF-8: {label}")
        return
    scan_forbidden_text(text, label, failures)
    reader = csv.DictReader(io.StringIO(text))
    pmcid_columns = [
        column for column in (reader.fieldnames or []) if column and "pmcid" in column.lower()
    ]
    pmcid_errors: list[tuple[int, str, str]] = []
    free_text_found = False
    for line_number, record in enumerate(reader, 2):
        if not free_text_found and SERVER.public_payload_has_exposed_free_text(record):
            append_failure(failures, f"withheld free text found in {label}:{line_number}")
            free_text_found = True
        for column in pmcid_columns:
            value = record.get(column)
            if value in (None, ""):
                continue
            if PMCID_PATTERN.fullmatch(value) is None:
                pmcid_errors.append((line_number, column, value))
    if pmcid_errors:
        examples = ", ".join(
            f"line {line}:{column}={value!r}" for line, column, value in pmcid_errors[:3]
        )
        append_failure(
            failures,
            f"invalid PMCID format in {label}: {len(pmcid_errors)} value(s); {examples}",
        )


def csv_row_count(body: bytes, label: str, failures: list[str]) -> int | None:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        append_failure(failures, f"CSV is not UTF-8: {label}")
        return None
    try:
        return sum(1 for _ in csv.DictReader(io.StringIO(text)))
    except csv.Error as error:
        append_failure(failures, f"CSV is invalid in {label}: {error}")
        return None


def scan_zip(body: bytes, label: str, failures: list[str]) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                filename = info.filename
                member = archive.read(filename)
                member_label = f"{label}!{filename}"
                scan_forbidden_text(filename, f"{member_label} member name", failures)
                suffix = PurePosixPath(filename).suffix.lower()
                if suffix == ".csv":
                    scan_csv(member, member_label, failures)
                elif suffix == ".json":
                    try:
                        text = member.decode("utf-8-sig")
                        scan_json(json.loads(text), member_label, failures, text)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        append_failure(failures, f"JSON is invalid: {member_label}")
                elif suffix == ".zip":
                    scan_zip(member, member_label, failures)
                else:
                    try:
                        scan_forbidden_text(member.decode("utf-8-sig"), member_label, failures)
                    except UnicodeDecodeError:
                        pass
    except zipfile.BadZipFile:
        append_failure(failures, f"ZIP is invalid: {label}")


def manifest_entry(manifest: dict[str, object], filename: str) -> dict[str, object] | None:
    files = manifest.get("files")
    if not isinstance(files, list):
        return None
    for entry in files:
        if isinstance(entry, dict) and entry.get("filename") == filename:
            return entry
    return None


def check_manifest_artifacts(manifest: dict[str, object], failures: list[str]) -> None:
    files = manifest.get("files")
    if not isinstance(files, list):
        append_failure(failures, "download_manifest files field is not a list")
        return

    seen_filenames: set[str] = set()
    for index, entry in enumerate(files):
        if not isinstance(entry, dict):
            append_failure(failures, f"download_manifest files[{index}] is not an object")
            continue
        filename = entry.get("filename")
        url = entry.get("url")
        if not isinstance(filename, str) or not filename:
            append_failure(failures, f"download_manifest files[{index}] has no filename")
            continue
        if filename in seen_filenames:
            append_failure(failures, f"download_manifest repeats filename: {filename}")
        seen_filenames.add(filename)
        if not isinstance(url, str) or not url.startswith("/api/"):
            append_failure(failures, f"download_manifest {filename} has an invalid public URL")
            continue

        artifact_path = PUBLIC_ROOT / url.lstrip("/")
        if not artifact_path.is_file():
            append_failure(failures, f"download_manifest URL is missing: {url}")
            continue
        body = artifact_path.read_bytes()
        if entry.get("bytes") != len(body):
            append_failure(failures, f"download_manifest byte count differs for {filename}")
        expected_sha256 = str(entry.get("sha256") or "").lower()
        if expected_sha256 != hashlib.sha256(body).hexdigest():
            append_failure(failures, f"download_manifest SHA256 differs for {filename}")

        expected_rows = entry.get("rows")
        if isinstance(expected_rows, int) and artifact_path.suffix.lower() == ".csv":
            rows = csv_row_count(body, url, failures)
            if rows is not None and rows != expected_rows:
                append_failure(
                    failures,
                    f"download_manifest rows differ for {filename}: {rows} != {expected_rows}",
                )

        schema = entry.get("schema")
        if isinstance(schema, str) and schema and schema != "RELEASE_MANIFEST.json":
            schema_paths = (
                PUBLIC_API / "manifest" / schema,
                PUBLIC_API / "download" / schema,
            )
            if not any(path.is_file() for path in schema_paths):
                append_failure(
                    failures,
                    f"download_manifest schema reference is missing: {schema}",
                )


def check_release_csv_rows(failures: list[str]) -> None:
    download_dir = PUBLIC_API / "download"
    for filename, expected_rows in EXPECTED_RELEASE_CSV_ROWS.items():
        path = download_dir / filename
        label = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            append_failure(failures, f"required release CSV is missing: {label}")
            continue
        rows = csv_row_count(path.read_bytes(), label, failures)
        if rows is not None and rows != expected_rows:
            append_failure(
                failures,
                f"{label} has {rows} data rows; expected {expected_rows}",
            )
    manifest_dir = PUBLIC_API / "manifest"
    for filename, expected_rows in EXPECTED_RELEASE_MANIFEST_ROWS.items():
        path = manifest_dir / filename
        label = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            append_failure(failures, f"required release manifest is missing: {label}")
            continue
        rows = csv_row_count(path.read_bytes(), label, failures)
        if rows is not None and rows != expected_rows:
            append_failure(
                failures,
                f"{label} has {rows} data rows; expected {expected_rows}",
            )


def check_all_tables_bundle(bundle: bytes, label: str, failures: list[str]) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            members = {
                PurePosixPath(info.filename).name: info.filename
                for info in archive.infolist()
                if not info.is_dir()
            }
            for filename in sorted(PROHIBITED_BUNDLE_MEMBERS & members.keys()):
                append_failure(failures, f"withheld work file found in {label}: {filename}")
            for filename, expected_rows in EXPECTED_RELEASE_CSV_ROWS.items():
                member_name = members.get(filename)
                if member_name is None:
                    append_failure(
                        failures, f"required release table missing from {label}: {filename}"
                    )
                    continue
                rows = csv_row_count(archive.read(member_name), f"{label}!{member_name}", failures)
                if rows is not None and rows != expected_rows:
                    append_failure(
                        failures,
                        f"{label}!{member_name} has {rows} data rows; expected {expected_rows}",
                    )
            for filename, expected_rows in EXPECTED_RELEASE_MANIFEST_ROWS.items():
                member_name = members.get(filename)
                if member_name is None:
                    append_failure(
                        failures, f"required release manifest missing from {label}: {filename}"
                    )
                    continue
                rows = csv_row_count(archive.read(member_name), f"{label}!{member_name}", failures)
                if rows is not None and rows != expected_rows:
                    append_failure(
                        failures,
                        f"{label}!{member_name} has {rows} data rows; expected {expected_rows}",
                    )
    except zipfile.BadZipFile:
        append_failure(failures, f"ZIP is invalid: {label}")


def check_static_stats(failures: list[str]) -> None:
    stats_path = PUBLIC_API / "stats"
    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        append_failure(failures, f"cannot read public stats: {error}")
        return
    counts = stats.get("counts") if isinstance(stats, dict) else None
    if not isinstance(counts, dict):
        append_failure(failures, "public stats has no counts object")
        return
    expected_counts = {
        "source_document": 660,
        "molecule": 524,
        "curation_audit": 737,
        "benchmark_split": 344,
    }
    for key, expected in expected_counts.items():
        if counts.get(key) != expected:
            append_failure(
                failures,
                f"public stats count {key}={counts.get(key)!r}; expected {expected}",
            )
    release_count = int(counts.get("toxicity_endpoint") or 0) + int(
        counts.get("offtarget_evidence") or 0
    )
    if release_count != 737:
        append_failure(failures, f"public stats release evidence={release_count}; expected 737")
    for key in ("curation_candidate", "curation_queue"):
        if key in counts:
            append_failure(failures, f"withheld public stats count is present: {key}")


def collect_public_asset_failures() -> tuple[int, list[str]]:
    failures: list[str] = []
    manifest_path = PUBLIC_API / "download_manifest"
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        append_failure(failures, f"cannot read public release manifest: {error}")
        manifest: dict[str, object] = {}
    else:
        if isinstance(manifest_payload, dict):
            manifest = manifest_payload
        else:
            append_failure(failures, "public release manifest is not a JSON object")
            manifest = {}
    if manifest.get("data_release_version") != REQUIRED_DATA_RELEASE:
        append_failure(
            failures,
            "download_manifest data_release_version must be " f"{REQUIRED_DATA_RELEASE}",
        )
    for relative in PROHIBITED_PUBLIC_PATHS:
        if (PUBLIC_ROOT / relative).exists():
            append_failure(failures, f"withheld public asset is present: public/{relative}")
    check_manifest_artifacts(manifest, failures)
    bundle_path = PUBLIC_API / "download" / "all_tables.zip"
    bundle_entry = manifest_entry(manifest, "all_tables.zip")
    if bundle_entry is None:
        append_failure(failures, "download_manifest has no all_tables.zip entry")
    elif not bundle_path.exists():
        append_failure(failures, "public all_tables.zip is missing")
    else:
        bundle = bundle_path.read_bytes()
        if bundle_entry.get("bytes") != len(bundle):
            append_failure(failures, "public all_tables.zip byte count differs from manifest")
        if str(bundle_entry.get("sha256") or "").lower() != hashlib.sha256(bundle).hexdigest():
            append_failure(failures, "public all_tables.zip SHA256 differs from manifest")
        check_all_tables_bundle(bundle, bundle_path.relative_to(ROOT).as_posix(), failures)

    check_release_csv_rows(failures)
    check_static_stats(failures)

    scanned = 0
    for path in sorted(item for item in PUBLIC_ROOT.rglob("*") if item.is_file()):
        relative = path.relative_to(ROOT).as_posix()
        body = path.read_bytes()
        suffix = path.suffix.lower()
        scan_forbidden_text(path.name, f"{relative} filename", failures)
        if suffix == ".csv":
            scan_csv(body, relative, failures)
            scanned += 1
        elif suffix == ".zip":
            scan_zip(body, relative, failures)
            scanned += 1
        elif suffix == ".json" or suffix == "":
            try:
                text = body.decode("utf-8-sig")
                payload = json.loads(text)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                if suffix == ".json" or path.is_relative_to(PUBLIC_API):
                    append_failure(failures, f"JSON is invalid: {relative}: {error}")
                continue
            scan_json(payload, relative, failures, text)
            scanned += 1
    return scanned, failures


def main() -> int:
    scanned, failures = collect_public_asset_failures()

    if failures:
        for failure in sorted(failures):
            print(f"FAIL: {failure}")
        return 1
    print(f"PASS: scanned {scanned} public API JSON/CSV/ZIP assets")
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "app" / "static"
MANIFEST_DIR = ROOT / "data" / "manifests"


JSON_ENDPOINTS = [
    "/api/health",
    "/api/stats",
    "/api/metadata",
    "/api/summary",
    "/api/facets",
    "/api/quality",
    "/api/coverage",
    "/api/examples",
    "/api/help",
    "/api/curation_protocol",
    "/api/data_availability",
    "/api/release_status",
    "/api/submission_pack",
    "/api/field_completeness",
    "/api/core_oligo_fields",
    "/api/independent_validation",
    "/api/novelty_position",
    "/api/archive_readiness",
    "/api/adoption_packet",
    "/api/agent_access",
    "/api/agent_connect",
    "/api/citation",
    "/api/use_cases",
    "/api/case_workflows",
    "/api/sequence_coverage",
    "/api/offtarget_taxonomy",
    "/api/client_examples",
    "/api/submission_schema",
    "/api/openapi.json",
    "/api/download_manifest",
    "/api/downloads",
    "/api/readiness",
    "/api/closest_work",
    "/api/data_dictionary",
    "/api/evidence",
    "/api/benchmark",
    "/api/benchmark_baseline_results",
    "/api/benchmark_tasks",
    "/agent.json",
    "/.well-known/oligovigil-agent.json",
    "/.well-known/ai-plugin.json",
    "/mcp.json",
    "/nlweb.json",
    "/.well-known/nlweb.json",
    "/bioschemas.json",
]


QUERY_ENDPOINTS = [
    ("/api/search?q=hepatotoxicity&limit=50", "/api/search"),
    ("/api/ask?q=Show%20GalNAc%20liver%20toxicity%20Grade%20A%2FB%20evidence&limit=25", "/api/ask"),
    ("/api/sources?limit=500", "/api/sources"),
    ("/api/source_detail?q=hepatotoxicity", "/api/source_detail"),
    ("/api/molecules?limit=500", "/api/molecules"),
    ("/api/evidence_records?limit=500", "/api/evidence_records"),
    ("/api/evidence_detail?domain=toxicity&id=1", "/api/evidence_detail"),
    ("/api/audit?entity_table=toxicity_endpoint&limit=500", "/api/audit"),
    ("/api/curation_queue?limit=500", "/api/curation_queue"),
    ("/api/curation_candidates?limit=500", "/api/curation_candidates"),
    (
        "/api/sequence_search?sequence=AUGCUACUGACUGA&modification=GalNAc&target=PCSK9",
        "/api/sequence_search",
    ),
    (
        "/api/safety_triage?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human",
        "/api/safety_triage",
    ),
    (
        "/api/safety_dossier?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human",
        "/api/safety_dossier",
    ),
    (
        "/api/evidence_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&endpoint=hepatic",
        "/api/evidence_graph",
    ),
    (
        "/api/prov_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&endpoint=hepatic",
        "/api/prov_graph",
    ),
    ("/api/modification_profile?term=galnac", "/api/modification_profile"),
]


DOWNLOAD_ENDPOINTS = [
    "/api/download/evidence_release.csv",
    "/api/download/benchmark_reference_splits.csv",
    "/api/download/benchmark_baseline_results.csv",
    "/api/download/benchmark_task_cards.csv",
    "/api/download/sequence_modification_curation_template.csv",
    "/api/download/core_oligo_field_curation_packet.csv",
    "/api/download/independent_curation_validation_template.csv",
    "/api/download/curation_candidates_filtered.csv",
    "/api/download/all_tables.zip",
    "/api/download/oligovigil_agent_pack.zip",
    "/api/download/source_document.csv",
    "/api/download/molecule.csv",
    "/api/download/toxicity_endpoint.csv",
    "/api/download/offtarget_evidence.csv",
    "/api/download/curation_audit.csv",
    "/api/download/benchmark_split.csv",
    "/api/download/curation_queue.csv",
    "/api/download/curation_candidate.csv",
]


TEXT_ENDPOINTS = [
    "/llms.txt",
    "/llms-full.txt",
]


HEADERS = """/*
  X-Robots-Tag: all
  Cache-Control: public, max-age=300

/api/*
  Content-Type: application/json; charset=utf-8
  Cache-Control: public, max-age=300

/api/download/*.csv
  Content-Type: text/csv; charset=utf-8
  Content-Disposition: attachment

/api/manifest/*.csv
  Content-Type: text/csv; charset=utf-8
  Content-Disposition: attachment

/api/download/*.zip
  Content-Type: application/zip
  Content-Disposition: attachment

/bioschemas.json
  Content-Type: application/ld+json; charset=utf-8

/llms.txt
  Content-Type: text/plain; charset=utf-8

/llms-full.txt
  Content-Type: text/plain; charset=utf-8
"""


REDIRECTS = """/downloads /#downloads 302
/* /index.html 200
"""


def ensure_safe_output(path: Path) -> Path:
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError(f"Refusing to write outside project root: {resolved}")
    return resolved


def fetch(base_url: str, endpoint: str, public_base_url: str) -> bytes:
    url = f"{base_url.rstrip('/')}{endpoint}"
    public = urlsplit(public_base_url)
    request = Request(
        url,
        headers={
            "User-Agent": "OligoVigil-static-export/1.0",
            "X-Forwarded-Proto": public.scheme or "https",
            "X-Forwarded-Host": public.netloc,
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise RuntimeError(f"{endpoint} returned HTTP {status}")
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"{endpoint} returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not fetch {endpoint}: {exc.reason}") from exc


def destination_for(endpoint: str, output_dir: Path, override: str | None = None) -> Path:
    path = override or urlsplit(endpoint).path
    if path == "/":
        path = "/index.html"
    return output_dir / path.lstrip("/")


def write_endpoint(
    base_url: str,
    public_base_url: str,
    output_dir: Path,
    endpoint: str,
    override: str | None = None,
) -> Path:
    body = fetch(base_url, endpoint, public_base_url)
    dest = destination_for(endpoint, output_dir, override)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return dest


def export_manifest_files(base_url: str, public_base_url: str, output_dir: Path) -> list[Path]:
    written = []
    for path in sorted(MANIFEST_DIR.glob("*.csv")):
        endpoint = f"/api/manifest/{path.name}"
        written.append(write_endpoint(base_url, public_base_url, output_dir, endpoint))
    return written


def json_file_is_valid(path: Path) -> bool:
    if path.suffix not in {".json", ""}:
        return True
    if "/api/download/" in path.as_posix():
        return True
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OligoVigil for Cloudflare Pages.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8077")
    parser.add_argument("--public-base-url", default="https://oligovigil.pages.dev")
    parser.add_argument("--output", default=str(ROOT / "public"))
    args = parser.parse_args()

    output_dir = ensure_safe_output(Path(args.output))
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(STATIC_DIR, output_dir)

    written: list[Path] = []
    for endpoint in JSON_ENDPOINTS + TEXT_ENDPOINTS + DOWNLOAD_ENDPOINTS:
        written.append(write_endpoint(args.base_url, args.public_base_url, output_dir, endpoint))
    for endpoint, override in QUERY_ENDPOINTS:
        written.append(
            write_endpoint(args.base_url, args.public_base_url, output_dir, endpoint, override=override)
        )
    written.extend(export_manifest_files(args.base_url, args.public_base_url, output_dir))

    (output_dir / "_headers").write_text(HEADERS, encoding="utf-8")
    (output_dir / "_redirects").write_text(REDIRECTS, encoding="utf-8")
    (output_dir / "STATIC_EXPORT_README.txt").write_text(
        "\n".join(
            [
                "OligoVigil Cloudflare Pages static export",
                f"generated_at_utc={datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
                f"source_base_url={args.base_url.rstrip('/')}",
                f"public_base_url={args.public_base_url.rstrip('/')}",
                "deployment_command=npx wrangler pages deploy public --project-name oligovigil",
                "",
            ]
        ),
        encoding="utf-8",
    )

    bad_json = [path for path in written if not json_file_is_valid(path)]
    if bad_json:
        for path in bad_json:
            print(f"Invalid JSON export: {path}", file=sys.stderr)
        return 2

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_base_url": args.base_url.rstrip("/"),
        "public_base_url": args.public_base_url.rstrip("/"),
        "output": str(output_dir),
        "files_written": len({path.resolve() for path in written}),
        "recommended_project_name": "oligovigil",
        "recommended_pages_url": "https://oligovigil.pages.dev",
    }
    (output_dir / "cloudflare-deployment.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

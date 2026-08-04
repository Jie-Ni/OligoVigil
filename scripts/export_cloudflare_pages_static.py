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
    "/api/coverage",
    "/api/data_availability",
    "/api/independent_validation",
    "/api/citation",
    "/api/download_manifest",
    "/api/downloads",
    "/api/data_dictionary",
    "/api/evidence",
    "/api/benchmark",
    "/api/benchmark_baseline_results",
    "/api/benchmark_tasks",
    "/bioschemas.json",
]


QUERY_ENDPOINTS = [
    ("/api/sources?limit=1000", "/api/sources"),
    ("/api/molecules?limit=1000", "/api/molecules"),
    ("/api/evidence_records?limit=1000", "/api/evidence_records"),
    ("/api/audit?limit=1000", "/api/audit"),
]


DOWNLOAD_ENDPOINTS = [
    "/api/download/evidence_release.csv",
    "/api/download/benchmark_reference_splits.csv",
    "/api/download/benchmark_baseline_results.csv",
    "/api/download/benchmark_task_cards.csv",
    "/api/download/benchmark_readme.md",
    "/api/download/all_tables.zip",
    "/api/download/source_document.csv",
    "/api/download/molecule.csv",
    "/api/download/toxicity_endpoint.csv",
    "/api/download/offtarget_evidence.csv",
    "/api/download/curation_audit.csv",
    "/api/download/benchmark_split.csv",
    "/api/manifest/benchmark_task_cards_v1.csv",
]


TEXT_ENDPOINTS: list[str] = []


PUBLIC_MANIFEST_FILES = {
    "benchmark_task_cards_v1.csv",
    "data_dictionary_v1.csv",
    "license_manifest_v1.csv",
    "source_license_manifest_v1.csv",
}


HEADERS = """/*
  X-Robots-Tag: all

/api/*
  Content-Type: application/json; charset=utf-8

/api/download/*.csv
  Content-Type: text/csv; charset=utf-8
  Content-Disposition: attachment

/api/manifest/*.csv
  Content-Type: text/csv; charset=utf-8
  Content-Disposition: attachment

/api/download/*.zip
  Content-Type: application/zip
  Content-Disposition: attachment

/api/download/*.md
  Content-Type: text/markdown; charset=utf-8

/bioschemas.json
  Content-Type: application/ld+json; charset=utf-8
"""


REDIRECTS = "/downloads /#downloads 302\n"


ROUTES = """{
  "version": 1,
  "include": [
    "/api/*"
  ],
  "exclude": []
}
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
        if path.name not in PUBLIC_MANIFEST_FILES:
            continue
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
    generated_assets = output_dir / "assets" / "generated"
    if generated_assets.exists():
        shutil.rmtree(generated_assets)

    written: list[Path] = []
    for endpoint in JSON_ENDPOINTS + TEXT_ENDPOINTS + DOWNLOAD_ENDPOINTS:
        written.append(write_endpoint(args.base_url, args.public_base_url, output_dir, endpoint))
    for endpoint, override in QUERY_ENDPOINTS:
        written.append(
            write_endpoint(
                args.base_url, args.public_base_url, output_dir, endpoint, override=override
            )
        )
    written.extend(export_manifest_files(args.base_url, args.public_base_url, output_dir))

    (output_dir / "_headers").write_text(HEADERS, encoding="utf-8")
    (output_dir / "_redirects").write_text(REDIRECTS, encoding="utf-8")
    (output_dir / "_routes.json").write_text(ROUTES, encoding="utf-8")
    (output_dir / "STATIC_EXPORT_README.txt").write_text(
        "\n".join(
            [
                "OligoVigil Cloudflare Pages static export",
                f"generated_at_utc={datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
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
        "public_base_url": args.public_base_url.rstrip("/"),
        "output": "public",
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

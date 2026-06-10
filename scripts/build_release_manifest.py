from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DELIVERY_DIR = PROJECT_ROOT / "04_delivery"
MANIFEST_PATH = DELIVERY_DIR / "RELEASE_MANIFEST.json"
CHECKSUM_PATH = DELIVERY_DIR / "CHECKSUMS_SHA256.txt"

INCLUDED_PATTERNS = [
    "repo_ready/data/seed/*.csv",
    "repo_ready/data/generated/*.csv",
    "repo_ready/data/generated/curation_protocol_v1.json",
    "repo_ready/data/manifests/*.csv",
    "repo_ready/data/schema_sqlite.sql",
    "repo_ready/app/server.py",
    "repo_ready/app/static/*",
    "repo_ready/app/static/assets/generated/*.png",
    "repo_ready/agent_ready/**/*",
    "repo_ready/scripts/*.py",
    "repo_ready/README.md",
    "repo_ready/Dockerfile",
    "repo_ready/docker-compose.yml",
    "00_scoping/*.md",
    "01_sources/*.md",
    "02_design/*.md",
    "02_design/*.sql",
    "03_ingestion_status.md",
    "04_delivery/*.md",
    "04_delivery/*.txt",
    "04_delivery/brand_assets/*.md",
    "04_delivery/brand_assets/raw_ai/*.png",
]
EXCLUDED_NAMES = {
    "FINAL_QA_REPORT.md",
    "RELEASE_MANIFEST.json",
    "CHECKSUMS_SHA256.txt",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def included_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in INCLUDED_PATTERNS:
        files.update(PROJECT_ROOT.glob(pattern))
    return sorted(
        path
        for path in files
        if path.is_file()
        and path.name not in EXCLUDED_NAMES
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )


def main() -> None:
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    files = included_files()
    entries = [
        {
            "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in files
    ]
    manifest = {
        "project": "OligoVigil",
        "release_type": "presubmission_release",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "file_count": len(entries),
        "entries": entries,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    CHECKSUM_PATH.write_text(
        "\n".join(f"{entry['sha256']}  {entry['path']}" for entry in entries) + "\n",
        encoding="utf-8",
    )
    print(f"release_manifest={MANIFEST_PATH}")
    print(f"checksums={CHECKSUM_PATH}")
    print(f"file_count={len(entries)}")


if __name__ == "__main__":
    main()

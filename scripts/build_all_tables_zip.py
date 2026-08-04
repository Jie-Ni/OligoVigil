from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.server import (
    ALL_TABLES_ZIP_PATH,
    PUBLIC_DOWNLOAD_MANIFEST_PATH,
    build_all_tables_zip_bytes,
)


def update_frozen_manifest(payload: bytes) -> None:
    manifest = json.loads(PUBLIC_DOWNLOAD_MANIFEST_PATH.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    for entry in files:
        if entry.get("filename") == "all_tables.zip":
            entry["bytes"] = len(payload)
            entry["sha256"] = hashlib.sha256(payload).hexdigest()
            break
    else:
        raise ValueError("download_manifest has no all_tables.zip entry")
    PUBLIC_DOWNLOAD_MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    payload = build_all_tables_zip_bytes()
    ALL_TABLES_ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALL_TABLES_ZIP_PATH.write_bytes(payload)
    update_frozen_manifest(payload)
    print(f"all_tables_zip={ALL_TABLES_ZIP_PATH}")
    print(f"bytes={len(payload)}")


if __name__ == "__main__":
    main()

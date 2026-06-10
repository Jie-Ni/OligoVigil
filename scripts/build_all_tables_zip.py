from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.server import ALL_TABLES_ZIP_PATH, build_all_tables_zip_bytes


def main() -> None:
    payload = build_all_tables_zip_bytes()
    ALL_TABLES_ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALL_TABLES_ZIP_PATH.write_bytes(payload)
    print(f"all_tables_zip={ALL_TABLES_ZIP_PATH}")
    print(f"bytes={len(payload)}")


if __name__ == "__main__":
    main()

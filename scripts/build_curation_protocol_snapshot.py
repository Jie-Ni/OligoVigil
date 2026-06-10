from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.server import CURATION_PROTOCOL_SNAPSHOT_PATH, build_curation_protocol_payload


def main() -> None:
    payload = build_curation_protocol_payload()
    CURATION_PROTOCOL_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CURATION_PROTOCOL_SNAPSHOT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"curation_protocol_snapshot={CURATION_PROTOCOL_SNAPSHOT_PATH}")
    print(f"bytes={CURATION_PROTOCOL_SNAPSHOT_PATH.stat().st_size}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
PMCID_FIELDS = {"pmcid", "source_pmcid"}
CANONICAL_NAME_FIELDS = {"canonical_name"}
INTERNAL_NAME_SUFFIX = re.compile(
    r"\s*\((?:v1 extraction artefact, pending source re-verification|"
    r"recovered B2 from PMID:\d+, curator:[A-Za-z0-9_-]+)\)\s*$",
    re.IGNORECASE,
)
STATUS_REPLACEMENTS = {
    "needs_curator_sequence_curation": "sequence_not_available",
    "needs_curator_modification_curation": "modification_not_available",
    "candidate_needs_curator_review": "curation_lead",
}


def normalized_pmcid(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    match = re.match(r"\s*(PMC\d+)", stripped, re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid PMCID without a canonical prefix: {value!r}")
    return match.group(1).upper()


def normalized_value(field: str, value: str) -> str:
    if field in PMCID_FIELDS:
        return normalized_pmcid(value)
    if field in CANONICAL_NAME_FIELDS:
        return INTERNAL_NAME_SUFFIX.sub("", value).strip()
    return STATUS_REPLACEMENTS.get(value, value)


def normalize_database(check_only: bool) -> tuple[int, int]:
    connection = sqlite3.connect(DB_PATH)
    pmcid_updates: list[tuple[str, int]] = []
    name_updates: list[tuple[str, int]] = []
    try:
        for row_id, value in connection.execute(
            "SELECT id, pmcid FROM source_document WHERE pmcid IS NOT NULL AND pmcid != ''"
        ):
            normalized = normalized_pmcid(str(value))
            if normalized != value:
                pmcid_updates.append((normalized, int(row_id)))
        for row_id, value in connection.execute(
            "SELECT id, canonical_name FROM molecule WHERE canonical_name IS NOT NULL"
        ):
            normalized = INTERNAL_NAME_SUFFIX.sub("", str(value)).strip()
            if normalized != value:
                name_updates.append((normalized, int(row_id)))

        normalized_ids = [value for value, _ in pmcid_updates]
        existing_ids = [
            str(row[0]).upper()
            for row in connection.execute(
                "SELECT pmcid FROM source_document WHERE pmcid IS NOT NULL AND pmcid != ''"
            )
        ]
        unchanged_ids = [
            value
            for value in existing_ids
            if "MANUSCRIPT-ID:" not in value and "EMBARGO-DATE:" not in value
        ]
        if len(set(normalized_ids + unchanged_ids)) != len(normalized_ids + unchanged_ids):
            raise ValueError("PMCID normalization would create duplicate identifiers")

        if not check_only:
            connection.executemany(
                "UPDATE source_document SET pmcid = ? WHERE id = ?",
                pmcid_updates,
            )
            connection.executemany(
                "UPDATE molecule SET canonical_name = ? WHERE id = ?",
                name_updates,
            )
            connection.commit()
    finally:
        connection.close()
    return len(pmcid_updates), len(name_updates)


def normalize_csv(path: Path, check_only: bool) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    changed = 0
    for row in rows:
        for field in fieldnames:
            value = str(row.get(field) or "")
            normalized = normalized_value(field, value)
            if normalized != value:
                row[field] = normalized
                changed += 1
    if not changed or check_only:
        return changed

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.replace(path)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    database_pmcids, database_names = normalize_database(args.check)
    csv_changes = 0
    changed_files = 0
    for path in sorted((ROOT / "data").rglob("*.csv")):
        changes = normalize_csv(path, args.check)
        if changes:
            changed_files += 1
            csv_changes += changes

    mode = "check" if args.check else "apply"
    print(f"mode={mode}")
    print(f"database_pmcid_changes={database_pmcids}")
    print(f"database_canonical_name_changes={database_names}")
    print(f"csv_files_changed={changed_files}")
    print(f"csv_cells_changed={csv_changes}")


if __name__ == "__main__":
    main()

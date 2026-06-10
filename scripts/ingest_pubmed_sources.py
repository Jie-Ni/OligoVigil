from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
DEFAULT_CANDIDATES = ROOT / "data" / "manifests" / "source_candidates_v3.csv"
DEFAULT_CANDIDATES_V4 = ROOT / "data" / "manifests" / "source_candidates_v4.csv"
DEFAULT_CANDIDATES_V5 = ROOT / "data" / "manifests" / "source_candidates_v5.csv"
FALLBACK_CANDIDATES_V2 = ROOT / "data" / "manifests" / "source_candidates_v2.csv"
FALLBACK_CANDIDATES = ROOT / "data" / "manifests" / "source_candidates_v1.csv"
SEED_SOURCE_CSV = ROOT / "data" / "seed" / "source_document.csv"
GENERATED_DIR = ROOT / "data" / "generated"
GENERATED_CSV = GENERATED_DIR / "source_document_pubmed_v1.csv"
GENERATED_JSON = GENERATED_DIR / "source_document_pubmed_v1.json"
GENERATED_SOURCE_ID_START = 1000


def read_candidates(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_seed_pmids() -> set[str]:
    pmids: set[str] = set()
    if not SEED_SOURCE_CSV.exists():
        return pmids
    with SEED_SOURCE_CSV.open("r", encoding="utf-8", newline="") as handle:
        pmids.update(row["pmid"] for row in csv.DictReader(handle) if row.get("pmid"))
    if DB_PATH.exists():
        import sqlite3

        conn = sqlite3.connect(DB_PATH)
        try:
            pmids.update(
                str(row[0])
                for row in conn.execute("SELECT pmid FROM source_document WHERE pmid IS NOT NULL")
                if row[0]
            )
        finally:
            conn.close()
    return pmids


def ncbi_open(url: str):
    delay = 2.0
    for attempt in range(6):
        try:
            time.sleep(0.35)
            return urlopen(url, timeout=30)
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 5:
                raise
            time.sleep(delay)
            delay *= 1.8
    raise RuntimeError("unreachable NCBI retry state")


def fetch_pubmed_chunk(ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    query = urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{query}"
    with ncbi_open(url) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload["result"]
    return {uid: result[uid] for uid in result["uids"]}


def fetch_pubmed(ids: list[str]) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for start in range(0, len(ids), 150):
        records.update(fetch_pubmed_chunk(ids[start : start + 150]))
    return records


def article_id(record: dict, kind: str) -> str:
    for item in record.get("articleids", []):
        if item.get("idtype") == kind:
            return item.get("value", "")
    return ""


def year_from_pubdate(pubdate: str) -> int | None:
    for token in pubdate.split():
        if token.isdigit() and len(token) == 4:
            return int(token)
    return None


def build_rows(start_id: int, candidates_path: Path) -> list[dict[str, object]]:
    seen_pmids: set[str] = set()
    seed_pmids = read_seed_pmids()
    candidates: list[dict[str, str]] = []
    for row in read_candidates(candidates_path):
        pmid = row.get("pmid")
        if not pmid or pmid in seed_pmids or pmid in seen_pmids:
            continue
        seen_pmids.add(pmid)
        candidates.append(row)
    metadata = fetch_pubmed([row["pmid"] for row in candidates])
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows: list[dict[str, object]] = []

    current_id = start_id
    for candidate in candidates:
        pmid = candidate["pmid"]
        record = metadata.get(pmid)
        if not record:
            continue
        doi = article_id(record, "doi")
        pmcid = article_id(record, "pmcid").replace("pmc-id: ", "").replace(";", "")
        rows.append(
            {
                "id": current_id,
                "source_type": candidate["source_type"],
                "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "pmid": pmid,
                "pmcid": pmcid,
                "doi": doi,
                "title": record.get("title", ""),
                "journal_or_agency": record.get("source", ""),
                "publication_year": year_from_pubdate(record.get("pubdate", "")),
                "license_status": candidate["license_status"],
                "reuse_category": candidate["reuse_category"],
                "accessed_at": now,
            }
        )
        current_id += 1
    return rows


def write_generated(rows: list[dict[str, object]]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if not rows:
        return
    with GENERATED_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_db(rows: list[dict[str, object]]) -> None:
    import sqlite3

    if not rows:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        existing_pmids = {
            row[0] for row in conn.execute("SELECT pmid FROM source_document WHERE pmid IS NOT NULL")
        }
        columns = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_sql = ", ".join(columns)
        inserts = [
            [row[col] for col in columns]
            for row in rows
            if str(row.get("pmid", "")) not in existing_pmids
        ]
        if inserts:
            conn.executemany(
                f"INSERT INTO source_document ({col_sql}) VALUES ({placeholders})",
                inserts,
            )
            conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-db", action="store_true")
    parser.add_argument("--start-id", type=int, default=GENERATED_SOURCE_ID_START)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=(
            DEFAULT_CANDIDATES_V5
            if DEFAULT_CANDIDATES_V5.exists()
            else DEFAULT_CANDIDATES_V4
            if DEFAULT_CANDIDATES_V4.exists()
            else DEFAULT_CANDIDATES
            if DEFAULT_CANDIDATES.exists()
            else FALLBACK_CANDIDATES_V2
            if FALLBACK_CANDIDATES_V2.exists()
            else FALLBACK_CANDIDATES
        ),
    )
    args = parser.parse_args()

    rows = build_rows(args.start_id, args.candidates)
    write_generated(rows)
    if args.load_db:
        load_db(rows)
    print(f"pubmed_sources={len(rows)} generated={GENERATED_CSV}")


if __name__ == "__main__":
    main()

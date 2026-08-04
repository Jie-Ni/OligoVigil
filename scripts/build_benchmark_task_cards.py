from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DB_PATH = ROOT / "data" / "oligosafety.db"
CSV_PATH = ROOT / "data" / "generated" / "benchmark_task_cards_v1.csv"
JSON_PATH = ROOT / "data" / "generated" / "benchmark_task_cards_v1.json"
MD_PATH = PROJECT_ROOT / "04_delivery" / "BENCHMARK_V1_CARD.md"
VERSION = "20260604_resource_depth_v42"


TASKS = {
    "toxicity_safety_v0_1": {
        "prediction_target": "oligonucleotide safety endpoint triage from molecule/modality/provenance fields",
        "label_source": "toxicity_endpoint.endpoint_category and endpoint_name",
        "metrics": "AUROC; AUPRC; macro-F1; PCC/Spearman or MSE only for numeric toxicity values",
        "baseline_models": "train-majority; modality-prior; evidence-grade-prior; target-prior deterministic baselines",
    },
    "offtarget_safety_v0_1": {
        "prediction_target": "observed off-target signal or off-target evidence type",
        "label_source": "offtarget_evidence.evidence_type and is_computational_prediction",
        "metrics": "AUROC; AUPRC; macro-F1; PCC/Spearman for ranked off-target risk",
        "baseline_models": "train-majority; modality-prior; evidence-grade-prior; target-prior deterministic baselines",
    },
}


def split_counts(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for task, split, count in conn.execute("""
        SELECT task_name, split_name, COUNT(*) AS n
        FROM benchmark_split
        GROUP BY task_name, split_name
        ORDER BY task_name, split_name
        """):
        counts.setdefault(str(task), {})[str(split)] = int(count)
    return counts


def grade_counts(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    query = """
        SELECT split.task_name, evidence_grade, COUNT(*) AS n
        FROM benchmark_split AS split
        JOIN toxicity_endpoint AS tox
          ON split.entity_table = 'toxicity_endpoint' AND split.entity_id = tox.id
        GROUP BY split.task_name, evidence_grade
        UNION ALL
        SELECT split.task_name, evidence_grade, COUNT(*) AS n
        FROM benchmark_split AS split
        JOIN offtarget_evidence AS off
          ON split.entity_table = 'offtarget_evidence' AND split.entity_id = off.id
        GROUP BY split.task_name, evidence_grade
        ORDER BY task_name, evidence_grade
    """
    for task, grade, count in conn.execute(query):
        counts.setdefault(str(task), {})[str(grade)] = counts.setdefault(str(task), {}).get(
            str(grade), 0
        ) + int(count)
    return counts


def task_cards(conn: sqlite3.Connection) -> list[dict[str, object]]:
    splits = split_counts(conn)
    grades = grade_counts(conn)
    cards: list[dict[str, object]] = []
    for task_name, config in TASKS.items():
        split_payload = splits.get(task_name, {})
        grade_payload = grades.get(task_name, {})
        cards.append(
            {
                "task_name": task_name,
                "version": VERSION,
                "release_reference": "OligoVigil web release v1.0.2",
                "prediction_target": config["prediction_target"],
                "label_source": config["label_source"],
                "eligibility_rule": "curator_verified accept evidence_grade in A/B",
                "split_strategy": "stored_source_plus_molecule_grouped_splits",
                "train_rows": split_payload.get("train", 0),
                "validation_rows": split_payload.get("validation", 0),
                "test_rows": split_payload.get("test", 0),
                "grade_a_rows": grade_payload.get("A", 0),
                "grade_b_rows": grade_payload.get("B", 0),
                "metrics": config["metrics"],
                "baseline_models": config["baseline_models"],
                "leakage_policy": "stored splits keep records sharing source identifier and molecule/cohort in one split",
                "download_reference_splits": "/api/download/benchmark_reference_splits.csv",
                "download_task_cards": "/api/manifest/benchmark_task_cards_v1.csv",
            }
        )
    return cards


def write_outputs(cards: list[dict[str, object]]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cards[0].keys()))
        writer.writeheader()
        writer.writerows(cards)
    JSON_PATH.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(
        int(card["train_rows"]) + int(card["validation_rows"]) + int(card["test_rows"])
        for card in cards
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "# Benchmark V1 Card",
        "",
        f"Generated at: `{now}`",
        f"Version: `{VERSION}`",
        f"Reference split rows: `{total}`",
        "Release reference: `OligoVigil web release v1.0.2`",
        "",
        "## Reuse Contract",
        "",
        "- Eligible records: curator-verified accepted Grade A/B release evidence only.",
        "- Split strategy: stored source plus molecule/cohort grouped leakage control.",
        "- Required citation: cite OligoVigil version, benchmark task name, and the downloaded reference split file.",
        "- Archived snapshot: OligoVigil v1.0.1, DOI 10.5281/zenodo.20633779.",
        "",
        "## Task Cards",
        "",
    ]
    for card in cards:
        lines.extend(
            [
                f"### {card['task_name']}",
                "",
                f"- target: {card['prediction_target']}",
                f"- labels: {card['label_source']}",
                f"- rows: train={card['train_rows']}, validation={card['validation_rows']}, test={card['test_rows']}",
                f"- grades: A={card['grade_a_rows']}, B={card['grade_b_rows']}",
                f"- metrics: {card['metrics']}",
                f"- baselines: {card['baseline_models']}",
                "",
            ]
        )
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cards = task_cards(conn)
    finally:
        conn.close()
    write_outputs(cards)
    print(f"csv={CSV_PATH}")
    print(f"json={JSON_PATH}")
    print(f"markdown={MD_PATH}")
    print(f"tasks={len(cards)}")


if __name__ == "__main__":
    main()

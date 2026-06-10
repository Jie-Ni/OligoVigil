from __future__ import annotations

import os

import pandas as pd


BASE_URL = os.environ.get("OLIGOVIGIL_BASE_URL", "http://127.0.0.1:8077").rstrip("/")

splits = pd.read_csv(f"{BASE_URL}/api/download/benchmark_reference_splits.csv")
tasks = pd.read_csv(f"{BASE_URL}/api/download/benchmark_task_cards.csv")
baseline = pd.read_csv(f"{BASE_URL}/api/download/benchmark_baseline_results.csv")
evidence = pd.read_csv(f"{BASE_URL}/api/download/evidence_release.csv")

print("tasks")
task_columns = [
    column
    for column in ["task_name", "prediction_target", "metrics", "split_strategy", "eligibility_rule"]
    if column in tasks.columns
]
print(tasks[task_columns].drop_duplicates())

print("split counts")
print(splits.groupby(["task_name", "split_name"]).size())

print("diagnostic baselines")
baseline_columns = [
    column
    for column in ["task_name", "evaluation_split", "baseline_model", "coverage", "accuracy", "macro_f1"]
    if column in baseline.columns
]
print(baseline[baseline_columns])

print("release evidence linked to benchmark")
eligible = evidence[evidence["evidence_grade"].isin(["A", "B"])]
print(eligible[["evidence_domain", "canonical_name", "evidence_grade", "pmid", "source_location"]].head())

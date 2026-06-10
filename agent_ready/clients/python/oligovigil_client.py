from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class OligoVigilClient:
    base_url: str = "http://127.0.0.1:8077"
    timeout: float = 30.0

    def _url(self, path: str, params: dict[str, str | int] | None = None) -> str:
        query = urlencode({key: value for key, value in (params or {}).items() if value not in ("", None)})
        return f"{self.base_url.rstrip('/')}{path}{'?' + query if query else ''}"

    def get_json(self, path: str, params: dict[str, str | int] | None = None) -> Any:
        request = Request(self._url(path, params), headers={"Accept": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_csv_rows(self, path: str, params: dict[str, str | int] | None = None) -> list[dict[str, str]]:
        request = Request(self._url(path, params), headers={"Accept": "text/csv"})
        with urlopen(request, timeout=self.timeout) as response:
            text = response.read().decode("utf-8")
        return list(csv.DictReader(io.StringIO(text)))

    def search(self, query: str, limit: int = 20) -> Any:
        return self.get_json("/api/search", {"q": query, "limit": limit})

    def evidence_records(self, domain: str = "", query: str = "", limit: int = 100) -> Any:
        return self.get_json("/api/evidence_records", {"domain": domain, "q": query, "limit": limit})

    def evidence_detail(self, domain: str, evidence_id: int) -> Any:
        return self.get_json("/api/evidence_detail", {"domain": domain, "id": evidence_id})

    def safety_triage(
        self,
        sequence: str = "",
        helm: str = "",
        target: str = "",
        modification: str = "",
        delivery: str = "",
        endpoint: str = "",
        species: str = "",
    ) -> Any:
        return self.get_json(
            "/api/safety_triage",
            {
                "sequence": sequence,
                "helm": helm,
                "target": target,
                "modification": modification,
                "delivery": delivery,
                "endpoint": endpoint,
                "species": species,
            },
        )

    def safety_dossier(
        self,
        sequence: str = "",
        helm: str = "",
        target: str = "",
        modification: str = "",
        delivery: str = "",
        endpoint: str = "",
        species: str = "",
    ) -> Any:
        return self.get_json(
            "/api/safety_dossier",
            {
                "sequence": sequence,
                "helm": helm,
                "target": target,
                "modification": modification,
                "delivery": delivery,
                "endpoint": endpoint,
                "species": species,
            },
        )

    def evidence_graph(
        self,
        sequence: str = "",
        helm: str = "",
        target: str = "",
        modification: str = "",
        delivery: str = "",
        endpoint: str = "",
        species: str = "",
    ) -> Any:
        return self.get_json(
            "/api/evidence_graph",
            {
                "sequence": sequence,
                "helm": helm,
                "target": target,
                "modification": modification,
                "delivery": delivery,
                "endpoint": endpoint,
                "species": species,
            },
        )

    def benchmark(self) -> Any:
        return self.get_json("/api/benchmark")

    def download_manifest(self) -> Any:
        return self.get_json("/api/download_manifest")

    def offtarget_taxonomy(self) -> Any:
        return self.get_json("/api/offtarget_taxonomy")

    def evidence_release_rows(self) -> list[dict[str, str]]:
        return self.get_csv_rows("/api/download/evidence_release.csv")

    def benchmark_split_rows(self) -> list[dict[str, str]]:
        return self.get_csv_rows("/api/download/benchmark_reference_splits.csv")

    def benchmark_baseline_rows(self) -> list[dict[str, str]]:
        return self.get_csv_rows("/api/download/benchmark_baseline_results.csv")

    def benchmark_task_rows(self) -> list[dict[str, str]]:
        return self.get_csv_rows("/api/download/benchmark_task_cards.csv")

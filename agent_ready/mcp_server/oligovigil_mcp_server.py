from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP


BASE_URL = os.environ.get("OLIGOVIGIL_BASE_URL", "http://127.0.0.1:8077").rstrip("/")
TIMEOUT = float(os.environ.get("OLIGOVIGIL_TIMEOUT", "30"))

mcp = FastMCP("oligovigil")


def get_json(path: str, params: dict[str, str | int] | None = None) -> Any:
    query = urlencode({key: value for key, value in (params or {}).items() if value not in ("", None)})
    url = f"{BASE_URL}{path}{'?' + query if query else ''}"
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


@mcp.tool()
def search_evidence(query: str, domain: str = "", limit: int = 20) -> Any:
    """Search OligoVigil release evidence, sources, molecules, and candidate gaps."""
    if domain:
        return get_json("/api/evidence_records", {"domain": domain, "q": query, "limit": limit})
    return get_json("/api/search", {"q": query, "limit": limit})


@mcp.tool()
def get_evidence_record(domain: str, evidence_id: int) -> Any:
    """Return a citable verified evidence record with provenance and audit trail."""
    return get_json("/api/evidence_detail", {"domain": domain, "id": evidence_id})


@mcp.tool()
def safety_triage(
    sequence: str = "",
    helm: str = "",
    target: str = "",
    modification: str = "",
    delivery: str = "",
    endpoint: str = "",
    species: str = "",
    cell_type: str = "",
) -> Any:
    """Build a source-grounded safety triage packet without de novo safety prediction."""
    return get_json(
        "/api/safety_triage",
        {
            "sequence": sequence,
            "helm": helm,
            "target": target,
            "modification": modification,
            "delivery": delivery,
            "endpoint": endpoint,
            "species": species,
            "cell_type": cell_type,
        },
    )


@mcp.tool()
def safety_dossier(
    sequence: str = "",
    helm: str = "",
    target: str = "",
    modification: str = "",
    delivery: str = "",
    endpoint: str = "",
    species: str = "",
    cell_type: str = "",
) -> Any:
    """Return a reusable Safety Dossier with risk matrix, evidence graph, provenance, and export links."""
    return get_json(
        "/api/safety_dossier",
        {
            "sequence": sequence,
            "helm": helm,
            "target": target,
            "modification": modification,
            "delivery": delivery,
            "endpoint": endpoint,
            "species": species,
            "cell_type": cell_type,
        },
    )


@mcp.tool()
def evidence_graph(
    sequence: str = "",
    helm: str = "",
    target: str = "",
    modification: str = "",
    delivery: str = "",
    endpoint: str = "",
    species: str = "",
    cell_type: str = "",
) -> Any:
    """Return the design-to-evidence graph for a Safety Dossier query."""
    return get_json(
        "/api/evidence_graph",
        {
            "sequence": sequence,
            "helm": helm,
            "target": target,
            "modification": modification,
            "delivery": delivery,
            "endpoint": endpoint,
            "species": species,
            "cell_type": cell_type,
        },
    )


@mcp.tool()
def modification_profile(term: str) -> Any:
    """Summarize release and candidate evidence for a chemistry, modality, or delivery term."""
    return get_json("/api/modification_profile", {"term": term})


@mcp.tool()
def benchmark_metadata() -> Any:
    """Return benchmark tasks, split policy, diagnostic baselines, and download links."""
    return get_json("/api/benchmark")


@mcp.tool()
def download_manifest() -> Any:
    """Return release downloads, checksums, row counts, schemas, and reuse policy."""
    return get_json("/api/download_manifest")


@mcp.resource("oligovigil://llms")
def llms_summary() -> str:
    """Return the concise agent-facing OligoVigil instructions."""
    return urlopen(f"{BASE_URL}/llms.txt", timeout=TIMEOUT).read().decode("utf-8")


if __name__ == "__main__":
    mcp.run()

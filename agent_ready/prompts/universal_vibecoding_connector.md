# Universal OligoVigil Connector Prompt

Use this prompt in an agentic coding tool, API client builder, or notebook assistant.

Connect to OligoVigil at `{BASE_URL}`. First read `{BASE_URL}/agent.json` and `{BASE_URL}/llms.txt`. If your environment supports OpenAPI import, import `{BASE_URL}/api/openapi.json`. If it supports MCP, use `{BASE_URL}/mcp.json` and the agent pack at `{BASE_URL}/api/download/oligovigil_agent_pack.zip`.

Build against these rules:

1. Use verified release evidence for claims.
2. Treat candidate records as non-citable gap context.
3. Use `/api/evidence_detail?domain={toxicity|offtarget}&id={id}` before making record-level safety claims.
4. Do not infer clinical safety or de novo off-target risk.
5. Preserve benchmark reference split groups and cite version/checksum metadata.

Useful workflows:

- Search evidence: `/api/search?q={query}`.
- Browse verified records: `/api/evidence_records?domain=toxicity&q={query}`.
- Open citable record: `/api/evidence_detail?domain=toxicity&id=1`.
- Generate source-grounded triage: `/api/safety_triage`.
- Reuse benchmark splits: `/api/benchmark` and `/api/download/benchmark_reference_splits.csv`.
- Download all tables: `/api/download/all_tables.zip`.

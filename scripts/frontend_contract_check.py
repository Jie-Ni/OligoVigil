from __future__ import annotations

import io
import json
import sys
import time
import zipfile
from urllib.request import urlopen


BASE_URL = "http://127.0.0.1:8077"


def fail(message: str) -> None:
    raise AssertionError(message)


def get(path: str) -> str:
    last_error: Exception | None = None
    for _ in range(8):
        try:
            with urlopen(f"{BASE_URL}{path}", timeout=5) as response:
                if response.status != 200:
                    fail(f"{path} returned {response.status}")
                return response.read().decode("utf-8")
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise last_error or AssertionError(f"{path} failed")


def get_json(path: str) -> object:
    return json.loads(get(path))


def main() -> None:
    html = get("/")
    for marker in [
        'id="search"',
        'id="ask"',
        'id="sequence"',
        'id="summary"',
        'id="quality"',
        'id="examples"',
        'id="query-examples"',
        'id="release"',
        'id="submission-pack-grid"',
        'id="field-completeness-table"',
        'id="core-oligo-status-grid"',
        'id="core-oligo-priority-table"',
        'id="core-oligo-gate-list"',
        'id="reviewer-risk-list"',
        'id="release-batch-list"',
        'id="benchmark-baseline-table"',
        'id="benchmark-task-list"',
        'id="agent"',
        'id="agent-summary-grid"',
        'id="agent-tool-grid"',
        'id="agent-connector-grid"',
        'id="agent-artifact-grid"',
        'id="agent-guardrail-list"',
        'id="agent-workflow-list"',
        'class="workflow-step-list"',
        'id="archive-readiness-grid"',
        'id="archive-file-table"',
        'id="adoption-grid"',
        'id="adoption-event-table"',
        'id="help"',
        'id="cite"',
        'id="usecases"',
        'id="coverage"',
        'id="source-detail"',
        'id="explorer"',
        'id="record"',
        'id="benchmark"',
        'id="triage"',
        'id="triage-helm-input"',
        'id="triage-dossier-grid"',
        'id="triage-evidence-graph"',
        'id="triage-risk-grid"',
        'id="triage-release-table"',
        'id="triage-candidate-table"',
        'id="api"',
        'id="submit"',
        'id="audit"',
        'id="evidence-record-table"',
        'id="audit-table"',
        'class="signal-strip"',
        'class="visual-band"',
        'class="examples-focus-layout"',
        "/assets/generated/hero-oligovigil-evidence.png",
        "/assets/generated/provenance-network.png",
        "/assets/generated/icon-hepatic-safety.png",
        "/assets/generated/icon-offtarget-neuro.png",
        "/api/download/evidence_release.csv",
        "/api/download/benchmark_reference_splits.csv",
        "/api/download/curation_candidates_filtered.csv",
        "/api/download/benchmark_task_cards.csv",
        "/api/download/sequence_modification_curation_template.csv",
        "/api/download/core_oligo_field_curation_packet.csv",
        "/api/download/independent_curation_validation_template.csv",
        "/api/safety_triage",
        "/api/safety_dossier",
        "/api/evidence_graph",
        "/api/prov_graph",
        "/bioschemas.json",
        "/nlweb.json",
        "/api/submission_pack",
        "/api/field_completeness",
        "/api/core_oligo_fields",
        "/api/curation_protocol",
        "/api/independent_validation",
        "/api/novelty_position",
        "/api/data_availability",
        "/api/archive_readiness",
        "/api/adoption_packet",
        "/api/agent_access",
        "/api/agent_connect",
        "/agent.json",
        "/.well-known/oligovigil-agent.json",
        "/.well-known/ai-plugin.json",
        "/mcp.json",
        "/api/download/oligovigil_agent_pack.zip",
        "/llms.txt",
        "/llms-full.txt",
        "/api/benchmark_baseline_results",
        'id="downloads"',
        'id="download-manifest-grid"',
        'id="search-molecule-table"',
        "20260604_core_validation_v45",
        'data-view-target="offtarget"',
        'data-view-target="trust"',
        'id="offtarget-taxonomy-grid"',
        'id="trust-release-grid"',
        'id="independent-validation-grid"',
        'id="validation-sampling-table"',
        'id="novelty-position-grid"',
        'id="novelty-claim-list"',
    ]:
        if marker not in html:
            fail(f"missing UI marker: {marker}")

    app_js = get("/app.js?v=contract")
    for marker in [
        "loadEvidenceRecords",
        "loadAudit",
        "loadQuality",
        "loadExamples",
        "runAsk",
        "loadAskExamples",
        "loadExampleResults",
        "loadReleaseStatus",
        "loadSubmissionPack",
        "loadFieldCompleteness",
        "loadCoreOligoFields",
        "loadCurationProtocol",
        "loadIndependentValidation",
        "loadNoveltyPosition",
        "renderReviewerRiskCards",
        "renderReleaseBatchCards",
        "renderBenchmarkTaskCards",
        "loadAgentAccess",
        "agent-tool-grid",
        "agent-connector-grid",
        "agent-artifact-grid",
        "loadHelp",
        "loadCitation",
        "loadUseCases",
        "loadCoverage",
        "loadSourceDetail",
        "loadRecordDetail",
        "loadBenchmark",
        "benchmark-baseline-table",
        "loadSequenceCoverage",
        "loadSequenceSearch",
        "loadSafetyTriage",
        "renderDossierGrid",
        "renderEvidenceGraph",
        "loadModificationProfile",
        "loadDownloadManifest",
        "loadClientExamples",
        "loadSubmissionSchema",
        "/api/evidence_records",
        "/api/ask",
        "/api/evidence_detail",
        "/api/benchmark",
        "/api/benchmark_tasks",
        "/api/case_workflows",
        "/api/help",
        "/api/release_status",
        "/api/submission_pack",
        "/api/field_completeness",
        "/api/core_oligo_fields",
        "/api/curation_protocol",
        "/api/independent_validation",
        "/api/novelty_position",
        "/api/data_availability",
        "/api/archive_readiness",
        "/api/adoption_packet",
        "/api/agent_access",
        "/api/agent_connect",
        "/agent.json",
        "/mcp.json",
        "/api/download/oligovigil_agent_pack.zip",
        "/api/benchmark_baseline_results",
        "/llms.txt",
        "/llms-full.txt",
        "/api/citation",
        "/api/sequence_coverage",
        "/api/offtarget_taxonomy",
        "/api/sequence_search",
        "/api/safety_triage",
        "/api/safety_dossier",
        "/api/evidence_graph",
        "/api/prov_graph",
        "/bioschemas.json",
        "/nlweb.json",
        "/api/download_manifest",
        "/api/downloads",
        "/api/download/core_oligo_field_curation_packet.csv",
        "/api/download/independent_curation_validation_template.csv",
        "/api/modification_profile",
        "/api/use_cases",
        "/api/case_workflows",
        "/api/client_examples",
        "/api/submission_schema",
        "/api/audit",
        "/api/facets",
        "/api/metadata",
        "/api/quality",
        "/api/coverage",
        "/api/source_detail",
        "/api/examples",
        "/api/ask",
        "/api/help",
        "/api/release_status",
        "/api/citation",
    ]:
        if marker not in app_js:
            fail(f"missing frontend contract marker: {marker}")

    metadata = get_json("/api/metadata")
    if not isinstance(metadata, dict) or metadata.get("active_source_manifest") != "source_candidates_v6.csv":
        fail("metadata endpoint does not report source_candidates_v6.csv")

    facets = get_json("/api/facets")
    if not isinstance(facets, dict) or "evidence_grades" not in facets:
        fail("facets endpoint missing evidence_grades key")

    quality = get_json("/api/quality")
    if not isinstance(quality, dict):
        fail("quality endpoint returned non-object payload")
    release_records = int(quality.get("release_evidence_records") or 0)
    verified_records = int(quality.get("curator_verified_release_records") or 0)
    if verified_records != release_records:
        fail("quality endpoint release records must all be human curator-verified")
    if release_records < 600:
        fail("quality endpoint must expose at least 600 human curator-verified release records")
    if quality.get("candidate_records", 0) < 10000:
        fail("quality endpoint returned too few 10x candidate records")

    examples = get_json("/api/examples")
    if not isinstance(examples, dict) or len(examples.get("examples", [])) < 10:
        fail("examples endpoint returned too few query examples")

    ask = get_json("/api/ask?q=Show%20GalNAc%20liver%20toxicity%20Grade%20A%2FB%20evidence")
    if not isinstance(ask, dict) or ask.get("query_plan", {}).get("write_access") is not False:
        fail("ask endpoint must expose a read-only query plan")
    if "records" not in ask or "citations" not in ask:
        fail("ask endpoint missing grounded records or citations")
    if ask.get("interpreted_query", {}).get("domain") != "toxicity":
        fail("ask endpoint failed to infer toxicity domain")

    use_cases = get_json("/api/use_cases")
    if not isinstance(use_cases, dict) or len(use_cases.get("use_cases", [])) < 4:
        fail("use_cases endpoint returned too few workflows")
    if len(use_cases.get("case_workflows", [])) < 4:
        fail("use_cases endpoint returned too few case workflows")

    case_workflows = get_json("/api/case_workflows")
    if not isinstance(case_workflows, dict) or len(case_workflows.get("case_workflows", [])) < 5:
        fail("case_workflows endpoint returned too few case workflows")

    help_payload = get_json("/api/help")
    if not isinstance(help_payload, dict) or len(help_payload.get("chapters", [])) < 8:
        fail("help endpoint returned too few help chapters")

    release_status = get_json("/api/release_status")
    if not isinstance(release_status, dict) or not release_status.get("release_batches"):
        fail("release_status endpoint missing release batch status")

    submission_pack = get_json("/api/submission_pack")
    if not isinstance(submission_pack, dict):
        fail("submission_pack endpoint returned non-object payload")
    if "go_no_go" not in submission_pack or "adoption_status" not in submission_pack:
        fail("submission_pack endpoint missing go/no-go or adoption status")
    if not submission_pack.get("public_release_blockers"):
        fail("submission_pack endpoint must expose public release blockers")

    field_completeness = get_json("/api/field_completeness")
    if not isinstance(field_completeness, dict):
        fail("field_completeness endpoint returned non-object payload")
    if not field_completeness.get("fields") or "summary" not in field_completeness:
        fail("field_completeness endpoint missing fields or summary")

    archive_readiness = get_json("/api/archive_readiness")
    if not isinstance(archive_readiness, dict) or not archive_readiness.get("required_files"):
        fail("archive_readiness endpoint missing required files")
    if "zenodo_metadata_draft" not in archive_readiness:
        fail("archive_readiness endpoint missing Zenodo metadata draft")

    adoption_packet = get_json("/api/adoption_packet")
    if not isinstance(adoption_packet, dict) or not adoption_packet.get("instrumentation_events"):
        fail("adoption_packet endpoint missing instrumentation events")
    if "usage_claim_policy" not in adoption_packet:
        fail("adoption_packet endpoint missing usage claim policy")

    agent_access = get_json("/api/agent_access")
    if not isinstance(agent_access, dict) or not agent_access.get("artifacts"):
        fail("agent_access endpoint missing artifacts")
    if len(agent_access.get("guardrails", [])) < 4:
        fail("agent_access endpoint returned too few guardrails")
    if agent_access.get("pack", {}).get("files", 0) < 14:
        fail("agent_access pack metadata returned too few files")
    if not agent_access.get("tool_profiles"):
        fail("agent_access endpoint missing universal tool profiles")

    agent_connect = get_json("/api/agent_connect")
    if not isinstance(agent_connect, dict) or len(agent_connect.get("entrypoints", [])) < 5:
        fail("agent_connect endpoint missing universal entrypoints")
    if not agent_connect.get("not_tool_specific"):
        fail("agent_connect must declare tool-agnostic access")

    agent_manifest = get_json("/agent.json")
    if not isinstance(agent_manifest, dict) or "openapi" not in json.dumps(agent_manifest):
        fail("agent.json missing OpenAPI discovery")

    mcp_manifest = get_json("/mcp.json")
    if not isinstance(mcp_manifest, dict) or "mcpServers" not in mcp_manifest:
        fail("mcp.json missing MCP server config")

    citation = get_json("/api/citation")
    if not isinstance(citation, dict) or "bibtex" not in citation or "preferred_citation" not in citation:
        fail("citation endpoint missing citable text")

    client_examples = get_json("/api/client_examples")
    if not isinstance(client_examples, dict) or len(client_examples.get("examples", [])) < 4:
        fail("client_examples endpoint returned too few snippets")

    submission_schema = get_json("/api/submission_schema")
    if not isinstance(submission_schema, dict) or len(submission_schema.get("required_fields", [])) < 8:
        fail("submission_schema endpoint returned too few fields")

    coverage = get_json("/api/coverage")
    if not isinstance(coverage, dict) or not coverage.get("candidate_release_gap"):
        fail("coverage endpoint missing candidate_release_gap")

    source_detail = get_json("/api/source_detail?q=hepatotoxicity")
    if not isinstance(source_detail, dict) or not source_detail.get("source"):
        fail("source detail endpoint did not return a source")

    openapi = get_json("/api/openapi.json")
    if not isinstance(openapi, dict):
        fail("openapi endpoint returned non-object payload")
    for path in [
        "/api/quality",
        "/api/coverage",
        "/api/examples",
        "/api/ask",
        "/api/help",
        "/api/release_status",
        "/api/submission_pack",
        "/api/field_completeness",
        "/api/curation_protocol",
        "/api/data_availability",
        "/api/archive_readiness",
        "/api/adoption_packet",
        "/api/agent_access",
        "/api/agent_connect",
        "/agent.json",
        "/.well-known/oligovigil-agent.json",
        "/.well-known/ai-plugin.json",
        "/mcp.json",
        "/llms.txt",
        "/llms-full.txt",
        "/api/citation",
        "/api/use_cases",
        "/api/client_examples",
        "/api/submission_schema",
        "/api/openapi.json",
        "/api/source_detail",
        "/api/evidence_records",
        "/api/evidence_detail",
        "/api/benchmark",
        "/api/benchmark_baseline_results",
        "/api/benchmark_tasks",
        "/api/case_workflows",
        "/api/sequence_coverage",
        "/api/sequence_search",
        "/api/safety_triage",
        "/api/safety_dossier",
        "/api/evidence_graph",
        "/api/prov_graph",
        "/bioschemas.json",
        "/nlweb.json",
        "/api/modification_profile",
        "/api/download_manifest",
        "/api/download/benchmark_reference_splits.csv",
        "/api/download/benchmark_baseline_results.csv",
        "/api/download/oligovigil_agent_pack.zip",
    ]:
        if path not in openapi.get("paths", {}):
            fail(f"openapi endpoint missing {path} path")

    sequence = get_json("/api/sequence_search?sequence=AUGCUACUGACUGA&modification=galnac&target=PCSK9")
    if not isinstance(sequence, dict) or not sequence.get("sequence_features"):
        fail("sequence_search endpoint missing sequence_features")
    if sequence.get("status", {}).get("release_grade_sequence_columns_available") is not True:
        fail("sequence_search must expose release-grade sequence columns")

    triage = get_json(
        "/api/safety_triage?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human"
    )
    if not isinstance(triage, dict) or not triage.get("risk_matrix"):
        fail("safety_triage endpoint missing risk matrix")
    if triage.get("triage_policy", {}).get("prediction_mode") != "no de novo safety prediction":
        fail("safety_triage must keep no-prediction guardrail")
    if not triage.get("validation_checklist"):
        fail("safety_triage endpoint missing validation checklist")
    if not triage.get("dossier"):
        fail("safety_triage endpoint missing dossier packet metadata")

    dossier = get_json(
        "/api/safety_dossier?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human"
    )
    if not isinstance(dossier, dict) or not dossier.get("evidence_graph"):
        fail("safety_dossier endpoint missing evidence graph")
    graph = get_json(
        "/api/evidence_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human"
    )
    if not isinstance(graph, dict) or not graph.get("nodes") or not graph.get("edges"):
        fail("evidence_graph endpoint missing nodes/edges")
    prov = get_json(
        "/api/prov_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human"
    )
    if prov.get("standard") != "W3C PROV-compatible JSON profile":
        fail("prov_graph endpoint missing W3C PROV profile label")
    bioschemas = get_json("/bioschemas.json")
    if bioschemas.get("@type") != "Dataset":
        fail("bioschemas endpoint must expose Dataset JSON-LD")
    nlweb = get_json("/nlweb.json")
    if len(nlweb.get("tools", [])) < 4:
        fail("nlweb endpoint missing tool discovery entries")

    sequence_coverage = get_json("/api/sequence_coverage")
    if not isinstance(sequence_coverage, dict) or "curation_template" not in sequence_coverage:
        fail("sequence_coverage endpoint missing curation template")

    modification = get_json("/api/modification_profile?term=galnac")
    if not isinstance(modification, dict) or not modification.get("profiles"):
        fail("modification_profile endpoint returned no profiles")

    download_manifest = get_json("/api/download_manifest")
    if not isinstance(download_manifest, dict) or not download_manifest.get("files"):
        fail("download_manifest endpoint returned no files")
    if not any(file.get("sha256") for file in download_manifest.get("files", [])):
        fail("download_manifest endpoint missing SHA256 checksums")
    download_filenames = {file.get("filename") for file in download_manifest.get("files", [])}
    if "source_license_manifest_v1.csv" not in download_filenames:
        fail("download_manifest missing source_license_manifest_v1.csv")
    download_alias = get_json("/api/downloads")
    if download_alias.get("version") != download_manifest.get("version"):
        fail("download alias version does not match download_manifest")

    search = get_json("/api/search?q=GalNAc%20hepatotoxicity")
    if not isinstance(search, dict) or not search.get("toxicity"):
        fail("search endpoint must support tokenized GalNAc hepatotoxicity queries")

    evidence = get_json("/api/evidence_records?limit=20")
    if not isinstance(evidence, list):
        fail("evidence explorer returned non-list payload")
    if release_records == 0 and evidence:
        fail("evidence explorer must hide rows before verified promotion")
    if release_records > 0 and not evidence:
        fail("evidence explorer must expose curator-verified release rows")

    evidence_detail = get_json("/api/evidence_detail?domain=toxicity&id=1")
    if release_records > 0:
        if not isinstance(evidence_detail, dict) or not evidence_detail.get("record"):
            fail("evidence_detail endpoint must expose a citable verified record")
        if "bibtex" not in evidence_detail.get("citation", {}):
            fail("evidence_detail endpoint missing BibTeX citation")

    benchmark = get_json("/api/benchmark")
    if not isinstance(benchmark, dict):
        fail("benchmark endpoint returned non-object payload")
    if release_records > 0 and int(benchmark.get("benchmark_eligible_records") or 0) <= 0:
        fail("benchmark endpoint must expose Grade A/B eligible records after verified promotion")
    if "benchmark_release" not in benchmark:
        fail("benchmark endpoint missing benchmark_release contract")
    if not benchmark.get("baseline_result_rows"):
        fail("benchmark endpoint missing diagnostic baseline results")
    baseline_results = get_json("/api/benchmark_baseline_results")
    if not isinstance(baseline_results, list) or not baseline_results:
        fail("benchmark_baseline_results endpoint returned no rows")
    baseline_models = {row.get("baseline_model") for row in baseline_results}
    for expected_model in {
        "train_majority_class",
        "modality_prior_class",
        "evidence_grade_prior_class",
        "target_prior_class",
    }:
        if expected_model not in baseline_models:
            fail(f"benchmark baseline missing {expected_model}")
    taxonomy = get_json("/api/offtarget_taxonomy")
    if not taxonomy.get("classes"):
        fail("offtarget taxonomy endpoint returned no classes")
    curation_protocol = get_json("/api/curation_protocol")
    if not isinstance(curation_protocol, dict):
        fail("curation_protocol endpoint returned non-object payload")
    release_gate = curation_protocol.get("release_gate", {})
    if release_records >= 600 and not release_gate.get("all_release_records_have_verified_accept_audit"):
        fail("curation_protocol must show every release row has curator_verified accept audit")
    if not curation_protocol.get("redistribution_policy"):
        fail("curation_protocol missing redistribution policy")
    data_availability = get_json("/api/data_availability")
    if not isinstance(data_availability, dict) or not data_availability.get("availability_statement_draft"):
        fail("data_availability endpoint missing statement draft")
    if not data_availability.get("public_release_files"):
        fail("data_availability endpoint missing public release files")
    benchmark_tasks = get_json("/api/benchmark_tasks")
    if not isinstance(benchmark_tasks, list) or len(benchmark_tasks) < 2:
        fail("benchmark_tasks endpoint returned too few task cards")

    audit_toxicity = get_json("/api/audit?entity_table=toxicity_endpoint&limit=20")
    audit_offtarget = get_json("/api/audit?entity_table=offtarget_evidence&limit=20")
    if not isinstance(audit_toxicity, list) or not isinstance(audit_offtarget, list):
        fail("audit endpoint returned non-list payload")
    release_audit = [*audit_toxicity, *audit_offtarget]
    if release_records == 0 and release_audit:
        fail("release audit endpoint must be empty before verified promotion")
    if release_records > 0 and not release_audit:
        fail("release audit endpoint must expose curator-verified audit rows")

    with urlopen(f"{BASE_URL}/api/download/evidence_release.csv", timeout=5) as response:
        body = response.read().decode("utf-8")
    if "evidence_domain" not in body:
        fail("evidence_release.csv missing expected header")
    for required_header in [
        "source_document_id",
        "source_pmcid",
        "source_license_status",
        "source_reuse_category",
        "curation_basis",
        "raw_quote_included",
    ]:
        if required_header not in body.splitlines()[0]:
            fail(f"evidence_release.csv missing {required_header}")
    evidence_lines = len([line for line in body.splitlines() if line.strip()])
    if release_records == 0 and evidence_lines != 1:
        fail("evidence_release.csv must be header-only before verified promotion")
    if release_records > 0 and evidence_lines <= 1:
        fail("evidence_release.csv must contain curator-verified release rows")
    if release_records >= 600 and evidence_lines != release_records + 1:
        fail("evidence_release.csv must export every verified release row")

    with urlopen(f"{BASE_URL}/api/download/benchmark_reference_splits.csv", timeout=5) as response:
        splits = response.read().decode("utf-8")
    if "task_name" not in splits or "leakage_group" not in splits:
        fail("benchmark_reference_splits.csv missing expected header")
    split_lines = len([line for line in splits.splitlines() if line.strip()])
    if release_records > 0 and split_lines <= 1:
        fail("benchmark_reference_splits.csv must contain eligible Grade A/B rows")

    with urlopen(f"{BASE_URL}/api/download/benchmark_baseline_results.csv", timeout=5) as response:
        baseline_csv = response.read().decode("utf-8")
    if "baseline_model" not in baseline_csv or "macro_f1" not in baseline_csv or "coverage" not in baseline_csv:
        fail("benchmark_baseline_results.csv missing expected header")
    if release_records > 0 and len([line for line in baseline_csv.splitlines() if line.strip()]) <= 1:
        fail("benchmark_baseline_results.csv must contain diagnostic baseline rows")

    with urlopen(f"{BASE_URL}/llms.txt", timeout=5) as response:
        llms_text = response.read().decode("utf-8")
    if "Verified release evidence supports claims" not in llms_text:
        fail("llms.txt missing release-evidence guardrail")

    with urlopen(f"{BASE_URL}/api/download/oligovigil_agent_pack.zip", timeout=5) as response:
        agent_pack = response.read()
    with zipfile.ZipFile(io.BytesIO(agent_pack), "r") as archive:
        names = set(archive.namelist())
    for name in [
        "agent_ready/oligovigil_skill/SKILL.md",
        "agent_ready/mcp_server/oligovigil_mcp_server.py",
        "agent_ready/connectors/universal_agent_manifest.json",
        "agent_ready/connectors/mcp_client_config.json",
        "agent_ready/connectors/openapi_action_manifest.json",
        "agent_ready/prompts/universal_vibecoding_connector.md",
        "agent_ready/clients/python/oligovigil_client.py",
        "agent_ready/clients/javascript/oligovigil-client.mjs",
        "agent_ready/prompts/oligovigil_prompt_pack.md",
        "agent_ready/llms.txt",
    ]:
        if name not in names:
            fail(f"agent pack missing {name}")

    with urlopen(f"{BASE_URL}/api/download/curation_candidates_filtered.csv?domain=toxicity", timeout=5) as response:
        candidates = response.read().decode("utf-8")
    if "candidate_signal" not in candidates or "toxicity" not in candidates:
        fail("filtered candidate CSV missing expected toxicity fields")

    print("frontend_contract_check=pass")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"frontend_contract_check=fail reason={exc}", file=sys.stderr)
        raise

const REQUIRED_PUBLIC_DATA_RELEASE = "1.0.2";
const PUBLIC_MANIFEST_PATH = "/api/download_manifest";
const PUBLIC_BUNDLE_PATH = "/api/download/all_tables.zip";
const REMOVED_PUBLIC_API_PATHS = new Set([
  "/.well-known/ai-plugin.json",
  "/.well-known/nlweb.json",
  "/.well-known/oligovigil-agent.json",
  "/agent.json",
  "/api/adoption_packet",
  "/api/agent_access",
  "/api/agent_connect",
  "/api/archive_readiness",
  "/api/closest_work",
  "/api/core_oligo_fields",
  "/api/curation_protocol",
  "/api/curation_candidates",
  "/api/curation_queue",
  "/api/download/core_oligo_field_curation_packet.csv",
  "/api/download/assay.csv",
  "/api/download/curation_candidate.csv",
  "/api/download/curation_candidates_filtered.csv",
  "/api/download/curation_queue.csv",
  "/api/download/oligovigil_agent_pack.zip",
  "/api/submission_pack",
  "/api/download/independent_curation_validation_template.csv",
  "/api/download/sequence_modification_curation_template.csv",
  "/api/examples",
  "/api/ask",
  "/api/help",
  "/api/use_cases",
  "/api/case_workflows",
  "/api/sequence_coverage",
  "/api/sequence_search",
  "/api/safety_triage",
  "/api/safety_dossier",
  "/api/evidence_graph",
  "/api/prov_graph",
  "/api/modification_profile",
  "/api/client_examples",
  "/api/submission_schema",
  "/api/openapi.json",
  "/api/search",
  "/api/evidence_detail",
  "/api/field_completeness",
  "/api/manifest/closest_work_matrix_v1.csv",
  "/api/manifest/core_oligo_field_curation_packet_v1.csv",
  "/api/manifest/curation_candidate_v1.csv",
  "/api/manifest/curation_queue_v1.csv",
  "/api/manifest/curator_review_template_v1.csv",
  "/api/manifest/independent_curation_validation_template_v1.csv",
  "/api/manifest/pubmed_discovery_candidates_v1.csv",
  "/api/manifest/pubmed_discovery_candidates_v2.csv",
  "/api/manifest/pubmed_discovery_candidates_v3.csv",
  "/api/manifest/pubmed_discovery_candidates_v4.csv",
  "/api/manifest/sequence_modification_curation_template_v1.csv",
  "/api/manifest/source_candidates_v1.csv",
  "/api/manifest/source_candidates_v2.csv",
  "/api/manifest/source_candidates_v3.csv",
  "/api/manifest/source_candidates_v4.csv",
  "/api/manifest/source_candidates_v5.csv",
  "/api/manifest/source_candidates_v6.csv",
  "/api/manifest/source_document_pubmed_v1.csv",
  "/api/novelty_position",
  "/api/offtarget_taxonomy",
  "/api/quality",
  "/api/readiness",
  "/api/release_status",
  "/api/source_detail",
  "/llms-full.txt",
  "/llms.txt",
  "/mcp.json",
  "/nlweb.json",
]);

function errorResponse(status, error, detail, path) {
  return new Response(JSON.stringify({ error, detail, path }), {
    status,
    headers: {
      "content-type": "application/problem+json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function normalizePublicHeaders(headers, pathname) {
  if (pathname.endsWith(".zip")) {
    headers.set("content-type", "application/zip");
    headers.set("content-disposition", "attachment");
  } else if (pathname.endsWith(".csv")) {
    headers.set("content-type", "text/csv; charset=utf-8");
    headers.set("content-disposition", "attachment");
  } else if (pathname.endsWith(".md")) {
    headers.set("content-type", "text/markdown; charset=utf-8");
  } else if (pathname.startsWith("/api/")) {
    headers.set("content-type", "application/json; charset=utf-8");
  }
  return headers;
}

function isUnexpectedSpaFallback(response, pathname) {
  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  return pathname.startsWith("/api/") && contentType.includes("text/html");
}

async function publicReleaseManifest(context, requestUrl, requestedResponse) {
  const response =
    requestUrl.pathname === PUBLIC_MANIFEST_PATH && context.request.method !== "HEAD"
      ? requestedResponse.clone()
      : await context.env.ASSETS.fetch(
          new Request(new URL(PUBLIC_MANIFEST_PATH, requestUrl).toString()),
        );
  if (!response.ok) {
    throw new Error("Public data release manifest is missing");
  }
  let manifest;
  try {
    manifest = await response.json();
  } catch {
    throw new Error("Public data release manifest is invalid JSON");
  }
  if (manifest.data_release_version !== REQUIRED_PUBLIC_DATA_RELEASE) {
    throw new Error(
      `Public data release must be ${REQUIRED_PUBLIC_DATA_RELEASE}; ` +
        `found ${manifest.data_release_version || "unversioned"}`,
    );
  }
  return manifest;
}

function publicBundleEntry(manifest) {
  const entry = manifest.files?.find((item) => item.filename === "all_tables.zip");
  if (
    !entry ||
    !Number.isInteger(entry.bytes) ||
    entry.bytes < 0 ||
    !/^[0-9a-f]{64}$/i.test(entry.sha256 || "")
  ) {
    throw new Error("Public release manifest has no valid all_tables.zip checksum");
  }
  return entry;
}

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function verifiedBundleResponse(context, requestUrl, manifest) {
  const entry = publicBundleEntry(manifest);
  const response = await context.env.ASSETS.fetch(
    new Request(requestUrl.toString(), { method: "GET" }),
  );
  if (!response.ok) {
    throw new Error("Public all_tables.zip is missing");
  }
  const body = await response.arrayBuffer();
  if (body.byteLength !== entry.bytes) {
    throw new Error("Public all_tables.zip byte count does not match manifest");
  }
  if ((await sha256Hex(body)) !== entry.sha256.toLowerCase()) {
    throw new Error("Public all_tables.zip SHA256 does not match manifest");
  }
  const headers = normalizePublicHeaders(new Headers(response.headers), requestUrl.pathname);
  headers.set("content-length", String(body.byteLength));
  return new Response(context.request.method === "HEAD" ? null : body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export async function onRequest(context) {
  const url = new URL(context.request.url);
  url.search = "";

  if (REMOVED_PUBLIC_API_PATHS.has(url.pathname)) {
    return errorResponse(
      404,
      "public_endpoint_removed",
      "Public endpoint not available",
      url.pathname,
    );
  }

  const assetRequest = new Request(url.toString(), context.request);
  const response = await context.env.ASSETS.fetch(assetRequest);
  if (response.status === 404 || isUnexpectedSpaFallback(response, url.pathname)) {
    return errorResponse(
      404,
      "static_export_endpoint_not_available",
      "Static export endpoint not available",
      url.pathname,
    );
  }

  let manifest;
  try {
    manifest = await publicReleaseManifest(context, url, response);
    if (url.pathname === PUBLIC_BUNDLE_PATH) {
      return await verifiedBundleResponse(context, url, manifest);
    }
  } catch (error) {
    return errorResponse(
      503,
      "public_release_artifact_unavailable",
      error instanceof Error ? error.message : "Public release validation failed",
      url.pathname,
    );
  }

  const headers = normalizePublicHeaders(new Headers(response.headers), url.pathname);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

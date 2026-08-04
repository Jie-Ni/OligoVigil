const REMOVED_ROOT_PATHS = new Set([
  "/.well-known/ai-plugin.json",
  "/.well-known/nlweb.json",
  "/.well-known/oligovigil-agent.json",
  "/agent.json",
  "/llms-full.txt",
  "/llms.txt",
  "/mcp.json",
  "/nlweb.json",
]);

function notFound(path) {
  return new Response(
    JSON.stringify({
      error: "not_found",
      detail: "Resource not found",
      path,
    }),
    {
      status: 404,
      headers: {
        "content-type": "application/problem+json; charset=utf-8",
        "cache-control": "no-store",
      },
    },
  );
}

export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (REMOVED_ROOT_PATHS.has(url.pathname)) {
    return notFound(url.pathname);
  }
  return context.env.ASSETS.fetch(context.request);
}

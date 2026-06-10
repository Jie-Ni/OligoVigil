export async function onRequest(context) {
  const url = new URL(context.request.url);
  url.search = "";

  const assetRequest = new Request(url.toString(), context.request);
  const response = await context.env.ASSETS.fetch(assetRequest);
  if (response.status !== 404) {
    return response;
  }

  return new Response(
    JSON.stringify({
      error: "Static export endpoint not available",
      path: new URL(context.request.url).pathname,
    }),
    {
      status: 404,
      headers: {
        "content-type": "application/json; charset=utf-8",
      },
    },
  );
}

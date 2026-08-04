# OligoVigil Public URL Deployment Guide

OligoVigil uses a stable, no-login public HTTPS URL. The existing v1.0.1 archive identifiers are:

- Data DOI: `10.5281/zenodo.20633779`
- DOI URL: `https://doi.org/10.5281/zenodo.20633779`
- Code/data release: `https://github.com/Jie-Ni/OligoVigil/releases/tag/v1.0.1`

The recommended free public-hosting route is Cloudflare Pages. It gives a stable `*.pages.dev` HTTPS URL without requiring the local laptop to stay online. The local Docker server remains useful for development and QA; Cloudflare Tunnel is only a temporary demo unless a named tunnel is bound to a domain.

## Recommended: Cloudflare Pages

Generate the static release package from the local read-only portal:

```powershell
git clone https://github.com/Jie-Ni/OligoVigil.git
cd OligoVigil
docker compose up -d --build
python scripts\export_cloudflare_pages_static.py --base-url http://127.0.0.1:8077 --public-base-url https://oligovigil.pages.dev --output public
```

Deploy with Wrangler after Cloudflare login:

```powershell
cd OligoVigil
npx wrangler login
npx wrangler pages deploy public --project-name oligovigil
```

Expected canonical URL if the project name is available:

```text
https://oligovigil.pages.dev
```

If Cloudflare reports that `oligovigil` is already taken, use a specific project name such as `oligovigil-db` and record the assigned `*.pages.dev` URL in the site metadata and release documentation.

### What the static export contains

- Full static portal from `app/static/`
- Core read-only JSON endpoints under `/api/`
- Download files under `/api/download/`
- Source/license manifests under `/api/manifest/`
- `agent.json`, `mcp.json`, `nlweb.json`, `bioschemas.json`, `llms.txt`
- Cloudflare `_headers` and `_redirects`
- A lightweight Pages Function under `functions/api/[[path]].js` that strips query strings and serves the exported static API fallback.

### Verification after deployment

Run these checks against the live URL:

```powershell
$url = "https://oligovigil.pages.dev"
Invoke-WebRequest "$url/" -UseBasicParsing
Invoke-WebRequest "$url/api/stats" -UseBasicParsing
Invoke-WebRequest "$url/api/citation" -UseBasicParsing
Invoke-WebRequest "$url/api/download/evidence_release.csv" -UseBasicParsing
Invoke-WebRequest "$url/api/openapi.json" -UseBasicParsing
Invoke-WebRequest "$url/bioschemas.json" -UseBasicParsing
Invoke-WebRequest "$url/.well-known/oligovigil-agent.json" -UseBasicParsing
```

Then verify that site metadata and downloadable artifacts point to the intended public release.

## Temporary: Cloudflare Quick Tunnel

Use only for live preview while developing:

```powershell
cloudflared tunnel --url http://localhost:8077
```

The resulting `*.trycloudflare.com` URL is temporary and should not be used as the canonical public URL.

## Optional: Named Cloudflare Tunnel

If you later buy or already own a domain in Cloudflare, a named tunnel can map `https://oligovigil.<domain>` to the local Docker server. This is stable if the host stays online:

```powershell
cloudflared tunnel login
cloudflared tunnel create oligovigil
cloudflared tunnel route dns oligovigil oligovigil.<your-domain>
cloudflared tunnel run oligovigil
```

Cloudflare Pages avoids depending on the local machine for public availability.

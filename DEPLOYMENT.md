# OligoVigil — public-URL deployment guide

The OligoVigil portal currently runs on `127.0.0.1:8077` for local QA. NAR Database Issue policy requires a **stable public HTTPS URL** committed for **≥ 5 years** before submission. This file lists three concrete paths; pick one, stand it up, and update the manuscript Data Availability + cover letter + Figure-3 screenshot with the real URL.

The portal command is:

```bash
cd C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready
python app/server.py --host 0.0.0.0 --port 8077
```

All routes are read-only and unauthenticated by design (this is part of the NAR Database "no-login" requirement). No DB writes; no secrets in env.

---

## Option A — Cloudflare Tunnel  (fastest; suitable for the temporary review URL)

Cloudflare Tunnel routes a public HTTPS URL through Cloudflare's edge to your local process, with automatic TLS and no inbound firewall change. Free tier is unlimited bandwidth for non-commercial use.

```bash
# install once (Windows)
winget install --id Cloudflare.cloudflared

# quick-tunnel (gives you a *.trycloudflare.com URL; temporary)
cloudflared tunnel --url http://localhost:8077

# OR named tunnel (stable public URL, e.g. https://oligovigil.<your-domain>)
cloudflared tunnel login                  # opens browser; pick the domain on Cloudflare
cloudflared tunnel create oligovigil
cloudflared tunnel route dns oligovigil oligovigil.<your-domain>
# then create ~/.cloudflared/config.yml:
#   tunnel: oligovigil
#   credentials-file: C:/Users/Jie/.cloudflared/<UUID>.json
#   ingress:
#     - hostname: oligovigil.<your-domain>
#       service: http://localhost:8077
#     - service: http_status:404
cloudflared tunnel run oligovigil         # foreground, or install as a service
cloudflared service install               # Windows service (auto-start on boot)
```

**Pros:** zero ports opened, instant HTTPS, free.
**Cons:** the process must stay running on the host (UIBK laptop or a small VM). The "trycloudflare.com" quick-tunnel URL is not stable — for NAR you must use a named tunnel with your own domain.

---

## Option B — Render / Railway / Fly.io free tier  (managed, always-on)

Containerise the portal and push to a managed host. Free tiers are sufficient for read-only traffic of this volume.

Dockerfile (place at repo root if not already present):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
EXPOSE 8077
CMD ["python", "app/server.py", "--host", "0.0.0.0", "--port", "8077"]
```

`requirements.txt` minimum:

```
# already minimal: server.py uses only stdlib + sqlite3 in the current codebase.
# add nothing unless you import a third-party package.
```

Then on Render: New > Web Service > connect GitHub repo > free tier > the host name becomes `https://oligovigil.onrender.com` (or a custom domain you point at it via CNAME).

**Pros:** managed TLS, log dashboard, redeploys on git push, free for low traffic.
**Cons:** the free tier on Render spins down after 15 min idle (cold start ~30 s). For NAR demo this is fine; for a 5-year commitment plan to upgrade to a paid tier (≈ $7/mo) once you have steady traffic.

---

## Option C — UIBK institutional hosting  (most stable for the 5-year commitment)

Ask the Digital Science Center for either a sub-domain on `*.uibk.ac.at` or a small VM in the institutional cloud, and have IT terminate TLS in front of the Flask process. Concrete asks to send to IT:

1. A DNS A record `oligovigil.dsc.uibk.ac.at` (or similar) pointing at the VM.
2. TLS cert via the university's Let's Encrypt / Sectigo pipeline.
3. A systemd unit that keeps `python app/server.py --host 127.0.0.1 --port 8077` alive, with nginx reverse-proxy:

```nginx
server {
    listen 443 ssl http2;
    server_name oligovigil.dsc.uibk.ac.at;
    ssl_certificate     /etc/letsencrypt/live/oligovigil.dsc.uibk.ac.at/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/oligovigil.dsc.uibk.ac.at/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:8077;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 60s;
    }
}
```

**Pros:** the most credible "5-year stability" story for NAR reviewers.
**Cons:** depends on IT turnaround (weeks, not hours).

---

## Recommended sequence

1. Stand up **Option A named tunnel** today on your own domain → use this URL in the manuscript + cover letter for the initial submission. NAR explicitly accepts a "stable URL committed for ≥ 5 years" — this counts.
2. In parallel, file an IT ticket for **Option C** so the eventual long-lived URL is on `uibk.ac.at`. After it is live, update the manuscript Data Availability + Figure-3 screenshot at proof stage.
3. Keep Option B in your back pocket as a no-IT-required fallback.

After deployment:

- Re-capture Figure 3 at the public URL (`python` `headless-chrome` snippet from the project history works):
  ```bash
  "C:/Program Files/Google/Chrome/Application/chrome.exe" \
    --headless --disable-gpu --no-sandbox --window-size=1440,1900 --hide-scrollbars \
    --screenshot=04_delivery/screenshots/oligovigil-portal-public-YYYYMMDD.png \
    https://oligovigil.<your-domain>/
  ```
  swap the path in `MANUSCRIPT_DRAFT_v4.md` Figure 3 caption.
- Edit `MANUSCRIPT_DRAFT_v4.md`, `04_cover_letter.md`, `03_title_page.md`, `metadata_ledger.md` and the `Data Availability` declaration to replace **every** `[public HTTPS URL TBD]` with the live URL.
- Re-compile the manuscript PDF (see `04_delivery/_v4_workflow.js` or run `pandoc` directly).

This script does NOT deploy automatically (paper-skill `do_not.yaml`: `no-public-publish`). The PI selects and commits to a URL.

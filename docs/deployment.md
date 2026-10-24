# Credits-only deployment

## Static explorer: Cloudflare Pages Free

Connect the public GitHub repository. Use frontend as the root, npm ci && npm run build as the build command, and dist as the output directory. Pin Node 24. Set VITE_API_URL only after the bounded API is ready.

The report files and fonts are bundled. No API call is required to open Compare or Inspect. Hash-based routes survive direct links without server routing. The _headers file sets publication security headers. No payment plan or paid upgrade is required.

Publish the real versioned report and exported policies after evaluation. Until then the site must continue to identify itself as a scripted illustration, not a submission result. Retain static access through December 15.

## Durable state: Neon Free

Create one Free PostgreSQL project. Store its TLS connection URL as ACD_DATABASE_URL in Render's secret environment. Do not enable a paid plan. Neon Free has no trial-expiration deadline, but monitor its storage and compute allowance.

Initialize the ledger against that URL from a trusted terminal using the confirmed private credit file. The application creates its schema. Never publish the connection URL or put it in a browser environment variable.

## Live API: Render Free

render.yaml selects a Free Docker web service with a single application worker. It does not create a paid database. Initially ACD_LIVE_ENABLED is false.

Configure secret environment variables NEBIUS_API_KEY, ACD_DATABASE_URL, ACD_JUDGE_CODE, and ACD_CLIENT_SALT. Add models.json and policies.json as Render secret files. Models must match verified account access/prices. Policies must be the exact frozen policy map. Do not put either inference keys or judge codes in those public policy files.

Set ACD_ALLOWED_ORIGINS to the exact Cloudflare site origin. Verify the deployment's trusted proxy/client IP handling before enabling public traffic; never blindly accept a visitor-supplied forwarding header. A conservative shared-IP quota is preferable to a bypassable quota.

Enable live mode only after the credit ledger, frozen configurations, header path, rate limits, and bounded deployment checks pass. The API supports fixed sample tasks only, requires idempotency keys, and reserves worst-case cost before a call.

Render Free sleeps and its filesystem is ephemeral. Store every durable operational fact in Neon. The application stays idle when the queue is empty and does not self-ping to avoid sleeping. A cold start is explicitly described in Apply.

## Container and optional Nebius Jobs

Build the same Python container with Docker. Its default command serves the API; override the command with acd benchmark for a batch.

Use Nebius Jobs only after a separate compute-credit grant, sufficient balance/expiry, storage, registry access, and documented job commands are verified. No speculative compute resource is provisioned. The local runner is the selected fallback and does not claim a Nebius Jobs deployment.

## Release checklist

- Backend, PostgreSQL concurrency, frontend flow, and production builds pass.
- Actual model IDs and prices are pinned; no inference credentials in CI.
- Full benchmark assignment and report are preserved, including failed work.
- Report and bundle secret scans pass; synthetic prompt review is recorded.
- Real report export is loaded by the local runner and tested with the second adapter.
- Public/judge quotas, separate allocations, kill switch, restart handling, and cold start pass deployment checks.
- Test public site, video, and judge instructions while signed out.
- Tag the exact submitted commit. Date later fixes separately.

Free-tier references: https://render.com/docs/free, https://neon.com/pricing, https://developers.cloudflare.com/pages/functions/pricing/

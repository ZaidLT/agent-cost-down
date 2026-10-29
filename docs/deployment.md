# Credits-only deployment

Use two Vercel Hobby projects from the same private repository. Never publish the repository or submission video before explicit final approval. Previews run with inference disabled. Require Vercel Authentication for all deployments during preparation and verify anonymously. A first deployment can be promoted to production even with a preview target, so configure protection before uploading. Do not disable protection until final review approval.

## Website

Set the project root to `frontend`, framework Vite, build command `npm run build`, and output directory `dist`. Run `npm ci` for installation. Only `VITE_API_URL` belongs in frontend settings. Reports and fonts are bundled, so Compare and Inspect work without the API. Routes use URL hashes.

Keep the scripted-example label until a genuine frozen report is exported. Keep the final explorer available through December 15. Vercel reads `frontend/vercel.json` for headers; Cloudflare `_headers` is not used by Vercel.

## Neon Free

Create a dedicated Free project with separate preview and production databases. With the Vercel Marketplace integration, connect only the API project, select both environments, and enable automatic database branching for Preview only. Keep Sensitive enabled. The API uses the integration-managed DATABASE_URL on Vercel so preview branches cannot inherit a manually copied production URL. Use the integration-managed pooled TLS `DATABASE_URL` on Vercel; use `ACD_DATABASE_URL` for a separately configured local or Render connection. The Python client uses NullPool because Neon already pools connections. Do not put database URLs in frontend settings.

Initialize each database explicitly from a trusted terminal. `uv run --env-file .env acd doctor --initialize-ledger` creates the tables and configures funding from `private/credits.json`. It requires verified promotional funding and explicit billing-risk acknowledgement. Never reuse an existing ledger to reset spending, and never initialize production from preview funding liabilities. Schema creation does not occur during function startup. The explicit Vercel build command runs scripts/initialize_database.py using the private integration credentials, checks connectivity, and creates missing tables without enabling or resetting funding. Logs contain only an endpoint fingerprint, table names and readiness flags. Set ACD_PRODUCTION_DATABASE_FINGERPRINT from the production setup result before preview deployment. The build rejects previews pointing at that endpoint before changing schema. Use Git-triggered previews: verification found that CLI previews reused the production connection, while Git previews received a separate Neon branch. The build uses --no-editable to preserve an installable Python package in the function bundle. Vercel sensitive variables cannot be downloaded locally; do not weaken that protection. After code updates, run `Ledger(url).initialize_schema()` against the intended database to add new tables without resetting existing accounting.

## Live API on Vercel

Use the repository root as the second project's root. `app.py` is the FastAPI entrypoint. `worker.py`, declared in `pyproject.toml`, registers a private Queue subscriber. `vercel.json` requests a 300-second function limit. Set `ACD_EXECUTION_MODE=queue`. The validated policy deadline must be at most 180 seconds. The pilot decides whether this deployment is eligible.

Backend secrets: `NEBIUS_API_KEY`, integration-managed `DATABASE_URL` (or `ACD_DATABASE_URL` on Render), `ACD_JUDGE_CODE`, and `ACD_CLIENT_SALT`. Store the verified model catalog and frozen five-policy map in `ACD_MODELS_JSON` and `ACD_POLICIES_JSON`. Set `ACD_ALLOWED_ORIGINS` to the exact website origin. Initially set `ACD_LIVE_ENABLED=false`. Keep preview and production secrets separate. Automatically branched preview deployments cannot enable inference, since a cloned spending ledger must not create a second spend allowance. Use protected production for bounded live verification after all gates pass. `.vercelignore` excludes local secrets, private operations, generated artifacts and development tools. It must retain frontend source because both Vercel projects share the Git repository.

Admission reserves funds in Neon before sending a queue wake-up. Durable dispatch status prevents resends under the same idempotency key. Each consumer invokes at most one policy run, chosen transactionally with judge priority. A duplicate delivery cannot claim a running/completed run. Concurrent deployments share the database lease and rate history. Lost send acknowledgements cancel only unclaimed jobs; uncertain model charges remain reserved. Queued deliveries expire visibly instead of silently replaying inference. Recovery runs at startup, submission and status reads.

Verify the deployed platform overwrites `x-vercel-forwarded-for` before enabling traffic. Generic forwarding headers are not trusted. Missing trusted ingress identity fails closed. There is no public queue callback route.

## Render fallback

If development tasks need a 300- or 600-second policy deadline, deploy `render.yaml` on Render Free with `ACD_EXECUTION_MODE=local`. It runs one application worker, drains the Neon queue and stops polling when idle. The same backend secrets and model/policy JSON apply. Temporary SQLite fixtures use writable temporary storage. Render's local disk holds no durable ledger state. Verify its trusted proxy configuration before enabling public requests.

Do not upgrade any plan. If the pilot cannot complete at 600 seconds, report the blocker. Run evaluation locally; Nebius Jobs remains optional only with separately verified compute credits.

## Release gates

Run backend and isolated PostgreSQL tests, frontend checks, queue packaging checks, bundle scans, clean-install quickstart and second adapter. Verify preview outage behavior, duplicate deliveries, process termination, quota limits, Neon failure and separate allocations. Only then enable bounded live testing. Check actual free-tier allowances in the account before deployment and weekly during judging. Record verified URLs privately.

References: [Vercel Queues](https://vercel.com/docs/queues/quickstart), [Queue pricing](https://vercel.com/docs/queues/pricing), [Python subscriber configuration](https://vercel.com/docs/queues/python-sdk), [Neon Free](https://neon.com/pricing), [Render Free](https://render.com/docs/free).


## Production funding handoff after report verification

Do not initialize a second $25 ledger in production. Once report and deployment gates pass, run `uv run python scripts/funding_handoff.py --destination-fingerprint <verified-production-fingerprint>`. This atomically retires the unused $5 judge and $2.50 public allowances in the local ledger and records a recoverable transfer receipt. It refuses pools with any existing jobs. The receipt is stored privately and contains no provider or database secret.

Upload that receipt as the production-only sensitive variable `ACD_FUNDING_RECEIPT_JSON`. On the next explicit deployment build, schema initialization imports only those two allocations, with development and evaluation set to zero. The destination fingerprint and production environment must match. A repeated deployment recognizes the receipt without resetting charges, and an already-funded destination refuses unrelated receipts. Preview must never receive this variable. Funding does not enable inference: keep `ACD_LIVE_ENABLED=false` until the remaining live-test gates pass. Record the source retirement and destination acceptance in the private operations register.


Render preparation privacy: set ACD_PREPARATION_MODE=true and a strong private ACD_PREPARATION_TOKEN before the first deploy. All HTTP application endpoints require Authorization: Bearer <token>; no token is embedded in the website. Omit an HTTP health-check path so Render uses TCP checks. Approved-origin CORS preflights expose no application data. Turn preparation mode off only after publication approval, then enable HTTP /healthz checks. The Vercel website retains its platform sign-in protection until the same approval. This deployment-only wrapper does not change local benchmark prompts, policies, tools or scoring.


Before enabling Render live execution, use the preparation-protected /v1/preparation/network endpoint to compare ordinary requests with forged X-Forwarded-For and CF-Connecting-IP headers. Render documents that all web-service traffic passes through Cloudflare; verify the Cloudflare client header is present and overwritten at that ingress on this deployed service. Only after that read-only probe succeeds set ACD_RENDER_PROXY_VERIFIED=true. Live admission otherwise fails closed. The diagnostic route disappears when preparation mode is disabled, and raw client addresses are not stored in the operational ledger. References: https://render.com/articles/how-render-handles-ddos-attacks and https://developers.cloudflare.com/fundamentals/reference/http-headers/ .

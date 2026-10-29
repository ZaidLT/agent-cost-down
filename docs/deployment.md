# Credits-only deployment

Use two Vercel Hobby projects from the same private repository. Never publish the repository or submission video before explicit final approval. Previews run with inference disabled. Require Vercel Authentication for all deployments during preparation and verify anonymously. A first deployment can be promoted to production even with a preview target, so configure protection before uploading. Do not disable protection until final review approval.

## Website

Set the project root to `frontend`, framework Vite, build command `npm run build`, and output directory `dist`. Run `npm ci` for installation. Only `VITE_API_URL` belongs in frontend settings. Reports and fonts are bundled, so Compare and Inspect work without the API. Routes use URL hashes.

Keep the scripted-example label until a genuine frozen report is exported. Keep the final explorer available through December 15. Vercel reads `frontend/vercel.json` for headers; Cloudflare `_headers` is not used by Vercel.

## Neon Free

Create a dedicated Free project with separate preview and production databases. With the Vercel Marketplace integration, connect only the API project, select both environments, and enable automatic database branching for Preview only. Keep Sensitive enabled. The API uses the integration-managed DATABASE_URL on Vercel so preview branches cannot inherit a manually copied production URL. Use the pooled TLS connection strings as `ACD_DATABASE_URL` in their corresponding API environments. The Python client uses NullPool because Neon already pools connections. Do not put database URLs in frontend settings.

Initialize each database explicitly from a trusted terminal. `uv run --env-file .env acd doctor --initialize-ledger` creates the tables and configures funding from `private/credits.json`. It requires verified promotional funding and explicit billing-risk acknowledgement. Never reuse an existing ledger to reset spending, and never initialize production from preview funding liabilities. Schema creation does not occur during function startup. The explicit Vercel build command runs scripts/initialize_database.py using the private integration credentials, checks connectivity, and creates missing tables without enabling or resetting funding. Logs contain only an endpoint fingerprint, table names and readiness flags. Vercel sensitive variables cannot be downloaded locally; do not weaken that protection. After code updates, run `Ledger(url).initialize_schema()` against the intended database to add new tables without resetting existing accounting.

## Live API on Vercel

Use the repository root as the second project's root. `app.py` is the FastAPI entrypoint. `worker.py`, declared in `pyproject.toml`, registers a private Queue subscriber. `vercel.json` requests a 300-second function limit. Set `ACD_EXECUTION_MODE=queue`. The validated policy deadline must be at most 180 seconds. The pilot decides whether this deployment is eligible.

Backend secrets: `NEBIUS_API_KEY`, integration-managed `DATABASE_URL` (or `ACD_DATABASE_URL` on Render), `ACD_JUDGE_CODE`, and `ACD_CLIENT_SALT`. Store the verified model catalog and frozen five-policy map in `ACD_MODELS_JSON` and `ACD_POLICIES_JSON`. Set `ACD_ALLOWED_ORIGINS` to the exact website origin. Initially set `ACD_LIVE_ENABLED=false`. Keep preview and production secrets separate. Automatically branched preview deployments cannot enable inference, since a cloned spending ledger must not create a second spend allowance. Use protected production for bounded live verification after all gates pass. `.vercelignore` excludes local secrets, private operations, reports and development tools from backend uploads.

Admission reserves funds in Neon before sending a queue wake-up. Durable dispatch status prevents resends under the same idempotency key. Each consumer invokes at most one policy run, chosen transactionally with judge priority. A duplicate delivery cannot claim a running/completed run. Concurrent deployments share the database lease and rate history. Lost send acknowledgements cancel only unclaimed jobs; uncertain model charges remain reserved. Queued deliveries expire visibly instead of silently replaying inference. Recovery runs at startup, submission and status reads.

Verify the deployed platform overwrites `x-vercel-forwarded-for` before enabling traffic. Generic forwarding headers are not trusted. Missing trusted ingress identity fails closed. There is no public queue callback route.

## Render fallback

If development tasks need a 300- or 600-second policy deadline, deploy `render.yaml` on Render Free with `ACD_EXECUTION_MODE=local`. It runs one application worker, drains the Neon queue and stops polling when idle. The same backend secrets and model/policy JSON apply. Temporary SQLite fixtures use writable temporary storage. Render's local disk holds no durable ledger state. Verify its trusted proxy configuration before enabling public requests.

Do not upgrade any plan. If the pilot cannot complete at 600 seconds, report the blocker. Run evaluation locally; Nebius Jobs remains optional only with separately verified compute credits.

## Release gates

Run backend and isolated PostgreSQL tests, frontend checks, queue packaging checks, bundle scans, clean-install quickstart and second adapter. Verify preview outage behavior, duplicate deliveries, process termination, quota limits, Neon failure and separate allocations. Only then enable bounded live testing. Check actual free-tier allowances in the account before deployment and weekly during judging. Record verified URLs privately.

References: [Vercel Queues](https://vercel.com/docs/queues/quickstart), [Queue pricing](https://vercel.com/docs/queues/pricing), [Python subscriber configuration](https://vercel.com/docs/queues/python-sdk), [Neon Free](https://neon.com/pricing), [Render Free](https://render.com/docs/free).

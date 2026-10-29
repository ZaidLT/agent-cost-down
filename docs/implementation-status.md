# Implementation status

Updated October 29, 2026. Preparation remains private.

## Verified

- Python policy runner, five policies, bounded tools, original-state restarts and independent evaluator.
- Forty generated tasks, development and held-out partitions, frozen protocol and policy export.
- Durable ledger, idempotency, queue dispatch recovery, shared rate history and explicit PostgreSQL initialization.
- Protected Vercel website and API, with distinct Neon production and Git-preview database branches. Live inference remains disabled and hosted ledgers unfunded.
- Exact account model IDs, regular prices and rate limits saved privately. The user supplied evidence of $25 promotional credit and confirmed it lasts until consumed. The user refreshed the $25 balance and confirmed no outstanding charges on October 29.
- Reviewer changes integrated from the separate Documents checkout: NVIDIA/Nemotron explanation, adapter instructions, measured-result headline and clearer labels.
- Revised allocation: 20% development, 45% evaluation, 20% judges, 10% public, 5% safety. Reservation forecasting uses the verified catalog. This does not prove actual study affordability.
- Local backend: 75 passed, one PostgreSQL integration test skipped. Frontend build and nine browser tests passed. PostgreSQL integration, schema consistency and container build also run in CI.
- Forecast: largest reservation is $1.5704064 for Nano followed by Ultra. Development admission headroom is $3.4295936 at concurrency one or $1.8591872 at two. Public funds cannot hold two largest reservations simultaneously.

## Remaining gates

1. Local funding initialized once from refreshed evidence; hosted ledgers remain unfunded. Both 18-execution pilots are complete.
2. Use concurrency one at a 180-second deadline. Its pilot completed in 169.49 seconds with full accounting and about $0.061 estimated spend. The parallel pilot contained two Super executions with incomplete usage, including one deadline interruption; retain both and their uncertain-charge holds.
3. Record actual human review of all forty fixtures before the full development comparison.
4. Complete 100 development executions, select candidate, freeze, forecast and complete 300 held-out executions.
5. Reproduce every report number, publish genuine evidence and verify fresh exported-policy execution.
6. Fund only judge/public allocations in production through an auditable handoff; keep preview inference disabled.
7. Verify channel upload, record final video, seek an external setup test, and complete Devpost materials.
8. Obtain final publication approval, verify signed-out links, submit and tag the release.

Thirty-six real pilot executions have run. Across both pilots, known estimated charges are $0.120095763 and uncertain-charge reservations are $0.881548800, leaving $3.998355437 available for development. A preliminary development estimate with 50% headroom is $0.6124739, plus the $1.5704064 largest reservation, within that available allowance. This is not a quality or final savings claim. Public examples remain explicitly scripted. Repository and deployments remain private pending approval. Official deadline: October 30, 2026 at 20:00 Istanbul; target submission: 18:00. Weekly operational checks continue through December 15 without routine inference.

The protected website Git deployment was repaired by retaining frontend sources in the shared ignore file. Both website and API are ready, require authentication, and the API reports live execution disabled. A fresh credential-free install, offline smoke and second-adapter run passed from commit 8bcda57. Human fixture review is still pending; no full development or held-out executions have started.


## Review corrections and version 3

The original Zaid Lattouf review with AI-assisted cross-check is recorded unchanged in fixtures/review.json. Its findings prompted generator v3 under fixtures-v3/: reasonable clarification alternatives, refusal order identity, independently effective date/status filters, and an explicit inclusive return-window anchor. Original fixtures and pilot evidence remain preserved. Scenario repetition and limited partial-return coverage remain disclosed limitations. Human acknowledgement of the short amendment packet is pending; do not treat the v2 review as approval of changed v3 expectations.

Version 3 passes 85 local backend tests (one PostgreSQL integration test skipped locally), with PostgreSQL and container checks passing in CI. All 121 fixture files regenerate byte-for-byte. A fresh single-concurrency pilot completed eighteen runs in 157.14 seconds with full usage data, no rate limits or interruptions, and $0.05907684 estimated spend. Use concurrency one and a 180-second task deadline. Full development and held-out execution have not started.

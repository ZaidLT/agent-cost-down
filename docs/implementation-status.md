# Implementation status

Updated October 29, 2026. Repository and deployments remain private pending final publication approval.

## Verified implementation

- Python policy runner, five policies, bounded tools, clean-state restarts and independent evaluator.
- Forty generated v3 tasks, disjoint development and held-out template groups, policy export and frozen protocol.
- Durable accounting, idempotency, queue recovery and separate budget pools. Local ledger funded once; hosted ledgers remain unfunded.
- Protected Vercel website and API, with separate Neon production and Git-preview databases. Hosted inference is disabled.
- Exact account model IDs, regular prices and rate limits recorded privately. The owner confirmed $25 promotional credit, no outstanding charges before inference, and no expiry until consumed.
- Approved allocations: $5 development, $11.25 evaluation, $5 judges, $2.50 public, $1.25 untouched safety.
- Human fixture review and v3 amendment acknowledgement are recorded. All 121 v3 fixture files reproduce byte-for-byte. The suite has seven distinct held-out scenarios and no task asking to return more than the remaining quantity.
- Latest local checks: 94 backend tests passed, one PostgreSQL integration test skipped locally, lint passed. Frontend build and nine browser tests passed. PostgreSQL and container checks also run in CI.

## Experiment status

Four eighteen-execution pilots are preserved: original single-concurrency, original parallel, v3 at 180 seconds, and v3 at 300 seconds. The parallel pilot had two incomplete usage records; associated uncertain-charge holds remain reserved. Only concurrency one is approved by the pilot evidence.

The first complete 100-execution v3 development study used a 180-second deadline. Two Nano executions timed out with incomplete accounting. All records remain intact at artifacts/development-v3-final. The freeze gate rejected that study; no held-out executions were started from it.

The approved deadline ladder then advanced to 300 seconds. Its eighteen-execution pilot completed with full accounting, no throttling or interruption, and $0.06514766 estimated spend. A fresh 100-execution development study is running at artifacts/development-v3-300. It passed the forecast and reservation-headroom check before starting. Completion and affordability of the held-out study are not yet established.

During that development batch, API-only changes added protected Render preparation and verified ingress handling. These do not change the local benchmark runner, prompts, tools, model settings or evaluator. The final code hash will be frozen after development and before held-out execution.

## Remaining release gates

1. Complete the development study with complete accounting, select its candidate, freeze, and forecast all 300 held-out executions with 50% headroom.
2. Run the untouched held-out study, preserve failures and reproduce all displayed metrics. Report negative results honestly.
3. Finish Render Free setup for the longer task deadline, using Neon production data. Verify ingress headers and private preparation access. Website stays on Vercel.
4. Transfer only the judge/public allocations to production using the one-time funding handoff. Never fund multiple ledgers from the same allocation.
5. Verify exported-policy execution, public controls, product flow, privacy and clean-install reproduction. Replace scripted defaults only with genuine measured evidence.
6. Complete the video, actual sponsor feedback, judge instructions and Devpost materials. Record external setup participation honestly.
7. Present the release for explicit publication approval, then verify signed-out links, submit and tag the exact release.

Official deadline: October 30, 2026 at 20:00 Istanbul; submission target: 18:00. Judge access must remain available through December 15. A passing test suite or scripted deployment is not a completed submission.


## V4 controlled repair, October 30

The complete v3 held-out report is preserved with status not_validated. The narrow v4 amendment and implementation were committed as aadb926 before inference. Offline replay accepted all 60 affected attempts and recovered 33 final held-out failures and nine development failures. Local verification passed 102 backend tests and ten browser tests; CI passed PostgreSQL, schemas and the container build. V4 is supervised with a hard 08:00 Istanbul cutoff. No v4 conclusion is claimed until its report exists.

Render Free is deployed with private bearer access and inference disabled. The proxy-verification flag remains disabled following automatic approval review; public quota admission must remain disabled until a trusted ingress proof is accepted. The existing production Neon database is verified and unfunded.

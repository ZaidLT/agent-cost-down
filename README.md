# Agent Cost Down

Compare an agent's execution policies, inspect independent outcomes, and apply the exact configuration you export.

A Python tool agent runs a fictional store through five fixed policies: small, Super, Ultra, small with one retry, and small followed by Ultra. Runtime checks decide whether another attempt is allowed. An independent evaluator scores the result afterward. Every attempt contributes to cost and latency.

**Current status:** the engine, generated fixtures, budget controls, API, report explorer, and deterministic tests are implemented. The bundled explorer uses clearly labeled scripted test fixtures. No Token Factory quality or savings result has been measured. Account setup, human fixture review, real evaluation, hosted publication, video, and competition submission remain release gates.

## Quickstart

Prerequisites: Python 3.13, uv, Node 24, npm, and Git. Account setup is separate from the ten-minute local setup target. This path uses no inference credits.

```sh
git clone https://github.com/ZaidLT/agent-cost-down.git
cd agent-cost-down
uv sync --locked
uv run acd doctor
uv run acd smoke --offline --output artifacts/illustration.json
uv run pytest
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Compare five policies, inspect the small-to-Ultra test trace, and export its configuration from Apply. Scripted identifiers cannot call the provider and carry no savings claim.

The repository includes 40 immutable generated tasks. To generate a new version without replacing them:

```sh
uv run acd --suite fixtures-v3 generate --seed 20261025 --quantity-base 3 --return-days 30 --as-of 2026-10-24
```

## Enable one bounded real run

1. Follow [account readiness](docs/operations.md). Verify promotional credit balance, expiry, card requirements, overage behavior, exact available model IDs, prices, and request/token limits. Credits are not a billing cap.
2. Copy the templates from examples into the ignored private directory. Replace every null with account-verified values. They intentionally fail validation until completed.
3. Set NEBIUS_API_KEY only in your local environment. Do not commit it or paste it into a report.
4. Initialize the durable ledger and start one task.

```sh
uv run acd doctor --online
uv run acd doctor --initialize-ledger
uv run acd smoke --policy small_only --task resolution-development-1 --output artifacts/live-smoke.json
```

A real smoke run reports the runtime verdict, separate outcome checks, and estimated charge. If usage is missing, the charge remains unknown and its reservation is retained. No uncertain request is automatically repeated.

Export and apply a policy from a measured report:

```sh
uv run acd export-policy --report artifacts/development-report.json --policy small_ultra --output artifacts/policy.json
uv run acd run --config artifacts/policy.json --task resolution-development-1 --output artifacts/applied.json
```

The loaded file controls the actual runner. Test exports are useful for inspecting the schema but fail the verified-model check for live execution.

## Reproduce the comparison

```sh
uv run acd benchmark --split development --output artifacts/development
uv run acd benchmark --split development --output artifacts/development --execute
uv run acd report --input artifacts/development --output artifacts/development-report.json
uv run acd benchmark --freeze-from artifacts/development-report.json --freeze artifacts/freeze.json
uv run acd benchmark --split heldout --freeze artifacts/freeze.json --output artifacts/heldout
uv run acd benchmark --split heldout --freeze artifacts/freeze.json --output artifacts/heldout --execute
uv run acd report --input artifacts/heldout --output artifacts/heldout-report.json
```

Commands without --execute only prepare the assignment and forecast. Freeze requires a recorded human review of all forty fixtures, complete development measurements, and matching configurations. Held-out execution checks code, dependency locks, fixtures, and model settings against the freeze.

Twenty held-out tasks, three repetitions, and five policies produce 300 assigned executions. Interrupted executions remain in the denominator. Completed checkpoints and the durable ledger prevent silent replacement. A report preserves a failed preselected candidate rather than choosing a new winner from held-out outcomes.

The held-out forecast uses development spend and duration with 50% headroom. The runtime reserves the conservative maximum cost before each run, protects separate allocations, and stops if the remaining allowance is inadequate.

Read [protocol and claims](docs/protocol.md) before quoting a result.

## Architecture

```text
Public task + original snapshot
             |
      loaded PolicyConfig
             |
      model + bounded tools
             |
      runtime validation -------- rejection -> clean restart
             |
       atomic commit / response
             |
       independent evaluator
             |
       sanitized RunRecord -> report -> React explorer
```

- Runtime package: provider, parsing, domain tools, and policy runner.
- Offline evaluator: private intent expectations and independent state comparison.
- PostgreSQL: jobs, leases, usage events, quotas, and budget reservations.
- SQLite: isolated task state and restricted authorized read-only SQL.
- Static explorer: saved reports with no API dependency.
- Public API: fixed task and policy identifiers only. No arbitrary prompts or SQL.
- Second adapter: inventory reservation, tested through the same exported-policy runner.

Generated JSON contracts are in schemas. See [architecture](docs/architecture.md) and [deployment](docs/deployment.md).

## Verification

```sh
uv run pytest
uv run ruff check src tests
cd frontend
npm run build
npx playwright install chromium
npm test
```

CI runs the backend suite with a PostgreSQL service, browser tests, production build, and container build. It has no inference key. Local PostgreSQL tests require ACD_TEST_DATABASE_URL pointing to an isolated database explicitly named acd_test.

## Troubleshooting

| Problem | Action |
| --- | --- |
| No available model or missing tool support | Resolve account access, then record the Nano-to-Lightning substitution before freezing. |
| Reservation rejected | Check confirmed balance and the named allocation. Do not top up or use the judge reserve. |
| Missing usage or interrupted request | Keep its reservation. Reconcile against provider evidence before releasing funds. |
| Rate limits or slow Ultra | Run the pilot. Test the common 180, 300, then 600 second deadline before freezing. |
| Sleeping API | Wait for the explicit wake-up message. The recorded explorer remains available. |
| Frozen input mismatch | Stop. Version the change and explicitly revise the protocol rather than overwrite evidence. |
| No report recommendation | This is a valid result. Inspect failures and limitations instead of claiming a saving. |

No CLI telemetry is collected. Please report quickstart completion time and setup blockers through GitHub issues. Visits and stars are not counted as completed use.

MIT license.

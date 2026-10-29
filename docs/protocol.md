# Measurement protocol

Five families each have eight synthetic cases: order/catalog resolution, quantity amendments, returns, read-only analysis, and ambiguity/unavailable actions. Scenario groups are assigned to development or held-out before instantiation. Generator version 2 changes the held-out scenario operation, such as size resolution instead of a color alias, relative instead of absolute quantity, or a previous partial return.

These are variations within supported workflows, not forty independently sampled production use cases. The generator and automated consistency checks do not substitute for human request/state/oracle review.

Record the review in fixtures/review.json:

```json
{
  "reviewer": "actual reviewer",
  "reviewed_at": "actual ISO timestamp",
  "reviewed_task_ids": ["all forty actual IDs"],
  "deep_review_notes": "Positive and negative cases, ambiguity, unrelated records, and business rules"
}
```

Do not populate this file merely to pass a gate.

## Development and freeze

Run six to eight development smoke tasks across the verified small, Super, and Ultra models. Record tool support, rate-limit behavior, tokens, latency, and complete task duration. Test concurrency one, then two before selecting the measured operating concurrency. The hosted API stays at one active task.

Use the bounded pilot script, first without --execute to inspect its assignment. Then run it with --concurrency 1 and --concurrency 2 in separate output directories. It uses six development tasks across all three single-model baselines, one shared limiter, fresh credit evidence, durable reservations, and a maximum of two local executions. Example: uv run --env-file .env python scripts/pilot.py --output artifacts/pilot-1 --concurrency 1 --execute. Keep these measurements separate from the full development comparison.

Start with eight model steps, twenty tool calls, and a full-task deadline of 180 seconds. If infrastructure timeouts prevent completion, test 300 then 600 seconds on development tasks. Use the smallest successful common deadline. Do not quietly increase it during final evaluation.

Run all five policies on twenty development cases. Select the cheapest candidate meeting the predeclared quality/error/savings requirements. Freeze code, dependency locks, model identifiers/settings, prices, prompts, parser, schemas, tools, limits, fixtures, review, and selected candidate.

The main batch is interleaved and defaults to concurrency one. Concurrency two requires --pilot-evidence from a matching successful 18-run parallel pilot, with no throttling, interruptions or incomplete measurements. The assignment and freeze retain the concurrency and pilot hash. Shared rate limiting covers the entire batch. The freeze stores a forecast based on development cost and elapsed time with 50% headroom.

For the competition batch, the default --completion-deadline is 2026-10-30T12:00:00+03:00. This enforces the October 30 noon Istanbul completion window. The date is an explicit scheduling constraint so later independent reproductions remain possible. Resuming preserves prior assignments and forecasts the remaining work. Every large batch requires credit evidence refreshed within twenty-four hours.

## Held-out evaluation

The assignment contains twenty tasks, three repetitions, and five policies. This is 300 full policy executions, at most 420 agent attempts, and 3,360 model calls before transport retries. Repetitions measure variability; they do not create sixty independent tasks.

A checkpoint never replaces an earlier completed execution. Interrupted or missing results keep their assigned denominator. The report exposes incomplete measurements instead of assigning zero cost. A candidate is validated only if it was selected on development data and passes the held-out gates. Other policies can be inspected without being promoted to a new validated winner.

## Metrics and claims

Report absolute success counts; paired outcomes; incorrect accepted actions and mutations; critical accepted errors; estimated spend; spend per success; savings versus Ultra and the cheapest acceptable single model; median/p95 elapsed time; escalation, normalization, runtime rejection, and missing-measurement rates.

Targets: at least 90% success, no lower observed success than Ultra, at least 30% less estimated spend, no increased incorrect accepted mutations, and zero critical accepted errors. A strong cascade story also needs 15% savings against the cheapest acceptable single model or a clearly stated quality advantage.

No claim of statistical non-inferiority or general production equivalence is supported. Show every failure. If the preselected candidate fails, publish not validated.

## Publication

Use the report exporter, which blocks secret-bearing artifacts. Review synthetic prompts and traces. Never bundle account files or evaluator expectations in the static explorer. Publish a genuine report under frontend/public/reports, update index.json to its versioned filename, and preserve the original file.

A scripted illustration cannot be relabeled as a model benchmark. A cached genuine run cannot be counted as a new live execution.

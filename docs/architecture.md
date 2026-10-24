# Execution contracts

PublicTask identifies a request, customer scope, frozen date, rules, and a hashed snapshot. Agent prompts omit split labels and private expectations. The only model-visible tools are an allowlisted typed interface. There is no filesystem, network, shell, or evaluator tool.

Each attempt receives a new SQLite database created from the original snapshot. Read-only SQL runs on a separate authorized projection with an authorizer, instruction budget, output row cap, and byte cap. It cannot attach files, modify data, enable extensions, or read another customer's order.

A terminal tool is accepted only when it is the sole tool call in that model response. This prevents a committed terminal action being followed by a rejected tool in the same response. Draft changes commit inside one transaction; any rejected line rolls back the entire draft.

## Outcome separation

ACCEPT is execution validity. It is not correctness. Wrong quantities, variants, or semantically unjustified refusals can be valid runtime results and fail independent evaluation. CLARIFY is a structured missing-information response. A justified refusal has ACCEPT plus resolution refused. RETRY terminates an attempt; UNRESOLVED ends the policy without a completion claim.

FailureContext contains only the PRD's enumerated runtime observations. Every field is required, unknown fields are rejected, the serialized context is capped at 2 KB, and canonical JSON Pointer paths are checked against both tool schemas and submitted argument shapes. Source model must match the first attempt. Small-to-small and small-to-Ultra use the same contract.

The parser trims outer whitespace/BOM and at most one enclosing code fence. It rejects duplicate keys, truncated or ambiguous JSON, non-finite values, coercion, unknown fields, and unknown tools. It never asks another model to repair an answer.

## Provider accounting

Direct HTTPX requests use the documented Token Factory chat-completions endpoint. Retries are explicit and bounded. Only explicit throttling is retried. A timeout, dropped response, or server failure may be billable, so it is not automatically retried. Every dispatched request creates a durable event first.

Returned prompt/completion tokens are priced using the pinned snapshot. These are estimated inference charges, not a provider invoice. Cached-token discounts or separate hosting costs are not silently inferred.

The conservative reservation uses maximum serialized request bytes plus protocol overhead, maximum output tokens, step limits, attempt limits, transport retries, and a 25% price margin. Integer nanodollars prevent accumulated floating point drift in the ledger. A charge exceeding its reservation disables spending.

## Hosted state

PostgreSQL stores every job, idempotency key, usage event, reservation, quota, and worker lease. SQLite is supported only for local development, never as Render's durable ledger.

Transactions serialize admission and budget changes with a PostgreSQL advisory lock. Public and judge money have separate allocations. Judge priority changes queue ordering, not global spending limits. A lease prevents concurrent workers from claiming the same run. Expired running jobs become interrupted; they are not replayed.

The frontend holds a judge access code only in memory and sends it in X-Judge-Code. It is absent from static assets and URLs. API bodies permit exactly task_id and policy_id, with a required Idempotency-Key header.

Frozen benchmark artifacts are immutable. Live trace payloads expire after seven days; accounting remains. Startup and submissions wake the worker. It does not continuously poll an empty queue.

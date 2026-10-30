# Clarification scoring sensitivity

This is a post-hoc analysis of immutable report 135c81cc2a5991c2. No inference, frozen scores, evaluator, fixture, selection rule or policy configuration changed.

## Finding

Sixteen of twenty-seven final v4 failures are clarification responses to “Please update my order.” The frozen evaluator accepts exactly the structured sets [request] and [request, order_id]. It does not grade the meaning of the accompanying free-text question.

Four failed responses include request plus additional fields: all three Ultra failures and one Nano-only failure. Twelve omit request from the structured fields. Some Super free-text questions nevertheless ask what to change, so “omitted request” describes the structured list, not necessarily the question’s meaning. The cascade’s two failed clarifications contain only order_id and ask only which order to update.

## Alternative rule

For these ambiguous-update clarifications only, accept a structured list containing request regardless of additional fields. Require every other frozen outcome check to pass. This is a plausible broader rule, not a claim that it is uniquely correct or that extra questions are always desirable. Free-text questions are not rescored.

| Policy | Frozen correct / 60 | Broader rule / 60 |
| --- | --- | --- |
| Nano | 52 | 53 |
| Super | 52 | 52 |
| Ultra | 57 | 60 |
| Nano retry | 55 | 55 |
| Nano followed by Ultra | 57 | 57 |

The cascade costs 74.5% less than Ultra in the recorded runs, under either scoring interpretation. The equal 57/60 headline depends on the frozen rule. Under the broader rule, Ultra leads 60 to 57; the cascade would not satisfy the original requirement to match its observed success count. The original declared-criteria status remains preserved as historical evidence, not evidence of robust quality parity.

## Reproduction and traceability

Run `uv run python scripts/clarification_sensitivity.py`. It reads the immutable v3/v4 reports, checks the alternative totals, and regenerates presentation-only JSON in frontend/src/data/. Those files record original report hashes, exact affected run IDs and all sixteen field lists/questions. Browser tests reconcile every diagnosis category against the original run records. This is not a new benchmark or an independently validated replacement winner.

The v3-to-v4 comparison shows 52 to 27 final failures and 33 to zero verified redundant-field contract failures. The repairs to redundant fields and feedback were tested together. Do not attribute every difference to either intervention alone.

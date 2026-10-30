# Account and launch register

Keep completed account details in ignored private/operations.json. The checked-in templates contain no live credentials.

## Readiness gates

| Item | Evidence to record | Current state |
| --- | --- | --- |
| Builders and hackathon credits | Redemption result, actual usable balance, expiry, liabilities, date | $25 hackathon credit confirmed October 29, no liabilities before pilot; provider no-expiry confirmation recorded. Additional Builders credit not claimed. |
| Token Factory billing | Credits not a hard cap, explicit billing-risk acknowledgement | Risk acknowledgement recorded; local funding initialized once. No top-ups or paid upgrades. |
| Model access | Actual IDs, Nano or documented Lightning substitution, tool support | All three models completed real tool-call requests; exact identifiers are pinned privately |
| Prices and limits | Dated provider source, account RPM/TPM, usage fields | Account rates and limits recorded; successful pilot responses included usage. Unknown charges retain reservations. |
| Ultra latency | Six to eight development tasks, deadline and concurrency observations | Initial single pilot Ultra p95 4.72 seconds. Parallel Super failures preclude concurrency two; v4 complete at concurrency one; Ultra evaluation median 5.45 seconds. |
| Nebius Jobs | Separate compute-credit grant and access within two-hour preflight | No configured access; local runner selected |
| YouTube | Unlisted 10 to 15 second test upload and signed-out playback | Deferred at user request until application/results are ready. |
| Hosting | Vercel Hobby website/API, Neon Free; Render Free only if pilot requires it | Protected deployments ready; isolated Neon branches verified; protected Render live verification in progress; public access remains disabled. |
| Fixture review | Forty cases plus deep positive/negative review | Original human/AI-assisted review recorded. V3 amendment acknowledgement recorded; automated regression and consistency checks pass |
| External quickstart | Actual completion or documented recruitment attempts | Pending |

Token Factory credits do not imply Nebius Cloud compute funding. Never enable a paid upgrade, cash top-up, or paid job without changing the approved budget.

The credit template deliberately requires promotional-only funding, explicit awareness of billing overages and a positive confirmed balance with verified expiry. Disabling optional top-ups does not stop automatic billing. For provider-confirmed non-expiring credit, set expires_at to null and no_expiry_confirmed to true. An unknown expiry must not use this exception. The ledger is an application limit, not a provider-enforced billing cap. Do not share the inference key with another workload without separately reconciling its liabilities.

## Allocation

Use confirmed usable promotional credit after liabilities: 20% development, 45% evaluation, 20% judges, 10% public, 5% untouched safety. Before initializing the ledger, run `uv run python scripts/reservation_forecast.py --usable-usd <confirmed amount>` with the verified price catalog and confirm every pool can hold its worst-case reservation. Judge allocation is disabled when confirmed expiry is before the end of December 15, 2026 in the frozen implementation. Current rules now require access through December 23; release operations must separately verify funding through that date. This account has confirmed non-expiring credit, so the earlier threshold does not restrict its coverage. Never repurpose that reserve to finish a benchmark.

Recheck provider balance and expiry before each large batch and weekly during judging. Record the result. When funding evidence is stale, stop admission. When a request has ambiguous usage, end that execution without automatically replaying it and retain its reservation. Further distinct executions must fit the remaining allocation after those holds. Do not reset or delete the ledger to regain allowance.

## Schedule

October 29: finish code and account readiness, human fixture review, pilot, development evaluation and freeze.
October 30 at 12:00 Istanbul: held-out evaluation completion gate. Forecast duration and cost with 50% headroom before admission. Do not shrink the 300-run study.
October 30 at 16:00 Istanbul: finished review packet, demo, video and submission text.
October 30 at 18:00 Istanbul: submission target, after explicit publication approval. Official deadline is 20:00 Istanbul.
Within 24 hours after submission: approved community announcements.
November 7: target five actual quickstart completions and two actionable reports.
Through December 23: weekly static/API/video availability, credit/expiry/free-tier usage, and judge-access checks. Avoid model calls for routine monitoring.

## Launch evidence

Post only after the public repository/demo and truthful measured result exist. Use the permitted Nebius showcase channel and Show HN after checking their rules. Ask for setup feedback, not votes. Do not fabricate recruitment attempts or count stars as users.

Record opt-in feedback: date, setup completed, time excluding account provisioning/model latency, policy used, blocker, issue link. Report zero completions honestly if that is the observed result.

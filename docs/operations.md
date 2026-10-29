# Account and launch register

Keep completed account details in ignored private/operations.json. The checked-in templates contain no live credentials.

## Readiness gates

| Item | Evidence to record | Current state |
| --- | --- | --- |
| Builders and hackathon credits | Redemption result, actual usable balance, expiry, liabilities, date | Unverified |
| Token Factory billing | Card requirement, credits not a hard cap, explicit billing-risk acknowledgement | Unverified |
| Model access | Actual IDs, Nano or documented Lightning substitution, tool support | Key authenticates; Nano, Super and Ultra listed; tool compatibility untested |
| Prices and limits | Dated provider source, account RPM/TPM, usage fields | Unverified |
| Ultra latency | Six to eight development tasks, deadline and concurrency observations | Not measured |
| Nebius Jobs | Separate compute-credit grant and access within two-hour preflight | No configured access; local runner selected |
| YouTube | Unlisted 10 to 15 second test upload and signed-out playback | Pending account access |
| Hosting | Vercel Hobby website/API, Neon Free; Render Free only if pilot requires it | Not provisioned |
| Fixture review | Forty cases plus deep positive/negative review | Automated consistency checks pass; human review pending |
| External quickstart | Actual completion or documented recruitment attempts | Pending |

Token Factory credits do not imply Nebius Cloud compute funding. Never enable a paid upgrade, cash top-up, or paid job without changing the approved budget.

The credit template deliberately requires promotional-only funding, explicit awareness of billing overages and a positive confirmed balance with verified expiry. Disabling optional top-ups does not stop automatic billing. For provider-confirmed non-expiring credit, set expires_at to null and no_expiry_confirmed to true. An unknown expiry must not use this exception. The ledger is an application limit, not a provider-enforced billing cap. Do not share the inference key with another workload without separately reconciling its liabilities.

## Allocation

Use confirmed usable promotional credit after liabilities: 10% development, 50% evaluation, 20% judges, 10% public, 10% untouched safety. Judge allocation is disabled when confirmed expiry is before the end of December 15, 2026. Never repurpose that reserve to finish a benchmark.

Recheck provider balance and expiry before each large batch and weekly during judging. Record the result. When evidence is stale or usage is ambiguous, stop inference and retain reservations. Do not reset or delete the ledger to regain allowance.

## Schedule

October 29: finish code and account readiness, human fixture review, pilot, development evaluation and freeze.
October 30 at 12:00 Istanbul: held-out evaluation completion gate. Forecast duration and cost with 50% headroom before admission. Do not shrink the 300-run study.
October 30 at 16:00 Istanbul: finished review packet, demo, video and submission text.
October 30 at 18:00 Istanbul: submission target, after explicit publication approval. Official deadline is 20:00 Istanbul.
Within 24 hours after submission: approved community announcements.
November 7: target five actual quickstart completions and two actionable reports.
Through December 15: weekly static/API/video availability, credit/expiry/free-tier usage, and judge-access checks. Avoid model calls for routine monitoring.

## Launch evidence

Post only after the public repository/demo and truthful measured result exist. Use the permitted Nebius showcase channel and Show HN after checking their rules. Ask for setup feedback, not votes. Do not fabricate recruitment attempts or count stars as users.

Record opt-in feedback: date, setup completed, time excluding account provisioning/model latency, policy used, blocker, issue link. Report zero completions honestly if that is the observed result.

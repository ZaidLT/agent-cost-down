# Competition demo and submission

Produce a 2 minute 45 second video from actual executions after the measurement gates pass.

A separate silent upload-test clip can be recorded from the local preview with frontend/scripts/record-upload-test.mjs. It is explicitly a scripted illustration and is not the final competition video. The locally prepared clip still needs a channel upload and signed-out playback check; narration/audio checks remain part of the final video work.

## Approved opening, first twenty seconds

Nebius's cookbook compares agent cost. Agent Cost Down turns that comparison into an executable policy: start small, escalate on runtime failure, measure outcomes with an independent evaluator, then export the configuration and run a fresh task with it.

Show executable policy, runtime escalation, independent evaluation, and a loaded export in that order. Keep the evaluator visibly separate from routing. Use this wording only for features demonstrated in the submitted build.

| Time | Evidence |
| --- | --- |
| 0:00 to 0:20 | Four implemented contributions and the loaded configuration |
| 0:20 to 0:55 | A real small-model rejection and escalation or unresolved outcome |
| 0:55 to 1:25 | Independent evaluation, including an accepted incorrect result if observed |
| 1:25 to 2:05 | Complete held-out comparison, failures, cost, and latency |
| 2:05 to 2:30 | Export and run a fresh predefined task |
| 2:30 to 2:45 | Reproduction instructions, actual sponsor usage, bounded claim |

Do not manufacture a rejection inside performance results. If only the deterministic validator test exhibits escalation, label that segment as a scripted test and acknowledge the weaker empirical cascade story. Label time compression.

## Submission fields to complete from evidence

Project title: Agent Cost Down.
Summary: executable agent policies with independent outcome evaluation.
Track: Best Apps and Agents.
Repository: MIT repository, kept private until final publication approval.
Demo: verified Vercel website URL, with Vercel or Render live backend selected by the pilot.
Video: YouTube URL, made public only after final approval, under three minutes, verified signed out.
Testing: fixed task instructions and separate secret judge header instructions.
Sponsor feedback: actual observed tool support, throttling, latency, documentation, and usage-accounting findings.
Release: exact submitted commit and immutable report ID.

Measured claim template:

Across [N] held-out tasks with [R] repetitions, [policy] used [X]% less estimated inference spend than [baseline], with [A/B] successful runs, [F] incorrect accepted actions, and [L] latency. Results apply to the published synthetic workload.

Leave the result unclaimed until measured. A negative qualification result remains a legitimate report.

## Launch drafts

Nebius showcase: We built Agent Cost Down, an open-source tool that turns a cost comparison into an executable small-model escalation policy. The published report separates runtime validity from independent correctness and includes failed runs. [Insert measured result and limitation.] Try the ten-minute quickstart at [repository] and inspect the evidence at [demo]. We would value feedback on setup friction and whether the exported policy fits your agent.

Show HN title: Show HN: Agent Cost Down, executable model policies with independent evals

Show HN body: [Insert short real result.] The project compares five fixed policies on a small synthetic order-agent workload, records failed and escalated attempts, and exports the same configuration the runner consumes. It is MIT licensed. The independent evaluator runs after execution, so expected answers cannot drive escalation. Limitations and reproduction instructions are included. Feedback on the quickstart and failure analysis would be particularly useful.

Publish these drafts only after replacing every placeholder with verified evidence and checking the community's current rules.


## V4 controlled rerun disclosure

Controlled rerun on the same evaluation suite. These tasks and their v3 results were inspected before the v4 amendment. This is not fresh independent validation.

The original report remains immutable. The controlled rerun measures redundant-field acceptance and precise runtime feedback together. Do not attribute gains to either intervention separately. Missing tool calls must not be described as malformed JSON. V4 is complete: the preselected Nano followed by Ultra policy achieved 57/60 correct, matching Ultra at 74.5% lower estimated cost and about 3.5 times the median latency. Qualification applies only to the declared criteria on this reused synthetic suite.

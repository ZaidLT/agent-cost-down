# Frontend handoff

The frontend uses React, TypeScript, Vite, CSS modules, self-hosted IBM Plex Sans, and Fira Code. Compare, Inspect, and Apply retain their existing hash routes. The graphite/cyan design uses the measured cost ruler and readable rejection/recovery sequence as its signature elements.

## Run and validate

```sh
npm ci
npm run dev
npm run build
npm test
```

The test server uses loopback port 5186 with a mocked API origin. Tests intercept all API responses and never spend inference credit. Synthetic fixtures are explicitly labeled and live only under tests/. The optional real-report screenshot checks run when an exact local v4 copy is present. Screenshots are written under test-results/screenshots/ at 390, 768, and 1440 pixels.

Local verification completed with a passing production build and 35 passing Playwright tests, including all three optional real-report screenshot checks. Design Taste source lint reported zero failures and zero warnings.

The suite covers report versions and deep links, disclosure, original v3 replay classifications, all failure categories, readable diffs, exact export, mismatched configuration, protected/unavailable API, cold start, quota, uncertain submission, submission timeout, bounded polling, keyboard focus, reduced motion, and long-content overflow.

## Preview the exact v4 evidence

Copy the original reports, unchanged, into the ignored repository directory:

- artifacts/frontend-preview/135c81cc2a5991c2.json: the exact heldout-v4-report.json bytes.
- artifacts/frontend-preview/04f6d572b16fa8a5.json: the exact development-v4-report.json bytes.

Then run:

```sh
npm run preview:evidence
```

Open http://127.0.0.1:5187. This local-only overlay supplies an in-memory report index and serves the copied report bytes. It never writes the production index or modifies a benchmark. The production build continues loading public/reports/index.json. It follows the backend-owned active report selection and preserves historical versions. The frontend commit is based on main 490618a, which publishes v4 alongside the original v3 report.

## Evidence and execution compatibility

Policy exports preserve the original complete JSON configuration, including unknown fields, and add supporting_report. Live configuration matching compares the full original object before enabling execution.

The v3 diagnosis map in src/data/v3-replay.json was produced by the same read-only replay procedure as scripts/replay_v3_contract.py, using the original reports and unchanged independent evaluator. It records report IDs and verified run/attempt IDs only. Held-out: 48 affected attempts and 33 final failures. Development: 12 attempts and nine final failures. It is diagnostic evidence and never changes a model outcome. Recorded NO_TOOL_CALL events override the inaccurate legacy INVALID_JSON context label.

Set only VITE_API_URL to the public API origin when building the frontend. Live execution needs successful health/catalog checks, an allowlisted task and policy, available budget, and exact configuration equality. The selected report's 300-second measured configuration will correctly remain disabled if the live catalog uses a different deadline or validator.

Judge codes stay in memory. Submission identity also stays in memory across hash navigation and report selection. An uncertain submission can only be recovered with its original key and payload. Polling stops after 170 status checks or 11 minutes 20 seconds, with a 20-second timeout per lookup. Explicitly resuming status checks does not create a replacement run. A full browser reload clears in-memory state; copy the displayed identifiers before closing or reloading an active run.

## Integration requirements and limits

- Final v4 assets and the active index are already supplied by backend main 490618a. No backend files, frozen policies, report assets, deployment settings, or root locks are changed by the frontend commit.
- Confirm the actual public API origin and the hosting platform's CSP connect-src policy. The existing public/_headers allows Render origins and localhost:8000; Vercel has separate header configuration.
- Live API behavior is validated with mocks, not a paid production execution. Protected preparation deployments intentionally remain unavailable to this frontend.
- Browser verification uses Chromium and emulated screen sizes. Physical iOS/Android hardware and other browser engines were not tested.
- Visual/accessibility review used the Design Taste app-screen checklist and the Web Interface Guidelines at https://github.com/vercel-labs/web-interface-guidelines. No external animation or chart framework was added.

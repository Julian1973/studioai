# Pass 3 Runtime Reachability Map

This is an evidence map of the current production route, not a second architecture.

## Active path

1. `cb-studio/app.html` and `cb-studio/director.js` issue authenticated requests for
   storyboard, package, department, keyframe, voice, animation, review and post state.
2. `cb-studio/serve.py` authenticates the request, validates tokens and dispatches to the
   existing engine operation or read-only projection.
3. `engine/cb_intake.py`, `engine/cb_state.py`, `engine/cb_safety.py` and
   `engine/cb_render.py` read and mutate the existing package/shot ledgers.
4. Paid provider calls are reachable only from the explicit Fire path after spend-token,
   billing, canon, reference, audio, freshness and concurrency checks.
5. Candidate approval, dailies review, retake comparison and post assembly remain
   human-directed ledger records.

## Route classes

`ACTIVE` routes are the current UI calls and required diagnostics: `/api/storyboard`,
`/api/story-intake-*`, `/api/episode-production-start`, `/api/department-*`,
`/api/shot-*`, `/api/director-action`, `/api/dailies-review`, `/api/production-state`,
`/api/production-preflight`, `/api/stop`, and the asset/reference routes used by the UI.

`COMPATIBILITY_READ_ONLY` routes are historical record readers and the explicit 410
`LEGACY_GONE_ROUTES` response. They cannot mutate a production record or fire a provider.

`TEST_ONLY` provider comparisons and fixtures are under `engine/test_*.py` and are
zero-spend. Seedance 2.0 is available only through the explicit `legacy_compare` contract.

The unused `/api/restart` route and its handler branch were removed in Pass 3. No current
UI source or test calls it. The server's internal freshness watcher still uses `_reexec`
for code reload, so the required operational behavior was not removed.

## State mutation ownership

Readiness and approval are projected by `engine/cb_state.py` and validated by the existing
safety/lineage layer. The server does not calculate an alternative readiness answer. The
new Pass 3 tests assert the removed route is absent, the current role map remains intact,
and the no-spend production path continues to pass.

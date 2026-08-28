# StudioAI Controlled Reduction Pass 3

Date: 2026-08-28
Base: `613c594560c9c103de26829492d898cc07442d08`

## Runtime authority

The authoritative ledger remains the owner of phase state, approval freshness, content
hashes, invalidation, spending, candidates, masters and continuity. The browser renders
server state. The server authenticates and dispatches; it does not create a second approval
state machine.

The production path is:

`Script -> Production Package -> Render -> Review`

The UI/server actions map to the existing ledger-backed operations as follows:

| Intention | Current entry point | Ledger/provider boundary |
| --- | --- | --- |
| approve_script | `/api/story-intake-decide`, `/api/storyboard-approve` | `cb_intake.decide_intake`, storyboard handover |
| prepare_production_package | `/api/episode-production-start`, `/api/department-run` | package/department records |
| fire_render | `/api/shot-run` with `fire`/`next` | `cb_render.fire_shot`, spend token and provider adapter |
| review_render | `/api/director-action`, `/api/dailies-review` | candidate review and dailies records |

Read-only projections such as `/api/production-state`, `/api/production-preflight`,
`/api/shot-package` and `/api/director-session` remain diagnostic views over those records.
`/api/stop` remains the operational STOP path. The old `/api/restart` mutation route was
removed because it was not called by the current UI and duplicated the server's existing
freshness watcher.

## Classifications

- `ACTIVE`: `cb-studio/serve.py`, `engine/cb_state.py`, `engine/cb_safety.py`,
  `engine/cb_render.py`, `engine/cb_intake.py`, `engine/cb_production_preflight.py`,
  `engine/cb_providers.py`, and the current four-phase UI routes.
- `COMPATIBILITY_READ_ONLY`: historical Episode 1 field translation at read boundaries,
  `LEGACY_GONE_ROUTES` 410 responses, and the explicit Seedance 2.0 comparison transport.
- `TEST_ONLY`: `engine/test_*.py`, `cb-studio/test_*.py`, and no-spend provider fixtures.
- `DEAD` removed in this pass: legacy `fire_gate`, `approve_gate`, `unapprove_gate`,
  `set_master_studio`, `clear_master_studio`, `_gate_ready`, `regen_shot`,
  `gen_audio_beat`, `gen_keyframe_beat`, `render_beat_clip`, `approve_beat`, and
  `rebuild_keyframes` server wrappers. Repository search found no runtime callers.

## Measured reduction

Measured against the Pass 2 base:

- Production Python files: unchanged at 62; no files were split or hidden.
- Production Python lines: `45,554 -> 45,454` (`-100` real runtime lines).
- HTTP route handlers: `55 -> 54`.
- State-mutating route handlers: reduced by removal of unused `/api/restart`; remaining
  mutations are ledger-backed and covered by current UI/tests.
- CLI commands: unchanged at 48 because the remaining commands are still used by the
  application, diagnostics, recovery or compatibility tests; no command was removed on
  speculation.
- Ledger mutation owners: one existing owner (`cb_render`/ledger APIs); no new owner added.
- Readiness implementations: one public production projection (`cb_state.production_state`).
- Invalidation implementations: existing safety/lineage checks retained as the sole
  production protection; no duplicate implementation was deleted.
- Compatibility aliases: existing explicit legacy readers/410 route retained; no new alias.
- Tracked files: `493 -> 496` (`+3`, the required result, reachability and proof-test files).
- Runtime diff: `100` lines deleted, `0` lines added in `serve.py`.

## Protections and verification

No provider was contacted and no approved Episode 1 asset or ledger was edited. The current
Seedance 2.5 route, ElevenLabs v3 audio authority, exact dialogue, listener mouth closure,
30-second timing checks, explicit Fire, spend-token idempotency, concurrency, invalidation,
canon/reference locks, STOP, QA, retakes, dailies and editing remain covered by the suite.

The full verification command from a clean checkout is:

```text
pytest -q
746 passed, 4 skipped, 0 failed
```

The four skips are the existing documented historical-media skips. The branch must be
rechecked from a fresh checkout after the final commit; this result does not authorize any
default-branch or recovery-reference change.

# Dynamic state persistence — historical local implementation qualification

Superseded for release by `../qualification-pass-3/RESULTS.md`. The 99-test result below records the earlier pass; two subsequently reproduced decision faults and their corrections are documented there.

2026-09-10. No production media or approvals changed. No provider requests; network socket connections disabled throughout the test suite. Not deployed or pushed in this pass.

## Implementation

Director Card carries timed entity changes and view visibility, including changed backgrounds. The derived resolver preserves state across camera changes, handles explicitly authored story-time resets, and scopes references independently of current state. Intended states are not observed outcomes.

Prompt Director includes the resolver evidence and concise positive state instructions in its reviewed payload. Critical unresolved state revisits block even if the injected reviewer returns READY. SEE receives the same derived state/reference context while retaining its distinct opening-action assessment.

Native reference bindings preserve source-slot metadata through renumbering. Pixel-state observations only survive when stateEvidenceHash matches the attached file (native MD5, project SHA256). Changed bindings invalidate native input signatures. Unknown image contents are not automatically recognised or declared compatible.

## Validation

99 passed in 6.61s, socket.socket.connect disabled. git diff --check passed.

Files tested: test_dynamic_state.py, test_director_next_pass.py, test_prompt_director_native_audit.py, test_prompt_director_route_audit.py, test_studio_prompt_director.py, test_studio_request_evidence.py, test_studio_production.py, test_watch_retake.py.

Coverage includes attachment, collapse, transfer and marks; separate vacated support; timed camera revisits; explicit resets; critical missing entry/evidence; native binding renumbering and file replacement; shared SEE context; sealed current-state text and stale-input rejection. Earlier route tests remain passing.

One integration regression found and corrected: verbose per-reference JSON in provider text lowered native syntax score. Detailed metadata now stays in review evidence, with concise state instructions in provider text.

## Evidence boundary

This proves structured state enforcement and tested integration, not automatic recognition of arbitrary images, live semantic reviewer accuracy, or a successful honeycomb render. New plans request the structured fields; legacy free-text plans with missing fields remain explicitly unverified rather than invented. No UI for authoring the new reference evidence was added. No Studio-wide readiness claim.

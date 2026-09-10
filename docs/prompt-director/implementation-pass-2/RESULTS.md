# Implementation pass 2 — scoped qualification

Implemented locally; no live provider or paid render was run for this pass. Not Studio-wide readiness. No approved production material was migrated or rewritten.

- **Targeted edits:** `cb_render.edit_shot` now declares source hash, edit window, correction, immutable audio and outside-window preservation. Prompt Director reviews before a token is issued. The resolved prompt, scope, report and snapshot participate in the token hash; Fire recomputes current bindings before submission. The separate returned edit candidate retains its origin review.
- **SEE:** `studio_keyframe_director` is a distinct assessment of the actual candidate pixels against camera, geography, pose, props/effects and planned action. It shares reference authority resolution with WATCH. Legacy approval/prepare routes assess and persist it; Fire requires matching current evidence. Project WATCH preparation runs SEE readiness before WATCH coherence, reserves for three bounded review calls, and verifies the current SEE evidence before video submission. Existing human SEE approval is not silently revoked or treated as action-readiness evidence.
- **Blocked evidence:** protected native Fire/edit/SEE/preparation entries and project command/job failures persist reason, revision, package hash, source bindings, corrective action and submission status under `cb-output/state/preflight-attempts`. Non-exception BLOCKED project results are recorded too. Generation submission and review submission are distinguished: after a possible call, cost/call status is unknown rather than falsely zero. Missing-source attempts record that evidence gap. As with any local durable store, an unavailable filesystem prevents a write and must surface as an error.
- **Actual compiler order:** `compile_animation_provider_prompt` and final native sealing use `studio_prompt_order.compile_order`. Audience purpose precedes acting/camera, then world/reference sections, then remaining guardrails/syntax. Content is reordered without paraphrasing dialogue. The final sealed native fixture asserts purpose first.
- **Legacy returned review:** `prepare_department(review-animation)` carries the originating seal, beat/lifecycle report, source snapshot and actual reference evidence into model context and the persisted review candidate. Origin reference hashes are checked; current replacements are refused. Its review signature binds originating evidence and reviewed media, not today's animation-generation state. Sampled frames do not claim audio, adjoining-cut review, human approval or delivery eligibility.

## Tests

`test-output.txt`: **86 passed**, with socket connections disabled globally for the qualification process. Media and reviewer results are synthetic/injected.

New route evidence:
- `test_targeted_edit_blocked_before_token_or_transport`
- `test_early_exception_durable_complete`
- `test_unsuitable_see_blocks_project_watch_request`
- `test_legacy_returned_review_receives_originating_plan`
- `test_native_fire_reaches_review_and_obeys_verdict` (READY case asserts actual sealed native order)

Additional existing request evidence, retake, project production, stale authority and coherence tests also passed. `git diff --check` passed.

## Qualification boundary

These tests prove the exercised routing, source binding, refusal and persistence behaviours. They do not establish the live reviewers' accuracy in recognising action feasibility, objects, geography or state resets in pixels. No real edited render, real SEE assessment or real audiovisual review was generated. Existing imported material without a sealed origin remains explicitly outside originating-Prompt-Director qualification. Unrelated provider utilities and the whole Studio are not certified by these results. Changes are in the local working tree; no Git push or active-server reload was performed during this pass.

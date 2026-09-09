# Prompt authority v1.0.0

Implemented after the 9 September two-shot trial exposed reference-led prop reloads,
wrong flight framing and a camera-change handoff requiring state revalidation.

## Runtime changes

- Seedance storyboard compilation preserves each supplied stage's time, purpose,
  opening state, action, acting/camera direction and ending state. Previously it
  emitted only action and ending state.
- Reference roles precede the storyboard plan. A supplied opening is emitted once
  with a short stage cross-reference. Identical consistency clauses are deduplicated;
  audio text and meaningful repetitions in actions/dialogue are not rewritten.
- Image aliases (`@图1`, `@Image 1`) resolve to the same upload slot. Typed preflight
  detects duplicate bindings, absent inputs, unassigned inputs and mismatched upload
  order. One explicit opening authority is distinct from previous-state continuity.
- `requiredState` and `depictedState` compare declared, reviewed reference metadata.
  Known disagreements require reference correction, not additional negative prose.
  Missing observations remain unverified and do not create another approval gate.
- Project SEE/WATCH requests separate references, opening, context, directed acting,
  ending and sound. Raw source script remains in the review record rather than being
  appended as a second animation script. SEE retains performance context labelled
  opening-only; WATCH retains measured approved dialogue cues.
- Projects can declare `requiredReferenceStates` by library asset name. Observed
  library `depictedState` is used only when `stateEvidenceHash` matches the actual
  image hash. These fields are also retained in reference receipts.

## Evidence boundary

This is deterministic compilation and metadata validation, not image recognition.
It cannot discover an unrecorded berry in an image, judge acting, prove geographic
accuracy or certify lip sync. Visual review must record the exact source state.
A returned render remains a candidate. Existing approved prompt text and media are
not silently rewritten; changes apply when a new request is prepared.

No blanket timing holds, automatic creative retries, new providers or spending
permissions are introduced. The current shot-2 chase revision was recompiled as
v02 with the empty-prop observation. Its stale opening berry-mark observation now correctly prevents submission; it still needs its opening/storyboard aligned
before generation. No provider was called for this software change.

## Verification

231 focused regression tests passed across compiler, transport, provider contract,
project workflow, director card, references, shot remix and voice timing. Added cases
cover missing storyboard fields, upload alias/order faults, known/unknown state,
approved-prompt preservation and project request propagation.

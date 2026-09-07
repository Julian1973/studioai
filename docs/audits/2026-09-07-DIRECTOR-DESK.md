# Director desk implementation — 7 September 2026

Implemented the outcome-led desk on the existing production engine; no replacement state database or alternate generation route was introduced.

## Changes

- Shared next-step projection for shot navigation, the next-action card and Director chat. Silent shots go from SEE to WATCH preparation.
- Persistent shot strip, large review surface, docked conversation, compact progress controls and secondary review tools under disclosure.
- SEE, HEAR and WATCH navigate directly to their review surfaces. Bookmarks and refresh preserve that choice even when generation has unmet prerequisites.
- Accepted relay opening frames remain visible in SEE instead of appearing missing behind a stale world-building instruction.
- UI keyframe, voice and numbered render approvals use the same hash-bound command as chat approvals. Successful keyframe/voice decisions use the existing automatic continuation workers.
- “Continue” prepares the shared next step within the episode allowance, but never approves media or submits a reviewed WATCH request.
- Revision previews disclose affected stages, preservation of accepted versions, and the need to check following-shot continuity when the landing changes.
- Late chat responses cannot redirect a reviewer who has moved to another shot or scene.

## Verification

Full engine/server/tool suite: **1,087 passed, 4 skipped**, process exit 0. Final review-navigation and accepted-opening refinements were checked separately in the focused UI suite; **103 passed**, process exit 0; see the accompanying test outputs.

Live browser rehearsal on Episode 2 Scene 8: SEE → HEAR → WATCH navigation; opening-frame display; selected shot and tab after refresh; docked conversation; current render ahead of its supporting opening frame. No approvals or generation commands were submitted in this rehearsal.

Responsive check at 390 × 844: document width 390, viewport width 390, one docked conversation region. Desktop viewport restored afterwards.

Source audit reports no issues. JavaScript syntax checked with Node. Production audit confirms all 19 accepted takes and their landing frames remain intact; job counts are unchanged. Live service reports stale=false, running=0.

## Scope of evidence

The workflow tests use isolated state and mocked provider boundaries. They cover progression, stale review protection, candidate selection, revision preservation, budget separation and recovery behavior. No paid Episode 3 script-to-render trial was performed; there is no Episode 3 script or approved trial allowance in this task. Passing tests do not guarantee provider output quality or resolve every historical error listed in the separate chat-error reconciliation.

## Evidence

- `2026-09-07-director-desk-tests.txt`
- `2026-09-07-director-desk-ui-tests.txt`
- `2026-09-07-director-desk-source-audit.json`
- `2026-09-07-director-desk-production.json`
- `2026-09-07-director-desk.patch` (scoped comparison with the pre-change backup; repository has other pre-existing changes)

# Director workspace implementation and verification

Implemented the software-wide director workspace over the existing project production
ledger. No live production was generated, approved, migrated or replaced in this build.

## Delivered

- Scene-grouped episode board with thumbnails, measured approved duration, approved
  voice coverage, generated-versus-approved counts, actionable states and estimates.
- Unified shot workspace and selected-shot agent. Actual reference roles and versions,
  source text, director intent, timed performance and generation prompts are visible.
- Versioned project character states, explicit human state approval, episode/scene
  scope checks and structured identity-trait conflict checks.
- Proposed direction diffs, apply/discard, undo with retained outcomes and spending,
  preserved voice for picture changes, and enforced picture isolation for voice edits.
- Local episode review with visible gaps, continuous playback, timed notes, trims,
  join review, version-bound assembly approval and project-local feedback learning.
- Recoverable local assembly jobs with no provider reservation; a review movie,
  FCPXML 1.8 and source-hash manifest for finishing handoff.
- Reviewed upgrade copy for supported legacy continuity ledgers. Historical episodes
  remain read-only archives; new episodes use the project agent. Original records
  remain in place. Only matching approval hashes count as verified approved footage.

## Evidence

- Working-checkout Python suite: **1,147 passed, 4 skipped**, exit 0, 64.21 seconds.
  Output: `/tmp/studio-director-release-final.txt`. This checkout also contains the
  user's pre-existing finishing work, which was not changed or included in this build.
- Existing workflow browser gate passed: `/tmp/studio-director-legacy-browser.txt`.
- New workspace browser gate passed: `/tmp/studio-review-browser-release.txt`.
  It drives actual HTML/JS, authenticated HTTP handlers and SQLite with synthetic
  providers and real ffmpeg test media. It covers all approval stages, edit preview
  and application, voice preservation, gaps, review notes, joins, continuous playback,
  handoff downloads, stable polling, mobile layout, state upload/approval/binding and
  cross-project state isolation. No uncaught page errors were observed.
- Screenshots were inspected under `/tmp/studio-review-browser/`. Test images are
  synthetic blue/red fixtures, not examples of generated creative quality.
- Live local Studio served the updated app and review JavaScript with HTTP 200.
  The existing Crystal Bears production endpoint still reports its legacy ledger.
- Read-only upgrade preview against current production: 2 episodes, 41 shot records,
  14 characters and 292 source/media files (about 1.01 GB). Episode 2 had 19/19 matching
  approved render hashes. Episode 1's 22 historical records had no matching approval
  hashes under this adapter; their historical status is preserved without inventing
  new approvals. The report contains 17 review items. No copy was performed.
- JavaScript syntax and `git diff --check` passed.

The browser check exposed a transition race: typing while HEAR approval completed
could retain the previous voice scope. The automatic scope now follows the active
review stage even when a draft message is present, while an explicit scope selection
is respected. The full browser flow was rerun after the fix.

## Limits

Software verification uses synthetic generation providers. It does not establish
model account access, emotional performance, likeness, lip sync or broadcast quality.
Identity checks compare declared structured traits and recorded references; they do
not semantically verify every sentence or inspect rendered likeness automatically.

The review preview is a local 24 fps transcode at the first source clip's dimensions.
Original approved media remains authoritative. FCPXML structure and source paths were
tested, but no Resolve import or finishing pass was performed. Final colour, audio,
delivery specification and artistic review remain separate from assembly approval.

Legacy upgrade copies are explicit, reviewable operations. They do not make historical
shots editable through a newly invented source/approval lineage. New episodes in the
upgraded project use the new production engine; library gaps and services are visible
in setup. API credentials are not copied.

See [Director workspace](../DIRECTOR_WORKSPACE.md) for the operating guide.

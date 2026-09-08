# Project agent implementation and verification

8 September 2026. Scope: project onboarding workspaces, their production agent,
workspace connections and project-owned production records. No established project
was migrated and no real provider generation was submitted during this work.

Implemented:

- Native credential-store connections with masked metadata, checks, rotation and disabling.
- Per-project direction/image/voice/video choices, voice casting and budget estimates.
- One command dispatcher for chat and buttons, durable jobs, reservations and approvals.
- Script-to-shot direction with project references, source coverage validation and a
  versioned creative standard that is included in the provider call.
- SEE / HEAR / reviewed WATCH request / returned WATCH approvals and automatic advancement.
- Scoped picture and voice revisions, retained outcome versions, project-local review learning.
- Matched opening/ending references, final-frame extraction and approved-voice conform.
- Versioned library editing and dependency-aware source refresh; unrelated assets do not
  stop existing shots or invalidate their outcomes.
- Recovery of known task/image results without re-submission; uncertain submissions
  require explicit account reconciliation and keep their estimated spend reserved.
- Legacy mutation routes reject explicit foreign project IDs.

Verification:

- Full suite: **1,125 passed, 4 skipped**, 55.78 seconds.
- Existing browser Golden Path: passed SEE/HEAR/WATCH progression, scene-plate selection,
  provider-failure recovery, notes, navigation, hash restore, media stability and stale tabs.
- Native browser against isolated projects and fake providers: allowance → directed shots
  → SEE → button approval → HEAR → chat approval → request with prompt/script/references
  → request approval → returned movie → final approval → next shot and previous ending.
- Browser library edit: finished first shot retained; affected unfinished second picture
  moved to preparation with its previous version retained.
- Narrow viewport (390 × 844): no horizontal page overflow; controls and agent present.
- Python compilation, JavaScript syntax and scoped Git whitespace checks passed.

The browser exercise caught a poll/completion race that displayed a false stale-review
error. Resume/status reads no longer require an editing revision; they remain bound to
the project, episode and saved job. The race has a dedicated regression. Approvals still
require the current revision and exact candidate ID/hash.

Tests used isolated SQLite stores and a fake vault, never live credentials. Actual media
decode, voice conform and ending-frame extraction ran on synthetic fixtures. The macOS
keyring backend was detected; real credential saving/account permissions and provider
generation remain live setup checks. No artistic or broadcast-quality claim follows
from these tests. See [the operating guide](../PROJECT_AGENT.md) for adapter limits and
the compatibility boundary for established projects.

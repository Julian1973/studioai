# Resolve Post Supervisor benchmark audit · 8 September 2026

The skill has a strong editorial, continuity, sound and colour foundation. Its original
Studio hook prepared a brief in the legacy Crystal Bears finishing desk; it did not
launch an editor or integrate returned edits into the project production ledger.
The implementation is a verified brief/handoff foundation, not a complete autonomous
post-production pipeline or evidence of broadcast-quality output.

## Corrected during this audit

- **Project scope and direction handoff.** The existing project **Create finishing
  handoff** action now embeds the Post Supervisor contract in `source-manifest.json`,
  alongside the FCPXML. It includes the selected project's script, bible and library
  context, exact shot direction, approved SEE/HEAR/request/WATCH IDs and file hashes,
  original WATCH prompt, assembly fingerprint and explicit assembly approval state.
  Approved media preserve their own source signatures. Current project context is
  labelled separately; it cannot silently rewrite approved performance. Missing
  authority records remain explicit rather than inferred from a flattened soundtrack.
- **Historical evidence isolation.** The old code globbed every post reference into
  every legacy episode brief, including Episode 2 findings. The shared contract loader
  now includes that case study only for the legacy Crystal Bears Ep2 scope. Generic
  project handoffs use the project production standard. Review and enhancement choices
  in the skill are project-specific; the existing legacy Google receipt gate remains.
- **Approval validation.** Verdict normalization now precedes receipt checks, closing
  the mixed-case/whitespace bypass. Verdict/history writes and candidate registration
  share a local review lock. Existing version names cannot overwrite their manifest.
  The UI only enables sign-off for a receipt matching the current cut hash. Legacy
  mutation endpoints refuse an explicitly supplied foreign project ID.
- **Resolve identity evidence.** The read-only snapshot includes product/version,
  project and timeline IDs, frame rate and track counts. The review page distinguishes
  ID match, names-only, mismatch and unbound. An ID match still does not establish
  correspondence between an edited timeline and an earlier exported file.
- **Review recovery.** Notes reuse the Studio draft mechanism with project, episode
  and cut-hash scope. New text typed during a save survives that save. Status refresh
  keeps the video and its parent connected so playback position survives.
- **Skill discovery.** The canonical repository skill now has a symlink at
  `~/.codex/skills/resolve-animation-post-supervisor`; there is no second copied rule set.

## Verified

- Read-only MCP and Studio bridge calls reached **DaVinci Resolve 21.0.4.5**, project
  `Ep2`, timeline `Ep2 - Audio timing repair v02`, 30 fps, two video and two audio
  tracks. Project and timeline IDs were returned. The existing candidate records
  names only; it is honestly reported as `names-only`. No timeline was changed.
- Full repository tests: **1,173 passed, 4 skipped**, 74.46 seconds. Output:
  `/tmp/studio-resolve-audit-suite.txt`. Includes regressions for normalization,
  concurrent verdict history, stale candidate identity, foreign voice references,
  scoped post contracts, retained approvals and no provider calls during handoff.
- Project browser workflow passed with real HTTP, SQLite and synthetic media/providers:
  SEE → HEAR → request → WATCH, revisions preserving voices, notes/joins, assembly
  approval, downloadable handoff, draft recovery and project isolation, desktop/mobile.
  Output: `/tmp/studio-resolve-project-ui.txt`.
- Dedicated finishing browser test uses real UI/player and synthetic local media with
  isolated API responses. It checks cut-scoped drafts, timeline mismatch, brief-only
  messaging, matching receipt controls, refresh playback, notes typed during a save
  and mobile width. Output: `/tmp/studio-resolve-finishing-ui.txt`.
- Skill frontmatter validation and changed JavaScript syntax checks passed. Live
  authenticated Studio health returned `stale: false` and served the changed UI files.

## Remaining implementation boundary

1. **Durable Resolve execution and return.** New project handoffs do not yet dispatch
   an editing job or import a returned candidate into the same project ledger. The
   available Codex skill/tools can perform requested work, but the Studio button only
   prepares its source-bound files. A complete integration needs project/episode/version
   binding, recoverable execution, exact export provenance and a returned candidate
   requiring human review. Do not use the legacy episode-only storage for multiple IPs.
2. **Timebase and source correspondence.** The existing project interchange uses
   24 fps; the legacy registration/vCube path is qualified for 30 fps. They are separate
   routes. Equal frame count or a timeline name is not proof that an export came from
   the correct approved sources. Actual conform/edit/export readback remains necessary.
3. **Enhancement readiness.** The legacy VOD adapter is outside the new workspace
   key-vault/provider-binding flow. Durable reconciliation without a returned execution
   ID, result retrieval and enhanced-output QC are not a completed project-wide route.
   No provider settings, paid processing or enhancement credentials were changed here.
4. **Artistic and delivery proof.** Craft guidance and passing software tests do not
   prove emotional impact, lip-sync, audible quality, temporal stability or a broadcaster's
   delivery specification. A representative original-shot/stem conform through actual
   repair, exported-media motion/listening review and human sign-off is still required.

No episode footage, production approvals, provider keys, or live Resolve edits were
changed in this audit. These source changes are local working-tree changes; no Git push
or release was performed.

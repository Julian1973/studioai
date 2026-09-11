# Production request consolidation — 11 September 2026

Status: request/provenance and prompt-structure changes implemented; focused offline regression verified. This document does not qualify Studio-wide production readiness or every migration criterion in the supplied design brief.

## Scope and preserved baseline

Keep existing source authorities, approval history, media, SQLite jobs, native transport and spend controls. The request is a compiled immutable snapshot, not a new editable database. Scene 1 is a read-only production baseline. Scene 2 is the live direction-path exercise; no Scene 1 retake is requested by this implementation.

## Implementation record

- Shared immutable JSON-byte request snapshots and stage projections; separate semantic truth and execution hashes.
- Native WATCH request bound into the existing spend envelope and verified against the execution plan.
- Project WATCH request bound at Prompt Director completion, checked at reservation and again at provider submission.
- Native and project SEE/HEAR provenance captured without requiring the other stage's approval.
- Targeted edit request carries exact source hash, correction, time window and audio authority.
- Private temporary media copies prevent reopening changed source bytes after review; input hashes are checked against the copied stream.
- Exact HTTP body evidence carries the request snapshot and its origin. Invalid request integrity is durably blocked before HTTP.
- Project returned-media review uses originating opening/audio/references. It never silently substitutes a newer approved reference.
- Native returned review, project assembly and native post source records carry request lineage. Unbound historical media is explicitly legacy-unverified, not rejected or given invented provenance.
- Final Seedance ordering lives in the final compiler. Official first-frame wording no longer attracts a spurious reference-scope penalty.
- Shared concise writing brief is supplied to the native animation specialist and project director. Project payloads no longer contain the entire bible or raw direction JSON/fingerprint.
- Scene planning reads the shared directing skill; stale independent rules about permanent screen positions and blanket appearance bans were removed.
- Beat-package selection requires the current immutable script version, not only the newest filename/mtime.
- Clearing all director sessions now also clears the production-state cache.
- Showrunner review receives complete source actions, shot cards and voice records rather than truncated JSON. Its authority explicitly preserves scripted actions over treatment preferences. The live reviewer had proposed deleting scripted business; that finding caused this correction before media generation.
- Technical owner-field errors receive a bounded schema/ownership correction without substituting a new story or dropping approved words.

## Live issue found during Scene 2 preparation

The director API rejected `PlannedSceneDirection` because extensible state/cinematography dictionaries were not valid strict structured-output objects. The shared native/project OpenAI transport now encodes open dictionaries in explicit JSON capsules on the wire and decodes them before original Pydantic validation. Stored production models and state fields remain unchanged. Tests cover the actual scene/project schemas and roundtrip/type rejection. This follows the [official Structured Outputs object requirements](https://developers.openai.com/api/docs/guides/structured-outputs).

## Evidence boundaries

Hash verification proves byte/content identity. Injected reviewer verdicts and synthetic fixtures prove routing and enforcement, not automatic image understanding, acting, lip sync or broadcast quality. The installed sd25-pe 0.3.3 guidance informs prompt structure; it is not evidence that every provider feature is enabled on this account. A legacy record without an originating snapshot remains legacy-unverified. Scene 2 direction returned successfully is distinct from SEE qualification, voice approval, an animation result and final post approval.

## Verification worklist

- [x] Preserve Scene 1 package and media baseline.
- [x] Exercise request immutability, stage dependency isolation, reference ordering and changed media bytes.
- [x] Exercise native/project actual HTTP bodies with mocked networks.
- [x] Exercise strict structured-output schema conversion and state roundtrip.
- [x] Finish expanded regression run and resolve failures.
- [x] Complete live Scene 2 direction preparation and inspect its saved handoff.
- [x] Recheck Scene 1 baseline and report exact final evidence.

## Live direction outcome

`cb-output/creative/Ep3_scene2_storyboard.json` is saved against the current immutable script, with no escalation and `awaiting-human-storyboard-approval`. The final source-preserving review accepts one 16-second proposed unit, five staged views and Aida's one exact dialogue occurrence. This replaces the intermediate 23-second proposal. The production-detail timing ID correction was performed by the existing bounded retry and validated before saving.

This is a direction outcome, not a generated SEE frame or WATCH result. In SEE preparation, Sunny's image in the pool needs its own reference role even though Aida is the only physically present character. The opening/reflection assets, physical timing and final audiovisual outcome are not qualified by this text review. No approved Scene 1 source or media was changed: package SHA256 matches the starting baseline and all 54 recorded media hashes match. No image, voice or video generation was run for Scene 2; director text calls were made and recorded by the existing cost ledger.

## Final checks

- Combined focused suite: 386 passed in 66.91 seconds, including the synthetic end-to-end golden path, project/native provider routes, request evidence, source review, strict schemas, compaction, reference roles and tracked objects. Log: `/tmp/studio-request-audit/combined-final.log`.
- `git diff --check` and Python compilation passed.
- Existing dirty-tree changes were preserved; this pass did not push or create a migration.
- Native/project request adapters preserve their existing source shapes; general cross-storage semantic equivalence and real multi-case provider/post qualification remain unproven. Do not equate shared snapshot infrastructure with those completed qualifications.

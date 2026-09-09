# Scene coverage through post — integration v1.0.0

Implementation and bounded verification recorded 9 September 2026 in
`/Users/julianjenkins/Desktop/Ai Studio`. **Complete live production qualification is pending.**

The first live two-unit revision exposed integration defects not covered by the earlier
synthetic run: a current revision brief missing from downstream reviewers, inconsistent
camera-view allocation, and scene creative roles using the routine validator route.
The active evidence is in `cb-output/production-runs/Ep3_S1_workflow_refire_v01/`.
Do not infer end-to-end readiness from the historical test totals below. These defects
are being corrected and retested. Julian subsequently paused animation submissions to
prioritise software reliability. No new animation candidate has been submitted in this run.
The scoped repair evidence is recorded in
`docs/verification/2026-09-09-production-handoff-repairs.md`.

This implements the next integration pass on the shared Director Card. It is not a new
approval regime, a rewrite of approved episodes, or a claim of qualified artistic results.
The post-supervision qualification status and its existing eight real-film cases remain
unchanged. The operating premise remains: you direct the film instead of managing machinery.

## The four creative outcomes

| Outcome | Production implementation | Evidence boundary |
| --- | --- | --- |
| Cinematic language and continuity | Plan scene views before clips. Carry audience purpose, framing, motivated cut, depth/staging, opening and landing, and what the next view reveals. Packing copies the authored framing and camera purpose instead of re-directing them. | A correct plan does not prove the returned camera move or edit works. |
| Acting and performance | Preserve intention, attention, listening, observable response, timing and landing through the Director Card. The SEE compiler gets opening anticipation; WATCH gets the action and reaction. | Intentional stillness remains valid. No motion quota or promise that generated acting will succeed. |
| Dialogue | The voice specialist receives the shared acting direction; validated performed words reach ElevenLabs. Visual revisions preserve approved voice. WATCH retains the measured audio authority and separate authorised generated SFX. | Actual synchronisation and the mix require picture-and-sound review. |
| Physical, visual and effects continuity | Carry before/cause/after state, world geography, meaningful marks, prop ownership and required references. Different angles preserve the same world state instead of copying screen composition. | An observed generator error does not silently become canon. |

The opening-sequence critique remains outside this integration. Examples involving a berry,
catapult or honeycomb are regression evidence, not universal show rules.

## Changes in this pass

- Added `studio_coverage.py`: a read-only, versioned scene-board projection from existing
  `sceneCoverage`, `directorCard.views` and legacy approved storyboard fields. There is no
  second authorable plan. Planning, the selected-shot agent context, review UI and post
  handoff consume the same source.
- Extended coverage with optional staging, action, performance, planned timing, opening,
  landing and next-view reveal. Older plans remain readable without invented fields.
- Clip allocation now carries the authored framing, purpose, cut reason, explicit action,
  acting and landing directly into the typed storyboard handoff. It cannot replace them
  with a conflicting paraphrase while claiming it preserved the scene view.
- Restored opening-time acting beats in SEE. Later beats, landing states and later camera
  views stay out of still-image emission. Explicit opening staging is also included by
  the legacy image compiler; explicit per-view staging reaches the animation compiler.
- Added a collapsible scene coverage board to both the project workspace and legacy
  SEE/WATCH surfaces. Board refresh follows scene changes; old project content is removed
  when changing selection. Authored text is escaped before rendering.
- A storyboard image brief now carries the same plan revision, ordered panels and reference
  responsibilities into the selected-shot agent context. This is **brief-only**: this pass
  does not add an automatic illustrated-storyboard generation job or a 3D reconstruction
  service. The UI board displays authored views; it does not pretend drawings exist.
- Project post briefs use the render's originating direction for its coverage board,
  keeping later editorial notes separately labelled. The existing FCPXML/source manifest
  and returned-candidate verification remain the production path.
- The legacy approved-shot exporter now carries source direction context, source-package
  hash and approval receipts. It rejects a changed take where an approval hash exists,
  sorts shot 2 before shot 10, and labels the requested episode correctly.
- `register_resolve_review.py --source-manifest <episode.json>` can bind those exported
  source records to a Resolve return, checking episode and source hashes. Post briefs
  expose the captured records. Older registrations without records explicitly remain
  unverified for historical source lineage; current notes are not represented as the
  direction that produced an older render.
- Updated the project production standard to version 5. The installed post doctrine and
  canon-locked animation skill text were not re-locked or changed by this pass.

## Compatibility repair discovered by live testing

Changing the shared Director Card implementation hash made a prepared Look brief appear
stale, which in turn made an unchanged approved scene plate and keyframe appear missing.
The repaired comparison treats **only a changed shared implementation hash** as compatible
for an existing direction record when every actual scene, shot, canon, skill, reference and
media input is identical. Current voice validation and animation compilation checks still
run. Changed creative inputs or runtime skill content do not qualify for that exception.
New work still loads the current code and specialists.

The persisted Director Card envelope version remains 1.0.0 to avoid changing every
historical approval merely for an additive schema enhancement. Integration versioning is
recorded here and in the new coverage projection. Old SEE records do not acquire new
opening fields simply because a newer reader can support them.

The live Episode 3 scene plate and SEE approval were verified current again, HEAR remained
current, and the browser showed 7/7 reference readiness. Approved voice and the existing
shot-one trial retained their previously recorded SHA-256 hashes.

## Verification

- Baseline: **1 failed, 1,299 passed, 4 skipped**. The failure was the missing SEE opening
  acting beat. It was repaired without leaking later action into the still prompt.
- Final suite: `python3 -m pytest engine cb-studio -q --disable-warnings --maxfail=5` —
  **1,310 passed, 4 skipped**, 92.84 seconds.
- Added coverage propagation, selective revision, historical signature compatibility,
  source-bound post direction, escaping, numeric shot ordering and changed-media tests.
- JavaScript syntax and changed Python module compilation passed.
- All seven runtime department skill sources were readable. This is a loading check,
  not a claim that new paid specialist generations were executed during the audit.
- Live server reported current code and zero running jobs. Browser review showed the
  coverage board, SEE/HEAR current, 7/7 references ready and no captured browser errors.

## Live DaVinci round trip

The test used a separate project and synthetic script/media through real Studio
transactions and fake AI providers. No live episode was rendered, approved or replaced.

1. Studio approved-shot assembly exported FCPXML 1.8 and a source manifest.
2. Resolve Studio **21.1.0.14** imported the exported timeline using MCP. Four linked
   items (two video and two audio), zero offline media; 96 video timeline frames.
3. Resolve rendered a UHD test output. `ffprobe` verified **3840×2160, 24 fps, 96 frames,
   4.000 seconds of video**, AAC stereo at 48 kHz. The AAC stream extends to 4.074667
   seconds; video extent and frame count are exact. This is a scaling/interchange test,
   not proof of perceptual AI upscaling or broadcast picture quality.
4. The returned file entered the isolated Studio through `register_finish`, bound to the
   current handoff and exact SHA-256. It remains a **candidate**, with the explicit
   synthetic-test limitation. Source approvals remained intact.
5. The Resolve test project was saved/exported and closed. No production timeline was edited.

Project ID: `b0e0bb59-9029-47f1-8f0c-04bd65081693`.
Timeline ID: `5014cba4-5480-4d6f-997a-3cc687f65d58`.
Returned SHA-256: `cc8619adf89967cbc6c791c83639de4fc99697ffac029172abd4ac093a624876`.

Evidence: `cb-output/workflow-qualification/2026-09-09/` contains the registration record,
media probe, Resolve project export and synthetic UHD movie. The original isolated
workspace remains under `/tmp/studio-workflow-qualification-20260909/`.

## Scope of the conclusion

These results verify code paths, revision propagation, source protection, media transport
and the live Resolve return. They do not constitute a new real-film post qualification,
an audition of the final programme, proof of animation quality, or a claim that every
historical chat and provider failure was reproduced. Review used the supplied exchange,
the original four feedback areas, the consolidated implementation brief, repository
contracts/tests and current live behaviour. Artistic qualification must use the existing
source-bound real-film cases and human verdicts, without adding a new rule maze.

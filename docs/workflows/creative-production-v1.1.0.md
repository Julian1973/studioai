# Creative production integration 1.1.0

Accepted scope: `docs/build-briefs/creative-production-v1.0.0.md`.
Software integration and real-film qualification are separate. No generated-media or
broadcast-quality claim follows from compilation or regression tests.

## Authoritative implementation

- Approved screenplay intake and episode vision: `cb_creative`, `cb_departments`.
  Screenplay-supported movements replace the former mandatory seven-step plot template.
- Shared scene coverage, acting, state changes, sound cues and source links:
  `studio_director_card`; per-view cinematography and listener direction are additive.
- Scoped classified instructions: `studio_creative_authority`. Explicit current records
  resolve by authority and scope. Unclassified legacy prose is labelled honestly; it is
  not assumed to have passed semantic analysis. Unknown scope is retained conservatively.
- SEE and WATCH: existing `cb_render`, `cb_departments`, `studio_production` compilers.
  Required classified instructions enter the request. Contradictory current authorities
  stop before HTTP with the conflicting decision. Deliberate holds need no cut quota.
- Submission snapshot: `studio_request_evidence` calls `delivery_snapshot` at the existing
  HTTP boundary. The snapshot is hash-bound evidence, never independently editable.
  Actual billing stays unknown. Explicit required-instruction omission is checked even
  when the damaged prompt itself was sealed as expected.
- Voice: existing exact-word performance validation before HEAR; approved recording and
  measured timings retain authority during animation. Visual edits preserve HEAR.
- Coverage review: shared `scene-coverage.js` exposes camera/listener detail and estimated
  timed text-plan playback. This is explicitly not an illustrated animatic or an audition.
  Existing approved footage assembly and review remain the media playback path.
- Sound and finishing: existing sound cue destinations, scoped edit impact, assembly,
  source-bound post manifest and Resolve candidate registration are retained.

## Qualification still needs actual footage

Use the existing review and post qualification records, not a new approval regime.
A real current scene must pass through SEE, HEAR, WATCH, adjoining-cut review and post.
Record reverse/time-jump/effect/character-SFX/physical-cause cases with exact inspected
ranges and human verdicts. Synthetic tests do not stand in for these cases.

## Scope freeze

Further creative rules require an actual case showing a defect or ambiguity. Episode 3
production decisions are made in existing scene/shot records, never in this document.

## Verification in this implementation pass

- Engine and Studio: 1,368 passed, 4 skipped.
- Final focused checks after sound-plan projection and screenplay wording: 165 passed.
- JavaScript syntax and diff whitespace checks passed.
- No paid generation, media approval, or new Resolve render was performed in this pass.
- The timed plan currently uses estimated allocation when individual measured intervals
  are unavailable. It is explicitly text-only. It is not the illustrated/audio animatic
  described as a target in the accepted brief.
- Legacy free prose is not fully semantically classified. The resolver enforces explicit
  typed instructions; unclassified historic paths require further migration before the
  brief's every-instruction classification claim can be made.

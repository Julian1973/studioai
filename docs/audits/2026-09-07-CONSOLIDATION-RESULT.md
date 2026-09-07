# Production consolidation · 7 September 2026

Premise: **you direct the film instead of managing the machinery.**

This release separates accepted film from generation readiness, removes several false stops,
strengthens paid-request recovery, and establishes a common standard for the runtime departments.
It does not certify artistic quality or claim industry leadership from automated tests.

## What changed

- Accepted footage is verified against its recorded take and landing-frame hashes. A changed
  compiler or draft does not hide that footage or send the director back through SEE and HEAR.
  Scene 8 opens in Director's Seat with its two accepted clips and a 60-second cut to review.
- Current scene packages, the renderer, editorial and the UI use the same active-shot filter.
  Superseded units do not become the next production task. The server supplies the scene's
  recommended stage; explicit draft inspection remains available.
- One candidate is the default in both the UI and worker. Multi-candidate tests explicitly
  request their batch size; authorization still binds the exact count and request.
- Package revision bookkeeping no longer invalidates a working signature on its own.
  Exact creative inputs and references still matter. Equivalent timing notation is normalized
  without paraphrasing action or dialogue. Optional typed timing channels allow concurrent
  camera, music and action. Musical “tonic resolution” is not a resolution setting.
- Craft scores and suggested counts are advisory. Actual reference, audio, story, provider
  and authorization contradictions still stop the affected operation. The compiler no longer
  emits nonexistent slider/weight interface instructions.
- Normal shot and Scene Look reads no longer migrate and rewrite the asset registry.
  Current media URLs come from the shot ledger; historical library migration remains separate.
  An identical asset registration no longer rewrites its registry. A cold Episode 1 scene
  lookup measured 5.9 seconds after the change versus 18.3 seconds before it.
- Keyframe contract verification now includes the same standard and section fields that the
  compiler signs. Tampering remains detectable.
- BytePlus task identity is recorded durably before polling. Known tasks resume without another
  create request; completed verified downloads can be reused. A lost create response is recorded
  as unknown and cannot automatically repeat the paid POST. Credential identity and input
  fingerprints prevent attaching a different request or account to that record. Per-batch keys
  separate new candidates from a previous use of the same output name. Cost logging deduplicates
  provider task IDs. Candidate and segment claims support recovery of known tasks.
- Quote decisions have an explicit persisted outcome, including comparisons. New render-worker
  refusal events are structured; older worker logs retain a compatibility classifier.
- Policy and transaction composition are explicit in `cb_render.py`. Scene commands declare
  their lease boundary, including the previously omitted import, reopen and continuity operations.
- Three conflicting specification documents now point to one current operating contract.
  Their full previous text is retained in `docs/archive/2026-09-07-pre-consolidation/`.
  The old fal endpoint is explicitly historical, so it cannot silently govern new requests.
- The server watches the engine source build as well as its own source and restarts when idle.
  Workers use its Python interpreter. Schema 7 retains old jobs and adds their outcome field.
  Low storage is checked before the shared video gateway.

## Skills and technology

All runtime departments load [the production standard](../../skills/production-standard.md)
before their own concise marked contract. Historical prose outside those blocks is not sent to
workers. The Seedance runtime contract now agrees with the compiler's exact transcript/audio
ownership and advisory craft policy.

[Provider evidence](../../skills/provider-evidence.md) records official-source checks and their
limits. New technology must pass endpoint-specific integration checks and a bounded, human-reviewed
media comparison before promotion. ModelArk and LAS capabilities are kept distinct. No unverified
upgrade has been switched into the film's production route.

## Verification

Full suite: **1,027 passed, 4 skipped in 218.28 seconds**, exit code **0**.
The final UI regression subset separately completed: **91 passed**.
Inline JavaScript syntax and `git diff --check` also passed.
[Complete test output](2026-09-07-consolidation-tests.txt).

Live browser verification: Episode 2 Scene 8 shows both shots as accepted; the progress rail agrees;
the scene opens in Director's Seat with 2/2 approved takes and a 60-second timeline.
The episode board shows all eight scene cuts ready for review, eight human decisions and
zero attention blockers. It correctly shows zero completed final scenes because those cuts
and masters have not been newly signed off. The cut was not
locked or mastered as part of this software task. The live server reports the current engine
build, no stale source and no running jobs. A Scene 8 package read took 3.69 seconds and left
the asset registry unchanged; see [live API evidence](2026-09-07-live-verification.json).

[Read-only evidence](2026-09-07-production-evidence-after.json): all eight Episode 2 package lineages
are current; all 19 accepted takes and all 19 landing frames match their approval hashes. All 19
now project as “Approved take.” The evidence audit did not change the production packages.

The test process blocks external socket connections. Provider lifecycle tests use fake responses; media
composition tests use local fixtures. No new paid creative trial was requested by this release. On Python 3.14, the test harness
freezes the imported module graph after collection to avoid repeated expensive final GC scans;
new test objects and pytest's unraisable-exception checks remain collectable.

## Remaining qualification and architecture work

- Unknown submissions still need reconciliation with the provider; the software deliberately
  does not guess whether a charge occurred. Recovery is on re-entry to the saved request, not a
  universal automatic background reconciler for every historical job.
- Atomic JSON writes and scene leases are not a crash-atomic transaction across every filesystem
  asset and SQLite row. Explicit service composition improves traceability; the large renderer
  still needs gradual extraction into smaller services with preserved contracts.
- Historical signatures retain compatibility checks. This release removes revision-only drift;
  it does not migrate every old artifact into a new dependency graph.
- End-to-end software tests do not prove the revised skills produce better acting, comedy or
  visual continuity. That needs the next authorized production run and Julian's media review.
  Fresh full ModelArk and Seedream schemas were not available in this documentation review;
  their existing configured limits remain in force.

## Recovery

Pre-change source snapshot: `/tmp/studio-consolidation-before-20260907.zip`.
Pre-migration SQLite snapshot: `/tmp/studio-consolidation-state-before.sqlite3`.
The source snapshot excludes credentials and media. Preserve the existing dirty working tree;
restore individual changes only after comparing against that snapshot. Do not reset the repository.

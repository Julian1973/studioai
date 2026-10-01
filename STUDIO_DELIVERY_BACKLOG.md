# Studio delivery baseline — 1 October 2026

## Product contract

A human-directed script-to-screen studio for animation and live action, operated on
Macs. BytePlus Seedance 2.5 and Seedream are preferred production models. Established
ElevenLabs voices remain active until individually approved Seed replacements exist.
Specialist agents share approved production state; internal neural-network MoE and
distributed GPU execution are separate infrastructure decisions.

## Verified baseline

- `engine/cb_gen.py`: direct BytePlus Seedream image and asynchronous Seedance video adapters.
- `engine/provider_capabilities.json`: default BytePlus Seedance route currently declares
  **480p only**. Higher-resolution BytePlus production is not qualified by this registry.
- `engine/cb_db.py`: SQLite coordination for leases, spend, jobs and render ratings.
- `cb-studio/serve.py:main`: restart restores jobs and marks interrupted work honestly;
  this is not proof of automatic provider-task resumption.
- `engine/studio_profile.py`: only `crystal-bears-v1` is supported. Additional show
  profiles exist as a foundation, not universal production support.
- `engine/cb_learning.py`: evidence and proposals exist, but its default paths and show
  label remain Bears-specific; JSON read/append/write also needs concurrency review.
- Director UI, legacy UI and dailies currently use different review scales.
- Baseline suite before scored Director changes: 753 passed, 4 skipped.
- Voice identity foundation is separate draft PR #4; not merged or integrated.

## Current change: scored Director reviews

SEE/keyframe, HEAR/voice, WATCH/animation and final-master accept/iterate actions now
ask for a score from 0 to 10 and a reason. The server stores supplied evidence in
SQLite against its fresh session projection before dispatching the action.

These are **review-requested** records, not confirmation that asynchronous production
actions succeeded. Records include requested candidate, session snapshot/hash and
reviewer. They are not exact generated-media lineage and are not eligible for automatic
prompt learning. Replayed identical request IDs are idempotent; different evidence
under the same ID is refused. Older clients remain compatible without scores.

Still required: history display, binding to exact reviewed media bytes, downstream job
result linkage, stale-review protection between the displayed UI and refreshed server
state, and scored reviews in legacy/post surfaces. Scores cannot authorise spend or
change established approval semantics.

## Delivery order and exit criteria

| Priority | Work | Exit criterion |
|---|---|---|
| P0 | Complete score integration and lineage | Every review surface binds feedback to exact displayed artifact, records job result, and displays history |
| P0 | Generalise show routing | Two unrelated productions stay isolated across scripts, assets, learning, costs and exports |
| P0 | Provider recovery | Restart/timeout reconciles existing task before any resubmission; duplicate paid jobs prevented |
| P0 | Operator walkthrough | SEE → HEAR → WATCH → edit → export completes without developer intervention |
| P1 | Voice migration | Authenticated persisted auditions, permissions and Seed adapter; one character approved across emotional test set |
| P1 | Animation departments | Defined contracts and independent reviews validated on a complete scene |
| P1 | Live-action adapter | Identity, wardrobe, blocking, eyelines, coverage and realism validated on a complete scene |
| P1 | Finishing | Editable cut and separate dialogue/music/effects, technical delivery presets, verified exports |
| P1 | Mac release | Repeatable install, credentials, updates, backups and restore on second machine |
| P2 | Feedback improvement | Changes beat fixed evaluation set before promotion; project preferences isolated |
| P2 | Isambard research | Allocation and workloads confirmed; baseline establishes useful training objective |

## External prerequisites

Confirm BytePlus account access, region, model contracts, prices and commercial terms.
Confirm permitted replication of each source voice. Obtain representative production
assets and approval decisions. Confirm Isambard allocation before scheduling jobs.
Live credentials and media must not be committed to source.

## Release evidence

Track first-pass approvals, revisions per approved shot, cost per approved minute,
completion time, continuity defects and recovery success. Human creative assessment
remains a separate requirement. Tests and mocked browser flows do not certify live
provider quality, Mac installation or Adobe-level readiness.

## Verification update

The Golden Path browser gate now passes on Linux Chromium, including SEE, HEAR,
WATCH, scored reviews, provider refusal, live-state polling and stale-build protection.
This is a zero-spend test with mocked production/provider API responses, not a live
BytePlus production or Mac installation trial.

Recovery now conservatively preserves an unresolved claim after a generation adapter
was entered and an exception occurred. Neither the candidate nor its active segment
can be automatically repaid. Completed candidates remain intact. Provider reconciliation
and recovery UI remain outstanding; manual reconciliation is required before retrying.
Pre-provider failures retain the existing retry behaviour. Targeted recovery and golden
engine checks: 30 passed. BytePlus and ElevenLabs credentials are absent in this checkout.

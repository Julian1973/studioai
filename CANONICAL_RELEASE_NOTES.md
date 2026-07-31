# Canonical recovery release notes

Release: 2.0  
Date: 27 July 2026

## v2.1 governed dailies and cost-learning

- Director Review now scores whether the intended beat is actually felt, alongside acting,
  causality, timing, camera/edit, continuity, reference fidelity and finish.
- Every review identifies the likely root cause and confidence instead of treating every
  weak outcome as a prompt failure.
- Cheapest-next-action routing prefers an existing candidate, edit recovery or free
  upstream revision before paid generation.
- A paid rerender must change one lever only, preserve named successful elements and define
  observable proof of improvement.
- Acknowledged dailies become immutable learning evidence while promotion into active
  creative memory remains explicit, human-approved and tied to a versioned source change.
- Studio presents the diagnosis and next experiment in plain language beside each shot.

## Recovered source

This build reconciles the two real development lines found in the 8th Hour handover:

- the later engine/end-to-end branch from `8Th-Hour-source(1).zip`;
- the front-to-back production and safety repair from `8Th-Hour-fixed-source.zip`.

The three overlapping files were merged against the original handover as their common base:

- `engine/cb_render.py`;
- `cb-studio/serve.py`;
- `cb-studio/app.html`.

The dedicated safety layer, production preflight and repair tests were restored from the
fixed branch. Later engine improvements and current production fixtures were retained.

## Added in this canonical build

- Seedance Production Director runtime skill.
- Structured dramatic beat, performance arc, one-to-three-shot plan, reference contract,
  continuity landing and surgical safeguards.
- Free 20-point cinematic craft gate.
- Exact ordered provider-reference disclosure with content hashes.
- Animation-direction staleness signatures tied to opening frame, Scene Look, references,
  voice and package revision.
- Voice-approval content hashing.
- Contracted current/stale timing slate.
- Voice & Timing moved before Cinematography in the Studio's production rail.
- Structured Director blueprint displayed separately from the editable provider prompt.
- Production preflight reports stale Animation direction and timing-slate drift.

## Verification

```text
154 passed, 4 skipped
```

The four skips are explicit historical-fixture skips for unavailable revision-6 source
media. Current package routing, script locks, safety, provider mocks, spend tokens,
resumability, reference order, voice separation, approval lifecycle, relay frames,
stitching, static hardening and the Seedance Director contract pass.

No live media provider was called during recovery or verification.

## Installation boundary

This release is source code. It deliberately excludes the Python virtual environment,
caches, provider credentials and generated media. Preserve the production `.env`, billing
profile, approved media, output records and history when placing it into the live 8th Hour
folder.

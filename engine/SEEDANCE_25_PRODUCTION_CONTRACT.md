# Seedance 2.5 Production Contract

**Status:** production route qualified; every paid request remains human-authorised
**Target model:** `dreamina-seedance-2-5-260628` — Seedance 2.5 on BytePlus ModelArk (`engine/provider_capabilities.json` → `defaultVideoModelId`; the registry is the authority, this page describes it)
**Provider endpoint:** `/api/v3/contents/generations/tasks` (asynchronous task; transport `byteplus-async`)
**Effective:** 2026-08-16 (BytePlus qualified and billing-confirmed); the fal `bytedance/seedance-2.5/reference-to-video` route stays registered and enabled as the alternate, selectable only by `CB_VIDEO_MODEL_ID`
**Verified resolution on the default route:** 480p only (854×480). fal's route verifies 480p and 720p. There is no delivery-resolution path above 480p on the default route until BytePlus 720p/1080p is qualified and registered — an open production decision, recorded 2026-09-03.

> CORRECTED 2026-09-03: until this correction the header named fal as the target and called BytePlus "a separate disabled adapter until qualified" — stale since 2026-08-16; every real Box Monsters take shipped through BytePlus.

## One Creative Rule

The story chooses the duration. The Studio packages each scene into the fewest natural production
units that preserve its full comic, emotional, dialogue, and action timing. Every unit is 4–30 seconds.
Thirty seconds is available continuity capacity whenever one causal arc can safely use it. It is not
a target. Nothing is padded to reach 30 seconds, nothing is rushed to fit inside it, and complexity
is never added merely because time remains.

## 30-Second Packing Rule

Before creating a new provider request, the Director must test whether the next consecutive stages
can remain in the current request. Setup, development, escalation, reaction, and payoff may use
motivated internal camera cuts while remaining one Seedance generation. A provider boundary is
allowed only for:

- the scene ending;
- a combined natural duration above 30 seconds;
- a location or time change;
- a reference-regime change;
- a deliberate continuity reset;
- a dramatic editorial break that is stronger than an internal cut;
- complexity protection where combining the action would materially increase drift risk.

Every boundary carries a typed reason and observable explanation. If two adjacent units total 30
seconds or less, a claimed duration-limit split is invalid. Dramatic and complexity splits within
that window require an explicit adversarial Showrunner judgement. The approved package stores a
deterministic packing audit, and production handover recomputes it before accepting the storyboard.

The Director-facing headline is `story beats -> production units`, followed by exact natural durations,
planned runtime, protected joins, and any short joins requiring review. Story beats are directing
evidence; they are never presented as one-render-per-beat instructions.

### Complexity ceiling

Duration capacity is not complexity capacity. The standard production unit contains no more than
three causal stages and three motivated camera views. Each stage has one primary visible change and
one observable end state. A scene under 30 seconds that needs more than this must be simplified
without losing script truth or split at a story-led `complexity_protection` boundary. The packing
audit blocks an overfilled unit before keyframe generation, provider upload or spend.

## Storyboard Contract

Each production unit must lock:

- one exact `targetDurationSec` from 4 through 30 seconds;
- one or more consecutive script beat IDs, with no loss, duplication, or reordering;
- 1–3 causal stages, each with one primary event and an observable end state;
- 1–3 motivated internal camera views, each with a story purpose and cut reason;
- exact dialogue occurrences in script order;
- an opening state and a final handoff state for continuity.

Stages are the default control language for Seedance 2.5. Use timestamp ranges only when a critical
handoff, entrance, exit, transition, dialogue cue, or Director-locked beat needs timing protection.
If timestamps are used, they must be consecutive and non-overlapping, and they must cover the
approved timed span without gaps. Split only for story grammar, a location or time change, a
reference-set change, a continuity reset, complexity protection, or because the natural action
exceeds 30 seconds.

## Reference Contract

Every reference is named and role-bound. The prompt states what to inherit and what to exclude.
Keyframe creation and animation both show and preserve their approved character, location, prop,
style, and continuity references. Approved voice audio is the sole dialogue, performance, and timing
master when dialogue exists.

One approved opening frame is the default temporal anchor. A last-frame or intermediate keyframe is
added only for a Director-approved first/last-frame or multi-keyframe task. The previous unit's
approved final frame provides the continuity chain into the next unit.

## Animation Contract

Animation Direction must return the exact approved duration, beat ownership, stage order, internal
view count, performance arc, camera behaviour, audio contract, consistency contract, and final
landing image. It may enrich observable direction but cannot rewrite script events, dialogue,
duration, references, or continuity state.

## Execution Contract

The production target is Seedance 2.5 through fal's documented
`bytedance/seedance-2.5/reference-to-video` endpoint. Seedance 2.0 routes are retired and cannot be
selected as fallbacks. The executable provider registry, rather than this prose document, remains
the authority for the live schema and limits. A render may fire only after all of the following are
true:

- fal authentication and the exact endpoint are available;
- the request fits the verified 4-30 second, reference, resolution, and audio contract;
- current pricing is configured and sealed into the spend disclosure;
- the disclosure names the same provider, model, duration, prompt, references, and audio;
- all creative and human approval lineage is current;
- the human explicitly approves the disclosed maximum spend.

The adapter translates Studio reference labels to fal upload-order tags such as `@Image1` and
`@Audio1` before submission. Any unsupported field, changed file hash, stale approval, missing audio,
or provider mismatch fails before upload, task creation, or spend.

## Production Evidence

Dreamina's current Seedance 2.5 production guidance describes narrative requests as staged
progression with explicit reference roles, one primary visible change per stage, observable end
states, and optional timing where precision matters. The Studio therefore removes avoidable joins
when continuity benefits, but keeps a named complexity-protection boundary when one request would
become less controllable.

- https://docs.byteplus.com/en/docs/ModelArk/2607689
- https://bytedance.larkoffice.com/docx/A88jd0B47oAd8zxWp5ycZFMfnxh
- local prompt skill: `.agents/skills/sd25-pe`

The fal Seedance 2.5 API documentation now provides the exact endpoint, request schema, 4-30 second
duration range, multimodal reference limits and 720p price used by the Studio. BytePlus remains a
separate disabled adapter until its account access, limits, terms and pricing are independently
qualified. Dreamina product availability alone is never treated as API proof.

- https://fal.ai/models/bytedance/seedance-2.5/reference-to-video/api

## Human Loop

The visible Studio flow is `Stage -> Take -> Master`. Stage contains the quietly prepared Story &
Direction, World Build, Voice & Timing and opening-keyframe work; the human decision is whether the
visible stage is right. Take contains animation and Director Review; the human decision is accept,
iterate or reject. Master contains conform, post-production QC and final approval. Internal contracts,
references, prompts and evidence remain inspectable but are not separate creative approval gates.

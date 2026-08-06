# Seedance 2.5 Production Contract

**Status:** authoring contract active; paid execution blocked pending BytePlus qualification  
**Target model:** `dreamina-seedance-2-5-260628`  
**Provider:** BytePlus ModelArk  
**Effective:** 2026-08-04

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

A unit longer than 15 seconds must use consecutive timestamp stages covering second 0 through the
exact approved duration without gaps or overlaps. Split only for story grammar, a location or time
change, a reference-set change, a continuity reset, or because the natural action exceeds 30 seconds.

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

The only target is Seedance 2.5 through the BytePlus asynchronous content-generation API. Seedance
2.0 routes are retired and cannot be selected as fallbacks. A render may fire only after all of the
following are true:

- the exact BytePlus model is activated for the account;
- model-specific duration, reference, resolution, and audio limits are verified;
- pricing and billing cadence are configured;
- the sealed spend disclosure names the same provider, model, duration, and references;
- all creative and human approval lineage is current.

Until then the system fails before upload, task creation, or spend. Storyboarding, prompt compilation,
reference review, and zero-spend preflight continue to work.

## Production Evidence

Dreamina's current Seedance 2.5 production guidance describes one 30-second narrative request as a
compact shot list with beat timing, camera direction, references, and a beginning-to-payoff arc. It
also advises simplifying scene complexity when drift appears. The Studio therefore removes avoidable
joins when continuity benefits, but keeps a named complexity-protection boundary when one request
would become less controllable.

- https://dreamina.capcut.com/seedance/seedance-2-5-prompt
- https://dreamina.capcut.com/seedance/seedance-2-5-best-settings
- https://dreamina.capcut.com/seedance/how-to-use-seedance-2-5

The public BytePlus ModelArk API documentation still lists Seedance 2.0 rather than the target 2.5
model ID. Dreamina product availability is not proof that this BytePlus account can call the API.
Paid execution therefore remains blocked until the exact route is activated and qualified.

## Human Loop

The visible Studio flow is `Stage -> Take -> Master`. Stage contains the quietly prepared Story &
Direction, World Build, Voice & Timing and opening-keyframe work; the human decision is whether the
visible stage is right. Take contains animation and Director Review; the human decision is accept,
iterate or reject. Master contains conform, post-production QC and final approval. Internal contracts,
references, prompts and evidence remain inspectable but are not separate creative approval gates.

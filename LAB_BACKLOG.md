# Lab Backlog — competitive doctrine, queued for adoption between scenes

Reviewed 2026-07-03 (Julian). The change freeze holds — nothing here is implemented now. Logged in priority order so
the next between-scenes window works it in order, not ad hoc. Each item needs its own ruling before it enters code;
none of these are pre-approved by being on this list.

## 1. The 720p draft ladder

Render exploratory seeds at DRAFT resolution; only the signed winner re-renders at full delivery resolution.

**FLAGGED FOR JULIAN'S RULING**: whether this enters NOW, as a cost-control measure exempt from the freeze (distinct
from a creative/spec change), or waits with the rest of this list. Not actioned either way until he rules.

## 2. Negatives vs. positive constraints — an A/B test

Vendor guidance says Seedance ignores traditional negative prompts. Proposed test: convert the NEGATIVES section to
positive locks (state what must be true, not what must not happen) on ONE already-crowned beat, and compare against
the current negatives-based version before deciding whether to change the doctrine for every beat.

## 3. @Video motion and camera references for stubborn gags

For beats where the still-image + text approach keeps missing the intended motion (e.g. a specific physical
performance a static keyframe can't fully specify), supply an actual VIDEO reference for motion/camera guidance
instead of relying on prose alone.

## 4. Camera end-state brace phrases, paired with the ENDING FRAME doctrine

A prompt technique naming the camera's END state explicitly, written to pair with (reinforce, not duplicate) the
ENDING FRAME doctrine (CLAUDE.md rule 15) — tightening the coherence between what the clip's camera should end on
and what the composed ending-frame deliverable actually shows.

## 5. A codified fallback template tier for the retake room

A structured, reusable fallback prompt template for Gate 4 (Retakes) — for when a beat's primary approach keeps
failing QA or missing the intended performance after repeated regeneration (see: 1.B3's keyframe needing six
regenerations to clear ANATOMY_DEFECT/ACTION_STATE_MISMATCH, 2026-07-03) and a simpler, more constrained fallback
would serve better than continuing to regenerate the same prompt shape.

## Chain doctrine note (not a backlog item — a pending correction to CLAUDE.md rule 15)

Vendor guidance confirms: an ENDING FRAME is a render-time FIRST-FRAME CARRY (something Seedance itself consumes to
seed a render's continuity), never a generation ANCHOR for a separate keyframe-composition step. This supports
reverting Gate 2's current behavior (built same-day, 2026-07-02: `cb_scene.chain_source_for` chaining a
continuation beat's KEYFRAME generation off the previous beat's ending frame) back to chaining keyframe generation
off the previous beat's OPENING keyframe, with the ending frame reserved for its correct role at Gate 3 (render
time) instead.

**Per "no spec changes now": this revert is queued, not applied.** `cb_scene.py` is UNCHANGED — the in-flight
1.B3→1.B4→1.B5 fire (started before this note) continues exactly as built, so as not to create inconsistency
between beats already chained under the current behavior and beats chained after a revert mid-fire. CLAUDE.md rule
15 itself is not rewritten yet, to avoid describing a behavior the code doesn't have; this file is the record until
the revert actually lands.

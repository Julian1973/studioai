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

## 3. @Video motion and camera references for stubborn gags / direct continuations

For beats where the still-image + text approach keeps missing the intended motion (e.g. a specific physical
performance a static keyframe can't fully specify), supply an actual VIDEO reference for motion/camera guidance
instead of relying on prose alone. Reconfirmed in Julian's consolidated doctrine sync (2026-07-03, item NINE) with
a second use case: a direct-continuation relay beat could reference the PREVIOUS beat's actual clip (not just its
harvested still frame) for motion/camera continuity, not only a stubborn-gag fallback.

## 4. Camera end-state brace phrases, paired with the ENDING FRAME doctrine

A prompt technique naming the camera's END state explicitly, written to pair with (reinforce, not duplicate) the
ENDING FRAME doctrine (CLAUDE.md rule 15) — tightening the coherence between what the clip's camera should end on
and what the composed ending-frame deliverable actually shows.

## 5. A codified fallback template tier for the retake room

A structured, reusable fallback prompt template for Gate 4 (Retakes) — for when a beat's primary approach keeps
failing QA or missing the intended performance after repeated regeneration (see: 1.B3's keyframe needing six
regenerations to clear ANATOMY_DEFECT/ACTION_STATE_MISMATCH, 2026-07-03) and a simpler, more constrained fallback
would serve better than continuing to regenerate the same prompt shape.

## Chain doctrine note — RESOLVED 2026-07-03 via the Relay Chain (CLAUDE.md rule 21)

Vendor guidance confirms: an ENDING FRAME is a render-time FIRST-FRAME CARRY (something Seedance itself consumes to
seed a render's continuity), never a generation ANCHOR for a separate keyframe-composition step. This was logged as
a queued revert of Gate 2's `cb_scene.chain_source_for` (which chained a continuation beat's KEYFRAME generation off
the previous beat's ending frame) back to opening-frame chaining.

**Resolution, same day, once Julian's Relay Chain ruling landed:** rather than revert to opening-frame chaining,
the correction is applied more directly — a relay/continuation beat now has NO separate keyframe-generation step at
all. Its harvested settle frame (the sharpest frame in the previous beat's signed clip's settle window, not
necessarily the literal last frame) is fed straight into Seedance's ref2vid as `@图1`, exactly the render-time
first-frame-carry role the vendor guidance described. `cb_scene.chain_source_for`/the opening-frame-chaining path
stays as the fallback for the FIRST beat in a relay (or any beat with no signed predecessor to open from) — see
`cb_scene.harvest_settle_frame` and CLAUDE.md rule 21.

## 6. Julian's action-prose style as the Director's T8 worked example — APPLIED 2026-07-03

**No longer a backlog item — Julian ordered this directly (his "new gold standard prompt" message, 2026-07-03),
superseding the freeze for this one item.** Applied to `cb_director.py`'s `_mind()` system prompt as "WORKED EXAMPLE
TWO — T8," alongside the existing T1 (1.B1) example, under the standing instruction: "author every beat's action at
this energy: vivid verbs, escalation inside the sentence, the cut placed for the laugh." His gold-standard beat is
filed verbatim as the worked-example text, with a summary of what to copy into every beat (speed from the first
shot, escalating clauses in one breath, a named camera end-state, an explicit hold instruction for a deadpan
character, an ambience-resumes settle-button on the close). The same prompt's structural additions (camera
end-states, a written invariant "rule" field, expression bindings, the ambience-resumes button, a constraints
line) were also applied to `cb_segprompt.py`'s `emit_json_v3` the same day — see the golden set
(`engine/goldens/segprompt__1.B2.txt`, `segprompt__1.B5.txt`) for the resulting shipped shape.

## 7. Julian's style line as the show style line — APPLIED 2026-07-03

**No longer a backlog item — Julian confirmed it directly** (Fable's code review sync, item THREE). Replaced the
show profile's style law: `shows/crystal-bears/laws/style.txt` (declared in `profile.json`'s `laws.style` key) now
holds "Premium 3D animated feature film aesthetic for children aged 4 to 8, bright hyper saturated colours, warm
golden hour sunlight with volumetric rays, glowing magical particles, lighthearted highly expressive slapstick
comedy". `cb_segprompt.py`'s `_v3_style()` now reads this file at import time (mirroring exactly how `WING_LAW`
loads from `laws/wing_law.txt`, inline-string fallback if the file is ever missing) instead of returning a
hardcoded string — every beat's shipped prompt (both emitters) carries the confirmed line now, not a candidate.

## 8. A scripted distance envelope baked into @Audio1

**FLAGGED, queued for adoption between scenes** (Julian's Audio Doctrine ruling, 2026-07-03, item 2). Since the
Director's own shots already say where a character is (far and chasing in shot 1, close and locked in shot 3),
`cb_voice` could bake a distance envelope directly into the @Audio1 track it builds — quiet and airy at the start
of a chase, swelling as the camera catches up — so Seedance receives a voice that already breathes with the
geography, rather than relying solely on a Gate-5 mix-time perspective ride after the fact. Lip sync is phoneme-
driven, not volume-driven, so sync holds either way. **Not built now** — the freeze holds; Gate 5's mix-time
perspective ride (see the Studio Bible's Gate 5 section) covers the signed clips in the meantime.

## Audio Doctrine — applied same day (2026-07-03, Julian)

Two of the four rulings are code/doc changes, done today: (1) both `cb_segprompt.py` emitters' audio law text now
states that ALL vocal sounds — hums, sing-songs, exclamations, not just spoken lines — are V3 performances inside
@Audio1, Seedance never generates a voice-like sound of any kind; (2) the Studio Bible's Gate 5 section documents
perspective-rides-as-mix-law and SFX-sweetening-as-declared-doctrine (see `CRYSTAL_BEARS_STUDIO_BIBLE.md`). Neither
of those two touches a render — they're mix-time practice and law-text, not generation code. Item 8 above (the
distance envelope) is the one piece actually queued, not applied.

## 9. Revisit the prose/JSON fork criterion after Scene 1

**FLAGGED, queued for after Scene 1** (Julian's consolidated doctrine sync, 2026-07-03, item SIX). The fork
currently routes on raw distinct-speaker count (0-1 -> prose, 2+ -> JSON). Once Scene 1's seeds are judged,
revisit whether the right criterion is actually "is this an EXCHANGE beat" (dialogue volleying between
characters) rather than raw speaker count — judged by where the losing seeds cluster (does prose lose more often
on beats that happen to have 2 speakers but only one really carries the scene, etc.). Not actioned now.

## NB2 chain refresh — REJECTED as a routine step (2026-07-03, Julian's consolidated doctrine sync, item NINE)

Proposed idea: re-mint a harvested settle frame through NB2 whenever QA flags its sharpness below a threshold,
with turnarounds enforced to hold identity. **Explicitly rejected as a routine mechanism** — it compounds
identity drift against the pixel-carry ruling (the whole point of harvesting is that the relay continues off the
ACTUAL rendered pixels, not a re-imagined approximation; running a harvested frame back through a generative
re-mint step reintroduces exactly the re-imagining the relay was built to remove). Logged as a rejected idea, not
a queued one — the answer to a soft harvest is a better harvest (a wider sample, more candidate frames) or a
retake of the underlying clip, never a generative refresh of the frame itself.

## Canon-correction check — 1.B2 hybrid prompt (2026-07-03)

Verified against the fired JSON before it shipped; all four passed clean, no edits needed to Julian's text (fired
verbatim per his instruction):

- **Hearts and crystals, not fairy dust** — `environment` reads "floating hearts and cut amethyst crystals hovering
  in the air," matching the Crystal world rule; no fairy-dust language present.
- **Goatee handlebar per gag_locks** — shot 2's action names "goatee handlebar moustache," satisfying
  `S1_GAG_02_OFFICIAL_MOUSTACHE_NUTS`'s `required_words: ["goatee","handlebar"]` in
  `shows/crystal-bears/canon/gag_locks.json`; no hit against either `prohibited_patterns` (`full beard`,
  `fuzzy yellow moustache`).
- **Identity text never ships** — `references` describes each bee only by role/position ("the larger eager bee,
  frame left" / "the smaller deadpan bee, frame right") plus "copy exactly, no redesign" — no physical-appearance
  description (no fur colour, glasses, markings) anywhere in the prompt, matching CLAUDE.md rule 5.
  Character names appear only inside the `dialogue.line` text (destined for @Audio1), never in `action`/`camera`.
- **References carry it** — `image_2`/`image_3` are pointed at Fuzzby's and Zenny's locked turnarounds
  (`cb-seed/assets/final_turnarounds/CB_Fuzzby.jpeg`, `CB_Zenny.jpeg`) with "no redesign," so identity comes from
  the reference images, not the text.

# Lab Backlog — competitive doctrine, queued for adoption between scenes

Reviewed 2026-07-03 (Julian). The change freeze holds — nothing here is implemented now. Logged in priority order so
the next between-scenes window works it in order, not ad hoc. Each item needs its own ruling before it enters code;
none of these are pre-approved by being on this list.

## 0. THE NAMED POST-SCENE-1 BUILD — Stage 5/6 infrastructure (2026-07-06, Julian's ruling)

**BUILT 2026-07-06** (items 1-3), same day as `GATE3_ANIMATION_DOCTRINE.md` itself, on Julian's own explicit
instruction ("implement the doctrine exactly... approval recording on takes with resume-by-approval-status").
The INFRASTRUCTURE FREEZE (CLAUDE.md rule 41) that deferred this is lifted for this specific build — it was a
direct ask, not a sweep found on the way to something else.

1. **DONE** — `cb_beats.record_approval(episode, code, slug, approved, correction=None, scene_num=None)` writes
   a per-take sidecar (`media/<ep>_<code>_<slug>.approval.json`, `{"approved": bool, "correction": str|None,
   "recorded_at": iso}`) recording Julian's felt-intent verdict as data — no `locked.json` schema change needed,
   a simple sidecar was enough and matches this codebase's existing `.qa.json`/`.join.json` convention exactly.
2. **DONE** — rejection archiving: `record_approval(approved=False, ...)` immediately moves the clip + its
   `.qa.json`/`.join.json`/`_settle.png`/`_remint.png`/approval sidecar to
   `media/archive/<episode>_scene<N>_rejected/<code>_<timestamp>/`, with a `.REJECTED.json` marker naming the
   one-sentence correction — never deleted, never anchoring/sourcing/resuming anything again. The beat's own
   normal path is clean afterward (status reverts to "unrendered"), ready for the corrected re-fire.
3. **DONE** — `cb_beats.beat_approval_status(episode, code, slug)` returns `"unrendered"|"pending"|"approved"`
   by reading the sidecar, never trusting a clip's mere presence. `cb_replicator.walk_scene` now checks this at
   both its resume points (the opener and the relay loop) and, critically, **halts for Julian's Eye after every
   single fire** rather than auto-advancing through green machine gates — "nothing self-advances past his eye"
   is now literal, not just a stated intention. Verified with a scripted lifecycle test (unrendered → pending →
   rejected+archived → unrendered → pending → approved) — every transition landed exactly as designed.
4. **STILL OUTSTANDING** — Stage 6's timecode-retake subsystem (`cb_post.assemble_review_cut`,
   `cb_post.retake_at_timecode`). Not part of this build; genuinely waits on real footage to test against.

Also fixed the same day, found by the doctrine audit that motivated this build: **@Video1 was never actually
trimmed to its documented "final ~3 seconds"** — the whole predecessor clip was being uploaded as the video
reference. `cb_beats._trim_video_tail(clip_path, seconds=3.0)` (ffmpeg `-sseof`, stream-copied, falls back to
the untrimmed clip on any failure) now wraps both call sites (`run`'s relay video-reference assembly,
`fire_next_beat`'s dry-run preview). Verified against a real archived clip.

## 1. The 720p draft ladder

Render exploratory seeds at DRAFT resolution; only the signed winner re-renders at full delivery resolution.

**FLAGGED FOR JULIAN'S RULING**: whether this enters NOW, as a cost-control measure exempt from the freeze (distinct
from a creative/spec change), or waits with the rest of this list. Not actioned either way until he rules.

## 2. Negatives vs. positive constraints — an A/B test

Vendor guidance says Seedance ignores traditional negative prompts. Proposed test: convert the NEGATIVES section to
positive locks (state what must be true, not what must not happen) on ONE already-crowned beat, and compare against
the current negatives-based version before deciding whether to change the doctrine for every beat.

## 3. @Video motion and camera references for stubborn gags / direct continuations — MOOT, ALREADY TRIED AND KILLED

**SUPERSEDED (found stale in the 2026-07-08 software-wide sign-off audit):** this exact mechanism was built —
CLAUDE.md rule 26, THE FIFTH ANCHOR, @Video1 (2026-07-04) — fired against real 1.B2 footage, and then explicitly
retired by Julian on render evidence (rule 51, 2026-07-07: "the video I don't like it either, I think it confuses
things") — "REMOVED entirely, not narrowed." `cb_qa.py`/`cb_golden.py` now actively BLOCK if @Video1 ever
reappears in a shipped prompt. Do not re-propose or re-build this without a fresh ruling from Julian.

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

## 9. Revisit the prose/JSON fork criterion after Scene 1 — MOOT, THE FORK ITSELF NO LONGER EXISTS

**SUPERSEDED (found stale in the 2026-07-08 software-wide sign-off audit):** `emit_prose_v3`/`emit_json_v3` (the
v3 prose/JSON fork this item is about) were deleted outright in THE DEFINITIVE BUILD purge (CLAUDE.md rule 40),
and the v4/v5 engines that replaced v3 never had a prose/JSON fork at all — v5 is one unified text compiler for
every beat regardless of speaker count. There is no criterion left to revisit; nothing to action.

**FLAGGED, queued for after Scene 1** (Julian's consolidated doctrine sync, 2026-07-03, item SIX). The fork
currently routes on raw distinct-speaker count (0-1 -> prose, 2+ -> JSON). Once Scene 1's seeds are judged,
revisit whether the right criterion is actually "is this an EXCHANGE beat" (dialogue volleying between
characters) rather than raw speaker count — judged by where the losing seeds cluster (does prose lose more often
on beats that happen to have 2 speakers but only one really carries the scene, etc.). Not actioned now.

## NB2 chain refresh / RE-MINT — REJECTED 2026-07-03, then SUPERSEDED BY THE DIRECTOR the same day

Original proposal (consolidated doctrine sync, item NINE): re-mint a harvested settle frame through NB2 whenever
QA flags its sharpness below a threshold, with turnarounds enforced to hold identity. **Explicitly rejected as a
routine mechanism** at the time — reasoned that it compounds identity drift against the pixel-carry ruling (the
relay continues off ACTUAL rendered pixels, not a re-imagined approximation; running a harvested frame back
through a generative step reintroduces exactly the re-imagining the relay was built to remove).

**Superseded the same day, by Julian's explicit ruling as director**: "The prior lab ruling is superseded by the
director: re-mint is now every link, not QA triggered." Re-mint is now STANDARD for every relay link —
`cb_scene.remint_settle_frame`, using a LOCKED, deliberately minimal restoration-only prompt
(`cb_prompts.build_remint_prompt`: same everything, artifacts and blur removed ONLY, turnarounds attached purely
to hold identity while cleaning) — narrower in scope than the originally-rejected "chain refresh" idea (which had
no locked prompt and no drift check). Guarded by a new hard BLOCK, `cb_qa.check_remint`, comparing the re-mint
against the harvest (position/state) and the turnarounds (identity), and by a human approval gate —
`cb_beats.fire_next_beat` prepares the cleaned anchor and STOPS; it only fires the next beat once called again
with `approved=True`. This record stays as the "why we nearly didn't do this" reasoning, in case the drift risk
the original rejection named ever actually shows up in the check's verdicts.

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

## Golden harness gap — relay-mode prompts have never been golden-tested (2026-07-04)

Found while diagnosing the "re-mint reads as the end frame, not the first" bug (fixed same day in
`cb_segprompt.py` — see the OPENING FRAME LOCK fix). `cb_golden.py`'s `current_snapshot()` calls
`cb_segprompt.shipped_prompt(b, sc)` with no `relay` argument at all, so it always exercises `relay=False` — the
non-relay fallback path — for every one of the 5 Scene-1 beats, even though 1.B2-1.B5 actually ship in
`relay=True` mode once the relay chain reaches them. The golden set showing "ZERO DIFFS" has therefore never
once proven anything about the relay-mode prompt text; the OPENING FRAME LOCK fix was verified by hand (a direct
`shipped_prompt(b, sc, relay=True)` call, diffed by eye, shown to Julian) precisely because the harness couldn't
do it.

**Why this wasn't just fixed on the spot**: making `current_snapshot()` call `cb_scene.relay_source_for()` to
compute the real relay status would make the golden baseline depend on live `engine/media/` state — whether
1.B1's remint file exists on disk at capture time, which changes day to day as beats get re-rendered/re-picked.
A golden snapshot needs to be deterministic; wiring in a live filesystem/harvest dependency risks a "golden" that
silently changes meaning between two runs on the same code, which defeats the harness's whole purpose.

**What a real fix needs**: either (a) a synthetic/fixture relay state the golden harness can hold constant
independent of `engine/media/`'s live contents (e.g. a fake remint path that's asserted to exist, never actually
harvested), so `current_snapshot()` can safely call `shipped_prompt(b, sc, relay=True)` for beats 2-5 without
touching real render output, or (b) a second, explicit set of golden entries (`segprompt_relay__1.B2` etc.)
captured and diffed alongside the existing `relay=False` ones, so both shipping modes are covered and a
prompt-touching change can't silently break one while the tool only reports the other clean. Needs a design
decision before implementing — flagging here rather than guessing.

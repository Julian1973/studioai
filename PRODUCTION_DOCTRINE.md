# THE PRODUCTION DOCTRINE — CRYSTAL BEARS, THE DEFINITIVE BUILD

**Locked 2026-07-06, Julian's consolidation ruling: "consolidate, purge, prove."** This document supersedes
`REPLICATOR.md` and the prior (2026-07-05) draft of this file, both retired the same day this was written —
this is now the SOLE source of truth for the pipeline's shape. Full dated history of how each piece was
arrived at still lives in `CLAUDE.md` (rules 1-39); this page states what is true NOW, not why. If code and
this page ever disagree, that is a bug — fix the disagreement the day it is found (rule 7).

## The hierarchy

**Episode → Scene → Beat.** A scene is a bubble: three locked constants (scene plate, ambient bed, style law)
held verbatim across every beat inside it. A beat is one gag arc, 15 seconds — 13s action + 2s settle. A
scene boundary is a full reset: new plate, new bed, a fresh anchor keyframe, relay depth back to zero.
**Ambient bed note (the v5 engine, 2026-07-06):** the scene plate and style law are still live-enforced in
every shipped prompt (rules 39 and the style block); the ambient bed's "word-for-word identical every clip"
guarantee is NOT currently enforced in the shipped text — v5's literal five-block spec has no ambience slot.
Flagged to Julian in the v5 build report, not silently dropped; this line states the bubble's ORIGINAL three
constants as designed, not a claim that all three are live in the prompt today.

## Stage 0 — Script-in

The script is the SOLE story source. Verbatim law: nothing downstream invents story or rewrites a line.
Dialogue is locked including its authored punctuation (a comma, an ellipsis, a case choice) — once Julian
rules a line's exact text, that text is what every V3 take is generated from; changing it is a fresh ruling,
not a typo fix. `cb_script.py` parses the signed script deterministically. TWO mechanisms enforce the lock, at two different
times (corrected 2026-07-07 — this line previously mis-attributed the check to `cb_qa`, which has no such
function): `cb_director.enforce_verbatim` snaps every beat's dialogue to the exact script line ONCE, at Gate-1
authoring time, inside `direct()`; `cb_preflight.check_scene_dialogue_verbatim` is the STANDING, re-runnable
hard BLOCK (a proper `difflib` alignment against `cb_script.dialogue_lines`, not a positional zip) that
re-checks the SAME ground truth at any later gate-arming point — the gap that let a hand-edited package drift
from the locked script go undetected before this rule was added (CLAUDE.md rule 48).

## Stage 1 — The Director pass (script → beat package) → GATE 1

`cb_director.py` breaks the script into scenes and beats. Scenes are bubbles (plate + ambient bed + style law,
locked verbatim per scene, from Stage 0 onward). Beats are single 15-second gag arcs (13s action + 2s settle,
`cb_segprompt.HANDLE_TOTAL`/`HANDLE_ACTION`/`HANDLE_SETTLE`) carrying BOTH manifests complete before Gate 1
can be signed — see `MANIFEST.md` for the full field list, `cb_preflight.py` for the enforcement:

- **Technical contract**: `endState`, `endStateStill`, `carryMarks`, `junctionType` (cut-default —
  `intentional_next_shot` unless the director's own cut explicitly declares `seamless_continuation`), a
  timing map whose `pauseHold` names the beat's ONE featured hold and states it ≤1.5s, `opensOn` (the
  Coverage Law's bridge — who the camera opens on and their mid-motion state), `actingContrast`, and speaker
  order matching the cuts' actual dialogue sequence.
- **Creative contract**: `humourLayer` (1-4), `kidRead`, `adultRead`, `want`/`need`, `emotionMechanic`, and
  the featured hold explicitly designated (the SAME `pauseHold` field, naming which moment in the beat earns
  the beat's one permitted hold — not necessarily the final button; a beat may hold on its tonal pivot
  instead, director's call).

Blanks BLOCK. No fallback text exists anywhere in the authoring path — `cb_qa.ManifestFieldMissing` is raised
by every emitter function that would otherwise have invented placeholder prose (rule 37's fallback sweep).

**GATE 1**: the storyboard exports as one document for Julian's own review outside the Studio (the Gate-1
external review rule); his signature — `cb_pipeline.approve("1", scene)` — follows that review, every scene,
every time. `manifest_ok()` refuses the signature while any BLOCK-kind gap remains in scope.

## Stage 2 — World (Gate 2a)

The scene plate is built, then checked (`cb_qa.check_plate`) against the Crystal World Rule — natural,
organic crystals, never cut, arranged or self-glowing at rest. Character turnarounds are verified against
canon (`config/characters.json`'s bible). The scene's ambient bed is locked — word-for-word identical across
every beat in the scene from here on (the Scene Bubble Law). **Gate 2a**: Julian signs; the signed plate
becomes the scene's master and is stored in the reusable locations library (`cb_pipeline._lock_plate_as_master`).

## Stage 3 — Voices

One directed V3 take per beat, generated from the LOCKED dialogue text only (Stage 0) — never a reworded or
paraphrased line. Fired INTO generation as `@Audio1`; Seedance generates no voice-like sound of its own, and
there is no post-generation voice swap, ever, even in a hypothetical two-step fallback (rule 29, absolute —
`cb_post` has no swap function by design). The Voice Bible registers (per-character cadence, stability,
delivery direction) drive `cb_voice.build_dialogue_track`, itself driven by the Director's Pass so the
performance matches the picture. Julian's ear approves the one take, or names the single correction for the
one permitted re-fire — the same one-render economy every other artifact in this pipeline gets.

## Stage 4 — Keyframes (Gate 2b)

ONE generated anchor keyframe per SCENE — never per beat; a relay beat never gets its own — 2K, centre-safe,
composited from the signed plate + character turnarounds (`cb_scene.keyframe_for`). Per-character
action-state QA (`ACTION_STATE_MISMATCH`) checks concrete, literally-checkable criteria (wing symmetry, body
lean), never a subjective "does this look dynamic" call (rule 17). **Gate 2b**: Julian signs.

## Stage 5 — Animation, the walk (Gate 3)

**SUPERSEDED 2026-07-06 — `GATE3_ANIMATION_DOCTRINE.md` (repo root) is now the Version of Record for Gate 3's
workflow, prompt shape, and Fidelity Law sources; where this section and that document disagree, the
document wins (its own Change Control, §5). This section is kept as a summary/cross-reference, not a second
authority — fix any drift the day it's found (rule 7).**

### The Scene-Opener Stack Law

A scene's FIRST beat fires with exactly FOUR visual references — the signed keyframe (Stage 4), each cast
member's turnaround, and the scene plate — plus `@Audio1`. No harvest, no re-mint on any opener: there is no
predecessor to harvest a settle frame from. This is now CODE-ENFORCED, not merely conventional:
`cb_preflight.check_opener_stack` is a per-beat BLOCK for a scene's first beat if its actual reference plan
would include a harvest or a re-mint — the manifest refuses to arm Gate 3 on a scene whose opener stack is
wrong, the same choke-point every other gate check uses.

### Every subsequent beat

Opens off the raw harvested settle frame from the **approved** predecessor take — never merely the predecessor
with a clip file on disk; a rejected take is dead to all resume and harvest logic (see "Approval, not file
existence," below). State reference is cut-default (`intentional_next_shot`): identity, carryMarks, lighting,
position carry forward; camera is free within the coverage leash (a new angle close to the predecessor's,
motivated by eyeline or motion, never a relocation or a fresh establishing wide — spatial-adjacency gated by
the join-check's COVERAGE tier). Turnarounds and the scene plate are present on every beat, opener or not
(rule 39 — the plate is a standing anchor, never relay-only).

**CORRECTED 2026-07-08 (software-wide audit):** both paragraphs above used to also name `@Video1` — a fifth
reference (the predecessor's own clip, for motion energy) that existed briefly (rule 26, added 2026-07-04)
and was RETIRED 2026-07-07 (rule 51 — Julian, watching 1.B2's actual footage: "the video I don't like it
either, I think it confuses things"). The reference stack is a fixed four now, opener or relay, with no
`@Video1` anywhere — this section's own prose had not been swept for that retirement until this audit found
it reading as if `@Video1` were still live.

### The v5 engine is the sole prompt author

No hand-authored prompt text, anywhere, ever. `cb_segprompt.emit_v5`/`shipped_prompt` is the only path from
beat data to shipped prompt (superseding v4 the same way v4 superseded v3, Julian's ruling 2026-07-06 — "THE
PERMANENT PROMPT COMPILER, superseding all prior emitter modes"); v4/v3/v2/v1 and every hand-edit escape
hatch are deleted, not merely deprecated (the Purge, below) — a builder that returns empty now surfaces as a
hard `ManifestFieldMissing`-class refusal, not a silent degrade to a weaker builder. Five mechanical blocks,
zero per-beat authoring: style (verbatim) / references (one line each, the same opener-relay-junction stack
logic v4 used) / actingDNA (per cast member, `characters.json`'s new `bible.actingDNA` field) / beat story
(`storyBeat` as the spine, vocal order, ending on `endState`'s settle, speed adjectives mechanically stripped)
/ tech close (duration/camera-lock law + the negative line — the standing six plus two new always-on items,
"no 2D animation style" and "no flat, static-feeling rendering"). A hard word-count BLOCK is enforced in
`cb_preflight.py` (`WORD_BUDGET_BLOCK`, 650 as of 2026-07-07 rule 52; `WORD_BUDGET_TARGET`, 400, is the
target, not a gate); every emit prints its own word count. NOTE: this paragraph describes an early v5 draft
(`bible.actingDNA`, a flattened `storyBeat` spine) both since superseded — see GATE3_ANIMATION_DOCTRINE.md
§2/§3 for the current, authoritative shape (Stage 5's own cross-reference, above).

### The one-render economy

One render per beat, standard tier. One automatic re-fire on a red gate. Second fail: a HARD STOP naming the
layer at fault (keyframe / brief / reference / take). Never a third roll. Machine gates per beat: Clip QA
(`cb_qa.check_clip`), carryMarks-scoped state continuity, spatial adjacency (Coverage), settle distinctiveness,
anti-hold. These are the MACHINE half of the loop — they stop there, deliberately.

### Approval, not file existence

Julian's felt-intent verdict per beat — does it flow, is it funny, does the four-year-old watch it again — is
the RESERVED VERDICT no machine check approximates. It is now recorded as a data field, not left implicit in
"a clip file happens to exist": `locked.json`'s per-beat lock gains an `approval` key —
`{"status": "approved"|"rejected"|"pending", "note": "..."}` — written by `cb_pipeline.approve_beat_take`.
Only an `approved` take may be harvested (`cb_scene.harvest_settle_frame`) — the still-frame anchor, the only
one that exists now that `@Video1` is retired (rule 51); a `rejected` take's clip is moved to `media/rejected/`
with a `.REJECTED.json` sidecar (recording why, and what
the one changed variable was on the re-fire that superseded it) and is invisible to every resume/harvest path
— `walk_scene` treats a beat with a `rejected`-only history as `pending`, not done, and re-fires it. **This is
the resume key**: `walk_scene` resumes on approval status read from `locked.json`, never on whether a clip
file happens to exist on disk — a clip can exist and still be correctly treated as not-done if it was never
approved.

## Stage 6 — Gate 4: retakes by timecode

The walked scene assembles into a review cut with burnt-in timecode (`cb_post.assemble_review_cut`, an
ffmpeg `drawtext` overlay on the hard-cut assembly, never on the delivery master). Julian names corrections
by timecode, not by beat code or file name. `cb_post.retake_at_timecode(scene, timecode, variable, value)`
maps timecode → beat → cut (via each beat's own duration and position in the scene's running order — a
beat's actual rendered clip is always `HANDLE_TOTAL` seconds, so the mapping is arithmetic, not guesswork),
applies the ONE named variable to that beat's data (never more than one field per retake — the retake
protocol), re-fires that beat only under the identical one-render economy, re-gates it, and returns it to
Julian. An approved retake replaces the take (the old one moves to `media/rejected/` exactly as any other
rejected take does — nothing is ever silently overwritten without a trace). Downstream beats do not
auto-refire off a changed predecessor: the join-check re-verifies state continuity against the new
predecessor and FLAGS a break for Julian's attention; it never blindly cascades a re-render.

## Stage 7 — Gate 5: post

Settle-trim (2.0 seconds, off each clip's edge frames) so the assembled film joins on living motion, never
hold-into-hold (`cb_post.assemble_conformed`, the JOIN CONTRACT). Beats stitched in signed order; the ambient
bed continuous across the whole scene (guaranteed by construction — the Scene Bubble Law). Music and grade
pass. Two masters delivered: the 16:9 feature master and a centre-safe 9:16 derivative
(`cb_post.export_masters`). **Gate 5**: Julian's final-cut approval.

## The gates — machine vs showrunner

Every stage names its gate holder; nothing self-advances past any gate, ever (rule 1). The machine checks
what it can check, mechanically and vision-assisted: verbatim dialogue, both manifests, plate canon,
action-state QA, Clip QA, carryMarks state, Coverage, settle distinctiveness, the prompt-law lint, the
opener-stack law. Julian checks the only things that matter and that no gate owns: does it flow, is it funny,
does the four-year-old watch it again — recorded now as the `approval` field, never left implicit.

| Stage | What happens | Gate holder |
|---|---|---|
| 0 — Script-in | Sole story source; dialogue locked including authored punctuation | — (the input) |
| 1 — Beat package | Script → storyboard; both manifests complete, blanks BLOCK | Julian signs Gate 1 (external review first) |
| 2 — World | Plate built + `check_plate`; turnarounds verified; ambient bed locked | Julian signs Gate 2a |
| 3 — Voices | One V3 take per beat from locked text, fired into generation | Julian's ear approves, or names the one correction |
| 4 — Keyframes | One 2K anchor per scene, action-state QA | Julian signs Gate 2b |
| 5 — The walk | Opener-stack law; cut-default relay; v5-only; one-render economy; approval-not-file-existence resume | Machine gates, then Julian's `approval` field per beat |
| 6 — Retakes | Timecode → beat/cut mapping; one named variable; re-fire; re-gate | Julian names the timecode + correction |
| 7 — Post | Settle-trim; stitch; continuous ambient bed; music/grade; two masters | Julian's final-cut approval |

## Where the detail lives

- **CLAUDE.md** — the numbered, dated constitution (rules 1-39), the record of why each piece exists.
- **MANIFEST.md** — the full field-by-field technical/creative contract spec.
- **This document** — the only stage map; `REPLICATOR.md` is retired (see the Purge record in CLAUDE.md).

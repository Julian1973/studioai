# MORNING HANDOVER — 2026-07-05 lock-in night → 2026-07-06

(Supersedes the previous handover in this file, dated 2026-07-04 — that one described the pre-junction-type-
pivot doctrine, now retired. This is the current state.)

Read `PRODUCTION_DOCTRINE.md` first if you want the one-page doctrine again. This file is just: where things
stand, what to watch, and the exact next steps. Everything below is committed and pushed — nothing is sitting
uncommitted, nothing is signed, nothing is designated.

## Three acts, tonight

1. Two final fixes — @Video1 now says motion-only (never camera framing), and 1.B2's own settle was
   rewritten to be its own distinct moment, plus a new mechanical check (`check_settle_distinctiveness`)
   guarding every future beat against the same drift. Golden-gated, committed.
2. The doctrine consolidated — CLAUDE.md rule 28 now the single, complete, current constitution absorbing
   rules 29-36 (rules 29-36 stay in place, unchanged, as the dated record of why). Mirrored into
   `REPLICATOR.md`'s gate map and a new `PRODUCTION_DOCTRINE.md` at repo root. Committed.
3. 1.B2 re-fired with both fixes, verified honestly, and the replicator's own mechanics proven end-to-end
   with a zero-cost dry walk. Everything pushed.

**Hard rule I held all night, as instructed: no gate sign-offs, no winner designations, no beat advancement.**
Nothing below needs undoing — it's all inspection and data, nothing committed the studio to a direction you
haven't seen.

## State of every beat, right now

| Beat | Clip on disk | Gate/sign-off | Notes |
|---|---|---|---|
| 1.B1 | `media/Ep1_1.B1_s1-b1-bizzy-fwip-nailed-it.mp4` | NOT signed (no per-beat clip sign-off recorded — `locked.json`'s `beats: {}` is empty) | From earlier session work, unchanged tonight |
| 1.B2 | `media/Ep1_1.B2_s1-b2-officially-nuts.mp4` — **this is tonight's FINAL fire, both fixes applied** | NOT signed, NOT designated as a relay winner | Three fires tonight, each overwriting the last; this is the one to watch |
| 1.B3 | none | — | Unfired |
| 1.B4 | none | — | Unfired |
| 1.B5 | none | — | Unfired, and still has no authored `endState`/`carryMarks` (a known, pre-existing gap, not touched tonight) |

**Gate status for Ep1 Scene 1** (`locked.json`): Gate 1 (Director/script breakdown) is signed. **Gate 2b
(keyframe/coverage) is NOT signed** — confirmed live: `cb_replicator.walk_scene("Ep1", "1")` halts immediately
there, zero render cost. This is the ONE thing standing between here and "launch the escorted run" — see
below. (The relay-UI "Approve Anchor" flow described in this file's previous, now-superseded version is
retired for `intentional_next_shot` beats — the default junction type no longer designates a winner through
that ceremony the way the pre-pivot doctrine did; see PRODUCTION_DOCTRINE.md.)

## Watch this

`~/Downloads/1B2_lockin_night_final_verdict_20260705_1954/1.B2_fire_both_fixes.mp4` — the last fire of the
night, both fixes in. Same folder has: the anchor frame, six extracted stills across the timeline, the clip
QA json, the exact shipped prompt, and `verdict_summary.txt` with my full honest read (below, condensed).

Two earlier verdict folders from tonight also exist if you want the fuller history:
`~/Downloads/1B2_three_rulings_verdict_20260705_1911/` (the first intentional-cut fire, before the STATE-tier
correction) and `~/Downloads/1B2_three_rulings_verdict_20260705_corrected_state_tier/` (the corrected-bar
re-evaluation, no new render).

### The honest read on tonight's final fire

- **JOIN CHECK: overall CONTINUOUS.** STATE (carryMarks-scoped) passed clean — the held-pollen prop correctly
  demoted to an advisory flag again, not a block. COVERAGE passed this run, but I'll say directly: the opening
  frame still reads as a fairly wide, pulled-back shot to my own eye (low angle, hills/horizon visible). Earlier
  testing found this same shape of frame BROKEN 2 of 3 independent vision-check runs — this is a borderline
  case that happened to pass this time, not one I'd bet on being consistent. Worth your own eye on this
  specifically.
- **Clip QA: PASS, 1 advisory note — CLIP_IDENTITY_DRIFT.** Traced to the same mid-dive moment (~t=5s) across
  THREE consecutive fires now: Fuzzby's cartoon design (glasses, proportions) briefly disappears into a more
  photorealistic-looking bee during the fast flower-dive. A real, repeatable pattern, not a fluke — flagging
  for a future ticket, out of scope for tonight's two fixes.
- **The settle-authoring fix — mixed, reported honestly.** The TEXT fix worked exactly as designed:
  1.B2's endState reads as a genuinely distinct moment (confirmed mechanically —
  `check_settle_distinctiveness` measured only 21% word-overlap with 1.B1's own endState, well under the 50%
  flag line), and Fuzzby's moustache is now clearly, correctly visible in the final frame. But the RENDERED
  POSE still closely echoes 1.B1's own ending — Fuzzby again lands on a fist-raised, one-leg-lifted stance,
  Zenny again holding a pollen cluster with a slight smile rather than a flat deadpan stare. The wording asked
  for "vibrating with pride, hovering with tiny eager bounces" — what rendered reads more like a repeat of
  1.B1's "Nailed it" pose. My read: the model's pose bias may be pulling from the reference anchor image
  itself (which shows exactly that pose) more than from the settle text. A wording fix alone may not fully
  solve this — worth watching whether it recurs on 1.B3-1.B5, which relay off DIFFERENT anchor poses.
- **The gag itself: consistent win.** The moustache/goatee reveal (~t=8s) has now rendered clearly and legibly
  across every fire tonight. This part of the doctrine is solid.

## Exact sequence for this morning

1. **Watch 1.B2** (the file above). Does it flow? Is it funny? Would a four-year-old ask to watch it again?
   That's the reserved verdict — nothing below is a substitute for it.
2. **If it plays**: nothing needs re-firing. The clip is already sitting at its official path; there is no
   separate "designate" step required for the automated loop to pick it up (confirmed tonight, see below).
3. **Sign Gate 2b** for Ep1 Scene 1 through the studio (the keyframe/coverage sign-off) — this is the ONE
   precondition standing between here and the escorted run. `walk_scene` will refuse to advance past it, by
   design (rule 1 — gates are hard locks).
4. **Launch the escorted run**: `cb_replicator.walk_scene("Ep1", "1")` (or the studio's equivalent trigger).
   It will pick up from 1.B2's current clip automatically and carry 1.B3→1.B5 through the full doctrine —
   junction-type-default cuts, carryMarks-scoped state gating, no-re-mint-on-cuts, the corrected @Video1 text,
   the erratic-in-character staging law — one seed each, standard tier, halting the instant anything comes
   back non-green. Verified tonight with a zero-cost dry walk (below) — the mechanics are sound; nothing
   needs fixing in the code to start this.
5. If it DOESN'T play: the settle/pose-echo issue above is the most likely place to start — either a further
   ruling on how to break the model's pull toward the anchor's pose, or accepting the current settle quality
   and moving on. Your call, not a gate's.

## What I verified before writing this (so "launch the escorted run" isn't a leap of faith)

- `cb_replicator.walk_scene("Ep1", "1")` — ran for real, halted exactly at the Gate 2b precondition, zero cost,
  nothing fired, nothing signed.
- `cb_beats.fire_next_beat(pkg, "1", "Ep1", "1.B2", dry_run=True)` — a zero-cost, no-mutation preview of 1.B3's
  own prep, run for real tonight. Confirmed correct on every consolidated law: `remint` is `None` (no re-mint
  on a cut), `anchor` is the raw harvested settle frame (not a re-mint), the shipped prompt carries the
  corrected @Video1 text, 1.B2's own `carryMarks` ("the moustache, the pollen on their legs") correctly threads
  into 1.B3's own @图1 state-carry clause, the reference stack uploads exactly 4 images (anchor + 2 turnarounds
  + plate) and 1 video (1.B2's own signed clip), and the `prohibited` list correctly merges to exactly 6
  standing negatives when a beat (1.B3) has no `stagingProhibited` of its own yet. **No drift found between
  the doctrine and the code — nothing needed fixing.**
- Golden set: zero diffs on every change tonight that didn't intentionally touch a prompt; every change that
  did was shown before recapture, per the standing rule.
- `test_gate_cascade.py`: still passes after every change tonight.

## What failed, was skipped, or is still open (with reasons)

- **Gate 2b is unsigned.** Not a failure — just the honest current state. It's the one precondition between
  here and the escorted run; see step 3 above.
- **No per-beat clip sign-off exists for 1.B1 or 1.B2** (`locked.json`'s `beats: {}` is empty). Both clips on
  disk came from direct `cb_beats.run` fires, not a winner-designation ceremony — this was deliberate tonight
  (the hard rule: no designations), not an oversight.
- **1.B3's/1.B4's/1.B5's `endState`/`carryMarks`/`opensOn` are not yet authored** with the same care 1.B1/1.B2
  now have — the mechanics all correctly fall back to generic defaults when these are absent (verified in the
  dry walk above), but the settle/coverage quality for those beats will only be as good as their own data once
  they're actually fired. Worth authoring these properly before (or during) the escorted run, not leaving them
  to the generic fallback if you want the same quality bar.
- **CLIP_IDENTITY_DRIFT at the flower-dive moment (~t=5s)** has now recurred on three consecutive 1.B2 fires.
  Flagged, not fixed — outside tonight's two named fixes, and not obviously a doctrine problem (reads more
  like a Seedance rendering quirk on fast, close motion).
- **The pose-echo-toward-the-anchor issue** (see "the honest read" above) is reported, not resolved. The data
  fix (distinct endState wording) is confirmed working at the text level; the render-level behaviour is a
  separate, harder question I haven't solved and didn't try to force through further tonight, per the hard
  rule (no beat advancement, and this isn't one of the two named fixes).
- **`PROMPT_LAWS_AUDIT.md`** still documents v3's shape, not v4's — CLAUDE.md rule 30 already named a fresh
  audit against v4 as "a future ticket, not done automatically by this rule," and that hasn't changed tonight.
- **Cut 4's Law 8 flag** ("has dialogue but framing names camera movement (drifting)") is a known, likely
  false-positive from the naive keyword scan (Zenny "drifting" up beside him describes her motion, not a
  camera move) — pre-existing, not touched tonight, still just an advisory flag, never a block.

## Everything committed and pushed tonight

```
82a231e Consolidate the doctrine: rule 28 absorbs rules 29-36, mirrored into REPLICATOR.md and PRODUCTION_DOCTRINE.md
b4aacd5 Two final lock-in-night fixes: @Video1 motion-only, and settle authoring must be the beat's own moment
41301b5 Scope the join-check's STATE tier to declared carryMarks only (CLAUDE.md rule 36)
```

All pushed to `studio-audit-and-restructure`. (`c8c52e3`, the junction-type-pivot-follow-through commit, was
pushed earlier in the same session, before lock-in night proper began.)

Nos da. Halting here.

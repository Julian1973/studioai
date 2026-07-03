# THE JOIN CONTRACT — Crystal Bears cut-to-cut continuity doctrine

Dictated by Julian, 2026-07-03, after watching Scene 1's assembled beats (1.B1–1.B5) and finding the individual
clips improved but the JOINS between them broken — jumpy, no flow, "just a series of shots strung together."
His diagnosis: **this is a handoff and edit layer problem, not a prompt problem.** Every beat can be well directed
on its own and the scene can still fail, because nothing governs the HANDOFF between one beat's last frame and the
next beat's first frame. This document is that governance. It does not change how any beat's prompt is written.

> **UPDATE, same day:** §1's root-cause finding (POSITION/CAMERA/STATE/WORLD jumps, and the pollen-state bug
> specifically) is now resolved at the prompt/pipeline layer by the RELAY CHAIN and HANDLE DOCTRINE (CLAUDE.md
> rules 20-21) — a continuation beat opens directly off its predecessor's harvested settle frame instead of a
> freshly generated keyframe, so position/state/light ride the actual pixels rather than being re-described. This
> document's edit-layer mechanisms (the settle window's trim handles, `cb_qa.check_join`, `assemble_conformed`)
> are unchanged and still apply — the relay fixes what enters a beat; the join contract still governs how already-
> rendered clips get cut together, including for a beat where the relay wasn't yet available (its first beat, or
> a predecessor without a clip yet).

## 1. The diagnosis (Scene 1, 2026-07-03 — the worked example)

All 4 joins in the current 5-beat Scene 1 were checked two ways: my own frame-by-frame viewing, and
`cb_qa.check_join()` (an independent vision-model pass comparing beat N's composed ending frame to beat N+1's
actual first rendered frame, asked three concrete questions — see §3). Both agreed. Every join broke on at least
one axis; several broke on two or three:

| Join | POSITION | CAMERA | STATE | WORLD/LIGHT | TEMPO |
|---|---|---|---|---|---|
| 1.B1 → 1.B2 | **JUMP** — medium 2-shot facing camera → Fuzzby suddenly huge/back-turned/foreground-blurred, Zenny tiny and far | **JUMP** — full reframe, no continuous move | — | — | mild — held pose → already-blurred motion |
| 1.B2 → 1.B3 | **JUMP** — extreme close single → wide 2-shot at a distance | **JUMP** | **JUMP** — Fuzzby's pollen moustache visible at 1.B2's end, gone at 1.B3's start | **JUMP** — the set itself changes (open lavender meadow → a tree-branch/cherry-blossom/rock-root area); a genuine environment change, not just a light shift | — |
| 1.B3 → 1.B4 | **JUMP** — tight close on Zenny alone → wide 2-shot, both visible | **JUMP** | — | **JUMP** — warm golden light → cooler dusk-blue sky, no transition shown | — |
| 1.B4 → 1.B5 | **JUMP** — Fuzzby/Zenny were frame-left/frame-right; they are SWAPPED at 1.B5's open | **JUMP** (asymmetric close → symmetric medium) | **JUMP** — Fuzzby's pollen dusting visible at 1.B4's end, gone at 1.B5's start | — | — |

**Root cause found for the repeated STATE jump (1.B2→1.B3, 1.B4→1.B5):** this is not the T2 ruling in action (CLAUDE.md
rule 9 — a temporary state resolving within its own take). Checked directly against the beat package: **1.B3, 1.B4
and 1.B5's OWN `startState` fields explicitly call for Fuzzby to still be pollen-covered/disheveled at the OPENING
of each of those beats** ("hovers pollen-covered from the prior gag," "more pollen-disheveled than before,"
"pollen-dusted and alert") — the story itself wants the mess to persist and build across this run of beats. The
rendered keyframes do not show it. This points at `cb_prompts.build_keyframe_prompt`'s CLEAN BASE IDENTITY rule
(added 2026-07-01) stripping a temporary state unconditionally, even when the CURRENT beat's own `startState` (not
just the previous beat) re-asserts it as a carried-forward opening condition — which KEYFRAME_DONE.md's own item 7
says should render ("appears ONLY if THIS shot's action names it" — it IS named, in `startState`, and still isn't
appearing). **Not fixed today** — per Julian's explicit scoping this is a prompt-layer question, out of bounds for
this pass. Flagged for his ruling; 1.B3, 1.B4 and 1.B5 are the beats whose keyframes would need a rebuild (and
therefore a re-render) if he confirms the fix.

The WORLD/set change at 1.B2→1.B3 (not just a light shift — a different physical location) is a second, separate
finding worth his attention: Scene 1 is one continuous location; check whether 1.B3's scene-plate reference or
`definingFeature` resolution is drifting to a different plate.

## 2. The rule (in force from 2026-07-03, edit/assembly layer only)

1. **Every beat's final 0.5–1 second is a SETTLE.** The character(s) come to rest in the pose that IS the next
   beat's `startState` — not a new pose to be re-invented, the same one, held. The camera arrives at whatever end
   state it was directed toward (rule 15's ending-frame doctrine — this is the frame that gets composed). Screen
   positions hold at their established frame-left/frame-right "home" — a character does not change sides between
   a beat's settle and the next beat's open unless the story explicitly stages a cross.
2. **Every beat's shot 1 opens FROM that settle.** Not a fresh re-establishing shot, not a new camera setup that
   happens to feature the same characters — a continuation of the pose, position and light the previous beat just
   settled into.
3. **Continuity gains a join check** (`cb_qa.check_join`, built 2026-07-03): compares beat N's composed ending
   frame (rule 15) against beat N+1's actual opening frame for POSITION, STATE and LIGHT — three concrete,
   answerable questions per rule 17, never a vague "does this flow." Report-only/advisory, like every other frame
   check in this pipeline; it names what broke, it does not auto-block a render.
4. **Gate 4 assembles the rough cut with TRIMS, not raw concatenation.** `cb_post.assemble_conformed` (built
   2026-07-03) trims a fixed settle allowance off the tail of every clip but the scene's last (`TRIM_OUT`, default
   0.35s) and off the head of every clip but the scene's first (`TRIM_IN`, default 0.20s) before hard-cutting them
   together. Showing a beat's full settle AND the next beat's full opening-echo of that same settle back-to-back
   doubles the stillness at every cut — trimming into and out of it lands the cut while there is still a whisper of
   motion on both sides, which is where the flow is actually made. Cuts stay HARD (rule/memory: no in-scene
   cross-dissolves — that grammar is unchanged). `assemble_picture` (the raw butt-join) is kept, unchanged, as the
   deliberate baseline for comparison — never deleted, never silently replaced as the default.

## 3. What this does NOT change

- No prompt-building code changes (`cb_segprompt.py`, `cb_prompts.py`, `cb_director.py`) — Julian's explicit
  scoping for this ruling. The STATE-jump root cause above is diagnosed, not fixed, for that reason.
- No re-renders. The rough cut in §1/§4 is built ENTIRELY from clips that already existed before this ruling.
- The FRAME CHAIN doctrine (rule 15) and its pending correction note are unchanged and unrelated — that doctrine is
  about what a CONTINUATION beat's keyframe generation chains off of; this doctrine is about how already-rendered
  clips get TRIMMED AND CUT TOGETHER at Gate 4. Different layer, same spirit (continuity carries forward).

## 4. The comparison Julian asked to see

Both built from the SAME 5 already-rendered official beat clips, no re-render:

- `engine/media/Ep1_Scene1_ROUGHCUT_raw_buttjoin.mp4` — the existing assembly, full clips, hard cut, no trims
  (what he watched and flagged).
- `engine/media/Ep1_Scene1_ROUGHCUT_conformed.mp4` — the new Gate-4 conform, same clips, same hard cuts, trimmed
  into/out of each settle per §2.4.

The conformed cut is shorter (47.7s vs 49.9s — exactly 4 joins × 0.55s) and lands each cut earlier, before the
double-hold. It does **not** fix the POSITION/STATE/WORLD jumps diagnosed in §1 — no amount of trimming corrects a
character teleporting screen sides or a set changing under them. Those need the upstream fix this document
deliberately leaves for Julian's ruling. The conformed cut is the honest ceiling of what an edit-layer-only fix can
do; the remaining jumpiness in it is the §1 findings, now isolated from "just bad editing" and named precisely.

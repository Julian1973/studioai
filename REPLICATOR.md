# THE REPLICATOR

One command: `walk_scene(episode, scene)` (`engine/cb_replicator.py`). It runs Gate 3 end to end for a whole
scene — every beat, relay chain and all — under the escorted-run rules, so the next ten scenes get built by
the same hands rule 28 already established, and the only thing a director ever authors again is Layer 2.

## The three inputs

`walk_scene` takes exactly two arguments — `episode`, `scene` — and resolves everything else from them, through
the same conventions every other module in this pipeline already uses:

1. **The show profile** — the laws (`shows/<show>/laws/*.txt`), the show's confirmed style line, the character
   config (`config/characters.json`) — read by `cb_segprompt`/`cb_prompts` exactly as they already do for any
   other fire. Nothing new.
2. **The scene data** — the scene's plate, ambient bed, location and atmosphere fields, resolved via the beat
   package's `scenes[]` entry matching `sceneNumber`. Same lookup `cb_beats.run`/`gate3_dryrun` already do.
3. **The director's cut** — the scene's signed, locked beat list: `cuts[]` (action/framing/dialogue),
   `endState`/`endStateStill`, `comedyMode`, `soundIntent`, `pauseHold`. This is Layer 2 — a human (or the
   Director skill) already wrote it before `walk_scene` is ever called. The beat package is resolved by the
   same glob `cb_pipeline._resolve_pkg` uses (`cb-output/<episode>_*beat_package.json`, newest by mtime).

Nothing else. No seed file, no winner pick, no approval flag — see "escorted" below for why.

## The one command

```
python3 cb_replicator.py <episode> <scene>
```
or, from any engine script: `from cb_replicator import walk_scene; walk_scene(episode, scene)`.

Each call processes as much of the scene as it safely can and returns one report:

```
{"status": "COMPLETE" | "HALTED", "scene": ..., "beats_done": [...], "halted_at": <beatCode or None>,
 "reason": "...", "evidence": [<Downloads paths>]}
```

**Resumable by construction.** Every piece of state it reads — official clips, `.qa.json` sidecars, harvested/
re-mint anchors, `locked.json` — lives on disk. Calling `walk_scene` again after fixing whatever halted it picks
up from the same beat; it never re-fires a beat that already has a clean, QA-passed clip, and never spends money
twice on the same take.

## The gate map

| Step | What runs | What it checks | Non-green means |
|---|---|---|---|
| Precondition | `locked.json`'s Gate 2b flag for this scene | Is the scene's own opening keyframe signed? | HALT before anything fires — rule 1, gates are hard locks |
| Assemble | `cb_segprompt.shipped_prompt` (beat 1: `relay=False`; every beat after: `relay=True`, `prev_end_state_still` AND `prev_carry_marks` threaded from the prior beat's own authored fields) — each relay beat's own `junctionType` (`intentional_next_shot`, the default, or `seamless_continuation`) is read here too, branching @图1's text between a state-reference clause and the locked opening-frame text (rule 31). The state-reference clause itself (rule 33/34) states the Coverage Law's spatial leash explicitly ("open on a fresh camera setup within the same space, close to where @图1 shows the characters"); the beat's own `opensOn` field supplies the concrete eyeline-bridge sentence that follows it. @Video1's own reference text is motion energy and action continuity ONLY as of 2026-07-05 lock-in night — never camera framing, shot size or composition, which comes from this beat's own direction (the earlier wording left framing implicitly copyable) | The rule-28 skeleton — Layer 1, mechanical | An empty prompt halts; nothing hand-edits it to fix that |
| Twelve-law lint | `cb_qa.check_prompt_laws` | Laws 4/7/8 (the only currently-convention-only gaps) as flags; laws 1/2/3/5/6/9/10/11/12 reported structural/uncheckable — see PROMPT_LAWS_AUDIT.md | Flags never halt (advisory by Julian's ruling, 2026-07-04); Laws 3 and 5 (voice) are the two hard blocks, and they fire **upstream**, inside `cb_beats.run`, before a clip ever exists — a refused beat is caught by the next step, not this one |
| Fire | `cb_beats.run` (beat 1) / `cb_beats.fire_next_beat(..., dry_run=True)` then `(..., approved=True)` (every beat after) | Single seed, standard tier (`fast=False`) — the same configuration as the 1.B2 camera-lock test | No clip on disk after firing = HALT (a Law 3/5-class refusal, or a render fault) |
| Harvest → (re-mint + drift check) | `cb_scene.harvest_settle_frame`, ALWAYS — then `cb_scene.remint_settle_frame` → `cb_qa.check_remint` ONLY when the beat about to be fired next is `seamless_continuation`. An `intentional_next_shot` next beat (the default) skips both entirely — RE-MINT SCOPING, rule 32, superseding this row's earlier "always re-mint" shape — its @图1 is a state reference, not a pixel-perfect anchor, so the NB2 cleanup pass buys nothing | Position/state vs the harvest, identity vs the turnarounds (seamless only) | `DRIFT` = HALT before the next beat's anchor is ever used (seamless only — an intentional-cut next beat has no drift check to fail; state continuity is verified by the join-check below instead, after firing) |
| Clip QA | `cb_qa.check_clip` (already run and sidecar-persisted by `cb_beats.run`) | Frozen/morph/identity-drift/pop-character/crystal-on-bee/unsafe-face and the rest of `CLIP_BLOCK_CODES` | Any block = HALT |
| Join check (+ anti-hold, seamless only) | `cb_qa.check_join` against a fresh frame-1 extraction of the just-fired clip, plus a last-frame extraction for the evidence pack | TWO-TIER (rule 31): STATE/LIGHT/GEOGRAPHY/COVERAGE (rule 34 adds COVERAGE — does the opening read as a continuation within the same space, not a fresh establishing wide or a relocation) is the hard gate on EVERY join, cut or continuation; POSITION/frame-identity is checked ONLY when the beat that just fired declared itself `seamless_continuation` — an `intentional_next_shot` join (the default) is never held to matching the literal frame, since a cut is expected to look different. STATE itself is scoped to the beat's own declared `carryMarks` ONLY (rule 36) — any other visible prop/substance (a held object, say) is advisory-only, surfaced via `check_join`'s `flags` list, never blocking | `BROKEN` (on the applicable tier(s) for this beat's junction type) = HALT — this is exactly the check that caught the still-open camera-hypothesis failure on 1.B2, and later the state-continuity break on its first intentional-cut fire |
| Next beat | `endStateStill` AND `carryMarks` thread forward automatically (read by `_v3_prev_frame_content`/`_v4_state_carry`); the beat declares its own `opensOn`/`actingContrast` for its own assembly step above; its own `endState` is checked (advisory, `check_settle_distinctiveness`) against the predecessor's own `endState` for excessive overlap — the settle must read as its own distinct moment, never a restatement of the previous beat's pose | — | Loop continues only if every step above came back green |

Gates are per CLAUDE.md rule 1 throughout: `walk_scene` can only ever operate on an already-signed Gate 2b, and
it never signs anything itself. Scene boundaries reset to canon automatically — `walk_scene` filters the beat
list to one scene before any of this runs, so `relay_source_for` can never see a different scene's settle
frame; a scene's own first beat always resolves `"first"`.

**THE SCENE BUBBLE LAW (rule 35, 2026-07-05)** formalizes this as a named doctrine rather than an implicit
side-effect of the per-scene filter: a scene's three locked constants — the scene plate, the ambient bed, the
style law — stay verbatim across every beat inside it (`_v3_style()` is show-profile-level, trivially
verbatim everywhere; `_v3_ambience(scene)`/the plate reference both read straight from THIS scene's own data,
unchanged beat to beat); a scene boundary is a full, deliberate reset — new plate, new ambient bed, a fresh
canon-generated anchor keyframe for the scene's own opening beat, relay depth back to zero, no visual
continuity owed across the boundary. Nothing new was needed to guarantee this; `walk_scene`'s own per-scene
filtering already made it true — this section names the guarantee explicitly.

## The gates — machine vs showrunner

`walk_scene` (and every check in the gate map above) is the MACHINE half of the loop: state continuity on
declared carryMarks, spatial adjacency (Coverage), Clip QA, the flag-only prompt-law lint. It stops there —
deliberately. Whether a signed-off, all-green beat actually FLOWS, is FUNNY, and is something a four-year-old
would ask to watch again is a RESERVED VERDICT that belongs to Julian alone; no check in this file is ever
built to approximate it, and `walk_scene` never signs a beat off on the machine's say-so. The loop is: fire →
machine gates → Julian's felt-intent verdict → sign → harvest → next beat. Escorted means the machine runs
itself between green checks; it does not mean the machine decides when a beat is DONE.

## What a director authors vs. what the machine owns

| Director authors (Layer 2) | Machine owns (Layer 1, this file + rule 28) |
|---|---|
| Shot list: count, durations summing to 15, camera intention per shot | The 15s split itself (13s action + 2s settle) — fixed constants, cannot drift |
| Action prose — the beat's own gag, written to the Layered Humour Model, ERRATIC IN CHARACTER BUT PRECISE IN CHOREOGRAPHY (rule 33) — every manic action a specific named gag with cause and consequence; adjective-chaos ("wildly," "crazily") banned as unreadable | The photograph-not-a-story discipline on @图1's content clause (endStateStill, once authored) |
| Dialogue bindings: who speaks, in which shot, what expression | The @Audio1-only audio law, and the regex strip that guarantees no spoken words leak into the prose |
| Tone line and per-beat foreground SFX | The locked ambient bed, word-for-word identical every clip in the scene (Scene Bubble Law, rule 35) |
| `endState` (directing prose) **and** `endStateStill` (the static photograph, hand-authored in parallel — rule 27 explicitly rejected an automatic transform between the two); `carryMarks` (a new field, rule 33 — a SHORT phrase naming what specifically persists, e.g. "the pollen on their legs," never a full sentence) | Threading `endStateStill`/`carryMarks` forward as the next beat's point-anchor content, mechanically, every beat; `endState` also drives THIS beat's own "settle in character" segment verbatim |
| `opensOn` (a new field, rule 33/34 — WHO the camera opens on and their immediate mid-motion state) and `actingContrast` (a new field — which characters play off each other and how) | The Coverage Law's spatial leash stated in @图1's own text (rule 34); the `acting_rules` field's per-character essence, from a new `characters.json` bible field (`actingRule`) |
| — | The five-anchor reference stack, the six negatives, the binding-handle wording, the style/world text — all assembled, never retyped |
| — | Every check in the gate map above, and the halt/evidence-pack discipline itself |

The hard rule this file enforces: **no prompt text is ever authored or edited by hand.** `cb_segprompt.py` is
the sole writer of the shipped prompt; `walk_scene` only ever calls it, reads its output, and decides whether
to keep going. Any change to what ships is an emitter change or a Layer-2 data change — golden-gated, shown to
Julian before the golden set is re-blessed, exactly as it already is for every fix in this repo's history.

## What this is not

Not autonomous. "Escorted" means the mechanical steps run themselves for as long as every check is green, and
stop the instant one isn't — never a fully unattended, fire-and-forget scene render. It fires one seed per
beat, standard tier, because a single clean take plus automated QA is the escort; there is no "pick a winner"
step because there's nothing for a human to adjudicate that the checks above don't already catch first.

## Maiden run

1.B2 has now been fired three times under the pivot (2026-07-05, lock-in night): the first `intentional_next_shot`
test surfaced the COVERAGE gap and a since-refined STATE tier; the corrected-bar re-evaluation confirmed
carryMarks-scoping works (the held-pollen false-positive is now advisory-only, three runs straight); a further
fire applied the @Video1 correction and the settle-authoring fix together. Each was single seed, standard tier,
the raw harvested anchor (no re-mint), full evidence pack to Downloads, nothing designated or signed. That is
exactly the behaviour `walk_scene`'s per-beat loop reproduces — the difference is only that it runs beat-to-beat
automatically instead of one manual `fire_next_beat` call at a time. A live, full-scene run has not been
executed as part of this build: Gate 2b is not yet signed for Ep1 Scene 1 (confirmed live — `walk_scene("Ep1",
"1")` correctly halts there, zero render cost), and this module does not sign gates. The first real end-to-end
walk happens once a scene's Gate 2b is signed and Julian runs it — see MORNING_HANDOVER.md for the exact
sequence.

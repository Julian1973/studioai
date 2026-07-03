# FIELD-TO-FRAME AUDIT — T33 (2026-07-02)

*Same bug class as the `startState`/`shotSize` find that started this: a field the Director writes rich content
into that nothing downstream ever reads is a leak. This audit enumerated every field in the Beat/Cut/Performance/
BeatContinuity/BeatCheck schema (`cb_director_schemas.py`) and grepped every consumer file in `engine/` (everything
except the write-side: `cb_director.py`, `cb_director_schemas.py`, `cb_writer.py`, `cb_llm.py`) for where each one
is actually consumed — not just referenced, but read into something that shapes a generated artifact (a keyframe
prompt, the Seedance clip prompt, a voice direction, or a QA check).*

**74 fields audited. 30 CONSUMED. 8 STRUCTURAL (bookkeeping, correctly not prompt-facing). 18 PARTIAL (consumed in
some of the four paths, missing from one it clearly belongs in). 18 LEAK (consumed nowhere).**

Per CLAUDE.md hard rule 11: this pass fixed every confirmed leak in the **keyframe, voice and QA paths** — the
scope Julian named. Leaks confined to the Seedance-clip path, or requiring a design decision rather than a
mechanical read-the-right-field fix, are listed below as deferred, not silently dropped.

## FIXED THIS PASS

### Keyframe (`cb_prompts.py`, `build_keyframe_prompt` / `_expression_mood`)
- **`light`** — wrong-key bug, identical to the `shotSize`/`shotType` precedent: the prompt read `shot.get("lighting")`,
  a key that is never populated on beat-native data. The Director's real per-beat field is `light`, and it is richer
  and beat-varying (e.g. differentiated per character) where the scene-level fallback was generic. Fixed to prefer
  `light`, falling back to the legacy key then the scene config.
- **`atmosphere`** — never reached the keyframe at all. Added as its own line (anchor beats) and folded into the
  CONTINUITY & CAMERA SHIFT text for chained beats (the chain-reference image shows the *previous* frame's light, so
  it cannot convey a narrative shift — e.g. cooling before a thunder beat — that this beat's own fields describe).
- **`keenWristbands`** — a genuine, confirmed bug: `build_keyframe_prompt` never called `char_refs()`/`_band_line()`
  at all (those are only wired into `build_charsheet_prompt`/`build_vision_prompt`). The keyframe — the one every
  chained beat and every Gate-3 take is built from — was pulling NO wristband-state reference image and asserting NO
  "Keen wears…" text. Fixed: the character-reference loop now attaches the matching `wristband_states` image, and
  `_band_line`'s text is folded into CONSTRAINTS. Verified with a synthetic Keen/crystal-cuffs beat (no real bear
  beats exist in the current Ep1 data to test against).
- **`crystalGlow`** — never reached the keyframe (only QA and voice read it). Added a `CRYSTAL STATE:` line in
  CONSTRAINTS for bears in frame, mirroring the existing bee-only crystal rule and matching what
  `cb_qa.py`'s `CRYSTAL_STATE_MISMATCH` check already expects the render to show.
- **`crystalTruth`**, **`audience_feeling_target`** — never reached the keyframe despite being exactly the kind of
  expression-shaping content `_expression_mood`'s EXPRESSION & MOOD line exists for. Added as additional segments.
- **`beautyMoment`** — a total leak (the Director's "this is the scene's one beauty beat" flag was discarded
  everywhere). Added a STYLE-line emphasis when true.
- **`wordlessHeld`** — never reached the keyframe (only voice/QA/segprompt read it). Added an explicit
  "this is the held, wordless, stillness-carries-it moment" note to EXPRESSION & MOOD.
- **`innerThought`** — confirmed as a *deliberate* keyframe exclusion (an existing code comment already says so —
  it belongs to the i2v/motion performance, not the still frame). Left alone in the keyframe; routed to voice instead
  (below), since the i2v path that was meant to carry it is dead code.

### QA (`cb_qa.py`)
- **`light`** — same wrong-key bug as the keyframe, inside `check_done_frame`'s `LIGHTING_MISMATCH` check. Fixed
  the same way.
- **`action`** — beat-level `shot.get("action")` is a phantom read: `action` only exists on `cuts[]` in beat-native
  data, so this was always empty, in both `check_done_frame`'s substance scan (gates `TRANSIENT_PROP_DRIFT`) and
  `_passB`'s resolve-verb scan (gates `CLIP_STATE_DROPPED`). Fixed to join every cut's own `action` text.
- **`endState`** — a dead read left over from the continuity-tail chaining mechanism T2's ruling removed; no such
  field is ever written. Dropped.
- **Found while fixing `action`**: widening the search text surfaced a pre-existing weakness — `RESOLVE_VERBS`/
  `SUBSTANCE_WORDS` matched as bare substrings (`"eat"` inside `"neatly"`, etc.), which the old, narrower
  `storyBeat`-only text mostly avoided by luck. Measured on real Ep1 data: the naive substring match flagged a
  resolve-verb on 16/45 beats; a word-boundary match (the fix) brings that to the 3 that are actually real. Added a
  shared `_any_word()` helper and applied it to both checks.

### QA-adjacent — Director's Eye (`cb_director_eye.py`, Gate 1.5)
- **`check`/`focalSubject`/`emotionalRead`/`heartCheck`** — the Director's own self-review triad was produced every
  beat and read by nothing, including the one function that exists specifically to curate what the Eye judges
  (`_slim()`). Added as `selfCheck` — lets the Eye flag a beat where its own independent read disagrees with the
  Director's.
- **`kidRead`**, **`audience_feeling_target`**, **`beautyMoment`** — all reached some path but not the bible/craft
  review. Added to `_slim()`.

### Voice (`cb_voice.py`)
- **The `_resolve_turns` fallback-shot leak** (found independently before the audit ran, then confirmed by it under
  `need`/PARTIAL): the per-line fallback direction (when there is no cached Director's-Pass acted line for that
  exact cut) called `direct_line()` with a synthetic shot carrying only that cut's `delivery` text — `emotionalIntent`,
  `crystalGlow`, `crystalTruth`, `need` and `performance.underneath`/`innerThought` were all silently absent, so a
  Heart/Crystal-Call beat could be mis-tagged or miss its need-leak whenever the cache was cold. Fixed: the fallback
  now builds its shot from the REAL beat, overriding only `performance.surface` with the line's own delivery note.
  **Verified on real data**: beat 1.B1 with no cached direction now correctly appends `[gulps]` (the need-leak) to
  both of Fuzzby's lines; before the fix, neither line got one.
- **`innerThought`** — added to `_leak()`'s contradiction check alongside `crystalTruth`/`need`/`performance.underneath`.

**Baseline proof**: `cb_segprompt.py` output on Ep1 1.B1-1.B3 is byte-identical before and after every fix above —
none of it touches the Seedance-clip path. Confirmed by diff, not assumption.

## DEFERRED — Seedance-clip path (out of this pass's named scope)

All confirmed LEAK or PARTIAL, all sharing one root cause: `cb_seedance.py`'s authoring/compact/flatten prompt
pipeline reads these fields correctly, but that whole prompt is discarded in practice — `cb_beats.run` and
`cb_seedance.get_seedance_prompt()` always prefer `cb_segprompt.for_beat()`'s output, which never returns empty for
a normal beat and never reads any of them.

`intensity` (total leak, zero reads anywhere) · `pacingVerbs` (total leak) · `motionTempo` (only reachable via the
unrouted `for_beat_v2`) · `music_emotion` · `pauseHold` · `physical_staging_intent` (validated for mere presence,
content never shipped) · `failed_correction_rule` (fetched, never read again — its five sibling staging-rule fields
ARE wired, this one was skipped) · `atmosphere`/`audience_feeling_target` (also true for the Seedance-clip text
specifically, independent of their keyframe/QA fixes above).

Fixing these means either routing `for_beat_v2` live (T7's own DoD explicitly reserves that for after Julian reviews
the 44 regenerated prompts) or teaching `for_beat` itself to read them — a decision for whoever picks up T7/T9, not
a same-pass mechanical fix.

## DEFERRED — needs a design decision, not a field-source swap

- **`director_mode`** — rich, 15-mode guidance text, heavily used in the Seedance-clip validator, completely absent
  from keyframe, voice and QA. Wiring it in properly means deciding what each of the 15 modes should mean for a
  still frame's composition, for voice's tender/comedy signal, and for a mode-aware QA expectation — a real design
  pass, not a one-line fix.
- **`cameraArc`**, **`physics_rule`**, **`prohibited_staging`**, **`visibility_rule`**, **`visual_payoff_rule`**,
  **`script_gag_lock_id`** — all correctly shape the PROMPT sent to Seedance, but nothing verifies the RENDERED clip
  actually honoured them. This is a new QA capability (vision-based staging/camera verification), not a leak fix.
- **`performance_notes`** ("acting truth for the performers") — ambiguous whether it belongs in the keyframe's
  expression or voice's tag selection; needs a call, not a guess.
- **`writerNote`** — meant to reach Julian as a human flag; needs studio/UI surfacing, not a keyframe/voice/QA read.

## NOT A LEAK — reviewed and left alone

- **`n`** (cut ordinal) — genuinely unread everywhere; every consumer fabricates its own via `enumerate()`. Inert:
  the schema already guarantees `cuts` stays in order, so this is redundant, not broken. Not worth the risk of
  replacing a working positional assumption with a field read that could disagree with it on bad data.
- **`delivery`** — a fallback used only when there's no cached Director's-Pass line; working as designed.
- **`physicalFeeling`**'s exclusion from `cb_voice.py`'s tenderness check — an existing, documented, deliberate
  design choice (physical-metaphor collision), not a leak.
- **`i2vPrompt`**, **`keyframePrompt`** — known-superseded legacy seed fields; the real prompts are always the
  assembled ones (`build_i2v_prompt`/`build_keyframe_prompt`), per existing project doctrine.

## T10 — the golden set

`engine/cb_golden.py` + `engine/goldens/` now store the 3 Seedance baseline prompts (1.B1-1.B3) and the 4 Scene-1
keyframe prompts (1.B1-1.B4, anchor + chained) as of this fix. `python3 cb_golden.py diff` compares current output
against them; `capture` deliberately overwrites the golden (only after a diff has been shown and reviewed). Captured
once, immediately after this pass, so it reflects the corrected state — not the pre-fix one.

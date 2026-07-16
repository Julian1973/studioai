> ⚠ **SUPERSEDED PENDING CUTOVER (architecture recovery, 2026-07-16):** this document
> governs ONLY the legacy beat pipeline until the shot pipeline's first real approved
> shot lands. THE_DEFINITIVE_PIPELINE.md is the one authoritative specification.

# THE MANIFEST — the two contracts (locked 2026-07-06, Julian)

Every beat, scene and package must satisfy TWO contracts — TECHNICAL and CREATIVE — before it may pass Gate 1
review, and before any later gate may arm. **A blank field BLOCKS, and names itself** — no generic fallback
text ever substitutes for missing authored content again (CLAUDE.md rule 7's "sharper code" principle applied
to data, not just code: if a field is required, its absence is a fact to report, never a gap to paper over).

`cb_preflight.py` is the single command that checks both contracts against the current beat package and
prints a PASS/FAIL gap table, per beat/scene/package, every gap named. See "Where the detail lives" at the
bottom for the code that enforces this.

## What counts as a BLOCK vs a FLAG

- **BLOCK** — a required field is present but empty, or missing entirely. Named exactly: `1.B4: BLOCK — endState missing`.
- **FLAG** — a computed/derived check with no fixed pass bar yet (e.g. the Fuzzby/Zenny ratio has no stated
  target), or a best-effort structural heuristic (single gag arc) that can't be a hard semantic guarantee.
  Reported for the record, same as this codebase's existing advisory-flag convention — never silently hidden.
- **STRUCTURAL** — already impossible to violate by construction (the emitter can't produce a wrong value) —
  reported so "every gap named" doesn't quietly mean "except the ones we forgot," not re-checked.

## TECHNICAL CONTRACT

### Per beat
| Field | Existing field name | Note |
|---|---|---|
| End-state directing prose | `endState` | rule 27/33 — this beat's own settle, in character |
| End-state as a still photograph | `endStateStill` | rule 27 — hand-authored PARALLEL to endState, never auto-derived; the ONLY thing the next beat's @图1 state-carry clause may quote |
| What visibly persists | `carryMarks` | rule 33 — short phrase, never a full sentence |
| Junction type | `junctionType` | rule 31 — must be EXPLICITLY declared (`intentional_next_shot` or `seamless_continuation`) on every beat after a scene's opener. The code still safely defaults an absent value to `intentional_next_shot` (rule 31 is unchanged) — but the Manifest wants it authored, not relied on as a silent default, so a missing `junctionType` is named as a gap even though rendering would still work correctly |
| One hold, stated ≤1.5s | `pauseHold` | must state a concrete duration; that duration must be ≤1.5s. **This exact framing ("outside the settle window") is MY synthesis of staging law 8 ("holds only on buttons, max 1, under 1.5s") plus the Handle Doctrine's 2s settle (rule 20) — the settle's own rest is a DESIGNED end-state, not a "held button," so it is exempt from this cap by definition, not by an explicit doctrine carve-out. Flagging this because the crosscheck confirmed no doctrine source states this exact scoping verbatim — it's a defensible derivation, not a quote** |
| Camera bridge on a cut | `opensOn` | rule 33/34 — `{who, action}`; required for `intentional_next_shot` beats (the default), not applicable to `seamless_continuation` beats |
| Character contrast for this beat | `actingContrast` | rule 33 |
| Speaker order matches the track | derived from `speakers` + `cuts[].dialogue` order | the order dialogue appears in `cuts[]` must match `speakers[]`'s own order — a mismatch means the emitter's ordinal speaker-binding sentence (rule 30/33) would misattribute a line |
| Single gag arc | best-effort structural heuristic | **FLAG only, not a hard BLOCK** — cb_qa.py's own comments already admit "Law 1's other half (one gag arc per beat)... this lint cannot cover at all." cb_preflight FLAGs whenever `pauseHold` is blank OR `script_gag_lock_id` is absent, as a proxy that a beat has SOMETHING to anchor a single arc on; it is not a semantic guarantee. *(CORRECTED 2026-07-12, full-codebase audit: this row previously claimed the check verifies "exactly one stated hold and no more than one script_gag_lock_id/climax marker" — there is no "climax marker" concept anywhere in the codebase, and `script_gag_lock_id` is a single `Optional[str]` field, so no cardinality/"no more than one" check exists or would be meaningful. The check is exactly the two simple booleans stated above, nothing more.)* |
| Delivery note on every spoken cut (THE DELIVERY LAW, rule 53, 2026-07-08) | `cuts[].delivery` | **hard BLOCK** whenever the same cut's `dialogue` is non-blank. Gate-1-native as of rule 53 (`cb_director_schemas.Cut.delivery`, `cb_director.scene_to_beats`'s prompt) — ACTING DIRECTION for the line's performance (tone, physical behaviour, what's held back/revealed), never the words; quoted verbatim into the shipped prompt as "{Name} performs {his/her} vocal beat from @Audio1 {delivery}." (`cb_segprompt._v5_cut_speaker_note`). Before this rule the field existed but was silently discarded by the emitter — every cut shipped as a bare "{Name} speaks." regardless of what was authored here |
| Relay opening note (optional) | `relayOpeningNote` | **Optional, no BLOCK.** One extra sentence for a relay beat's @图1 clause naming what breaks immediately after the anchor frame — only when opensOn/carryMarks alone leave real ambiguity. Gate-1-native as of rule 53; most beats leave this null |
| Spatial axis (optional) | `spatialAxis` | **Optional, no BLOCK.** A fixed one-sentence blocking law (who's in which lane, "never swap sides") — only when the scene's own blocking benefits from an explicit standing rule. Gate-1-native as of rule 53; most beats leave this null |
| Staging prohibited, well-formed (optional) | `stagingProhibited` | **Optional; a BLOCK only if present-but-malformed** (`cb_preflight.check_beat_technical` — must be a list of non-blank strings when the field exists at all). A short list of this beat's own specific gag-failure modes, merged into the shipped Negative line ahead of the twelve standing negatives (`cb_segprompt._v5_negative_line`). Found MISSING from `cb_director_schemas.Beat` entirely in the 2026-07-08 sign-off audit — real, load-bearing data with no schema field to back it, meaning Gate 1 could never natively author it; closed the same day (schema field + Director prompt guidance added, matching `relayOpeningNote`/`spatialAxis`'s own treatment) |
| Word count (the v5 engine, rule 42, 2026-07-06; cap RAISED rule 52, 2026-07-07) | `cb_preflight.check_beat_word_count` compiles THIS beat's actual v5 prompt (same relay/junction resolution cb_beats.run uses) and counts it — **`WORD_BUDGET_BLOCK`+ words (650) is a hard BLOCK**, `WORD_BUDGET_TARGET`-BLOCK (400-650) is a FLAG (over the target, not gated), under 400 is clean. Raised from 400/250 — the old pair predated the shot-list restoration and decision 1's anti-hold-safe relay wording, both real content, not bloat |
| Dialogue verbatim fidelity (THE PIXAR-CRAFT GATE, rule 48, 2026-07-07) | `cb_preflight.check_scene_dialogue_verbatim` | **hard BLOCK, zero LLM.** Compares every scene's shipped cut dialogue against `cb_script.dialogue_lines` (the same deterministic ground truth `cb_director.enforce_verbatim` uses at Gate-1 authoring time) via a proper `difflib` LCS alignment — not a positional zip, which would cascade a false mismatch onto every line after any legitimate cut. Standing and re-runnable at any gate-arming point, unlike `enforce_verbatim`, which only ever runs once, inside `direct()`'s own authoring pass — this closes the gap that let a later hand-edited package drift from the locked script undetected. A clean 1:1 line rewrite is auto-fixable (`cb_preflight.fix_scene_dialogue_verbatim`, zero LLM — the script IS the ground truth by the Faithful Director law); a drop/insert/uneven rewrite is named and left for a human decision. See "Per scene" below for the scene-scoped half of this same check (a dropped/inserted/multi-line-rewritten script line reports at the scene level, not a single beat) |

### Per scene
| Check | Mechanism |
|---|---|
| Plate passes | `cb_qa.check_plate` (crystal shape, no characters in frame) |
| Ambient bed present | `ambientBed` field on the scene. **NO LONGER READ into any beat's shipped prompt as of the v5 engine (2026-07-06)** — v5's literal five-block spec has no ambience slot; the field's own presence is still checked here (a scene-level data gap is still worth naming), but rule 25's "word-for-word identical every clip" guarantee no longer has anything live enforcing it in the shipped text. Flagged to Julian in the v5 build report as a real behaviour change, not silently dropped — reported STRUCTURAL pending his call on whether to fold it back in |
| Scene look present (THE SCENE-LOOK LAW, rule 53, 2026-07-08) | `sceneLook` field on the scene | **hard BLOCK.** Gate-1-native (`cb_director_schemas.Scene.sceneLook`, `Field(min_length=1)` — same pattern as `ambientBed`/`parentLine`). Read verbatim into every beat's shipped Block 1, appended as a second sentence after the show's own fixed style law (`cb_segprompt._v5_scene_look`) — added the same day the universal style law was leaned (rule 52, decision 4) and scene-specific atmosphere moved OUT of it; a scene with no `sceneLook` ships every one of its beats with ZERO atmosphere language. Backfilled for Scenes 2-10 the same session (derived mechanically from each scene's own already-authored `lighting` field — THE FIDELITY LAW, never invented) |
| Locations cache in sync | `cb_prompts.scene_cache_stale()`, called directly by `cb_preflight.check_scene_technical` | *(CORRECTED 2026-07-12, full-codebase audit: this row previously cited a `tools/sync_scenes.py --check` subprocess shellout — cb_preflight.py's own inline comment, dated 2026-07-06, documents that approach was found broken (wrong cwd, the script lives at repo-root not engine/) and replaced; the live check calls `cb_prompts.scene_cache_stale()` in-process and never invokes `tools/sync_scenes.py` at all. That script still exists as a separate, manual-sync CLI utility — just not what this check runs.)* |
| Performance throughline (per scene) | `performanceThroughline` (STRUCTURAL, informational — never a BLOCK/FLAG) | rule 58 — computed live and zero-LLM by `cb_director._derive_performance_throughline(beats)`, reading each beat's own already-authored `fidelityAllocation.primary` and collapsing consecutive beats sharing the same primary into a "who carries this scene, and when it hands off" sentence. Superseded rule 57's first (retracted) version, which asked for a separately hand/LLM-authored scene-level field authored BEFORE any beats existed — backwards, since the beats' own data already answers the question the moment they're written |
| Vocabulary pass | `cb_qa.check_scene_vocabulary` (canon/banned_vocabulary.json) |
| Dialogue verbatim fidelity, scene-scoped cases (rule 48, 2026-07-07) | `cb_preflight.check_scene_dialogue_verbatim` | a dropped script line, an inserted/invented line, or a multi-line rewrite that isn't a clean 1:1 substitution reports here (scope: scene), not against a single beat — see "Per beat" above for the common 1:1 rewrite case. A deliberate, already-approved creative cut (e.g. a line moved to wordless action) still reports as a BLOCK with an explicit caveat that it may be intentional — this check names the fact, it does not judge the creative call |

### Per character (new tier — the crosscheck caught this was missing from the first draft)
**CORRECTED 2026-07-07** (found stale during the rule-48 documentation sweep — this table still described `actingRule`/`actingDNA`, both retired by rule 28's THE ACTINGDNA RETRACTION the same session they were introduced; `cb_preflight.check_characters_technical`'s actual, current code checks the fields below, not those two names):
| Field | Note |
|---|---|
| `actingNote` or `bible.mannerisms` | at least one required — the movement-and-comedy register the v5 engine's Acting DNA block quotes verbatim (GATE3_ANIMATION_DOCTRINE.md §3, the Fidelity Law) — required for every character who actually appears (`characters`/`openingCast`) in ANY beat of the package |
| `bible.dos` | the Always list — Gate-1 review criteria (GATE3_ANIMATION_DOCTRINE.md §3); NOT read by the shipped v5 prompt itself |
| `bible.donts` | the Never list — same scope as `bible.dos` |

### Already structurally guaranteed, not part of cb_preflight's checklist (named here so "every gap named" doesn't imply these were forgotten)
- The four-anchor reference stack (rules 24/28/39) — the emitter cannot omit an anchor; Law 3 hard-blocks upstream in `cb_beats.run` before any clip renders. CORRECTED 2026-07-08 (software-wide audit): this used to read "four/five," describing the era when @Video1 (the fifth anchor, rule 26) was a live option — @Video1 was retired 2026-07-07 (rule 51), the stack is a fixed four now, opener or relay.
- The twelve standing negatives (rules 43/44, twelfth added 2026-07-13) — `cb_segprompt._standing_negatives()` is a fixed, sliced-to-twelve list; cannot ship fewer or more. CORRECTED 2026-07-08 (software-wide audit): this used to say "six," citing `_v3_negatives`, a function deleted in THE DEFINITIVE BUILD purge (rule 40) — the live mechanism and count have been eleven since rule 43/44's own ruling, this line just never caught up. CORRECTED AGAIN 2026-07-13: a real rendered take (1.B3) carried hallucinated background foreign-language audio — "no foreign-language speech" only ever covered the primary voice, so a twelfth item ("no invented background voices") was added, paired with a new positive-preservation sentence next to @Audio1 itself ("No other voices generated").
- Dialogue words never appearing in the prompt (rule 28 Layer 1.6) — regex-stripped on every free-text field, every emitter.
- The Handle Doctrine's 13s action + 2s settle split (rule 20) — now code-enforced (fixed 2026-07-06; see the duration bug this session diagnosed and fixed in `cb_beats.py`/`cb_seedance.py`).
- Settle-distinctiveness (rule 28 Layer 1.9) and the Coverage Law's join-check criterion (rule 34) — both are POST-FIRE checks on the actual rendered clip (`check_settle_distinctiveness`, `check_join_state`'s COVERAGE tier), not pre-fire field-presence checks — out of cb_preflight's scope by design; they already run automatically inside `cb_beats.run`/`walk_scene`.

## CREATIVE CONTRACT

### Per beat
| Field | Existing field name | Note |
|---|---|---|
| Humour layer | `humourLayer` (1–4) | **NEW field — not yet authored anywhere in the current package.** Presence-only check: cb_preflight verifies the field EXISTS and is an integer 1–4; it never judges whether the beat actually ACHIEVES that layer — that judgment stays the reserved showrunner verdict rule 28 protects ("no check is ever built to approximate it"). Depends on the not-yet-added Layered Humour Model bible (`shows/crystal-bears/bible/`) for what each layer actually means — the check can confirm a value is PRESENT today, but the bible must exist before anyone can confirm the value is CORRECT |
| Kid read | `kidRead` | existing |
| Adult read | `adultRead` | existing |
| Want vs need | `want`, `need` | existing |
| Emotion-as-mechanic statement | `emotionMechanic` | **NEW field — not yet authored anywhere.** Presence-only, same reserved-verdict caveat as humourLayer |
| Ensemble individuation (THE PIXAR-CRAFT GATE, rule 48, 2026-07-07) | `cb_preflight.check_beat_ensemble` → `cb_craft.check_ensemble_individuation` | **FLAG only, zero LLM, best-effort heuristic** — for a beat naming 3+ characters, checks whether each one's action-text window touches a verb from their OWN `characters.json` `lexicon.verbs`, and separately flags when 2+ characters are given the exact same verb. Deliberately does NOT flag a character simply being absent from a beat's action text (rule 46's active/background cast split already established that's the correct, deliberate fix for the cast-size word-count bug, not a fresh finding). A companion, LLM-cost repair proposal (`cb_craft.propose_ensemble_fix`, via its own CLI `--propose-fix=<beatCode>`) drafts a bible-cited rewrite for human review — never auto-applied, never wired into this manifest check itself |
| Fidelity allocation | `fidelityAllocation` (`primary`/`secondary`/`economized`) | **hard BLOCK on each of the three sub-fields independently** (THE FIDELITY-ALLOCATION LAW, rule 50, 2026-07-07 — "identity fidelity, motion boldness, and scene density compete for one budget"). `primary` must be a real character name (never blank/"none"); `secondary`/`economized` must be a name or an explicit "none". Gate-1-native as of rule 47/50 (`cb_director_schemas.FidelityAllocation`, `cb_director.scene_to_beats`'s prompt); `cb_director._finalize_beat_manifest_fields` mechanically defaults a missing `primary` from the beat's own speakers/cast (never invented prose) *(added 2026-07-12, full-codebase audit: this row was missing entirely despite the field being a live hard BLOCK)* |

### Per scene
| Check | Mechanism | Note |
|---|---|---|
| Fuzzby/Zenny ratio | computed from `characters`/`openingCast` presence across the scene's beats | **FLAG only — no stated target exists yet.** Reports the actual computed ratio; needs Julian to state what ratio (or range) counts as a PASS before this can BLOCK |
| Laugh beat per non-Heart pillar | at least one beat has `comedyMode == "BIG"` among every beat across the WHOLE package sharing this scene's own `pillar` value | *(CORRECTED 2026-07-12, full-codebase audit: this row previously described a SCENE-scoped check — "at least one beat in the scene" — but the actual code, per rule 46's own fix, is PILLAR-scoped: `check_scene_creative`'s `pillar_mate_beats` parameter pools every beat sharing a pillar across the whole package, not just this one scene's own beats. This matters because the Five Emotional Pillars are TIMECODE segments of the whole episode, not per-scene tags — more than one scene can share a pillar (e.g. Scenes 1 and 2 both fall in "The Everyday Spark"), and a quiet scene correctly passes if its pillar-mate elsewhere already delivers the laugh.)* Scenes whose `pillar` is "heart" are exempt |
| One parent-layer line | `parentLine` | **NEW per-scene field — not yet authored anywhere** |

### Per package
| Check | Note |
|---|---|
| The North Star six questions, answered in full | **Does not exist as a literal six anywhere in canon.** The crosscheck confirmed `CRYSTAL_BEARS_LOCKED_CANON.md` §0 states exactly FOUR explicit test questions ("Will they laugh out loud? Will they breathe in? Does the crystal tell the truth the bear can't yet say? Does it reach the kid and the parent at once?") plus a separately-numbered EIGHT craft laws below it — no itemized six. cb_preflight checks for a new package-level field (`northStarAnswers`) and reports it BLOCK-missing, but the exact six questions need Julian's own definition before this check can mean anything more precise than "a field exists" |

## Data-quality finding (not one of the requested fields, surfaced because it affects the "per non-Heart pillar" grouping)
The current package's `pillar` values are inconsistently cased/worded across scenes: `spark`, `Deepening
Feeling` (scene 4), `deepening` (scene 5), `connection`, `heart`, `ripple` — scenes 4 and 5 both appear to mean
"The Deepening" (Pillar #2) but are spelled differently. cb_preflight does a case-insensitive substring match
so this doesn't break the Heart-pillar exemption, but the underlying inconsistency is worth a cleanup pass at
the source (the Director/Gate-1 authoring step) separately from this ticket.

## Fallback removal — CLAUDE.md rule (Julian, 2026-07-06): "remove every generic fallback"

Confirmed and fixed (2026-07-06 sweep, `cb_segprompt.py`/`cb_seedance.py`): every place a prompt-authoring
function silently substituted generic boilerplate for a missing beat field now raises `ManifestFieldMissing`
instead — named exactly, caught by `cb_beats.run`/`gate3_prepare` as a hard BLOCK, never folded into a
still-shippable prompt. See CLAUDE.md rule 37 for the full sweep report (what was fixed, what's a different
category and deliberately left alone).

## The Gate-1 external review standing rule (Julian, 2026-07-06)

Gate 1 is never signed inside the Studio alone. The storyboard exports as a single document for Julian's
creative review OUTSIDE the studio first; his sign-off follows that review, every scene, every time. (Export
mechanism: follow-up ticket — this rule is recorded as doctrine now; the code to produce the export document
is not yet built.)

## Where the detail lives
- **`engine/cb_preflight.py`** — the one command. `python3 cb_preflight.py <package.json>` — per-beat PASS/FAIL
  across both contracts, every gap named, plus per-scene and per-package sections. `--preview-dialogue-fix`
  previews (never writes) the mechanical dialogue-verbatim auto-fix.
- **`engine/cb_craft.py`** — THE PIXAR-CRAFT GATE (rule 48, 2026-07-07): the `CRAFT_RUBRIC` constant and
  `score_scene_craft` (LLM dual-read scorer, invoked explicitly via `--score`, never auto-run by `cb_preflight`
  since it costs real API calls), `check_ensemble_individuation` (the zero-cost check wired into
  `cb_preflight.check_beat_ensemble`), and `propose_ensemble_fix` (a bible-cited repair proposal, via
  `--propose-fix=<beatCode>`, never auto-applied).
- **`engine/cb_script.py`** — the deterministic screenplay parser; `dialogue_lines()` is the ground truth both
  `cb_director.enforce_verbatim` (authoring time) and `cb_preflight.check_scene_dialogue_verbatim` (standing,
  re-runnable) compare against.
- **CLAUDE.md rule 37** — the numbered, dated ruling this document mirrors, plus the fallback-removal sweep report.
- **CLAUDE.md rule 48** — THE PIXAR-CRAFT GATE: the dialogue-verbatim gate, the craft rubric, and the
  ensemble-individuation check, including the parser bug (`cb_script.py`) found and fixed the same session.
- **`shows/crystal-bears/bible/`** — read-only canon (North Star, Layered Humour Model, Character Voice Bible,
  Five Pillars) the package builder must consult. Does not exist yet as of this writing — Julian is adding it.

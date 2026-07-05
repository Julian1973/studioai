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
| Single gag arc | best-effort structural heuristic | **FLAG only, not a hard BLOCK** — cb_qa.py's own comments already admit "Law 1's other half (one gag arc per beat)... this lint cannot cover at all." cb_preflight checks for exactly one stated hold and no more than one `script_gag_lock_id`/climax marker as a proxy; it is not a semantic guarantee |

### Per scene
| Check | Mechanism |
|---|---|
| Plate passes | `cb_qa.check_plate` (crystal shape, no characters in frame) |
| Ambient bed present | `ambientBed` field on the scene. Word-for-word identity across every beat in the scene is **already structurally guaranteed by construction** (`_v3_ambience`/`_v4_references` read straight from the scene dict, never per-beat — rule 35) — reported STRUCTURAL, not re-checked |
| Locations cache in sync | `tools/sync_scenes.py --check` — confirmed live 2026-07-06 (this is the exact tool that was blocking every beat's fire this session before the sync ran) |
| Vocabulary pass | `cb_qa.check_scene_vocabulary` (canon/banned_vocabulary.json) |

### Per character (new tier — the crosscheck caught this was missing from the first draft)
| Field | Note |
|---|---|
| `actingRule` | one-line acting essence in `characters.json`'s `bible` (rule 28 Layer 2.6) — required for every character who actually appears (`characters`/`openingCast`) in ANY beat of the package |

### Already structurally guaranteed, not part of cb_preflight's checklist (named here so "every gap named" doesn't imply these were forgotten)
- The four/five-anchor reference stack (rules 24/25/28) — the emitter cannot omit an anchor; Law 3 hard-blocks upstream in `cb_beats.run` before any clip renders.
- The six standing negatives (rules 25/28/30) — `_v3_negatives` is a fixed, sliced-to-six list; cannot ship 5 or 7.
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

### Per scene
| Check | Mechanism | Note |
|---|---|---|
| Fuzzby/Zenny ratio | computed from `characters`/`openingCast` presence across the scene's beats | **FLAG only — no stated target exists yet.** Reports the actual computed ratio; needs Julian to state what ratio (or range) counts as a PASS before this can BLOCK |
| Laugh beat per non-Heart pillar | at least one beat in the scene has `comedyMode == "BIG"` | scenes whose `pillar` field is NOT "heart" (case-insensitive) must have at least one BIG-mode beat. Scene 7 (pillar "heart") is exempt |
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
  across both contracts, every gap named, plus per-scene and per-package sections.
- **CLAUDE.md rule 37** — the numbered, dated ruling this document mirrors, plus the fallback-removal sweep report.
- **`shows/crystal-bears/bible/`** — read-only canon (North Star, Layered Humour Model, Character Voice Bible,
  Five Pillars) the package builder must consult. Does not exist yet as of this writing — Julian is adding it.

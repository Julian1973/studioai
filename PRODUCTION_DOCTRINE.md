# THE PRODUCTION DOCTRINE — CRYSTAL BEARS, THE WHOLE MACHINE, ONE PAGE

Read this first. Full mechanical detail lives in `CLAUDE.md` rule 28 (the numbered constitution) and
`REPLICATOR.md` (the escorted-run gate map); this page is the same doctrine, told straight through, the way
Julian described it the night it locked (2026-07-05). If this page and either of those ever disagree, that's
a bug — fix the disagreement the day it's found (CLAUDE.md rule 7).

## The hierarchy

**Episode → Scene → Beat.**

A **scene** is a bubble: three locked constants — scene plate, ambient bed, style law — held verbatim across
every beat inside it. A **beat** is one gag arc, 15 seconds: 13s action + 2s settle. A scene boundary is a
full reset: new plate, new bed, a fresh canon-generated anchor keyframe, relay depth back to zero. Nothing
about the beat laws below is scene-specific — they apply identically inside every bubble.

## The joins — the week's hardest-won truth

Beats join by **cut, not freeze**. Nine renders proved frame-freezing is both impossible on this surface and,
when approximated, boring — Julian's eye caught what no gate did.

Every beat declares its own **junction type**:
- `intentional_next_shot` — THE DEFAULT. A new gag arc, a fresh camera setup, energy already in frame.
- `seamless_continuation` — ONLY when the director's cut explicitly says one shot continues unbroken across
  the boundary. Omission is never read as this — it's always the rarer, declared case.

Each beat opens on a **new angle within the bubble**, close to where the last beat ended, motivated by
eyeline or motion — Zenny's head-turn tracking Fuzzby is the house bridge. Never a relocation, never a
mid-scene establishing wide (the wide belongs to the scene's opening beat only).

**What carries across the cut is state, not framing.** The beat's own declared `carryMarks` (a short phrase —
"the moustache, the pollen on their legs, the warm light" — never a full sentence) is HARD-GATED by the
join-check; everything else visible in the anchor (a bee casually holding pollen, say) is advisory only,
logged as a flag, never blocking.

The **raw harvested settle frame** is the state reference for a cut — no re-mint. Re-mint (the NB2 cleanup
pass) is retained only for a declared `seamless_continuation` join, where @图1 really is used as literal
first-frame pixels.

## The prompt — v4, locked

Six-line reference contract, one job each:
- **@图1** — for a cut (the default): a state-reference clause naming what carries (identity, carryMarks,
  lighting, position) plus the spatial leash ("open on a fresh camera setup within the same space, close to
  where @图1 shows the characters — the camera moves, the world does not"). For a seamless join: the locked
  opening frame, exactly.
- **@Video1** — motion energy and action continuity ONLY. Never camera framing, shot size or composition —
  the camera setup comes from THIS beat's own direction. (Fixed 2026-07-05 lock-in night — the earlier
  wording left framing implicitly copyable from the previous clip.)
- **Character turnarounds** — identity anchor, name-welded directly to the slot ("Fuzzby is the bee from
  @图2"), zero physical description anywhere.
- **Scene plate** — the duration anchor, the environmental constant for the whole clip.
- **@Audio1** — the sole vocal source, covering dialogue, hums and sing-song alike; drives the generation
  directly, never stitched on after (no post voice swap, ever, even in a future two-step fallback).

One continuous `prompt` field: the opener, character bindings, an OPEN-ON sentence naming who the camera
opens on and their mid-motion state (cut beats only — the Coverage Law's bridge, stated concretely), then a
labelled timing clock whose closing segment is always **"settle in character:"** — the beat's own `endState`
verbatim, never a generic idle-life placeholder, never a restatement of the previous beat's pose. `acting_rules`
is its own top-level field. `continuity` names the beat's own carry marks plus the show's warm light.
`prohibited` merges the beat's own staging list with the six standing negatives — Crystal World Rule and Wing
Law, always.

Dialogue words never appear in the prompt. **Erratic in character, precise in choreography**: every manic
action is a named gag with cause and consequence (rockets, brakes too late, loops once, stops) — the model
executes actions and butchers adjectives, so adjective-chaos ("wildly," "crazily") is banned as unreadable.

## The gates — machine vs showrunner

The machine checks what it can check: state continuity on carryMarks, spatial adjacency (Coverage), Clip QA,
gag-element presence, the flag-only prompt-law lint. Julian checks the only things that matter and that no
gate owns: **does it flow, is it funny, does the four-year-old watch it again.** This is a reserved verdict,
not a gap in the machine — no check is ever built to approximate it. The Layered Humour checklist rides above
it all: Fuzzby's chaos beats, Zenny's deadpan with its pause protected (the settle is where her look
breathes), the laugh-so-hard-they-miss-it ambition intact.

## The one-render economy (locked 2026-07-05, the full-reset night)

One fire per artifact — the scene plate, a voice take, a keyframe, a beat render. Never a batch of exploratory
seeds as the default. On a failed gate: ONE automatic re-fire, never blind. If that re-fire also fails: a HARD
STOP with a diagnosis naming the layer at fault (keyframe / brief / reference / take, rule 3) — never a third
roll.

The voice pass is the same economy, stated explicitly: ONE directed V3 take per beat, never a batch of
candidate reads. Julian's ear either approves it, or names the single correction for the one permitted
re-fire. There is no "pick a favourite among several" step for voice — the same discipline the felt-intent
gate already holds the beat render to.

This is DOCTRINE as of tonight; the retry/hard-stop wiring itself is not yet code-enforced —
`cb_beats.run`/`fire_next_beat`'s historical multi-seed default and the Studio's seed-picker panel still exist
in the codebase unchanged. Wiring the economy into the code is a follow-up ticket for when the new script
arrives, not done as part of the reset.

## The loop, and the full production line — the canonical stage map

fire → machine gates → Julian's eye → sign → harvest → cut into the next beat, which declares its own
junction type. Escorted through Scene 1 by hand (`cb_beats.fire_next_beat`); `cb_replicator.walk_scene` walks
it thereafter under the identical laws — nothing beat-specific lives in its own code, only in the beat data.
That loop is Stage 5 below. The full line, script to master:

Every stage names its gate holder. The machine checks; Julian signs. Nothing self-advances past any gate,
ever (CLAUDE.md rule 1).

| Stage | What happens | Gate holder |
|---|---|---|
| **0 — Script-in** | The script is the SOLE story source. Nothing downstream invents story; everything traces back to this. | — (the input) |
| **1 — Beat package → Gate 1** | The script becomes the beat package (storyboard): scenes, beats, cuts, dialogue, junction types. | Julian signs Gate 1 |
| **2 — World and cast** | The scene plate is built, then checked (`check_plate`) against the Crystal World Rule (natural, organic, never cut or arranged); character turnarounds verified against canon; the scene's ambient bed locked — word-for-word identical across every beat in the scene from here on (the Scene Bubble Law). | The machine checks (`check_plate`); folds into Gate 2's review, no separate sign-off |
| **3 — Voice pass** | One directed V3 take per beat, per the Character Voice Bible (cadence, register, the per-character V3 tags). The one-render economy applies here explicitly (above). | Julian's ear approves, or names the single correction |
| **4 — Gate 2: anchor keyframe** | One anchor keyframe per SCENE (not per beat — a relay beat never gets its own keyframe), 2K, centre-safe, per-character action-state QA (does the pose show what the story says is happening). | Julian signs Gate 2 |
| **5 — Gate 3: the escorted walk** | `cb_replicator.walk_scene` fires one render per beat, standard tier. Machine gates: Clip QA, carryMarks-scoped state continuity, spatial adjacency (Coverage), settle distinctiveness, the prompt-law lint. Then the reserved verdict — does it flow, is it funny, does the four-year-old watch it again. | Machine gates, then Julian's felt-intent sign-off, PER BEAT |
| **6 — Gate 4: retakes** | A retake fires only on Julian's own verdict — never a machine flag alone. One variable changes per re-fire (the retake protocol) — never re-roll blind hoping something different happens. | Julian names what's wrong and what changes; the machine never retakes on its own initiative |
| **7 — Gate 5: post** | Settle-trim so the cut joins on living motion, not hold-into-hold (the JOIN CONTRACT). Beats assembled; the ambient bed continuous across the whole scene; music and grade pass; two masters delivered — the 16:9 feature master and a centre-safe 9:16 derivative. | Julian's final-cut approval |

A stage marked "the machine checks" is still a real gate — it just doesn't need Julian's own eyes on every
single instance, the way Gate 1/2/3/4/5 do. Nothing in this table skips a step by being fast, cheap or
automatic.

Directing goes in. Animation comes out.

## Where the detail lives

- **CLAUDE.md rule 28** — the numbered, code-cross-referenced constitution (this page's source of record).
- **REPLICATOR.md** — the escorted-run gate map, step by step, with the exact function each step calls.
- **CLAUDE.md rules 29-36** — the dated case-by-case history of how this doctrine was arrived at (why each
  piece exists, not just what it says).
- **MORNING_HANDOVER.md** — the state of every beat, right now, and what to do next.

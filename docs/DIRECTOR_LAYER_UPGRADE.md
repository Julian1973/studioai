# DIRECTOR LAYER UPGRADE — defect report + spec for the creative room
**To:** Codex (studioai) · **From:** Claude (prescriber) · **Date:** 2026-08-09
**Process law:** defects go to the system with the why. No hand-fixed outputs.
**Attachment:** `hold-cap-fix.patch` (applies clean at 2f8d878; run the cb_departments
and render test suites after applying).

---

## DEFECT 1 — The system structurally denies every joke its landing (patch attached)

Three sites, one failure. Our render evidence ("landed, looked great, lacked pace,
comedy very stuttered") plus the entire absorbed corpus says a comedy button needs a
**held landing of ≥ 2.0 seconds** to read. The code forbids it everywhere:

1. `engine/cb_departments.py:237` — schema caps `recoveryHoldSec` at **≤ 1.5s**.
   A director literally cannot express the hold a BIG gag needs.
2. `engine/cb_departments.py:879` — the LLM instruction says "a readable
   recoveryHoldSec **of no more than 1.5 seconds**." The director is being *taught*
   to truncate landings.
3. `engine/cb_render.py:2618` — the render path hardcodes `recoveryHoldSec: 0.8`
   for every gag arc regardless of mode. **Every button the studio has fired had a
   0.8-second landing.** This alone plausibly explains "stuttered."

**Fix (in the patch):** cap raised to 3.0s; validator added — `BIG` arcs refuse
< 2.0s ("'briefly' is not a duration"); instruction text now teaches ≥ 2.0s for BIG
and unit-ending arcs, 0.6–1.5s for SMALL mid-chain arcs; render default becomes
mode-aware (BIG → 2.2, SMALL → 1.0). **Follow-up beyond the patch:** a missing
hold should be a validation *error*, not a silent default — silent defaults are how
this defect survived every review.

## DEFECT 2 — Missing direction fields (spec; implement in cb_departments schemas)

The v2 room's gag anatomy is right. These fields from the AAA Prompt Standard are
absent, and each absence maps to an observed failure class:

| Field | Spec | Failure it prevents |
|---|---|---|
| `geography` | Scene-constant list of screen-direction facts ("corridor runs frame-left/west to frame-right/east; X never reverses"), emitted **verbatim into every shot of the scene** | silent left/right flips the audience feels but can't name |
| per-stage `cause` | Every timeline stage names what caused it from the prior stage | floaty, unmotivated motion |
| per-stage `endState` | Every stage ends in a describable frame; final stage's endState is the next shot's opening reference | wandering long takes, broken relay seams |
| `motionVocabulary` enforcement | Per-character belongs/banned verb lists as canon data; a banned verb near a name is a validation error | generic performance — "walks in" instead of character |
| `styleParagraph` injection | The versioned canonical style constant is **compiler-injected verbatim**, never LLM-authored per shot | look drift between shots and between keyframe mints and renders |
| `negativeSpace` on keyframe briefs | "Hold empty space frame-X for Y entering at Ns" | centred beauty compositions that destroy planned reveals |

Reference implementation for all six exists in `engine/` (beat-engine drop): the
IR schema in `shots/S1_SH1A.json`, enforcement in `beat_engine.py` preflight,
data in `grammar_pack.json`.

## DEFECT 3 — Doctrine conflict: "no permanent screen sides" vs the geography ledger

Gate 4 doctrine says "no permanent screen sides." Correct at *treatment* level,
dangerous at *shot* level. Ruling to encode: the treatment may choose any geography
it likes; once chosen, the scene's geography ledger is law for every shot in that
scene, and a side-switch must be an explicit, staged re-establish — never an
accident of generation.

## UPGRADE 1 — The exemplar library is all stick, no carrot

The room learns from EX-005, a *rejected* package. Ingest
`engine/shots/S1_SH1A.json` (the golden fixture: chase → crash → gymnastic finish
→ held "Nailed it" button, with causal stages, numeric 2.2s hold, geography and
end states) as the first **positive** exemplar so Gate 6 can compare candidates
against an approved shape, not only against a failure.

## UPGRADE 2 — The blind duel (acceptance test for "does the room write magic")

Run the v2 room end-to-end on the S1.SH1A script beats. Present its shot direction
and the golden fixture to Julian at SEE sign-off unlabeled. Julian judges which is
funnier on paper. Room wins or ties → the layer is proven and the engine compiles
its output. Room loses → the diff between the two files is the next upgrade spec.
Either outcome converts taste into system.

## VERIFICATION CHECKLIST
- [ ] Patch applied; `test_cb_departments.py` + render suites green (update any test
      asserting the 1.5 cap or 0.8 default — those assertions encoded the defect)
- [ ] A BIG gag with 1.0s hold is REJECTED at validation with the landing message
- [ ] A missing hold errors loudly instead of defaulting
- [ ] Schema fields from Defect 2 present and enforced; geography emitted verbatim
      across a scene's shots
- [ ] Golden fixture ingested as positive exemplar
- [ ] Blind duel scheduled on S1.SH1A

# THE UX/UI HAS TO MATCH THE NEW PROCESS

Julian, 2026-07-26: *"the changes behind haven't been updated in the ux ui"* — then, plainly:
**"The ux ui has to match the new process."**

He is right, and he diagnosed it before I did. I spent the evening fixing symptoms — a missing
button, a wrong label — when the actual defect is that the engine was restructured over weeks
and the Studio was patched at its edges instead of reconciled with it.

This is the same class of bug this project has hit before and named: **two tables, one truth.**
Last time it was two chair tables. Now it is the engine's stage contract and the UI's idea of it.

---

## THE EVIDENCE, FROM JULIAN'S OWN SCREEN

Shot panel for S1.SH1, as it actually renders today:

| his section | prepare | approve | fire |
|---|---|---|---|
| 01 · STORYBOARD | — | ✔ APPROVED | — |
| **02 · OPENING FRAME** | **✗** | **✗** | **Generate** |
| 03 · SPECIAL REFERENCES | — | — | optional |
| 04 · VOICE | — | **APPROVE DIRECTION** | — |
| 05 · DIRECTION | **PREPARE** | ✗ | — |
| 06 · PROMPT | — | — | unavailable |

Three sections, three different shapes. **02 is the one with a fire button and no way to
authorise it.** The engine refuses it (`_require_approved_department`, stage `cinematography`)
and the panel offers no path to satisfy that requirement — so the only button it shows can
only ever fail.

Julian hit exactly that wall, twice, and said "I'm lost" and "I don't see approve". He was
not missing anything. It is not there.

I unblocked him by calling `department-prepare` and `/api/department-decide` from the command
line. **That is a workaround, not a fix, and it must not be treated as one.**

## THE NAMING, WHICH IS PART OF THE SAME PROBLEM

I handed him a table of engine names — "Cinematography", "Look Development" — while his screen
says **02 · OPENING FRAME**. His correction: *"please refer to the numbers and the real stage
names, stage three is opening frame."*

Nobody should have to translate between the engine's vocabulary and their own screen. The UI's
names and numbers are the real ones. The engine's internal stage keys are an implementation
detail and belong nowhere a human reads.

## THE REQUIREMENT

**One reconciliation pass, not more patches.**

1. **Every stage gets the identical row shape**: prepare → read → approve → fire. No stage
   exposes a fire button without the authorisation path that the engine demands behind it.
2. **Driven from the engine's own roster** (`cb_departments.DEPARTMENTS` / `cb_render.
   _DEPARTMENT_WORKERS`), never hardcoded in `app.html` — hardcoding is precisely how the two
   drifted apart, and `test_studio_chair_table.py` already exists because of the last time.
3. **Julian's names and numbers**, everywhere a human reads: the panel, the engine's refusal
   messages, and any document. "Opening frame", not "keyframe"; "02", not "stage 3".
4. **A test that fails when they drift again** — extend `test_studio_chair_table.py`, which
   already binds labels to the engine table, to also bind the ROW SHAPE: every stage the engine
   gates on must expose prepare and approve in the UI.

## WHAT IS ALREADY TRUE AND MUST NOT BE BROKEN

- The engine's refusal is CORRECT. `no approved department direction = no provider call` is a
  real protection that has saved money before. The fix is to give the UI a way to satisfy it —
  never to weaken the gate.
- The two-stage contract (prepare is free and text-only; fire spends) is the right shape. The
  UI should make that obvious, not hide half of it.

## STATE AT HANDOVER

- Scene 1 storyboard: **built and passed review** (10 shots, `Ep1_scene1_storyboard.json`)
- Scene 1 plate: **approved**
- S1.SH1 opening-frame direction: **prepared and approved** (via CLI — see above)
- S1.SH1 opening frame itself: **not yet generated** — Julian to press Generate on 02

---

# THE RECONCILIATION, DONE — 2026-07-26

## WHAT THE AUDIT ACTUALLY FOUND (measured, before anything was changed)

The engine hard-gates exactly three stages behind an approved specialist direction —
confirmed by reading every `_require_approved_department` call site in `cb_render.py`, not
from memory:

| Julian's section | engine gate | what the row offered before | after |
|---|---|---|---|
| 01 · STORYBOARD | none | review + sign-off | unchanged |
| **02 · OPENING FRAME** | **cinematography** (openers) | **Generate only — no prepare, no approve** | **prepare → read → approve → Generate** |
| 03 · SPECIAL REFERENCES | none | uploads | unchanged |
| 04 · VOICE | **voice** | Approve only — no Prepare when nothing was prepared | prepare → read → approve → Generate |
| 05 · DIRECTION | **animation** | prepare → read → approve | same, now from the shared block |
| 06 · PROMPT | reads 05's approval | names its blocker | now names it as "05 · DIRECTION" |
| 07 · FIRE | animation (spends; 05 authorises) | locked | locked, and names 05 by Julian's own name |
| 08 · REVIEW | none | take decisions | unchanged |

02's authorisation path did exist — buried two levels down, inside a collapsed
"Departments & technical detail" disclosure, under the word "Cinematography". Julian was
not missing it in the row. It was not in the row.

Three further defects fell out of the same audit and are fixed here:

1. `attachDepartmentPanel` was the only thing that ever loaded the cinematography record,
   and it mounts AFTER the row renders — so `deptLocksGeneration` was handed an undefined
   readiness on first paint and **Generate rendered ENABLED on a shot the engine refuses.**
2. `/api/shot-approve-stage` was hardcoded to `("voice", "animation")` — the two sections
   that happened to have rows. 02 could not have been approved from its own row even if the
   row had offered to.
3. `department_readiness` labelled its own refusal `f"{stage} readiness check"`. That string
   is printed verbatim onto the row and into the disabled button's tooltip, so the engine's
   stage key was on Julian's screen inside the sentence telling him what to do about it.

## WHAT CHANGED

- **One table, in the engine**: `cb_departments.SHOT_PANEL` — each section's number, Julian's
  own name, the engine stage it is gated by, and which section *authorises* that stage.
  `panel_label()` / `panel_section()` / `authorising_stages()` are the only readers anyone
  needs. It is served with the per-shot state on `/api/shot-departments`.
- **The panel reads it**: row numbers and titles, the shared prepare/approve block, the
  blocked-row copy, and the disabled-button labels all come from that table.
  `app.html` holds no stage list of its own — a test refuses one.
- **One row shape**: `authBlockHTML(stage, shotId)` builds prepare → read → approve for every
  gated section. All three now behave identically across all five states a direction can be
  in (nothing prepared / candidate pending / approved+current / approved-but-stale / loading).
- **Julian's names everywhere a human reads**: the two gate refusals, the readiness reason,
  the approve-endpoint's own message, and every row label.

## THE GATE IS NOT WEAKENED

Nothing was removed, loosened or bypassed. `_require_approved_department` still refuses on
exactly the same conditions; its message changed, its behaviour did not. The disabled
Generate button is still only the visible explanation — the backend refusal is still the
protection. What changed is that the screen now offers a way to *satisfy* it.

## HOW IT WAS VERIFIED (no paid provider call was made, of any kind)

- Both suites before and after. `test_studio_chair_table.py` 5 → 15 tests;
  `test_cb_render_department_gate.py` 37 → 38. The 8 pre-existing `test_cb_intent.py` /
  `test_cb_engine.py` failures (old Scene 1 production data) are untouched and still fail.
- **Mutation-tested**: reintroducing the original defect (removing 02's auth block), gating a
  stage with no section, and putting the engine key back in the refusal each make a specific
  new test fail. A test that cannot fail binds nothing.
- The row logic was executed headlessly in node against every direction state; all three
  gated sections produced the identical shape.
- Read back from the running server on 127.0.0.1:8765 — the served page, the panel table on
  `/api/shot-departments`, and the real refusal text on `/api/departments`.

## STILL OPEN AFTER THIS PASS

- `cb-studio/test_static_hardening.py` fails 2 of its file-existence checks
  (`Ep1_The_Adventure_Begins_Final_v2.txt`, a plate candidate PNG). Pre-existing, from
  tonight's separate script/plate reset — untouched by this work, not fixed here.
- Row *content* is still bespoke per section (the frame row's four sources, voice's player,
  fire's disclosure). Only the number, the name, and the authorisation shape are driven from
  the engine. Making the whole row data-driven would be a rewrite of the runner, not a
  reconciliation, and was not attempted.
- The collapsed "Departments & technical detail" panel is unchanged and still the place to
  *edit* a direction before approving. The rows now make it optional rather than mandatory.

## STILL OPEN, SEPARATE FROM THIS

- `cb_creative` prints unflushed → the Studio showed "Starting…" for a real 17-minute run
- No timeout on the Anthropic path → a stalled call hangs indefinitely
- `performanceModes` empty on all 10 shots → the shot-density rule cannot fire
- 8 tests woke when the beat package returned and assert against the OLD Scene 1 data

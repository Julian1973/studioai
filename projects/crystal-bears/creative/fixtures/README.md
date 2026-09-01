# Craft fixtures — known-good and known-laboured prompts

These are REAL compiled prompts kept as calibration data, not examples to copy.

## SH2_LABOURED_FIXTURE.txt
S1.SH2's shipped prompt, 2026-07-25. Technically correct and dramatically immobilised —
an external craft review's words: *"the prompt repeatedly tells Seedance to settle, anchor
and hold. The model is therefore doing exactly what it is being asked to do."*

Measured against the approved SH1 keeper:

| | SH1 keeper (approved) | SH2 (laboured) |
|---|---|---|
| stasis terms per 100 words | 1.94 | **3.21** |
| `two-shot` | 0 | **4** |
| geography contradiction | none | Zenny anchored to her flower **and** hovering beside Fuzzby |

`cb_render.check_stasis_load` is calibrated on exactly this pair: it must return ZERO
advisories on the keeper and must fire on this fixture. `test_cb_render.py` asserts both,
so the check can never drift into flagging good work or waving through laboured work.

NEVER FIRE THIS PROMPT. It is kept as evidence.

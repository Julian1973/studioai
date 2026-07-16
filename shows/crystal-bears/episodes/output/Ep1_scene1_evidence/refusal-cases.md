# Matrix cases 4-6 — refusal evidence (real cb_render, zero spend, sandbox copy)
_run 2026-07-16T10:10:27 · source package untouched (sandbox episode EpVAL, deleted after each case)_

## Case 4: relay fires before source approval
- PASS — REFUSED as designed: REFUSED — 1.B1.S2 relays off 1.B1.S1, which is not approved+harvested yet (status: designed) — Julian's eye comes first, always

## Case 5: failed-validation package cannot fire
- PASS — REFUSED as designed: REFUSED — the production package failed design validation; fix the design, never fire past a red validator

## Case 6: dialogue shot without its voice track
- PASS — REFUSED as designed: REFUSED — 1.B1.S1 has dialogue but no voice track (Law 5: voice first, no native-voice fallback)

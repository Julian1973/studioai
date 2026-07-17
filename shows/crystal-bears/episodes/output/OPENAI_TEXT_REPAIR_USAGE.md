# OpenAI text-repair usage — Ep1 Scene 1 (2026-07-16)

Recorded separately per Julian's instruction: "zero media spend" is correct for this session's
repair work, but it is NOT zero total provider spend — the automated observable-direction repair
loop makes real OpenAI text calls.

## Actual usage

| Run | Purpose | Calls | Model | Outcome |
|---|---|---|---|---|
| 1 | Abstract→observable repair (crashed at prompt-refresh, results lost in memory) | 6 | gpt-5.5 | paid, discarded |
| 2 | Abstract→observable repair (revision 3) | 6 | gpt-5.5 | 6/6 passed attempt 1 |
| 3 | Field-budget compression repair (revision 4) | 6 | gpt-5.5 | 6/6 passed attempt 1 |
| 4–5 | Option-D recompiles (revisions 5–6) | 0 | — | zero-LLM |
| **Total** | | **18 completions** | | |

Each call carried roughly 700–1,000 input tokens (field + protected continuity context) and
60–120 output tokens — order of magnitude **12,000–20,000 total tokens**.

## Estimated cost — explicitly unconfirmed

The billing profile (`engine/billing_profile.json`) carries confirmed entries for fal and a
pending entry for ElevenLabs only; **no OpenAI rate is confirmed**. At any currently published
GPT-5-class list rate this usage lands **well under $1 (est. low single-digit cents to ~$0.50)**,
but per the standing billing discipline no figure here is presented as a verified account cost.
Closing this properly means adding an OpenAI entry to the billing profile from the account's own
confirmed plan — pending Julian.

Design-time note: every repair call is labelled (`repair_<shotId>_<field>`) via cb_llm, and each
repair records its model + prompt version in the package's `repairLog`. cb_llm does not currently
capture per-call token usage; adding that capture is the natural follow-up if OpenAI spend is to
be ledgered like fal/ElevenLabs media spend.

---

## Creative Room build (2026-07-16, CREATIVE ROOM vNEXT)

Text-completion usage for the creative-room engine (cb_creative.py) — episode vision + 5 scene runs
(the polluted maiden Scene-1 run included) across 4 role passes each plus Showrunner reviews/revisions:

| Call type | Model | Count (approx) |
|---|---|---|
| Episode vision | gpt-5.5 | 1 |
| Scene direction (Director, incl. 3-interpretation exploration) | gpt-5.5 | 6 |
| Shot design + cinematography passes | gpt-5.5 | 12 |
| Voice design | gpt-5.5 | 6 |
| Showrunner reviews + internal revisions | gpt-5.5 | 9 |
| **Total** | | **~34 completions** |

No confirmed per-token OpenAI rate is on file for this billing profile — usage is recorded, cost is
NOT invented. Order-of-magnitude judgement only: comparable to the repair-loop batch above (well under
$1–$5 range for gpt-5.5 structured completions of this size). Zero media provider calls; zero Seedance
tokens issued; zero fal/ElevenLabs spend.

---

## Creative Room process v2 rebuild + proof reruns (2026-07-17)

Four real scene runs through the rebuilt 7-gate process (Scene 1 with the ambition brief;
Scenes 2/3/9 with no hints): per scene ~8-10 gpt-5.5 structured completions (Gate 0 canon
proposal where cast gaps exist, Gate 1 joint treatments, Gate 2 selection, Gate 3 beats,
Gate 4 shot conference, Gate 5 performance + voice, Gate 6 adversarial review, production
detail) ≈ **~38 completions total**. Rate unconfirmed — usage recorded, cost not invented.
Zero media provider calls; zero Seedance tokens; zero fal/ElevenLabs spend.

## Creative Learning System (2026-07-17): zero LLM calls — the system is deterministic
governance code; classification proposals are mechanical. No media, no tokens.

## Storyboard-schema checkpoint: production-detail-only regeneration (2026-07-17)

One real Gate-5 production-detail pass (cb_llm.structured, ProductionPass schema) against
Candidate 2's 7 frozen Creative Shot Cards, authoring intendedDurationRange per shot from
already-approved physicalPerformance/animationTiming/dialogue timing. 1 completion. Gates
0-4 did not run (no treatments, no beats, no shot conference, no adversarial review — proven
by test). Zero media/provider spend.

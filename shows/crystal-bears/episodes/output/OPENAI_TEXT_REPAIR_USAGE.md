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

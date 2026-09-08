# Project model routing and cost evidence — 8 September 2026

Implemented for the project production engine, preserving the existing legacy desk.

## Behaviour

New direction configurations offer task routing on the same workspace account:
- Creative direction: GPT-6 Astra; $2 conservative reservation per call.
- Exact prompt wording maintenance: GPT-5.6 Terra; $0.50 per call.
- Explicit workflow explanation without a selected shot: GPT-5.6 Luna; $0.10 per call.

These are configurable reservation defaults, not predicted invoices or proof of model access. Existing single-model services remain pinned until changed. Each queued job freezes its route, model, estimate and credential revision. No paid fallback or retry is automatic. Free-form creative requests stay with the creative director. Routine responses cannot change typed shot decisions; assistant responses cannot revise shots. Human proposal and media approval remain required.

The service form exposes all routing choices. Production shows configured connections, missing services, actual model used and partial token-cost evidence. Optional review does not block generation.

Director context strips old outcome files and version history from the selected shot while retaining the full script, bible, assets and scene geography. No cheaper route discards story context. The plan still populates the pipeline and advances to the first SEE candidate.

## Accounting

OpenAI Responses usage is recorded before production validation. Successful parsed responses retain input, output, cache-read and cache-write counters. Standard list-price estimates are calculated only for the three exact model IDs, complete consistent counters, standard service tier and short inputs (at most 100,000 tokens). Rates expire after 31 December 2026. Unknown models, incomplete counters, longer input and other service tiers remain explicitly unpriced. This is not an account invoice: discounts, residency surcharges and other provider billing are not reconciled.

Cache writes replace their ordinary-input charge; they are not double counted. Reasoning output is already included in output tokens. Committed allowance never drops below the initial reservation; a higher measured list-price estimate raises commitment. HEAR reserves its per-request voice estimate for every dialogue line, since each line invokes the provider. Media without measured price retains its configured estimate. Failed or lost responses can still lack usage; their existing conservative recovery rules remain.

Sources checked:
- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/guides/prompt-caching
- https://developers.openai.com/api/reference/cli/resources/responses/methods/create

## Verification and live readiness

- 231 regression tests passed before the final voice reservation refinement.
- 53 targeted production/model-policy tests passed after it; final policy suite: 25 passed, including per-line voice reservations.
- Project browser flow passed including routing controls, setup visibility, SEE/HEAR/request/WATCH, edits preserving voice, Gemini review, references, project isolation, timeline and mobile layout.
- No paid generation, video upload or artistic benchmark was run.

Live inspection found Crystal Bears still uses the legacy project desk; the project workspace has zero BYOK connections and no saved service bindings. No credentials or production records were changed. Episode 3's script was not supplied yet.

Before running Episode 3 on the new engine, use the existing reviewed Upgrade workspace flow to copy Crystal Bears assets and preserve older episodes as archives, connect provider accounts through Workspace connections, check account access and choose Project services, then import Episode 3 and approve its allowance. Gemini review is optional and needs its own account. This document does not certify a live provider test or broadcast quality.
